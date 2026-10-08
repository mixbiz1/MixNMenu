"""Output reads stored documents; draft labels never become business mutations."""
import copy
import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow, call
from test_batch2a_contract_import_cost import confirmed_contract
from test_batch2a_gui_permissions import ui_adapter
from test_contract_document_v1 import assert_pdf_body_preserved, source
from contract_document_templates import FORMS, render
from financing_document import document_html, export_contract_pdf, print_contract
from audit_service import AuditEvent
import models


@pytest.mark.parametrize('form',list(FORMS))
@pytest.mark.parametrize('status',['DRAFT','CONFIRMED','CANCELLED'])
def test_all_form_states_pdf_print_labels_and_database_are_immutable(flow,qt_application,tmp_path,form,status,monkeypatch):
    client,factory=flow
    contract=confirmed_contract(client,FORMS[form][1])
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':form})
    assert row['document_id']==1 and row['version']==1
    if status=='CONFIRMED': row=call(client,'POST',f"/contract-documents/{row['document_id']}/confirm")
    elif status=='CANCELLED': row=call(client,'POST',f"/contract-documents/{row['document_id']}/cancel",json={'reason':'출력 정책 확인'})
    row=call(client,'GET',f"/contract-documents/{row['document_id']}")
    frozen=copy.deepcopy(row)
    with factory() as db:
        before_snapshot=db.get(models.ContractDocument,1).snapshot_json
        before_body=db.get(models.ContractDocument,1).body
        before_audit=db.query(AuditEvent).count()
    from PySide6.QtGui import QPdfWriter
    from PySide6.QtPdf import QPdfDocument
    import PySide6.QtPrintSupport as native
    monkeypatch.setattr(native,'QPrinter',lambda *args,**kwargs:pytest.fail('native printer discovery in PDF'))
    texts=[]
    for action in ['pdf','print']:
        path=tmp_path/f'{form}_{status}_{action}.pdf'
        if action=='pdf': export_contract_pdf(row,path)
        else:
            # Actual shared printing renderer, without native driver discovery.
            device=QPdfWriter(str(path)); device.setResolution(600)
            print_contract(row,device); del device
        reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
        assert reader.pageCount()==1
        size=reader.pagePointSize(0); assert abs(size.width()-595.28)<1 and abs(size.height()-841.89)<1
        text=assert_pdf_body_preserved(reader,row['body']); texts.append(text)
        assert ('초안 / 검토용' in text)==(status=='DRAFT')
        assert ('취소된 계약서' in text)==(status=='CANCELLED')
        assert ('금액(원)' in ''.join(text.split()))==(form=='BL_TRANSFER_TAX')
        reader.close()
    assert ''.join(texts[0].split())==''.join(texts[1].split())
    assert row==frozen
    assert call(client,'GET','/contract-documents/1')==frozen
    with factory() as db:
        document=db.get(models.ContractDocument,1)
        assert (document.status,document.version)==(status,1)
        assert document.body==before_body and document.snapshot_json==before_snapshot
        assert db.query(AuditEvent).count()==before_audit
    if status=='CONFIRMED':
        call(client,'PUT','/contract-documents/1',409,json={'body':'확정본 변경 시도'})
        assert call(client,'GET','/contract-documents/1')==frozen


@pytest.mark.parametrize('form',list(FORMS))
def test_edited_html_draft_has_notice_without_modifying_stored_body(qt_application,tmp_path,form):
    from PySide6.QtGui import QTextDocument
    from PySide6.QtPdf import QPdfDocument
    editor=QTextDocument(); editor.setHtml(render(source(FORMS[form][1]),form))
    body=editor.toHtml(); assert '<body style=' in body
    document={'body':body,'version':1,'status':'DRAFT','snapshot':{'body_format':'HTML'}}
    original=copy.deepcopy(document); path=tmp_path/'draft.pdf'; export_contract_pdf(document,path)
    reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
    assert reader.pageCount()==1
    assert '초안 / 검토용' in assert_pdf_body_preserved(reader,body)
    assert document==original and '초안 / 검토용' not in body


def test_legacy_plain_draft_and_bodyless_html_are_labeled(qt_application):
    from PySide6.QtGui import QTextDocument
    for body,metadata in [('과거 초안 원문',{}),('<html><p>편집 초안 원문</p></html>',{'body_format':'HTML'})]:
        row={'body':body,'version':1,'status':'DRAFT','snapshot':metadata}
        frozen=copy.deepcopy(row); rendered=QTextDocument(); rendered.setHtml(document_html(row))
        assert '초안 / 검토용' in rendered.toPlainText() and '초안 원문' in rendered.toPlainText()
        assert row==frozen


def test_gui_draft_pdf_and_print_do_only_get_without_saving_pending_edits(flow,ui_adapter,monkeypatch,tmp_path):
    ui,_=ui_adapter; client,factory=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    row=call(client,'GET',f"/contract-documents/{row['document_id']}")
    window=ui.ContractDocumentWindow(); window.load(row)
    window.body.append('저장하지 않은 편집: 출력으로 자동 저장하지 않음')
    with factory() as db: before_audit=db.query(AuditEvent).count()
    calls=[]; actual_request=window.request
    def request(method,*args,**kwargs):
        calls.append(method); return actual_request(method,*args,**kwargs)
    monkeypatch.setattr(window,'request',request)
    pdf_path=tmp_path/'gui_draft.pdf'; print_path=tmp_path/'gui_print.pdf'
    monkeypatch.setattr(ui.QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(pdf_path),'PDF (*.pdf)'))
    import PySide6.QtPrintSupport as native
    from PySide6.QtGui import QPdfWriter
    from PySide6.QtPdf import QPdfDocument
    class Printer:
        HighResolution=1
        def __new__(cls,*args): return QPdfWriter(str(print_path))
    class Dialog:
        def __init__(self,*args): pass
        def exec(self): return ui.QDialog.Accepted
    monkeypatch.setattr(native,'QPrinter',Printer); monkeypatch.setattr(native,'QPrintDialog',Dialog)
    window.pdf(); window.print_document()
    assert calls==['get','get']
    for path in [pdf_path,print_path]:
        reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
        assert reader.pageCount()==1
        text=assert_pdf_body_preserved(reader,row['body'])
        assert '초안 / 검토용' in text and '저장하지 않은 편집' not in text
        reader.close()
    assert call(client,'GET','/contract-documents/1')==row
    with factory() as db: assert db.query(AuditEvent).count()==before_audit
    window.close()


def test_draft_capacity_failure_preserves_database_and_existing_pdf(flow,qt_application,tmp_path):
    client,factory=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    data=source(); data['contract']['memo']='실제 계약 특약의 긴 검토 문구입니다. '*300
    call(client,'PUT','/contract-documents/1',json={'body':render(data,'IMPORT_AGENCY'),'reason':'초안 수용한계 검증'})
    row=call(client,'GET','/contract-documents/1')
    with factory() as db:
        original_snapshot=db.get(models.ContractDocument,1).snapshot_json
        original_audit=db.query(AuditEvent).count()
    target=tmp_path/'existing.pdf'; target.write_bytes(b'previous valid output')
    with pytest.raises(RuntimeError,match='A4 1페이지 수용 한계'):
        export_contract_pdf(row,target)
    assert target.read_bytes()==b'previous valid output' and list(tmp_path.iterdir())==[target]
    assert call(client,'GET','/contract-documents/1')==row
    with factory() as db:
        assert db.get(models.ContractDocument,1).snapshot_json==original_snapshot
        assert db.query(AuditEvent).count()==original_audit
