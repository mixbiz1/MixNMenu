import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox, QDialog, QStyleFactory
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor

API_BASE_URL = "http://127.0.0.1:8000"


class CustomMessageBox(QDialog):
    """OS 다크모드의 영향을 받지 않는 라이트모드 알림창"""
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(340, 160)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        # 강제 라이트 팔레트
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#ffffff"))
        palette.setColor(QPalette.WindowText, QColor("#111111"))
        self.setPalette(palette)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 메시지 텍스트
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setStyleSheet("color: #111111; font-size: 10pt; font-family: '맑은 고딕'; background: transparent;")
        
        # 확인 버튼
        btn_ok = QPushButton("확인")
        btn_ok.setFixedWidth(80)
        btn_ok.setFixedHeight(30)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #1a5ac7;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1449a3;
            }
        """)
        btn_ok.clicked.connect(self.accept)
        
        layout.addWidget(lbl_msg)
        layout.addSpacing(10)
        layout.addWidget(btn_ok, alignment=Qt.AlignCenter)
        
        self.setStyleSheet("QDialog { background-color: #ffffff; border: 1px solid #b8c2cc; }")


class CompanyRegWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setObjectName("CompanyRegWidget")
        self.setWindowTitle("업체등록")
        self.resize(780, 640)
        
        # 라이트 팔레트 강제 재설정
        self.set_light_palette()
        
        self.init_ui()
        self.center_window()
        self.load_data()

    def set_light_palette(self):
        """OS 다크모드가 적용되어 있어도 라이트 팔레트로 강제 재설정"""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#eef1f5"))
        palette.setColor(QPalette.WindowText, QColor("#222222"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f7fafe"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#222222"))
        palette.setColor(QPalette.Text, QColor("#111111"))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor("#222222"))
        palette.setColor(QPalette.BrightText, QColor("#ff0000"))
        palette.setColor(QPalette.Highlight, QColor("#1a5ac7"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 상단 타이틀 영역
        header_layout = QHBoxLayout()
        
        lbl_logo = QLabel("MXMN")
        lbl_logo.setObjectName("lbl_logo")
        lbl_logo.setFont(QFont("Segoe UI", 16, QFont.Bold))
        
        lbl_sub_title = QLabel("자사 업체 정보 등록/수정")
        lbl_sub_title.setObjectName("lbl_sub_title")
        lbl_sub_title.setFont(QFont("Malgun Gothic", 10))

        header_layout.addWidget(lbl_logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(lbl_sub_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # 2. 입력 폼 그룹박스
        form_group = QGroupBox("업체 기본 정보")
        form_group.setObjectName("form_group")
        form_group.setFont(QFont("Malgun Gothic", 9, QFont.Bold))
        
        grid = QGridLayout(form_group)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)
        grid.setContentsMargins(15, 20, 15, 15)

        self.txt_comp_name = QLineEdit()
        self.txt_comp_name_en = QLineEdit()
        self.txt_ceo_name = QLineEdit()
        self.txt_biz_no = QLineEdit()
        self.txt_zip_code = QLineEdit()
        self.txt_address = QLineEdit()
        self.txt_uptae = QLineEdit()
        self.txt_upjong = QLineEdit()
        self.txt_lic_no = QLineEdit()
        self.txt_bank1 = QLineEdit()
        self.txt_bank2 = QLineEdit()
        self.txt_tel = QLineEdit()
        self.txt_fax = QLineEdit()
        self.txt_pcs = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_consult = QTextEdit()
        self.txt_consult.setMaximumHeight(55)

        grid.addWidget(QLabel("사업자명(*)"), 0, 0)
        grid.addWidget(self.txt_comp_name, 0, 1)

        grid.addWidget(QLabel("영문 사업자명"), 1, 0)
        grid.addWidget(self.txt_comp_name_en, 1, 1)

        grid.addWidget(QLabel("대표자명"), 2, 0)
        grid.addWidget(self.txt_ceo_name, 2, 1)

        grid.addWidget(QLabel("사업자번호(*)"), 3, 0)
        grid.addWidget(self.txt_biz_no, 3, 1)

        grid.addWidget(QLabel("우편번호"), 4, 0)
        grid.addWidget(self.txt_zip_code, 4, 1)

        grid.addWidget(QLabel("주소"), 5, 0)
        grid.addWidget(self.txt_address, 5, 1, 1, 3)

        grid.addWidget(QLabel("업태"), 6, 0)
        grid.addWidget(self.txt_uptae, 6, 1)

        grid.addWidget(QLabel("업종"), 7, 0)
        grid.addWidget(self.txt_upjong, 7, 1)

        grid.addWidget(QLabel("영업허가번호"), 8, 0)
        grid.addWidget(self.txt_lic_no, 8, 1)

        grid.addWidget(QLabel("전화번호"), 0, 2)
        grid.addWidget(self.txt_tel, 0, 3)

        grid.addWidget(QLabel("팩스번호"), 1, 2)
        grid.addWidget(self.txt_fax, 1, 3)

        grid.addWidget(QLabel("PCS/휴대폰"), 2, 2)
        grid.addWidget(self.txt_pcs, 2, 3)

        grid.addWidget(QLabel("이메일 ID"), 3, 2)
        grid.addWidget(self.txt_email, 3, 3)

        grid.addWidget(QLabel("계좌번호 1"), 4, 2)
        grid.addWidget(self.txt_bank1, 4, 3)

        grid.addWidget(QLabel("계좌번호 2"), 6, 2)
        grid.addWidget(self.txt_bank2, 6, 3)

        grid.addWidget(QLabel("제품상담/메모"), 7, 2)
        grid.addWidget(self.txt_consult, 7, 3, 2, 1)

        main_layout.addWidget(form_group)

        # 3. 하단 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_confirm = QPushButton("확인 (저장)")
        self.btn_confirm.setObjectName("btn_confirm")
        self.btn_confirm.setFixedWidth(110)
        self.btn_confirm.setFixedHeight(34)
        self.btn_confirm.clicked.connect(self.save_data)

        self.btn_close = QPushButton("닫기")
        self.btn_close.setObjectName("btn_close")
        self.btn_close.setFixedWidth(90)
        self.btn_close.setFixedHeight(34)
        self.btn_close.clicked.connect(self.close_window)

        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

        # 4. QSS 스타일시트 적용
        self.setStyleSheet("""
            QWidget#CompanyRegWidget {
                background-color: #eef1f5;
            }
            
            QLabel#lbl_logo {
                color: #1a5ac7;
                background-color: transparent;
            }
            QLabel#lbl_sub_title {
                color: #333333;
                background-color: transparent;
            }

            QLabel {
                color: #222222;
                background-color: transparent;
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 9pt;
            }

            QGroupBox#form_group {
                background-color: #ffffff;
                color: #1a5ac7;
                border: 1px solid #b8c2cc;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox#form_group::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: #ffffff;
                color: #1a5ac7;
            }

            QLineEdit, QTextEdit {
                color: #111111;
                background-color: #ffffff;
                border: 1px solid #c0c7d0;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 9pt;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #1a5ac7;
                background-color: #f7fafe;
            }

            QPushButton {
                font-family: 'Malgun Gothic', '맑은 고딕';
                font-size: 9pt;
                font-weight: bold;
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #b0b8c4;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #f0f4fb;
                border-color: #1a5ac7;
                color: #1a5ac7;
            }

            QPushButton#btn_confirm {
                background-color: #ffffff;
                color: #1a5ac7;
                border: 1.5px solid #1a5ac7;
            }
            QPushButton#btn_confirm:hover {
                background-color: #1a5ac7;
                color: #ffffff;
            }
        """)

    def close_window(self):
        self.close()

    def show_alert(self, title, message):
        """커스텀 팝업 메시지 출력"""
        dlg = CustomMessageBox(title, message, self)
        dlg.exec()

    def load_data(self):
        try:
            res = requests.get(f"{API_BASE_URL}/api/v1/company", timeout=3)
            if res.status_code == 200:
                data = res.json()
                self.txt_comp_name.setText(data.get("comp_name", ""))
                self.txt_comp_name_en.setText(data.get("comp_name_en", ""))
                self.txt_ceo_name.setText(data.get("ceo_name", ""))
                self.txt_zip_code.setText(data.get("zip_code", ""))
                self.txt_address.setText(data.get("address", ""))
                self.txt_biz_no.setText(data.get("biz_no", ""))
                self.txt_uptae.setText(data.get("uptae", ""))
                self.txt_upjong.setText(data.get("upjong", ""))
                self.txt_lic_no.setText(data.get("lic_no", ""))
                self.txt_bank1.setText(data.get("bank1", ""))
                self.txt_bank2.setText(data.get("bank2", ""))
                self.txt_tel.setText(data.get("tel", ""))
                self.txt_fax.setText(data.get("fax", ""))
                self.txt_pcs.setText(data.get("pcs", ""))
                self.txt_email.setText(data.get("email", ""))
                self.txt_consult.setPlainText(data.get("consult", ""))
        except Exception as e:
            print(f"[Warning] 데이터 로드 실패: {e}")

    def save_data(self):
        data = {
            "comp_code": "00001",
            "comp_name": self.txt_comp_name.text().strip(),
            "comp_name_en": self.txt_comp_name_en.text().strip(),
            "ceo_name": self.txt_ceo_name.text().strip(),
            "zip_code": self.txt_zip_code.text().strip(),
            "address": self.txt_address.text().strip(),
            "biz_no": self.txt_biz_no.text().strip(),
            "uptae": self.txt_uptae.text().strip(),
            "upjong": self.txt_upjong.text().strip(),
            "lic_no": self.txt_lic_no.text().strip(),
            "bank1": self.txt_bank1.text().strip(),
            "bank2": self.txt_bank2.text().strip(),
            "tel": self.txt_tel.text().strip(),
            "fax": self.txt_fax.text().strip(),
            "pcs": self.txt_pcs.text().strip(),
            "email": self.txt_email.text().strip(),
            "consult": self.txt_consult.toPlainText().strip(),
        }

        if not data["comp_name"]:
            self.show_alert("경고", "사업자명을 입력해 주세요.")
            self.txt_comp_name.setFocus()
            return
        if not data["biz_no"]:
            self.show_alert("경고", "사업자 등록번호를 입력해 주세요.")
            self.txt_biz_no.setFocus()
            return

        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/company", json=data, timeout=3)
            if res.status_code == 200:
                self.show_alert("성공", "회사 정보가 정상적으로 저장되었습니다.")
            else:
                self.show_alert("저장 실패", f"서버 오류: {res.text}")
        except Exception as e:
            self.show_alert("오류", f"서버 통신 오류:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = CompanyRegWidget()
    window.show()
    sys.exit(app.exec())