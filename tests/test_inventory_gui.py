import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

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

    def get(url, **kwargs):
        requests.append((url, kwargs))
        if url.endswith("/warehouses"):
            return response([{"warehouse_id": 1, "warehouse_name": "냉동창고", "use_yn": True, "company_use_yn": True}])
        return response({"rows": [{"lot_id": 1, "lot_code": "L1", "product_name": "상품",
                                   "current_box_qty": 8, "current_weight": "80.00"}],
                         "summary": {"beginning_box_qty": 0, "beginning_weight": "0.00",
                                     "inbound_box_qty": 10, "inbound_weight": "100.00",
                                     "outbound_box_qty": 2, "outbound_weight": "20.00",
                                     "current_box_qty": 8, "current_weight": "80.00",
                                     "inventory_amount": 80000}, "group_by": "LOT"})

    monkeypatch.setattr("views.inventory_reg.httpx.get", get)
    window = InventoryRegWindow()
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == "L1"
    _, request = requests[-1]
    assert request["params"]["start_date"] <= request["params"]["end_date"]
    assert request["params"]["group_by"] == "LOT"
    assert request["params"]["include_zero"] is False
    window.group_by.setCurrentIndex(1)
    window.storage_type.setCurrentIndex(1)
    window.load_inventory()
    assert requests[-1][1]["params"]["group_by"] == "WAREHOUSE"
    assert requests[-1][1]["params"]["storage_type"] == "FROZEN"
    window.close()


def test_lot_history_dialog_keeps_source_identity_visible():
    app = QApplication.instance() or QApplication([])
    from views.inventory_reg import InventoryHistoryDialog
    dialog = InventoryHistoryDialog({"lot_code": "L1", "product_name": "상품"}, [{
        "date": "2026-10-02", "direction": "OUTBOUND", "transaction_no": "OU-1",
        "source_type": "SALE", "source_id": 7, "source_no": "SA-7",
        "box_delta": -1, "weight_delta": "10.00", "balance_box_qty": 2,
        "balance_weight": "20.00",
    }])
    assert dialog.table.item(0, 3).text() == "SA-7 [SALE:7]"
    assert dialog.table.item(0, 4).text() == "-1"
    dialog.close()
