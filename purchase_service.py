"""일반 매입의 계산·입력 불변규칙. API와 자동검증이 함께 사용한다."""

from decimal import Decimal, ROUND_CEILING

from fastapi import HTTPException


def ceil_won(value) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_CEILING))


def calculate_purchase_line(weight, unit_price, tax_rate) -> dict:
    weight_value = Decimal(str(weight)).quantize(Decimal("0.01"))
    price_value = Decimal(str(unit_price))
    rate_value = Decimal(str(tax_rate))
    if weight_value <= 0 or price_value < 0 or rate_value < 0:
        raise HTTPException(status_code=400, detail="중량·단가·세율을 확인하세요.")
    if weight_value != Decimal(str(weight)):
        raise HTTPException(status_code=400, detail="중량은 소수점 둘째 자리까지만 입력할 수 있습니다.")
    if price_value != price_value.to_integral_value():
        raise HTTPException(status_code=400, detail="단가는 원 단위 정수로 입력하세요.")
    supply = ceil_won(weight_value * price_value)
    tax = ceil_won(Decimal(supply) * rate_value / Decimal("100"))
    return {"supply_amount": supply, "tax_amount": tax, "total_amount": supply + tax}


def validate_box_qty(value) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise HTTPException(status_code=400, detail="BOX는 0 이상의 정수로 입력하세요.")
    return int(value)


def validate_client_amounts(calculated: dict, supplied: dict) -> None:
    labels = {
        "supply_amount": "공급가액", "tax_amount": "세액", "total_amount": "합계금액",
    }
    for key, label in labels.items():
        value = supplied.get(key)
        if value is not None and int(value) != calculated[key]:
            raise HTTPException(status_code=400, detail=f"{label}이 서버 계산값과 일치하지 않습니다.")


def summarize_purchase(lines: list[dict]) -> dict:
    if not lines:
        raise HTTPException(status_code=400, detail="매입 Detail을 1건 이상 입력하세요.")
    return {
        "total_box_qty": sum(line["box_qty"] for line in lines),
        "total_weight": sum((Decimal(str(line["weight"])) for line in lines), Decimal("0.00")),
        "total_supply_amount": sum(line["supply_amount"] for line in lines),
        "total_tax_amount": sum(line["tax_amount"] for line in lines),
        "total_amount": sum(line["total_amount"] for line in lines),
    }
