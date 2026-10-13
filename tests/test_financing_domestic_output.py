"""Confirmed domestic source and read-only Korean A4 request output."""
import copy
import json
from datetime import date
from decimal import Decimal
import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow,call
from test_batch2a_contract_import_cost import ready_case
from test_financing_releases import ready,ship
from test_batch2a_gui_permissions import ui_adapter
import models


def domestic(flow):
    client,factory=flow;contract,case,purchase=ready_case(flow,'DOMESTIC_PURCHASE')
    with factory() as db:
        row=db.get(models.FinancingContract,contract['contract_id']);row.financing_start_date=date(2026,10,1)
        term=row.terms[0];term.recovery_template='EXCLUDE_BROKERAGE'
        conditions=json.loads(term.conditions_json)
        conditions['expense_conditions']=[{'code':code,'basis':basis,'unit_rate':rate,'tax_treatment':'EXEMPT','payer':'ACTUAL_SHIPPER'}
             for code,basis,rate in [('STORAGE','KG_DAY','0.9'),('INOUT','KG','0'),('WEIGHING','BOX','0')]]
        term.conditions_json=json.dumps(conditions);db.commit()
    item=purchase['items'][0]
    call(client,'POST',f"/financing-contracts/{contract['contract_id']}/lots",201,json={'lot_id':item['lot_id'],
        'contract_item_id':contract['items'][0]['contract_item_id'],'contract_box_qty':item['box_qty'],'contract_weight':str(item['weight'])})
    return {'contract_id':contract['contract_id'],'shipper_account_id':1,'release_date':'2026-10-05',
            'interest_year_days':365,'request_key':'domestic','lines':[{'lot_id':purchase['items'][0]['lot_id'],'box_qty':1,'weight':'10.00'}]}


def test_domestic_confirmed_purchase_without_import_allocation_and_repeat(flow):
    client,factory=flow;payload=domestic(flow);row=ship(client,payload)
    line=row['snapshot']['lines'][0]
    assert line['allocation_id'] is None and line['settlement_id'] is None
    assert line['cost_source']['kind']=='DOMESTIC_PURCHASE'
    assert Decimal(line['components']['COST'])==10000
    assert Decimal(line['components']['STORAGE'])==45
    again=ship(client,{**payload,'request_key':'domestic-repeat'})
    assert again['sale_id']!=row['sale_id']
    with factory() as db:assert db.query(models.ImportCostAllocation).count()==0


@pytest.mark.parametrize('problem',['discount','changed_cost','missing_inbound','cancelled_purchase','unknown_contract'])
def test_ambiguous_domestic_cost_is_blocked(flow,problem):
    client,factory=flow;payload=domestic(flow)
    with factory() as db:
        lot=db.get(models.Lot,payload['lines'][0]['lot_id']);item=db.query(models.PurchaseItem).filter_by(lot_id=lot.lot_id).one()
        if problem=='discount':item.discount_amount=1
        if problem=='changed_cost':lot.individual_cost+=1
        if problem=='missing_inbound':item.inbound_item_id=None
        if problem=='cancelled_purchase':item.purchase.document_status='CANCELLED'
        if problem=='unknown_contract':db.get(models.FinancingContract,payload['contract_id']).contract_type='IMPORT_AGENCY'
        db.commit()
    call(client,'POST','/financing-releases',409,json=payload)


def test_domestic_shipping_rechecks_exact_cost_source(flow):
    client,factory=flow;payload=domestic(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    with factory() as db:
        item=db.query(models.PurchaseItem).filter_by(lot_id=payload['lines'][0]['lot_id']).one();item.supply_amount+=1;db.commit()
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",409)
    with factory() as db:assert db.query(models.Sale).count()==0


def test_pdf_korean_a4_snapshot_only_and_many_rows(flow,tmp_path,qt_application):
    from financing_release_document import export_request_pdf,request_html
    from PySide6.QtPdf import QPdfDocument
    client,factory=flow;payload=domestic(flow)
    with factory() as db:db.get(models.Company,'00001').bank1='테스트은행 123-456 예금주 테스트';db.commit()
    row=call(client,'POST','/financing-releases',201,json=payload)
    row=call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    frozen=copy.deepcopy(row)
    with factory() as db:db.get(models.Company,'00001').bank1='현재계좌 사용금지';db.commit()
    target=tmp_path/'request.pdf';export_request_pdf(row,target)
    pdf=QPdfDocument();assert pdf.load(str(target))==QPdfDocument.Error.None_
    assert pdf.pageCount()==1
    text=pdf.getAllText(0).text();assert '입금요청서' in text and '123-456' in text and '현재계좌' not in text
    size=pdf.pagePointSize(0);assert abs(size.width()-595)<2 and abs(size.height()-842)<2
    pdf.close();assert row==frozen
    many=copy.deepcopy(row);many['snapshot']['lines']*=60;many['snapshot']['prepared_lines']*=60
    export_request_pdf(many,tmp_path/'many.pdf');pdf.load(str(tmp_path/'many.pdf'))
    assert pdf.pageCount()>1;pdf.close()
    escaped=copy.deepcopy(row);escaped['snapshot']['shipper']['name']='<script>test</script>'
    assert '<script>' not in request_html(escaped)
    broken=copy.deepcopy(row);broken['snapshot']['bank_account']=''
    original=target.read_bytes()
    with pytest.raises(ValueError):export_request_pdf(broken,target)
    assert target.read_bytes()==original


def test_gui_pdf_only_reads_saved_request(flow,ui_adapter,monkeypatch,tmp_path):
    from views.financing_release import FinancingReleaseWindow
    import views.financing_release as ui
    import financing_release_document as output
    client,_=flow;payload=domestic(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    window=FinancingReleaseWindow();window.load(row);calls=[]
    monkeypatch.setattr(window,'request',lambda method,path,**kw:(calls.append((method,path)) or row))
    monkeypatch.setattr(ui.QFileDialog,'getSaveFileName',lambda *a:(str(tmp_path/'gui.pdf'),'PDF'))
    monkeypatch.setattr(output,'export_request_pdf',lambda saved,path:assert_saved(saved,row))
    window.export_pdf();assert calls==[('get',f"/{row['release_id']}")];window.close()


def assert_saved(saved,row):assert saved==row
