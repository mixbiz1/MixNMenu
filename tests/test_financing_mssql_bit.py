"""Compile the actual financing queries as SQL Server SQL; do not execute SQL."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Query, Session
from test_financing_contracts import financing


def sql_server_sql(query):
    sql = str(query.statement.compile(dialect=mssql.dialect(), compile_kwargs={'literal_binds': True}))
    assert not re.search(r'\bIS\s+(?:NOT\s+)?[01]\b', sql, re.IGNORECASE), sql
    return sql


@pytest.mark.parametrize('require_sale', [False, True])
def test_actual_account_and_sale_relation_bit_filters_compile_for_mssql(monkeypatch, require_sale):
    statements = []
    account = SimpleNamespace(account_id=1)
    def first(query):
        statements.append(sql_server_sql(query))
        return account
    monkeypatch.setattr(Query, 'first', first)
    with Session() as db:
        assert financing._account(db, '00001', 1, require_sale=require_sale) is account
    sql = statements[0]
    assert 'tb_company_account.use_yn = 1' in sql
    assert 'tb_company_account.trade_stop_yn = 0' in sql
    assert 'tb_account.use_yn = 1' in sql
    assert len(statements) == (2 if require_sale else 1)
    if require_sale:
        assert 'tb_company_account.sales_yn = 1' in statements[1]
        assert 'tb_company_account.trade_stop_yn = 0' in statements[1]


def test_actual_lot_assignment_bit_filter_compiles_for_mssql(monkeypatch):
    statements = []
    class QueryCaptured(Exception): pass
    def first(query):
        statements.append(sql_server_sql(query))
        raise QueryCaptured
    monkeypatch.setattr(Query, 'first', first)
    with Session() as db, pytest.raises(QueryCaptured):
        financing._add_lot(db, SimpleNamespace(status='DRAFT', comp_code='00001'),
            financing.ContractLotInput(lot_id=1,contract_box_qty=1,contract_weight=10), 'tester')
    assert len(statements) == 1 and 'tb_lot.use_yn = 1' in statements[0]


def test_financing_update_permission_bit_filter_compiles_for_mssql(monkeypatch):
    statements=[]
    def first(query):
        statements.append(sql_server_sql(query)); return SimpleNamespace()
    monkeypatch.setattr(Query, 'first', first)
    request=SimpleNamespace(state=SimpleNamespace(user_id='tester',is_admin=False))
    with Session() as db: assert financing._can_approve_cost_return(db,request)
    assert 'tb_user_menu_permission.can_update = 1' in statements[0]


def test_batch2a_sources_do_not_use_boolean_is_predicates():
    # Reject the cross-dialect trap while leaving valid .is_(None) unchanged.
    root=Path(__file__).resolve().parents[1]
    for name in ['financing_contract_routes.py','financing_intake_routes.py','main.py','permissions.py']:
        tree=ast.parse((root/name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'is_','is_not','isnot'}:
                assert not any(isinstance(arg,ast.Constant) and isinstance(arg.value,bool) for arg in node.args), (name,node.lineno)
