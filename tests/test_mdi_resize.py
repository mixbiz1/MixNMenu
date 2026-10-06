import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from views.mdi_subwindow import ResizableMdiArea, ResizableMdiSubWindow
from app_context import app_context
from views.mxmn_main_window import MixNMainWindow
from views.main_dashboard import MainDashboard
from views.payment_reg import PaymentRegWindow
from views.receipt_reg import ReceiptRegWindow
from views.financing_contract_reg import FinancingContractWindow
import views.financing_contract_reg as financing_contract_view

_APP = QApplication.instance() or QApplication([])


class _SampleMdiWindow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("창 내용 유지 확인"))


def test_mdi_area_wraps_each_widget_with_resizable_subwindow():
    app = _APP
    area = ResizableMdiArea()
    first_widget, second_widget = QWidget(), QWidget()
    first = area.addSubWindow(first_widget)
    second = area.addSubWindow(second_widget)

    assert isinstance(first, ResizableMdiSubWindow)
    assert isinstance(second, ResizableMdiSubWindow)
    assert first.widget() is first_widget
    assert second.widget() is second_widget
    assert len(area.subWindowList()) == 2
    area.close()


def test_mdi_subwindow_resize_edges_and_corners_are_wide_and_draggable():
    app = _APP
    area = ResizableMdiArea()
    child = QWidget()
    sub = area.addSubWindow(child)
    sub.resize(320, 220)
    area.resize(600, 450)
    area.show()
    sub.show()
    app.processEvents()

    margin = sub.RESIZE_MARGIN
    w, h = sub.width(), sub.height()
    assert sub._edges_at(QPoint(margin - 1, h // 2)) == "l"
    assert sub._edges_at(QPoint(w - margin + 1, h // 2)) == "r"
    assert sub._edges_at(QPoint(w // 2, margin - 1)) == "t"
    assert sub._edges_at(QPoint(w // 2, h - margin + 1)) == "b"
    assert sub._edges_at(QPoint(margin - 1, margin - 1)) == "lt"
    assert sub._edges_at(QPoint(w - margin + 1, margin - 1)) == "rt"
    assert sub._edges_at(QPoint(margin - 1, h - margin + 1)) == "lb"
    assert sub._edges_at(QPoint(w - margin + 1, h - margin + 1)) == "rb"

    gestures = (
        (QPoint(4, 100), QPoint(24, 100), -20, 0),       # left
        (QPoint(316, 100), QPoint(336, 100), 20, 0),     # right
        (QPoint(160, 4), QPoint(160, 24), 0, -20),       # top
        (QPoint(160, 216), QPoint(160, 236), 0, 20),     # bottom
        (QPoint(4, 4), QPoint(24, 24), -20, -20),        # top-left
        (QPoint(316, 4), QPoint(336, 24), 20, -20),     # top-right
        (QPoint(4, 216), QPoint(24, 236), -20, 20),     # bottom-left
        (QPoint(316, 216), QPoint(336, 236), 20, 20),   # bottom-right
    )
    for start, finish, width_change, height_change in gestures:
        sub.setGeometry(20, 20, 320, 220)
        app.processEvents()
        old_width, old_height = sub.width(), sub.height()
        QTest.mousePress(sub, Qt.LeftButton, pos=start)
        QTest.mouseMove(sub, finish, delay=10)
        QTest.mouseRelease(sub, Qt.LeftButton, pos=finish)
        app.processEvents()
        assert sub.width() == old_width + width_change
        assert sub.height() == old_height + height_change
    area.close()


def test_receipt_and_payment_can_coexist_and_reopening_activates_existing_window():
    app = _APP
    app_context.set_company("00001", "테스트회사")
    main = MixNMainWindow()
    initial_count = len(main.mdi_area.subWindowList())

    main.open_receipt_reg()
    receipt_sub = next(s for s in main.mdi_area.subWindowList() if type(s.widget()) is ReceiptRegWindow)
    main.open_payment_reg()
    payment_sub = next(s for s in main.mdi_area.subWindowList() if type(s.widget()) is PaymentRegWindow)
    assert len(main.mdi_area.subWindowList()) == initial_count + 2

    receipt_sub.widget().hide()
    main.open_receipt_reg()
    assert len(main.mdi_area.subWindowList()) == initial_count + 2
    assert main.mdi_area.activeSubWindow() is receipt_sub
    assert not receipt_sub.widget().isHidden()
    assert payment_sub in main.mdi_area.subWindowList()
    main.close()


def test_dashboard_close_reopen_reuses_visible_menu_content_repeatedly():
    app = _APP
    main = MixNMainWindow()
    main.show()
    app.processEvents()

    sub = next(s for s in main.mdi_area.subWindowList() if isinstance(s.widget(), MainDashboard))
    dashboard = sub.widget()
    assert dashboard.isVisible()
    assert dashboard.findChildren(QPushButton)

    for _ in range(3):
        sub.close()
        app.processEvents()
        assert sub in main.mdi_area.subWindowList()
        assert sub.widget() is dashboard

        main.open_dashboard()
        app.processEvents()
        sub = next(s for s in main.mdi_area.subWindowList() if isinstance(s.widget(), MainDashboard))
        assert sub.widget() is dashboard
        assert dashboard.isVisible()
        assert dashboard.findChildren(QPushButton)
        assert sum(isinstance(s.widget(), MainDashboard) for s in main.mdi_area.subWindowList()) == 1

    main.close()


def test_delete_on_close_mdi_window_is_removed_and_recreated_with_content():
    app = _APP
    main = MixNMainWindow()
    main._open_single_mdi(_SampleMdiWindow, "테스트 업무창", "테스트")
    sub = next(s for s in main.mdi_area.subWindowList() if isinstance(s.widget(), _SampleMdiWindow))
    old_widget = sub.widget()
    assert old_widget.findChild(QLabel).text() == "창 내용 유지 확인"

    sub.close()
    app.processEvents()
    assert sub not in main.mdi_area.subWindowList()

    main._open_single_mdi(_SampleMdiWindow, "테스트 업무창", "테스트")
    replacement = next(s for s in main.mdi_area.subWindowList() if isinstance(s.widget(), _SampleMdiWindow))
    assert replacement.widget() is not old_widget
    assert replacement.widget().findChild(QLabel).text() == "창 내용 유지 확인"
    assert not replacement.widget().isHidden()
    main.close()


def test_financing_contract_mdi_close_reopen_keeps_single_live_window(monkeypatch):
    class Response:
        def json(self): return []
        def raise_for_status(self): return None

    monkeypatch.setattr(FinancingContractWindow, "_get", lambda self, path, **params: [])
    monkeypatch.setattr(financing_contract_view.httpx, "get", lambda *args, **kwargs: Response())
    main = MixNMainWindow()
    main.open_financing_contract()
    sub = next(s for s in main.mdi_area.subWindowList() if type(s.widget()) is FinancingContractWindow)
    screen = sub.widget()
    assert screen.findChild(QLabel) is not None
    main.open_financing_contract()
    assert sum(type(s.widget()) is FinancingContractWindow for s in main.mdi_area.subWindowList()) == 1
    sub.close()
    _APP.processEvents()
    assert sub not in main.mdi_area.subWindowList()
    main.open_financing_contract()
    replacement = next(s for s in main.mdi_area.subWindowList() if type(s.widget()) is FinancingContractWindow)
    assert replacement.widget() is not screen
    assert sum(type(s.widget()) is FinancingContractWindow for s in main.mdi_area.subWindowList()) == 1
    main.close()
