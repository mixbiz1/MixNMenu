"""MXMN 인증 토큰과 메뉴/API 권한의 단일 기준."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass


MENU_DEFINITIONS = (
    ("SYS_COMPANY", "업체등록", "시스템관리", 10),
    ("SYS_USER", "사용자등록", "사용자관리", 20),
    ("SYS_PERMISSION", "사용자별 프로그램 권한", "사용자관리", 30),
    ("MASTER_COMMON", "공통코드입력", "코드관리", 110),
    ("MASTER_GOODS_COMMON", "상품공통코드", "코드관리", 120),
    ("MASTER_PRODUCT", "상품코드입력", "코드관리", 130),
    ("MASTER_EXPENSE", "경비코드입력", "코드관리", 140),
    ("MASTER_ACCOUNT", "거래처입력", "코드관리", 150),
    ("MASTER_WAREHOUSE", "창고입력", "코드관리", 160),
    ("MASTER_LOT", "LOT조회/보정", "코드관리", 170),
    ("OPENING_INVENTORY", "최초재고 등록", "초기자료등록", 180),
    ("OPENING_BALANCE", "거래처 최초잔액 등록", "초기자료등록", 190),
    ("TRADE_COMMON", "거래 공통설정", "거래관리", 200),
    ("PURCHASE_GENERAL", "상품매입등록", "상품입/출고관리", 210),
)

MENU_CODES = {row[0] for row in MENU_DEFINITIONS}
CRUD_ACTIONS = {"read", "create", "update", "delete"}
_EPHEMERAL_SECRET = secrets.token_bytes(32)


@dataclass(frozen=True)
class RoutePermission:
    menu_code: str
    action: str


def action_for_method(method: str) -> str:
    return {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method.upper(), "read")


def permission_for_request(method: str, path: str) -> RoutePermission | None:
    """등록 순서에 영향받지 않는 API→메뉴 권한 매핑."""
    if not path.startswith("/api/v1/"):
        return None
    action = action_for_method(method)
    relative = path.removeprefix("/api/v1/")
    if relative.startswith("auth/"):
        return None
    if relative.startswith("users/") and relative.endswith("/password"):
        return None  # 본인 여부는 endpoint에서 검사
    if relative == "users" or relative.startswith("users/"):
        code = "SYS_PERMISSION" if relative.endswith("/access") else "SYS_USER"
        return RoutePermission(code, action)
    if relative.startswith("code-groups"):
        return RoutePermission("MASTER_COMMON", action)
    if relative.startswith("expense-codes"):
        return RoutePermission("MASTER_EXPENSE", action)
    if relative.startswith("tax-codes"):
        return RoutePermission("TRADE_COMMON", action)
    if relative.startswith("product-categories") or relative.startswith("products"):
        return RoutePermission("MASTER_PRODUCT", action)
    if relative.startswith("accounts"):
        return RoutePermission("MASTER_ACCOUNT", action)
    if relative.startswith("warehouses"):
        return RoutePermission("MASTER_WAREHOUSE", action)
    if relative.startswith("companies/"):
        parts = relative.split("/")
        resource = parts[2] if len(parts) > 2 else ""
        code = {
            "warehouses": "MASTER_WAREHOUSE",
            "lots": "MASTER_LOT",
            "opening-inventories": "OPENING_INVENTORY",
            "opening-balances": "OPENING_BALANCE",
            "accounts": "MASTER_ACCOUNT",
            "accounting-periods": "TRADE_COMMON",
            "trade-input-options": "TRADE_COMMON",
            "purchase-options": "PURCHASE_GENERAL",
            "purchases": "PURCHASE_GENERAL",
            "purchase-payable-summary": "PURCHASE_GENERAL",
            "meatwatch": "PURCHASE_GENERAL",
        }.get(resource, "SYS_COMPANY")
        if resource == "purchases" and len(parts) > 4 and parts[4] in {"confirm", "cancel"}:
            action = "update"
        return RoutePermission(code, action)
    if relative in {"company", "companies"}:
        return RoutePermission("SYS_COMPANY", action)
    return None


def company_code_from_path(path: str) -> str | None:
    prefix = "/api/v1/companies/"
    if not path.startswith(prefix):
        return None
    value = path[len(prefix):].split("/", 1)[0]
    return value or None


def _secret() -> bytes:
    value = os.getenv("MXMN_AUTH_SECRET", "").strip()
    # 미설정 시 예측 불가능한 프로세스 임시 Key를 사용한다. 서버 재시작 뒤에는
    # 재로그인이 필요하지만 알려진 기본문자열로 Token을 위조할 수는 없다.
    return value.encode("utf-8") if value else _EPHEMERAL_SECRET


def issue_token(user_id: str, lifetime_seconds: int = 12 * 60 * 60) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + lifetime_seconds}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_token(token: str) -> str | None:
    try:
        encoded_text, signature_text = token.split(".", 1)
        encoded = encoded_text.encode("ascii")
        supplied = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        expected = hmac.new(_secret(), encoded, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            return None
        raw = base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4))
        payload = json.loads(raw)
        if int(payload["exp"]) < int(time.time()):
            return None
        return str(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
