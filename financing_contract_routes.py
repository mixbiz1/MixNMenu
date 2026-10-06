"""Financing contract setup over existing MXMN accounts, LOTs and Audit history."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from audit_service import record_audit_event
from database import get_db
import models
from trade_common import allocate_document_no


router = APIRouter()
TEMPLATES = {"ALL_IN", "EXCLUDE_BROKERAGE", "EXCLUDE_BROKERAGE_STORAGE", "INTEREST_ONLY", "COST_ONLY", "FREE"}
CONTRACT_TYPES = {"IMPORT_AGENCY", "BL_TRANSFER", "DOMESTIC_PURCHASE"}


class TermInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effective_from: date
    recovery_template: str = "FREE"
    contract_days: int | None = Field(default=None, ge=1)
    annual_interest_rate: Decimal = Field(default=Decimal(0), ge=0)
    interest_rate_1: Decimal | None = Field(default=None, ge=0)
    interest_period_days_1: int | None = Field(default=None, ge=1)
    interest_rate_2: Decimal | None = Field(default=None, ge=0)
    interest_period_days_2: int | None = Field(default=None, ge=1)
    storage_rate_per_kg_day: Decimal = Field(default=Decimal(0), ge=0)
    brokerage_rate: Decimal = Field(default=Decimal(0), ge=0)
    brokerage_rate_1: Decimal | None = Field(default=None, ge=0)
    brokerage_rate_2: Decimal | None = Field(default=None, ge=0)
    inbound_outbound_rate_per_kg: Decimal = Field(default=Decimal(0), ge=0)
    weighing_rate_per_box: Decimal = Field(default=Decimal(0), ge=0)
    conditions: dict[str, Any] = Field(default_factory=dict)
    change_reason: str | None = Field(default=None, max_length=1000)


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: int
    agreement_status: str = "PENDING"
    agreement_date: date | None = None
    effective_date: date | None = None
    memo: str | None = Field(default=None, max_length=1000)


class ContractLotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_id: int
    contract_item_id: int | None = None
    contract_box_qty: int = Field(default=0, ge=0)
    contract_weight: Decimal = Field(default=Decimal(0), ge=0)
    linked_date: date | None = None
    conditions_override: dict[str, Any] | None = None
    memo: str | None = Field(default=None, max_length=1000)


class ContractItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int
    contract_box_qty: int = Field(default=0, ge=0)
    contract_weight: Decimal = Field(default=Decimal(0), ge=0)
    contract_unit_price: Decimal | None = Field(default=None, ge=0)
    memo: str | None = Field(default=None, max_length=1000)


class ContractCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_no: str | None = Field(default=None, max_length=50)
    contract_type: str
    contract_date: date
    contractor_account_id: int
    customs_date: date | None = None
    cost_finalized_date: date | None = None
    warehouse_arrival_date: date | None = None
    financing_start_date: date | None = None
    deposit_required: bool = False
    deposit_amount: Decimal = Field(default=Decimal(0), ge=0)
    deposit_memo: str | None = Field(default=None, max_length=1000)
    memo: str | None = Field(default=None, max_length=1000)
    items: list[ContractItemInput] = Field(default_factory=list)
    participants: list[ParticipantInput] = Field(default_factory=list)
    lots: list[ContractLotInput] = Field(default_factory=list)
    terms: list[TermInput] = Field(default_factory=list)


class ContractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_type: str
    contract_date: date
    contractor_account_id: int
    customs_date: date | None = None
    cost_finalized_date: date | None = None
    warehouse_arrival_date: date | None = None
    financing_start_date: date | None = None
    deposit_required: bool = False
    deposit_amount: Decimal = Field(default=Decimal(0), ge=0)
    deposit_memo: str | None = Field(default=None, max_length=1000)
    memo: str | None = Field(default=None, max_length=1000)


class CancelInput(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class ParticipantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agreement_status: str
    agreement_date: date | None = None
    effective_date: date | None = None
    status: str = "ACTIVE"
    memo: str | None = Field(default=None, max_length=1000)


def _err(status: int, detail: str):
    raise HTTPException(status_code=status, detail=detail)


def _company(db: Session, comp_code: str):
    row = db.get(models.Company, comp_code)
    if row is None:
        _err(404, "회사를 찾을 수 없습니다.")
    return row


def _account(db: Session, comp_code: str, account_id: int, *, require_sale: bool = False):
    row = (db.query(models.Account).join(models.CompanyAccount, models.CompanyAccount.account_id == models.Account.account_id)
           .filter(models.CompanyAccount.comp_code == comp_code,
                   models.CompanyAccount.account_id == account_id,
                   models.CompanyAccount.use_yn.is_(True), models.CompanyAccount.trade_stop_yn.is_(False),
                   models.Account.use_yn.is_(True)).first())
    if require_sale and row is not None:
        sale_relation = db.query(models.CompanyAccount).filter_by(comp_code=comp_code, account_id=account_id,
            use_yn=True, trade_stop_yn=False, sales_yn=True).first()
        if sale_relation is None:
            row = None
    if row is None:
        _err(404, "해당 회사에서 사용할 수 있는 거래처가 아닙니다.")
    return row


def _contract(db: Session, comp_code: str, contract_id: int):
    row = (db.query(models.FinancingContract)
           .filter_by(comp_code=comp_code, contract_id=contract_id).first())
    if row is None:
        _err(404, "파이낸싱 계약을 찾을 수 없습니다.")
    return row


def _actor(request: Request) -> str:
    return getattr(request.state, "user_id", "system")


def _can_approve_cost_return(db: Session, request: Request) -> bool:
    if bool(getattr(request.state, "is_admin", False)):
        return True
    return db.query(models.UserMenuPermission).filter_by(
        user_id=_actor(request), menu_code="FINANCING_CONTRACT", can_update=True).first() is not None


def _term_payload(data: TermInput):
    if data.recovery_template not in TEMPLATES:
        _err(400, "지원하지 않는 출고가 회수 유형입니다.")
    return data.model_dump(exclude={"conditions"})


def _append_term(db: Session, contract: models.FinancingContract, data: TermInput, actor: str,
                 *, is_admin: bool = False):
    _term_payload(data)
    if data.interest_rate_2 is not None and (data.interest_rate_1 is None and data.annual_interest_rate == 0 or data.interest_period_days_1 is None):
        _err(400, "2차 이자율을 적용하려면 1차 이자율과 1차 적용기간이 필요합니다.")
    if data.recovery_template == "INTEREST_ONLY":
        if contract.contract_type != "DOMESTIC_PURCHASE":
            _err(409, "원가를 반품으로 정리하는 이자형은 국내매입계약에서만 선택할 수 있습니다.")
        if (data.conditions.get("cost_return_management_approved") is not True or
                data.conditions.get("counterparty_agreement_confirmed") is not True or
                not str(data.conditions.get("management_approval_memo", "")).strip()):
            _err(409, "이자형은 원가 반품에 대한 경영자 승인, 계약자 합의, 승인 메모가 기록되어야 합니다.")
        if not is_admin:
            _err(403, "이자형 원가반품 조건은 파이낸싱 계약 수정 권한자가 승인해야 합니다.")
    latest = max(contract.terms, key=lambda row: row.version, default=None)
    if latest and data.effective_from < latest.effective_from:
        _err(409, "새 계약조건의 적용일은 기존 마지막 조건 적용일보다 빠를 수 없습니다.")
    if contract.status not in {"DRAFT", "CONFIRMED", "ACTIVE"}:
        _err(409, "종결 또는 취소된 계약에는 조건을 추가할 수 없습니다.")
    row = models.FinancingContractTerm(
        contract_id=contract.contract_id, version=(latest.version + 1 if latest else 1),
        recovery_template=data.recovery_template, contract_days=data.contract_days,
        annual_interest_rate=data.interest_rate_1 if data.interest_rate_1 is not None else data.annual_interest_rate,
        interest_rate_1=data.interest_rate_1 if data.interest_rate_1 is not None else data.annual_interest_rate,
        interest_period_days_1=data.interest_period_days_1,
        interest_rate_2=data.interest_rate_2,
        interest_period_days_2=data.interest_period_days_2,
        storage_rate_per_kg_day=data.storage_rate_per_kg_day,
        brokerage_rate=data.brokerage_rate_1 if data.brokerage_rate_1 is not None else data.brokerage_rate,
        brokerage_rate_1=data.brokerage_rate_1 if data.brokerage_rate_1 is not None else data.brokerage_rate,
        brokerage_rate_2=data.brokerage_rate_2,
        inbound_outbound_rate_per_kg=data.inbound_outbound_rate_per_kg,
        weighing_rate_per_box=data.weighing_rate_per_box,
        conditions_json=json.dumps({**data.conditions,
            **({"cost_return_management_approved_by": actor} if data.recovery_template == "INTEREST_ONLY" else {})},
            ensure_ascii=False, sort_keys=True, default=str),
        effective_from=data.effective_from, change_reason=data.change_reason, created_by=actor,
    )
    contract.terms.append(row)
    db.flush()
    record_audit_event(db, comp_code=contract.comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CREATE", entity_type="FINANCING_CONTRACT_TERM", entity_id=row.term_id,
        source="API", after={"contract_id": contract.contract_id, "version": row.version,
        "effective_from": row.effective_from, "recovery_template": row.recovery_template,
        "contract_days": row.contract_days, "interest_rate_1": row.interest_rate_1,
        "interest_period_days_1": row.interest_period_days_1, "interest_rate_2": row.interest_rate_2,
        "interest_period_days_2": row.interest_period_days_2,
        "storage_rate_per_kg_day": row.storage_rate_per_kg_day,
        "brokerage_rate_1": row.brokerage_rate_1, "brokerage_rate_2": row.brokerage_rate_2,
        "inbound_outbound_rate_per_kg": row.inbound_outbound_rate_per_kg,
        "weighing_rate_per_box": row.weighing_rate_per_box,
        "conditions": json.loads(row.conditions_json)},
        related_entity_type="FINANCING_CONTRACT", related_entity_id=contract.contract_id)
    return row


def _add_participant(db: Session, contract: models.FinancingContract, data: ParticipantInput, actor: str):
    if contract.status != "DRAFT":
        _err(409, "계약 확정 후에는 참여업체 구성을 변경할 수 없습니다.")
    _account(db, contract.comp_code, data.account_id, require_sale=True)
    if data.account_id == contract.contractor_account_id:
        _err(409, "최초 계약업체는 이미 계약 책임자로 등록되어 있습니다.")
    if data.agreement_status not in {"PENDING", "CONFIRMED"}:
        _err(400, "특별출고약정 상태는 PENDING 또는 CONFIRMED여야 합니다.")
    if data.agreement_status == "CONFIRMED" and not data.agreement_date:
        _err(400, "특별출고약정을 확인한 날짜를 입력해야 합니다.")
    row = models.FinancingContractParticipant(
        contract_id=contract.contract_id, account_id=data.account_id, role="AUTHORIZED_SHIPPER",
        agreement_status=data.agreement_status, agreement_date=data.agreement_date,
        effective_date=data.effective_date or data.agreement_date, status="ACTIVE", memo=data.memo, created_by=actor)
    contract.participants.append(row)
    db.flush()
    record_audit_event(db, comp_code=contract.comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CREATE", entity_type="FINANCING_CONTRACT_PARTICIPANT", entity_id=row.participant_id,
        source="API", after={"contract_id": contract.contract_id, "account_id": row.account_id,
        "role": row.role, "agreement_status": row.agreement_status, "agreement_date": row.agreement_date},
        related_entity_type="FINANCING_CONTRACT", related_entity_id=contract.contract_id)
    return row


def _add_item(db: Session, contract: models.FinancingContract, data: ContractItemInput, actor: str):
    if contract.status != "DRAFT":
        _err(409, "계약상품은 초안 상태에서만 추가할 수 있습니다.")
    if data.contract_box_qty == 0 and data.contract_weight == 0:
        _err(400, "계약상품 수량은 Box 또는 Kg 중 하나 이상 입력해야 합니다.")
    product = db.get(models.Product, data.product_id)
    if product is None or not product.use_yn:
        _err(404, "사용 가능한 상품 Master를 찾을 수 없습니다.")
    row = models.FinancingContractItem(
        contract_id=contract.contract_id, line_no=len(contract.items) + 1,
        product_id=product.product_id, contract_box_qty=data.contract_box_qty,
        contract_weight=data.contract_weight, contract_unit_price=data.contract_unit_price,
        memo=data.memo, created_by=actor)
    contract.items.append(row)
    db.flush()
    record_audit_event(db, comp_code=contract.comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CREATE", entity_type="FINANCING_CONTRACT_ITEM", entity_id=row.contract_item_id,
        source="API", after={"contract_id": contract.contract_id, "line_no": row.line_no,
        "product_id": row.product_id, "contract_box_qty": row.contract_box_qty,
        "contract_weight": row.contract_weight, "contract_unit_price": row.contract_unit_price,
        "memo": row.memo}, related_entity_type="FINANCING_CONTRACT", related_entity_id=contract.contract_id)
    return row


def _generate_contract_no(db: Session, comp_code: str, contract_date: date,
                          contractor: models.Account, contract_type: str) -> str:
    type_code = {"IMPORT_AGENCY": "IM", "BL_TRANSFER": "BL", "DOMESTIC_PURCHASE": "DP"}[contract_type]
    if db.get_bind().dialect.name == "mssql":
        issued = allocate_document_no(db, comp_code, "FINANCING_CONTRACT", contract_date)
        sequence = int(issued.rsplit("-", 1)[1])
    else:
        # SQLite is used by the isolated route tests. Production SQL Server uses the
        # shared UPDLOCK/HOLDLOCK sequence allocator above.
        sequence = (db.query(func.max(models.FinancingContract.contract_id)).filter(
            models.FinancingContract.comp_code == comp_code).scalar() or 0) + 1
    return f"FC-{comp_code}-{contract_date:%y%m%d}-{contractor.account_code[:8]}-{type_code}-{sequence:04d}"


def _add_lot(db: Session, contract: models.FinancingContract, data: ContractLotInput, actor: str):
    if contract.status not in {"DRAFT", "CONFIRMED", "ACTIVE"}:
        _err(409, "종결 또는 취소된 계약에는 LOT를 연결할 수 없습니다.")
    if data.contract_box_qty == 0 and data.contract_weight == 0:
        _err(400, "배정 수량은 Box 또는 Kg 중 하나 이상 입력해야 합니다.")
    lot = db.query(models.Lot).filter(models.Lot.comp_code == contract.comp_code,
        models.Lot.lot_id == data.lot_id, models.Lot.use_yn.is_(True)).first()
    if lot is None:
        _err(404, "해당 회사에서 사용할 수 있는 기존 LOT가 아닙니다.")
    if lot.status != "OPEN":
        _err(409, "OPEN 상태인 ERP LOT만 계약상품에 배정할 수 있습니다.")
    candidates = [item for item in contract.items if item.product_id == lot.product_id]
    if data.contract_item_id is not None:
        item = next((item for item in contract.items if item.contract_item_id == data.contract_item_id), None)
        if item is None:
            _err(404, "해당 계약의 계약상품을 찾을 수 없습니다.")
        if item.product_id != lot.product_id:
            _err(409, "LOT 상품과 선택한 계약상품이 다릅니다.")
    elif len(candidates) == 1:
        item = candidates[0]
    elif not candidates:
        _err(409, "LOT 상품에 해당하는 계약상품이 없습니다.")
    else:
        _err(400, "같은 상품이 여러 줄이면 LOT 배정 시 계약상품을 지정해야 합니다.")
    allocated_box = sum(x.contract_box_qty for x in item.lots if x.status == "ACTIVE")
    allocated_weight = sum((Decimal(x.contract_weight or 0) for x in item.lots if x.status == "ACTIVE"), Decimal(0))
    if ((item.contract_box_qty > 0 and allocated_box + data.contract_box_qty > item.contract_box_qty) or
            (Decimal(item.contract_weight or 0) > 0 and allocated_weight + data.contract_weight > Decimal(item.contract_weight or 0))):
        _err(409, "이 LOT 배정으로 계약상품의 Box 또는 Kg 수량을 초과합니다.")
    inbound_box = db.query(func.coalesce(func.sum(models.InboundItem.box_qty), 0)).join(models.Inbound).filter(
        models.Inbound.comp_code == contract.comp_code, models.InboundItem.lot_id == lot.lot_id).scalar() or 0
    outbound_box = db.query(func.coalesce(func.sum(models.OutboundItem.box_qty), 0)).join(models.Outbound).filter(
        models.Outbound.comp_code == contract.comp_code, models.OutboundItem.lot_id == lot.lot_id).scalar() or 0
    inbound_weight = db.query(func.coalesce(func.sum(models.InboundItem.weight), 0)).join(models.Inbound).filter(
        models.Inbound.comp_code == contract.comp_code, models.InboundItem.lot_id == lot.lot_id).scalar() or 0
    outbound_weight = db.query(func.coalesce(func.sum(models.OutboundItem.weight), 0)).join(models.Outbound).filter(
        models.Outbound.comp_code == contract.comp_code, models.OutboundItem.lot_id == lot.lot_id).scalar() or 0
    active = (db.query(models.FinancingContractLot).join(models.FinancingContract)
        .filter(models.FinancingContract.comp_code == contract.comp_code,
            models.FinancingContractLot.lot_id == lot.lot_id,
            models.FinancingContractLot.status == "ACTIVE",
            models.FinancingContract.status.in_(["DRAFT", "CONFIRMED", "ACTIVE"])).all())
    if (sum(x.contract_box_qty for x in active) + data.contract_box_qty > int(inbound_box) - int(outbound_box) or
        sum((Decimal(x.contract_weight or 0) for x in active), Decimal(0)) + data.contract_weight > Decimal(inbound_weight or 0) - Decimal(outbound_weight or 0)):
        _err(409, f"LOT {lot.lot_code}의 계약 배정량이 기존 재고수불 잔량을 초과합니다.")
    row = models.FinancingContractLot(contract_id=contract.contract_id, lot_id=lot.lot_id,
        contract_item_id=item.contract_item_id,
        contract_box_qty=data.contract_box_qty, contract_weight=data.contract_weight,
        linked_date=data.linked_date or date.today(),
        conditions_override_json=json.dumps(data.conditions_override, ensure_ascii=False, sort_keys=True, default=str) if data.conditions_override is not None else None,
        memo=data.memo, created_by=actor)
    contract.lots.append(row)
    db.flush()
    record_audit_event(db, comp_code=contract.comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CREATE", entity_type="FINANCING_CONTRACT_LOT", entity_id=row.contract_lot_id,
        source="API", after={"contract_id": contract.contract_id, "lot_id": row.lot_id,
        "contract_item_id": row.contract_item_id,
        "contract_box_qty": row.contract_box_qty, "contract_weight": row.contract_weight,
        "conditions_override": data.conditions_override},
        related_entity_type="FINANCING_CONTRACT", related_entity_id=contract.contract_id)
    return row


def _snapshot(row: models.FinancingContract):
    return {"contract_id": row.contract_id, "comp_code": row.comp_code, "contract_no": row.contract_no,
        "contract_type": row.contract_type, "contract_date": row.contract_date, "contractor_account_id": row.contractor_account_id,
        "contractor_name": row.contractor.account_name if row.contractor else None, "status": row.status,
        "customs_date": row.customs_date, "cost_finalized_date": row.cost_finalized_date,
        "warehouse_arrival_date": row.warehouse_arrival_date, "financing_start_date": row.financing_start_date,
        "deposit_required": row.deposit_required, "deposit_amount": row.deposit_amount,
        "deposit_memo": row.deposit_memo, "memo": row.memo, "created_by": row.created_by,
        "created_at": row.created_at, "updated_by": row.updated_by, "updated_at": row.updated_at,
        "confirmed_by": row.confirmed_by, "confirmed_at": row.confirmed_at,
        "cancelled_by": row.cancelled_by, "cancelled_at": row.cancelled_at,
        "participants": [{"participant_id": p.participant_id, "account_id": p.account_id,
            "account_name": p.account.account_name if p.account else None, "role": p.role,
            "agreement_status": p.agreement_status, "agreement_date": p.agreement_date,
            "effective_date": p.effective_date, "status": p.status, "memo": p.memo} for p in row.participants],
        "lots": [{"contract_lot_id": x.contract_lot_id, "lot_id": x.lot_id,
            "contract_item_id": x.contract_item_id,
            "lot_code": x.lot.lot_code if x.lot else None,
            "product_id": x.lot.product_id if x.lot else None,
            "product_name": x.lot.product.product_name if x.lot and x.lot.product else None,
            "warehouse_id": x.lot.warehouse_id if x.lot else None,
            "warehouse_name": x.lot.warehouse.warehouse_name if x.lot and x.lot.warehouse else None,
            "contract_box_qty": x.contract_box_qty, "contract_weight": x.contract_weight,
            "linked_date": x.linked_date, "status": x.status, "conditions_override": json.loads(x.conditions_override_json) if x.conditions_override_json else None,
            "memo": x.memo} for x in row.lots],
        "items": [{"contract_item_id": x.contract_item_id, "line_no": x.line_no,
            "product_id": x.product_id, "product_code": x.product.product_code if x.product else None,
            "product_name": x.product.product_name if x.product else None,
            "contract_box_qty": x.contract_box_qty, "contract_weight": x.contract_weight,
            "contract_unit_price": x.contract_unit_price, "memo": x.memo,
            "allocated_box_qty": sum(l.contract_box_qty for l in x.lots if l.status == "ACTIVE"),
            "allocated_weight": sum((Decimal(l.contract_weight or 0) for l in x.lots if l.status == "ACTIVE"), Decimal(0))}
            for x in row.items],
        "terms": [{"term_id": t.term_id, "version": t.version, "effective_from": t.effective_from,
            "recovery_template": t.recovery_template, "contract_days": t.contract_days,
            "annual_interest_rate": t.annual_interest_rate, "storage_rate_per_kg_day": t.storage_rate_per_kg_day,
            "interest_rate_1": t.interest_rate_1, "interest_period_days_1": t.interest_period_days_1,
            "interest_rate_2": t.interest_rate_2, "interest_period_days_2": t.interest_period_days_2,
            "brokerage_rate": t.brokerage_rate, "brokerage_rate_1": t.brokerage_rate_1,
            "brokerage_rate_2": t.brokerage_rate_2, "inbound_outbound_rate_per_kg": t.inbound_outbound_rate_per_kg,
            "weighing_rate_per_box": t.weighing_rate_per_box, "conditions": json.loads(t.conditions_json or "{}"),
            "change_reason": t.change_reason, "created_by": t.created_by, "created_at": t.created_at} for t in row.terms]}


@router.get("/api/v1/companies/{comp_code}/financing-contracts")
def list_contracts(comp_code: str, db: Session = Depends(get_db)):
    _company(db, comp_code)
    rows = db.query(models.FinancingContract).filter_by(comp_code=comp_code).order_by(
        models.FinancingContract.contract_date.desc(), models.FinancingContract.contract_id.desc()).all()
    return [_snapshot(row) for row in rows]


@router.get("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}")
def get_contract(comp_code: str, contract_id: int, db: Session = Depends(get_db)):
    return _snapshot(_contract(db, comp_code, contract_id))


@router.post("/api/v1/companies/{comp_code}/financing-contracts", status_code=201)
def create_contract(comp_code: str, data: ContractCreate, request: Request, db: Session = Depends(get_db)):
    _company(db, comp_code)
    if data.contract_type not in CONTRACT_TYPES:
        _err(400, "지원하지 않는 파이낸싱 계약 유형입니다.")
    contractor = _account(db, comp_code, data.contractor_account_id)
    actor = _actor(request)
    contract_no = _generate_contract_no(db, comp_code, data.contract_date, contractor, data.contract_type)
    row = models.FinancingContract(comp_code=comp_code, contract_no=contract_no,
        contract_type=data.contract_type, contract_date=data.contract_date,
        contractor_account_id=data.contractor_account_id, customs_date=data.customs_date,
        cost_finalized_date=data.cost_finalized_date, warehouse_arrival_date=data.warehouse_arrival_date,
        financing_start_date=data.financing_start_date, deposit_required=data.deposit_required,
        deposit_amount=data.deposit_amount, deposit_memo=data.deposit_memo, memo=data.memo,
        status="DRAFT", created_by=actor, updated_by=actor)
    db.add(row)
    try:
        db.flush()
        row.participants.append(models.FinancingContractParticipant(account_id=data.contractor_account_id,
            role="ORIGINAL_CONTRACTOR", agreement_status="NOT_REQUIRED", status="ACTIVE", created_by=actor))
        record_audit_event(db, comp_code=comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
            action="CREATE", entity_type="FINANCING_CONTRACT", entity_id=row.contract_id,
            source="API", after={"contract_no": row.contract_no, "contract_type": row.contract_type,
            "contract_date": row.contract_date, "contractor_account_id": row.contractor_account_id,
            "status": row.status, "customs_date": row.customs_date, "cost_finalized_date": row.cost_finalized_date,
            "warehouse_arrival_date": row.warehouse_arrival_date, "financing_start_date": row.financing_start_date,
            "deposit_required": row.deposit_required, "deposit_amount": row.deposit_amount,
            "deposit_memo": row.deposit_memo, "memo": row.memo})
        for participant in data.participants:
            _add_participant(db, row, participant, actor)
        items = list(data.items)
        if not items and data.lots:
            # Compatibility for the first Phase 1 client: turn its pre-existing LOT
            # selection into a contract item snapshot when its goods are already in stock.
            totals: dict[int, tuple[int, Decimal]] = {}
            for lot_data in data.lots:
                lot = db.query(models.Lot).filter_by(lot_id=lot_data.lot_id, comp_code=comp_code).first()
                if lot is None:
                    _err(404, "해당 회사에서 사용할 수 있는 기존 LOT가 아닙니다.")
                box, weight = totals.get(lot.product_id, (0, Decimal(0)))
                totals[lot.product_id] = (box + lot_data.contract_box_qty, weight + lot_data.contract_weight)
            items = [ContractItemInput(product_id=product_id, contract_box_qty=qty[0], contract_weight=qty[1])
                for product_id, qty in totals.items()]
        for item in items:
            _add_item(db, row, item, actor)
        for lot in data.lots:
            _add_lot(db, row, lot, actor)
        for term in data.terms:
            _append_term(db, row, term, actor, is_admin=_can_approve_cost_return(db, request))
        db.commit()
        return _snapshot(row)
    except IntegrityError as exc:
        db.rollback()
        _err(409, "계약번호 또는 연결 데이터가 중복되었거나 유효하지 않습니다.")


@router.put("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}")
def update_contract(comp_code: str, contract_id: int, data: ContractUpdate, request: Request,
                    db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    if row.status != "DRAFT":
        _err(409, "확정된 계약의 기본정보는 수정할 수 없습니다.")
    if data.contract_type not in CONTRACT_TYPES:
        _err(400, "지원하지 않는 파이낸싱 계약 유형입니다.")
    _account(db, comp_code, data.contractor_account_id)
    actor = _actor(request)
    before = {"contract_no": row.contract_no, "contract_type": row.contract_type, "contract_date": row.contract_date,
        "contractor_account_id": row.contractor_account_id, "customs_date": row.customs_date,
        "cost_finalized_date": row.cost_finalized_date, "warehouse_arrival_date": row.warehouse_arrival_date,
        "financing_start_date": row.financing_start_date, "deposit_required": row.deposit_required,
        "deposit_amount": row.deposit_amount, "deposit_memo": row.deposit_memo, "memo": row.memo}
    if row.contractor_account_id != data.contractor_account_id:
        _err(409, "최초 계약업체는 생성 후 변경할 수 없습니다. 새 계약으로 등록하십시오.")
    if row.contract_type != data.contract_type or row.contract_date != data.contract_date:
        row.contract_no = _generate_contract_no(db, comp_code, data.contract_date, row.contractor, data.contract_type)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.updated_by = actor
    row.updated_at = datetime.now(timezone.utc)
    after = {key: getattr(row, key) for key in before}
    record_audit_event(db, comp_code=comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="UPDATE", entity_type="FINANCING_CONTRACT", entity_id=row.contract_id,
        source="API", before=before, after=after)
    db.commit()
    return _snapshot(row)


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/participants", status_code=201)
def add_participant(comp_code: str, contract_id: int, data: ParticipantInput, request: Request,
                    db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    result = _add_participant(db, row, data, _actor(request))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _err(409, "이 거래처는 이미 계약 참여자로 등록되어 있습니다.")
    return {"participant_id": result.participant_id, "contract_id": result.contract_id,
        "account_id": result.account_id, "role": result.role, "agreement_status": result.agreement_status,
        "agreement_date": result.agreement_date, "effective_date": result.effective_date, "status": result.status}


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/items", status_code=201)
def add_contract_item(comp_code: str, contract_id: int, data: ContractItemInput, request: Request,
                      db: Session = Depends(get_db)):
    contract = _contract(db, comp_code, contract_id)
    item = _add_item(db, contract, data, _actor(request))
    db.commit()
    return {"contract_item_id": item.contract_item_id, "contract_id": contract_id,
        "line_no": item.line_no, "product_id": item.product_id,
        "contract_box_qty": item.contract_box_qty, "contract_weight": item.contract_weight}


@router.put("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/participants/{participant_id}")
def update_participant(comp_code: str, contract_id: int, participant_id: int, data: ParticipantUpdate,
                       request: Request, db: Session = Depends(get_db)):
    contract = _contract(db, comp_code, contract_id)
    if contract.status != "DRAFT":
        _err(409, "계약 확정 후에는 참여업체 약정정보를 수정할 수 없습니다.")
    row = db.query(models.FinancingContractParticipant).filter_by(
        contract_id=contract_id, participant_id=participant_id).first()
    if row is None:
        _err(404, "계약 참여업체를 찾을 수 없습니다.")
    if row.role == "ORIGINAL_CONTRACTOR":
        _err(409, "최초 계약업체의 역할은 변경할 수 없습니다.")
    if data.agreement_status not in {"PENDING", "CONFIRMED"} or data.status not in {"ACTIVE", "INACTIVE"}:
        _err(400, "특별약정 또는 참여 상태값이 올바르지 않습니다.")
    if data.agreement_status == "CONFIRMED" and not data.agreement_date:
        _err(400, "특별출고약정을 확인한 날짜를 입력해야 합니다.")
    before = {"agreement_status": row.agreement_status, "agreement_date": row.agreement_date,
        "effective_date": row.effective_date, "status": row.status, "memo": row.memo}
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    if row.agreement_status == "CONFIRMED" and row.effective_date is None:
        row.effective_date = row.agreement_date
    record_audit_event(db, comp_code=comp_code, user_id=_actor(request), menu_code="FINANCING_CONTRACT",
        action="UPDATE", entity_type="FINANCING_CONTRACT_PARTICIPANT", entity_id=row.participant_id,
        source="API", before=before, after=data.model_dump(mode="json"),
        related_entity_type="FINANCING_CONTRACT", related_entity_id=contract_id)
    db.commit()
    return {"participant_id": row.participant_id, "contract_id": contract_id, "account_id": row.account_id,
        "role": row.role, "agreement_status": row.agreement_status, "agreement_date": row.agreement_date,
        "effective_date": row.effective_date, "status": row.status, "memo": row.memo}


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/lots", status_code=201)
def add_contract_lot(comp_code: str, contract_id: int, data: ContractLotInput, request: Request,
                     db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    result = _add_lot(db, row, data, _actor(request))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _err(409, "이 LOT는 이미 해당 계약에 연결되어 있습니다.")
    return {"contract_lot_id": result.contract_lot_id, "contract_id": result.contract_id,
        "lot_id": result.lot_id, "contract_box_qty": result.contract_box_qty,
        "contract_weight": result.contract_weight, "linked_date": result.linked_date}


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/terms", status_code=201)
def add_term(comp_code: str, contract_id: int, data: TermInput, request: Request, db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    try:
        term = _append_term(db, row, data, _actor(request), is_admin=_can_approve_cost_return(db, request))
        db.commit()
    except IntegrityError:
        db.rollback()
        _err(409, "계약조건 버전 또는 적용일이 중복되었습니다.")
    return {"term_id": term.term_id, "contract_id": term.contract_id, "version": term.version,
        "effective_from": term.effective_from, "recovery_template": term.recovery_template,
        "conditions": json.loads(term.conditions_json)}


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/confirm")
def confirm_contract(comp_code: str, contract_id: int, request: Request, db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    if row.status != "DRAFT":
        _err(409, "초안 상태의 계약만 확정할 수 있습니다.")
    if not row.items or not row.terms:
        _err(409, "계약을 확정하기 전에 계약상품과 계약조건 버전을 등록해야 합니다.")
    unapproved = [p for p in row.participants if p.role == "AUTHORIZED_SHIPPER" and
        (p.status != "ACTIVE" or p.agreement_status != "CONFIRMED" or p.agreement_date is None)]
    if unapproved:
        _err(409, "추가 출고업체는 특별출고약정을 확인한 뒤 계약을 확정할 수 있습니다.")
    # Contract quantities are not inventory. At confirmation, prevent total confirmed commitments
    # from exceeding today's source-ledger availability; every later release must re-check it.
    for link in row.lots:
        inbound_box = db.query(func.coalesce(func.sum(models.InboundItem.box_qty), 0)).join(models.Inbound).filter(
            models.Inbound.comp_code == comp_code, models.InboundItem.lot_id == link.lot_id).scalar() or 0
        outbound_box = db.query(func.coalesce(func.sum(models.OutboundItem.box_qty), 0)).join(models.Outbound).filter(
            models.Outbound.comp_code == comp_code, models.OutboundItem.lot_id == link.lot_id).scalar() or 0
        inbound_weight = db.query(func.coalesce(func.sum(models.InboundItem.weight), 0)).join(models.Inbound).filter(
            models.Inbound.comp_code == comp_code, models.InboundItem.lot_id == link.lot_id).scalar() or 0
        outbound_weight = db.query(func.coalesce(func.sum(models.OutboundItem.weight), 0)).join(models.Outbound).filter(
            models.Outbound.comp_code == comp_code, models.OutboundItem.lot_id == link.lot_id).scalar() or 0
        active = (db.query(models.FinancingContractLot).join(models.FinancingContract)
            .filter(models.FinancingContract.comp_code == comp_code,
                models.FinancingContractLot.lot_id == link.lot_id,
                models.FinancingContract.contract_id != row.contract_id,
                models.FinancingContract.status.in_(["DRAFT", "CONFIRMED", "ACTIVE"]),
                models.FinancingContractLot.status == "ACTIVE").all())
        committed_box = sum(x.contract_box_qty for x in active) + link.contract_box_qty
        committed_weight = sum((Decimal(x.contract_weight or 0) for x in active), Decimal(0)) + Decimal(link.contract_weight or 0)
        available_box = int(inbound_box) - int(outbound_box)
        available_weight = Decimal(inbound_weight or 0) - Decimal(outbound_weight or 0)
        if committed_box > available_box or committed_weight > available_weight:
            _err(409, f"LOT {link.lot.lot_code}의 계약수량이 기존 재고수불 잔량 또는 다른 확정계약 배정량을 초과합니다.")
    actor = _actor(request)
    before = {"status": row.status}
    row.status = "CONFIRMED"
    row.confirmed_by = row.updated_by = actor
    row.confirmed_at = row.updated_at = datetime.now(timezone.utc)
    record_audit_event(db, comp_code=comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CONFIRM", entity_type="FINANCING_CONTRACT", entity_id=row.contract_id,
        source="API", before=before, after={"status": row.status, "confirmed_by": actor,
        "confirmed_at": row.confirmed_at})
    db.commit()
    return _snapshot(row)


@router.post("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/cancel")
def cancel_contract(comp_code: str, contract_id: int, data: CancelInput, request: Request,
                    db: Session = Depends(get_db)):
    row = _contract(db, comp_code, contract_id)
    if row.status not in {"DRAFT", "CONFIRMED"}:
        _err(409, "현재 상태의 계약은 취소할 수 없습니다.")
    # Downstream financing releases/sales will add explicit FK guards in their phase.
    actor = _actor(request)
    before = {"status": row.status}
    row.status = "CANCELLED"
    row.cancelled_by = row.updated_by = actor
    row.cancelled_at = row.updated_at = datetime.now(timezone.utc)
    record_audit_event(db, comp_code=comp_code, user_id=actor, menu_code="FINANCING_CONTRACT",
        action="CANCEL", entity_type="FINANCING_CONTRACT", entity_id=row.contract_id,
        source="API", before=before, after={"status": row.status, "cancelled_by": actor,
        "cancelled_at": row.cancelled_at}, reason=data.reason)
    db.commit()
    return _snapshot(row)


@router.get("/api/v1/companies/{comp_code}/financing-contracts/{contract_id}/history")
def contract_history(comp_code: str, contract_id: int, db: Session = Depends(get_db)):
    _contract(db, comp_code, contract_id)
    from audit_service import AuditEvent
    rows = db.query(AuditEvent).filter(AuditEvent.comp_code == comp_code).filter(
        ((AuditEvent.entity_type == "FINANCING_CONTRACT") & (AuditEvent.entity_id == str(contract_id))) |
        ((AuditEvent.related_entity_type == "FINANCING_CONTRACT") & (AuditEvent.related_entity_id == str(contract_id)))).order_by(
        AuditEvent.audit_event_id).all()
    return [{"audit_event_id": row.audit_event_id, "action": row.action,
        "entity_type": row.entity_type, "entity_id": row.entity_id, "source": row.source,
        "before_json": row.before_json, "after_json": row.after_json, "reason": row.reason,
        "user_id": row.user_id, "created_at": row.created_at} for row in rows]
