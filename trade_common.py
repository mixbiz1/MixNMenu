"""후속 매입·입고·매출 전표가 공유하는 불변 업무규칙."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text

DOCUMENT_PREFIXES = {
    "PURCHASE": "PU",
    "PURCHASE_INBOUND": "PI",
    "IMPORT_INBOUND": "II",
    "SALE": "SA",
    "OUTBOUND": "OU",
    "RECEIPT": "RC",
    "PAYMENT": "PM",
}

DOCUMENT_TRANSITIONS = {
    "DRAFT": {"CONFIRMED"},
    "CONFIRMED": {"CANCELLED"},
    "CANCELLED": set(),
}


def allocate_document_no(db, comp_code: str, document_type: str, document_date: date) -> str:
    """현재 DB transaction 안에서 SQL Server 잠금을 잡아 중복 없이 발번한다."""
    prefix = DOCUMENT_PREFIXES.get(document_type)
    if not prefix:
        raise ValueError(f"지원하지 않는 전표종류입니다: {document_type}")
    row = db.execute(text("""
        SET NOCOUNT ON;
        DECLARE @result TABLE (last_number INT);
        UPDATE dbo.tb_document_sequence WITH (UPDLOCK, HOLDLOCK)
           SET last_number = last_number + 1,
               updated_at = SYSDATETIMEOFFSET()
        OUTPUT inserted.last_number INTO @result
         WHERE comp_code = :comp_code
           AND document_type = :document_type
           AND sequence_date = :sequence_date;
        IF @@ROWCOUNT = 0
        BEGIN
            INSERT INTO dbo.tb_document_sequence
                (comp_code, document_type, sequence_date, last_number, updated_at)
            OUTPUT inserted.last_number INTO @result
            VALUES (:comp_code, :document_type, :sequence_date, 1, SYSDATETIMEOFFSET());
        END;
        SELECT TOP 1 last_number FROM @result;
    """), {
        "comp_code": comp_code,
        "document_type": document_type,
        "sequence_date": document_date,
    }).scalar_one()
    return f"{prefix}-{document_date:%Y%m%d}-{int(row):04d}"


def ensure_period_open(db, comp_code: str, document_date: date) -> None:
    import models

    period = db.query(models.AccountingPeriod).filter(
        models.AccountingPeriod.comp_code == comp_code,
        models.AccountingPeriod.period_year == document_date.year,
        models.AccountingPeriod.period_month == document_date.month,
    ).first()
    # 미등록 기간은 OPEN으로 취급한다. 첫 마감 시 명시적 기간행이 생성된다.
    if period and period.period_status != "OPEN":
        raise HTTPException(status_code=409, detail="마감된 회계기간의 거래는 변경할 수 없습니다.")


def ensure_draft(document) -> None:
    if document.document_status != "DRAFT":
        raise HTTPException(status_code=409, detail="확정 또는 취소된 전표는 원문을 변경할 수 없습니다.")


def apply_status_transition(document, target_status: str, actor_user_id: str) -> None:
    current = str(document.document_status).upper()
    target = target_status.upper()
    if target not in DOCUMENT_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=409, detail=f"허용되지 않는 전표상태 전환입니다: {current} → {target}")
    now = datetime.now(timezone.utc)
    document.document_status = target
    document.updated_by = actor_user_id
    document.updated_at = now
    if target == "CONFIRMED":
        document.confirmed_by = actor_user_id
        document.confirmed_at = now
    elif target == "CANCELLED":
        document.cancelled_by = actor_user_id
        document.cancelled_at = now


def tax_snapshot(tax_code, transaction_date: date) -> dict:
    if not tax_code.use_yn or tax_code.valid_from > transaction_date or (
        tax_code.valid_to and tax_code.valid_to < transaction_date
    ):
        raise HTTPException(status_code=400, detail="거래일에 유효하지 않은 세금코드입니다.")
    return {
        "tax_code_snapshot": tax_code.tax_code,
        "tax_name_snapshot": tax_code.tax_name,
        "tax_rate_snapshot": Decimal(tax_code.tax_rate),
    }


def validate_leaf_input_expense(db, expense_id: int):
    import models

    expense = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_id == expense_id,
        models.ExpenseCode.use_yn == True,
    ).first()
    if not expense or expense.node_type != "INPUT":
        raise HTTPException(status_code=400, detail="사용 중인 실제입력 경비코드만 선택할 수 있습니다.")
    has_child = db.query(models.ExpenseCode.expense_id).filter(
        models.ExpenseCode.parent_expense_id == expense_id,
        models.ExpenseCode.use_yn == True,
    ).first()
    if has_child:
        raise HTTPException(status_code=400, detail="하위항목이 없는 최하위 실제입력 경비코드만 선택할 수 있습니다.")
    return expense
