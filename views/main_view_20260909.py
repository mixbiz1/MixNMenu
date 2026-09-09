import os
import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMdiArea, QMdiSubWindow, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from PySide6.QtUiTools import QUiLoader

from views.main_dashboard import MainDashboard

try:
    from views.company_reg import CompanyRegView
except ImportError:
    CompanyRegView = None


class MainWindowController:
    """mxmn_main_window.ui 기반 MDI 메인 윈도우 제어 클래스"""
    def __init__(self, user_name=""):
        self.user_name = user_name
        self.window = None
        self.mdi_area = None
        
        self.sub_dashboard = None
        self.sub_company = None
        
        self.init_ui()
        self.bind_events()

    def init_ui(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_path = os.path.join(base_dir, "ui", "mxmn_main_window.ui")

        loader = QUiLoader()
        self.window = loader.load(ui_path)

        if not self.window:
            print(f"[Error] UI 파일 로드 실패: {ui_path}")
            return

        self.window.setWindowTitle(f"MixNMenu - [{self.user_name}] 님 접속 중")

        # centralwidget에 안전하게 QMdiArea 배치 (기존 UI 파괴 방지)
        central_widget = self.window.findChild(QWidget, "centralwidget")
        if central_widget:
            layout = central_widget.layout()
            if not layout:
                layout = QVBoxLayout(central_widget)
                layout.setContentsMargins(0, 0, 0, 0)
            
            self.mdi_area = QMdiArea()
            self.mdi_area.setViewMode(QMdiArea.SubWindowView)
            self.mdi_area.setStyleSheet("background-color: #2D2D2D;")
            layout.addWidget(self.mdi_area)

        # 초기 대시보드 열기
        self.open_dashboard()

    def bind_events(self):
        """개별 QAction에 직접 트리거 연결"""
        if not self.window:
            return

        # 1. 업체등록
        act_company = self.window.findChild(QAction, "action_company_reg")
        if act_company:
            act_company.setMenuRole(QAction.NoRole)
            act_company.triggered.connect(self.open_company_reg)

        # 2. 단축메뉴
        act_shortcut = self.window.findChild(QAction, "action_shortcut")
        if act_shortcut:
            act_shortcut.setMenuRole(QAction.NoRole)
            act_shortcut.triggered.connect(self.open_dashboard)

        # 3. 종료
        act_exit = self.window.findChild(QAction, "action_exit")
        if act_exit:
            act_exit.setMenuRole(QAction.NoRole)
            act_exit.triggered.connect(self.window.close)

    def open_dashboard(self):
        print(">>> open_dashboard() 실행")
        if not self.mdi_area:
            return

        try:
            if self.sub_dashboard and self.sub_dashboard.isVisible():
                self.mdi_area.setActiveSubWindow(self.sub_dashboard)
                return

            dashboard_widget = MainDashboard()
            self.sub_dashboard = QMdiSubWindow()
            self.sub_dashboard.setWidget(dashboard_widget)
            self.sub_dashboard.setWindowTitle("바탕화면 - 단축메뉴")
            
            self.sub_dashboard.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.sub_dashboard.destroyed.connect(lambda: setattr(self, 'sub_dashboard', None))
            
            self.mdi_area.addSubWindow(self.sub_dashboard)
            self.sub_dashboard.resize(1050, 600)
            self.sub_dashboard.show()
        except Exception as e:
            print(f"[Error] 단축메뉴 열기 실패: {e}")

    def open_company_reg(self):
        print(">>> open_company_reg() 실행")
        if not self.mdi_area:
            return

        if CompanyRegView:
            try:
                if self.sub_company and self.sub_company.isVisible():
                    self.mdi_area.setActiveSubWindow(self.sub_company)
                    return

                company_widget = CompanyRegView()
                self.sub_company = QMdiSubWindow()
                self.sub_company.setWidget(company_widget)
                self.sub_company.setWindowTitle("업체등록")
                
                self.sub_company.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                self.sub_company.destroyed.connect(lambda: setattr(self, 'sub_company', None))
                
                self.mdi_area.addSubWindow(self.sub_company)
                self.sub_company.resize(900, 550)
                self.sub_company.show()
            except Exception as e:
                print(f"[Error] 업체등록 열기 실패: {e}")
        else:
            QMessageBox.information(
                self.window, 
                "안내", 
                "1.업체등록 모듈(CompanyRegView)을 가져올 수 없거나 연동 파일 준비 중입니다."
            )


def load_main_window(user_name: str = ""):
    controller = MainWindowController(user_name)
    return controller.window