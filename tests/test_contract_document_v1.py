"""Standard contract forms, real API/GUI, immutable output and no native PDF printers."""
import copy
from decimal import Decimal
import inspect
import json
import re

import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow, call, BASE
from test_batch2a_contract_import_cost import confirmed_contract, ready_case
from test_batch2a_gui_permissions import ui_adapter
import models
from audit_service import AuditEvent
from contract_document_templates import FORMS, render, contract_amount, REVISION
from financing_document import document_html, export_contract_pdf


def plain(html):
    from PySide6.QtGui import QTextDocument
    document=QTextDocument(); document.setHtml(html); return document.toPlainText()


def assert_pdf_body_preserved(reader, body):
    """Font metrics can paginate the same legal text differently on Windows.

    Verify every text block, including table cells/signatures, rather than
    requiring a page count measured with the Work machine's Korean font.
    A page number alone must not count as contractual content.
    """
    from PySide6.QtGui import QTextDocument
    normalized = lambda value: re.sub(r'\s+', '', value)
    pages = [reader.getAllText(page).text() for page in range(reader.pageCount())]
    assert pages, 'PDF has no pages'
    contents=[]
    for page_number, page_text in enumerate(pages, 1):
        content = re.sub(r'\s*' + str(page_number) + r'\s*$', '', page_text).strip()
        assert content, f'PDF page {page_number} contains only a footer/blank space'
        contents.append(content)
    extracted = '\n'.join(contents)
    text_document = QTextDocument(); text_document.setHtml(body)
    block = text_document.begin()
    while block.isValid():
        expected = normalized(block.text())
        if expected:
            assert expected in normalized(extracted), f'Missing PDF body block: {block.text()}'
        block = block.next()
    return extracted


def source(kind='IMPORT_AGENCY'):
    return {'company':{'name':'주식회사 믹스비즈','biz_no':'212-81-83146','address':'경기도 하남시 미사강변중앙로 208, 701-2-6호','ceo_name':'조일','bank1':'기업은행 테스트 계좌'},
        'partner':{'name':'표준 계약업체','biz_no':'206-86-72085','address':'경기도 하남시','address_detail':'상세주소','ceo_name':'계약 대표'},
        'contract':{'contract_type':kind,'contract_no':'FC-00001-261006-00001-IM-0001','contract_date':'2026-10-06','memo':'원본에 따른 별도 약정',
            'deposit_required':False,'participants':[], 'items':[{'contract_item_id':1,'product_id':1,'product_name':'루돌프 장족',
                'contract_box_qty':1137,'contract_weight':'22005.39','contract_unit_price':2250,'memo':None}],
            'terms':[{'version':1,'effective_from':'2026-10-01','contract_days':90,'recovery_template':'ALL_IN','interest_rate_1':'7.0',
                'interest_rate_2':'8.0','interest_period_days_1':90,'interest_period_days_2':90,'brokerage_rate_1':'1.5','brokerage_rate_2':'1.7',
                'storage_rate_per_kg_day':'0.9','conditions':{}}]},
        'document_goods':{'1':{'origin':'오스트리아','warehouse_name':'삼진1','bl_no':'2605-0944-VM','container_no':'FBIU5008553','invoice_reference':'LACONES-JOE-038/2026'}}}


@pytest.fixture
def qt():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('form',list(FORMS))
def test_standard_forms_match_original_clause_and_table_structure_without_json(qt,form):
    data=source(FORMS[form][1]); html=render(data,form); visible=plain(html)
    assert data['contract']['contract_no'] in visible
    assert '주식회사 믹스비즈' in visible and '표준 계약업체' in visible and '대표' in visible
    assert '루돌프 장족' in visible and '22,005.39' in visible
    assert '{{' not in html and 'None' not in visible
    for internal in ['effective_from','recovery_template','contract_item_id','interest_rate_1','conditions','Sample Template',"{'",'법률문구 검토 전']:
        assert internal not in visible
    if form in {'BL_TRANSFER_TAX','BL_TRANSFER_CUSTOMS'}:
        assert '양도자는 양수자에게 아래 상품에 대한 모든 권리를 양도하기로 합니다.' in visible
        for label in ['양도자','양수자','상품내역','BL#',"Con't#",'박스수','중량(kg)','계약일','명판','법인인감','인감']: assert label in visible
        assert '1,137' in visible and 'FBIU5008553' in visible
        assert ('금액(원)' in visible) == (form == 'BL_TRANSFER_TAX')
        assert ('49,512,128' in visible) == (form == 'BL_TRANSFER_TAX')
        if form=='BL_TRANSFER_CUSTOMS':
            assert not any(value in visible for value in ['USD','KRW','2,250','7.00%','이자','수수료','30,000'])
            assert '원본에 따른 별도 약정' not in visible
    else:
        for clause in ['요청대상물품정보 및 책임','1년3개월','3영업일','제3자에게 임의로 처분','거래조건','계약(중개)수수료',
                       '계약기간 연장','창고료','최종 출고전에','출고요청 및 판매대금입금','오전9시~오후4시30분']:
            assert clause in visible
        assert '7.00%' in visible and '1.50%' in visible and '0.90원/Kg·일' in visible
        assert '원본에 따른 별도 약정' in visible
        if form=='DOMESTIC_PURCHASE':
            assert '국내에서 물품을 구매하여' in visible and '계근출고로 산정' in visible
            assert '2,250' in visible and '49,512,128' in visible and 'BL#' in visible
        else:
            assert '해외에서 물품을 수입하여' in visible and '국내외의 모든 제반문제' in visible
            assert '해외거래선과 협의' in visible and '검역완료시점부터 90일이내' in visible
            assert '물품대금+관세+각종은행수수료+운송비용+관세사수수료' in visible
            assert 'USD/kg' in visible and '2,250' not in visible


def test_missing_values_are_blank_future_terms_ignored_and_master_strings_escaped(qt):
    data=source(); data['company']['bank1']=None; data['partner']['ceo_name']=None
    data['contract']['items'][0]['contract_unit_price']=None
    data['contract']['items'][0]['product_name']='<img src="file:///secret">'
    data['contract']['terms'].append({**data['contract']['terms'][0],'version':2,'effective_from':'2027-01-01','interest_rate_1':'99'})
    html=render(data,'DOMESTIC_PURCHASE'); visible=plain(html)
    assert '<img src=' not in html and '&lt;img' in html
    assert '________' in visible and 'None' not in visible
    assert '7.00%' in visible and '99.00%' not in visible
    assert '기업은행 테스트 계좌' not in visible
    assert contract_amount(data['contract']['items']) is None


def test_contract_amount_is_sum_of_existing_per_line_won_ceiling_policy():
    assert contract_amount([{'contract_weight':'10.01','contract_unit_price':101},
                            {'contract_weight':'12.03','contract_unit_price':1}])==Decimal(1025)


def test_three_bl_forms_share_contract_pk_and_supersede_only_same_form(flow,qt):
    client,factory=flow; contract=confirmed_contract(client,'BL_TRANSFER')
    documents=[]
    for form in ['BL_TRANSFER','BL_TRANSFER_TAX','BL_TRANSFER_CUSTOMS']:
        documents.append(call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':form}))
    assert [x['version'] for x in documents]==[1,2,3]
    for row in documents:
        call(client,'POST',f"/contract-documents/{row['document_id']}/confirm")
    old_tax=call(client,'GET',f"/contract-documents/{documents[1]['document_id']}")
    assert old_tax['snapshot']['sample_template'] is False
    replacement=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'BL_TRANSFER_TAX'})
    replacement=call(client,'POST',f"/contract-documents/{replacement['document_id']}/confirm")
    assert replacement['version']==4
    assert call(client,'GET',f"/contract-documents/{documents[1]['document_id']}")['status']=='SUPERSEDED'
    assert call(client,'GET',f"/contract-documents/{documents[1]['document_id']}")['snapshot']==old_tax['snapshot']
    for row in [documents[0],documents[2]]: assert call(client,'GET',f"/contract-documents/{row['document_id']}")['status']=='CONFIRMED'
    case=call(client,'POST','/import-cases',201,json={'contract_id':contract['contract_id']})
    basic=call(client,'GET',f"/contract-documents/{documents[0]['document_id']}")
    assert case['source_snapshot']==basic['snapshot']
    with factory() as db:
        assert db.query(models.FinancingContract).count()==1
        assert db.query(AuditEvent).filter_by(action='SUPERSEDE').count()==1


def test_existing_sample_draft_regeneration_preserves_pk_version_and_audits_before_after(flow,qt):
    client,factory=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    with factory() as db:
        saved=db.get(models.ContractDocument,row['document_id']); snapshot=json.loads(saved.snapshot_json)
        snapshot.pop('body_format'); snapshot.pop('template_revision'); snapshot.pop('document_goods')
        saved.body="기존 Sample Template {'interest_rate_1': '7.5'}"; saved.snapshot_json=json.dumps(snapshot); db.commit()
    converted=call(client,'POST',f"/contract-documents/{row['document_id']}/regenerate",json={'reason':'표준양식 적용'})
    assert (converted['document_id'],converted['version'],converted['status'])==(row['document_id'],1,'DRAFT')
    assert 'interest_rate_1' not in plain(converted['body'])
    assert converted['snapshot']['template_revision']==REVISION
    with factory() as db:
        update=db.query(AuditEvent).filter_by(action='UPDATE').one()
        assert '기존 Sample' in json.loads(update.before_json)['body']
        assert json.loads(update.after_json)['snapshot']['body_format']=='HTML'
        assert update.reason=='표준양식 적용'
    fixed=call(client,'POST',f"/contract-documents/{row['document_id']}/confirm")
    call(client,'POST',f"/contract-documents/{row['document_id']}/regenerate",409,json={'reason':'확정본 변경 차단'})
    assert call(client,'GET',f"/contract-documents/{row['document_id']}")['snapshot']==fixed['snapshot']


def test_html_edit_and_confirm_snapshot_remain_immutable_and_output_never_rerenders_master_or_template(flow,qt,monkeypatch):
    client,factory=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    html=row['body'].replace('________%', '10.00%',1).replace('</body>','<p>검토한 실제 특약</p></body>')
    row=call(client,'PUT',f"/contract-documents/{row['document_id']}",json={'body':html,'reason':'실제 문구 검토'})
    row=call(client,'POST',f"/contract-documents/{row['document_id']}/confirm"); frozen=copy.deepcopy(row['snapshot'])
    with factory() as db:
        db.get(models.Product,1).product_name='후속 상품명'; db.get(models.Account,1).address='후속 주소'; db.commit()
    monkeypatch.setattr('contract_document_templates.render',lambda *args:(_ for _ in ()).throw(AssertionError('must use issued body')))
    reread=call(client,'GET',f"/contract-documents/{row['document_id']}")
    assert reread['snapshot']==frozen and '검토한 실제 특약' in plain(document_html(reread))
    reread['body']='동적 본문 무시'; assert '동적 본문 무시' not in document_html(reread)
    call(client,'PUT',f"/contract-documents/{row['document_id']}",409,json={'body':'확정본 변경'})
    cancelled=call(client,'POST',f"/contract-documents/{row['document_id']}/cancel",json={'reason':'문서 취소'})
    assert cancelled['snapshot']==frozen and '취소된 계약서' in plain(document_html(cancelled))


@pytest.mark.parametrize('body',['<html><body><script>alert(1)</script></body></html>',
    '<html><body><img src="file:///secret"/></body></html>',
    '<html><body><p style="background:url(https://example.com)">x</p></body></html>'])
def test_unsafe_rich_resource_is_rejected_without_snapshot_changes(flow,body):
    client,_=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    call(client,'PUT',f"/contract-documents/{row['document_id']}",400,json={'body':body})
    assert call(client,'GET',f"/contract-documents/{row['document_id']}")['snapshot']==row['snapshot']


def test_gui_selects_three_bl_forms_shows_tables_and_saves_pending_edits_before_confirm(flow,ui_adapter,monkeypatch):
    ui,_=ui_adapter; client,_=flow; contract=confirmed_contract(client,'BL_TRANSFER')
    window=ui.ContractDocumentWindow(); monkeypatch.setattr(window,'choose',lambda *args,**kwargs:contract)
    window.pick_contract(); assert window.template.count()==3
    window.template.setCurrentIndex(window.template.findData('BL_TRANSFER_CUSTOMS')); window.create()
    visible=window.body.toPlainText(); assert '관세사제출' in visible and '금액(원)' not in visible
    assert '<html>' not in visible and 'interest_rate_1' not in visible
    window.body.append('확인한 상품 표시'); window.action('confirm')
    assert window.current['status']=='CONFIRMED' and window.body.isReadOnly()
    assert '확인한 상품 표시' in window.current['snapshot']['body']
    assert window.table.columnCount()==5
    window.close()


@pytest.mark.parametrize('form',list(FORMS))
def test_pdf_all_forms_korean_tables_and_snapshot_only_no_qprinter(qt,tmp_path,form,monkeypatch):
    import PySide6.QtPrintSupport as native
    def no_printer(*args,**kwargs): raise AssertionError('native printer discovery in PDF')
    monkeypatch.setattr(native,'QPrinter',no_printer)
    body=render(source(FORMS[form][1]),form)
    document={'body':'Master 무시','version':1,'status':'CONFIRMED',
              'snapshot':{'body':body,'body_format':'HTML','template_revision':REVISION}}
    target=tmp_path/(form+'.pdf'); export_contract_pdf(document,target)
    from PySide6.QtPdf import QPdfDocument
    reader=QPdfDocument(); assert reader.load(str(target))==QPdfDocument.Error.None_
    assert reader.pageCount()==1
    size=reader.pagePointSize(0)
    assert abs(size.width()-595.28)<1 and abs(size.height()-841.89)<1
    bounds=reader.getAllText(0).boundingRectangle()
    assert bounds.left()>=33 and bounds.top()>=33
    assert bounds.right()<=size.width()-33 and bounds.bottom()<=size.height()-33
    extracted=assert_pdf_body_preserved(reader,body)
    assert '믹스비즈' in extracted and '루돌프' in extracted
    assert 'Master 무시' not in extracted and 'interest_rate_1' not in extracted
    assert ('금액(원)' in re.sub(r'\s+','',extracted))==(form=='BL_TRANSFER_TAX')
    reader.close()
    assert 'QPdfWriter' in inspect.getsource(export_contract_pdf)


@pytest.mark.parametrize('form',['IMPORT_AGENCY','BL_TRANSFER'])
def test_import_contract_long_terms_reject_unreadable_output_without_changing_snapshot(qt,tmp_path,form,monkeypatch):
    import PySide6.QtPrintSupport as native
    monkeypatch.setattr(native,'QPrinter',lambda *args,**kwargs: pytest.fail('native printer discovery in PDF'))
    data=source(form)
    data['contract']['memo']='검토할 실제 계약 특약사항 및 수입물품 인수 조건 확인. '*120
    body=render(data,form)
    snapshot={'body':body,'body_format':'HTML','template_revision':REVISION}
    document={'body':'변경된 Master 본문','version':1,'status':'CONFIRMED','snapshot':snapshot}
    frozen=copy.deepcopy(document)
    target=tmp_path/'preserved.pdf'; target.write_bytes(b'existing PDF remains')
    with pytest.raises(RuntimeError,match='A4 1페이지 수용 한계'):
        export_contract_pdf(document,target)
    assert target.read_bytes()==b'existing PDF remains'
    assert document==frozen and list(tmp_path.iterdir())==[target]


def test_pdf_body_check_rejects_a_footer_only_page(qt):
    class Reader:
        def pageCount(self): return 2
        def getAllText(self,page):
            from types import SimpleNamespace
            return SimpleNamespace(text=lambda:'계약 본문\n1' if page==0 else '\n 2\n')
    with pytest.raises(AssertionError,match='page 2'):
        assert_pdf_body_preserved(Reader(),'<p>계약 본문</p>')


def test_legacy_confirmed_plain_body_stays_unchanged(qt):
    document={'body':'현재 Master 본문','version':1,'status':'CONFIRMED','snapshot':{'body':'과거 확정본\n사용자 특별조건','sample_template':True}}
    assert '과거 확정본' in plain(document_html(document))
    assert '현재 Master 본문' not in document_html(document)


def test_actual_gui_expense_conditions_tax_and_payer_are_rendered_without_raw_codes(qt):
    data=source(); term=data['contract']['terms'][0]
    term['conditions']={'expense_conditions':[
        {'code':'INBOUND_OUTBOUND','basis':'KG','unit_rate':'80','tax_treatment':'TAXABLE','payer':'ORIGINAL_CONTRACTOR','memo':'입출고 약정'},
        {'code':'WORK','basis':'BOX','unit_rate':'150','tax_treatment':'EXEMPT','payer':'ACTUAL_SHIPPER'},
        {'code':'BROKERAGE','basis':'PERCENT','rate_1':'1.5','tax_treatment':'EXEMPT','payer':'MXMN'}]}
    term['inbound_outbound_rate_per_kg']='80'
    visible=plain(render(data,'IMPORT_AGENCY'))
    assert visible.count('입출고비:')==1
    assert '80.00원/Kg / 부가세 별도 / 부담: 고객사' in visible
    assert '150.00원/Box / 면세 / 부담: 출고업체' in visible
    assert '중개수수료 부담: 판매사' in visible and '1.50%(면세)' in visible
    assert 'VAT별도' not in visible
    assert 'ORIGINAL_CONTRACTOR' not in visible and 'expense_conditions' not in visible


def test_many_contract_goods_explain_single_page_limit_without_losing_snapshot(qt,tmp_path):
    data=source('DOMESTIC_PURCHASE')
    item=data['contract']['items'][0]
    data['contract']['items']=[dict(item,contract_item_id=n,product_name=f'계약상품 {n:03}') for n in range(1,101)]
    body=render(data,'DOMESTIC_PURCHASE'); path=tmp_path/'multiple.pdf'
    document={'body':body,'version':1,'status':'CONFIRMED','snapshot':{'body':body,'body_format':'HTML'}}
    original=copy.deepcopy(document)
    with pytest.raises(RuntimeError,match='A4 1페이지 수용 한계'):
        export_contract_pdf(document,path)
    assert not path.exists() and document==original and not list(tmp_path.iterdir())
    assert '계약상품 001' in body and '계약상품 100' in body and '계약 대표' in body


def test_actual_contract_lot_metadata_is_carried_and_frozen(flow,qt):
    client,factory=flow; contract,case,purchase=ready_case(flow,'BL_TRANSFER')
    item=contract['items'][0]
    lot_id=next(row['lot_id'] for row in purchase['items'] if row['product_id']==item['product_id'])
    with factory() as db:
        lot=db.get(models.Lot,lot_id); lot.origin='오스트리아'; lot.container_no='CN-REAL'
        warehouse_name=lot.warehouse.warehouse_name; db.commit()
    call(client,'POST',f"/financing-contracts/{contract['contract_id']}/lots",201,json={
        'contract_item_id':item['contract_item_id'],'lot_id':lot_id,'contract_box_qty':1,'contract_weight':'10'})
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'BL_TRANSFER_TAX'})
    metadata=row['snapshot']['document_goods'][str(item['contract_item_id'])]
    assert metadata=={'origin':'오스트리아','bl_no':'BL-COST-1','container_no':'CN-REAL','warehouse_name':warehouse_name}
    assert 'BL-COST-1' in plain(row['body']) and 'CN-REAL' in plain(row['body'])
    row=call(client,'POST',f"/contract-documents/{row['document_id']}/confirm")
    with factory() as db:
        db.get(models.Lot,lot_id).bl_no='Master BL 변경'; db.commit()
    after=call(client,'GET',f"/contract-documents/{row['document_id']}")
    assert after['snapshot']==row['snapshot'] and 'Master BL 변경' not in document_html(after)


@pytest.mark.parametrize('form',list(FORMS))
def test_normal_two_products_keep_one_page_and_reprint_snapshot(qt,tmp_path,form):
    from PySide6.QtPdf import QPdfDocument
    data=source(FORMS[form][1]); first=data['contract']['items'][0]
    data['contract']['items'].append(dict(first,contract_item_id=2,product_name='두 번째 한글 계약상품',contract_box_qty=10,contract_weight='150.25'))
    data['document_goods']['2']=dict(data['document_goods']['1'])
    data['partner']['address_detail']='미사강변 사무실 상세주소'
    body=render(data,form)
    row={'body':'현재 Master 본문','version':2,'status':'CONFIRMED','snapshot':{'body':body,'body_format':'HTML'}}
    frozen=copy.deepcopy(row); texts=[]
    for index in range(2):
        path=tmp_path/f'{form}_{index}.pdf'; export_contract_pdf(row,path)
        reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
        assert reader.pageCount()==1
        texts.append(assert_pdf_body_preserved(reader,body)); reader.close()
    assert texts[0]==texts[1] and row==frozen


def test_pdf_and_print_share_physical_a4_layout_across_device_resolutions(qt,tmp_path):
    from PySide6.QtGui import QPdfWriter
    from PySide6.QtPdf import QPdfDocument
    from financing_document import print_contract,contract_page
    body=render(source(),'IMPORT_AGENCY')
    row={'body':body,'version':1,'status':'CONFIRMED','snapshot':{'body':body,'body_format':'HTML'}}
    outputs=[]; rectangles=[]
    for resolution in (96,300,600):
        path=tmp_path/f'device_{resolution}.pdf'; writer=QPdfWriter(str(path)); writer.setResolution(resolution)
        print_contract(row,writer); del writer
        reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
        assert reader.pageCount()==1
        outputs.append(re.sub(r'\s+','',assert_pdf_body_preserved(reader,body)))
        rect=reader.getAllText(0).boundingRectangle()
        rectangles.append((rect.x(),rect.y(),rect.width(),rect.height())); reader.close()
    assert len(set(outputs))==1
    for rect in rectangles[1:]:
        assert all(abs(a-b)<=2 for a,b in zip(rectangles[0],rect))
    doc,scale,available=contract_page(row)
    assert doc.documentLayout().documentSize().height()*scale<=available.height()+0.01
    assert scale*9>=8.5


def test_readable_scaling_near_limit_keeps_complete_body(qt,tmp_path):
    from financing_document import contract_page
    from PySide6.QtPdf import QPdfDocument
    data=source()
    for repetitions in range(1,121):
        data['contract']['memo']='추가 특약의 상품 인수 조건을 확인합니다. '*repetitions
        body=render(data,'IMPORT_AGENCY')
        row={'body':body,'version':1,'status':'CONFIRMED','snapshot':{'body':body,'body_format':'HTML'}}
        try: doc,scale,available=contract_page(row)
        except RuntimeError: break
        if scale<1:
            assert scale*9>=8.5
            path=tmp_path/'scaled.pdf'; export_contract_pdf(row,path)
            reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
            assert reader.pageCount()==1
            assert_pdf_body_preserved(reader,body)
            return
    pytest.fail('Did not exercise the readable 8.5–9pt scaling band')


def test_rich_editor_confirmed_snapshot_keeps_one_page(qt,tmp_path):
    from PySide6.QtGui import QTextDocument
    from PySide6.QtPdf import QPdfDocument
    editor=QTextDocument(); editor.setHtml(render(source(),'IMPORT_AGENCY'))
    body=editor.toHtml()
    row={'body':'변경된 Master','version':1,'status':'CONFIRMED','snapshot':{'body':body,'body_format':'HTML'}}
    frozen=copy.deepcopy(row); path=tmp_path/'edited.pdf'; export_contract_pdf(row,path)
    reader=QPdfDocument(); assert reader.load(str(path))==QPdfDocument.Error.None_
    assert reader.pageCount()==1
    assert_pdf_body_preserved(reader,body)
    assert row==frozen
