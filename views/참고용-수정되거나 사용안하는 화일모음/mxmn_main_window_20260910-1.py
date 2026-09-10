import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMdiArea, QMdiSubWindow,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QStyleFactory
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPalette, QColor

# 이전에 제작한 업체등록 위젯 모듈 임포트
try:
    from company_reg import CompanyRegWidget
except ImportError:
    CompanyRegWidget = None


class MixNMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setObjectName("MixNMainWindow")
        self.setWindowTitle("MixNMenu - ERP System")
        self.resize(1249, 678)
        
        # QSS 배경 적용 설정 및 라이트 모드 강제
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.set_light_palette()

        # 중앙 MDI 영역 생성
        self.mdi_area = QMdiArea()
        self.mdi_area.setObjectName("mdi_area")
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.mdi_area)

        # 메뉴바 및 상태바 구축
        self.init_menu_bar()
        self.init_status_bar()
        
        # 스타일시트 적용
        self.apply_stylesheet()

    def set_light_palette(self):
        """OS 다크모드의 영향을 받지 않도록 메인 창 라이트 팔레트 강제 적용"""
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

        # ----------------------------------------------------
        # 1. 시스템관리
        # ----------------------------------------------------
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
        self.action6 = QAction("6.원격지원", self)
        self.action7 = QAction("7.환경설정", self)
        self.action8 = QAction("8.미트통신 열기", self)
        self.menu1.addAction(self.action4)
        self.menu1.addAction(self.action_shortcut)
        self.menu1.addAction(self.action6)
        self.menu1.addAction(self.action7)
        self.menu1.addAction(self.action8)
        self.menu1.addSeparator()

        self.action_exit = QAction("9.종료", self)
        self.action_exit.triggered.connect(self.close)
        self.menu1.addAction(self.action_exit)

        # ----------------------------------------------------
        # 2. 코드관리
        # ----------------------------------------------------
        self.menu2 = QMenu("2.코드관리", self)
        
        self.menu1_2 = QMenu("1.사용자관리", self)
        self.action1_9 = QAction("1.사용자등록", self)
        self.action2_9 = QAction("2.사용자별 프로그램 권한", self)
        self.action3_8 = QAction("3.전자계산서사용자등록", self)
        self.action4_7 = QAction("4.사용자 접속현황", self)
        self.menu1_2.addAction(self.action1_9)
        self.menu1_2.addAction(self.action2_9)
        self.menu1_2.addAction(self.action3_8)
        self.menu1_2.addAction(self.action4_7)
        self.menu2.addMenu(self.menu1_2)

        self.action2_2 = QAction("2.코드관리", self)
        self.action3_2 = QAction("3.거래처 기초잔액 입력", self)
        self.action4_iU = QAction("4.더존iU연동관리", self)
        self.menu2.addAction(self.action2_2)
        self.menu2.addAction(self.action3_2)
        self.menu2.addAction(self.action4_iU)

        # ----------------------------------------------------
        # 3. 수입관리
        # ----------------------------------------------------
        self.menu3 = QMenu("3.수입관리", self)
        self.action1_3 = QAction("1.오퍼관리", self)
        self.action2_3 = QAction("2.수입부대비용관리", self)
        self.menu3.addAction(self.action1_3)
        self.menu3.addAction(self.action2_3)

        # ----------------------------------------------------
        # 4. 상품입/출고관리
        # ----------------------------------------------------
        self.menu4 = QMenu("4.상품입/출고관리", self)
        actions_menu4 = [
            "1.입고전표(직수입)", "2.입고전표(국내)", "3.출고전표", "4.창고이동",
            "5.로스출고", "6.생산일보", "7.지육구매입고/판매출고", "8.지육생산입고",
            "9.거래처 자료 일괄전환", "10.견적서", "11.생산 가공계획"
        ]
        for name in actions_menu4:
            self.menu4.addAction(QAction(name, self))

        # ----------------------------------------------------
        # 5. 입금/출금관리
        # ----------------------------------------------------
        self.menu5 = QMenu("5.입금/출금관리", self)
        actions_menu5 = ["1.입금(미수금)관리", "2.출금(미지급)관리", "3.입금(경비)관리", "4.출금(경비)관리", "5.통장이체"]
        for name in actions_menu5:
            self.menu5.addAction(QAction(name, self))

        # ----------------------------------------------------
        # 6. 월재고마감관리
        # ----------------------------------------------------
        self.menu6 = QMenu("6.월재고마감관리", self)
        actions_menu6 = ["1.재고마감관리", "2.일마감", "3.더존연동", "4.매출이익정산"]
        for name in actions_menu6:
            self.menu6.addAction(QAction(name, self))

        # ----------------------------------------------------
        # 7. 조회/출력
        # ----------------------------------------------------
        self.menu7 = QMenu("7.조회/출력", self)
        actions_menu7 = [
            "1.코드현황", "2.매입현황", "3.판매현황", "4.원장출력", "5.일계표",
            "6.매출이익", "7.입출금현황", "8.미수/미지급현황", "9.상품재고현황",
            "10.DM발송", "11.손익계산서", "12.잔액확인서", "13.거래매역 확인서(월별)",
            "14.통장관리", "15.경리일보", "16.자산현황", "17.거래내역서", "18.생산현황",
            "19.거래명세표출력(일괄)", "20.생산라벨현황", "21.일일보고", "22.바코드현황"
        ]
        for name in actions_menu7:
            self.menu7.addAction(QAction(name, self))

        # ----------------------------------------------------
        # 8. 계산서관리
        # ----------------------------------------------------
        self.menu8 = QMenu("8.계산서관리", self)
        actions_menu8 = [
            "1.계산서작업", "2.계산서입력", "3.계산서현황", "4.계산서출력(일괄)",
            "5.계산서삭제", "6.거래사실확인서", "7.전자계산서"
        ]
        for name in actions_menu8:
            self.menu8.addAction(QAction(name, self))

        # ----------------------------------------------------
        # 9. 파이낸싱/계약판매
        # ----------------------------------------------------
        self.menu9 = QMenu("9.파이낸싱/계약판매", self)

        # 메뉴바에 전체 메뉴 추가
        self.menuBar.addMenu(self.menu1)
        self.menuBar.addMenu(self.menu2)
        self.menuBar.addMenu(self.menu3)
        self.menuBar.addMenu(self.menu4)
        self.menuBar.addMenu(self.menu5)
        self.menuBar.addMenu(self.menu6)
        self.menuBar.addMenu(self.menu7)
        self.menuBar.addMenu(self.menu8)
        self.menuBar.addMenu(self.menu9)

    def apply_stylesheet(self):
        """MixNMenu 표준 메인 윈도우 QSS 디자인"""
        self.setStyleSheet("""
            QMainWindow#MixNMainWindow {
                background-color: #eef1f5;
            }

            /* MDI 영역 배경을 어둡지 않게 라이트 그레이로 지정 */
            QMdiArea#mdi_area {
                background-color: #d2d9e1;
                border: none;
            }

            /* 서브 윈도우 외곽 프레임 스타일 */
            QMdiSubWindow {
                background-color: #eef1f5;
                border: 1px solid #b8c2cc;
            }

            /* 상단 메뉴바 스타일 */
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

            /* 드롭다운 메뉴 스타일 */
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

            QMenu::separator {
                height: 1px;
                background-color: #e0e0e0;
                margin: 4px 6px;
            }

            /* 상태바 스타일 */
            QStatusBar {
                background-color: #ffffff;
                color: #555555;
                border-top: 1px solid #d0d7de;
                font-size: 8.5pt;
            }
        """)

    def open_company_reg(self):
        """1.업체등록 메뉴 클릭 시 MDI 서브윈도우로 창 열기"""
        if CompanyRegWidget is None:
            QMessageBox.warning(self, "경고", "company_reg.py 모듈을 찾을 수 없습니다.")
            return

        # 기존에 이미 열려있는 동일 서브윈도우가 있는지 확인
        for sub_win in self.mdi_area.subWindowList():
            if isinstance(sub_win.widget(), CompanyRegWidget):
                self.mdi_area.setActiveSubWindow(sub_win)
                return

        # 새로 생성하여 MDI 영역에 추가
        view = CompanyRegWidget()
        sub_window = self.mdi_area.addSubWindow(view)
        sub_window.setWindowTitle("업체등록")
        sub_window.resize(view.size())
        view.show()
        sub_window.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    main_win = MixNMainWindow()
    main_win.show()
    
    sys.exit(app.exec())