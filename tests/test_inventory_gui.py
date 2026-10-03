import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock
from datetime import date
from decimal import Decimal

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app_context import app_context
from views.inventory_reg import InventoryRegWindow


def response(data):
    result = Mock()
    result.raise_for_status = Mock()
    result.json.return_value = data
    return result


def test_inventory_screen_requests_period_company_filters_and_grouping(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    requests = []
    failures = []
    criticals = []

    def get(url, **kwargs):
        if url.endswith("/warehouses"):
            return response([{"warehouse_id": 1, "warehouse_name": "냉동창고", "use_yn": True, "company_use_yn": True}])
        requests.append((url, kwargs))
        if failures:
            raise RuntimeError("조회 실패 fixture")
        group = kwargs["params"]["group_by"]
        lot_rows = [
            {"lot_id": 1, "lot_code": "L1", "warehouse_name": "냉동창고", "product_name": "상품",
             "beginning_box_qty": 0, "beginning_weight": "0.00", "inbound_box_qty": 7,
             "inbound_weight": "70.00", "outbound_box_qty": 1, "outbound_weight": "10.00",
             "current_box_qty": 6, "current_weight": "60.00", "average_weight": "10.00",
             "individual_cost": 1000, "inventory_amount": 60000, "bl_no": "BL-1", "history_no": "H-1"},
            {"lot_id": 2, "lot_code": "L2", "warehouse_name": "냉동창고", "product_name": "상품",
             "beginning_box_qty": 1, "beginning_weight": "10.00", "inbound_box_qty": 5,
             "inbound_weight": "50.00", "outbound_box_qty": 2, "outbound_weight": "20.00",
             "current_box_qty": 4, "current_weight": "40.00", "average_weight": "10.00",
             "individual_cost": 1000, "inventory_amount": 40000, "bl_no": "BL-2", "history_no": "H-2"},
        ]
        aggregate = {"warehouse_name": "냉동창고", "product_name": "상품", "source_lot_count": 2,
                     "beginning_box_qty": 1, "beginning_weight": "10.00",
                     "inbound_box_qty": 12, "inbound_weight": "120.00",
                     "outbound_box_qty": 3, "outbound_weight": "30.00",
                     "current_box_qty": 10, "current_weight": "100.00",
                     "average_weight": "10.00", "inventory_amount": 100000}
        rows = lot_rows if group == "LOT" else [aggregate]
        if group == "WAREHOUSE":
            rows = [{key: value for key, value in aggregate.items() if key != "product_name"}]
        elif group == "PRODUCT":
            rows = [{key: value for key, value in aggregate.items() if key != "warehouse_name"}]
        return response({"start_date": "2025-10-01", "end_date": "2026-10-03",
                         "rows": rows,
                         "summary": {"beginning_box_qty": 1, "beginning_weight": "10.00",
                                     "inbound_box_qty": 12, "inbound_weight": "120.00",
                                     "outbound_box_qty": 3, "outbound_weight": "30.00",
                                     "current_box_qty": 10, "current_weight": "100.00",
                                     "inventory_amount": 100000}, "group_by": group})

    monkeypatch.setattr("views.inventory_reg.httpx.get", get)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: criticals.append(args[2]))
    window = InventoryRegWindow()
    assert window.table.rowCount() == 2
    assert window.table.item(0, 2).text() == "L1"
    _, request = requests[-1]
    assert request["params"]["start_date"] == date.today().replace(day=1).isoformat()
    assert request["params"]["end_date"] == date.today().isoformat()
    assert request["params"]["group_by"] == "LOT"
    assert request["params"]["include_zero"] is False
    assert "조회기간 2025-10-01 ~ 2026-10-03" in window.applied_conditions.text()
    assert "현재고 0 제외" in window.applied_conditions.text()
    assert "LOT별 상세" in window.applied_conditions.text()
    window.start_date.setText("2025-10-01")
    window.end_date.setText("2026-10-03")
    window.load_inventory()
    assert requests[-1][1]["params"]["start_date"] == "2025-10-01"
    assert requests[-1][1]["params"]["end_date"] == "2026-10-03"
    window.group_by.setCurrentIndex(1)
    window.storage_type.setCurrentIndex(1)
    window.warehouse.setCurrentIndex(1)
    assert "LOT별 상세" in window.applied_conditions.text()
    assert window.table.rowCount() == 2
    window.load_inventory()
    assert requests[-1][1]["params"]["group_by"] == "WAREHOUSE"
    assert requests[-1][1]["params"]["storage_type"] == "FROZEN"
    assert requests[-1][1]["params"]["warehouse_id"] == 1
    assert "냉동창고" in window.applied_conditions.text()
    assert "냉동" in window.applied_conditions.text()
    assert "창고별" in window.applied_conditions.text()
    assert window.table.rowCount() == 1
    assert window.table.horizontalHeaderItem(0).text() == "창고"
    assert window.table.item(0, 0).text() == "냉동창고"
    assert window.table.item(0, 1).text() == "2"
    assert window.table.item(0, 2).text() == "1"
    assert window.table.item(0, 3).text() == "10.00"
    assert window.table.item(0, 4).text() == "12"
    assert window.table.item(0, 5).text() == "120.00"
    assert window.table.item(0, 6).text() == "3"
    assert window.table.item(0, 7).text() == "30.00"
    assert window.table.item(0, 8).text() == "10"
    assert window.table.item(0, 9).text() == "100.00"
    assert window.table.item(0, 10).text() == "10.00"
    assert window.table.item(0, 11).text() == "100,000"

    window.group_by.setCurrentIndex(2)
    assert "창고별" in window.applied_conditions.text()
    assert window.table.horizontalHeaderItem(0).text() == "창고"
    window.load_inventory()
    assert requests[-1][1]["params"]["group_by"] == "PRODUCT"
    assert "상품별" in window.applied_conditions.text()
    assert window.table.rowCount() == 1
    assert window.table.horizontalHeaderItem(0).text() == "상품명"
    assert window.table.item(0, 0).text() == "상품"
    assert window.table.item(0, 1).text() == "2"

    prior_label = window.applied_conditions.text()
    prior_summary = window.summary.text()
    prior_cells = [window.table.item(0, column).text() for column in range(window.table.columnCount())]
    window.group_by.setCurrentIndex(1)
    failures.append(True)
    window.load_inventory()
    assert requests[-1][1]["params"]["group_by"] == "WAREHOUSE"
    assert window.applied_conditions.text() == prior_label
    assert window.summary.text() == prior_summary
    assert [window.table.item(0, column).text() for column in range(window.table.columnCount())] == prior_cells
    assert window._last_successful_request["group_by"] == "PRODUCT"
    assert criticals == ["조회 실패 fixture"]
    window.close()


def test_lot_history_dialog_keeps_source_identity_visible():
    app = QApplication.instance() or QApplication([])
    from views.inventory_reg import InventoryHistoryDialog
    opened = []
    dialog = InventoryHistoryDialog({"lot_code": "L1", "product_name": "상품"}, [{
        "date": "2026-10-01", "direction": "BEGINNING", "beginning_box_qty": 3,
        "beginning_weight": "30.00", "box_delta": 0, "weight_delta": "0.00",
        "balance_box_qty": 3, "balance_weight": "30.00",
    }, {
        "date": "2026-10-02", "direction": "INBOUND", "transaction_no": "IN-1",
        "account_name": "매입처", "source_type": "PURCHASE", "source_id": 5,
        "source_no": "PU-5", "box_delta": 2, "weight_delta": "20.00",
        "balance_box_qty": 5, "balance_weight": "50.00",
    }, {
        "date": "2026-10-02", "direction": "OUTBOUND", "transaction_no": "OU-1",
        "account_name": "매출처",
        "source_type": "SALE", "source_id": 7, "source_no": "SA-7",
        "box_delta": -3, "weight_delta": "30.00", "balance_box_qty": 2,
        "balance_weight": "20.00",
    }], "2026-10-01", "2026-10-03", lambda kind, source_id: opened.append((kind, source_id)))
    assert dialog.table.item(1, 3).text() == "매입처"
    assert dialog.table.item(1, 13).text() == "매입 PU-5"
    assert dialog.table.item(1, 13).data(Qt.UserRole + 1) == ("PURCHASE", 5)
    assert dialog.table.item(2, 3).text() == "매출처"
    assert dialog.table.item(2, 9).text() == "30.00"
    assert dialog.table.item(2, 13).text() == "매출 SA-7"
    assert dialog.table.item(2, 13).data(Qt.UserRole + 1) == ("SALE", 7)
    assert "전재고 3 Box / 30.00 Kg" in dialog.summary.text()
    assert "현재고 2 Box / 20.00 Kg" in dialog.summary.text()
    dialog.table.selectRow(1)
    dialog.open_selected_source()
    dialog.table.selectRow(2)
    dialog.open_selected_source()
    assert opened == [("PURCHASE", 5), ("SALE", 7)]
    assert "조회기간 2026-10-01 ~ 2026-10-03" in dialog.header.text()
    dialog.close()


@pytest.mark.parametrize("box_value", [2, 2.0, Decimal("2.00"), "2.00"])
@pytest.mark.parametrize("weight_value", [Decimal("30.25"), 30, 30.25, "30.25"])
def test_lot_history_dialog_formats_api_numeric_types(box_value, weight_value):
    app = QApplication.instance() or QApplication([])
    from views.inventory_reg import InventoryHistoryDialog

    dialog = InventoryHistoryDialog({"lot_code": "L-NUM"}, [
        {"date": "2026-10-01", "direction": "BEGINNING",
         "beginning_box_qty": box_value, "beginning_weight": weight_value,
         "box_delta": 0, "weight_delta": "0.00",
         "balance_box_qty": box_value, "balance_weight": weight_value},
        {"date": "2026-10-02", "direction": "INBOUND",
         "box_delta": box_value, "weight_delta": weight_value,
         "balance_box_qty": "4.00", "balance_weight": "60.50"},
        {"date": "2026-10-03", "direction": "OUTBOUND",
         "box_delta": "-2.00", "weight_delta": "-30.25",
         "balance_box_qty": box_value, "balance_weight": weight_value},
    ])

    assert dialog.table.item(0, 4).text() == "2"
    assert dialog.table.item(0, 5).text() == f"{Decimal(str(weight_value)):,.2f}"
    assert dialog.table.item(1, 6).text() == "2"
    assert dialog.table.item(1, 7).text() == f"{Decimal(str(weight_value)):,.2f}"
    assert dialog.table.item(1, 10).text() == "4"
    assert dialog.table.item(1, 11).text() == "60.50"
    assert dialog.table.item(2, 8).text() == "2"
    assert dialog.table.item(2, 9).text() == "30.25"
    assert dialog.table.item(2, 10).text() == "2"
    assert dialog.table.item(2, 11).text() == f"{Decimal(str(weight_value)):,.2f}"
    assert "출고 2 Box / 30.25 Kg" in dialog.summary.text()
    dialog.close()


def test_date_validation_happens_before_request_and_keeps_last_success(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    requests = []
    def get(url, **kwargs):
        if url.endswith("/warehouses"):
            return response([])
        requests.append((url, kwargs))
        return response({"rows": [{"lot_id": 1, "lot_code": "L-DATE", "product_name": "기준재고",
                                    "current_box_qty": 4, "current_weight": "40.00"}], "summary": {
            "beginning_box_qty": 0, "beginning_weight": 0, "inbound_box_qty": 0,
            "inbound_weight": 0, "outbound_box_qty": 0, "outbound_weight": 0,
            "current_box_qty": 0, "current_weight": 0, "inventory_amount": 0,
        }, "start_date": "2026-10-01", "end_date": "2026-10-03"})

    monkeypatch.setattr("views.inventory_reg.httpx.get", get)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    criticals = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: criticals.append(args[2]))
    window = InventoryRegWindow()
    request_count = len(requests)
    prior_label = window.applied_conditions.text()
    prior_summary = window.summary.text()
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == "L-DATE"
    window.start_date.setText("2026-02-30")
    window.load_inventory()
    assert len(requests) == request_count
    assert "실제 날짜" in warnings[-1]
    assert window.applied_conditions.text() == prior_label
    assert window.summary.text() == prior_summary
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == "L-DATE"
    window.start_date.setText("2026-10-04")
    window.end_date.setText("2026-10-03")
    window.load_inventory()
    assert len(requests) == request_count
    assert "늦을 수 없습니다" in warnings[-1]
    assert window.applied_conditions.text() == prior_label
    assert window.summary.text() == prior_summary
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == "L-DATE"
    assert criticals == []
    window.close()


def test_calendar_picker_preserves_calendar_selection():
    app = QApplication.instance() or QApplication([])
    from PySide6.QtCore import QDate
    from views.inventory_reg import CalendarPicker
    picker = CalendarPicker(QDate(2026, 10, 3))
    assert picker.selected_iso_date() == "2026-10-03"
    picker.close()
