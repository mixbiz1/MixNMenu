import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from decimal import Decimal
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication
from test_sales_outbound import api, payload, URL
from views.sale_reg import SaleRegWindow


def test_availability_current_edit_and_cancel(api):
    client,factory=api
    endpoint=URL+'/lot-availability'
    assert client.get(endpoint).json()[0]['available_box_qty']==10
    sale=client.post(URL,json=payload()).json()
    lot=client.get(endpoint,params={'editing_sale_id':sale['sale_id']}).json()[0]
    assert (lot['available_box_qty'],Decimal(str(lot['available_weight'])))==(8,Decimal('80'))
    assert (lot['editing_box_qty'],Decimal(str(lot['editing_weight'])))==(2,Decimal('20'))
    assert client.get(endpoint,params={'editing_sale_id':999}).status_code==404
    assert client.get('/api/v1/companies/OTHER/sales/lot-availability',params={'editing_sale_id':sale['sale_id']}).status_code==404
    response=client.put(URL+'/'+str(sale['sale_id']),json=payload(3,'30')); assert response.status_code==200,response.text
    assert client.get(endpoint).json()[0]['available_box_qty']==7
    with factory() as db:
        from audit_service import AuditEvent
        import models
        assert db.get(models.Sale,sale['sale_id']).document_status=='CONFIRMED'
        assert db.query(AuditEvent).order_by(AuditEvent.audit_event_id.desc()).first().action=='UPDATE'
    invalid=payload(11,'110'); assert client.put(URL+'/'+str(sale['sale_id']),json=invalid).status_code==409
    assert client.get(endpoint).json()[0]['available_box_qty']==7
    client.post(URL+'/'+str(sale['sale_id'])+'/cancel',json={'reason':'테스트'})
    lot=client.get(endpoint,params={'editing_sale_id':sale['sale_id']}).json()[0]
    assert lot['available_box_qty']==10 and lot['editing_box_qty']==0

@pytest.fixture
def gui(monkeypatch):
    application=QApplication.instance() or QApplication([])
    lot={'lot_id':1,'lot_code':'L1','product_id':1,'product_name':'상품','warehouse_name':'창고','use_yn':True,'available_box_qty':10,'available_weight':'100','editing_box_qty':0,'editing_weight':'0'}
    def get(self,path,**params):
        if path=='sales/lot-availability': return [dict(lot)]
        if path=='accounts': return [{'account_id':1,'account_name':'거래처','account_code':'A','sales_yn':True}]
        if path=='sales-receivable-summary': return dict(previous_receivable=100,today_sales=200,today_receipt=0,current_receivable=300)
        return []
    monkeypatch.setattr(SaleRegWindow,'_get',get)
    window=SaleRegWindow()
    yield window,lot
    window.close()


def enter(window,row,box,kg,price=2000):
    for col,value in [(3,box),(4,kg),(5,price)]: window.table.item(row,col).setText(str(value))


def test_gui_same_lot_negative_reason_and_row_delete(gui):
    window,_=gui; enter(window,0,6,'60'); window.add_row(); enter(window,1,5,'41')
    assert window.table.item(0,9).text()=='-1'
    assert window.table.item(1,10).text()=='-1.00'
    assert '마이너스' in window.warning.text()
    with pytest.raises(ValueError,match='사유'): window.payload()
    window.reason.setText('선출고'); assert window.payload()['inventory_exception_reason']=='선출고'
    window.table.setCurrentCell(0,3); window.remove_row(); assert window.table.item(0,9).text()=='5'
    assert '현재 미수: 300원' in window.summary.text()


def test_gui_load_edit_save_cancel(gui,monkeypatch):
    window,lot=gui
    sale={'sale_id':2,'sale_no':'SA-2','sale_date':'2026-10-02','account_id':1,'account_name':'거래처','document_status':'CONFIRMED','memo':'원메모','inventory_exception_reason':'기존사유','items':[dict(line_no=1,product_id=1,lot_id=1,box_qty=2,weight='20',unit_price=2000,discount_amount=0,memo='행메모')]}
    lot.update(available_box_qty=8,available_weight='80',editing_box_qty=2,editing_weight='20')
    window.load_sale(sale)
    assert window.table.item(0,9).text()=='8'
    assert window.table.item(0,10).text()=='80.00'
    enter(window,0,3,'30'); assert window.table.item(0,9).text()=='7'
    assert window.payload()['memo']=='원메모' and window.payload()['items'][0]['memo']=='행메모'
    response=Mock(); response.json.return_value=sale
    put=Mock(return_value=response); post=Mock(return_value=response)
    monkeypatch.setattr('views.sale_reg.httpx.put',put); monkeypatch.setattr('views.sale_reg.httpx.post',post)
    monkeypatch.setattr('views.sale_reg.QMessageBox.information',lambda *_:None)
    window.save(); assert put.call_args.args[0].endswith('/sales/2')
    monkeypatch.setattr('views.sale_reg.QInputDialog.getText',lambda *_:('취소 검증',True))
    window.cancel(); assert post.call_args.args[0].endswith('/sales/2/cancel')
    assert post.call_args.kwargs['json']=={'reason':'취소 검증'} and window.sale_id is None
    sale['document_status']='CANCELLED'; window.load_sale(sale)
    assert not window.btn_save.isEnabled() and not window.btn_cancel.isEnabled()
