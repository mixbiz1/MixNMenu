from decimal import Decimal

import pytest
from fastapi import HTTPException

from purchase_service import (
    calculate_purchase_line, summarize_purchase, validate_box_qty, validate_client_amounts,
)


def test_purchase_rounds_calculated_won_up():
    result = calculate_purchase_line(Decimal("10.01"), 1234, Decimal("10.00"))
    assert result == {"supply_amount": 12353, "tax_amount": 1236, "total_amount": 13589}


def test_purchase_zero_tax_snapshot_calculation():
    assert calculate_purchase_line("256.37", 7000, 0) == {
        "supply_amount": 1794590, "tax_amount": 0, "total_amount": 1794590,
    }


def test_purchase_rejects_fractional_won_and_excess_weight_precision():
    with pytest.raises(HTTPException):
        calculate_purchase_line("1.001", 1000, 10)
    with pytest.raises(HTTPException):
        calculate_purchase_line("1.00", "1000.5", 10)


def test_purchase_box_is_integer_and_non_negative():
    assert validate_box_qty(12) == 12
    with pytest.raises(HTTPException): validate_box_qty(1.5)
    with pytest.raises(HTTPException): validate_box_qty(-1)


def test_purchase_client_amount_tampering_is_rejected():
    calculated = {"supply_amount": 1000, "tax_amount": 100, "total_amount": 1100}
    validate_client_amounts(calculated, calculated)
    with pytest.raises(HTTPException):
        validate_client_amounts(calculated, {**calculated, "tax_amount": 99})


def test_purchase_summary():
    result = summarize_purchase([
        {"box_qty": 2, "weight": Decimal("10.25"), "supply_amount": 1000, "tax_amount": 100, "total_amount": 1100},
        {"box_qty": 3, "weight": Decimal("20.10"), "supply_amount": 2000, "tax_amount": 0, "total_amount": 2000},
    ])
    assert result == {"total_box_qty": 5, "total_weight": Decimal("30.35"),
                      "total_supply_amount": 3000, "total_tax_amount": 100, "total_amount": 3100}
    with pytest.raises(HTTPException): summarize_purchase([])
