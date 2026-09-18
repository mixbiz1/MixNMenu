import api_client as httpx

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMdiSubWindow,
)


API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class UserPermissionWindow(QWidget):
    """사용자별 업무회사와 메뉴 CRUD 권한을 한 번에 저장한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.users = []
        self.current_user_id = None
        self.setWindowTitle("사용자별 프로그램 권한")
        self.resize(1120, 700)
        self._build_ui()
        QTimer.singleShot(50, self.load_users)

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("사용자"))
        self.user_list = QListWidget()
        self.user_list.setMaximumHeight(110)
        top.addWidget(self.user_list, 1)
        self.btn_refresh = QPushButton("새로고침 [F7]")
        self.btn_save = QPushButton("권한저장 [F4]")
        self.btn_close = QPushButton("닫기")
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_save)
        top.addWidget(self.btn_close)
        root.addLayout(top)

        self.guide = QLabel("일반 사용자는 업무회사를 1곳 이상 지정합니다. 조회 권한이 없는 메뉴는 실행할 수 없습니다.")
        self.guide.setWordWrap(True)
        root.addWidget(self.guide)

        split = QSplitter(Qt.Horizontal)
        self.company_list = QListWidget()
        self.company_list.setAlternatingRowColors(True)
        split.addWidget(self.company_list)

        self.menu_table = QTableWidget(0, 7)
        self.menu_table.setHorizontalHeaderLabels(["그룹", "메뉴", "메뉴코드", "조회", "등록", "수정", "삭제"])
        self.menu_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.menu_table.verticalHeader().setVisible(False)
        self.menu_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.menu_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.menu_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for col in (3, 4, 5, 6):
            self.menu_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        split.addWidget(self.menu_table)
        split.setSizes([330, 790])
        root.addWidget(split, 1)

        self.user_list.currentItemChanged.connect(self.load_access)
        self.btn_refresh.clicked.connect(self.load_users)
        self.btn_save.clicked.connect(self.save_access)
        self.btn_close.clicked.connect(self.close_window)

    @staticmethod
    def _detail(response):
        try:
            return response.json().get("detail", response.text)
        except Exception:
            return response.text

    def load_users(self):
        try:
            response = httpx.get(f"{API_BASE_URL}/users", params={"include_inactive": "true"}, timeout=10)
            response.raise_for_status()
            self.users = response.json()
            selected = self.current_user_id
            self.user_list.clear()
            for user in self.users:
                state = "사용" if user.get("use_yn") else "중지"
                admin = " / 관리자" if user.get("is_admin") else ""
                item = QListWidgetItem(f"{user['user_id']}  {user['user_name']}  [{state}{admin}]")
                item.setData(Qt.UserRole, user["user_id"])
                self.user_list.addItem(item)
                if user["user_id"] == selected:
                    self.user_list.setCurrentItem(item)
            if self.user_list.count() and self.user_list.currentRow() < 0:
                self.user_list.setCurrentRow(0)
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

    def load_access(self, current, _previous=None):
        if current is None:
            return
        self.current_user_id = current.data(Qt.UserRole)
        try:
            response = httpx.get(f"{API_BASE_URL}/users/{self.current_user_id}/access", timeout=10)
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response))
            data = response.json()
            is_admin = bool(data.get("is_admin"))
            self.company_list.clear()
            for company in data["companies"]:
                item = QListWidgetItem(f"{company['comp_code']}  {company['comp_name']}")
                item.setData(Qt.UserRole, company["comp_code"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if company["allowed"] else Qt.Unchecked)
                self.company_list.addItem(item)

            self.menu_table.setRowCount(len(data["menus"]))
            for row, menu in enumerate(data["menus"]):
                for col, value in enumerate((menu["menu_group"], menu["menu_name"], menu["menu_code"])):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.menu_table.setItem(row, col, item)
                values = (
                    menu.get("can_read", False), menu.get("can_create", False),
                    menu.get("can_update", False), menu.get("can_delete", False),
                )
                for col, checked in zip((3, 4, 5, 6), values):
                    box = QCheckBox()
                    box.setChecked(checked)
                    box.setEnabled(not is_admin)
                    box.setStyleSheet("margin-left:18px")
                    self.menu_table.setCellWidget(row, col, box)
            self.company_list.setEnabled(not is_admin)
            self.btn_save.setEnabled(not is_admin)
            self.guide.setText(
                "관리자는 전체 회사와 모든 메뉴 권한이 고정 적용됩니다."
                if is_admin else
                "업무회사를 1곳 이상 지정하고 메뉴별 조회·등록·수정/삭제 권한을 저장합니다."
            )
        except Exception as exc:
            QMessageBox.critical(self, "권한 조회 오류", str(exc))

    def save_access(self):
        if not self.current_user_id:
            return
        companies = [
            self.company_list.item(i).data(Qt.UserRole)
            for i in range(self.company_list.count())
            if self.company_list.item(i).checkState() == Qt.Checked
        ]
        permissions = []
        for row in range(self.menu_table.rowCount()):
            read = self.menu_table.cellWidget(row, 3).isChecked()
            create = self.menu_table.cellWidget(row, 4).isChecked()
            update = self.menu_table.cellWidget(row, 5).isChecked()
            delete = self.menu_table.cellWidget(row, 6).isChecked()
            permissions.append({
                "menu_code": self.menu_table.item(row, 2).text(),
                "can_read": read, "can_create": create,
                "can_update": update, "can_delete": delete,
            })
        try:
            response = httpx.put(
                f"{API_BASE_URL}/users/{self.current_user_id}/access",
                json={"company_codes": companies, "menu_permissions": permissions}, timeout=15,
            )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response))
            QMessageBox.information(self, "저장 완료", "업무회사 및 메뉴 권한을 저장했습니다.")
            self.load_access(self.user_list.currentItem())
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F4:
            self.save_access()
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
