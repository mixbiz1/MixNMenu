import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMdiArea, QMdiSubWindow,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QStyleFactory
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPalette, QColor

# 프로젝트 루트 경로 추가
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 모듈 임포트
try:
    from views.company_reg import CompanyRegWidget
except ImportError:
    try:
        from company_reg import CompanyRegWidget
    except ImportError:
        CompanyRegWidget = None

try:
    from views.main_dashboard import MainDashboard
except ImportError:
    try:
        from main_dashboard import MainDashboard
    except ImportError:
        MainDashboard = None


class MixNMainWindow(QMainWindow):
    def __init__(self, user_name=""):
        super().__init__()
        
        self.setObjectName("MixNMainWindow")
        title = "MixNMenu - ERP System"
        if user_name:
            title += f" - [{user_name}] 접속 중"
        self.setWindowTitle(title)
        self.resize(1249, 678)
        
        # 라이트 모드 강제 적용
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.set_light_palette()

        # 중앙 MDI 영역 생성
        self.mdi_area = QMdiArea()
        self.mdi_area.setObjectName("mdi_area")
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.mdi_area)

        # 서브 윈도우 인스턴스 관리용 변수
        self.sub_dashboard = None
        self.sub_company = None

        # 메뉴바 및 상태바 구축
        self.init_menu_bar()
        self.init_status_bar()
        self.apply_stylesheet()

        # 로그인 후 메인화면 진입 시 단축메뉴(대시보드) 자동 열기
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

        # 메뉴바 추가
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
        """단축메뉴(대시보드) 서브 창 오픈"""
        if MainDashboard is None:
            QMessageBox.warning(self, "경고", "main_dashboard.py 모듈을 찾을 수 없습니다.")
            return

        # 열려 있으면 활성화
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
            print(">>> [성공] 단축메뉴 대시보드 오픈")
        except Exception as e:
            print(f"[Error] 단축메뉴 열기 실패: {e}")

    def open_company_reg(self):
        """1.업체등록(자회사/당사 정보) 서브 창 오픈"""
        if CompanyRegWidget is None:
            QMessageBox.warning(self, "경고", "company_reg.py 모듈을 찾을 수 없습니다.")
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
            print(">>> [성공] 업체등록 창 오픈")
        except Exception as e:
            print(f"[Error] 업체등록 열기 실패: {e}")


def load_main_window(user_name=""):
    """외부(로그인 창 등)에서 호출하는 진입점 함수"""
    return MixNMainWindow(user_name=user_name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    main_win = MixNMainWindow()
    main_win.show()
    
    sys.exit(app.exec())