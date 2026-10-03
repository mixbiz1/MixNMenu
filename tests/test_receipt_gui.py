import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

from PySide6.QtWidgets import QApplication, QMessageBox

from app_context import app_context
from views.receipt_reg import ReceiptRegWindow


def test_new_receipt_starts_blank_and_repeated_save_creates_new_transactions(monkeypatch):
    application = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    window = ReceiptRegWindow()
    window.account.addItem("거래처", 1)
    window.load_data = lambda: None
    window.load_summary = lambda: None

    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "account_transaction_id": 17,
        "transaction_no": "RC-20261003-0001",
    }
    post = Mock(return_value=response)
    put = Mock(return_value=response)
    monkeypatch.setattr("views.receipt_reg.httpx.post", post)
    monkeypatch.setattr("views.receipt_reg.httpx.put", put)
    monkeypatch.setattr("views.receipt_reg.QMessageBox.question", lambda *_: QMessageBox.Yes)
    monkeypatch.setattr("views.receipt_reg.QMessageBox.information", lambda *_: None)

    assert window.amount.value() == 0
    assert window.amount.specialValueText() == " "
    assert window.amount.text().strip() == ""
    assert window.current_id is None
    assert not window.btn_delete.isEnabled()

    window.amount.setValue(50000)
    window.save_data()
    assert post.call_count == 1
    assert put.call_count == 0
    assert window.current_id is None
    assert window.amount.value() == 0
    assert window.amount.text().strip() == ""
    assert not window.btn_delete.isEnabled()
    assert window.btn_save.text().startswith("저장")

    # A stale currentRow after clearSelection must not reload the previous receipt.
    window.rows = [{
        "account_transaction_id": 17, "receipt_date": "2026-10-03",
        "account_id": 1, "amount": 999999, "memo": "old",
    }]
    window.table.setRowCount(1)
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtCore import Qt
    cell = QTableWidgetItem("2026-10-03")
    cell.setData(Qt.UserRole, 17)
    window.table.setItem(0, 0, cell)
    window.table.selectRow(0)
    window._enter_new_mode(keep_context=True)
    assert window.current_id is None
    assert window.amount.value() == 0
    assert window.amount.text().strip() == ""


    window.amount.setValue(100000)
    window.save_data()
    assert post.call_count == 2
    assert put.call_count == 0
    assert window.current_id is None
    assert window.amount.value() == 0
    window.close()



def test_amount_live_grouping_and_load_does_not_repeat_summary(monkeypatch):
    application = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")

    class CountingReceiptWindow(ReceiptRegWindow):
        def __init__(self):
            self.summary_calls = 0
            super().__init__()

        def load_summary(self):
            self.summary_calls += 1

    class Response:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    accounts = [
        {"account_id": i, "account_name": f"거래처{i}", "sales_yn": True}
        for i in range(1, 31)
    ]

    def fake_get(url, **kwargs):
        if url.endswith("/accounts"):
            return Response(accounts)
        if url.endswith("/receipts"):
            return Response([])
        raise AssertionError(url)

    monkeypatch.setattr("views.receipt_reg.httpx.get", fake_get)
    window = CountingReceiptWindow()
    window.load_data()
    # 거래처 30건을 채워도 요약조회는 마지막에 한 번만 실행되어야 한다.
    assert window.summary_calls == 1

    editor = window.amount.lineEdit()
    editor.setText("1234567 원")
    editor.setCursorPosition(len("1234567"))
    window._format_amount_input(editor.text())
    assert window.amount.value() == 1234567
    assert "1,234,567" in window.amount.text()
    window.close()
