"""Real Qt/API adapters, permission isolation, PDF and SQL Server DDL safety."""
import copy
import json
from pathlib import Path
import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow,call,BASE
from test_batch2a_gui_permissions import ui_adapter
from test_batch2a_migration import Connection
from test_financing_phase2 import ready,separate,receive,assign,apply,request_and_confirm,bank_ship,complete_contract,close_data
from permissions import issue_token,permission_for_request
import models
import db_financing_phase2_migrate as migration


def test_migration_fk_order_unicode_nullable_unique_and_prerequisite_guard(monkeypatch):
    batches=migration.statements();creates=[x for x in batches if 'CREATE TABLE' in x]
    assert len(creates)==6
    new=set()
    for table,sql in zip(migration.TABLES,creates):
        assert f'CREATE TABLE dbo.{table.name}' in sql and 'IF OBJECT_ID' in sql
        assert 'DROP' not in sql and 'ALTER TABLE' not in sql and 'CREATE INDEX' not in sql
        for fk in table.foreign_keys:
            assert f'REFERENCES dbo.{fk.column.table.name} ({fk.column.name})' in sql
            assert fk.column.table not in migration.TABLES or fk.column.table.name in new
        new.add(table.name)
    assert any("CK_fin_contract_status" in x and "'SETTLED'" in x and "'CLOSED'" in x for x in batches)
    assert any("CK_account_tx_type" in x and "'DEPOSIT_APPLIED'" in x and "WITH CHECK" in x for x in batches)
    nullable=[x for x in batches if 'UQ_fin_charge_transaction' in x or 'UQ_fin_deposit_move_transaction' in x]
    assert all('WHERE transaction_id IS NOT NULL' in x for x in nullable)
    connection=Connection()
    class Engine:
        def begin(self):return connection
    monkeypatch.setattr(migration,'engine',Engine())
    migration.migrate();first=list(connection.batches);migration.migrate();assert connection.batches==first+first
    assert not any('tb_user_menu_permission' in x for x,_ in first)
    assert {p['code'] for _,p in first if p and 'code' in p}=={'FINANCING_DEPOSIT','FINANCING_CLOSE'}
    missing=Connection(missing=('tb_fin_release','release_id'))
    monkeypatch.setattr(Engine,'begin',lambda self:missing)
    with pytest.raises(RuntimeError):migration.migrate()
    assert not missing.batches


def test_new_menu_permissions_do_not_borrow_write_and_cross_company(flow):
    client,factory=flow
    assert permission_for_request('GET',BASE+'/financing-deposits').menu_code=='FINANCING_DEPOSIT'
    assert permission_for_request('POST',BASE+'/financing-deposits/1/apply').action=='update'
    assert permission_for_request('GET',BASE+'/financing-closures/contracts/1').menu_code=='FINANCING_CLOSE'
    assert permission_for_request('POST',BASE+'/financing-closures/contracts/1/close').action=='update'
    assert permission_for_request('GET',BASE+'/financing-releases',lookup_for='FINANCING_DEPOSIT').menu_code=='FINANCING_DEPOSIT'
    assert permission_for_request('POST',BASE+'/financing-releases',lookup_for='FINANCING_DEPOSIT').menu_code=='FINANCING_RELEASE'
    with factory() as db:
        db.add(models.User(user_id='phase2-reader',user_name='읽기전용',password_hash='x',is_admin=False));db.commit()
        db.add(models.UserCompanyAccess(user_id='phase2-reader',comp_code='00001'));db.commit()
    client.headers['Authorization']='Bearer '+issue_token('phase2-reader')
    assert client.get(BASE+'/financing-deposits').status_code==403
    assert client.post(BASE+'/financing-deposits',json={}).status_code==403
    assert client.get(BASE+'/financing-closures').status_code==403


def test_gui_deposit_receive_assign_apply_and_close_adapters(flow,ui_adapter,monkeypatch):
    from views.financing_settlement import FinancingDepositWindow,FinancingClosureWindow
    client,factory=flow;payload=complete_contract(flow);release=request_and_confirm(client,payload)
    window=FinancingDepositWindow();window.account.setProperty('pk',1);window.day.setText('2026-10-01');window.amount.setText('1000');window.reference.setText('GUI-BANK')
    window.receive();assert window.current['balance']==1000
    window.contract.setProperty('pk',payload['contract_id']);window.day.setText('2026-10-02');window.assign()
    assert window.assignment.count()==1
    window.release.setProperty('pk',release['release_id']);window.day.setText('2026-10-05');window.reason.setText('계약대금 상계 합의');window.apply()
    assert window.current['applied_amount']==1000
    bank_ship(client,release,int(release['total_amount'])-1000)
    call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':int(release['total_amount'])-1000,'bank_reference':'OUTPUT-CASH-REMAINDER'})
    closer=FinancingClosureWindow();closer.contract.setProperty('pk',payload['contract_id']);closer.reconcile()
    assert closer.reconciliation['can_close']
    closer.day.setText('2026-10-06');closer.reason.setText('최종대사');closer.reference.setText('GUI-FINAL')
    closer.cost_review.setChecked(True);closer.bank_review.setChecked(True);closer.close_contract()
    assert closer.current['snapshot']['remaining_receivable']==0
    saved=closer.current['closure_id'];closer.clear();closer.load(closer.request('get',f'/{saved}'));assert 'CLOSED' in closer.summary.text()
    window.close();closer.close()


def test_negative_ordinary_receipt_cannot_reverse_deposit_only_application(flow):
    client,_=flow;payload,_=ready(flow);deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'])
    release=request_and_confirm(client,payload);apply(client,deposit,assignment,release)
    bank_ship(client,release,int(release['total_amount'])-500)
    call(client,'POST','/receipts',409,json={'account_id':1,'receipt_date':'2026-10-05','amount':-1,'memo':'보증금 반제는 별도'})
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['applied_amount']==500


def test_new_transaction_atomicity_even_after_late_audit_failure(flow,monkeypatch):
    import financing_deposit_routes as deposits
    client,factory=flow
    monkeypatch.setattr(deposits,'record_audit_event',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('late audit')))
    response=client.post(BASE+'/financing-deposits',json={'account_id':1,'received_on':'2026-10-01','amount':1000,'request_key':'late-audit','bank_reference':'LATE-AUDIT'})
    assert response.status_code==500
    with factory() as db:
        assert db.query(models.FinancingDeposit).count()==0
        assert db.query(models.FinancingBankEvidence).count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='DEPOSIT_RECEIPT').count()==0


def test_phase2_real_korean_a4_pdfs_multipage_frozen_closure(flow,qt_application,tmp_path):
    from financing_settlement_document import export_deposit_pdf,export_closure_pdf
    from financing_release_document import export_request_pdf
    from PySide6.QtPdf import QPdfDocument
    client,factory=flow;payload=complete_contract(flow)
    with factory() as db:
        db.get(models.Company,'00001').bank1='테스트은행 123-456 예금주 테스트';db.commit()
    deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'],1000)
    release=request_and_confirm(client,payload);apply(client,deposit,assignment,release,1000)
    bank_ship(client,release,int(release['total_amount'])-1000)
    call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':int(release['total_amount'])-1000,'bank_reference':'OUTPUT-CASH-REMAINDER'})
    closed=call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",201,json=close_data())
    deposit=call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")
    release=call(client,'GET',f"/financing-releases/{release['release_id']}")
    targets=[(tmp_path/'deposit.pdf',lambda target:export_deposit_pdf(deposit,target),'보증금 원장'),
             (tmp_path/'closed.pdf',lambda target:export_closure_pdf(closed['snapshot'],target,'CLOSED'),'최종정산내역'),
             (tmp_path/'funded.pdf',lambda target:export_request_pdf(release,target),'현재 보증금 충당')]
    reader=QPdfDocument()
    for filename,render,label in targets:
        render(filename);assert reader.load(str(filename))==QPdfDocument.Error.None_
        assert reader.pageCount()==1 and label in reader.getAllText(0).text()
        size=reader.pagePointSize(0);assert abs(size.width()-595)<2 and abs(size.height()-842)<2;reader.close()
    frozen=copy.deepcopy(closed['snapshot']);many=copy.deepcopy(frozen);many['lots']*=80
    export_closure_pdf(many,tmp_path/'many-closed.pdf','CLOSED');reader.load(str(tmp_path/'many-closed.pdf'));assert reader.pageCount()>1
    extracted='\n'.join(reader.getAllText(i).text() for i in range(reader.pageCount()))
    assert extracted.count(frozen['lots'][0]['lot_code'])==len(many['lots']);reader.close()
    with factory() as db:
        db.get(models.Product,1).product_name='변경 Master';db.get(models.Account,1).account_name='변경된 보증금 업체명';db.commit()
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['account_name']==deposit['account_name']
    again=call(client,'GET',f"/financing-closures/{closed['closure_id']}");assert again['snapshot']==frozen


def test_mixed_tax_pdf_separate_invoice_target_not_added_to_product_request(flow,qt_application,tmp_path):
    from financing_release_document import export_request_pdf
    from PySide6.QtPdf import QPdfDocument
    client,factory=flow;payload,_=ready(flow);separate(factory,payload)
    with factory() as db:db.get(models.Company,'00001').bank1='테스트은행 123-456';db.commit()
    release=request_and_confirm(client,payload);target=tmp_path/'mixed.pdf';export_request_pdf(release,target)
    reader=QPdfDocument();assert reader.load(str(target))==QPdfDocument.Error.None_
    text='\n'.join(reader.getAllText(i).text() for i in range(reader.pageCount()))
    assert '별도청구 내역' in text and '세금계산서 발행대상' in text and '현재 보증금' not in text
    assert '27' in text and '29' in text
    reader.close()
