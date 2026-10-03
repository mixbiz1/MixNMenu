import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QGroupBox, QMessageBox

from api_config import API_BASE_URL
import api_client as httpx
from app_context import app_context
from views.receipt_reg import ReceiptRegWindow
from views.table_utils import ListTableItem, begin_list_update, end_list_update


class PaymentRegWindow(ReceiptRegWindow):
    """지급은 입금 화면의 검증된 입력 UX를 유지하되 매입 미지급에 배분한다."""
    def __init__(self):
        super().__init__()
        self._rename_for_payment()

    def _rename_for_payment(self):
        replacements = {"입금관리": "지급관리", "입금 입력": "지급 입력", "입금 내역": "지급 내역", "입금일 *": "지급일 *", "입금액 *": "지급액 *", "미수 현황": "미지급 현황", "전미수": "전미지급", "금일입금": "금일지급", "현미수": "현미지급", "입금액을 등록하면 거래처 미수잔액에 자동 반영됩니다.": "지급액을 등록하면 거래처 미지급잔액에 자동 반영됩니다."}
        for widget in self.findChildren(QLabel):
            if widget.text() in replacements: widget.setText(replacements[widget.text()])
        for widget in self.findChildren(QGroupBox):
            if widget.title() in replacements: widget.setTitle(replacements[widget.title()])
        self.table.setHorizontalHeaderLabels(["지급일", "거래처", "지급액", "적요", "지급번호"])
        self.memo.setPlaceholderText("지급방법·계좌·비고 등 (음수 조정은 적요 또는 사유 필수)")

    def load_data(self):
        if self._loading: return
        self._loading = True; self.btn_search.setEnabled(False); self.btn_search.setText("조회 중...")
        try:
            accounts = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/accounts", timeout=10); accounts.raise_for_status()
            payments = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/payments", timeout=10); payments.raise_for_status()
            selected = self.account.currentData(); self.accounts = [x for x in accounts.json() if x.get("purchase_yn")]
            blocked = self.account.blockSignals(True)
            try:
                self.account.clear()
                for item in self.accounts: self.account.addItem(item["account_name"], item["account_id"])
                if self.account.count(): self.account.setCurrentIndex(max(0, self.account.findData(selected)) if selected is not None else 0)
            finally: self.account.blockSignals(blocked)
            self.rows = payments.json(); begin_list_update(self.table); self.table.setRowCount(len(self.rows))
            for row, item in enumerate(self.rows):
                for col, value in enumerate((item["payment_date"], item["account_name"], item["amount"], item.get("memo"), item["transaction_no"])):
                    cell = ListTableItem(f"{int(value):,}" if col == 2 else str(value or ""), int(value) if col == 2 else str(value or ""))
                    if col == 2: cell.setTextAlignment(0x82)
                    self.table.setItem(row, col, cell)
                self.table.item(row, 0).setData(Qt.UserRole, item["account_transaction_id"])
            end_list_update(self.table, (90,220,100,160,130), (120,420,160,420,210)); self.load_summary()
        except Exception as exc: QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally: self._loading = False; self.btn_search.setEnabled(True); self.btn_search.setText("조회")

    def load_summary(self):
        account_id = self.account.currentData()
        if account_id is None: self._set_summary_values(0, 0, 0); return
        try:
            r = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/payment-payable-summary", params={"account_id": account_id, "transaction_date": self.receipt_date.date().toString("yyyy-MM-dd")}, timeout=10); r.raise_for_status(); v=r.json()
            self._set_summary_values(int(v["previous_payable"]), int(v["today_payment"]), int(v["current_payable"]))
        except Exception: self.prev_balance.setText("조회 실패"); self.today_receipt.setText("-"); self.current_balance.setText("-")

    def on_selected(self):
        if not self.table.selectionModel().hasSelection(): return
        row=self.table.currentRow()
        if row < 0 or self.table.item(row,0) is None: return
        tx=self.table.item(row,0).data(Qt.UserRole); item=next((x for x in self.rows if x["account_transaction_id"]==tx),None)
        if not item: return
        self.current_id=tx; self.btn_delete.setEnabled(True); self.btn_save.setText("수정저장 [F4]")
        from PySide6.QtCore import QDate
        self.receipt_date.setDate(QDate.fromString(str(item["payment_date"]),"yyyy-MM-dd")); self.account.setCurrentIndex(max(0,self.account.findData(item["account_id"]))); self._set_amount_value(item["amount"]); self.memo.setText(item.get("memo") or ""); self.audit_reason.clear(); self.audit_reason_label.setVisible(True); self.audit_reason.setVisible(True); self.load_summary()

    def _enter_new_mode(self, keep_context=False):
        super()._enter_new_mode(keep_context=keep_context)

    def _set_summary_values(self, previous, today_payment, current):
        self.prev_balance.setText(f"{int(previous):,} 원")
        self.today_receipt.setText(f"{int(today_payment):,} 원")
        self.current_balance.setText(f"{int(current):,} 원")

    def save_data(self):
        if self.account.currentData() is None: QMessageBox.warning(self,"입력 확인","거래처를 선택해 주세요."); return
        if self.amount.value() == 0: QMessageBox.warning(self,"입력 확인","지급액을 입력해 주세요."); self.amount.setFocus(); return
        if self.amount.value() < 0 and not (self.memo.text().strip() or self.audit_reason.text().strip()): QMessageBox.warning(self,"입력 확인","음수 조정은 적요 또는 조정사유를 입력해 주세요."); return
        amount=math.ceil(self.amount.value()); action="수정" if self.current_id else "등록"
        if QMessageBox.question(self,"지급 저장",f"지급 {amount:,}원을 {action}하시겠습니까?") != QMessageBox.Yes: return
        payload={"payment_date":self.receipt_date.date().toString("yyyy-MM-dd"),"account_id":self.account.currentData(),"amount":amount,"memo":self.memo.text().strip() or None,"audit_reason":self.audit_reason.text().strip() or None}; url=f"{API_BASE_URL}/companies/{app_context.company_code}/payments"; editing=self.current_id
        self.btn_save.setEnabled(False); self.btn_save.setText("저장 중...")
        try:
            r=httpx.put(f"{url}/{editing}",json=payload,timeout=15) if editing else httpx.post(url,json=payload,timeout=15); r.raise_for_status(); saved=r.json(); QMessageBox.information(self,"저장 완료",f"지급 {saved['transaction_no']}가 저장되었습니다."); self.load_data()
            if editing: self.current_id=saved["account_transaction_id"]; self._select_id(self.current_id)
            else: self._enter_new_mode(keep_context=True)
        except Exception as exc: QMessageBox.critical(self,"저장 오류",self._error_text(exc))
        finally: self.btn_save.setEnabled(True); self.btn_save.setText("수정저장 [F4]" if self.current_id else "저장 [F4]")

    def delete_data(self):
        if not self.current_id: QMessageBox.warning(self,"선택 확인","삭제할 지급을 목록에서 선택해 주세요."); return
        if QMessageBox.warning(self,"지급 삭제","선택한 지급과 자동 배분내역을 삭제하시겠습니까?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        try:
            r=httpx.delete(f"{API_BASE_URL}/companies/{app_context.company_code}/payments/{self.current_id}",timeout=15); r.raise_for_status(); QMessageBox.information(self,"삭제 완료",r.json().get("message","삭제되었습니다.")); self.clear_form(); self.load_data()
        except Exception as exc: QMessageBox.critical(self,"삭제 오류",self._error_text(exc))
