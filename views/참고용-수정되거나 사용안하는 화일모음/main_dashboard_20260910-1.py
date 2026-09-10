# views/main_dashboard.py
import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, 
    QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtUiTools import QUiLoader


class DashboardCard(QFrame):
    """카테고리별 단축메뉴 카드 위젯 (UI 하위 컴포넌트)"""
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
        
        # 버튼 생성 및 스타일/이벤트 적용
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
    """ui/main_dashboard.ui 파일을 읽어와서 제어하는 View 클래스"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        # 1. .ui 파일 경로 탐색 및 로드
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_file_path = os.path.join(base_dir, "ui", "main_dashboard.ui")
        
        loader = QUiLoader()
        self.ui = loader.load(ui_file_path, self)
        
        # 메인 레이아웃 적용
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.ui)
        
        # 상단 설명 라벨에서 '(주)믹스비즈 - ' 문구 제거
        title_label = self.ui.findChild(QLabel, "lbl_title")  # ui 상의 라벨 객체명
        if not title_label:
            # objectName이 지정되지 않은 경우를 대비해 첫 번째 QLabel 탐색
            for label in self.ui.findChildren(QLabel):
                if "(주)믹스비즈" in label.text():
                    title_label = label
                    break

        if title_label:
            new_text = title_label.text().replace("(주)믹스비즈 - ", "")
            title_label.setText(new_text)

        # 2. 카테고리별 단축메뉴 구성 데이터 ('계약판매' 우측 배치)
        menu_structure = {
            "코드관리": [
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
        
        # 3. .ui 파일 상의 gridLayout_cards 영역에 단축메뉴 카드 배치
        grid_layout = self.ui.findChild(object, "gridLayout_cards")
        
        if grid_layout:
            col = 0
            for category, buttons in menu_structure.items():
                card = DashboardCard(category, buttons, self.handle_menu_click)
                grid_layout.addWidget(card, 0, col, Qt.AlignTop)
                col += 1

    def show_popup_msg(self, title: str, message: str, icon_type: str = "info"):
        """다크모드 / 라이트모드 환경과 상관없이 고정 가독성을 보장하는 팝업 메시지창"""
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
            QMessageBox {
                background-color: #f8f9fa !important;
            }
            QMessageBox QLabel {
                color: #1a1a1a !important;
                font-size: 13px;
                font-weight: bold;
                background-color: transparent !important;
            }
            QPushButton {
                background-color: #ffffff !important;
                color: #222222 !important;
                border: 1px solid #b0b0b0 !important;
                border-radius: 4px;
                padding: 5px 18px;
                min-width: 65px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e !important;
                color: #ffffff !important;
                border-color: #005a9e !important;
            }
            QPushButton:pressed {
                background-color: #004578 !important;
                color: #ffffff !important;
            }
        """)
        msg.exec()

    def handle_menu_click(self, menu_name: str):
        """단축메뉴 버튼 클릭 시 상위/세부 화면을 연결하는 공통 핸들러"""
        print(f"[단축메뉴 클릭]: {menu_name}")
        
        if menu_name == "거래처입력":
            self.show_popup_msg("메뉴 실행", "거래처 입력(업체등록) 화면을 연동합니다.")
        elif menu_name in ["수입대행", "BL양수도", "국내매입"]:
            self.show_popup_msg("계약판매 실행", f"[{menu_name}] 계약 및 파이낸싱 관리 화면을 연동합니다.")
        else:
            self.show_popup_msg("메뉴 선택", f"'{menu_name}' 메뉴가 선택되었습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    
    window = MainDashboard()
    window.resize(1100, 650)
    window.show()
    
    sys.exit(app.exec())