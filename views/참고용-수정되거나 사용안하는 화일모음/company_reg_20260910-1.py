import os
import requests
from PySide6.QtWidgets import QWidget, QMessageBox, QApplication, QLabel, QLineEdit
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt

API_BASE_URL = "http://127.0.0.1:8000"

class CompanyRegWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        loader = QUiLoader()
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_path = os.path.join(base_dir, "ui", "company_reg.ui")
        
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            print(f"[Error] UI 파일을 열 수 없습니다: {ui_path}")
            return
        
        self.ui = loader.load(ui_file, self)
        ui_file.close()

        self.setWindowTitle("업체 등록")
        
        self.center_window()
        self.init_ui()
        self.load_data()

    def center_window(self):
        """화면 정중앙에 창 띄우기"""
        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def init_ui(self):
        self.ui.btn_confirm.clicked.connect(self.save_data)
        self.ui.btn_close.clicked.connect(self.close)
        
        # 로고 텍스트 변경
        for child in self.ui.findChildren(object):
            if child.objectName() in ["label_logo", "lbl_logo", "btn_logo"] or "logo" in child.objectName().lower():
                if hasattr(child, "setText"):
                    child.setText("MXMN")

        # 동그라미 친 우측 상단 입력폼 영역 및 하단 안내 문구 확실하게 숨기기
        try:
            for child in self.ui.findChildren(QWidget):
                # 1. 우측 상단 영역(대략 X 좌표가 600 이상이거나 특정 레이아웃에 포함된 경우) 위젯 숨기기
                pos = child.pos()
                if pos.x() > 580 and pos.y() < 250:
                    child.setVisible(False)
                    continue

                # 2. 텍스트 내용 기반 하단 안내 문구 숨기기
                if hasattr(child, "text"):
                    text = child.text()
                    if "저작권법" in text or "복사나 복제" in text or "개발업체의 사전" in text:
                        child.setVisible(False)
        except Exception:
            pass

        # 입력창 및 확인/닫기 버튼 글자색 검정색 지정
        self.setStyleSheet("""
            QLineEdit {
                color: black;
                background-color: white;
            }
            QPushButton#btn_confirm, QPushButton#btn_close {
                color: black;
            }
        """)

    def load_data(self):
        try:
            res = requests.get(f"{API_BASE_URL}/api/v1/company")
            if res.status_code == 200:
                data = res.json()
                self.ui.txt_comp_name.setText(data.get("comp_name", ""))
                self.ui.txt_comp_name_en.setText(data.get("comp_name_en", ""))
                self.ui.txt_ceo_name.setText(data.get("ceo_name", ""))
                self.ui.txt_zip_code.setText(data.get("zip_code", ""))
                self.ui.txt_address.setText(data.get("address", ""))
                self.ui.txt_biz_no.setText(data.get("biz_no", ""))
                self.ui.txt_uptae.setText(data.get("uptae", ""))
                self.ui.txt_upjong.setText(data.get("upjong", ""))
                self.ui.txt_lic_no.setText(data.get("lic_no", ""))
                self.ui.txt_bank1.setText(data.get("bank1", ""))
                self.ui.txt_bank2.setText(data.get("bank2", ""))
                self.ui.txt_tel.setText(data.get("tel", ""))
                self.ui.txt_fax.setText(data.get("fax", ""))
                self.ui.txt_pcs.setText(data.get("pcs", ""))
                self.ui.txt_email.setText(data.get("email", ""))
                self.ui.txt_consult.setText(data.get("consult", ""))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터 로드 중 오류 발생:\n{e}")

    def save_data(self):
        data = {
            "comp_code": "00001",
            "comp_name": self.ui.txt_comp_name.text(),
            "comp_name_en": self.ui.txt_comp_name_en.text(),
            "ceo_name": self.ui.txt_ceo_name.text(),
            "zip_code": self.ui.txt_zip_code.text(),
            "address": self.ui.txt_address.text(),
            "biz_no": self.ui.txt_biz_no.text(),
            "uptae": self.ui.txt_uptae.text(),
            "upjong": self.ui.txt_upjong.text(),
            "lic_no": self.ui.txt_lic_no.text(),
            "bank1": self.ui.txt_bank1.text(),
            "bank2": self.ui.txt_bank2.text(),
            "tel": self.ui.txt_tel.text(),
            "fax": self.ui.txt_fax.text(),
            "pcs": self.ui.txt_pcs.text(),
            "email": self.ui.txt_email.text(),
            "consult": self.ui.txt_consult.text(),
        }

        if not data["comp_name"]:
            QMessageBox.warning(self, "경고", "사업자명을 입력해 주세요.")
            self.ui.txt_comp_name.setFocus()
            return
        if not data["biz_no"]:
            QMessageBox.warning(self, "경고", "등록번호를 입력해 주세요.")
            self.ui.txt_biz_no.setFocus()
            return

        try:
            res = requests.post(f"{API_BASE_URL}/api/v1/company", json=data)
            if res.status_code == 200:
                QMessageBox.information(self, "성공", "회사 정보가 정상적으로 저장되었습니다.")
            else:
                QMessageBox.warning(self, "실패", f"저장 실패: {res.text}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 통신 중 오류 발생:\n{e}")