from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from trade_common import allocate_document_no, apply_status_transition, ensure_draft, tax_snapshot


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _SequenceDb:
    def __init__(self, value):
        self.value = value
        self.params = None

    def execute(self, statement, params):
        self.params = params
        assert "UPDLOCK, HOLDLOCK" in str(statement)
        return _ScalarResult(self.value)


def test_document_number_format_and_scope_parameters():
    db = _SequenceDb(12)
    result = allocate_document_no(db, "00001", "PURCHASE", date(2026, 9, 18))
    assert result == "PU-20260918-0012"
    assert db.params == {
        "comp_code": "00001", "document_type": "PURCHASE",
        "sequence_date": date(2026, 9, 18),
    }


def test_only_draft_is_editable_and_status_is_one_way():
    document = SimpleNamespace(
        document_status="DRAFT", updated_by=None, updated_at=None,
        confirmed_by=None, confirmed_at=None, cancelled_by=None, cancelled_at=None,
    )
    ensure_draft(document)
    apply_status_transition(document, "CONFIRMED", "admin")
    assert document.document_status == "CONFIRMED"
    assert document.confirmed_by == "admin"
    with pytest.raises(HTTPException):
        ensure_draft(document)
    with pytest.raises(HTTPException):
        apply_status_transition(document, "DRAFT", "admin")
    apply_status_transition(document, "CANCELLED", "admin")
    assert document.cancelled_by == "admin"


def test_tax_snapshot_copies_transaction_time_values():
    code = SimpleNamespace(
        tax_code="VAT10", tax_name="과세 10%", tax_rate=Decimal("10.00"),
        valid_from=date(2000, 1, 1), valid_to=None, use_yn=True,
    )
    assert tax_snapshot(code, date(2026, 9, 18)) == {
        "tax_code_snapshot": "VAT10",
        "tax_name_snapshot": "과세 10%",
        "tax_rate_snapshot": Decimal("10.00"),
    }


def test_tax_snapshot_rejects_expired_code():
    code = SimpleNamespace(
        tax_code="OLD", tax_name="과거세율", tax_rate=Decimal("5.00"),
        valid_from=date(2000, 1, 1), valid_to=date(2020, 12, 31), use_yn=True,
    )
    with pytest.raises(HTTPException):
        tax_snapshot(code, date(2026, 9, 18))
