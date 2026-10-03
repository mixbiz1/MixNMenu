import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app_context import app_context
from views.payment_reg import PaymentRegWindow


def test_payment_new_mode_hides_zero_and_uses_payment_terms():
    application = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    window = PaymentRegWindow()
    assert window.amount.value() == 0
    assert window.amount.lineEdit().text().strip() == ""
    assert [window.table.horizontalHeaderItem(i).text() for i in range(5)] == ["지급일", "거래처", "지급액", "적요", "지급번호"]
    window.amount.setValue(1234567)
    window._format_amount_input(window.amount.lineEdit().text())
    assert "1,234,567" in window.amount.text()
    window._enter_new_mode(keep_context=True)
    assert window.amount.lineEdit().text().strip() == ""
    window.close()
