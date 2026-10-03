from api_config import API_BASE_URL
import math
import api_client as httpx

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QDateEdit, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QMdiSubWindow,
    QComboBox,
)

from app_context import app_context
from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update


class ReceiptRegWindow(QWidget):
    """거래처 입금을 독립 원거래로 저장하고 기존 미수에 FIFO 배분한다."""

    def __init__(self):
        super().__init__()
        self.accounts = []
        self.rows = []
        self.current_id = None
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("입금관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)
        note = QLabel("입금액을 등록하면 거래처 미수잔액에 자동 반영됩니다.")
        note.setStyleSheet("color: #475569;")
        root.addWidget(note)

        body = QHBoxLayout(); root.addLayout(body)
        form_box = QGroupBox("입금 입력"); form_box.setMaximumWidth(520); form = QFormLayout(form_box)
        self.company = QLabel(app_context.company_name or app_context.company_code)
        self.receipt_date = QDateEdit(QDate.currentDate()); self.receipt_date.setCalendarPopup(True); self.receipt_date.setDisplayFormat("yyyy-M-d"); self.receipt_date.setKeyboardTracking(False)
        self.account = QComboBox(); self.account.setMinimumWidth(260)
        self.amount = QDoubleSpinBox(); self.amount.setDecimals(0); self.amount.setRange(-999999999999999, 999999999999999); self.amount.setGroupSeparatorShown(True); self.amount.setSuffix(" 원"); self.amount.lineEdit().textEdited.connect(self._format_amount_input)
        self._amount_is_blank = True
        self.memo = QLineEdit(); self.memo.setPlaceholderText("입금방법·통장·비고 등")
        self.audit_reason = QLineEdit(); self.audit_reason.setPlaceholderText("수정 사유를 입력해 주세요")
        self.prev_balance = QLabel("0 원")
        self.today_receipt = QLabel("0 원")
        self.current_balance = QLabel("0 원")
        for label in (self.prev_balance, self.today_receipt, self.current_balance):
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setStyleSheet("font-weight: 700;")
        form.addRow("업무회사", self.company)
        form.addRow("입금일 *", self.receipt_date)
        form.addRow("거래처 *", self.account)
        form.addRow("입금액 *", self.amount)
        form.addRow("적요", self.memo)
        self.audit_reason_label = QLabel("수정사유")
        form.addRow(self.audit_reason_label, self.audit_reason)
        self.audit_reason_label.setVisible(False); self.audit_reason.setVisible(False)

        balance_box = QGroupBox("미수 현황")
        balance_layout = QGridLayout(balance_box)
        balance_layout.addWidget(QLabel("전미수"), 0, 0); balance_layout.addWidget(self.prev_balance, 0, 1)
        balance_layout.addWidget(QLabel("금일입금"), 0, 2); balance_layout.addWidget(self.today_receipt, 0, 3)
        balance_layout.addWidget(QLabel("현미수"), 1, 0); balance_layout.addWidget(self.current_balance, 1, 1)
        form.addRow(balance_box)

        buttons = QHBoxLayout()
        self.btn_new = QPushButton("신규 [F2]")
        self.btn_save = QPushButton("저장 [F4]")
        self.btn_delete = QPushButton("삭제 [F6]")
        self.btn_search = QPushButton("조회 [F7]")
        self.btn_close = QPushButton("닫기")
        for button in (self.btn_new, self.btn_save, self.btn_delete, self.btn_search, self.btn_close): buttons.addWidget(button)
        form.addRow(buttons); body.addWidget(form_box, 0)

        list_box = QGroupBox("입금 내역"); ll = QVBoxLayout(list_box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["입금일", "거래처", "입금액", "적요", "입금번호"])
        configure_list_table(self.table, (100, 300, 120, 260, 160))
        self.table.setAlternatingRowColors(True); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        ll.addWidget(self.table); body.addWidget(list_box, 1)

        self.btn_new.clicked.connect(self.clear_form)
        self.btn_save.clicked.connect(self.save_data)
        self.btn_delete.clicked.connect(self.delete_data)
        self.btn_search.clicked.connect(self.load_data)
        self.btn_close.clicked.connect(self.close_window)
        self.table.itemSelectionChanged.connect(self.on_selected)
        self.account.currentIndexChanged.connect(self.load_summary)
        self.receipt_date.dateChanged.connect(self.load_summary)
        self.btn_new.setShortcut("F2"); self.btn_save.setShortcut("F4"); self.btn_delete.setShortcut("F6"); self.btn_search.setShortcut("F7")
        self.btn_delete.setEnabled(False)
        self.nav = [self.receipt_date, self.account, self.amount, self.memo]
        for widget in self.nav: widget.installEventFilter(self)
        self._set_amount_blank()

    def _format_amount_input(self, _text):
        """입금액을 입력하는 동안에도 3자리 쉼표를 즉시 표시한다."""
        if getattr(self, "_formatting_amount", False):
            return
        editor = self.amount.lineEdit()
        raw = editor.text()
        suffix = self.amount.suffix()
        # 신규 상태는 숫자와 단위를 모두 비운다. 첫 키 입력 때 단위를 복구하되
        # 사용자가 방금 입력한 문자열은 그대로 보존한다.
        if self._amount_is_blank:
            self._amount_is_blank = False
            self.amount.setSuffix(" 원")
            editor.setText(raw)
            suffix = self.amount.suffix()
        core = raw[:-len(suffix)] if suffix and raw.endswith(suffix) else raw
        negative = core.strip().startswith("-")
        digits = "".join(ch for ch in core if ch.isdigit())
        cursor = editor.cursorPosition()
        digits_before = sum(ch.isdigit() for ch in raw[:cursor])
        self._formatting_amount = True
        try:
            if not digits:
                editor.setText("-" if negative else "")
                return
            value = int(digits) * (-1 if negative else 1)
            value = max(int(self.amount.minimum()), min(value, int(self.amount.maximum())))
            self.amount.setValue(value)
            display = editor.text()
            editable_end = max(0, len(display) - len(suffix)) if suffix else len(display)
            if digits_before <= 0:
                editor.setCursorPosition(0)
                return
            seen = 0
            pos = 0
            while pos < editable_end:
                if display[pos].isdigit():
                    seen += 1
                    if seen >= digits_before:
                        pos += 1
                        break
                pos += 1
            editor.setCursorPosition(min(pos, editable_end))
        finally:
            self._formatting_amount = False

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
            receipts = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/receipts", timeout=10); receipts.raise_for_status()
            selected = self.account.currentData()
            self.accounts = [x for x in accounts.json() if x.get("sales_yn")]
            # 거래처 Combo 재구성 중 currentIndexChanged가 매 항목마다 미수조회 API를
            # 호출하지 않도록 Signal을 잠근다. 화면 오픈 지연의 주 원인을 제거한다.
            previous_block = self.account.blockSignals(True)
            try:
                self.account.clear()
                for item in self.accounts:
                    self.account.addItem(item["account_name"], item["account_id"])
                if selected is not None:
                    index = self.account.findData(selected)
                    self.account.setCurrentIndex(index if index >= 0 else 0)
                elif self.account.count():
                    self.account.setCurrentIndex(0)
            finally:
                self.account.blockSignals(previous_block)
            self.rows = receipts.json()
            begin_list_update(self.table); self.table.setRowCount(len(self.rows))
            for row, item in enumerate(self.rows):
                values = (item["receipt_date"], item["account_name"], item["amount"], item.get("memo"), item["transaction_no"])
                for col, value in enumerate(values):
                    display = f"{int(value):,}" if col == 2 else str(value or "")
                    sort_value = int(value) if col == 2 else str(value or "")
                    cell = ListTableItem(display, sort_value)
                    if col == 2: cell.setTextAlignment(0x82)
                    self.table.setItem(row, col, cell)
                self.table.item(row, 0).setData(Qt.UserRole, item["account_transaction_id"])
            end_list_update(self.table, (90, 220, 100, 160, 130), (120, 420, 160, 420, 210))
            self.load_summary()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally:
            self._loading = False; self.btn_search.setEnabled(True); self.btn_search.setText("조회")

    def load_summary(self):
        account_id = self.account.currentData()
        if account_id is None:
            self._set_summary_values(0, 0, 0)
            return
        try:
            response = httpx.get(
                f"{API_BASE_URL}/companies/{app_context.company_code}/sales-receivable-summary",
                params={"account_id": account_id, "transaction_date": self.receipt_date.date().toString("yyyy-MM-dd")}, timeout=10,
            )
            response.raise_for_status(); value = response.json()
            self._set_summary_values(
                int(value["previous_receivable"]),
                int(value["today_receipt"]),
                int(value["current_receivable"]),
            )
        except Exception:
            self.prev_balance.setText("조회 실패")
            self.today_receipt.setText("-")
            self.current_balance.setText("-")

    def _set_summary_values(self, previous, today_receipt, current):
        self.prev_balance.setText(f"{int(previous):,} 원")
        self.today_receipt.setText(f"{int(today_receipt):,} 원")
        self.current_balance.setText(f"{int(current):,} 원")

    def _set_amount_blank(self):
        """신규 입력에서는 0원 대신 금액 편집란 전체를 비워 둔다."""
        self._amount_is_blank = True
        self.amount.setSuffix("")
        self.amount.setValue(0)
        self.amount.lineEdit().clear()

    def _set_amount_value(self, value):
        self._amount_is_blank = False
        self.amount.setSuffix(" 원")
        self.amount.setValue(float(value))

    def _enter_new_mode(self, keep_context=False):
        """신규 입력은 기존 전표 선택상태와 완전히 분리한다."""
        self.current_id = None
        if not keep_context:
            self.receipt_date.setDate(QDate.currentDate())
        self._set_amount_blank()
        self.memo.clear()
        self.audit_reason.clear()
        self.table.clearSelection()
        self.audit_reason_label.setVisible(False)
        self.audit_reason.setVisible(False)
        self.btn_delete.setEnabled(False)
        self.btn_save.setText("저장 [F4]")
        (self.amount if keep_context else self.receipt_date).setFocus()
        self.load_summary()

    def clear_form(self):
        self._enter_new_mode(keep_context=False)

    def on_selected(self):
        # clearSelection() 뒤에도 currentRow는 남을 수 있으므로 실제 선택 여부를 기준으로 수정모드에 진입한다.
        if not self.table.selectionModel().hasSelection():
            return
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None: return
        transaction_id = self.table.item(row, 0).data(Qt.UserRole)
        item = next((x for x in self.rows if x["account_transaction_id"] == transaction_id), None)
        if not item: return
        self.current_id = transaction_id
        self.btn_delete.setEnabled(True)
        self.btn_save.setText("수정저장 [F4]")
        self.receipt_date.setDate(QDate.fromString(str(item["receipt_date"]), "yyyy-MM-dd"))
        self.account.setCurrentIndex(max(0, self.account.findData(item["account_id"])))
        self._set_amount_value(item["amount"]); self.memo.setText(item.get("memo") or ""); self.audit_reason.clear()
        self.audit_reason_label.setVisible(True); self.audit_reason.setVisible(True)
        self.load_summary()

    def save_data(self):
        if self.account.currentData() is None: QMessageBox.warning(self, "입력 확인", "거래처를 선택해 주세요."); return
        if self.amount.value() <= 0: QMessageBox.warning(self, "입력 확인", "입금액을 입력해 주세요."); self.amount.setFocus(); return
        rounded = math.ceil(self.amount.value()); action = "수정" if self.current_id else "등록"
        if QMessageBox.question(self, "입금 저장", f"입금 {rounded:,}원을 {action}하시겠습니까?") != QMessageBox.Yes: return
        payload = {
            "receipt_date": self.receipt_date.date().toString("yyyy-MM-dd"),
            "account_id": self.account.currentData(), "amount": rounded,
            "memo": self.memo.text().strip() or None, "audit_reason": self.audit_reason.text().strip() or None,
        }
        self.btn_save.setEnabled(False); self.btn_save.setText("저장 중...")
        try:
            url = f"{API_BASE_URL}/companies/{app_context.company_code}/receipts"
            editing_id = self.current_id
            response = httpx.put(f"{url}/{editing_id}", json=payload, timeout=15) if editing_id else httpx.post(url, json=payload, timeout=15)
            response.raise_for_status(); saved = response.json(); QMessageBox.information(self, "저장 완료", f"입금 {saved['transaction_no']}가 저장되었습니다.")
            self.load_data()
            if editing_id:
                self.current_id = saved["account_transaction_id"]
                self._select_id(self.current_id)
            else:
                # 신규 저장 후에는 같은 거래처/입금일을 유지하고 다음 입금을 바로 추가할 수 있게 신규 상태로 복귀한다.
                self._enter_new_mode(keep_context=True)
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", self._error_text(exc))
        finally:
            self.btn_save.setEnabled(True)
            self.btn_save.setText("수정저장 [F4]" if self.current_id else "저장 [F4]")

    def delete_data(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "삭제할 입금을 목록에서 선택해 주세요."); return
        if QMessageBox.warning(self, "입금 삭제", "선택한 입금과 자동 배분내역을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/companies/{app_context.company_code}/receipts/{self.current_id}", timeout=15)
            response.raise_for_status(); QMessageBox.information(self, "삭제 완료", response.json().get("message", "삭제되었습니다.")); self.clear_form(); self.load_data()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def _select_id(self, transaction_id):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == transaction_id:
                self.table.selectRow(row); return

    def open_source_id(self, transaction_id):
        """원장에서 전달된 입금/지급 원거래 ID를 선택해 수정모드로 연다."""
        self.load_data()
        if not any(int(item["account_transaction_id"]) == int(transaction_id) for item in self.rows):
            return False
        self._select_id(int(transaction_id))
        return self.current_id == int(transaction_id)

    def close_window(self):
        parent = self.parentWidget(); parent.close() if isinstance(parent, QMdiSubWindow) else self.close()

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
