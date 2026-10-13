"""Effective-date boundaries, exact Decimal totals and frozen past quotes."""
import copy
import json
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from test_financing_releases import ready
from test_batch1b_distribution_e2e import flow, call
from test_trade_flow_integrity import db_factory
from financing_release_routes import period_interest, term_segments
import models


def terms():
    return [{'term_id':1,'version':1,'effective_from':'2026-01-01','interest_rate_1':'7',
             'interest_period_days_1':30,'interest_rate_2':'8','interest_period_days_2':60},
            {'term_id':2,'version':2,'effective_from':'2026-01-31','interest_rate_1':'9',
             'interest_period_days_1':30,'interest_rate_2':'10','interest_period_days_2':60}]


def test_change_date_once_original_period_positions_no_rate_reset():
    amount, detail=period_interest(Decimal(100000),date(2026,1,1),date(2026,2,1),terms(),365)
    assert amount==Decimal(100000)*(Decimal(7)*30+Decimal(10)*2)/100/365
    assert [(x['days_1'],x['days_2']) for x in detail['segments']]==[(30,0),(0,2)]
    assert detail['segments'][1]['start']==date(2026,1,31)


def test_period_missing_start_or_over_horizon_is_blocked():
    with pytest.raises(HTTPException):term_segments(terms(),date(2025,12,1),date(2026,1,1))
    with pytest.raises(HTTPException):period_interest(Decimal(1),date(2026,1,1),date(2026,5,1),terms(),365)


def add_version(factory,payload,recovery=None):
    with factory() as db:
        contract=db.get(models.FinancingContract,payload['contract_id']);old=contract.terms[0]
        values={column.name:getattr(old,column.name) for column in old.__table__.columns
                if column.name not in {'term_id','version','effective_from','created_at'}}
        conditions=json.loads(values['conditions_json']);conditions['expense_conditions'][0]['unit_rate']='1.8'
        values.update(conditions_json=json.dumps(conditions),interest_rate_1=Decimal('10'),
                      version=2,effective_from=date(2026,10,4),change_reason='약정 요율 변경')
        if recovery:values['recovery_template']=recovery
        db.add(models.FinancingContractTerm(**values));db.commit()


def test_partial_quote_segment_costs_and_previous_snapshot_stays_frozen(flow):
    client,factory=flow;payload,_=ready(flow)
    before=call(client,'POST','/financing-releases',201,json=payload)
    frozen=copy.deepcopy(before['snapshot'])
    add_version(factory,payload)
    payload['request_key']='new-terms'
    after=call(client,'POST','/financing-releases',201,json=payload)
    line=after['snapshot']['lines'][0];principal=Decimal(line['components']['COST'])
    assert Decimal(line['components']['INTEREST'])==principal*(Decimal('7.5')+Decimal(10)*2)/100/365
    assert Decimal(line['components']['STORAGE'])==Decimal('45')
    assert len(after['snapshot']['term_segments'])==2
    assert call(client,'GET',f"/financing-releases/{before['release_id']}")['snapshot']==frozen
    call(client,'POST',f"/financing-releases/{after['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{after['release_id']}/payment-check",json={'reference':'은행 TEST','amount':int(after['total_amount'])})
    shipped=call(client,'POST',f"/financing-releases/{after['release_id']}/ship")
    assert shipped['sale_id']
    assert shipped['snapshot']==after['snapshot']


@pytest.mark.parametrize('recovery',['ALL_IN','COST_ONLY'])
def test_changed_brokerage_or_recovery_cannot_silently_recover_again(flow,recovery):
    client,factory=flow;payload,_=ready(flow,'ALL_IN' if recovery=='ALL_IN' else 'EXCLUDE_BROKERAGE')
    add_version(factory,payload,recovery)
    call(client,'POST','/financing-releases',409,json=payload)
