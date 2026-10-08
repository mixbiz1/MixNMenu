"""Document provenance/presentation only; no invented agreement rates or legal names."""
import copy
import json
from decimal import Decimal

import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mssql
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow, call
from test_batch2a_contract_import_cost import contract_data, confirmed_contract
from test_batch2a_gui_permissions import ui_adapter
from test_contract_document_v1 import source, plain, assert_pdf_body_preserved
from contract_document_templates import FORMS, render, validation, RATE_INPUT_KEY, RATE_FIELDS
from financing_document import export_contract_pdf, document_html
from audit_service import AuditEvent
import models

COSTS = [('storage_rate_per_kg_day','STORAGE','창고료 기준'),
         ('inbound_outbound_rate_per_kg','INBOUND_OUTBOUND','입출고비'),
         ('weighing_rate_per_box','WEIGHING','계근비')]


@pytest.mark.parametrize('field,code,label',COSTS)
@pytest.mark.parametrize('case',['null','legacy_zero','explicit_zero','expense_zero'])
def test_missing_and_explicit_zero_are_not_interchangeable(qt_application,field,code,label,case):
    data=source(); term=data['contract']['terms'][0]
    term[field]=None if case=='null' else '0.000000'
    if case=='explicit_zero': term['conditions'][RATE_INPUT_KEY]={field:True}
    if case=='expense_zero':
        term['conditions']['expense_conditions']=[{'code':code,'basis':'KG','unit_rate':'0',
            'tax_treatment':'EXEMPT','payer':'ORIGINAL_CONTRACTOR'}]
        if code=='STORAGE': label='창고료'
    before=copy.deepcopy(data); text=plain(render(data,'IMPORT_AGENCY'))
    assert (label+': 미확정' in text)==(case in {'null','legacy_zero'})
    assert (label+': 0.00원' in text)==(case in {'explicit_zero','expense_zero'})
    assert data==before


def test_explicit_null_expense_is_unconfirmed_and_not_hidden_or_defaulted(qt_application):
    data=source(); term=data['contract']['terms'][0]
    term['storage_rate_per_kg_day']='999'
    term['conditions']['expense_conditions']=[{'code':'STORAGE','unit_rate':None,'basis':'KG_DAY'}]
    visible=plain(render(data,'IMPORT_AGENCY'))
    assert '창고료: 미확정' in visible and '999' not in visible
    assert any('창고료' in item for item in validation(data,'IMPORT_AGENCY')['optional'])


@pytest.mark.parametrize('form',list(FORMS))
def test_legal_name_not_guessed_and_original_master_details_preserved(qt_application,form):
    data=source(FORMS[form][1]); data['partner']['name']='(계약)(주)제이케이미트코퍼레이션_장봉근'
    text=plain(render(data,form)); report=validation(data,form)
    assert '(계약)' not in text and '제이케이미트코퍼레이션' not in text
    assert '206-86-72085' in text and '계약 대표' in text and '경기도 하남시' in text
    assert any('법적 상호' in item for item in report['required'])
    # An underscore or parentheses in a real registered name must not be stripped.
    data['partner']['name']='(주)한글_법인(서울)'
    assert '(주)한글_법인(서울)' in plain(render(data,form))


def test_mapping_has_no_usd_deposit_or_period_invention(qt_application):
    data=source(); term=data['contract']['terms'][0]
    term['contract_days']=None; term['interest_period_days_1']=90
    data['company']['bank1']=None
    data['contract'].update(deposit_required=True,deposit_amount=30000)
    data['contract']['items'][0]['contract_unit_price']=123456789
    text=plain(render(data,'IMPORT_AGENCY')); review=validation(data,'IMPORT_AGENCY')
    assert '123,456,789' not in text
    assert '검역완료시점부터 ________일이내' in text and '1차 이자 적용기간: 90일' in text
    assert '________% (협의)' in text and '계약 보증금: 30,000원' in text
    assert '판매대금 입금계좌: ________' in text
    for label in ['USD','보증금 비율','출고약정기간','입금계좌']:
        assert any(label in item for item in review['required'])
    assert any('연장' in item for item in validation({**data,'contract':{**data['contract'],'terms':[]}},'IMPORT_AGENCY')['optional'])


@pytest.mark.parametrize('mode',['omitted','explicit_zero','gui_blank'])
def test_api_keeps_numeric_columns_and_records_zero_provenance(flow,qt_application,mode):
    client,factory=flow; payload=contract_data(); term=payload['terms'][0]
    term.pop('storage_rate_per_kg_day')
    if mode=='explicit_zero':
        for field in RATE_FIELDS: term[field]='0'
    if mode=='gui_blank':
        for field in RATE_FIELDS: term[field]='0'
        term['conditions']={RATE_INPUT_KEY:{field:False for field in COST_FIELD_NAMES}}
    row=call(client,'POST','/financing-contracts',201,json=payload)
    saved=call(client,'GET',f"/financing-contracts/{row['contract_id']}")['terms'][0]
    flags=saved['conditions'][RATE_INPUT_KEY]
    for field in COST_FIELD_NAMES:
        assert Decimal(saved[field])==0
        assert flags[field] is (mode=='explicit_zero')
    call(client,'POST',f"/financing-contracts/{row['contract_id']}/confirm")
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':row['contract_id'],'template_type':'IMPORT_AGENCY'})
    text=plain(doc['body'])
    assert ('입출고비: 0.00원/Kg' in text)==(mode=='explicit_zero')
    assert ('입출고비: 미확정' in text)==(mode!='explicit_zero')
    with factory() as db:
        contract=db.get(models.FinancingContract,row['contract_id'])
        assert contract.terms[0].storage_rate_per_kg_day==0
        assert db.query(AuditEvent).filter_by(entity_type='FINANCING_CONTRACT_TERM').count()==1


COST_FIELD_NAMES = [entry[0] for entry in COSTS]


def test_invalid_presence_is_rejected_atomically(flow):
    client,factory=flow; payload=contract_data()
    payload['terms'][0]['conditions']={RATE_INPUT_KEY:{'storage_rate_per_kg_day':False}}
    call(client,'POST','/financing-contracts',400,json=payload)
    with factory() as db:
        assert db.query(models.FinancingContract).count()==0
        assert db.query(models.FinancingContractTerm).count()==0
        assert db.query(AuditEvent).count()==0


def test_schema_proves_legacy_missing_costs_cannot_be_null_without_migration():
    table=models.FinancingContractTerm.__table__
    sql=str(CreateTable(table).compile(dialect=mssql.dialect()))
    for name in COST_FIELD_NAMES:
        assert table.c[name].nullable is False
        assert table.c[name].default.arg==0
        assert f'{name} NUMERIC(18, 6) NOT NULL' in sql


def test_gui_blank_and_zero_round_trip_and_review_without_silent_mutation(flow,ui_adapter,monkeypatch):
    ui,_=ui_adapter; client,_=flow
    from views.financing_contract_reg import FinancingContractWindow
    window=FinancingContractWindow()
    for field in [window.storage,window.inout,window.weighing]: field.clear()
    missing=window._term_payload()
    assert all(missing['conditions'][RATE_INPUT_KEY][field] is False for field in COST_FIELD_NAMES)
    window.inout.setText('0')
    for combo in [window.expense_fields['inbound_outbound'][2],window.expense_fields['inbound_outbound'][3]]:
        combo.setCurrentIndex(1)
    zero=window._term_payload()
    assert zero['conditions'][RATE_INPUT_KEY]['inbound_outbound_rate_per_kg'] is True
    assert zero['conditions']['expense_conditions'][0]['unit_rate']=='0'
    window.close()
    contract=confirmed_contract(client)
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    with flow[1]() as db: count=db.query(AuditEvent).count()
    review=ui.ContractDocumentWindow(); review.load(doc)
    assert '필수 확인' in review.validation.toPlainText() and 'USD' in review.validation.toPlainText()
    assert '선택·추가조건' in review.validation.toPlainText()
    assert review.body.isReadOnly() is False
    with flow[1]() as db: assert db.query(AuditEvent).count()==count
    review.close()


@pytest.mark.parametrize('form',list(FORMS))
def test_all_forms_pdf_content_policy_and_snapshot_reprint(qt_application,tmp_path,form,monkeypatch):
    from PySide6.QtPdf import QPdfDocument
    import PySide6.QtPrintSupport as native
    monkeypatch.setattr(native,'QPrinter',lambda *args,**kwargs:pytest.fail('native discovery'))
    data=source(FORMS[form][1]); term=data['contract']['terms'][0]
    term['conditions'].update({RATE_INPUT_KEY:{field:True for field in COST_FIELD_NAMES},
        'expense_conditions':[{'code':'BROKERAGE','tax_treatment':'TAXABLE','payer':'ORIGINAL_CONTRACTOR'}]})
    term.update(inbound_outbound_rate_per_kg='0',weighing_rate_per_box='0')
    body=render(data,form)
    row={'body':body,'status':'DRAFT','version':1,'snapshot':{**data,'body_format':'HTML'}}
    before=copy.deepcopy(row); texts=[]
    for status in ['DRAFT','CONFIRMED']:
        row['status']=status
        if status=='CONFIRMED': row['snapshot']['body']=body
        file=tmp_path/f'{form}_{status}.pdf'; export_contract_pdf(row,file)
        reader=QPdfDocument(); assert reader.load(str(file))==QPdfDocument.Error.None_
        assert reader.pageCount()==1
        size=reader.pagePointSize(0); assert abs(size.width()-595.28)<1 and abs(size.height()-841.89)<1
        text=assert_pdf_body_preserved(reader,body); texts.append(text)
        assert ('초안 / 검토용' in text)==(status=='DRAFT')
        assert ('49,512,128' in text)==(form in {'BL_TRANSFER_TAX','DOMESTIC_PURCHASE'})
        if form=='BL_TRANSFER_CUSTOMS':
            assert not any(label in text for label in ['금액','0.00원','7.00%','1.50%'])
        else:
            assert '계약 대표' in text
        reader.close()
    assert row['body']==before['body'] and row['version']==1
    frozen=copy.deepcopy(row)
    row['body']='Master 변경 무시'
    assert document_html(row)==body
    assert frozen['snapshot']['body']==body


def test_existing_document_id_snapshot_never_rewritten_by_validation_or_template_update(flow,qt_application):
    client,factory=flow; contract=confirmed_contract(client)
    row=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    with factory() as db:
        stored=db.get(models.ContractDocument,1); source_data=json.loads(stored.snapshot_json)
        source_data['template_revision']='20261008.v1'
        source_data['contract']['terms'][0]['conditions'].pop(RATE_INPUT_KEY,None)
        stored.snapshot_json=json.dumps(source_data)
        stored.body=stored.body.replace('입출고비: 미확정','입출고비: 0.00원/Kg')
        db.commit()
        raw=stored.snapshot_json; body=stored.body; count=db.query(AuditEvent).count()
    doc=call(client,'GET','/contract-documents/1')
    assert doc['validation']['required'] and doc['document_id']==1 and doc['version']==1
    with factory() as db:
        stored=db.get(models.ContractDocument,1)
        assert stored.snapshot_json==raw and stored.body==body and stored.status=='DRAFT'
        assert db.query(AuditEvent).count()==count
    # Explicit regenerate is the existing audited action and keeps the old source.
    regenerated=call(client,'POST','/contract-documents/1/regenerate',json={'reason':'데이터 표시 검토'})
    assert (regenerated['document_id'],regenerated['version'],regenerated['status'])==(1,1,'DRAFT')
    assert '입출고비: 미확정' in regenerated['body']
    confirmed=call(client,'POST','/contract-documents/1/confirm')
    with factory() as db:
        stored=db.get(models.ContractDocument,1); raw=stored.snapshot_json
        db.get(models.Account,1).account_name='변경한 Master'; db.commit()
    assert call(client,'GET','/contract-documents/1')['snapshot']==confirmed['snapshot']
    with factory() as db: assert db.get(models.ContractDocument,1).snapshot_json==raw
    call(client,'POST','/contract-documents/1/regenerate',409,json={'reason':'확정본 보호'})


@pytest.mark.parametrize('first,fallback,label',[('interest_rate_1','annual_interest_rate','연금리'),
                                                 ('brokerage_rate_1','brokerage_rate','수입원가의')])
def test_default_rate_zero_is_not_certified_as_a_free_agreement(qt_application,first,fallback,label):
    data=source(); term=data['contract']['terms'][0]
    term[first]=term[fallback]='0'
    missing=plain(render(data,'IMPORT_AGENCY'))
    assert label+' ________' in missing
    term['conditions'][RATE_INPUT_KEY]={fallback:True}
    explicit=plain(render(data,'IMPORT_AGENCY'))
    assert label+' 0.00%' in explicit


def test_gui_reloads_explicit_zero_rates_and_prices_without_blank_coercion(flow,ui_adapter):
    client,_=flow
    payload=contract_data(); payload['items'][0]['contract_unit_price']='0'
    payload['terms'][0].update(interest_rate_1='0',brokerage_rate_1='0',storage_rate_per_kg_day='0',
        inbound_outbound_rate_per_kg='0',weighing_rate_per_box='0')
    row=call(client,'POST','/financing-contracts',201,json=payload)
    from views.financing_contract_reg import FinancingContractWindow
    window=FinancingContractWindow(); window.contracts=[row]; window.table.setRowCount(1)
    window.table.setCurrentCell(0,0); window._select_row()
    assert Decimal(window.interest_1.text())==0 and Decimal(window.brokerage_1.text())==0
    for field in [window.storage,window.inout,window.weighing]: assert Decimal(field.text())==0
    assert Decimal(window.item_table.item(0,3).text())==0
    window.close()


def test_gui_contract_days_uses_existing_dto_without_interest_period_alias(flow,ui_adapter,qt_application):
    from views.financing_contract_reg import FinancingContractWindow
    client,_=flow; window=FinancingContractWindow()
    window.contract_days.setText('30'); window.interest_days_1.setText('90')
    term=window._term_payload()
    assert term['contract_days']==30 and term['interest_period_days_1']==90
    term['effective_from']='2026-10-01'
    payload=contract_data(); payload['terms']=[term]
    row=call(client,'POST','/financing-contracts',201,json=payload)
    call(client,'POST',f"/financing-contracts/{row['contract_id']}/confirm")
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':row['contract_id'],'template_type':'IMPORT_AGENCY'})
    text=plain(doc['body'])
    assert '검역완료시점부터 30일이내' in text and '1차 이자 적용기간: 90일' in text
    assert not any('출고약정기간' in item for item in doc['validation']['required'])
    window.contracts=[row]; window.table.setRowCount(1); window.table.setCurrentCell(0,0); window._select_row()
    assert window.contract_days.text()=='30' and window.interest_days_1.text()=='90'
    window.clear_form(); assert not window.contract_days.text()
    window.close()
