import sys
import os
import requests
from PySide6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox, QDialog
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont, QPalette, QColor

# 백엔드 FastAPI 포트에 맞춰 필요 시 포트 번호(8000/8080)를 수정하세요.
API_BASE_URL = "http://127.0.0.1:8000"


class CustomMessageBox(QDialog):
    """라이트모드 알림창"""
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(360, 170)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#ffffff"))
        palette.setColor(QPalette.WindowText, QColor("#111111"))
        self.setPalette(palette)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setStyleSheet("color: #111111; font-size: 10pt; font-family: '맑은 고딕'; background: transparent;")
        
        btn_ok = QPushButton("확인")
        btn_ok.setFixedWidth(80)
        btn_ok.setFixedHeight(30)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #1a5ac7; color: #ffffff;
                border: none; border-radius: 4px; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #1449a3; }
        """)
        btn_ok.clicked.connect(self.accept)
        
        layout.addWidget(lbl_msg)
        layout.addSpacing(10)
        layout.addWidget(btn_ok, alignment=Qt.AlignCenter)


class CompanyRegWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CompanyRegWidget")
        self.setWindowTitle("업체등록")
        self.resize(780, 640)
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.set_light_palette()
        self.init_ui()
        self.setup_navigation_order()
        self.load_data()

    def set_light_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#eef1f5"))
        palette.setColor(QPalette.WindowText, QColor("#222222"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.Text, QColor("#111111"))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor("#222222"))
        palette.setColor(QPalette.Highlight, QColor("#1a5ac7"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        lbl_logo = QLabel("MXMN")
        lbl_logo.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_sub_title = QLabel("자사 업체 정보 등록/수정")
        lbl_sub_title.setFont(QFont("Malgun Gothic", 10))

        header_layout.addWidget(lbl_logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(lbl_sub_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        form_group = QGroupBox("업체 기본 정보")
        form_group.setFont(QFont("Malgun Gothic", 9, QFont.Bold))
        
        grid = QGridLayout(form_group)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)

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

        grid.addWidget(QLabel("사업자명(*)"), 0, 0); grid.addWidget(self.txt_comp_name, 0, 1)
        grid.addWidget(QLabel("영문 사업자명"), 1, 0); grid.addWidget(self.txt_comp_name_en, 1, 1)
        grid.addWidget(QLabel("대표자명"), 2, 0); grid.addWidget(self.txt_ceo_name, 2, 1)
        grid.addWidget(QLabel("사업자번호(*)"), 3, 0); grid.addWidget(self.txt_biz_no, 3, 1)
        grid.addWidget(QLabel("우편번호"), 4, 0); grid.addWidget(self.txt_zip_code, 4, 1)
        grid.addWidget(QLabel("주소"), 5, 0); grid.addWidget(self.txt_address, 5, 1, 1, 3)
        grid.addWidget(QLabel("업태"), 6, 0); grid.addWidget(self.txt_uptae, 6, 1)
        grid.addWidget(QLabel("업종"), 7, 0); grid.addWidget(self.txt_upjong, 7, 1)
        grid.addWidget(QLabel("영업허가번호"), 8, 0); grid.addWidget(self.txt_lic_no, 8, 1)

        grid.addWidget(QLabel("전화번호"), 0, 2); grid.addWidget(self.txt_tel, 0, 3)
        grid.addWidget(QLabel("팩스번호"), 1, 2); grid.addWidget(self.txt_fax, 1, 3)
        grid.addWidget(QLabel("PCS/휴대폰"), 2, 2); grid.addWidget(self.txt_pcs, 2, 3)
        grid.addWidget(QLabel("이메일 ID"), 3, 2); grid.addWidget(self.txt_email, 3, 3)
        grid.addWidget(QLabel("계좌번호 1"), 4, 2); grid.addWidget(self.txt_bank1, 4, 3)
        grid.addWidget(QLabel("계좌번호 2"), 6, 2); grid.addWidget(self.txt_bank2, 6, 3)
        grid.addWidget(QLabel("제품상담/메모"), 7, 2); grid.addWidget(self.txt_consult, 7, 3, 2, 1)

        main_layout.addWidget(form_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_confirm = QPushButton("확인 (저장)")
        self.btn_confirm.setFixedWidth(110)
        self.btn_confirm.setFixedHeight(34)
        self.btn_confirm.clicked.connect(self.save_data)

        self.btn_close = QPushButton("닫기")
        self.btn_close.setFixedWidth(90)
        self.btn_close.setFixedHeight(34)
        self.btn_close.clicked.connect(self.close_window)

        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def setup_navigation_order(self):
        self.enter_order = [
            self.txt_comp_name, self.txt_comp_name_en, self.txt_ceo_name,
            self.txt_biz_no, self.txt_zip_code, self.txt_address,
            self.txt_uptae, self.txt_upjong, self.txt_lic_no,
            self.txt_tel, self.txt_fax, self.txt_pcs,
            self.txt_email, self.txt_bank1, self.txt_bank2,
            self.txt_consult, self.btn_confirm
        ]
        for w in self.enter_order:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if isinstance(obj, QTextEdit) and not (event.modifiers() & Qt.ControlModifier):
                    return super().eventFilter(obj, event)
                if obj in self.enter_order:
                    idx = self.enter_order.index(obj)
                    next_idx = idx + 1 if idx + 1 < len(self.enter_order) else 0
                    self.enter_order[next_idx].setFocus()
                    if isinstance(self.enter_order[next_idx], QLineEdit):
                        self.enter_order[next_idx].selectAll()
                    return True
        return super().eventFilter(obj, event)

    def close_window(self):
        parent = self.parentWidget()
        if parent and parent.inherits("QMdiSubWindow"):
            parent.close()
        else:
            self.close()

    def load_data(self):
        """DB 칼럼 매핑 명칭(comp_nm, ceo_nm 등)과 호환되도록 바인딩 보완"""
        try:
            res = requests.get(f"{API_BASE_URL}/api/v1/company", timeout=3)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]

                # DB 칼럼명 및 레거시 필드명 매핑
                self.txt_comp_name.setText(data.get("comp_nm") or data.get("comp_name") or "")
                self.txt_comp_name_en.setText(data.get("comp_enm") or data.get("comp_name_en") or "")
                self.txt_ceo_name.setText(data.get("ceo_nm") or data.get("ceo_name") or "")
                self.txt_biz_no.setText(data.get("biz_no") or "")
                self.txt_zip_code.setText(data.get("zip_no") or data.get("zip_code") or "")
                self.txt_address.setText(data.get("addr") or data.get("address") or "")
                self.txt_uptae.setText(data.get("uptae") or "")
                self.txt_upjong.setText(data.get("upjong") or "")
                self.txt_lic_no.setText(data.get("lic_no") or "")
                self.txt_tel.setText(data.get("tel_no") or data.get("tel") or "")
                self.txt_fax.setText(data.get("fax_no") or data.get("fax") or "")
                self.txt_pcs.setText(data.get("mbl_no") or data.get("pcs") or "")
                self.txt_email.setText(data.get("eml_addr") or data.get("email") or "")
                self.txt_bank1.setText(data.get("bank1") or data.get("acct_no1") or "")
                self.txt_bank2.setText(data.get("bank2") or data.get("acct_no2") or "")
                self.txt_consult.setPlainText(data.get("consult") or data.get("memo") or "")
        except Exception as e:
            print(f"데이터 조회 중 통신 오류: {e}")

    def save_data(self):
        """모든 UI 입력을 DB 필드명에 맞춰 전체 전송"""
        comp_name = self.txt_comp_name.text().strip()
        biz_no = self.txt_biz_no.text().strip()

        if not comp_name or not biz_no:
            CustomMessageBox("경고", "사업자명과 사업자번호는 필수 입력 항목입니다.", self).exec()
            return

        # DB 칼럼 표준명과 표준 폼 필드명을 모두 포함하여 백엔드 모델 호환성 확보
        payload = {
            "comp_cd": "00001",
            "comp_code": "00001",
            "comp_nm": comp_name,
            "comp_name": comp_name,
            "comp_enm": self.txt_comp_name_en.text().strip(),
            "comp_name_en": self.txt_comp_name_en.text().strip(),
            "ceo_nm": self.txt_ceo_name.text().strip(),
            "ceo_name": self.txt_ceo_name.text().strip(),
            "biz_no": biz_no,
            "zip_no": self.txt_zip_code.text().strip(),
            "zip_code": self.txt_zip_code.text().strip(),
            "addr": self.txt_address.text().strip(),
            "address": self.txt_address.text().strip(),
            "uptae": self.txt_uptae.text().strip(),
            "upjong": self.txt_upjong.text().strip(),
            "lic_no": self.txt_lic_no.text().strip(),
            "tel_no": self.txt_tel.text().strip(),
            "tel": self.txt_tel.text().strip(),
            "fax_no": self.txt_fax.text().strip(),
            "fax": self.txt_fax.text().strip(),
            "mbl_no": self.txt_pcs.text().strip(),
            "pcs": self.txt_pcs.text().strip(),
            "eml_addr": self.txt_email.text().strip(),
            "email": self.txt_email.text().strip(),
            "bank1": self.txt_bank1.text().strip(),
            "bank2": self.txt_bank2.text().strip(),
            "consult": self.txt_consult.toPlainText().strip(),
            "memo": self.txt_consult.toPlainText().strip()
        }

        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/company", json=payload, timeout=3)
            if res.status_code in (200, 201):
                CustomMessageBox("성공", "업체 정보가 정상적으로 저장되었습니다.", self).exec()
            else:
                CustomMessageBox("저장 실패", f"서버 응답 오류 (코드: {res.status_code}):\n{res.text}", self).exec()
        except Exception as e:
            CustomMessageBox("통신 오류", f"백엔드 서버와 통신할 수 없습니다:\n{e}", self).exec()


# 외부 호출 앨리어스
CompanyRegView = CompanyRegWidget