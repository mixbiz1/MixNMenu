"""거래처원장 파생 조회 화면."""

from datetime import date

import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class AccountLedgerWindow(QWidget):
    COLUMNS = (
        ("transaction_date", "일자"), ("transaction_no", "전표번호"),
        ("type_label", "구분"), ("memo", "적요"), ("box_qty", "Box"),
        ("weight", "중량(Kg)"), ("unit_price", "단가"),
        ("transaction_amount", "원거래금액"),
        ("sales_amount", "매출금액"), ("receipt_amount", "수금액"),
        ("purchase_amount", "매입금액"), ("payment_amount", "지급액"),
        ("balance", "잔액"), ("reference", "LOT·이력번호"),
    )

    def __init__(self):
        super().__init__()
        self.accounts = []
        self.ledger = None
        self._loading = False
        self._build_ui()
        self.load_accounts()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("거래처원장")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)
        filters = QHBoxLayout()
        self.company = QLabel(app_context.company_name or app_context.company_code)
        self.start_date = QDateEdit(QDate.currentDate().addDays(1 - QDate.currentDate().day()))
        self.end_date = QDateEdit(QDate.currentDate())
        for control in (self.start_date, self.end_date):
            control.setCalendarPopup(True)
            control.setDisplayFormat("yyyy-MM-dd")
            control.setKeyboardTracking(False)
        self.account = QComboBox()
        self.account.setMinimumWidth(260)
        self.btn_search = QPushButton("조회")
        self.btn_search.clicked.connect(self.load_ledger)
        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.close)
        form = QFormLayout()
        form.addRow("업무회사", self.company)
        form.addRow("거래처", self.account)
        form.addRow("시작일", self.start_date)
        form.addRow("종료일", self.end_date)
        filters.addLayout(form)
        filters.addStretch(1)
        filters.addWidget(self.btn_search)
        filters.addWidget(self.btn_close)
        root.addLayout(filters)
        self.balance_summary = QLabel("전잔액: -    기간 증감: -    최종잔액: -")
        self.balance_summary.setStyleSheet("font-weight: 700; padding: 6px;")
        root.addWidget(self.balance_summary)
        self.tabs = QTabWidget()
        self.transaction_table = self._new_table([title for _, title in self.COLUMNS])
        self.daily_table = self._new_table(["일자", "Box", "중량(Kg)", "매출", "수금", "매입", "지급", "순변동"])
        self.monthly_table = self._new_table(["월", "Box", "중량(Kg)", "매출", "수금", "매입", "지급", "순변동"])
        self.period_table = self._new_table(["조회기간", "Box", "중량(Kg)", "매출", "수금", "매입", "지급", "순변동"])
        self.tabs.addTab(self.transaction_table, "거래내역")
        self.tabs.addTab(self.daily_table, "일계")
        self.tabs.addTab(self.monthly_table, "월계")
        self.tabs.addTab(self.period_table, "기간합계")
        root.addWidget(self.tabs, 1)

    @staticmethod
    def _new_table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSortingEnabled(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _display(value, key):
        if value is None:
            return ""
        if key in {"box_qty", "unit_price", "transaction_amount", "sales_amount", "receipt_amount", "purchase_amount", "payment_amount", "balance", "net_change"}:
            return f"{int(value):,}"
        if key == "weight":
            return f"{float(value):,.2f}"
        return str(value)

    def _fill_table(self, table, rows, keys):
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, key in enumerate(keys):
                cell = QTableWidgetItem(self._display(row.get(key), key))
                if key in {"box_qty", "unit_price", "transaction_amount", "sales_amount", "receipt_amount", "purchase_amount", "payment_amount", "balance", "net_change", "weight"}:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row_index, column, cell)
        table.resizeColumnsToContents()

    def load_accounts(self):
        selected = self.account.currentData()
        try:
            response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/accounts", timeout=10)
            response.raise_for_status()
            self.accounts = response.json()
            self.account.clear()
            for item in self.accounts:
                if item.get("use_yn", True) and not item.get("trade_stop_yn", False):
                    self.account.addItem(item["account_name"], item["account_id"])
            if selected is not None:
                index = self.account.findData(selected)
                if index >= 0:
                    self.account.setCurrentIndex(index)
            if self.account.count():
                self.load_ledger()
        except Exception as exc:
            QMessageBox.critical(self, "거래처 조회 오류", str(exc))

    def load_ledger(self):
        if self._loading:
            return
        account_id = self.account.currentData()
        if account_id is None:
            self._clear_results()
            return
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        if start > end:
            QMessageBox.warning(self, "조회조건 확인", "시작일은 종료일보다 늦을 수 없습니다.")
            return
        self._loading = True
        self.btn_search.setEnabled(False)
        try:
            response = httpx.get(
                f"{API_BASE_URL}/companies/{app_context.company_code}/account-ledger",
                params={"account_id": account_id, "start_date": start, "end_date": end},
                timeout=20,
            )
            response.raise_for_status()
            self.ledger = response.json()
            self._fill_table(self.transaction_table, self.ledger["transactions"], [key for key, _ in self.COLUMNS])
            summary_keys = ("box_qty", "weight", "sales_amount", "receipt_amount", "purchase_amount", "payment_amount", "net_change")
            self._fill_table(self.daily_table, [dict(day=day, **values) for day, values in self.ledger["daily_totals"].items()], ["day", *summary_keys])
            self._fill_table(self.monthly_table, [dict(month=month, **values) for month, values in self.ledger["monthly_totals"].items()], ["month", *summary_keys])
            self._fill_table(self.period_table, [dict(month=f"{start} ~ {end}", **self.ledger["period_total"])], ["month", *summary_keys])
            total = self.ledger["period_total"]
            self.balance_summary.setText(
                f"전잔액: {int(self.ledger['opening_balance']):,}원    "
                f"기간 순변동: {int(total['net_change']):,}원    "
                f"최종잔액: {int(self.ledger['ending_balance']):,}원"
            )
        except Exception as exc:
            QMessageBox.critical(self, "원장 조회 오류", str(exc))
        finally:
            self._loading = False
            self.btn_search.setEnabled(True)

    def _clear_results(self):
        self.ledger = None
        self.transaction_table.setRowCount(0)
        self.daily_table.setRowCount(0)
        self.monthly_table.setRowCount(0)
        self.period_table.setRowCount(0)
        self.balance_summary.setText("전잔액: -    기간 증감: -    최종잔액: -")
