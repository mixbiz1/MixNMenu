import time

import permissions


def test_api_route_permission_mapping():
    assert permissions.permission_for_request("GET", "/api/v1/products").menu_code == "MASTER_PRODUCT"
    assert permissions.permission_for_request("POST", "/api/v1/products").action == "create"
    rule = permissions.permission_for_request("DELETE", "/api/v1/companies/00001/lots/3")
    assert (rule.menu_code, rule.action) == ("MASTER_LOT", "delete")
    assert permissions.permission_for_request("PUT", "/api/v1/users/test/access").menu_code == "SYS_PERMISSION"
    assert permissions.permission_for_request("PUT", "/api/v1/users/test/password") is None
    assert permissions.permission_for_request("GET", "/api/v1/warehouses/next-code").menu_code == "MASTER_WAREHOUSE"
    assert permissions.permission_for_request("GET", "/api/v1/company").menu_code == "SYS_COMPANY"
    assert permissions.permission_for_request("GET", "/api/v1/tax-codes").menu_code == "TRADE_COMMON"
    rule = permissions.permission_for_request(
        "PUT", "/api/v1/companies/00001/accounting-periods/2026/9"
    )
    assert (rule.menu_code, rule.action) == ("TRADE_COMMON", "update")
    assert permissions.permission_for_request(
        "GET", "/api/v1/companies/00001/trade-input-options"
    ).menu_code == "TRADE_COMMON"
    assert permissions.permission_for_request(
        "GET", "/api/v1/companies/00001/purchases"
    ).menu_code == "PURCHASE_GENERAL"
    confirm = permissions.permission_for_request(
        "POST", "/api/v1/companies/00001/purchases/1/confirm"
    )
    assert (confirm.menu_code, confirm.action) == ("PURCHASE_GENERAL", "update")
    assert permissions.permission_for_request(
        "GET", "/api/v1/companies/00001/purchase-payable-summary"
    ).menu_code == "PURCHASE_GENERAL"
    assert permissions.permission_for_request(
        "GET", "/api/v1/companies/00001/meatwatch/bl-lookup"
    ).menu_code == "PURCHASE_GENERAL"


def test_company_code_from_path():
    assert permissions.company_code_from_path("/api/v1/companies/00002/warehouses") == "00002"
    assert permissions.company_code_from_path("/api/v1/products") is None


def test_signed_token_round_trip_and_tamper(monkeypatch):
    monkeypatch.setenv("MXMN_AUTH_SECRET", "unit-test-secret")
    token = permissions.issue_token("admin")
    assert permissions.verify_token(token) == "admin"
    assert permissions.verify_token(token + "x") is None


def test_expired_token(monkeypatch):
    monkeypatch.setenv("MXMN_AUTH_SECRET", "unit-test-secret")
    monkeypatch.setattr(time, "time", lambda: 100)
    token = permissions.issue_token("user01", lifetime_seconds=1)
    monkeypatch.setattr(time, "time", lambda: 102)
    assert permissions.verify_token(token) is None


def test_menu_codes_are_unique():
    codes = [row[0] for row in permissions.MENU_DEFINITIONS]
    assert len(codes) == len(set(codes))
