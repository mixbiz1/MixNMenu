"""Batch 2A: contract snapshots -> import intake -> actual cost/LOT allocation.
No sale, receipt, deposit or inventory quantity is materialized here.
"""
import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from audit_service import record_audit_event
import models
import financing_contract_routes as contracts
from contract_document_templates import FORMS, REVISION, render, is_html, validate_html

router = APIRouter(prefix='/api/v1/companies/{comp_code}')
TITLES = {code: item[0] for code, item in FORMS.items()}

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

class DocumentCreate(Input):
    contract_id: int
    template_type: str

class BodyInput(Input):
    body: str = Field(min_length=1, max_length=100000)
    reason: str | None = Field(default=None, max_length=1000)

class Reason(Input):
    reason: str = Field(min_length=2, max_length=1000)

class CaseItemInput(Input):
    contract_item_id: int | None = None
    product_id: int
    lot_id: int | None = None
    box_qty: int = Field(default=0, ge=0)
    weight: Decimal = Field(default=Decimal(0), ge=0, decimal_places=2)
    memo: str | None = Field(default=None, max_length=1000)

class CaseCreate(Input):
    contract_id: int | None = None
    supplier_account_id: int | None = None
    bl_no: str | None = Field(default=None, max_length=80)
    reference: str | None = Field(default=None, max_length=100)
    currency: str = Field(default='USD', pattern=r'^[A-Z]{3}$')
    customs_date: date | None = None
    warehouse_receipt_date: date | None = None
    memo: str | None = Field(default=None, max_length=1000)
    items: list[CaseItemInput] | None = None

class CaseUpdate(CaseCreate):
    reason: str | None = Field(default=None, max_length=1000)

class RowInput(Input):
    cost_name: str = Field(min_length=1, max_length=100)
    cost_kind: str = 'EVENT'
    occurred_on: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    rate: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    basis: str | None = Field(default=None, max_length=50)
    basis_quantity: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    amount: Decimal | None = Field(default=None, decimal_places=4)
    currency: str = Field(default='KRW', pattern=r'^[A-Z]{3}$')
    exchange_rate: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    tax_kind: str = 'EXEMPT'
    tax_amount_krw: Decimal = Field(default=Decimal(0), ge=0, decimal_places=0)
    capitalize_tax: bool = False
    payer: str = 'MXMN'
    product_id: int | None = None
    lot_id: int | None = None
    memo: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)

class CostCreate(Input):
    import_case_id: int
    basic_rows: bool = True

class DirectAllocation(Input):
    case_item_id: int
    amount: Decimal = Field(ge=0, decimal_places=0)

class ConfirmCost(Input):
    allocation_method: str = 'WEIGHT'
    allocations: list[DirectAllocation] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=1000)


def fail(detail, status=409):
    raise HTTPException(status, detail)


def columns(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@contextmanager
def atomic(db):
    try:
        yield
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, '중복 또는 후속 참조가 있는 자료입니다.') from exc
    except Exception:
        db.rollback()
        raise


def locked(db, model, company, key, value):
    row = db.query(model).with_hint(model, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql').with_for_update().filter(
        model.comp_code == company, getattr(model, key) == value).first()
    if row is None: fail('현재 회사의 자료를 찾을 수 없습니다.', 404)
    return row


def audit(db, request, row, action, before=None, reason=None, entity=None):
    row.updated_by = request.state.user_id
    row.updated_at = datetime.now(timezone.utc)
    record_audit_event(db, comp_code=row.comp_code, user_id=request.state.user_id,
        menu_code={'ContractDocument': 'FINANCING_DOCUMENT', 'ImportCase': 'IMPORT_INTAKE'}.get(type(row).__name__, 'IMPORT_COST'),
        action=action, entity_type=entity or type(row).__name__.upper(),
        entity_id=getattr(row, 'document_id', getattr(row, 'import_case_id', None)) if isinstance(row, (models.ContractDocument, models.ImportCase)) else row.settlement_id,
        source=f'{request.method} {request.url.path}', before=before, after=view(row), reason=reason,
        related_entity_type='FINANCING_CONTRACT' if getattr(row, 'contract_id', None) else 'IMPORT_CASE',
        related_entity_id=getattr(row, 'contract_id', None) or getattr(row, 'import_case_id', None))


def view(row):
    data = columns(row)
    for field in ['snapshot_json', 'source_snapshot_json']:
        if field in data: data[field.removesuffix('_json')] = json.loads(data.pop(field)) if getattr(row, field) else None
    if isinstance(row, models.ImportCase):
        data['contract_no'] = data['source_snapshot'].get('contract', {}).get('contract_no')
        data['supplier_name'] = row.supplier.account_name if row.supplier else None
        data['items'] = [{**columns(x), 'product_name': x.product.product_name, 'lot_code': x.lot.lot_code if x.lot else None} for x in row.items]
    if isinstance(row, models.ImportCostSettlement):
        data['rows'] = [columns(x) for x in row.rows]
        data['allocations'] = [columns(x) for x in row.allocations]
    return data


def party(row, name):
    return {'name': getattr(row, name), **{k: getattr(row, k, None) for k in ['biz_no','address','address_detail','ceo_name','uptae','upjong','bank1']}}


def contract_source(db, contract):
    metadata = {}
    for item in contract.items:
        lots = [link.lot for link in contract.lots if link.status == 'ACTIVE' and link.contract_item_id == item.contract_item_id and link.lot]
        distinct = lambda getter: ' / '.join(dict.fromkeys(str(value) for lot in lots if (value := getter(lot))))
        metadata[str(item.contract_item_id)] = {
            'origin': distinct(lambda lot: lot.origin) or item.product.origin,
            'bl_no': distinct(lambda lot: lot.bl_no), 'container_no': distinct(lambda lot: lot.container_no),
            'warehouse_name': distinct(lambda lot: lot.warehouse.warehouse_name if lot.warehouse else None),
        }
    return {'contract': contracts._snapshot(contract), 'document_goods': metadata,
            'company': party(db.get(models.Company, contract.comp_code), 'comp_name'),
            'partner': party(contract.contractor, 'account_name')}


@router.get('/contract-documents')
def documents(comp_code: str, contract_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ContractDocument).filter_by(comp_code=comp_code)
    if contract_id is not None: query = query.filter_by(contract_id=contract_id)
    return [view(x) for x in query.order_by(models.ContractDocument.document_id.desc()).all()]


@router.post('/contract-documents', status_code=201)
def create_document(comp_code: str, data: DocumentCreate, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        contract = locked(db, models.FinancingContract, comp_code, 'contract_id', data.contract_id)
        if contract.status not in {'CONFIRMED','ACTIVE'}: fail('확정 계약에서 계약서를 작성합니다.')
        if data.template_type not in FORMS or FORMS[data.template_type][1] != contract.contract_type: fail('계약유형과 Template Type이 일치해야 합니다.', 400)
        if db.query(models.ContractDocument).filter_by(contract_id=contract.contract_id, template_type=data.template_type, status='DRAFT').first(): fail('기존 초안을 수정하거나 취소한 뒤 새 version을 만드세요.')
        version = (db.query(func.max(models.ContractDocument.version)).filter_by(contract_id=contract.contract_id).scalar() or 0) + 1
        source = contract_source(db, contract)
        source.update({'body_format': 'HTML', 'template_revision': REVISION})
        row = models.ContractDocument(comp_code=comp_code, contract_id=contract.contract_id, template_type=data.template_type,
            version=version, status='DRAFT', body=render(source, data.template_type), snapshot_json=dumps(source),
            created_by=request.state.user_id, updated_by=request.state.user_id)
        db.add(row); db.flush(); audit(db, request, row, 'CREATE')
        result = view(row)
    return result


@router.get('/contract-documents/{document_id}')
def document(comp_code: str, document_id: int, db: Session = Depends(get_db)):
    return view(locked(db, models.ContractDocument, comp_code, 'document_id', document_id))


@router.post('/contract-documents/{document_id}/regenerate')
def regenerate_document(comp_code: str, document_id: int, data: Reason, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ContractDocument, comp_code, 'document_id', document_id)
        if row.status != 'DRAFT': fail('초안만 표준양식으로 다시 작성할 수 있습니다.')
        before = view(row)
        source = json.loads(row.snapshot_json)
        source.update({'body_format':'HTML', 'template_revision':REVISION})
        row.body = render(source, row.template_type); row.snapshot_json = dumps(source)
        audit(db, request, row, 'UPDATE', before, data.reason); result = view(row)
    return result


@router.put('/contract-documents/{document_id}')
def edit_document(comp_code: str, document_id: int, data: BodyInput, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ContractDocument, comp_code, 'document_id', document_id)
        if row.status != 'DRAFT': fail('확정된 계약서는 수정할 수 없습니다. 새 version을 만드세요.')
        before = view(row)
        source = json.loads(row.snapshot_json)
        if is_html(data.body):
            try: validate_html(data.body)
            except ValueError as exc: fail(str(exc), 400)
            source['body_format'] = 'HTML'
        else:
            source['body_format'] = 'PLAIN'
        row.snapshot_json = dumps(source)
        row.body = data.body; row.updated_by = request.state.user_id; row.updated_at = datetime.now(timezone.utc)
        audit(db, request, row, 'UPDATE', before, data.reason); result = view(row)
    return result


@router.post('/contract-documents/{document_id}/confirm')
def confirm_document(comp_code: str, document_id: int, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ContractDocument, comp_code, 'document_id', document_id)
        contract = locked(db, models.FinancingContract, comp_code, 'contract_id', row.contract_id)
        if contract.status not in {'CONFIRMED','ACTIVE'}: fail('현재 계약 상태에서 확정할 수 없습니다.')
        if row.status == 'CONFIRMED': return view(row)
        if row.status != 'DRAFT': fail('초안만 확정할 수 있습니다.')
        before = view(row)
        for old in db.query(models.ContractDocument).filter_by(contract_id=row.contract_id, template_type=row.template_type, status='CONFIRMED').all():
            old_before = view(old); old.status = 'SUPERSEDED'; audit(db, request, old, 'SUPERSEDE', old_before)
        source = json.loads(row.snapshot_json)
        source.update({'body': row.body, 'template_type': row.template_type, 'version': row.version, 'sample_template': not bool(source.get('template_revision'))})
        row.snapshot_json = dumps(source); row.status = 'CONFIRMED'; row.confirmed_at = datetime.now(timezone.utc)
        audit(db, request, row, 'CONFIRM', before); result = view(row)
    return result


@router.post('/contract-documents/{document_id}/cancel')
def cancel_document(comp_code: str, document_id: int, data: Reason, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ContractDocument, comp_code, 'document_id', document_id)
        if row.status not in {'DRAFT','CONFIRMED'}: fail('현재 계약서 상태에서 취소할 수 없습니다.')
        before = view(row); row.status = 'CANCELLED'; audit(db, request, row, 'CANCEL', before, data.reason); result = view(row)
    return result


def replace_case_items(db, case, entries):
    contract = contracts._contract(db, case.comp_code, case.contract_id) if case.contract_id else None
    lot_ids = [x.lot_id for x in entries if x.lot_id]
    if len(lot_ids) != len(set(lot_ids)): fail('한 수입건에서 동일 LOT를 중복 연결할 수 없습니다.', 400)
    case.items.clear(); db.flush()
    for number, data in enumerate(entries, 1):
        product = db.get(models.Product, data.product_id)
        if not product or not product.use_yn: fail('사용 가능한 상품이 아닙니다.', 400)
        if contract:
            item = next((x for x in contract.items if x.contract_item_id == data.contract_item_id), None)
            if item is None or item.product_id != data.product_id: fail('계약상품과 수입상품이 다릅니다.', 400)
        elif data.contract_item_id is not None: fail('일반 수입건에는 계약상품을 연결할 수 없습니다.', 400)
        if data.lot_id:
            lot = locked(db, models.Lot, case.comp_code, 'lot_id', data.lot_id)
            if lot.product_id != data.product_id: fail('LOT 상품이 다릅니다.', 400)
            if lot.bl_no and lot.bl_no != case.bl_no: fail('LOT의 BL과 수입건 BL이 다릅니다.', 400)
        case.items.append(models.ImportCaseItem(line_no=number, **data.model_dump()))
    db.flush()


@router.get('/import-cases')
def cases(comp_code: str, search: str = '', db: Session = Depends(get_db)):
    query = db.query(models.ImportCase).filter_by(comp_code=comp_code)
    if search: query = query.filter((models.ImportCase.import_case_no.contains(search)) | (models.ImportCase.bl_no.contains(search)))
    return [view(x) for x in query.order_by(models.ImportCase.import_case_id.desc()).all()]


@router.post('/import-cases', status_code=201)
def create_case(comp_code: str, data: CaseCreate, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        contracts._company(db, comp_code)
        source = {}; entries = data.items
        if data.contract_id:
            contract = locked(db, models.FinancingContract, comp_code, 'contract_id', data.contract_id)
            if contract.status not in {'CONFIRMED','ACTIVE'}: fail('확정 계약에서 수입건을 만드세요.')
            doc = db.query(models.ContractDocument).filter_by(contract_id=data.contract_id, template_type=contract.contract_type, status='CONFIRMED').order_by(models.ContractDocument.version.desc()).first()
            source = json.loads(doc.snapshot_json) if doc else contract_source(db, contract)
            if entries is None:
                entries = [CaseItemInput(contract_item_id=x.contract_item_id, product_id=x.product_id,
                    box_qty=x.contract_box_qty, weight=x.contract_weight) for x in contract.items]
        if not entries: fail('수입상품을 등록하세요.', 400)
        if data.supplier_account_id: contracts._account(db, comp_code, data.supplier_account_id)
        values = data.model_dump(exclude={'items'})
        row = models.ImportCase(comp_code=comp_code, import_case_no=f'IC-{date.today():%Y%m%d}-{uuid4().hex[:12]}',
            status='DRAFT', source_snapshot_json=dumps(source), created_by=request.state.user_id, updated_by=request.state.user_id, **values)
        db.add(row); db.flush(); replace_case_items(db, row, entries); audit(db, request, row, 'CREATE'); result = view(row)
    return result


@router.get('/import-cases/{import_case_id}')
def case_detail(comp_code: str, import_case_id: int, db: Session = Depends(get_db)):
    return view(locked(db, models.ImportCase, comp_code, 'import_case_id', import_case_id))


@router.put('/import-cases/{import_case_id}')
def edit_case(comp_code: str, import_case_id: int, data: CaseUpdate, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ImportCase, comp_code, 'import_case_id', import_case_id)
        if row.status not in {'DRAFT','IN_PROGRESS'} or db.query(models.ImportCostSettlement).filter_by(import_case_id=import_case_id).first(): fail('원가정산을 시작한 수입건은 기본정보를 변경할 수 없습니다.')
        if row.contract_id != data.contract_id: fail('원계약 연결은 변경할 수 없습니다.')
        if data.supplier_account_id: contracts._account(db, comp_code, data.supplier_account_id)
        before = view(row)
        for k, v in data.model_dump(exclude={'items','reason','contract_id'}).items(): setattr(row, k, v)
        if data.items is not None: replace_case_items(db, row, data.items)
        row.updated_by = request.state.user_id; row.updated_at = datetime.now(timezone.utc)
        db.flush(); db.expire(row, ['supplier'])
        audit(db, request, row, 'UPDATE', before, data.reason); result = view(row)
    return result


@router.post('/import-cases/{import_case_id}/start')
def start_case(comp_code: str, import_case_id: int, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ImportCase, comp_code, 'import_case_id', import_case_id)
        if row.status != 'DRAFT': fail('초안 수입건만 접수 진행할 수 있습니다.')
        if not row.bl_no: fail('BL을 입력하세요.', 400)
        before = view(row); row.status = 'IN_PROGRESS'; audit(db, request, row, 'START', before); result = view(row)
    return result


@router.post('/import-cases/{import_case_id}/close')
def close_case(comp_code: str, import_case_id: int, data: Reason, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ImportCase, comp_code, 'import_case_id', import_case_id)
        if row.status != 'COST_CONFIRMED': fail('원가확정 후 수입접수를 마감할 수 있습니다.')
        before = view(row); row.status = 'CLOSED'; audit(db, request, row, 'CLOSE', before, data.reason); result = view(row)
    return result


def editable_cost(db, company, key):
    row = locked(db, models.ImportCostSettlement, company, 'settlement_id', key)
    if row.status != 'DRAFT': fail('초안 원가정산만 수정할 수 있습니다.')
    return row


def row_values(data, case, final=False):
    if data.cost_kind not in {'EVENT','PERIOD'}: fail('EVENT/PERIOD 구분이 올바르지 않습니다.', 400)
    if data.tax_kind not in {'EXEMPT','TAXABLE','ZERO','OUT_OF_SCOPE'}: fail('세무속성이 올바르지 않습니다.', 400)
    if data.payer not in {'MXMN','CONTRACTOR','SUPPLIER','SHIPPER'}: fail('부담주체가 올바르지 않습니다.', 400)
    if data.product_id and data.product_id not in {x.product_id for x in case.items}: fail('배부 상품이 수입건에 없습니다.', 400)
    if data.lot_id and not any(x.lot_id == data.lot_id and (not data.product_id or x.product_id == data.product_id) for x in case.items): fail('배부 LOT가 수입상품과 일치하지 않습니다.', 400)
    if data.period_start and data.period_end and data.period_end < data.period_start: fail('기간 종료일이 시작일보다 빠릅니다.', 400)
    if final:
        if data.amount is None: fail('실제 금액이 없는 기본항목을 입력하거나 삭제하세요.')
        if data.cost_kind == 'EVENT' and data.occurred_on is None: fail('EVENT 비용의 실제 발생일을 입력하세요.')
        if data.cost_kind == 'PERIOD' and (not data.period_start or not data.period_end or data.rate is None or not data.basis or data.basis_quantity is None): fail('PERIOD 비용의 기간/Rate/Basis/수량/실제 계산결과를 입력하세요.')
    krw = None
    if data.amount is not None:
        if data.currency != 'KRW' and data.exchange_rate is None: fail('외화 비용의 실제 환율을 입력하세요.', 400)
        if data.currency == 'KRW' and data.exchange_rate not in {None, Decimal(1)}: fail('원화 환율은 1입니다.', 400)
        krw = (data.amount * (data.exchange_rate or Decimal(1))).quantize(Decimal(1), rounding=ROUND_CEILING)
        if data.capitalize_tax: krw += data.tax_amount_krw
    return {**data.model_dump(exclude={'reason'}), 'krw_amount': krw}


@router.get('/import-costs')
def costs(comp_code: str, import_case_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ImportCostSettlement).filter_by(comp_code=comp_code)
    if import_case_id is not None: query = query.filter_by(import_case_id=import_case_id)
    return [view(x) for x in query.order_by(models.ImportCostSettlement.settlement_id.desc()).all()]


@router.post('/import-costs', status_code=201)
def create_cost(comp_code: str, data: CostCreate, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        case = locked(db, models.ImportCase, comp_code, 'import_case_id', data.import_case_id)
        if case.status not in {'IN_PROGRESS','COSTING'}: fail('접수 진행 중인 수입건에서 원가정산을 시작하세요.')
        if db.query(models.ImportCostSettlement).filter(models.ImportCostSettlement.import_case_id == case.import_case_id,
                models.ImportCostSettlement.status.in_(['DRAFT','CONFIRMED'])).first(): fail('이미 유효한 원가정산이 있습니다.')
        version = (db.query(func.max(models.ImportCostSettlement.version)).filter_by(import_case_id=case.import_case_id).scalar() or 0) + 1
        row = models.ImportCostSettlement(comp_code=comp_code, import_case_id=case.import_case_id,
            version=version, status='DRAFT', created_by=request.state.user_id, updated_by=request.state.user_id)
        db.add(row); db.flush()
        if data.basic_rows:
            for number, name in enumerate(['상품대금','관세','통관비','운송비','입고비'], 1):
                row.rows.append(models.ImportCostRow(line_no=number, cost_name=name, cost_kind='EVENT', currency='KRW',
                    origin='AUTO', reference_json=dumps({'reference_only': True, 'contract_source': json.loads(case.source_snapshot_json)})))
        before = view(case); case.status = 'COSTING'; audit(db, request, case, 'COSTING', before)
        db.flush(); audit(db, request, row, 'CREATE'); result = view(row)
    return result


@router.get('/import-costs/{settlement_id}')
def cost_detail(comp_code: str, settlement_id: int, db: Session = Depends(get_db)):
    return view(locked(db, models.ImportCostSettlement, comp_code, 'settlement_id', settlement_id))


@router.post('/import-costs/{settlement_id}/rows', status_code=201)
def add_cost_row(comp_code: str, settlement_id: int, data: RowInput, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = editable_cost(db, comp_code, settlement_id)
        case = locked(db, models.ImportCase, comp_code, 'import_case_id', row.import_case_id)
        before = view(row); values = row_values(data, case)
        number = max((x.line_no for x in row.rows), default=0) + 1
        row.rows.append(models.ImportCostRow(line_no=number, origin='MANUAL', **values)); db.flush()
        row.total_cost = sum((x.krw_amount or 0 for x in row.rows), Decimal(0))
        audit(db, request, row, 'ADD_ROW', before, data.reason); result = view(row)
    return result


@router.put('/import-costs/{settlement_id}/rows/{cost_row_id}')
def edit_cost_row(comp_code: str, settlement_id: int, cost_row_id: int, data: RowInput, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = editable_cost(db, comp_code, settlement_id)
        case = locked(db, models.ImportCase, comp_code, 'import_case_id', row.import_case_id)
        line = next((x for x in row.rows if x.cost_row_id == cost_row_id), None)
        if not line: fail('원가행이 없습니다.', 404)
        before = view(row)
        for k, v in row_values(data, case).items(): setattr(line, k, v)
        row.total_cost = sum((x.krw_amount or 0 for x in row.rows), Decimal(0))
        row.updated_by = request.state.user_id; row.updated_at = datetime.now(timezone.utc)
        audit(db, request, row, 'UPDATE_ROW', before, data.reason); result = view(row)
    return result


@router.delete('/import-costs/{settlement_id}/rows/{cost_row_id}')
def delete_cost_row(comp_code: str, settlement_id: int, cost_row_id: int, request: Request, reason: str = '', db: Session = Depends(get_db)):
    with atomic(db):
        row = editable_cost(db, comp_code, settlement_id)
        line = next((x for x in row.rows if x.cost_row_id == cost_row_id), None)
        if not line: fail('원가행이 없습니다.', 404)
        before = view(row); row.rows.remove(line)
        row.total_cost = sum((x.krw_amount or 0 for x in row.rows), Decimal(0))
        audit(db, request, row, 'DELETE_ROW', before, reason); result = view(row)
    return result


def target_lots(db, case, current_id=None):
    targets = []
    if not case.items or any(x.lot_id is None for x in case.items): fail('모든 수입상품에 실제 ERP LOT를 연결하세요.')
    for item in sorted(case.items, key=lambda x: x.line_no):
        lot = locked(db, models.Lot, case.comp_code, 'lot_id', item.lot_id)
        if lot.product_id != item.product_id or not lot.use_yn or lot.status != 'OPEN': fail('현재 수입상품과 LOT 상태가 일치하지 않습니다.')
        if lot.bl_no and lot.bl_no != case.bl_no: fail('수입건과 LOT의 BL이 다릅니다.')
        # Keep even cancelled SALE history protected; never rewrite a sold LOT.
        if db.query(models.OutboundItem).filter_by(lot_id=lot.lot_id).first() or db.query(models.SaleItem).filter_by(lot_id=lot.lot_id).first(): fail('출고 또는 SALE 이력이 있는 LOT의 원가를 변경할 수 없습니다.')
        other = db.query(models.ImportCostAllocation).join(models.ImportCostSettlement).filter(
            models.ImportCostAllocation.lot_id == lot.lot_id, models.ImportCostSettlement.status == 'CONFIRMED')
        if current_id: other = other.filter(models.ImportCostSettlement.settlement_id != current_id)
        if other.first(): fail('다른 확정 원가정산에 배부된 LOT입니다.')
        weight = db.query(func.coalesce(func.sum(models.InboundItem.weight), 0)).join(models.Inbound).filter(
            models.Inbound.comp_code == case.comp_code, models.InboundItem.lot_id == lot.lot_id).scalar()
        if not weight or Decimal(weight) <= 0: fail('실제 입고 중량이 있는 LOT만 원가를 배부할 수 있습니다.')
        targets.append((item, lot, Decimal(weight)))
    return targets


def distribute(amount, targets):
    weight = sum((x[2] for x in targets), Decimal(0)); remaining = abs(amount); result = {}
    for index, (item, lot, kg) in enumerate(targets):
        share = remaining if index == len(targets)-1 else (abs(amount)*kg/weight).quantize(Decimal(1), rounding=ROUND_FLOOR)
        result[item.case_item_id] = -share if amount < 0 else share
        remaining -= share
    return result


@router.post('/import-costs/{settlement_id}/confirm')
def confirm_cost(comp_code: str, settlement_id: int, data: ConfirmCost, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ImportCostSettlement, comp_code, 'settlement_id', settlement_id)
        case = locked(db, models.ImportCase, comp_code, 'import_case_id', row.import_case_id)
        if row.status == 'CONFIRMED': return view(row)
        if row.status != 'DRAFT' or case.status != 'COSTING': fail('초안 원가정산만 확정할 수 있습니다.')
        if not case.customs_date or not case.warehouse_receipt_date or not case.bl_no: fail('BL/통관일/입고일을 입력하세요.')
        targets = target_lots(db, case)
        before = view(row)
        if not row.rows: fail('실제 원가행을 입력하세요.')
        for line in row.rows:
            data_line = RowInput(**{k: getattr(line, k) for k in RowInput.model_fields if k != 'reason'})
            line.krw_amount = row_values(data_line, case, final=True)['krw_amount']
        total = sum((line.krw_amount for line in row.rows), Decimal(0))
        if total <= 0: fail('확정 총원가는 0원보다 커야 합니다.')
        if data.allocation_method == 'WEIGHT':
            if data.allocations: fail('중량배부에는 직접 배부액을 입력하지 않습니다.', 400)
            shares = {item.case_item_id: Decimal(0) for item, _, _ in targets}
            for line in row.rows:
                members = [t for t in targets if (not line.product_id or t[0].product_id == line.product_id) and (not line.lot_id or t[1].lot_id == line.lot_id)]
                if not members: fail('원가행의 배부 대상이 없습니다.')
                for key, value in distribute(line.krw_amount, members).items(): shares[key] += value
        elif data.allocation_method == 'DIRECT':
            if any(x.product_id or x.lot_id for x in row.rows): fail('상품/LOT 지정 비용은 중량배부를 사용하세요. 직접배부는 전체 원가에만 적용합니다.')
            shares = {x.case_item_id: x.amount for x in data.allocations}
            if len(shares) != len(data.allocations) or set(shares) != {x[0].case_item_id for x in targets} or sum(shares.values()) != total: fail('직접배부 LOT/금액 합계가 확정 총원가와 다릅니다.')
        else: fail('WEIGHT 또는 DIRECT 배부를 선택하세요.', 400)
        if any(value < 0 for value in shares.values()): fail('차감 후 LOT별 확정 원가는 음수가 될 수 없습니다.')
        allocation_snapshot = []
        for item, lot, kg in targets:
            unit = (shares[item.case_item_id]/kg).quantize(Decimal(1), rounding=ROUND_CEILING)
            allocation = models.ImportCostAllocation(settlement_id=row.settlement_id, case_item_id=item.case_item_id,
                lot_id=lot.lot_id, actual_weight=kg, allocated_cost=shares[item.case_item_id], unit_cost=unit,
                previous_unit_cost=lot.individual_cost, allocation_method=data.allocation_method)
            db.add(allocation); db.flush()
            record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code='IMPORT_COST',
                action='ALLOCATE_COST', entity_type='LOT', entity_id=lot.lot_id, source='API',
                before={'individual_cost': lot.individual_cost, 'bl_no': lot.bl_no},
                after={'individual_cost': unit, 'allocated_cost': shares[item.case_item_id], 'actual_weight': kg, 'bl_no': case.bl_no},
                reason=data.reason, related_entity_type='IMPORT_COST', related_entity_id=row.settlement_id)
            lot.individual_cost = unit
            if not lot.bl_no: lot.bl_no = case.bl_no
            if case.contract_id:
                contract = locked(db, models.FinancingContract, comp_code, 'contract_id', case.contract_id)
                if contract.status not in {'CONFIRMED','ACTIVE'}: fail('원계약 상태가 유효하지 않습니다.')
                link = db.query(models.FinancingContractLot).filter_by(contract_id=case.contract_id, lot_id=lot.lot_id).first()
                if link:
                    if link.contract_item_id != item.contract_item_id or link.status != 'ACTIVE': fail('기존 계약 LOT 연결과 수입상품이 다릅니다.')
                else:
                    boxes = db.query(func.sum(models.InboundItem.box_qty)).join(models.Inbound).filter(models.Inbound.comp_code == comp_code, models.InboundItem.lot_id == lot.lot_id).scalar() or 0
                    contracts._add_lot(db, contract, contracts.ContractLotInput(lot_id=lot.lot_id,
                        contract_item_id=item.contract_item_id, contract_box_qty=boxes, contract_weight=kg,
                        linked_date=case.warehouse_receipt_date), request.state.user_id)
            allocation_snapshot.append({**columns(allocation), 'product_id': lot.product_id,
                'product_name': db.get(models.Product, lot.product_id).product_name, 'lot_code': lot.lot_code,
                'bl_no': case.bl_no, 'warehouse_id': lot.warehouse_id})
        row.status = 'CONFIRMED'; row.total_cost = total; row.confirmed_at = datetime.now(timezone.utc)
        row.updated_by = request.state.user_id; row.updated_at = row.confirmed_at
        before_case = view(case); case.status = 'COST_CONFIRMED'
        case.updated_by = request.state.user_id; case.updated_at = row.confirmed_at
        row.snapshot_json = dumps({'case': view(case), 'rows': [columns(x) for x in row.rows],
            'allocations': allocation_snapshot, 'total_cost': total, 'version': row.version,
            'confirmed_at': row.confirmed_at, 'confirmed_by': request.state.user_id})
        db.flush(); db.expire(row, ['allocations'])
        audit(db, request, case, 'COST_CONFIRMED', before_case)
        audit(db, request, row, 'CONFIRM', before, data.reason); result = view(row)
    return result


@router.post('/import-costs/{settlement_id}/cancel')
def cancel_cost(comp_code: str, settlement_id: int, data: Reason, request: Request, db: Session = Depends(get_db)):
    with atomic(db):
        row = locked(db, models.ImportCostSettlement, comp_code, 'settlement_id', settlement_id)
        case = locked(db, models.ImportCase, comp_code, 'import_case_id', row.import_case_id)
        if row.status not in {'DRAFT','CONFIRMED'} or case.status == 'CLOSED': fail('현재 상태에서 확정취소할 수 없습니다.')
        before = view(row)
        if row.status == 'CONFIRMED':
            targets = target_lots(db, case, row.settlement_id)
            for allocation in row.allocations:
                lot = next(lot for _, lot, _ in targets if lot.lot_id == allocation.lot_id)
                if lot.individual_cost != allocation.unit_cost: fail('후속 원가 변경이 있어 자동 복원할 수 없습니다.')
                record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code='IMPORT_COST',
                    action='RESTORE_COST', entity_type='LOT', entity_id=lot.lot_id, source='API',
                    before={'individual_cost': lot.individual_cost}, after={'individual_cost': allocation.previous_unit_cost},
                    reason=data.reason, related_entity_type='IMPORT_COST', related_entity_id=row.settlement_id)
                lot.individual_cost = allocation.previous_unit_cost
        before_case = view(case)
        row.status = 'CANCELLED'; case.status = 'COSTING'
        audit(db, request, case, 'COST_CANCELLED', before_case, data.reason)
        audit(db, request, row, 'CANCEL', before, data.reason); result = view(row)
    return result
