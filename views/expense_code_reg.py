import httpx

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMdiSubWindow,
)


API_BASE_URL = "http://127.0.0.1:8000/api/v1"

SECTION_LABELS = {
    "SALES": "매출",
    "PURCHASE": "매입·매출원가",
    "SGA": "판매관리비",
    "NON_OPERATING_INCOME": "영업외수익",
    "NON_OPERATING_EXPENSE": "영업외비용",
}


class ExpenseCodeWindow(QWidget):
    """손익계산서·경비통계에 사용할 계층형 경비코드 관리 화면."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_expense_id = None
        self.codes = []
        self.setWindowTitle("경비코드입력")
        self.resize(1180, 720)
        self._build_ui()
        self._apply_style()
        QTimer.singleShot(50, self.load_codes)

    def _build_ui(self):
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("경비코드 계층관리"))
        toolbar.addStretch()
        self.include_inactive = QCheckBox("사용중지 포함")
        self.btn_refresh = QPushButton("조회 [F7]")
        self.btn_new = QPushButton("최상위 신규 [F2]")
        self.btn_child = QPushButton("하위코드 추가")
        self.btn_save = QPushButton("저장 [F4]")
        self.btn_delete = QPushButton("삭제 [F6]")
        self.btn_close = QPushButton("닫기")
        for widget in (
            self.include_inactive, self.btn_refresh, self.btn_new, self.btn_child,
            self.btn_save, self.btn_delete, self.btn_close,
        ):
            toolbar.addWidget(widget)
        root.addLayout(toolbar)

        guide = QLabel(
            "매출·매입·판매관리비 등 손익구분 아래에 필요한 코드를 최대 4단계로 구성합니다. "
            "삭제는 자료연결 안전을 위해 선택 코드와 하위코드를 사용중지합니다."
        )
        guide.setWordWrap(True)
        guide.setObjectName("guide")
        root.addWidget(guide)

        splitter = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["경비코드 / 계층"])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        splitter.addWidget(self.tree)

        detail = QGroupBox("경비코드 정보")
        form = QFormLayout(detail)
        self.expense_code = QLineEdit()
        self.expense_code.setReadOnly(True)
        self.expense_code.setPlaceholderText("자동발번")
        self.expense_name = QLineEdit()
        self.parent_code = QComboBox()
        self.statement_section = QComboBox()
        for value, label in SECTION_LABELS.items():
            self.statement_section.addItem(label, value)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 9999)
        self.use_yn = QCheckBox("사용")
        self.use_yn.setChecked(True)
        self.description = QTextEdit()
        self.description.setMaximumHeight(110)
        self.level_label = QLabel("1단계")
        form.addRow("경비코드 *", self.expense_code)
        form.addRow("경비명 *", self.expense_name)
        form.addRow("상위코드", self.parent_code)
        form.addRow("손익구분 *", self.statement_section)
        form.addRow("계층", self.level_label)
        form.addRow("표시순서", self.sort_order)
        form.addRow("설명", self.description)
        form.addRow("사용여부", self.use_yn)
        splitter.addWidget(detail)
        splitter.setSizes([560, 620])
        root.addWidget(splitter, 1)

        self.btn_refresh.clicked.connect(self.load_codes)
        self.include_inactive.stateChanged.connect(self.load_codes)
        self.btn_new.clicked.connect(self.new_root)
        self.btn_child.clicked.connect(self.new_child)
        self.btn_save.clicked.connect(self.save_code)
        self.btn_delete.clicked.connect(self.delete_code)
        self.btn_close.clicked.connect(self.close_window)
        self.tree.itemClicked.connect(self.on_tree_selected)
        self.parent_code.currentIndexChanged.connect(self._sync_parent_section)
        self.expense_name.installEventFilter(self)
        self.parent_code.installEventFilter(self)
        self.statement_section.installEventFilter(self)

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
            QLineEdit, QTextEdit, QComboBox, QSpinBox {{ background:{field}; color:{text};
                         border:1px solid {border}; border-radius:2px; min-height:25px; padding:2px 5px; }}
            QPushButton {{ background:{field}; color:{text}; border:1px solid {border};
                           border-radius:3px; min-height:28px; padding:3px 10px; }}
            QTreeWidget {{ background:{field}; color:{text}; border:1px solid {border};
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

    def load_codes(self):
        try:
            response = httpx.get(
                f"{API_BASE_URL}/expense-codes",
                params={"include_inactive": str(self.include_inactive.isChecked()).lower()},
                timeout=10,
            )
            response.raise_for_status()
            self.codes = response.json()
            self.tree.clear()
            items = {}
            for code in self.codes:
                state = "" if code.get("use_yn") else " [사용중지]"
                label = f"[{code['expense_code']}] {code['expense_name']}{state}"
                item = QTreeWidgetItem([label])
                item.setData(0, Qt.UserRole, code)
                items[code["expense_id"]] = item
            for code in self.codes:
                item = items[code["expense_id"]]
                parent = items.get(code.get("parent_expense_id"))
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
            self.tree.expandAll()
            self._fill_parent_combo()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

    def _fill_parent_combo(self, selected_id=None):
        self.parent_code.blockSignals(True)
        self.parent_code.clear()
        self.parent_code.addItem("상위코드 없음 (최상위)", None)
        for code in self.codes:
            if not code.get("use_yn") or code.get("expense_level", 1) >= 4:
                continue
            if code.get("expense_id") == self.current_expense_id:
                continue
            indent = "　" * max(0, code.get("expense_level", 1) - 1)
            self.parent_code.addItem(
                f"{indent}{code['expense_name']} [{code['expense_code']}]",
                code["expense_id"],
            )
        index = self.parent_code.findData(selected_id)
        self.parent_code.setCurrentIndex(index if index >= 0 else 0)
        self.parent_code.blockSignals(False)
        self._sync_parent_section()

    def _code_by_id(self, expense_id):
        return next((row for row in self.codes if row["expense_id"] == expense_id), None)

    def _sync_parent_section(self):
        parent = self._code_by_id(self.parent_code.currentData())
        if parent:
            index = self.statement_section.findData(parent["statement_section"])
            self.statement_section.setCurrentIndex(max(index, 0))
            self.statement_section.setEnabled(False)
            self.level_label.setText(f"{parent['expense_level'] + 1}단계")
        else:
            self.statement_section.setEnabled(True)
            self.level_label.setText("1단계")

    def on_tree_selected(self, item, column):
        code = item.data(0, Qt.UserRole)
        if not code:
            return
        self.current_expense_id = code["expense_id"]
        self.expense_code.setText(code["expense_code"])
        self.expense_name.setText(code["expense_name"])
        self._fill_parent_combo(code.get("parent_expense_id"))
        index = self.statement_section.findData(code["statement_section"])
        self.statement_section.setCurrentIndex(max(index, 0))
        self.level_label.setText(f"{code.get('expense_level', 1)}단계")
        self.sort_order.setValue(code.get("sort_order", 0))
        self.description.setPlainText(code.get("description") or "")
        self.use_yn.setChecked(bool(code.get("use_yn")))

    def _next_code(self):
        response = httpx.get(f"{API_BASE_URL}/expense-codes/next-code", timeout=10)
        response.raise_for_status()
        return response.json()["expense_code"]

    def new_root(self):
        self.current_expense_id = None
        self.tree.clearSelection()
        self.expense_name.clear()
        self.description.clear()
        self.sort_order.setValue(0)
        self.use_yn.setChecked(True)
        self._fill_parent_combo(None)
        try:
            self.expense_code.setText(self._next_code())
        except Exception as exc:
            QMessageBox.critical(self, "자동발번 오류", str(exc))
            return
        self.expense_name.setFocus()

    def new_child(self):
        parent_id = self.current_expense_id
        parent = self._code_by_id(parent_id)
        if not parent:
            QMessageBox.warning(self, "선택 확인", "상위 경비코드를 먼저 선택하세요.")
            return
        if parent.get("expense_level", 1) >= 4:
            QMessageBox.warning(self, "계층 확인", "경비코드는 4단계까지만 생성할 수 있습니다.")
            return
        self.current_expense_id = None
        self.expense_name.clear()
        self.description.clear()
        self.sort_order.setValue(0)
        self.use_yn.setChecked(True)
        self._fill_parent_combo(parent_id)
        try:
            self.expense_code.setText(self._next_code())
        except Exception as exc:
            QMessageBox.critical(self, "자동발번 오류", str(exc))
            return
        self.expense_name.setFocus()

    def save_code(self):
        name = self.expense_name.text().strip()
        if not self.expense_code.text().strip() or not name:
            QMessageBox.warning(self, "입력 확인", "경비코드와 경비명은 필수입니다.")
            return
        payload = {
            "expense_code": self.expense_code.text().strip().upper(),
            "expense_name": name,
            "parent_expense_id": self.parent_code.currentData(),
            "statement_section": self.statement_section.currentData(),
            "description": self.description.toPlainText().strip() or None,
            "sort_order": self.sort_order.value(),
            "use_yn": self.use_yn.isChecked(),
        }
        try:
            if self.current_expense_id:
                response = httpx.put(
                    f"{API_BASE_URL}/expense-codes/{self.current_expense_id}",
                    json=payload,
                    timeout=10,
                )
            else:
                response = httpx.post(
                    f"{API_BASE_URL}/expense-codes", json=payload, timeout=10
                )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response, response.text))
            QMessageBox.information(self, "저장 완료", "경비코드가 저장되었습니다.")
            self.load_codes()
            self.new_root()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_code(self):
        if not self.current_expense_id:
            QMessageBox.warning(self, "삭제 확인", "삭제할 경비코드를 선택하세요.")
            return
        if QMessageBox.question(
            self,
            "삭제 확인",
            "선택 경비코드와 모든 하위코드를 사용중지하시겠습니까?\n기존 자료는 삭제하지 않습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            response = httpx.delete(
                f"{API_BASE_URL}/expense-codes/{self.current_expense_id}", timeout=10
            )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response, response.text))
            self.current_expense_id = None
            self.load_codes()
            self.new_root()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", str(exc))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F2:
            self.new_root()
        elif event.key() == Qt.Key_F4:
            self.save_code()
        elif event.key() == Qt.Key_F6:
            self.delete_code()
        elif event.key() == Qt.Key_F7:
            self.load_codes()
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
