import api_client as httpx

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QVBoxLayout, QWidget, QMdiSubWindow,
)

from app_context import app_context
from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update


API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class UserRegWindow(QWidget):
    """로그인 사용자를 등록·수정하고 사용상태를 관리한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user_id = None
        self.users = []
        self.setWindowTitle("사용자등록")
        self.resize(1100, 680)
        self._build_ui()
        self._apply_style()
        QTimer.singleShot(50, self.load_users)

    def _build_ui(self):
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("사용자 ID 또는 사용자명")
        self.search.setMinimumWidth(300)
        self.include_inactive = QCheckBox("사용중지 포함")
        self.include_inactive.setChecked(True)
        self.btn_refresh = QPushButton("새로고침 [F7]")
        self.btn_new = QPushButton("신규 [F2]")
        self.btn_save = QPushButton("저장 [F4]")
        self.btn_cancel = QPushButton("취소 [F5]")
        self.btn_status = QPushButton("사용중지 [F6]")
        self.btn_close = QPushButton("닫기")
        toolbar.addWidget(QLabel("검색"))
        toolbar.addWidget(self.search)
        toolbar.addStretch()
        for widget in (self.include_inactive, self.btn_refresh, self.btn_new,
                       self.btn_save, self.btn_cancel, self.btn_status, self.btn_close):
            toolbar.addWidget(widget)
        root.addLayout(toolbar)

        guide = QLabel(
            "로그인 사용자를 등록합니다. 사용자 ID는 저장 후 변경할 수 없습니다. "
            "기존 사용자의 비밀번호 칸을 비워 저장하면 비밀번호는 변경되지 않습니다."
        )
        guide.setObjectName("guide")
        guide.setWordWrap(True)
        root.addWidget(guide)

        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["사용자 ID", "사용자명", "상태", "등록일"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.table, (180, 220, 100, 170))
        splitter.addWidget(self.table)

        detail = QGroupBox("사용자 정보")
        form = QFormLayout(detail)
        self.user_id = QLineEdit()
        self.user_id.setMaxLength(50)
        self.user_name = QLineEdit()
        self.user_name.setMaxLength(50)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setMaxLength(100)
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.Password)
        self.password_confirm.setMaxLength(100)
        self.status_label = QLabel("신규")
        form.addRow("사용자 ID *", self.user_id)
        form.addRow("사용자명 *", self.user_name)
        form.addRow("초기/변경 비밀번호 *", self.password)
        form.addRow("비밀번호 확인 *", self.password_confirm)
        form.addRow("계정상태", self.status_label)
        splitter.addWidget(detail)
        splitter.setSizes([650, 450])
        root.addWidget(splitter, 1)

        self.btn_refresh.clicked.connect(self.load_users)
        self.btn_new.clicked.connect(self.new_user)
        self.btn_save.clicked.connect(self.save_user)
        self.btn_cancel.clicked.connect(self.cancel_edit)
        self.btn_status.clicked.connect(self.toggle_status)
        self.btn_close.clicked.connect(self.close_window)
        self.search.returnPressed.connect(self.load_users)
        self.include_inactive.stateChanged.connect(self.load_users)
        self.table.itemSelectionChanged.connect(self.on_selected)
        for field in (self.user_id, self.user_name, self.password, self.password_confirm):
            field.installEventFilter(self)

    def _apply_style(self):
        dark = self.palette().window().color().lightness() < 128
        if dark:
            window, panel, field, text, border, selected = (
                "#202124", "#292a2d", "#303134", "#f1f3f4", "#5f6368", "#174ea6"
            )
        else:
            window, panel, field, text, border, selected = (
                "#f4f6f8", "#ffffff", "#ffffff", "#111111", "#aeb6bf", "#cfe8ff"
            )
        self.setStyleSheet(f"""
            QWidget {{ background:{window}; color:{text}; font-family:'맑은 고딕'; font-size:9pt; }}
            QGroupBox {{ background:{panel}; border:1px solid {border}; border-radius:4px;
                         margin-top:10px; padding:12px 8px 8px; font-weight:bold; }}
            QLineEdit {{ background:{field}; color:{text}; border:1px solid {border};
                         border-radius:2px; min-height:25px; padding:2px 5px; }}
            QPushButton {{ background:{field}; color:{text}; border:1px solid {border};
                           border-radius:3px; min-height:28px; padding:3px 10px; }}
            QTableWidget {{ background:{field}; color:{text}; gridline-color:{border};
                            selection-background-color:{selected}; selection-color:{text}; }}
            QHeaderView::section {{ background:{panel}; color:{text}; border:1px solid {border};
                                    padding:5px; font-weight:bold; }}
            QLabel#guide {{ background:{panel}; border:1px solid {border}; padding:7px; }}
        """)

    @staticmethod
    def _detail(response, fallback):
        try:
            return response.json().get("detail", fallback)
        except Exception:
            return fallback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.focusNextChild()
            return True
        return super().eventFilter(obj, event)

    def load_users(self):
        try:
            response = httpx.get(
                f"{API_BASE_URL}/users",
                params={
                    "include_inactive": str(self.include_inactive.isChecked()).lower(),
                    "search": self.search.text().strip(),
                }, timeout=10,
            )
            response.raise_for_status()
            self.users = response.json()
            begin_list_update(self.table)
            self.table.setRowCount(len(self.users))
            for row, user in enumerate(self.users):
                created = str(user.get("created_at") or "")[:19].replace("T", " ")
                values = (user["user_id"], user["user_name"],
                          "사용" if user.get("use_yn") else "사용중지", created)
                for column, value in enumerate(values):
                    item = ListTableItem(value)
                    item.setData(Qt.UserRole, user["user_id"])
                    self.table.setItem(row, column, item)
            end_list_update(self.table, (120, 140, 80, 130), (240, 300, 120, 220))
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

    def _find_user(self, user_id):
        return next((row for row in self.users if row["user_id"] == user_id), None)

    def on_selected(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return
        user = self._find_user(self.table.item(row, 0).data(Qt.UserRole))
        if not user:
            return
        self.current_user_id = user["user_id"]
        self.user_id.setText(user["user_id"])
        self.user_id.setReadOnly(True)
        self.user_name.setText(user["user_name"])
        self.password.clear()
        self.password_confirm.clear()
        self.status_label.setText("사용" if user.get("use_yn") else "사용중지")
        self.btn_status.setText("사용중지 [F6]" if user.get("use_yn") else "사용재개 [F6]")
        self.btn_status.setEnabled(user["user_id"] != app_context.user_id or not user.get("use_yn"))

    def new_user(self):
        self.current_user_id = None
        self.table.clearSelection()
        self.user_id.setReadOnly(False)
        self.user_id.clear()
        self.user_name.clear()
        self.password.clear()
        self.password_confirm.clear()
        self.status_label.setText("신규 (저장 후 사용)")
        self.btn_status.setEnabled(False)
        self.user_id.setFocus()

    def cancel_edit(self):
        selected = self.table.selectedItems()
        if selected:
            self.on_selected()
        else:
            self.new_user()

    def save_user(self):
        user_id = self.user_id.text().strip()
        name = self.user_name.text().strip()
        password = self.password.text()
        confirm = self.password_confirm.text()
        if not user_id or not name:
            QMessageBox.warning(self, "입력 확인", "사용자 ID와 사용자명을 입력하세요.")
            return
        if not self.current_user_id and not password:
            QMessageBox.warning(self, "입력 확인", "신규 사용자의 초기 비밀번호를 입력하세요.")
            return
        if password and len(password) < 4:
            QMessageBox.warning(self, "입력 확인", "비밀번호는 4자 이상 입력하세요.")
            return
        if password != confirm:
            QMessageBox.warning(self, "입력 확인", "비밀번호와 확인값이 일치하지 않습니다.")
            return
        try:
            if self.current_user_id:
                response = httpx.put(
                    f"{API_BASE_URL}/users/{self.current_user_id}",
                    json={"user_name": name, "new_password": password or None},
                    timeout=10,
                )
            else:
                response = httpx.post(
                    f"{API_BASE_URL}/users",
                    json={"user_id": user_id, "user_name": name,
                          "initial_password": password, "use_yn": True}, timeout=10,
                )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response, response.text))
            QMessageBox.information(self, "저장 완료", "사용자 정보가 저장되었습니다.")
            self.load_users()
            self.new_user()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def toggle_status(self):
        user = self._find_user(self.current_user_id)
        if not user:
            QMessageBox.warning(self, "선택 확인", "사용자를 먼저 선택하세요.")
            return
        target = not bool(user.get("use_yn"))
        action = "사용재개" if target else "사용중지"
        if QMessageBox.question(
            self, f"{action} 확인", f"{user['user_name']} 계정을 {action}하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            response = httpx.put(
                f"{API_BASE_URL}/users/{user['user_id']}/status",
                json={"use_yn": target, "actor_user_id": app_context.user_id or ""},
                timeout=10,
            )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response, response.text))
            QMessageBox.information(self, "처리 완료", f"계정을 {action}했습니다.")
            self.load_users()
        except Exception as exc:
            QMessageBox.critical(self, "처리 오류", str(exc))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F2:
            self.new_user()
        elif event.key() == Qt.Key_F4:
            self.save_user()
        elif event.key() == Qt.Key_F5:
            self.cancel_edit()
        elif event.key() == Qt.Key_F6:
            self.toggle_status()
        elif event.key() == Qt.Key_F7:
            self.load_users()
        else:
            super().keyPressEvent(event)

    def close_window(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QMdiSubWindow):
                parent.close()
                return
            parent = parent.parentWidget()
        self.close()
