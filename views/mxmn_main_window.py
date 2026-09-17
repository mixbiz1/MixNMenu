import sys
import os
import traceback
import httpx
import time

from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QMainWindow,
    QWidget,
    QMdiArea,
    QMdiSubWindow,
    QMenuBar,
    QMenu,
    QStatusBar,
    QMessageBox,
    QStyleFactory,
    QLabel,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
)

from PySide6.QtCore import Qt, QObject, QEvent, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QPalette, QColor

# MXMN 공통 실행 Context
from app_context import app_context

# 거래처입력 화면
try:
    from views.account_reg import AccountRegWindow
except ImportError:
    from account_reg import AccountRegWindow

# 공통코드관리 화면
try:
    from views.common_code_reg import CommonCodeWindow
except ImportError:
    from common_code_reg import CommonCodeWindow

# 상품공통코드관리 화면
try:
    from views.goods_common_code_reg import GoodsCommonCodeWindow
except ImportError:
    from goods_common_code_reg import GoodsCommonCodeWindow

# 상품입력 화면
try:
    from views.product_reg import ProductRegWindow
except ImportError:
    from product_reg import ProductRegWindow

try:
    from views.expense_code_reg import ExpenseCodeWindow
except ImportError:
    from expense_code_reg import ExpenseCodeWindow

# 창고입력 화면
try:
    from views.warehouse_reg import WarehouseRegWindow
except ImportError:
    from warehouse_reg import WarehouseRegWindow

# LOT입력 화면
try:
    from views.lot_reg import LotRegWindow
except ImportError:
    from lot_reg import LotRegWindow

try:
    from views.opening_inventory_reg import OpeningInventoryRegWindow
    from views.opening_balance_reg import OpeningBalanceRegWindow
except ImportError:
    from opening_inventory_reg import OpeningInventoryRegWindow
    from opening_balance_reg import OpeningBalanceRegWindow

try:
    from views.password_change import PasswordChangeDialog
except ImportError:
    from password_change import PasswordChangeDialog


# ============================================================
# 1. 프로젝트 루트 및 views 폴더 경로 설정
# ============================================================

current_dir = os.path.dirname(
    os.path.abspath(__file__)
)

base_dir = os.path.dirname(
    current_dir
)

for p in [
    base_dir,
    current_dir,
]:
    if p not in sys.path:
        sys.path.insert(
            0,
            p,
        )


# ============================================================
# 2. company_reg 모듈 유연 임포트
# ============================================================

CompanyRegWidget = None

company_reg_error_msg = ""

try:

    import views.company_reg as company_reg_mod

except ImportError:

    try:

        import company_reg as company_reg_mod

    except Exception as e:

        company_reg_mod = None

        company_reg_error_msg = (
            f"company_reg.py 파일 임포트 실패:\n"
            f"{e}\n\n"
            f"[상세 추적]:\n"
            f"{traceback.format_exc()}"
        )


if company_reg_mod:

    # --------------------------------------------------------
    # 클래스 탐색
    # --------------------------------------------------------

    for target_name in [
        "CompanyRegWidget",
        "CompanyRegView",
        "CompanyReg",
        "CompanyRegistration",
    ]:

        if hasattr(
            company_reg_mod,
            target_name,
        ):

            CompanyRegWidget = getattr(
                company_reg_mod,
                target_name,
            )

            break

    # 이름으로 찾지 못한 경우 QWidget 파생 클래스 탐색

    if CompanyRegWidget is None:

        for attr_name in dir(
            company_reg_mod
        ):

            attr = getattr(
                company_reg_mod,
                attr_name,
            )

            if (
                isinstance(attr, type)
                and issubclass(attr, QWidget)
                and attr is not QWidget
            ):

                CompanyRegWidget = attr

                break

    if CompanyRegWidget is None:

        company_reg_error_msg = (
            "company_reg.py 내에서 "
            "유효한 QWidget 클래스를 찾지 못했습니다."
        )


# ============================================================
# 3. main_dashboard 모듈 임포트
# ============================================================

MainDashboard = None

dashboard_error_msg = ""

try:

    from views.main_dashboard import MainDashboard

except Exception:

    try:

        from main_dashboard import MainDashboard

    except Exception as e:

        dashboard_error_msg = (
            f"main_dashboard.py 로드 실패:\n"
            f"{e}\n\n"
            f"[상세 추적]:\n"
            f"{traceback.format_exc()}"
        )


# ============================================================
# 4. 업무회사 선택/변경 Dialog
# ============================================================

class CommandEventFilter(QObject):
    """전체 버튼의 명령 접수 표시와 빠른 중복 클릭을 공통 차단한다."""

    def __init__(self, parent=None, interval_ms=700):
        super().__init__(parent)
        self.interval_seconds = interval_ms / 1000
        self.last_command_at = {}

    @staticmethod
    def _show_command_feedback(button):
        button.setDown(True)
        button.setProperty("mxmnCommandActive", True)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

        def clear_feedback():
            try:
                button.setDown(False)
                button.setProperty("mxmnCommandActive", False)
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
            except RuntimeError:
                pass

        QTimer.singleShot(250, clear_feedback)

    def eventFilter(self, obj, event):
        if not isinstance(obj, QAbstractButton):
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonDblClick:
            event.accept()
            return True

        is_mouse_command = event.type() == QEvent.MouseButtonPress
        is_key_command = (
            event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)
        )
        if not (is_mouse_command or is_key_command):
            return super().eventFilter(obj, event)
        if is_key_command and event.isAutoRepeat():
            return True

        now = time.monotonic()
        key = id(obj)
        if now - self.last_command_at.get(key, 0) < self.interval_seconds:
            event.accept()
            return True
        self.last_command_at[key] = now
        self._show_command_feedback(obj)
        return super().eventFilter(obj, event)

class CompanySwitchDialog(QDialog):
    """FastAPI의 회사 목록을 조회하여 현재 업무회사를 선택한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MXMN - 업무회사 변경")
        self.setFixedSize(430, 190)
        self.selected_company = None
        self.setStyleSheet("QDialog { background-color: #ffffff; color: #000000; }")
        self._init_ui()
        self._load_companies()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        title = QLabel("변경할 업무회사를 선택하십시오.")
        layout.addWidget(title)

        self.company_combo = QComboBox()
        self.company_combo.setMinimumHeight(32)
        self.company_combo.setStyleSheet("""
            QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #808080; padding: 4px 8px; }
            QComboBox QAbstractItemView { background-color: #ffffff; color: #000000; selection-background-color: #0d47a1; selection-color: #ffffff; }
        """)
        layout.addWidget(self.company_combo)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("변    경")
        cancel_btn = QPushButton("취    소")
        ok_btn.clicked.connect(self._accept_company)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

    def _load_companies(self):
        try:
            response = httpx.get("http://127.0.0.1:8000/api/v1/companies", timeout=10.0)
            if response.status_code != 200:
                raise RuntimeError(f"회사 목록 조회 실패 (HTTP {response.status_code})")

            self.company_combo.clear()
            current_index = 0
            for company in response.json():
                code = company.get("comp_code")
                name = company.get("comp_name")
                if not code:
                    continue
                self.company_combo.addItem(f"{code}  {name}", {"comp_code": code, "comp_name": name})
                if code == app_context.company_code:
                    current_index = self.company_combo.count() - 1

            if self.company_combo.count() == 0:
                raise RuntimeError("등록된 회사가 없습니다.")
            self.company_combo.setCurrentIndex(current_index)
        except Exception as e:
            QMessageBox.critical(self, "회사 조회 오류", str(e))
            self.reject()

    def _accept_company(self):
        company = self.company_combo.currentData()
        if not company:
            QMessageBox.warning(self, "알림", "회사를 선택해 주세요.")
            return
        self.selected_company = company
        self.accept()


# ============================================================
# 5. MXMN 메인 윈도우
# ============================================================

class MixNMainWindow(QMainWindow):

    def __init__(self, user_name=""):

        super().__init__()

        self._command_event_filter = CommandEventFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._command_event_filter)

        self.setObjectName(
            "MixNMainWindow"
        )

        # ----------------------------------------------------
        # Window Title
        # ----------------------------------------------------

        title = "MixNMenu - ERP System"

        # Context 사용을 우선한다.
        if app_context.has_user:

            title += (
                f" - [{app_context.user_name}] 접속 중"
            )

        elif user_name:

            title += (
                f" - [{user_name}] 접속 중"
            )

        self.setWindowTitle(
            title
        )

        self.resize(
            1249,
            678,
        )

        # ----------------------------------------------------
        # 라이트 모드
        # ----------------------------------------------------

        self.setAttribute(
            Qt.WA_StyledBackground,
            True,
        )

        self.set_light_palette()

        # ----------------------------------------------------
        # 중앙 MDI
        # ----------------------------------------------------

        self.mdi_area = QMdiArea()

        self.mdi_area.setObjectName(
            "mdi_area"
        )

        self.mdi_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.mdi_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )

        self.setCentralWidget(
            self.mdi_area
        )

        # ----------------------------------------------------
        # 메뉴 / 상태바
        # ----------------------------------------------------

        self.init_menu_bar()

        self.init_status_bar()

        self.apply_stylesheet()
        self.refresh_window_title()

        # ----------------------------------------------------
        # 대시보드 자동 오픈
        # ----------------------------------------------------

        self.open_dashboard()

        # 초기 상태
        self.set_work_status(
            "시스템 준비 완료"
        )


    # ========================================================
    # Light Palette
    # ========================================================

    def set_light_palette(self):

        palette = QPalette()

        palette.setColor(
            QPalette.Window,
            QColor("#eef1f5"),
        )

        palette.setColor(
            QPalette.WindowText,
            QColor("#222222"),
        )

        palette.setColor(
            QPalette.Base,
            QColor("#ffffff"),
        )

        palette.setColor(
            QPalette.AlternateBase,
            QColor("#f7fafe"),
        )

        palette.setColor(
            QPalette.Text,
            QColor("#111111"),
        )

        palette.setColor(
            QPalette.Button,
            QColor("#ffffff"),
        )

        palette.setColor(
            QPalette.ButtonText,
            QColor("#222222"),
        )

        palette.setColor(
            QPalette.Highlight,
            QColor("#1a5ac7"),
        )

        palette.setColor(
            QPalette.HighlightedText,
            QColor("#ffffff"),
        )

        self.setPalette(
            palette
        )


    # ========================================================
    # Status Bar
    # ========================================================

    def init_status_bar(self):

        self.status_bar = QStatusBar(
            self
        )

        self.setStatusBar(
            self.status_bar
        )

        # ----------------------------------------------------
        # 왼쪽 : 현재 회사 + 사용자
        # ----------------------------------------------------

        self.session_label = QLabel()

        self.session_label.setObjectName(
            "session_label"
        )

        self.session_label.setText(
            app_context.session_display
        )

        self.session_label.setMinimumWidth(
            430
        )

        # ----------------------------------------------------
        # 오른쪽 : 현재 작업 상태
        # ----------------------------------------------------

        self.work_status_label = QLabel(
            "시스템 준비 완료"
        )

        self.work_status_label.setObjectName(
            "work_status_label"
        )

        self.work_status_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )

        # 상태바에 배치
        self.status_bar.addWidget(
            self.session_label,
            1,
        )

        self.status_bar.addPermanentWidget(
            self.work_status_label,
        )


    def refresh_session_status(self):
        """
        AppContext의 현재 회사/사용자 정보를
        상태표시줄에 다시 반영한다.
        """

        if hasattr(
            self,
            "session_label",
        ):

            self.session_label.setText(
                app_context.session_display
            )


    def set_work_status(self, message):
        """
        현재 회사/사용자 정보는 유지하면서
        오른쪽 작업 상태 메시지만 변경한다.
        """

        if hasattr(
            self,
            "work_status_label",
        ):

            self.work_status_label.setText(
                message
            )


    # ========================================================
    # Menu Bar
    # ========================================================

    def init_menu_bar(self):

        self.menuBar = QMenuBar(
            self
        )

        self.setMenuBar(
            self.menuBar
        )

        # ----------------------------------------------------
        # 1. 시스템관리
        # ----------------------------------------------------

        self.menu1 = QMenu(
            "1.시스템관리",
            self,
        )

        self.action_company_reg = QAction(
            "1.업체등록",
            self,
        )

        self.action_company_reg.triggered.connect(
            self.open_company_reg
        )

        self.menu1.addAction(
            self.action_company_reg
        )

        self.action_company_switch = QAction(
            "2.업무회사 변경",
            self,
        )
        self.action_company_switch.triggered.connect(
            self.change_company
        )
        self.menu1.addAction(
            self.action_company_switch
        )

        self.action2 = QAction(
            "3.비밀번호변경",
            self,
        )
        self.action2.triggered.connect(self.open_password_change)

        self.action3 = QAction(
            "4.프린터설정",
            self,
        )

        self.menu1.addAction(
            self.action2
        )

        self.menu1.addAction(
            self.action3
        )

        self.menu1.addSeparator()

        self.action4 = QAction(
            "5.우편번호조회",
            self,
        )
        self.action4.triggered.connect(self.open_postcode_lookup)

        self.action_shortcut = QAction(
            "6.단축메뉴",
            self,
        )

        self.action_shortcut.triggered.connect(
            self.open_dashboard
        )

        self.menu1.addAction(
            self.action4
        )

        self.menu1.addAction(
            self.action_shortcut
        )

        self.action7 = QAction(
            "7.환경설정",
            self,
        )

        self.menu1.addAction(
            self.action7
        )

        self.menu1.addSeparator()

        self.action_exit = QAction(
            "8.종료",
            self,
        )

        self.action_exit.triggered.connect(
            self.close
        )

        self.menu1.addAction(
            self.action_exit
        )

        # ----------------------------------------------------
        # 2. 코드관리
        # ----------------------------------------------------

        self.menu2 = QMenu(
            "2.코드관리",
            self,
        )

        self.menu1_2 = QMenu(
            "1.사용자관리",
            self,
        )

        self.menu1_2.addAction(
            QAction(
                "1.사용자등록",
                self,
            )
        )

        self.menu1_2.addAction(
            QAction(
                "2.사용자별 프로그램 권한",
                self,
            )
        )

        self.menu1_2.addAction(
            QAction(
                "3.전자계산서사용자등록",
                self,
            )
        )

        self.menu1_2.addAction(
            QAction(
                "4.사용자 접속현황",
                self,
            )
        )

        self.menu2.addMenu(
            self.menu1_2
        )

        common_code_action = QAction(
            "2.공통코드입력",
            self,
        )
        common_code_action.triggered.connect(
            self.open_common_code
        )
        self.menu2.addAction(
            common_code_action
        )

        goods_common_code_action = QAction(
            "3.상품공통코드",
            self,
        )
        goods_common_code_action.triggered.connect(
            self.open_goods_common_code
        )
        self.menu2.addAction(
            goods_common_code_action
        )

        product_action = QAction(
            "4.상품코드입력",
            self,
        )
        product_action.triggered.connect(
            self.open_product_reg
        )
        self.menu2.addAction(
            product_action
        )

        expense_code_action = QAction(
            "5.경비코드입력",
            self,
        )
        expense_code_action.triggered.connect(
            self.open_expense_code
        )
        self.menu2.addAction(
            expense_code_action
        )

        account_action = QAction(
            "6.거래처입력",
            self,
        )
        account_action.triggered.connect(
            self.open_account_reg
        )
        self.menu2.addAction(
            account_action
        )

        warehouse_action = QAction(
            "7.창고입력",
            self,
        )
        warehouse_action.triggered.connect(
            self.open_warehouse_reg
        )
        self.menu2.addAction(
            warehouse_action
        )

        lot_action = QAction(
            "8.LOT조회/보정",
            self,
        )
        lot_action.triggered.connect(
            self.open_lot_reg
        )
        self.menu2.addAction(
            lot_action
        )

        opening_menu = QMenu("9.초기자료등록", self)
        opening_inventory_action = QAction("1.최초재고 등록", self)
        opening_inventory_action.triggered.connect(self.open_opening_inventory_reg)
        opening_menu.addAction(opening_inventory_action)
        opening_balance_action = QAction("2.거래처 최초잔액 등록", self)
        opening_balance_action.triggered.connect(self.open_opening_balance_reg)
        opening_menu.addAction(opening_balance_action)
        self.menu2.addMenu(opening_menu)

        # ----------------------------------------------------
        # 기타 업무 메뉴
        # ----------------------------------------------------

        self.menu3 = QMenu(
            "3.수입관리",
            self,
        )

        self.menu4 = QMenu(
            "4.상품입/출고관리",
            self,
        )

        self.menu5 = QMenu(
            "5.입금/출금관리",
            self,
        )

        self.menu6 = QMenu(
            "6.월재고마감관리",
            self,
        )

        self.menu7 = QMenu(
            "7.조회/출력",
            self,
        )

        self.menu8 = QMenu(
            "8.계산서관리",
            self,
        )

        self.menu9 = QMenu(
            "9.파이낸싱/계약판매",
            self,
        )

        # ----------------------------------------------------
        # 메뉴바 배치
        # ----------------------------------------------------

        for menu in [
            self.menu1,
            self.menu2,
            self.menu3,
            self.menu4,
            self.menu5,
            self.menu6,
            self.menu7,
            self.menu8,
            self.menu9,
        ]:

            self.menuBar.addMenu(
                menu
            )


    # ========================================================
    # Stylesheet
    # ========================================================

    def apply_stylesheet(self):

        self.setStyleSheet(
            """
            QMainWindow#MixNMainWindow {
                background-color: #eef1f5;
            }

            QMdiArea#mdi_area {
                background-color: #d2d9e1;
                border: none;
            }

            QMdiSubWindow {
                background-color: #eef1f5;
                border: 1px solid #b8c2cc;
            }

            QMenuBar {
                background-color: #ffffff;
                color: #222222;
                border-bottom: 1px solid #d0d7de;
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 9.5pt;
                padding: 2px;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 6px 10px;
                border-radius: 4px;
            }

            QMenuBar::item:selected {
                background-color: #eef1f5;
                color: #1a5ac7;
                font-weight: bold;
            }

            QMenu {
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #c0c7d0;
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 9pt;
                padding: 4px 0px;
            }

            QMenu::item {
                padding: 6px 24px 6px 12px;
            }

            QMenu::item:selected {
                background-color: #1a5ac7;
                color: #ffffff;
            }

            QStatusBar {
                background-color: #ffffff;
                color: #555555;
                border-top: 1px solid #d0d7de;
                font-size: 8.5pt;
            }

            QLabel#session_label {
                color: #1a3f75;
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 8.5pt;
                font-weight: bold;
                padding-left: 6px;
            }

            QLabel#work_status_label {
                color: #555555;
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 8.5pt;
                padding-right: 8px;
            }
            """
        )


    # ========================================================
    # Current Company / Session
    # ========================================================

    def refresh_window_title(self):
        company_text = (
            f"{app_context.company_code} {app_context.company_name}"
            if app_context.has_company else "회사 미선택"
        )
        user_text = app_context.user_name if app_context.has_user else "미로그인"
        self.setWindowTitle(f"MXMN - [{company_text}] - [{user_text}]")

    def change_company(self):
        """재로그인 없이 현재 업무회사를 안전하게 변경한다."""
        dialog = CompanySwitchDialog(self)
        if dialog.exec() != QDialog.Accepted or not dialog.selected_company:
            self.set_work_status("업무회사 변경이 취소되었습니다.")
            return

        company = dialog.selected_company
        new_code = company["comp_code"]
        new_name = company["comp_name"]

        if new_code == app_context.company_code:
            self.set_work_status("현재 사용 중인 회사입니다.")
            return

        # 공통 Dirty-State 규약을 구현한 업무창이 있으면 먼저 확인한다.
        dirty_windows = []
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            checker = getattr(widget, "is_dirty", None)
            try:
                if callable(checker) and checker():
                    dirty_windows.append(sub.windowTitle())
                elif checker is True:
                    dirty_windows.append(sub.windowTitle())
            except Exception:
                pass

        if dirty_windows:
            QMessageBox.warning(
                self,
                "회사 변경 불가",
                "저장되지 않은 변경사항이 있는 화면이 있습니다.\n\n"
                + "\n".join(f"- {name}" for name in dirty_windows)
                + "\n\n현재 단계에서는 해당 화면에서 먼저 저장하거나 취소한 뒤 회사 변경을 다시 실행해 주세요.",
            )
            self.set_work_status("미저장 작업 때문에 회사 변경이 중단되었습니다.")
            return

        open_windows = self.mdi_area.subWindowList()
        if open_windows:
            answer = QMessageBox.question(
                self,
                "업무회사 변경 확인",
                f"현재 회사: {app_context.company_code} {app_context.company_name}\n"
                f"변경 회사: {new_code} {new_name}\n\n"
                "회사 변경 시 현재 열려 있는 업무창은 모두 닫힙니다.\n"
                "계속하시겠습니까?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer != QMessageBox.Yes:
                self.set_work_status("업무회사 변경이 취소되었습니다.")
                return

        self.mdi_area.closeAllSubWindows()
        if self.mdi_area.subWindowList():
            QMessageBox.warning(
                self,
                "회사 변경 중단",
                "닫히지 않은 업무창이 있어 회사 변경을 중단했습니다.",
            )
            return

        app_context.set_company(new_code, new_name)
        self.refresh_session_status()
        self.refresh_window_title()
        self.open_dashboard()
        self.set_work_status(f"업무회사가 {new_code} {new_name}(으)로 변경되었습니다.")


    # ========================================================
    # Dashboard
    # ========================================================

    def open_password_change(self):
        """현재 로그인 사용자의 비밀번호 변경 창을 연다."""
        dialog = PasswordChangeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.set_work_status("비밀번호가 변경되었습니다.")

    def open_postcode_lookup(self):
        """행정안전부 도로명주소 안내시스템의 우편번호 조회를 연다."""
        url = QUrl("https://www.juso.go.kr/openIndexPage.do")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "우편번호 조회",
                "우편번호 조회 화면을 열 수 없습니다. 기본 웹 브라우저 설정을 확인해 주세요.",
            )
            return
        self.set_work_status("우편번호 조회 화면을 기본 웹 브라우저에서 열었습니다.")

    def _bring_subwindow_to_front(self, sub_window):
        """가장 최근 요청한 MDI 창을 다른 작업창보다 앞으로 올린다."""
        sub_window.show()
        self.mdi_area.setActiveSubWindow(sub_window)
        sub_window.raise_()
        sub_window.activateWindow()
        widget = sub_window.widget()
        if widget is not None:
            widget.raise_()
            widget.setFocus(Qt.OtherFocusReason)
        QApplication.processEvents()

    def open_dashboard(self):
        """단축메뉴(대시보드) 오픈"""

        if MainDashboard is None:

            if dashboard_error_msg:

                QMessageBox.warning(
                    self,
                    "대시보드 로드 경고",
                    dashboard_error_msg,
                )

            return

        for sub in self.mdi_area.subWindowList():

            if isinstance(
                sub.widget(),
                MainDashboard,
            ):

                self.mdi_area.setActiveSubWindow(
                    sub
                )
                self._bring_subwindow_to_front(sub)

                self.set_work_status(
                    "단축메뉴가 활성화되었습니다."
                )

                return

        try:

            dashboard_widget = MainDashboard(
                main_window=self
            )

            sub_window = self.mdi_area.addSubWindow(
                dashboard_widget
            )

            sub_window.setWindowTitle(
                "바탕화면 - 단축메뉴"
            )

            sub_window.resize(
                1050,
                600,
            )

            sub_window.show()
            self._bring_subwindow_to_front(sub_window)

            self.set_work_status(
                "단축메뉴가 열렸습니다."
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "단축메뉴 실행 에러",
                (
                    "단축메뉴 생성 중 오류가 발생했습니다:\n"
                    f"{e}\n\n"
                    f"{traceback.format_exc()}"
                ),
            )


    # ========================================================
    # Company Registration
    # ========================================================

    def open_company_reg(self):
        """1.업체등록(자회사/당사 정보) 오픈"""

        if CompanyRegWidget is None:

            detail_msg = (
                company_reg_error_msg
                if company_reg_error_msg
                else
                "company_reg.py 내 위젯 클래스가 정의되지 않았습니다."
            )

            QMessageBox.critical(
                self,
                "모듈 로드 에러",
                (
                    "company_reg.py 로딩 실패:\n\n"
                    f"{detail_msg}"
                ),
            )

            return

        for sub in self.mdi_area.subWindowList():

            if isinstance(
                sub.widget(),
                CompanyRegWidget,
            ):

                self.mdi_area.setActiveSubWindow(
                    sub
                )
                self._bring_subwindow_to_front(sub)

                self.set_work_status(
                    "1.업체등록 창이 활성화되었습니다."
                )

                return

        try:

            company_widget = CompanyRegWidget()

            sub_window = self.mdi_area.addSubWindow(
                company_widget
            )

            sub_window.setWindowTitle(
                "1.업체등록"
            )

            sub_window.resize(
                company_widget.sizeHint()
            )

            company_widget.show()

            sub_window.show()
            self._bring_subwindow_to_front(sub_window)

            # 회사/사용자 정보는 그대로 유지하고
            # 작업 메시지만 변경한다.
            self.set_work_status(
                "1.업체등록 창이 열렸습니다."
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "업체등록 실행 에러",
                (
                    "업체등록 위젯 오픈 중 오류 발생:\n"
                    f"{e}\n\n"
                    f"{traceback.format_exc()}"
                ),
            )


    # ========================================================
    # Dashboard shortcut connection
    # ========================================================

    def connect_account_shortcut(self):
        """바탕화면 <<코드관리>> '거래처입력' 버튼을 동일 화면에 연결한다."""
        connected = 0

        for button in self.findChildren(QAbstractButton):
            if button.text().strip() == "거래처입력":
                try:
                    button.clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass

                button.clicked.connect(self.open_account_reg)
                connected += 1

        return connected

    # ========================================================
    # Common Code
    # ========================================================

    def open_common_code(self):
        """공통코드관리 화면을 MDI에 1개만 연다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, CommonCodeWindow):
                    self.mdi_area.setActiveSubWindow(sub)
                    sub.showNormal()
                    sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("2.코드관리 창이 활성화되었습니다.")
                    return

            code_widget = CommonCodeWindow()
            sub_window = self.mdi_area.addSubWindow(code_widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle("공통코드관리")

            self._common_code_subwindow = sub_window
            self._common_code_widget = code_widget

            def clear_common_code_refs(*args):
                self._common_code_subwindow = None
                self._common_code_widget = None

            sub_window.destroyed.connect(clear_common_code_refs)
            code_widget.show()
            sub_window.show()
            self.mdi_area.setActiveSubWindow(sub_window)
            sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status("2.코드관리 창이 열렸습니다.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "공통코드관리 실행 오류",
                f"공통코드관리 화면을 열 수 없습니다.\n\n{e}",
            )


    # ========================================================
    # Goods Common Code
    # ========================================================

    def open_goods_common_code(self):
        """상품공통코드관리 화면을 MDI에 1개만 연다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, GoodsCommonCodeWindow):
                    self.mdi_area.setActiveSubWindow(sub)
                    sub.showNormal()
                    sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("상품공통코드관리 창이 활성화되었습니다.")
                    return

            code_widget = GoodsCommonCodeWindow()
            sub_window = self.mdi_area.addSubWindow(code_widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle("상품공통코드관리")

            self._goods_common_code_subwindow = sub_window
            self._goods_common_code_widget = code_widget

            def clear_goods_common_code_refs(*args):
                self._goods_common_code_subwindow = None
                self._goods_common_code_widget = None

            sub_window.destroyed.connect(clear_goods_common_code_refs)
            code_widget.show()
            sub_window.show()
            self.mdi_area.setActiveSubWindow(sub_window)
            sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status("상품공통코드관리 창이 열렸습니다.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "상품공통코드관리 실행 오류",
                f"상품공통코드관리 화면을 열 수 없습니다.\n\n{e}",
            )


    # ========================================================
    # Product Registration
    # ========================================================

    def open_product_reg(self):
        """계층형 상품분류 및 상품 Master 화면을 MDI에 1개만 연다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, ProductRegWindow):
                    sub.showNormal(); sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("상품입력 창이 활성화되었습니다.")
                    return
            widget = ProductRegWindow()
            sub_window = self.mdi_area.addSubWindow(widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle("상품입력")
            widget.show(); sub_window.show(); sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status("상품입력 창이 열렸습니다.")
        except Exception as e:
            QMessageBox.critical(self, "상품입력 실행 오류", f"상품입력 화면을 열 수 없습니다.\n\n{e}")


    # ========================================================
    # Expense Code Registration
    # ========================================================

    def open_expense_code(self):
        """계층형 경비코드 Master 화면을 MDI에 1개만 연다."""
        self._open_single_mdi(
            ExpenseCodeWindow,
            "경비코드입력",
            "5.경비코드입력",
        )


    # ========================================================
    # Warehouse Registration
    # ========================================================

    def open_warehouse_reg(self):
        """창고 Master 화면을 MDI에 1개만 연다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, WarehouseRegWindow):
                    self.mdi_area.setActiveSubWindow(sub)
                    widget.show()
                    sub.showNormal(); sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("7.창고입력 창이 활성화되었습니다.")
                    return
            widget = WarehouseRegWindow()
            sub_window = self.mdi_area.addSubWindow(widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle(
                f"창고입력 - {app_context.company_name or app_context.company_code}"
            )
            widget.show(); sub_window.show(); sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status("7.창고입력 창이 열렸습니다.")
        except Exception as e:
            QMessageBox.critical(self, "창고입력 실행 오류", f"창고입력 화면을 열 수 없습니다.\n\n{e}")


    # ========================================================
    # LOT Registration
    # ========================================================

    def open_lot_reg(self):
        """LOT Master 화면을 MDI에 1개만 연다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, LotRegWindow):
                    self.mdi_area.setActiveSubWindow(sub)
                    widget.show(); sub.showNormal(); sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("8.LOT조회/보정 창이 활성화되었습니다.")
                    return
            widget = LotRegWindow()
            sub_window = self.mdi_area.addSubWindow(widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle(
                f"LOT조회/보정 - {app_context.company_name or app_context.company_code}"
            )
            widget.show(); sub_window.show(); sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status("8.LOT조회/보정 창이 열렸습니다.")
        except Exception as e:
            QMessageBox.critical(self, "LOT조회/보정 실행 오류", f"LOT조회/보정 화면을 열 수 없습니다.\n\n{e}")


    def open_opening_inventory_reg(self):
        """최초재고 등록 화면을 MDI에 1개만 연다."""
        self._open_single_mdi(
            OpeningInventoryRegWindow,
            "최초재고 등록",
            "초기자료등록 → 최초재고 등록",
        )


    def open_opening_balance_reg(self):
        """거래처 최초잔액 등록 화면을 MDI에 1개만 연다."""
        self._open_single_mdi(
            OpeningBalanceRegWindow,
            "거래처 최초잔액 등록",
            "초기자료등록 → 거래처 최초잔액 등록",
        )


    def _open_single_mdi(self, widget_class, title, status_text):
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, widget_class):
                    self.mdi_area.setActiveSubWindow(sub)
                    widget.show(); sub.showNormal(); sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status(f"{status_text} 창이 활성화되었습니다.")
                    return
            widget = widget_class()
            sub_window = self.mdi_area.addSubWindow(widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle(
                f"{title} - {app_context.company_name or app_context.company_code}"
            )
            widget.show(); sub_window.show(); sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)
            self.set_work_status(f"{status_text} 창이 열렸습니다.")
        except Exception as e:
            QMessageBox.critical(self, f"{title} 실행 오류", f"{title} 화면을 열 수 없습니다.\n\n{e}")


    # ========================================================
    # Account Registration
    # ========================================================

    def open_account_reg(self):
        """거래처 등록/수정 화면을 MDI에 1개만 열고, 닫힌 후에는 정상 재생성한다."""
        try:
            for sub in self.mdi_area.subWindowList():
                widget = sub.widget()
                if widget is not None and isinstance(widget, AccountRegWindow):
                    self.mdi_area.setActiveSubWindow(sub)
                    sub.showNormal()
                    sub.showMaximized()
                    self._bring_subwindow_to_front(sub)
                    self.set_work_status("6.거래처입력 창이 활성화되었습니다.")
                    return

            # AccountRegWindow 실제 생성자는 parent=None만 받는다.
            account_widget = AccountRegWindow()

            sub_window = self.mdi_area.addSubWindow(account_widget)
            sub_window.setAttribute(Qt.WA_DeleteOnClose, True)
            sub_window.setWindowTitle(
                f"거래처입력 - {app_context.company_name or app_context.company_code}"
            )

            # 닫기 후 삭제되기 전까지 명시적 참조 유지
            self._account_subwindow = sub_window
            self._account_widget = account_widget

            def clear_account_refs(*args):
                self._account_subwindow = None
                self._account_widget = None

            sub_window.destroyed.connect(clear_account_refs)

            account_widget.show()
            sub_window.show()
            self.mdi_area.setActiveSubWindow(sub_window)
            sub_window.showMaximized()
            self._bring_subwindow_to_front(sub_window)

            self.set_work_status("6.거래처입력 창이 열렸습니다.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "거래처입력 실행 오류",
                f"거래처입력 화면을 열 수 없습니다.\n\n{e}",
            )
