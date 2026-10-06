"""Real HTTP adapters exercise focused GUI data succession without an external server."""
import inspect
import re
from decimal import Decimal
import pytest
from test_batch1b_distribution_e2e import flow, call, BASE
from test_trade_flow_integrity import db_factory
from test_batch2a_contract_import_cost import confirmed_contract, ready_case, fill_basic, basic_cost
import models
from permissions import issue_token, permission_for_request


def test_workflow_read_permission_borrows_only_safe_lookup_endpoints(flow):
    client, factory = flow
    contract, case, _ = ready_case(flow)
    with factory() as db:
        db.add(models.User(user_id='cost-reader',user_name='조회자',password_hash='x',is_admin=False))
        for code in ['IMPORT_COST','IMPORT_INTAKE','FINANCING_DOCUMENT']:
            if not db.get(models.MenuMaster, code):
                db.add(models.MenuMaster(menu_code=code,menu_name=code,menu_group='Financing',sort_order=1))
        db.commit()
        db.add(models.UserCompanyAccess(user_id='cost-reader',comp_code='00001'))
        db.add(models.UserMenuPermission(user_id='cost-reader',menu_code='IMPORT_COST',can_read=True))
        db.commit()
    client.headers['Authorization']='Bearer '+issue_token('cost-reader')
    for path in ['/import-cases',f"/import-cases/{case['import_case_id']}",'/financing-contracts','/lots','/accounts']:
        assert client.get(BASE+path,params={'lookup_for':'IMPORT_COST'}).status_code==200
    assert client.get('/api/v1/products',params={'lookup_for':'IMPORT_COST'}).status_code==200
    assert client.get(BASE+'/import-cases').status_code==403
    assert client.get(BASE.replace('00001','00002')+'/import-cases',params={'lookup_for':'IMPORT_COST'}).status_code==403
    assert client.post(BASE+'/import-costs',json={'import_case_id':case['import_case_id']}).status_code==403
    assert client.put(BASE+f"/import-cases/{case['import_case_id']}",params={'lookup_for':'IMPORT_COST'},json={}).status_code==403
    assert permission_for_request('POST',BASE+'/import-costs/1/rows').action=='update'


@pytest.fixture
def ui_adapter(flow,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app_context import app_context
    import views.financing_intake as ui
    application=QApplication.instance() or QApplication([])
    client,_=flow
    monkeypatch.setattr(app_context,'can',lambda *args:True)
    monkeypatch.setattr(app_context,'_company_code','00001')
    for method in ['get','post','put','delete']:
        def adapter(url,_method=method,**kwargs):
            kwargs.pop('timeout',None)
            return client.request(_method,url[url.index('/api/v1'):],**kwargs)
        monkeypatch.setattr(ui.httpx,method,adapter)
    return ui, application


def test_gui_contract_document_create_edit_confirm_requery(flow,ui_adapter,monkeypatch):
    ui,_=ui_adapter; client,_=flow; contract=confirmed_contract(client)
    window=ui.ContractDocumentWindow()
    monkeypatch.setattr(window,'choose',lambda *args,**kwargs:contract)
    window.pick_contract(); window.create()
    assert contract['contract_no'] in window.body.toPlainText()
    window.body.appendPlainText('추가 약정'); window.save(); window.action('confirm')
    assert window.body.isReadOnly() and window.current['status']=='CONFIRMED'
    assert '추가 약정' in window.current['snapshot']['body']
    window.refresh(); window.clear(); assert not window.body.isReadOnly()
    window.close()


def test_gui_import_intake_inherits_product_pk_quantity_and_keeps_supplier_separate(flow,ui_adapter,monkeypatch):
    ui,_=ui_adapter; client,_=flow; contract=confirmed_contract(client)
    window=ui.ImportCaseWindow(); monkeypatch.setattr(window,'choose',lambda *args,**kwargs:contract)
    window.pick_contract()
    payload=window.payload()
    assert payload['contract_id']==contract['contract_id'] and payload['supplier_account_id'] is None
    assert [Decimal(x['weight']) for x in payload['items']]==[Decimal('140.00'),Decimal('50.00')]
    assert [x['product_id'] for x in payload['items']]==[1,2]
    assert not window.customs.text() and not window.receipt.text()
    window.save(); assert window.current['import_case_id'] and window.items.rowCount()==2
    window.close()


def test_gui_cost_screen_shows_conditions_actual_rows_and_exact_allocations(flow,ui_adapter,monkeypatch):
    ui,_=ui_adapter; client,_=flow; _,case,_=ready_case(flow)
    window=ui.ImportCostWindow(); monkeypatch.setattr(window,'choose',lambda *args,**kwargs:call(client,'GET',f"/import-cases/{case['import_case_id']}"))
    window.pick_case(); window.create()
    assert window.cost_rows.rowCount()==5 and window.allocations.rowCount()==3
    assert window.case.property('pk')==case['import_case_id']
    assert 'interest_rate_1' in window.conditions.toPlainText()
    value=fill_basic(client,window.current); window.load(value); window.confirm()
    assert window.current['status']=='CONFIRMED'
    assert sum(int(window.allocations.item(i,3).text()) for i in range(3))==157053
    assert window.current['snapshot']['total_cost']=='157053'
    window.close()


def test_contract_output_uses_snapshot_qpdfwriter_and_failure_preserves_confirmed_document(flow,ui_adapter,tmp_path,monkeypatch):
    import financing_document as renderer
    ui,_=ui_adapter; client,factory=flow; contract=confirmed_contract(client)
    document=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    document=call(client,'POST',f"/contract-documents/{document['document_id']}/confirm")
    assert 'QPdfWriter' in inspect.getsource(renderer.export_contract_pdf)
    assert 'QPrinter' not in inspect.getsource(renderer)
    document['body']='현재 값은 사용하지 않습니다'
    assert '현재 값은 사용하지 않습니다' not in renderer.document_html(document)
    filename=tmp_path/'contract.pdf'; renderer.export_contract_pdf(document,filename)
    assert filename.read_bytes().startswith(b'%PDF-')
    assert re.search(rb'/Type\s*/Page\b',filename.read_bytes())
    frozen=call(client,'GET',f"/contract-documents/{document['document_id']}")['snapshot']
    monkeypatch.setattr(renderer,'print_contract',lambda *args:(_ for _ in ()).throw(RuntimeError('safe injected PDF failure')))
    with pytest.raises(RuntimeError,match='safe injected'):
        renderer.export_contract_pdf(document,tmp_path/'failure.pdf')
    assert not (tmp_path/'failure.pdf').exists()
    assert call(client,'GET',f"/contract-documents/{document['document_id']}")['snapshot']==frozen
    with factory() as db: assert db.get(models.FinancingContract,contract['contract_id']).status=='CONFIRMED'
