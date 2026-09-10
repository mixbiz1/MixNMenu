import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QMessageBox, QScrollArea
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
        self.setStyleSheet("""
            DashboardCard {
                background-color: #F8F9FA;
                border: 1px solid #CED4DA;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 카테고리 헤더
        lbl_title = QLabel(f"<< {category_title} >>")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setFont(QFont("Malgun Gothic", 11, QFont.Bold))
        lbl_title.setStyleSheet("color: #003399; margin-bottom: 4px;")
        layout.addWidget(lbl_title)
        
        # 버튼 생성 및 이벤트 연결
        for btn_name in button_names:
            btn = QPushButton(btn_name)
            btn.setFont(QFont("Malgun Gothic", 10))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #222222;
                    border: 1px solid #B0BEC5;
                    border-radius: 4px;
                    padding: 4px 8px;
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
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_file_path = os.path.join(base_dir, "ui", "main_dashboard.ui")
        
        grid_layout = None
        
        # 1. .ui 파일이 정상 존재하는 경우 UI 로드
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
            # 상단 제목 영역
            title_lbl = QLabel("바탕화면 단축메뉴")
            title_lbl.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
            title_lbl.setStyleSheet("color: #1a5ac7; margin-bottom: 10px;")
            main_layout.addWidget(title_lbl)
            
            # 카드가 배치될 스크롤/그리드 영역
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
            
            container = QWidget()
            grid_layout = QGridLayout(container)
            grid_layout.setSpacing(15)
            scroll_area.setWidget(container)
            
            main_layout.addWidget(scroll_area)

        # 3. 단축메뉴 데이터구조 정의
        menu_structure = {
            "코드관리": [
                "업체등록",
                "공통코드입력(공통)",
                "공통코드입력(상품)",
                "거래처입력",
                "상품입력",
                "경비코드입력"
            ],
            "입출금관리": [
                "입금(미수금)관리",
                "출금(미지급)관리",
                "입금(경비)관리",
                "출금(경비)관리"
            ],
            "전표관리": [
                "입고전표(입력/수정)",
                "입고전표(삭제)",
                "출고전표(입력/수정)",
                "출고전표(삭제)",
                "입고전표(직수입)",
                "직수입고전표(삭제)"
            ],
            "계약판매": [
                "수입대행",
                "BL양수도",
                "국내매입"
            ]
        }
        
        # 4. 카테고리 카드 그리드 배치
        col = 0
        for category, buttons in menu_structure.items():
            card = DashboardCard(category, buttons, self.handle_menu_click)
            grid_layout.addWidget(card, 0, col, Qt.AlignTop)
            col += 1

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
        
        # 1. 업체등록 (1.시스템관리 -> 1.업체등록 창 연동)
        if menu_name == "업체등록":
            if self.main_window and hasattr(self.main_window, "open_company_reg"):
                self.main_window.open_company_reg()
            else:
                self.show_popup_msg("안내", "업체등록(자회사 관리) 화면을 연동합니다.")
                
        # 2. 거래처입력
        elif menu_name == "거래처입력":
            self.show_popup_msg("안내", "거래처 입력(타사/매입·매출처) 화면은 별도 구현 예정입니다.")
            
        # 3. 계약 및 파이낸싱
        elif menu_name in ["수입대행", "BL양수도", "국내매입"]:
            self.show_popup_msg("계약판매", f"[{menu_name}] 계약 및 파이낸싱 관리 화면 준비 중입니다.")
            
        # 4. 기타 메뉴
        else:
            self.show_popup_msg("메뉴 선택", f"'{menu_name}' 화면을 연결합니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    
    window = MainDashboard()
    window.resize(1100, 650)
    window.show()
    
    sys.exit(app.exec())