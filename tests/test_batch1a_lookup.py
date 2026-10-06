from unittest.mock import Mock
import pytest
from test_sales_outbound import api
import models
from permissions import permission_for_request, issue_token


def test_existing_search_endpoints_and_no_argument_compatibility(api):
    client,factory=api
    with factory() as db:
        product=db.get(models.Product,1); product.specification='냉동 규격';
        account=db.get(models.Account,1); account.biz_no='123-45-67890'
        db.add(models.Product(product_code='P2',product_name='다른 상품',tax_type='2'))
        db.commit()
    assert len(client.get('/api/v1/products').json()) == 2
    assert client.get('/api/v1/products',params={'search':'냉동','limit':50}).json()[0]['product_id'] == 1
    assert len(client.get('/api/v1/products',params={'limit':1}).json()) == 1
    for term in ('A1','거래처','123-45'):
        result=client.get('/api/v1/companies/00001/accounts',params={'search':term,'purpose':'SALE','limit':50})
        assert result.status_code==200,result.text
        assert result.json()[0]['account_id']==1
    assert len(client.get('/api/v1/companies/00001/accounts').json())==1
    assert client.get('/api/v1/products',params={'limit':101}).status_code==422
    assert client.get('/api/v1/companies/00001/accounts',params={'limit':0}).status_code==422
    result=client.get('/api/v1/companies/00001/purchase-options',params={'transaction_date':'2026-10-02','product_query':'냉동'})
    assert result.status_code==200,result.text
    assert result.json()['products'][0]['product_id']==1


def test_shared_lookup_pk_selection_after_sort():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from views.lookup_dialog import LookupDialog
    from views.purchase_reg import LookupDialog as LegacyLookup
    application=QApplication.instance() or QApplication([])
    assert LegacyLookup is LookupDialog
    dialog=LookupDialog(None,'search','',[('name','name')],lambda term:[{'id':99,'name':'Z'},{'id':3,'name':'A'}])
    dialog.table.setSortingEnabled(True); dialog.table.sortItems(0,Qt.AscendingOrder)
    dialog.table.selectRow(0); dialog.accept_current()
    assert dialog.selected['id']==3
    dialog.close()


def test_workflow_lookup_permissions_are_read_only_and_scoped(api):
    client,factory=api
    with factory() as db:
        db.add(models.User(user_id='reader',user_name='R',password_hash='x',is_admin=False)); db.commit()
        db.add_all([models.UserCompanyAccess(user_id='reader',comp_code='00001'),
                    models.UserMenuPermission(user_id='reader',menu_code='SALES_GENERAL',can_read=True,can_create=False,can_update=False,can_delete=False)])
        db.commit()
    client.headers['Authorization']='Bearer '+issue_token('reader')
    assert client.get('/api/v1/products',params={'lookup_for':'SALES_GENERAL','limit':50}).status_code==200
    assert client.get('/api/v1/products').status_code==403
    assert client.get('/api/v1/companies/00001/accounts',params={'lookup_for':'SALES_GENERAL'}).status_code==200
    assert client.get('/api/v1/companies/OTHER/accounts',params={'lookup_for':'SALES_GENERAL'}).status_code==403
    assert client.get('/api/v1/products/1',params={'lookup_for':'SALES_GENERAL'}).status_code==403
    assert permission_for_request('POST','/api/v1/products','SALES_GENERAL').menu_code=='MASTER_PRODUCT'
    assert permission_for_request('POST','/api/v1/companies/00001/sales/1/statements').action=='create'


def test_sale_lookup_uses_server_search_and_selected_pk(monkeypatch):
    from views.sale_reg import SaleRegWindow
    import views.sale_reg as ui
    from PySide6.QtWidgets import QApplication, QDialog
    app=QApplication.instance() or QApplication([])
    calls=[]
    def get(self,path,**params):
        calls.append((path,params))
        if path=='accounts': return [{'account_id':17,'account_code':'A17','account_name':'선택업체','sales_yn':True}]
        return []
    monkeypatch.setattr(SaleRegWindow,'_get',get)
    monkeypatch.setattr(SaleRegWindow,'_get_account',lambda *args:{})
    def accept(dialog): dialog.accept_current(); return QDialog.Accepted
    monkeypatch.setattr(ui.LookupDialog,'exec',accept)
    window=SaleRegWindow(); window.lookup_customer()
    assert window.customer['account_id']==17
    assert any(params.get('purpose')=='SALE' and params.get('limit')==50 and 'search' in params for _,params in calls)
    window.close()


def test_financing_lookup_connects_product_contractor_shipper(monkeypatch):
    from PySide6.QtWidgets import QApplication, QDialog
    import views.financing_contract_reg as ui
    app=QApplication.instance() or QApplication([])
    calls=[]
    def get(self,path,**params):
        calls.append(params)
        return [{'account_id':7,'account_code':'A7','account_name':'업체'}] if path=='accounts' else []
    monkeypatch.setattr(ui.FinancingContractWindow,'_get',get)
    response=Mock(); response.json.return_value=[]
    monkeypatch.setattr(ui.httpx,'get',Mock(return_value=response))
    monkeypatch.setattr(ui.LookupDialog,'exec',lambda d:(d.accept_current() or QDialog.Accepted))
    window=ui.FinancingContractWindow()
    window.lookup_account(window.contractor,'CONTRACT'); window.lookup_account(window.shipper,'SALE')
    assert window.contractor.currentData()==7 and window.shipper.currentData()==7
    response.json.return_value=[{'product_id':99,'product_code':'P99','product_name':'선택상품'}]
    window.lookup_product(); assert window.product.currentData()==99
    window.item_box.setText('1'); window.item_kg.setText('2'); window.add_item_row()
    assert window._items_payload()[0]['product_id']==99
    assert any(p.get('purpose')=='SALE' and p.get('limit')==50 for p in calls)
    assert ui.httpx.get.call_args.kwargs['params']['search']==''
    window.close()


def test_purchase_lookup_keeps_existing_request_and_pk(monkeypatch):
    from PySide6.QtWidgets import QApplication,QDialog
    import views.purchase_reg as ui
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.PurchaseRegWindow,'load_base_options',lambda self:None)
    monkeypatch.setattr(ui.PurchaseRegWindow,'load_all',lambda self:None)
    monkeypatch.setattr(ui.PurchaseRegWindow,'load_payable_summary',lambda self:None)
    calls=[]
    def options(self,**params):
        calls.append(params)
        return {'suppliers':[{'account_id':42,'account_code':'A42','account_name':'매입처'}]}
    monkeypatch.setattr(ui.PurchaseRegWindow,'_option_request',options)
    monkeypatch.setattr(ui.LookupDialog,'exec',lambda d:(d.accept_current() or QDialog.Accepted))
    window=ui.PurchaseRegWindow(); window.supplier_edit.setText('매입'); window.lookup_supplier()
    assert window._supplier['account_id']==42 and calls[-1]=={'supplier_query':'매입'}
    window.close()
