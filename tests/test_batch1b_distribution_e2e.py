"""HTTP E2E over real ORM transactions; only SQL Server numbering is adapted by
our existing SQLite fixture. No production database or server is contacted.
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from test_trade_flow_integrity import db_factory, main
import models
from audit_service import AuditEvent
from database import get_db
from permissions import issue_token
from settlement_service import source_allocated

BASE = '/api/v1/companies/00001'
DAY = '2026-10-03'


def decimal(value):
    return Decimal(str(value))


@pytest.fixture
def flow(db_factory, monkeypatch):
    with db_factory() as db:
        db.add_all([
            models.Company(comp_code='00002', comp_name='격리회사', biz_no='2'),
            models.Product(product_id=2, product_code='P2', product_name='과세 가공육', tax_type='1'),
            models.Warehouse(warehouse_id=2, warehouse_code='W2', warehouse_name='제2창고'),
            models.TaxCode(tax_code='VAT10', tax_name='부가세', tax_kind='TAXABLE',
                           tax_rate=10, valid_from=date(2000, 1, 1)),
        ])
        db.commit()
        db.add(models.CompanyWarehouse(comp_code='00001', warehouse_id=2))
        db.commit()

    def dependency():
        with db_factory() as db:
            yield db

    previous = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(main, 'SessionLocal', db_factory)
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            client.headers['Authorization'] = 'Bearer ' + issue_token('tester')
            yield client, db_factory
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)


def call(client, method, path, expected=200, **kwargs):
    response = client.request(method, BASE + path, **kwargs)
    assert response.status_code == expected, response.text
    return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text


def purchase_data():
    return {'purchase_date': '2026-10-01', 'account_id': 2, 'finalize': True,
            'audit_reason': 'E2E 복수 LOT 매입', 'items': [
                {'line_no': 1, 'product_id': 1, 'warehouse_id': 1, 'box_qty': 10,
                 'weight': '100.00', 'unit_price': 1000, 'bl_no': 'BL-E2E-1', 'history_no': 'H-E2E-1'},
                {'line_no': 2, 'product_id': 1, 'warehouse_id': 2, 'box_qty': 4,
                 'weight': '40.00', 'unit_price': 1000, 'bl_no': 'BL-E2E-2'},
                {'line_no': 3, 'product_id': 2, 'warehouse_id': 1, 'box_qty': 5,
                 'weight': '50.00', 'unit_price': 2000, 'bl_no': 'BL-E2E-3'},
            ]}


def sale_data(purchase):
    return {'sale_date': '2026-10-02', 'account_id': 1,
            'audit_reason': 'E2E 복수행 출고', 'items': [
                {'line_no': 1, 'product_id': 1, 'lot_id': purchase['items'][0]['lot_id'],
                 'box_qty': 2, 'weight': '20.00', 'unit_price': 1500},
                {'line_no': 2, 'product_id': 1, 'lot_id': purchase['items'][1]['lot_id'],
                 'box_qty': 0, 'weight': '5.50', 'unit_price': 1500},
                {'line_no': 3, 'product_id': 2, 'lot_id': purchase['items'][2]['lot_id'],
                 'box_qty': 1, 'weight': '10.00', 'unit_price': 2500},
            ]}


def settlement(client, kind, amount, **extra):
    return call(client, 'POST', '/' + kind + 's', 201, json={
        kind + '_date': DAY, 'account_id': 2 if kind == 'payment' else 1,
        'amount': amount, 'memo': 'E2E 부분/최종 정산', 'audit_reason': 'E2E 정산', **extra,
    })


def outstanding(client, kind):
    account = 2 if kind == 'payable' else 1
    route = '/purchase-payable-summary' if kind == 'payable' else '/sales-receivable-summary'
    return call(client, 'GET', route, params={'account_id': account, 'transaction_date': DAY})['current_' + kind]


def ledger(client, account):
    return call(client, 'GET', '/account-ledger', params={
        'account_id': account, 'start_date': '2026-10-01', 'end_date': DAY})


def source_row(db, document, kind):
    number = document['purchase_no'] if kind == 'PURCHASE_PAYABLE' else document['sale_no']
    return db.query(models.AccountTransaction).filter_by(
        comp_code='00001', transaction_no=number, transaction_type=kind).one()


def state(factory):
    """Capture all business rows, not just counts, to expose partial failed writes."""
    classes = (models.Purchase, models.PurchaseItem, models.Lot, models.Inbound,
               models.InboundItem, models.Sale, models.SaleItem, models.Outbound,
               models.OutboundItem, models.AccountTransaction,
               models.AccountTransactionAllocation, models.TradeStatement, AuditEvent)
    with factory() as db:
        return {cls.__tablename__: sorted(
            [tuple(str(getattr(row, column.name)) for column in cls.__table__.columns)
             for row in db.query(cls).all()]) for cls in classes}


def check_inventory(client, factory, purchase, sale=None):
    expected = [(8, '80.00'), (4, '34.50'), (4, '40.00')] if sale else [(10, '100'), (4, '40'), (5, '50')]
    ids = [item['lot_id'] for item in purchase['items']]
    params = {'start_date': '2026-10-02', 'end_date': DAY, 'include_zero': True}
    lots = call(client, 'GET', '/inventory', params={**params, 'group_by': 'LOT'})
    by_id = {row['lot_id']: row for row in lots['rows']}
    assert set(by_id) == set(ids)
    with factory() as db:
        for index, lot_id in enumerate(ids):
            row = by_id[lot_id]
            assert (row['current_box_qty'], decimal(row['current_weight'])) == (expected[index][0], decimal(expected[index][1]))
            assert row['beginning_box_qty'] + row['inbound_box_qty'] - row['outbound_box_qty'] == row['current_box_qty']
            assert decimal(row['beginning_weight']) + decimal(row['inbound_weight']) - decimal(row['outbound_weight']) == decimal(row['current_weight'])
            assert main._lot_available(db, '00001', lot_id) == (row['current_box_qty'], decimal(row['current_weight']))
            movement = call(client, 'GET', f'/inventory/lots/{lot_id}/transactions', params={'end_date': DAY})
            assert sum(x['box_delta'] for x in movement['rows']) == row['current_box_qty']
            assert sum((decimal(x['weight_delta']) for x in movement['rows']), Decimal(0)) == decimal(row['current_weight'])
            assert movement['rows'][0]['source_type'] == 'PURCHASE'
            assert movement['rows'][0]['source_id'] == purchase['purchase_id']
            if sale:
                assert movement['rows'][-1]['source_type'] == 'SALE'
                assert movement['rows'][-1]['source_id'] == sale['sale_id']
            assert movement['current_box_qty'] == row['current_box_qty']
            assert decimal(movement['current_weight']) == decimal(row['current_weight'])
    for group, key in [('PRODUCT', 'product_id'), ('WAREHOUSE', 'warehouse_id')]:
        report = call(client, 'GET', '/inventory', params={**params, 'group_by': group})
        assert report['summary'] == lots['summary']
        for aggregate in report['rows']:
            members = [row for row in lots['rows'] if row[key] == aggregate[key]]
            for field in ['beginning_box_qty', 'beginning_weight', 'inbound_box_qty',
                          'inbound_weight', 'outbound_box_qty', 'outbound_weight',
                          'current_box_qty', 'current_weight', 'inventory_amount']:
                assert decimal(aggregate[field]) == sum((decimal(row[field]) for row in members), Decimal(0))
    return lots['summary']


def check_snapshot(document, sale):
    snapshot = document['snapshot']
    for field in ['total_box_qty', 'total_weight', 'total_supply_amount',
                  'total_tax_amount', 'total_discount_amount', 'total_amount']:
        assert decimal(snapshot[field]) == decimal(sale[field])
    assert len(snapshot['items']) == len(sale['items']) == 3
    for stored, item in zip(snapshot['items'], sale['items']):
        for field in ['product_id', 'lot_id', 'box_qty', 'weight', 'unit_price',
                      'supply_amount', 'tax_amount', 'total_amount']:
            assert decimal(stored[field]) == decimal(item[field])


def test_normal_distribution_purchase_to_statement_has_no_unexplained_difference(flow):
    client, factory = flow
    purchase = call(client, 'POST', '/purchases', 201, json=purchase_data())
    assert purchase['document_status'] == 'CONFIRMED'
    assert decimal(purchase['total_amount']) == 250000
    with factory() as db:
        assert db.query(models.Lot).count() == db.query(models.InboundItem).count() == 3
        assert db.query(models.Inbound).count() == 2
        for item in purchase['items']:
            linked = db.get(models.PurchaseItem, item['purchase_item_id'])
            inbound = db.get(models.InboundItem, linked.inbound_item_id)
            assert (inbound.lot_id, inbound.product_id, inbound.box_qty, inbound.weight) == (
                linked.lot_id, linked.product_id, linked.box_qty, linked.weight)
        assert source_row(db, purchase, 'PURCHASE_PAYABLE').original_amount == 250000
    check_inventory(client, factory, purchase)
    payment = settlement(client, 'payment', 70000)
    assert payment['allocated_amount'] == 70000 and payment['unallocated_amount'] == 0
    assert outstanding(client, 'payable') == 180000
    with factory() as db:
        source = source_row(db, purchase, 'PURCHASE_PAYABLE')
        assert source.original_amount - source_allocated(db, source.account_transaction_id) == 180000
    before = state(factory)
    call(client, 'PUT', f"/purchases/{purchase['purchase_id']}", 409, json=purchase_data())
    call(client, 'POST', f"/purchases/{purchase['purchase_id']}/cancel", 409, json={'reason': '지급 후 취소 시도'})
    assert state(factory) == before

    sale = call(client, 'POST', '/sales', 201, json=sale_data(purchase))
    assert sale['document_status'] == 'CONFIRMED'
    assert (sale['total_box_qty'], decimal(sale['total_weight'])) == (3, Decimal('35.50'))
    assert decimal(sale['total_amount']) == 65750
    with factory() as db:
        assert db.query(models.Outbound).count() == 2
        assert db.query(models.OutboundItem).count() == 3
        for item in sale['items']:
            linked = db.query(models.OutboundItem).filter_by(sale_item_id=item['sale_item_id']).one()
            assert (linked.lot_id, linked.box_qty, linked.weight) == (item['lot_id'], item['box_qty'], decimal(item['weight']))
        assert source_row(db, sale, 'SALES_RECEIVABLE').original_amount == decimal(sale['total_amount'])
    summary = check_inventory(client, factory, purchase, sale)
    assert (summary['current_box_qty'], decimal(summary['current_weight'])) == (16, Decimal('154.50'))
    receipt = settlement(client, 'receipt', 20000)
    assert receipt['allocated_amount'] == 20000 and outstanding(client, 'receivable') == 45750
    with factory() as db:
        source = source_row(db, sale, 'SALES_RECEIVABLE')
        assert source.original_amount - source_allocated(db, source.account_transaction_id) == 45750
    before = state(factory)
    call(client, 'PUT', f"/sales/{sale['sale_id']}", 409, json=sale_data(purchase))
    call(client, 'POST', f"/sales/{sale['sale_id']}/cancel", 409, json={'reason': '입금 후 취소 시도'})
    assert state(factory) == before
    assert ledger(client, 1)['ending_balance'] == 45750
    assert ledger(client, 2)['ending_balance'] == -180000
    for kind, document, amount in [('payment', payment, 80000), ('receipt', receipt, 25000)]:
        payload = {kind + '_date': DAY, 'account_id': 2 if kind == 'payment' else 1,
                   'amount': amount, 'audit_reason': '부분 정산 수정'}
        changed = call(client, 'PUT', f"/{kind}s/{document['account_transaction_id']}", json=payload)
        assert changed['allocated_amount'] == amount
        call(client, 'DELETE', f"/{kind}s/{document['account_transaction_id']}", params={'reason': '부분 정산 삭제'})
    assert outstanding(client, 'payable') == 250000
    assert outstanding(client, 'receivable') == 65750
    with factory() as db:
        assert db.query(models.AccountTransactionAllocation).count() == 0
    payment = settlement(client, 'payment', 70000)
    payment2 = settlement(client, 'payment', 180000)
    receipt = settlement(client, 'receipt', 20000)
    receipt2 = settlement(client, 'receipt', 45750)
    assert outstanding(client, 'payable') == outstanding(client, 'receivable') == 0
    with factory() as db:
        for document, kind in [(purchase, 'PURCHASE_PAYABLE'), (sale, 'SALES_RECEIVABLE')]:
            source = source_row(db, document, kind)
            assert decimal(source.original_amount) - source_allocated(db, source.account_transaction_id) == 0
    for account, source_type, source_id, settlements in [
        (2, 'PURCHASE', purchase['purchase_id'], [payment, payment2]),
        (1, 'SALE', sale['sale_id'], [receipt, receipt2]),
    ]:
        book = ledger(client, account)
        assert book['ending_balance'] == 0
        if account == 2:
            assert book['period_total']['purchase_amount'] == book['period_total']['payment_amount'] == 250000
        else:
            assert book['period_total']['sales_amount'] == book['period_total']['receipt_amount'] == 65750
        first = book['transactions'][0]
        assert (first['source_type'], first['source_id']) == (source_type, source_id)
        assert all((row['source_type'], row['source_id']) == (source_type, source_id) for row in first['details'])
        assert [row['source_id'] for row in book['transactions'][1:]] == [row['account_transaction_id'] for row in settlements]
        assert sum(row['net_change'] for row in book['transactions']) == 0

    path = f"/sales/{sale['sale_id']}/statements"
    before_issue = state(factory)
    document = call(client, 'POST', path)
    check_snapshot(document, sale)
    with factory() as db:
        stored = db.get(models.TradeStatement, document['statement_id']).snapshot_json
        db.get(models.Product, 1).product_name = '발행 후 변경 상품'
        db.get(models.Account, 1).account_name = '발행 후 변경 거래처'
        db.get(models.Company, '00001').comp_name = '발행 후 변경 회사'
        db.commit()
    reprinted = call(client, 'GET', path + '/' + str(document['statement_id']))
    assert reprinted['snapshot'] == document['snapshot']
    assert call(client, 'POST', path)['statement_id'] == document['statement_id']
    for method in ['GET', 'POST']:
        response = client.request(method, BASE.replace('00001', '00002') + path)
        assert response.status_code == 404
    after_issue = state(factory)
    for table, rows in before_issue.items():
        if table not in {models.TradeStatement.__tablename__, AuditEvent.__tablename__}:
            assert after_issue[table] == rows
    with factory() as db:
        assert db.get(models.TradeStatement, document['statement_id']).snapshot_json == stored
        assert db.query(models.TradeStatement).count() == 1
        for entity, entity_id, expected in [('PURCHASE', purchase['purchase_id'], ['CREATE', 'CONFIRM']),
                                            ('SALE', sale['sale_id'], ['CREATE', 'CONFIRM']),
                                            ('TRADE_STATEMENT', document['statement_id'], ['ISSUE'])]:
            events = db.query(AuditEvent).filter_by(entity_type=entity, entity_id=str(entity_id)).order_by(AuditEvent.audit_event_id).all()
            assert [event.action for event in events] == expected
            assert all(event.after_json for event in events)
        for entity in ['RECEIPT', 'PAYMENT']:
            events = db.query(AuditEvent).filter_by(entity_type=entity).order_by(AuditEvent.audit_event_id).all()
            assert [event.action for event in events] == ['CREATE', 'UPDATE', 'DELETE', 'CREATE', 'CREATE']
            assert events[1].before_json and events[1].after_json and events[1].reason == '부분 정산 수정'
            assert events[2].before_json and events[2].reason == '부분 정산 삭제'


def test_corrections_cancellations_document_versions_and_audit_restore_chain(flow):
    client, factory = flow
    purchase = call(client, 'POST', '/purchases', 201, json=purchase_data())
    changed = purchase_data(); changed['items'][0]['weight'] = '110.00'; changed['audit_reason'] = '입고 중량 정정'
    purchase = call(client, 'PUT', f"/purchases/{purchase['purchase_id']}", json=changed)
    assert decimal(purchase['total_amount']) == 260000
    with factory() as db:
        assert db.query(models.Lot).count() == db.query(models.InboundItem).count() == 3
        assert source_row(db, purchase, 'PURCHASE_PAYABLE').original_amount == 260000
    data = sale_data(purchase)
    sale = call(client, 'POST', '/sales', 201, json=data)
    path = f"/sales/{sale['sale_id']}/statements"
    first = call(client, 'POST', path)
    before = state(factory)
    call(client, 'PUT', f"/purchases/{purchase['purchase_id']}", 409, json=changed)
    call(client, 'POST', f"/purchases/{purchase['purchase_id']}/cancel", 409, json={'reason': '출고 후 취소'})
    assert state(factory) == before
    data['items'][0]['weight'] = '21.00'; data['audit_reason'] = '출고 중량 정정'
    sale = call(client, 'PUT', f"/sales/{sale['sale_id']}", json=data)
    second = call(client, 'POST', path)
    assert (first['version'], second['version']) == (1, 2)
    check_snapshot(second, sale)
    assert call(client, 'GET', path + '/' + str(first['statement_id']))['snapshot'] == first['snapshot']
    assert call(client, 'GET', path + '/' + str(first['statement_id']))['status'] == 'SUPERSEDED'
    with factory() as db:
        assert db.query(models.OutboundItem).count() == 3
        assert source_row(db, sale, 'SALES_RECEIVABLE').original_amount == 67250
        assert main._lot_available(db, '00001', purchase['items'][0]['lot_id']) == (8, Decimal('89.00'))
    call(client, 'POST', f"/sales/{sale['sale_id']}/cancel", json={'reason': '출고 취소'})
    assert outstanding(client, 'receivable') == 0
    with factory() as db:
        assert db.query(models.Outbound).count() == db.query(models.OutboundItem).count() == 0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count() == 0
        assert main._lot_available(db, '00001', purchase['items'][0]['lot_id']) == (10, Decimal('110.00'))
    versions = call(client, 'GET', path)
    assert len(versions) == 2 and all(row['status'] == 'CANCELLED' for row in versions)
    call(client, 'POST', path, 409)
    # Cancelling a SALE removes movements/receivable, but its original item/LOT
    # references remain for history. That used purchase is still protected.
    before = state(factory)
    call(client, 'POST', f"/purchases/{purchase['purchase_id']}/cancel", 409, json={'reason': '사용 이력 LOT 매입 취소'})
    assert state(factory) == before
    with factory() as db:
        assert db.query(models.TradeStatement).count() == 2
        assert db.query(models.SaleItem).count() == 3
        events = db.query(AuditEvent).filter_by(entity_type='SALE').order_by(AuditEvent.audit_event_id).all()
        assert [x.action for x in events] == ['CREATE', 'CONFIRM', 'UPDATE', 'CANCEL']
        assert events[-1].reason == '출고 취소' and events[-1].before_json and events[-1].after_json
        assert json.loads(events[-1].after_json)['document_status'] == 'CANCELLED'
        update = db.query(AuditEvent).filter_by(entity_type='PURCHASE', action='UPDATE').one()
        assert update.before_json and update.after_json and update.reason == '입고 중량 정정'


def test_unused_purchase_edit_cancel_restores_inbound_lot_payable_and_audit(flow):
    client, factory = flow
    purchase = call(client, 'POST', '/purchases', 201, json=purchase_data())
    changed = purchase_data()
    changed['items'][0]['weight'] = '110.00'
    changed['audit_reason'] = '후속 거래 없는 매입 정정'
    purchase = call(client, 'PUT', f"/purchases/{purchase['purchase_id']}", json=changed)
    assert outstanding(client, 'payable') == 260000
    with factory() as db:
        assert db.query(models.Lot).count() == db.query(models.InboundItem).count() == 3
        assert main._lot_available(db, '00001', purchase['items'][0]['lot_id']) == (10, Decimal('110.00'))
    call(client, 'POST', f"/purchases/{purchase['purchase_id']}/cancel", json={'reason': '매입 취소'})
    assert outstanding(client, 'payable') == 0
    assert call(client, 'GET', '/inventory', params={'start_date': '2026-10-01', 'end_date': DAY})['rows'] == []
    assert ledger(client, 2)['ending_balance'] == 0
    with factory() as db:
        assert db.query(models.Lot).count() == db.query(models.InboundItem).count() == db.query(models.Inbound).count() == 0
        assert db.query(models.AccountTransaction).count() == 0
        assert db.get(models.Purchase, purchase['purchase_id']).document_status == 'CANCELLED'
        events = db.query(AuditEvent).filter_by(entity_type='PURCHASE').order_by(AuditEvent.audit_event_id).all()
        assert [x.action for x in events] == ['CREATE', 'CONFIRM', 'UPDATE', 'CANCEL']
        assert events[-1].reason == '매입 취소' and events[-1].before_json and events[-1].after_json
        assert json.loads(events[-1].after_json)['document_status'] == 'CANCELLED'


def test_same_lot_cumulative_negative_inventory_requires_reason_and_cancel_restores(flow):
    client, factory = flow
    purchase = call(client, 'POST', '/purchases', 201, json=purchase_data())
    first = sale_data(purchase)['items'][0]
    data = {'sale_date': '2026-10-02', 'account_id': 1, 'items': [
        {**first, 'box_qty': 6, 'weight': '60'},
        {**first, 'line_no': 2, 'box_qty': 5, 'weight': '45'},
    ]}
    before = state(factory)
    call(client, 'POST', '/sales', 409, json=data)
    assert state(factory) == before
    data['inventory_exception_reason'] = '계근차이 확인 후 선출고'
    sale = call(client, 'POST', '/sales', 201, json=data)
    assert sale['inventory_exception_yn'] and sale['inventory_exception_reason'] == data['inventory_exception_reason']
    with factory() as db:
        assert main._lot_available(db, '00001', first['lot_id']) == (-1, Decimal('-5.00'))
        event = db.query(AuditEvent).filter_by(entity_type='SALE', action='CONFIRM').one()
        assert data['inventory_exception_reason'] in event.after_json
    call(client, 'POST', f"/sales/{sale['sale_id']}/cancel", json={'reason': '예외출고 취소'})
    check_inventory(client, factory, purchase)


@pytest.mark.parametrize('stage', ['purchase', 'sale', 'statement'])
def test_failure_after_materialization_leaves_no_partial_business_rows(flow, monkeypatch, stage):
    client, factory = flow
    import trade_statement_routes
    if stage != 'purchase':
        purchase = call(client, 'POST', '/purchases', 201, json=purchase_data())
    if stage == 'statement':
        sale = call(client, 'POST', '/sales', 201, json=sale_data(purchase))
    before = state(factory)
    module = trade_statement_routes if stage == 'statement' else main
    original = module.record_audit_event
    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        if stage == 'statement' or kwargs['action'] == 'CONFIRM':
            raise RuntimeError('Injected post-write failure')
    monkeypatch.setattr(module, 'record_audit_event', fail_after_write)
    path, data = ('/purchases', purchase_data()) if stage == 'purchase' else (
        ('/sales', sale_data(purchase)) if stage == 'sale' else (f"/sales/{sale['sale_id']}/statements", None))
    call(client, 'POST', path, 500, json=data)
    assert state(factory) == before
