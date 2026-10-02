import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from decimal import Decimal
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_sales_outbound import api, payload, URL
from views.sale_reg import CancelReasonDialog, SaleRegWindow
from views.purchase_reg import LookupDialog


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
    lot={'lot_id':1,'lot_code':'L1','product_id':1,'product_name':'상품','warehouse_name':'창고','use_yn':True,'individual_cost':1000,'available_box_qty':10,'available_weight':'100','editing_box_qty':0,'editing_weight':'0'}
    def get(self,path,**params):
        if path=='sales/lot-availability': return [dict(lot)]
        if path=='accounts': return [{'account_id':1,'account_name':'거래처','account_code':'A','sales_yn':True}]
        if path=='sales-receivable-summary': return dict(previous_receivable=100,today_sales=200,today_receipt=0,current_receivable=300)
        return []
    monkeypatch.setattr(SaleRegWindow,'_get',get)
    monkeypatch.setattr(SaleRegWindow,'_get_account',lambda self,key:dict(phone='02-111-2222',fax='02-111-3333',tax_email='sales@example.com'))
    window=SaleRegWindow()
    window.set_customer(window.accounts[0]); window.refresh_summary()
    yield window,lot
    window.close()


def enter(window,row,box,kg,price=2000):
    physical_row=row*2
    window.select_lot(row,window.lots[0])
    for col,value in [(3,box),(4,kg),(7,price)]: window.table.cellWidget(physical_row,col).setText(str(value))


def test_gui_same_lot_negative_reason_and_row_delete(gui):
    window,_=gui; enter(window,0,6,'60'); window.add_row(); enter(window,1,5,'41')
    assert window.table.item(1,3).text()=='10 → -1'
    assert window.table.item(3,4).text()=='100.00 → -1.00'
    assert '마이너스' in window.warning.text()
    with pytest.raises(ValueError,match='사유'): window.payload()
    window.reason.setText('선출고'); assert window.payload()['inventory_exception_reason']=='선출고'
    window.table.setCurrentCell(0,3); window.remove_row(); assert window.table.item(1,3).text()=='10 → 5'
    assert window.current_receivable.text()=='현미수금 300'


@pytest.mark.parametrize(('box_input','expected_box'), [('1',1), ('',0), ('0',0)])
def test_gui_box_optional_for_valid_weight_sale(gui,box_input,expected_box):
    window,_=gui
    enter(window,0,box_input,'21.00')
    assert window.payload()['items'][0]['box_qty']==expected_box


def test_gui_multiple_lots_allow_blank_box_in_one_row(gui):
    window,_=gui
    enter(window,0,'','21.00')
    lot_b={**window.lots[0],'lot_id':2,'lot_code':'L2'}
    lot_b.update(available_box_qty=5,available_weight='30.00')
    window.lots.append(lot_b)
    window.add_row()
    window.select_lot(1,lot_b)
    for col,value in [(3,'1'),(4,'22.00'),(7,'2000')]:
        window.table.cellWidget(2,col).setText(value)
    items=window.payload()['items']
    assert [item['lot_id'] for item in items]==[1,2]
    assert [item['box_qty'] for item in items]==[0,1]
    assert [item['weight'] for item in items]==['21.00','22.00']
    assert window.table.item(1,3).text()=='10 → 10'
    assert window.table.item(1,4).text()=='100.00 → 79.00'
    assert window.table.item(3,3).text()=='5 → 4'
    assert window.table.item(3,4).text()=='30.00 → 8.00'


def test_gui_invalid_box_text_is_rejected_as_input_error(gui):
    window,_=gui
    enter(window,0,'1x','21.00')
    with pytest.raises(ValueError,match='BOX'):
        window.payload()


def test_gui_load_edit_save_cancel(gui,monkeypatch):
    window,lot=gui
    sale={'sale_id':2,'sale_no':'SA-2','sale_date':'2026-10-02','account_id':1,'account_name':'거래처','document_status':'CONFIRMED','memo':'원메모','inventory_exception_reason':'기존사유','items':[dict(line_no=1,product_id=1,lot_id=1,box_qty=2,weight='20',unit_price=2000,discount_amount=0,memo='행메모')]}
    lot.update(available_box_qty=8,available_weight='80',editing_box_qty=2,editing_weight='20')
    window.load_sale(sale)
    assert window.table.item(1,3).text()=='8 → 8'
    assert window.table.item(1,4).text()=='80.00 → 80.00'
    assert window.table.item(0,5).text()=='10.00'
    assert window.table.item(1,5).text()=='10.00 → 10.00'
    enter(window,0,3,'30'); assert window.table.item(1,3).text()=='8 → 7'
    assert window.table.item(1,4).text()=='80.00 → 70.00'
    assert window.table.item(1,5).text()=='10.00 → 10.00'
    assert window.payload()['memo']=='원메모' and window.payload()['items'][0]['memo']=='행메모'
    response=Mock(); response.json.return_value=sale
    put=Mock(return_value=response); post=Mock(return_value=response)
    monkeypatch.setattr('views.sale_reg.httpx.put',put); monkeypatch.setattr('views.sale_reg.httpx.post',post)
    monkeypatch.setattr('views.sale_reg.QMessageBox.information',lambda *_:None)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr('views.sale_reg.QMessageBox.question',lambda *_:QMessageBox.Yes)
    window.save(); assert put.call_args.args[0].endswith('/sales/2')
    def accept_cancel_reason(dialog):
        dialog.editor.setPlainText('취소 검증')
        return QDialog.Accepted
    monkeypatch.setattr(CancelReasonDialog,'exec',accept_cancel_reason)
    window.cancel(); assert post.call_args.args[0].endswith('/sales/2/cancel')
    assert post.call_args.kwargs['json']=={'reason':'취소 검증'} and window.sale_id is None
    sale['document_status']='CANCELLED'; window.load_sale(sale)
    assert not window.btn_save.isEnabled() and not window.btn_cancel.isEnabled()


def test_gui_two_level_stock_projection_and_average_weight(gui):
    window,lot=gui
    window.lots[0].update(available_box_qty=100,available_weight='2064.00')
    enter(window,0,'1','20.00')
    assert window.table.item(0,5).text()=='20.00'
    assert window.table.item(1,3).text()=='100 → 99'
    assert window.table.item(1,4).text()=='2,064.00 → 2,044.00'
    assert window.table.item(1,5).text()=='20.64 → 20.65'
    enter(window,0,'0','15.00')
    assert window.table.item(0,5).text()=='—'
    assert window.table.item(1,3).text()=='100 → 100'
    assert window.table.item(1,4).text()=='2,064.00 → 2,049.00'
    assert window.table.item(1,5).text()=='20.64 → 20.49'
    assert window.table.columnWidth(1)>=400


def test_inventory_lookup_uses_arrow_keys_and_enter(gui):
    rows = [{'lot_code':'L1','product_name':'상품 1'},
            {'lot_code':'L2','product_name':'상품 2'}]
    dialog = LookupDialog(gui[0], '재고조회', '', [('LOT','lot_code'),('상품','product_name')], lambda _: rows)
    dialog.show()
    dialog.table.setFocus()
    assert dialog.table.currentRow()==0
    QTest.keyClick(dialog.table, Qt.Key_Down)
    assert dialog.table.currentRow()==1
    QTest.keyClick(dialog.table, Qt.Key_Up)
    assert dialog.table.currentRow()==0
    QTest.keyClick(dialog.table, Qt.Key_Down)
    QTest.keyClick(dialog.table, Qt.Key_Return)
    assert dialog.result()==QDialog.Accepted
    assert dialog.selected['lot_code']=='L2'


def test_cancel_reason_dialog_blank_multiline_and_limit(gui,monkeypatch):
    monkeypatch.setattr('views.sale_reg.QMessageBox.warning',lambda *_:None)
    dialog=CancelReasonDialog(gui[0])
    dialog.accept()
    assert dialog.result()!=QDialog.Accepted
    dialog.editor.setPlainText('   ')
    dialog.accept()
    assert dialog.result()!=QDialog.Accepted
    multiline='첫째 줄\n둘째 줄\n셋째 줄'
    dialog.editor.setPlainText(multiline)
    assert dialog.reason==multiline
    assert dialog.character_count.text()==f'{len(multiline)} / 1000'
    dialog.editor.setPlainText('가'*1200)
    assert len(dialog.editor.toPlainText())==1000
    assert dialog.character_count.text()=='1000 / 1000'
    dialog.reject()


def test_cancel_reason_dialog_valid_reason_and_shortcut(gui):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    dialog=CancelReasonDialog(gui[0])
    dialog.editor.setPlainText('거래처 요청으로 취소\n재고는 원복 확인')
    dialog.show()
    dialog.editor.setFocus()
    QTest.keyClick(dialog.editor,Qt.Key_Return,Qt.ControlModifier)
    assert dialog.result()==QDialog.Accepted
    assert dialog.reason=='거래처 요청으로 취소\n재고는 원복 확인'


def test_cancel_reason_dialog_escape_closes(gui):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    dialog=CancelReasonDialog(gui[0])
    dialog.show()
    QTest.keyClick(dialog.editor,Qt.Key_Escape)
    assert dialog.result()==QDialog.Rejected


def test_gui_date_list_header_and_memo(gui):
    window,_=gui
    base={'sale_id':2,'sale_no':'SA-2','sale_date':window.date.date().toString('yyyy-MM-dd'),'account_id':1,'account_code':'A','account_name':'거래처','document_status':'CONFIRMED','total_amount':40000,'memo':'전표 메모','items':[dict(line_no=1,product_id=1,lot_id=1,box_qty=2,weight='20',unit_price=2000,discount_amount=0,memo='행 메모')]}
    window.saved=[base,{**base,'sale_id':3,'sale_date':'2000-01-01'},
                  {**base,'sale_id':4,'document_status':'CANCELLED'},
                  {**base,'sale_id':5,'document_status':' cancelled '}]
    window.refresh_today(); assert window.today_table.rowCount()==1
    window.today_table.selectRow(0)
    assert window.sale_id==2 and window.document_no.text()=='SA-2'
    assert window.customer_edit.text()=='거래처 (A)' and window.memo.toPlainText()=='전표 메모'
    window.memo.setPlainText('변경된 메모'); window.table.cellWidget(0,11).setText('상세 메모')
    assert window.payload()['memo']=='변경된 메모' and window.payload()['items'][0]['memo']=='상세 메모'
    assert 'BOX 2 / 중량 20.00 KG / 매출액 40,000' in window.total_label.text()


def test_gui_exception_visibility_blank_row_and_enter(gui,monkeypatch):
    window,_=gui
    assert window.exception_panel.isHidden()
    enter(window,0,11,'50'); assert not window.exception_panel.isHidden()
    assert 'color:#b71c1c' in window.table.cellWidget(0,3).styleSheet()
    enter(window,0,1,'10'); assert window.exception_panel.isHidden()
    window.add_row(); assert len(window.payload()['items'])==1
    focus=[]; monkeypatch.setattr(window,'_focus_cell',lambda row,col:focus.append((row,col)))
    window.table.cellWidget(0,3).returnPressed.emit(); assert focus[-1]==(0,4)
    window.table.setCurrentCell(0,3); window.remove_row()
    window.table.cellWidget(0,3).returnPressed.emit(); assert focus[-1]==(0,4)


def test_profit_rounding_zero_revenue_and_loss(gui):
    window,lot=gui
    assert window.profit_values(Decimal('1.25'),6001,5001)==(7502,6252,1250,Decimal('16.66'))
    assert window.profit_values(Decimal('10.00'),0,1000)==(0,10000,-10000,None)
    enter(window,0,1,'10.00',6000)
    assert window.table.item(0,6).text()=='1,000'
    assert window.table.item(0,8).text()=='60,000'
    assert window.table.item(0,9).text()=='50,000'
    assert window.table.item(0,10).text()=='83.33%'
    assert '매출원가 10,000 / 매출이익 50,000' in window.total_label.text()
    enter(window,0,1,'10.00',900)
    assert window.table.item(0,9).text()=='-1,000'
    assert window.table.item(0,10).text()=='-11.11%'
    assert window.table.item(0,9).foreground().color().name()=='#b71c1c'
    assert window.payload()['items'][0]['unit_price']==900
    lot.pop('individual_cost'); window.refresh_inventory()
    assert window.table.item(0,6).text()=='미확인'
    assert '매출원가 미확인' in window.total_label.text()


def test_customer_contacts_change_and_reset(gui,monkeypatch):
    window,_=gui
    assert (window.phone.text(),window.fax.text(),window.email.text())==('02-111-2222','02-111-3333','sales@example.com')
    monkeypatch.setattr(SaleRegWindow,'_get_account',lambda self,key:dict(phone='031-1234',fax=None,tax_email='other@example.com'))
    window.set_customer(dict(account_id=2,account_code='B',account_name='다른거래처'))
    assert (window.phone.text(),window.fax.text(),window.email.text())==('031-1234','—','other@example.com')
    window.new_sale(keep_date=True)
    assert (window.phone.text(),window.fax.text(),window.email.text())==('—','—','—')
    window.set_customer(window.accounts[0]); window.clear_customer()
    assert window.email.text()=='—' and window.customer is None
    window.set_customer(window.accounts[0])
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr('views.sale_reg.QMessageBox.question',lambda *_:QMessageBox.Yes)
    window.reset_input(); assert window.phone.text()=='—'
