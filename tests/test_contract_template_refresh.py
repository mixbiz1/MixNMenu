"""Template updates require an explicit DRAFT rewrite, never implicit PDF changes."""
import copy
import json
import re

import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow, call
from test_batch2a_contract_import_cost import confirmed_contract, contract_data
from test_batch2a_gui_permissions import ui_adapter
from test_contract_document_v1 import source, assert_pdf_body_preserved, plain
from contract_document_templates import FORMS, REVISION, render
from financing_document import export_contract_pdf
from audit_service import AuditEvent
import models

OLD='“고객사”는 물품 출고시, “판매사”에게 사전에 출고요청신청 후 예상금액을 “고객사” 지정계좌로 입금완료한 후에 출고하기로 한다.'
NEW='“고객사”는 물품 출고 시, “판매사”에게 사전에 출고요청을 신청하고, 예상 판매대금을 “판매사”가 지정하는 계좌로 입금 완료한 후 출고하기로 한다.'
FORMS_WITH_CLAUSE=['IMPORT_AGENCY','BL_TRANSFER','DOMESTIC_PURCHASE']


@pytest.mark.parametrize('form',list(FORMS))
def test_five_templates_keep_approved_clause_and_submission_form_policy(qt_application,form):
    text=plain(render(source(FORMS[form][1]),form))
    assert OLD not in text
    assert (NEW in text)==(form in FORMS_WITH_CLAUSE)
    if form=='BL_TRANSFER_CUSTOMS': assert '금액' not in text
    if form=='BL_TRANSFER_TAX': assert '금액(원)' in text


@pytest.mark.parametrize('form',FORMS_WITH_CLAUSE)
def test_id_one_gui_explicit_rewrite_pdf_and_confirmed_history(flow,ui_adapter,qt_application,tmp_path,form,monkeypatch):
    client,factory=flow; ui,_=ui_adapter
    payload=contract_data(form)
    payload.update(contract_no='FC-00001-261006-00001-IM-0001',contract_date='2026-10-06')
    contract=call(client,'POST','/financing-contracts',201,json=payload)
    contract=call(client,'POST',f"/financing-contracts/{contract['contract_id']}/confirm")
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':form})
    with factory() as db:
        row=db.get(models.ContractDocument,1)
        snapshot=json.loads(row.snapshot_json); snapshot['template_revision']='20261008.v1.integrity'
        row.snapshot_json=json.dumps(snapshot,ensure_ascii=False)
        assert NEW in row.body
        row.body=row.body.replace(NEW,OLD); db.commit()
        before_body=row.body; before_snapshot=copy.deepcopy(snapshot)
        before_audit=db.query(AuditEvent).count()
    doc=call(client,'GET','/contract-documents/1')
    window=ui.ContractDocumentWindow(); window.load(doc)
    assert OLD in window.body.toPlainText() and '이전 양식' in window.summary.text()
    # Reload/PDF must not silently regenerate the stored draft.
    from PySide6.QtPdf import QPdfDocument
    import PySide6.QtPrintSupport as native
    monkeypatch.setattr(native,'QPrinter',lambda *a,**kw:pytest.fail('PDF native discovery'))
    old_file=tmp_path/'old.pdf'; export_contract_pdf(doc,old_file)
    reader=QPdfDocument(); assert reader.load(str(old_file))==QPdfDocument.Error.None_
    assert OLD in assert_pdf_body_preserved(reader,before_body); reader.close()
    with factory() as db:
        assert db.get(models.ContractDocument,1).body==before_body
        assert json.loads(db.get(models.ContractDocument,1).snapshot_json)==before_snapshot
        assert db.query(AuditEvent).count()==before_audit
    window.reason.setText('판매대금 계좌 주체를 승인된 표준양식으로 재작성')
    window.regenerate()
    fresh=call(client,'GET','/contract-documents/1')
    assert (fresh['document_id'],fresh['version'],fresh['status'])==(1,1,'DRAFT')
    assert NEW in window.body.toPlainText() and OLD not in window.body.toPlainText()
    assert '이전 양식' not in window.summary.text()
    expected=copy.deepcopy(before_snapshot); expected['template_revision']=REVISION
    assert fresh['snapshot']==expected
    assert '________' in fresh['body']  # no missing data invented
    with factory() as db:
        assert db.query(AuditEvent).count()==before_audit+1
        audit=db.query(AuditEvent).filter_by(entity_type='CONTRACTDOCUMENT',action='UPDATE').one()
        assert OLD in json.loads(audit.before_json)['body'] and NEW in json.loads(audit.after_json)['body']
        assert audit.reason==window.reason.text()
    # The actual GUI PDF action fetches saved body, not an editor-only buffer.
    path=tmp_path/'new.pdf'
    monkeypatch.setattr(ui.QFileDialog,'getSaveFileName',lambda *a,**kw:(str(path),'PDF (*.pdf)'))
    window.pdf(); reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
    assert reader.pageCount()==1
    text=assert_pdf_body_preserved(reader,fresh['body'])
    assert re.sub(r'\s+','',NEW) in re.sub(r'\s+','',text)
    assert '“고객사”지정계좌' not in re.sub(r'\s+','',text) and '초안 / 검토용' in text
    reader.close()
    # Editor save persists the approved text; it does not re-render the source.
    window.body.append('검토한 추가 문구'); window.save()
    assert NEW in call(client,'GET','/contract-documents/1')['body']
    confirmed=call(client,'POST','/contract-documents/1/confirm'); frozen=copy.deepcopy(confirmed['snapshot'])
    with factory() as db: count=db.query(AuditEvent).count()
    call(client,'POST','/contract-documents/1/regenerate',409,json={'reason':'확정본 교체 금지'})
    call(client,'PUT','/contract-documents/1',409,json={'body':'확정본 교체 금지'})
    assert call(client,'GET','/contract-documents/1')['snapshot']==frozen
    with factory() as db: assert db.query(AuditEvent).count()==count
    window.close()


def test_old_confirmed_body_never_upgraded_on_read_or_output(flow,qt_application,tmp_path):
    client,factory=flow; contract=confirmed_contract(client)
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    call(client,'PUT','/contract-documents/1',json={'body':doc['body'].replace(NEW,OLD),'reason':'과거 확정본 보존 검증'})
    confirmed=call(client,'POST','/contract-documents/1/confirm')
    frozen=copy.deepcopy(confirmed['snapshot'])
    doc=call(client,'GET','/contract-documents/1')
    target=tmp_path/'historical.pdf'; export_contract_pdf(doc,target)
    from PySide6.QtPdf import QPdfDocument
    reader=QPdfDocument(); assert reader.load(str(target))==QPdfDocument.Error.None_
    text=assert_pdf_body_preserved(reader,frozen['body']); assert OLD in text
    assert NEW not in text and '초안 / 검토용' not in text
    assert call(client,'GET','/contract-documents/1')['snapshot']==frozen
    reader.close()
