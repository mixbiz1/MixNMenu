import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QMessageBox, QScrollArea, QMdiSubWindow
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtUiTools import QUiLoader


class DashboardCard(QFrame):
    """카테고리별 단축메뉴 카드 위젯"""
    def __init__(self, category_title: str, button_names: list, on_button_click):
        super().__init__()
        self.on_button_click = on_button_click
        
        self.setFrameShape(QFrame.StyledPanel)
        # 고정 폭 제거 및 최소 폭 설정으로 자유로운 크기 조절 지원
        self.setMinimumWidth(180)
        self.setStyleSheet("""
            DashboardCard {
                background-color: #F8F9FA;
                border: 1px solid #CED4DA;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # 카테고리 헤더
        lbl_title = QLabel(f"<< {category_title} >>")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setFont(QFont("Malgun Gothic", 10.5, QFont.Bold))
        lbl_title.setStyleSheet("color: #003399; margin-bottom: 4px;")
        layout.addWidget(lbl_title)
        
        # 버튼 생성 및 이벤트 연결
        for btn_name in button_names:
            btn = QPushButton(btn_name)
            btn.setFont(QFont("Malgun Gothic", 9.5))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #222222;
                    border: 1px solid #B0BEC5;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #E3F2FD;
                    border-color: #2196F3;
                    color: #0D47A1;
                }
                QPushButton:pressed {
                    background-color: #BBDEFB;
                    color: #0D47A1;
                }
            """)
            btn.clicked.connect(lambda checked=False, name=btn_name: self.on_button_click(name))
            layout.addWidget(btn)
            
        layout.addStretch()


class MainDashboard(QWidget):
    """단축메뉴 바탕화면 메인 위젯"""
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self._maximized_once = False  # 최초 1회만 자동 최대화
        self.init_ui()
        
    def showEvent(self, event):
        super().showEvent(event)
        if not self._maximized_once:
            self._maximized_once = True
            parent = self.parent()
            while parent:
                if isinstance(parent, QMdiSubWindow):
                    parent.showMaximized()
                    break
                parent = parent.parent()
            if self.main_window and hasattr(self.main_window, "showMaximized"):
                self.main_window.showMaximized()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_file_path = os.path.join(base_dir, "ui", "main_dashboard.ui")
        
        grid_layout = None
        
        # 1. .ui 파일이 존재하는 경우 로드 시도 (실패 시 Fallback)
        if os.path.exists(ui_file_path):
            try:
                loader = QUiLoader()
                self.ui = loader.load(ui_file_path, self)
                main_layout.addWidget(self.ui)
                
                title_label = self.ui.findChild(QLabel, "lbl_title")
                if not title_label:
                    for label in self.ui.findChildren(QLabel):
                        if "(주)믹스비즈" in label.text():
                            title_label = label
                            break
                if title_label:
                    title_label.setText(title_label.text().replace("(주)믹스비즈 - ", ""))

                grid_layout = self.ui.findChild(object, "gridLayout_cards")
            except Exception as e:
                print(f"[Warning] .ui 파일 로드 실패, 순수 파이썬 레이아웃으로 대체합니다: {e}")

        # 2. .ui 파일이 없거나 로드 실패 시 파이썬 코드로 UI 자동 동적 생성 (Fallback)
        if grid_layout is None:
            title_lbl = QLabel("바탕화면 단축메뉴")
            title_lbl.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
            title_lbl.setStyleSheet("color: #1a5ac7; margin-bottom: 10px;")
            main_layout.addWidget(title_lbl)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
            
            container = QWidget()
            grid_layout = QGridLayout(container)
            grid_layout.setSpacing(12)
            grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            scroll_area.setWidget(container)
            
            main_layout.addWidget(scroll_area)

        # 3. 단축메뉴 데이터 구조 정의
        menu_structure = {
            "코드관리": [
                "거래처입력",
                "공통코드입력",
                "상품공통코드입력",
                "상품입력코드"
            ],
            "입출금관리": [
                "입금(미수금)관리",
                "출금(미지급)관리",
                "입금(경비)관리",
                "출금(경비)관리",
                "미수/미지급현황"
            ],
            "전표관리": [
                "입고전표(입력/수정)",
                "입고전표(삭제)",
                "출고전표(입력/수정)",
                "출고전표(삭제)",
                "입고전표(직수입)",
                "직수입고전표(삭제)",
                "상품재고현황"
            ],
            "계약판매": [
                "수입대행",
                "BL양수도",
                "국내매입"
            ],
            "계산서관리": [
                "매입계산서입력",
                "매출계산서입력",
                "계산서내역",
                "매입세금계산서입력",
                "매출세금계산서입력",
                "매출세금계산서내역"
            ],
            "미트와치": [
                "미트와치 수입업자",
                "미트와치 판매업자"
            ]
        }
        
        # 4. 카테고리 카드 그리드 배치 (한 줄에 최대 4개씩 배치)
        row, col = 0, 0
        max_cols = 4  
        for category, buttons in menu_structure.items():
            card = DashboardCard(category, buttons, self.handle_menu_click)
            grid_layout.addWidget(card, row, col, Qt.AlignTop)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def show_popup_msg(self, title: str, message: str, icon_type: str = "info"):
        """가독성이 보장된 팝업 메세지창"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        
        if icon_type == "info":
            msg.setIcon(QMessageBox.Information)
        elif icon_type == "warning":
            msg.setIcon(QMessageBox.Warning)
        elif icon_type == "critical":
            msg.setIcon(QMessageBox.Critical)

        msg.setStyleSheet("""
            QMessageBox { background-color: #f8f9fa !important; }
            QMessageBox QLabel { color: #1a1a1a !important; font-size: 13px; font-weight: bold; }
            QPushButton {
                background-color: #ffffff !important; color: #222222 !important;
                border: 1px solid #b0b0b0 !important; border-radius: 4px; padding: 5px 18px; min-width: 65px;
            }
            QPushButton:hover { background-color: #005a9e !important; color: #ffffff !important; }
        """)
        msg.exec()

    def handle_menu_click(self, menu_name: str):
        """단축메뉴 클릭 이벤트 연동"""
        print(f"[단축메뉴 클릭]: {menu_name}")
        
        if menu_name == "거래처입력":
            if self.main_window and hasattr(self.main_window, "open_account_reg"):
                self.main_window.open_account_reg()
            else:
                self.show_popup_msg(
                    "실행 오류",
                    "메인창의 거래처입력 기능과 연결되지 않았습니다.",
                    "warning",
                )
        elif menu_name == "공통코드입력":
            if self.main_window and hasattr(self.main_window, "open_common_code"):
                self.main_window.open_common_code()
            else:
                self.show_popup_msg("실행 오류", "공통코드입력 기능과 연결되지 않았습니다.", "warning")
        elif menu_name == "상품공통코드입력":
            if self.main_window and hasattr(self.main_window, "open_goods_common_code"):
                self.main_window.open_goods_common_code()
            else:
                self.show_popup_msg("실행 오류", "상품공통코드입력 기능과 연결되지 않았습니다.", "warning")
        elif menu_name == "상품입력코드":
            if self.main_window and hasattr(self.main_window, "open_product_reg"):
                self.main_window.open_product_reg()
            else:
                self.show_popup_msg(
                    "실행 오류",
                    "메인창의 상품코드입력 기능과 연결되지 않았습니다.",
                    "warning",
                )
        elif menu_name in ["수입대행", "BL양수도", "국내매입"]:
            self.show_popup_msg("계약판매", f"[{menu_name}] 계약 및 파이낸싱 관리 화면 준비 중입니다.")
        elif menu_name in ["매입계산서입력", "매출계산서입력", "계산서내역", "매입세금계산서입력", "매출세금계산서입력", "매출세금계산서내역"]:
            self.show_popup_msg("계산서관리", f"[{menu_name}] 전자계산서/세금계산서 화면을 연결합니다.")
        elif menu_name in ["미트와치 수입업자", "미트와치 판매업자"]:
            self.show_popup_msg("미트와치", f"[{menu_name}] 연동 화면을 연결합니다.")
        elif menu_name == "미수/미지급현황":
            self.show_popup_msg("입출금관리", "[미수/미지급현황] 조회 화면을 연결합니다.")
        elif menu_name == "상품재고현황":
            self.show_popup_msg("전표관리", "[상품재고현황] 조회 화면을 연결합니다.")
        else:
            self.show_popup_msg("메뉴 선택", f"'{menu_name}' 화면을 연결합니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    
    window = MainDashboard()
    window.resize(1200, 700)
    window.show()
    
    sys.exit(app.exec())
