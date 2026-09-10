import sys
import os
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMdiArea, QMdiSubWindow,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QStyleFactory
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPalette, QColor

# 1. 프로젝트 루트 및 views 폴더 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(current_dir)

for p in [base_dir, current_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# 2. company_reg 모듈 유연 임포트
CompanyRegWidget = None
company_reg_error_msg = ""

try:
    import views.company_reg as company_reg_mod
except ImportError:
    try:
        import company_reg as company_reg_mod
    except Exception as e:
        company_reg_mod = None
        company_reg_error_msg = f"company_reg.py 파일 임포트 실패:\n{e}\n\n[상세 추적]:\n{traceback.format_exc()}"

if company_reg_mod:
    # 클래스 탐색
    for target_name in ["CompanyRegWidget", "CompanyRegView", "CompanyReg", "CompanyRegistration"]:
        if hasattr(company_reg_mod, target_name):
            CompanyRegWidget = getattr(company_reg_mod, target_name)
            break
    
    if CompanyRegWidget is None:
        for attr_name in dir(company_reg_mod):
            attr = getattr(company_reg_mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, QWidget) and attr is not QWidget:
                CompanyRegWidget = attr
                break

    if CompanyRegWidget is None:
        company_reg_error_msg = "company_reg.py 내에서 유효한 QWidget 클래스를 찾지 못했습니다."

# 3. main_dashboard 모듈 임포트
MainDashboard = None
dashboard_error_msg = ""
try:
    from views.main_dashboard import MainDashboard
except Exception:
    try:
        from main_dashboard import MainDashboard
    except Exception as e:
        dashboard_error_msg = f"main_dashboard.py 로드 실패:\n{e}\n\n[상세 추적]:\n{traceback.format_exc()}"


class MixNMainWindow(QMainWindow):
    def __init__(self, user_name=""):
        super().__init__()
        
        self.setObjectName("MixNMainWindow")
        title = "MixNMenu - ERP System"
        if user_name:
            title += f" - [{user_name}] 접속 중"
        self.setWindowTitle(title)
        self.resize(1249, 678)
        
        # 라이트 모드 테마 적용
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.set_light_palette()

        # 중앙 MDI 영역 생성
        self.mdi_area = QMdiArea()
        self.mdi_area.setObjectName("mdi_area")
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.mdi_area)

        # 메뉴바 및 상태바 구성
        self.init_menu_bar()
        self.init_status_bar()
        self.apply_stylesheet()

        # 대시보드 자동 오픈
        self.open_dashboard()

    def set_light_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#eef1f5"))
        palette.setColor(QPalette.WindowText, QColor("#222222"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f7fafe"))
        palette.setColor(QPalette.Text, QColor("#111111"))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor("#222222"))
        palette.setColor(QPalette.Highlight, QColor("#1a5ac7"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

    def init_status_bar(self):
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("시스템 준비 완료")

    def init_menu_bar(self):
        self.menuBar = QMenuBar(self)
        self.setMenuBar(self.menuBar)

        # 1. 시스템관리
        self.menu1 = QMenu("1.시스템관리", self)
        
        self.action_company_reg = QAction("1.업체등록", self)
        self.action_company_reg.triggered.connect(self.open_company_reg)
        self.menu1.addAction(self.action_company_reg)

        self.action2 = QAction("2.비밀번호변경", self)
        self.action3 = QAction("3.프린터설정", self)
        self.menu1.addAction(self.action2)
        self.menu1.addAction(self.action3)
        self.menu1.addSeparator()

        self.action4 = QAction("4.우편번호조회", self)
        self.action_shortcut = QAction("5.단축메뉴", self)
        self.action_shortcut.triggered.connect(self.open_dashboard)
        self.menu1.addAction(self.action4)
        self.menu1.addAction(self.action_shortcut)

        self.action6 = QAction("6.원격지원", self)
        self.action7 = QAction("7.환경설정", self)
        self.action8 = QAction("8.미트통신 열기", self)
        self.menu1.addAction(self.action6)
        self.menu1.addAction(self.action7)
        self.menu1.addAction(self.action8)
        self.menu1.addSeparator()

        self.action_exit = QAction("9.종료", self)
        self.action_exit.triggered.connect(self.close)
        self.menu1.addAction(self.action_exit)

        # 2. 코드관리
        self.menu2 = QMenu("2.코드관리", self)
        self.menu1_2 = QMenu("1.사용자관리", self)
        self.menu1_2.addAction(QAction("1.사용자등록", self))
        self.menu1_2.addAction(QAction("2.사용자별 프로그램 권한", self))
        self.menu1_2.addAction(QAction("3.전자계산서사용자등록", self))
        self.menu1_2.addAction(QAction("4.사용자 접속현황", self))
        self.menu2.addMenu(self.menu1_2)

        self.menu2.addAction(QAction("2.코드관리", self))
        self.menu2.addAction(QAction("3.거래처 기초잔액 입력", self))
        self.menu2.addAction(QAction("4.더존iU연동관리", self))

        # 기타 메뉴
        self.menu3 = QMenu("3.수입관리", self)
        self.menu4 = QMenu("4.상품입/출고관리", self)
        self.menu5 = QMenu("5.입금/출금관리", self)
        self.menu6 = QMenu("6.월재고마감관리", self)
        self.menu7 = QMenu("7.조회/출력", self)
        self.menu8 = QMenu("8.계산서관리", self)
        self.menu9 = QMenu("9.파이낸싱/계약판매", self)

        # 메뉴바 배치
        for m in [self.menu1, self.menu2, self.menu3, self.menu4, self.menu5, self.menu6, self.menu7, self.menu8, self.menu9]:
            self.menuBar.addMenu(m)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow#MixNMainWindow { background-color: #eef1f5; }
            QMdiArea#mdi_area { background-color: #d2d9e1; border: none; }
            QMdiSubWindow { background-color: #eef1f5; border: 1px solid #b8c2cc; }
            QMenuBar {
                background-color: #ffffff; color: #222222;
                border-bottom: 1px solid #d0d7de;
                font-family: 'Malgun Gothic', '맑은 고딕'; font-size: 9.5pt; padding: 2px;
            }
            QMenuBar::item { background-color: transparent; padding: 6px 10px; border-radius: 4px; }
            QMenuBar::item:selected { background-color: #eef1f5; color: #1a5ac7; font-weight: bold; }
            QMenu {
                background-color: #ffffff; color: #222222; border: 1px solid #c0c7d0;
                font-family: 'Malgun Gothic', '맑은 고딕'; font-size: 9pt; padding: 4px 0px;
            }
            QMenu::item { padding: 6px 24px 6px 12px; }
            QMenu::item:selected { background-color: #1a5ac7; color: #ffffff; }
            QStatusBar { background-color: #ffffff; color: #555555; border-top: 1px solid #d0d7de; font-size: 8.5pt; }
        """)

    def open_dashboard(self):
        """단축메뉴(대시보드) 오픈"""
        if MainDashboard is None:
            if dashboard_error_msg:
                QMessageBox.warning(self, "대시보드 로드 경고", dashboard_error_msg)
            return

        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), MainDashboard):
                self.mdi_area.setActiveSubWindow(sub)
                return

        try:
            dashboard_widget = MainDashboard(main_window=self)
            sub_window = self.mdi_area.addSubWindow(dashboard_widget)
            sub_window.setWindowTitle("바탕화면 - 단축메뉴")
            sub_window.resize(1050, 600)
            sub_window.show()
        except Exception as e:
            QMessageBox.critical(self, "단축메뉴 실행 에러", f"단축메뉴 생성 중 오류가 발생했습니다:\n{e}\n\n{traceback.format_exc()}")

    def open_company_reg(self):
        """1.업체등록(자회사/당사 정보) 오픈"""
        if CompanyRegWidget is None:
            detail_msg = company_reg_error_msg if company_reg_error_msg else "company_reg.py 내 위젯 클래스가 정의되지 않았습니다."
            QMessageBox.critical(self, "모듈 로드 에러", f"company_reg.py 로딩 실패:\n\n{detail_msg}")
            return

        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), CompanyRegWidget):
                self.mdi_area.setActiveSubWindow(sub)
                return

        try:
            company_widget = CompanyRegWidget()
            sub_window = self.mdi_area.addSubWindow(company_widget)
            sub_window.setWindowTitle("1.업체등록")
            sub_window.resize(company_widget.sizeHint())
            company_widget.show()
            sub_window.show()
            self.statusBar.showMessage("1.업체등록 창이 열렸습니다.")
        except Exception as e:
            QMessageBox.critical(self, "업체등록 실행 에러", f"업체등록 위젯 오픈 중 오류 발생:\n{e}\n\n{traceback.format_exc()}")


def load_main_window(user_name=""):
    return MixNMainWindow(user_name=user_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    main_win = MixNMainWindow()
    main_win.show()
    
    sys.exit(app.exec())