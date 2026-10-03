import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox
from PySide6.QtCore import Qt
from unittest.mock import Mock

from app_context import app_context
from views.payment_reg import PaymentRegWindow


def test_payment_new_mode_hides_zero_and_uses_payment_terms():
    application = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    window = PaymentRegWindow()
    assert window.amount.value() == 0
    assert window.amount.lineEdit().text().strip() == ""
    assert not any(label.text() == "선지급" for label in window.findChildren(QLabel))
    assert [window.table.horizontalHeaderItem(i).text() for i in range(5)] == ["지급일", "거래처", "지급액", "적요", "지급번호"]
    window.amount.setValue(1234567)
    window._format_amount_input(window.amount.lineEdit().text())
    assert "1,234,567" in window.amount.text()
    window._enter_new_mode(keep_context=True)
    assert window.amount.lineEdit().text().strip() == ""
    assert window.amount.suffix() == ""

    # 부호를 포함해 입력해도 음수 조정과 천 단위 구분이 유지된다.
    editor = window.amount.lineEdit()
    editor.setText("-1000000")
    editor.setCursorPosition(len("-1000000"))
    window._format_amount_input(editor.text())
    assert window.amount.value() == -1000000
    assert "-1,000,000" in window.amount.text()

    window.rows = [{
        "account_transaction_id": 7,
        "payment_date": "2026-10-03",
        "account_id": 1,
        "amount": 2500000,
        "memo": "기존 지급",
    }]
    window.table.setRowCount(1)
    cell = QTableWidgetItem("2026-10-03")
    cell.setData(Qt.UserRole, 7)
    window.table.setItem(0, 0, cell)
    window.table.selectRow(0)
    window.on_selected()
    assert window.current_id == 7
    assert window.amount.value() == 2500000
    assert "2,500,000" in window.amount.text()
    window.close()


def test_payment_save_and_delete_return_to_a_completely_blank_amount(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    window = PaymentRegWindow()
    window.account.addItem("거래처", 1)
    window.load_data = lambda: None
    window.load_summary = lambda: None

    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"account_transaction_id": 8, "transaction_no": "PY-20261003-0001"}
    post = Mock(return_value=response)
    monkeypatch.setattr("views.payment_reg.httpx.post", post)
    monkeypatch.setattr("views.payment_reg.QMessageBox.question", lambda *_: QMessageBox.Yes)
    monkeypatch.setattr("views.payment_reg.QMessageBox.information", lambda *_: None)

    window.amount.setValue(1500)
    window.save_data()
    assert post.call_count == 1
    assert window.current_id is None
    assert window.amount.value() == 0
    assert window.amount.text().strip() == ""
    assert window.amount.suffix() == ""

    response.json.return_value = {"message": "삭제되었습니다."}
    delete = Mock(return_value=response)
    monkeypatch.setattr("views.payment_reg.httpx.delete", delete)
    monkeypatch.setattr("views.payment_reg.QMessageBox.warning", lambda *_args, **_kwargs: QMessageBox.Yes)
    window.current_id = 8
    window.delete_data()
    assert delete.call_count == 1
    assert window.current_id is None
    assert window.amount.text().strip() == ""
    assert window.amount.suffix() == ""
    window.close()
