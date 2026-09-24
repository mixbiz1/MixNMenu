from api_config import API_BASE_URL
import api_client as requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QGroupBox, QDialog, QComboBox
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont, QPalette, QColor



class CustomMessageBox(QDialog):
    """라이트모드 알림창"""

    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(380, 180)
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
        lbl_msg.setStyleSheet(
            "color:#111111; font-size:10pt; font-family:'맑은 고딕'; background:transparent;"
        )

        btn_ok = QPushButton("확인")
        btn_ok.setFixedWidth(80)
        btn_ok.setFixedHeight(30)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color:#1a5ac7; color:#ffffff;
                border:none; border-radius:4px; font-size:9pt; font-weight:bold;
            }
            QPushButton:hover { background-color:#1449a3; }
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
        self.resize(820, 690)

        self.is_new_mode = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.set_light_palette()
        self.init_ui()
        self.setup_navigation_order()
        self.load_company_list()

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

        selector_group = QGroupBox("회사 선택")
        selector_group.setFont(QFont("Malgun Gothic", 9, QFont.Bold))
        selector_layout = QHBoxLayout(selector_group)

        selector_layout.addWidget(QLabel("등록 회사"))
        self.cbo_company = QComboBox()
        self.cbo_company.setMinimumWidth(300)
        self.cbo_company.currentIndexChanged.connect(self.on_company_changed)
        selector_layout.addWidget(self.cbo_company)

        selector_layout.addSpacing(15)
        selector_layout.addWidget(QLabel("회사코드"))
        self.txt_comp_code = QLineEdit()
        self.txt_comp_code.setFixedWidth(100)
        self.txt_comp_code.setMaxLength(10)
        self.txt_comp_code.setPlaceholderText("예: 00002")
        selector_layout.addWidget(self.txt_comp_code)

        self.btn_new = QPushButton("신규")
        self.btn_new.setFixedWidth(80)
        self.btn_new.clicked.connect(self.new_company)
        selector_layout.addWidget(self.btn_new)

        self.btn_reload = QPushButton("새로고침")
        self.btn_reload.setFixedWidth(90)
        self.btn_reload.clicked.connect(self.load_company_list)
        selector_layout.addWidget(self.btn_reload)
        selector_layout.addStretch()
        main_layout.addWidget(selector_group)

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
            self.txt_comp_code, self.txt_comp_name, self.txt_comp_name_en,
            self.txt_ceo_name, self.txt_biz_no, self.txt_zip_code,
            self.txt_address, self.txt_uptae, self.txt_upjong, self.txt_lic_no,
            self.txt_tel, self.txt_fax, self.txt_pcs, self.txt_email,
            self.txt_bank1, self.txt_bank2, self.txt_consult, self.btn_confirm,
        ]
        for widget in self.enter_order:
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
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

    def clear_form(self):
        for widget in [
            self.txt_comp_name, self.txt_comp_name_en, self.txt_ceo_name,
            self.txt_biz_no, self.txt_zip_code, self.txt_address,
            self.txt_uptae, self.txt_upjong, self.txt_lic_no, self.txt_bank1,
            self.txt_bank2, self.txt_tel, self.txt_fax, self.txt_pcs,
            self.txt_email,
        ]:
            widget.clear()
        self.txt_consult.clear()

    def set_company_data(self, data):
        self.txt_comp_code.setText(data.get("comp_code") or "")
        self.txt_comp_name.setText(data.get("comp_name") or "")
        self.txt_comp_name_en.setText(data.get("comp_name_en") or "")
        self.txt_ceo_name.setText(data.get("ceo_name") or "")
        self.txt_biz_no.setText(data.get("biz_no") or "")
        self.txt_zip_code.setText(data.get("zip_code") or "")
        self.txt_address.setText(data.get("address") or "")
        self.txt_uptae.setText(data.get("uptae") or "")
        self.txt_upjong.setText(data.get("upjong") or "")
        self.txt_lic_no.setText(data.get("lic_no") or "")
        self.txt_tel.setText(data.get("tel") or "")
        self.txt_fax.setText(data.get("fax") or "")
        self.txt_pcs.setText(data.get("pcs") or "")
        self.txt_email.setText(data.get("email") or "")
        self.txt_bank1.setText(data.get("bank1") or "")
        self.txt_bank2.setText(data.get("bank2") or "")
        self.txt_consult.setPlainText(data.get("consult") or "")

    def load_company_list(self, select_code=None):
        try:
            res = requests.get(f"{API_BASE_URL}/companies", timeout=3)
            if res.status_code != 200:
                CustomMessageBox("조회 실패", f"회사 목록 조회 실패:\n{res.text}", self).exec()
                return

            companies = res.json()
            self.cbo_company.blockSignals(True)
            self.cbo_company.clear()
            for company in companies:
                code = company.get("comp_code", "")
                name = company.get("comp_name", "")
                self.cbo_company.addItem(f"{code}  {name}", code)
            self.cbo_company.blockSignals(False)

            if not companies:
                self.new_company()
                return

            target_index = 0
            if select_code:
                for i in range(self.cbo_company.count()):
                    if self.cbo_company.itemData(i) == select_code:
                        target_index = i
                        break
            self.cbo_company.setCurrentIndex(target_index)
            self.load_company(self.cbo_company.itemData(target_index))
        except Exception as e:
            CustomMessageBox("통신 오류", f"회사 목록을 조회할 수 없습니다:\n{e}", self).exec()

    def on_company_changed(self, index):
        if index < 0:
            return
        comp_code = self.cbo_company.itemData(index)
        if comp_code:
            self.load_company(comp_code)

    def load_company(self, comp_code):
        try:
            res = requests.get(f"{API_BASE_URL}/companies/{comp_code}", timeout=3)
            if res.status_code == 200:
                self.is_new_mode = False
                self.txt_comp_code.setReadOnly(True)
                self.set_company_data(res.json())
            else:
                CustomMessageBox("조회 실패", f"회사 정보 조회 실패:\n{res.text}", self).exec()
        except Exception as e:
            CustomMessageBox("통신 오류", f"회사 정보를 조회할 수 없습니다:\n{e}", self).exec()

    def new_company(self):
        self.is_new_mode = True
        self.cbo_company.setCurrentIndex(-1)
        self.clear_form()
        self.txt_comp_code.clear()
        self.txt_comp_code.setReadOnly(False)
        self.txt_comp_code.setFocus()

    def build_payload(self):
        return {
            "comp_code": self.txt_comp_code.text().strip(),
            "comp_name": self.txt_comp_name.text().strip(),
            "comp_name_en": self.txt_comp_name_en.text().strip() or None,
            "biz_no": self.txt_biz_no.text().strip(),
            "meatwatch_bplc_no": None,
            "ceo_name": self.txt_ceo_name.text().strip() or None,
            "zip_code": self.txt_zip_code.text().strip() or None,
            "address": self.txt_address.text().strip() or None,
            "uptae": self.txt_uptae.text().strip() or None,
            "upjong": self.txt_upjong.text().strip() or None,
            "lic_no": self.txt_lic_no.text().strip() or None,
            "bank1": self.txt_bank1.text().strip() or None,
            "bank2": self.txt_bank2.text().strip() or None,
            "tel": self.txt_tel.text().strip() or None,
            "fax": self.txt_fax.text().strip() or None,
            "pcs": self.txt_pcs.text().strip() or None,
            "email": self.txt_email.text().strip() or None,
            "consult": self.txt_consult.toPlainText().strip() or None,
        }

    def save_data(self):
        payload = self.build_payload()
        if not payload["comp_code"] or not payload["comp_name"] or not payload["biz_no"]:
            CustomMessageBox(
                "경고", "회사코드, 사업자명, 사업자번호는 필수 입력 항목입니다.", self
            ).exec()
            return

        try:
            if self.is_new_mode:
                res = requests.post(
                    f"{API_BASE_URL}/companies", json=payload, timeout=3
                )
            else:
                res = requests.put(
                    f"{API_BASE_URL}/companies/{payload['comp_code']}",
                    json=payload,
                    timeout=3,
                )

            if res.status_code in (200, 201):
                saved_code = payload["comp_code"]
                CustomMessageBox("성공", res.json().get("message", "정상 저장되었습니다."), self).exec()
                self.load_company_list(select_code=saved_code)
            else:
                try:
                    detail = res.json().get("detail", res.text)
                except Exception:
                    detail = res.text
                CustomMessageBox("저장 실패", f"서버 응답 오류 ({res.status_code}):\n{detail}", self).exec()
        except Exception as e:
            CustomMessageBox("통신 오류", f"백엔드 서버와 통신할 수 없습니다:\n{e}", self).exec()


CompanyRegView = CompanyRegWidget
