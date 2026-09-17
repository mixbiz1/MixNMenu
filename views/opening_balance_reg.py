import math
import httpx

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMdiSubWindow,
)

from app_context import app_context


API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class OpeningBalanceRegWindow(QWidget):
    """거래처 최초 미수·미지급을 부분결제 가능한 원거래로 생성한다."""

    def __init__(self):
        super().__init__()
        self.accounts = []
        self.rows = []
        self.current_id = None
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("거래처 최초잔액 등록"); title.setStyleSheet("font-size: 20px; font-weight: 700;"); root.addWidget(title)
        note = QLabel("미수금·미지급금을 기준일의 원거래로 생성합니다. 이후 부분수금·부분지급은 이 원거래에 배분됩니다."); note.setStyleSheet("color: #475569;"); root.addWidget(note)
        body = QHBoxLayout(); root.addLayout(body)

        form_box = QGroupBox("최초잔액 입력"); form_box.setMaximumWidth(440); form = QFormLayout(form_box)
        self.company = QLabel(app_context.company_name or app_context.company_code)
        self.base_date = QDateEdit(QDate.currentDate()); self.base_date.setCalendarPopup(True); self.base_date.setDisplayFormat("yyyy-M-d"); self.base_date.setKeyboardTracking(False)
        self.balance_type = QComboBox(); self.balance_type.addItem("미수금", "RECEIVABLE"); self.balance_type.addItem("미지급금", "PAYABLE")
        self.account = QComboBox(); self.account.setMinimumWidth(250)
        self.amount = QDoubleSpinBox(); self.amount.setDecimals(0); self.amount.setMaximum(999999999999999); self.amount.setGroupSeparatorShown(True); self.amount.setSuffix(" 원")
        self.memo = QLineEdit(); self.memo.setPlaceholderText("이관 근거 또는 비고")
        form.addRow("업무회사", self.company); form.addRow("기준일 *", self.base_date); form.addRow("잔액구분 *", self.balance_type)
        form.addRow("거래처 *", self.account); form.addRow("금액 *", self.amount); form.addRow("메모", self.memo)
        buttons = QHBoxLayout(); self.btn_new = QPushButton("신규 [F2]"); self.btn_save = QPushButton("저장 [F4]"); self.btn_delete = QPushButton("삭제 [F6]"); self.btn_search = QPushButton("조회 [F7]"); self.btn_close = QPushButton("닫기")
        for button in (self.btn_new,self.btn_save,self.btn_delete,self.btn_search,self.btn_close): buttons.addWidget(button)
        form.addRow(buttons); body.addWidget(form_box, 0)

        list_box = QGroupBox("등록된 최초잔액"); ll = QVBoxLayout(list_box)
        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels(["기준일","구분","거래처","원거래번호","최초금액","배분금액","미결잔액","메모"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        for col, width in enumerate((95,70,280,145,115,105,115,180)): self.table.setColumnWidth(col, width)
        self.table.setAlternatingRowColors(True); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        ll.addWidget(self.table); body.addWidget(list_box, 1)

        self.balance_type.currentIndexChanged.connect(self._filter_accounts); self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_data); self.btn_delete.clicked.connect(self.delete_data); self.btn_search.clicked.connect(self.load_data); self.btn_close.clicked.connect(self.close_window)
        self.table.itemSelectionChanged.connect(self.on_selected)
        self.btn_new.setShortcut("F2"); self.btn_save.setShortcut("F4"); self.btn_delete.setShortcut("F6"); self.btn_search.setShortcut("F7")
        self.nav = [self.base_date, self.balance_type, self.account, self.amount, self.memo]
        for widget in self.nav: widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and obj in self.nav:
            index = self.nav.index(obj)
            (self.nav[index + 1] if index + 1 < len(self.nav) else self.btn_save).setFocus()
            return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.accounts: QTimer.singleShot(0, self.load_data)

    def load_data(self):
        if self._loading: return
        self._loading = True; self.btn_search.setEnabled(False); self.btn_search.setText("조회 중...")
        try:
            accounts = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/accounts", timeout=10); accounts.raise_for_status()
            balances = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/opening-balances", timeout=10); balances.raise_for_status()
            self.accounts = accounts.json(); self._filter_accounts(); self.rows = balances.json(); self.table.setRowCount(len(self.rows))
            labels = {"RECEIVABLE":"미수금", "PAYABLE":"미지급금"}
            for row, item in enumerate(self.rows):
                values = (item["base_date"], labels.get(item["balance_type"], item["balance_type"]), item["account_name"], item["transaction_no"], item["amount"], item["allocated_amount"], item["remaining_amount"], item.get("memo"))
                for col, value in enumerate(values):
                    display = f"{int(value):,}" if col in (4,5,6) else str(value or "")
                    cell = QTableWidgetItem(display)
                    if col in (4,5,6): cell.setTextAlignment(0x82)
                    self.table.setItem(row, col, cell)
                self.table.item(row, 0).setData(Qt.UserRole, item["account_transaction_id"])
        except Exception as exc: QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally: self._loading = False; self.btn_search.setEnabled(True); self.btn_search.setText("조회")

    def _filter_accounts(self):
        selected = self.account.currentData(); self.account.clear(); kind = self.balance_type.currentData()
        flag = "sales_yn" if kind == "RECEIVABLE" else "purchase_yn"
        for item in self.accounts:
            if item.get(flag): self.account.addItem(f"{item['account_name']} ({item['account_code']})", item["account_id"])
        if selected is not None: self.account.setCurrentIndex(max(0, self.account.findData(selected)))

    def clear_form(self):
        self.current_id = None; self.base_date.setDate(QDate.currentDate()); self.amount.setValue(0); self.memo.clear(); self.account.setCurrentIndex(0); self.table.clearSelection(); self.base_date.setFocus()

    def on_selected(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None: return
        transaction_id = self.table.item(row, 0).data(Qt.UserRole)
        item = next((x for x in self.rows if x["account_transaction_id"] == transaction_id), None)
        if not item: return
        self.current_id = transaction_id
        self.base_date.setDate(QDate.fromString(str(item["base_date"]), "yyyy-MM-dd"))
        self.balance_type.setCurrentIndex(max(0, self.balance_type.findData(item["balance_type"])))
        self._filter_accounts(); self.account.setCurrentIndex(max(0, self.account.findData(item["account_id"])))
        self.amount.setValue(float(item["amount"])); self.memo.setText(item.get("memo") or "")

    def save_data(self):
        if self.account.currentData() is None: QMessageBox.warning(self, "입력 확인", "거래처를 선택해 주세요."); return
        if self.amount.value() <= 0: QMessageBox.warning(self, "입력 확인", "금액을 입력해 주세요."); self.amount.setFocus(); return
        rounded = math.ceil(self.amount.value())
        kind = "미수금" if self.balance_type.currentData() == "RECEIVABLE" else "미지급금"
        action = "수정" if self.current_id else "생성"
        if QMessageBox.question(self, "최초잔액 저장", f"{kind} {rounded:,}원을 {action}하시겠습니까?") != QMessageBox.Yes: return
        payload = {"base_date":self.base_date.date().toString("yyyy-MM-dd"),"account_id":self.account.currentData(),"balance_type":self.balance_type.currentData(),"amount":rounded,"memo":self.memo.text().strip() or None}
        self.btn_save.setEnabled(False); self.btn_save.setText("저장 중...")
        try:
            url = f"{API_BASE_URL}/companies/{app_context.company_code}/opening-balances"
            response = httpx.put(f"{url}/{self.current_id}", json=payload, timeout=15) if self.current_id else httpx.post(url, json=payload, timeout=15)
            response.raise_for_status(); saved = response.json(); QMessageBox.information(self, "저장 완료", f"원거래 {saved['transaction_no']}가 저장되었습니다.")
            self.current_id = saved["account_transaction_id"]; self.load_data(); self._select_id(self.current_id)
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))
        finally: self.btn_save.setEnabled(True); self.btn_save.setText("저장")

    def delete_data(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "삭제할 최초잔액을 목록에서 선택해 주세요."); return
        if QMessageBox.warning(self, "최초잔액 삭제", "선택한 최초잔액 원거래를 삭제하시겠습니까?\n수금·지급이 배분된 자료는 삭제되지 않습니다.", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/companies/{app_context.company_code}/opening-balances/{self.current_id}", timeout=15)
            response.raise_for_status(); QMessageBox.information(self, "삭제 완료", response.json().get("message", "삭제되었습니다.")); self.clear_form(); self.load_data()
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def _select_id(self, transaction_id):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == transaction_id:
                self.table.selectRow(row); return

    def close_window(self):
        parent = self.parentWidget(); parent.close() if isinstance(parent, QMdiSubWindow) else self.close()

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
