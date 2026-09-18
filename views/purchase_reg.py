"""일반 매입 작성·조회·수정·확정·취소 PySide6 화면."""

import math
from decimal import Decimal, ROUND_CEILING

import api_client as httpx
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

from app_context import app_context

API_BASE_URL = "http://127.0.0.1:8000/api/v1"
COLUMNS = ["상품 *", "손익·경비코드 *", "BOX *", "중량(KG) *", "단가 *",
           "세금코드 *", "공급가액", "세액", "합계", "메모"]


def _won(value):
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_CEILING))


class PurchaseRegWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.current_id = None
        self.saved = []
        self.options = {}
        self._loading = False
        self._build_ui()
        self.load_options()
        self.load_all()
        self.new_document()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("일반 매입등록")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        root.addWidget(QLabel("매입 금액전표만 등록합니다. 실제 입고·LOT·재고는 후속 매입입고에서 별도로 처리됩니다."))

        header = QGroupBox("매입 Header")
        hl = QHBoxLayout(header)
        hl.addWidget(QLabel("업무회사")); hl.addWidget(QLabel(app_context.company_name or app_context.company_code))
        hl.addWidget(QLabel("매입일 *")); self.purchase_date = QDateEdit(QDate.currentDate())
        self.purchase_date.setCalendarPopup(True); self.purchase_date.setDisplayFormat("yyyy-MM-dd")
        hl.addWidget(self.purchase_date)
        hl.addWidget(QLabel("매입처 *")); self.supplier = QComboBox(); self.supplier.setMinimumWidth(260)
        hl.addWidget(self.supplier)
        hl.addWidget(QLabel("상태")); self.status = QLabel("작성중")
        self.status.setStyleSheet("font-weight:700;color:#1d4ed8;"); hl.addWidget(self.status); hl.addStretch()
        root.addWidget(header)

        buttons = QHBoxLayout()
        self.btn_search = QPushButton("조회 [F7]"); self.btn_new = QPushButton("신규 [F2]")
        self.btn_add = QPushButton("＋ 행 추가"); self.btn_remove = QPushButton("－ 행 삭제")
        self.btn_save = QPushButton("저장 [F4]"); self.btn_delete = QPushButton("삭제 [F6]")
        self.btn_confirm = QPushButton("확정"); self.btn_cancel = QPushButton("전표취소")
        for button in (self.btn_search, self.btn_new, self.btn_add, self.btn_remove,
                       self.btn_save, self.btn_delete, self.btn_confirm, self.btn_cancel):
            buttons.addWidget(button)
        buttons.addStretch(); root.addLayout(buttons)

        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        for col, width in enumerate((250, 230, 70, 100, 100, 130, 110, 100, 110, 180)):
            self.table.setColumnWidth(col, width)
        root.addWidget(self.table, 2)

        total_box = QHBoxLayout(); total_box.addStretch()
        self.total_label = QLabel("BOX 0 / KG 0.00 / 공급가액 0 / 세액 0 / 합계 0")
        self.total_label.setStyleSheet("font-size:15px;font-weight:700;"); total_box.addWidget(self.total_label)
        root.addLayout(total_box)
        self.memo = QTextEdit(); self.memo.setPlaceholderText("Header 메모"); self.memo.setMaximumHeight(55); root.addWidget(self.memo)

        root.addWidget(QLabel("저장된 일반 매입전표 — 행을 선택하면 상세를 불러옵니다."))
        self.saved_table = QTableWidget(0, 8)
        self.saved_table.setHorizontalHeaderLabels(["전표번호", "매입일", "매입처", "상태", "BOX", "KG", "공급가액", "합계"])
        self.saved_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.saved_table.setEditTriggers(QAbstractItemView.NoEditTriggers); root.addWidget(self.saved_table, 1)

        self.btn_search.clicked.connect(self.load_all); self.btn_new.clicked.connect(self.new_document)
        self.btn_add.clicked.connect(self.add_row); self.btn_remove.clicked.connect(self.remove_rows)
        self.btn_save.clicked.connect(self.save_data); self.btn_delete.clicked.connect(self.delete_document)
        self.btn_confirm.clicked.connect(lambda: self.change_status("confirm"))
        self.btn_cancel.clicked.connect(lambda: self.change_status("cancel"))
        self.saved_table.itemSelectionChanged.connect(self.load_selected)
        self.purchase_date.dateChanged.connect(self.load_options)
        self.table.itemChanged.connect(self._item_changed)

    def load_options(self):
        if not app_context.company_code: return
        try:
            day = self.purchase_date.date().toString("yyyy-MM-dd")
            response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchase-options",
                                 params={"transaction_date": day}, timeout=15)
            response.raise_for_status(); self.options = response.json()
            current = self.supplier.currentData(); self.supplier.clear()
            for row in self.options.get("suppliers", []):
                self.supplier.addItem(f"{row['account_name']} ({row['account_code']})", row["account_id"])
            if current is not None: self.supplier.setCurrentIndex(max(0, self.supplier.findData(current)))
            for row in range(self.table.rowCount()):
                product = self.table.cellWidget(row, 0)
                expense = self.table.cellWidget(row, 1)
                tax = self.table.cellWidget(row, 5)
                self._fill_combos(row, {
                    "product_id": product.currentData() if isinstance(product, QComboBox) else None,
                    "expense_id": expense.currentData() if isinstance(expense, QComboBox) else None,
                    "tax_code_snapshot": tax.currentData() if isinstance(tax, QComboBox) else None,
                })
        except Exception as exc:
            QMessageBox.critical(self, "기준자료 조회 오류", self._error_text(exc))

    def add_row(self, value=None):
        value = value or {}; row = self.table.rowCount(); self.table.insertRow(row)
        for col in range(2, len(COLUMNS)):
            self.table.setItem(row, col, QTableWidgetItem(""))
        self._fill_combos(row, value)
        for col, key, default in ((2, "box_qty", 0), (3, "weight", "0.00"), (4, "unit_price", 0),
                                  (6, "supply_amount", 0), (7, "tax_amount", 0), (8, "total_amount", 0), (9, "memo", "")):
            self.table.item(row, col).setText(str(value.get(key, default) or default))
        for col in (6, 7, 8): self.table.item(row, col).setFlags(self.table.item(row, col).flags() & ~Qt.ItemIsEditable)
        self._recalculate(row)

    def _fill_combos(self, row, value=None):
        value = value or {}
        product = self.table.cellWidget(row, 0) if row < self.table.rowCount() else None
        expense = self.table.cellWidget(row, 1) if row < self.table.rowCount() else None
        tax = self.table.cellWidget(row, 5) if row < self.table.rowCount() else None
        if not isinstance(product, QComboBox): product = QComboBox(); self.table.setCellWidget(row, 0, product)
        if not isinstance(expense, QComboBox): expense = QComboBox(); self.table.setCellWidget(row, 1, expense)
        if not isinstance(tax, QComboBox): tax = QComboBox(); self.table.setCellWidget(row, 5, tax); tax.currentIndexChanged.connect(lambda _, r=row: self._recalculate(r))
        selections = ((product, self.options.get("products", []), "product_id", "product_name", value.get("product_id")),
                      (expense, self.options.get("expense_codes", []), "expense_id", "expense_name", value.get("expense_id")),
                      (tax, self.options.get("tax_codes", []), "tax_code", "tax_name", value.get("tax_code_snapshot")))
        for combo, rows, key, label, selected in selections:
            combo.blockSignals(True); combo.clear()
            for item in rows:
                combo.addItem(f"{item.get(label)} ({item.get(key)})", item.get(key))
                combo.setItemData(combo.count() - 1, item, Qt.UserRole + 1)
            if selected is not None: combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)

    def _item_changed(self, item):
        if self._loading: return
        if item.column() in (2, 3, 4): self._recalculate(item.row())

    def _recalculate(self, row):
        try:
            weight = Decimal(self.table.item(row, 3).text().replace(",", ""))
            price = Decimal(self.table.item(row, 4).text().replace(",", ""))
            tax = self.table.cellWidget(row, 5); data = tax.currentData(Qt.UserRole + 1) or {}
            supply = _won(weight * price); tax_amount = _won(Decimal(supply) * Decimal(str(data.get("tax_rate", 0))) / 100)
            self._loading = True
            self.table.item(row, 6).setText(f"{supply:,}"); self.table.item(row, 7).setText(f"{tax_amount:,}")
            self.table.item(row, 8).setText(f"{supply + tax_amount:,}")
        except Exception:
            pass
        finally:
            self._loading = False; self.update_totals()

    def update_totals(self):
        def number(row, col):
            try: return Decimal(self.table.item(row, col).text().replace(",", ""))
            except Exception: return Decimal(0)
        boxes = sum(int(number(r, 2)) for r in range(self.table.rowCount()))
        weight = sum((number(r, 3) for r in range(self.table.rowCount())), Decimal(0))
        supply = sum(int(number(r, 6)) for r in range(self.table.rowCount()))
        tax = sum(int(number(r, 7)) for r in range(self.table.rowCount()))
        self.total_label.setText(f"BOX {boxes:,} / KG {weight:,.2f} / 공급가액 {supply:,} / 세액 {tax:,} / 합계 {supply + tax:,}")

    def _row_payload(self, row):
        def text(col): return (self.table.item(row, col).text() or "").replace(",", "").strip()
        product = self.table.cellWidget(row, 0).currentData(); expense = self.table.cellWidget(row, 1).currentData()
        tax = self.table.cellWidget(row, 5).currentData()
        if product is None or expense is None or tax is None: raise ValueError(f"{row + 1}행 기준자료를 모두 선택하세요.")
        try:
            box = int(text(2)); weight = Decimal(text(3)); price = int(text(4))
        except Exception as exc: raise ValueError(f"{row + 1}행 BOX·중량·단가를 확인하세요.") from exc
        if box < 0 or weight <= 0 or weight.as_tuple().exponent < -2 or price < 0:
            raise ValueError(f"{row + 1}행은 BOX 정수, 중량 소수점 2자리, 단가 원 단위로 입력하세요.")
        return {"line_no": row + 1, "product_id": product, "expense_id": expense, "box_qty": box,
                "weight": str(weight), "unit_price": price, "tax_code": tax,
                "supply_amount": int(text(6)), "tax_amount": int(text(7)), "total_amount": int(text(8)),
                "memo": text(9) or None}

    def save_data(self):
        if self.supplier.currentData() is None: QMessageBox.warning(self, "입력 확인", "매입처를 선택하세요."); return
        try: items = [self._row_payload(row) for row in range(self.table.rowCount())]
        except ValueError as exc: QMessageBox.warning(self, "입력 확인", str(exc)); return
        payload = {"purchase_date": self.purchase_date.date().toString("yyyy-MM-dd"),
                   "account_id": self.supplier.currentData(), "memo": self.memo.toPlainText().strip() or None,
                   "items": items}
        try:
            base = f"{API_BASE_URL}/companies/{app_context.company_code}/purchases"
            response = httpx.put(f"{base}/{self.current_id}", json=payload, timeout=25) if self.current_id else httpx.post(base, json=payload, timeout=25)
            response.raise_for_status(); result = response.json(); self.current_id = result["purchase_id"]
            QMessageBox.information(self, "저장 완료", f"일반 매입전표 {result['purchase_no']}가 저장되었습니다.")
            self.load_all(); self._select(self.current_id)
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))

    def load_all(self):
        if not app_context.company_code: return
        try:
            response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases", timeout=15)
            response.raise_for_status(); self.saved = response.json(); self.saved_table.setRowCount(0)
            for value in self.saved:
                row = self.saved_table.rowCount(); self.saved_table.insertRow(row)
                values = (value["purchase_no"], value["purchase_date"], value.get("account_name"), value["document_status"],
                          value["total_box_qty"], value["total_weight"], value["total_supply_amount"], value["total_amount"])
                for col, cell in enumerate(values): self.saved_table.setItem(row, col, QTableWidgetItem(str(cell)))
                self.saved_table.item(row, 0).setData(Qt.UserRole, value["purchase_id"])
        except Exception as exc: QMessageBox.critical(self, "조회 오류", self._error_text(exc))

    def load_selected(self):
        row = self.saved_table.currentRow()
        if row < 0 or not self.saved_table.item(row, 0): return
        purchase_id = self.saved_table.item(row, 0).data(Qt.UserRole)
        value = next((item for item in self.saved if item["purchase_id"] == purchase_id), None)
        if not value: return
        self.current_id = purchase_id; self.purchase_date.setDate(QDate.fromString(value["purchase_date"], "yyyy-MM-dd"))
        self.load_options(); self.supplier.setCurrentIndex(max(0, self.supplier.findData(value["account_id"])))
        self.memo.setPlainText(value.get("memo") or ""); self.table.setRowCount(0)
        self._loading = True
        for item in value.get("items", []): self.add_row(item)
        self._loading = False; self._set_status(value["document_status"]); self.update_totals()

    def new_document(self):
        self.current_id = None; self.purchase_date.setDate(QDate.currentDate()); self.memo.clear(); self.table.setRowCount(0)
        self.add_row(); self._set_status("DRAFT")

    def remove_rows(self):
        for row in sorted({x.row() for x in self.table.selectedIndexes()}, reverse=True): self.table.removeRow(row)
        if self.table.rowCount() == 0: self.add_row()
        self.update_totals()

    def delete_document(self):
        if not self.current_id: return
        if QMessageBox.question(self, "전표 삭제", "작성 중인 전표를 삭제하시겠습니까?") != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases/{self.current_id}", timeout=15)
            response.raise_for_status(); self.load_all(); self.new_document()
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def change_status(self, action):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "저장된 전표를 선택하세요."); return
        try:
            response = httpx.post(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases/{self.current_id}/{action}", timeout=15)
            response.raise_for_status(); result = response.json(); self.load_all(); self._select(result["purchase_id"])
            QMessageBox.information(self, "처리 완료", f"전표 상태가 {result['document_status']}로 변경되었습니다.")
        except Exception as exc: QMessageBox.critical(self, "상태 변경 오류", self._error_text(exc))

    def _set_status(self, status):
        labels = {"DRAFT": "작성중", "CONFIRMED": "확정", "CANCELLED": "취소"}; self.status.setText(labels.get(status, status))
        editable = status == "DRAFT"; self.table.setEnabled(editable); self.purchase_date.setEnabled(editable)
        self.supplier.setEnabled(editable); self.memo.setEnabled(editable); self.btn_save.setEnabled(editable)
        self.btn_delete.setEnabled(editable); self.btn_add.setEnabled(editable); self.btn_remove.setEnabled(editable)
        self.btn_confirm.setEnabled(status == "DRAFT"); self.btn_cancel.setEnabled(status == "CONFIRMED")

    def _select(self, purchase_id):
        for row in range(self.saved_table.rowCount()):
            if self.saved_table.item(row, 0).data(Qt.UserRole) == purchase_id:
                self.saved_table.selectRow(row); return

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
