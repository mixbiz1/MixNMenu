from api_config import API_BASE_URL
import api_client as httpx

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout,
)

from app_context import app_context




class PasswordChangeDialog(QDialog):
    """현재 로그인 사용자의 비밀번호를 확인 후 변경한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("비밀번호 변경")
        self.setModal(True)
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"사용자: {app_context.user_id} ({app_context.user_name})"))
        form = QFormLayout()
        self.current_password = self._password_field()
        self.new_password = self._password_field()
        self.confirm_password = self._password_field()
        form.addRow("현재 비밀번호 *", self.current_password)
        form.addRow("새 비밀번호 *", self.new_password)
        form.addRow("새 비밀번호 확인 *", self.confirm_password)
        root.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Save).setText("변경")
        self.buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.buttons.accepted.connect(self.change_password)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.current_password.returnPressed.connect(self.new_password.setFocus)
        self.new_password.returnPressed.connect(self.confirm_password.setFocus)
        self.confirm_password.returnPressed.connect(self.change_password)

    @staticmethod
    def _password_field():
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setMaxLength(100)
        return field

    def change_password(self):
        current = self.current_password.text()
        new = self.new_password.text()
        confirm = self.confirm_password.text()
        if not current or not new or not confirm:
            QMessageBox.warning(self, "입력 확인", "비밀번호 세 항목을 모두 입력해 주세요.")
            return
        if len(new) < 4:
            QMessageBox.warning(self, "입력 확인", "새 비밀번호는 4자 이상 입력해 주세요.")
            return
        if new != confirm:
            QMessageBox.warning(self, "입력 확인", "새 비밀번호와 확인값이 일치하지 않습니다.")
            self.confirm_password.clear()
            self.confirm_password.setFocus()
            return
        try:
            response = httpx.put(
                f"{API_BASE_URL}/users/{app_context.user_id}/password",
                json={"current_password": current, "new_password": new},
                timeout=10,
            )
            if response.status_code >= 400:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise RuntimeError(detail)
            QMessageBox.information(self, "변경 완료", "비밀번호가 변경되었습니다. 다음 로그인부터 새 비밀번호를 사용하세요.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "변경 오류", str(exc))
