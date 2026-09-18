"""상품매입 작성·조회·확정과 국내입고/LOT 생성 화면."""

from decimal import Decimal, ROUND_CEILING
import api_client as httpx
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
from app_context import app_context

API_BASE_URL = "http://127.0.0.1:8000/api/v1"
COLUMNS = ["상품 검색 *", "입고창고 *", "BOX *", "평균중량", "중량(KG) *", "단가 *",
           "과세", "공급가액", "세액", "합계", "이력번호", "BL번호", "미트와치", "LOT 결과", "메모"]


def _won(value):
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_CEILING))


class SearchCombo(QComboBox):
    """키워드 입력 후 Enter로 서버검색하는 선택상자."""
    def __init__(self, callback, placeholder):
        super().__init__(); self.setEditable(True); self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)
        self.lineEdit().returnPressed.connect(lambda: callback(self))

    def set_result(self, text, value, payload=None):
        self.clear(); self.addItem(text, value); self.setItemData(0, payload or {}, Qt.UserRole + 1)
        self.setCurrentIndex(0)


class PurchaseRegWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.current_id = None; self.saved = []; self.warehouses = []
        self._loading = False; self._payable_values = (0, 0)
        self._build_ui(); self.load_base_options(); self.load_all(); self.new_document()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("상품매입등록"); title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        root.addWidget(QLabel("상품매입 전용입니다. 확정하면 국내입고·LOT·재고와 미지급 원거래가 함께 생성됩니다. 경비매입은 별도 처리합니다."))

        header = QGroupBox("상품매입 Header"); hl = QHBoxLayout(header)
        hl.addWidget(QLabel("업무회사")); hl.addWidget(QLabel(app_context.company_name or app_context.company_code))
        hl.addWidget(QLabel("매입일 *")); self.purchase_date = QDateEdit(QDate.currentDate())
        self.purchase_date.setCalendarPopup(True); self.purchase_date.setDisplayFormat("yyyy-MM-dd"); hl.addWidget(self.purchase_date)
        hl.addWidget(QLabel("매입처 검색 *"))
        self.supplier = SearchCombo(self.search_suppliers, "상호·코드·사업자번호 입력 후 Enter")
        self.supplier.setMinimumWidth(330); hl.addWidget(self.supplier)
        hl.addWidget(QLabel("상태")); self.status = QLabel("작성중")
        self.status.setStyleSheet("font-weight:700;color:#1d4ed8;"); hl.addWidget(self.status); hl.addStretch()
        root.addWidget(header)

        payable = QGroupBox("매입처 미지급 현황"); pl = QHBoxLayout(payable)
        self.previous_payable = QLabel(); self.current_purchase = QLabel()
        self.today_payment = QLabel(); self.current_payable = QLabel()
        for label in (self.previous_payable, self.current_purchase, self.today_payment, self.current_payable):
            label.setStyleSheet("font-size:14px;font-weight:700;padding:4px 12px;"); pl.addWidget(label)
        pl.addStretch(); root.addWidget(payable)

        buttons = QHBoxLayout()
        self.btn_search = QPushButton("조회 [F7]"); self.btn_new = QPushButton("신규 [F2]")
        self.btn_add = QPushButton("＋ 행 추가"); self.btn_remove = QPushButton("－ 행 삭제")
        self.btn_save = QPushButton("저장 [F4]"); self.btn_delete = QPushButton("삭제 [F6]")
        self.btn_confirm = QPushButton("확정(입고·LOT 생성)"); self.btn_cancel = QPushButton("전표취소")
        for button in (self.btn_search, self.btn_new, self.btn_add, self.btn_remove,
                       self.btn_save, self.btn_delete, self.btn_confirm, self.btn_cancel):
            buttons.addWidget(button)
        buttons.addStretch(); root.addLayout(buttons)

        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems); self.table.setAlternatingRowColors(True)
        for col, width in enumerate((270, 190, 65, 90, 100, 100, 60, 110, 90, 110, 150, 170, 85, 150, 160)):
            self.table.setColumnWidth(col, width)
        root.addWidget(self.table, 2)
        totals = QHBoxLayout(); totals.addStretch()
        self.total_label = QLabel(); self.total_label.setStyleSheet("font-size:16px;font-weight:700;")
        totals.addWidget(self.total_label); root.addLayout(totals)
        self.memo = QTextEdit(); self.memo.setPlaceholderText("Header 메모"); self.memo.setMaximumHeight(50); root.addWidget(self.memo)

        root.addWidget(QLabel("저장된 상품매입전표 — 확정 전표는 LOT 결과까지 표시됩니다."))
        self.saved_table = QTableWidget(0, 9)
        self.saved_table.setHorizontalHeaderLabels(["전표번호", "매입일", "매입처", "상태", "BOX", "KG", "매입액", "LOT", "BL번호"])
        self.saved_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.saved_table.setEditTriggers(QAbstractItemView.NoEditTriggers); root.addWidget(self.saved_table, 1)

        self.btn_search.clicked.connect(self.load_all); self.btn_new.clicked.connect(self.new_document)
        self.btn_add.clicked.connect(self.add_row); self.btn_remove.clicked.connect(self.remove_rows)
        self.btn_save.clicked.connect(self.save_data); self.btn_delete.clicked.connect(self.delete_document)
        self.btn_confirm.clicked.connect(lambda: self.change_status("confirm"))
        self.btn_cancel.clicked.connect(lambda: self.change_status("cancel"))
        self.saved_table.itemSelectionChanged.connect(self.load_selected)
        self.purchase_date.dateChanged.connect(self.load_payable_summary)
        self.supplier.currentIndexChanged.connect(self.load_payable_summary)
        self.table.itemChanged.connect(self._item_changed)

    def _option_request(self, **params):
        params["transaction_date"] = self.purchase_date.date().toString("yyyy-MM-dd")
        response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchase-options",
                             params=params, timeout=15)
        response.raise_for_status(); return response.json()

    def load_base_options(self):
        try:
            self.warehouses = self._option_request().get("warehouses", [])
            for row in range(self.table.rowCount()): self._fill_warehouse(row)
        except Exception as exc:
            QMessageBox.critical(self, "기준자료 조회 오류", self._error_text(exc))

    def search_suppliers(self, combo):
        keyword = combo.currentText().strip()
        if not keyword: return
        try:
            rows = self._option_request(supplier_query=keyword).get("suppliers", [])
            combo.clear()
            for value in rows:
                combo.addItem(f"{value['account_name']} ({value['account_code']})", value["account_id"])
            if rows: combo.showPopup()
            else: QMessageBox.information(self, "검색 결과", "조건에 맞는 사용 중인 매입거래처가 없습니다.")
        except Exception as exc:
            QMessageBox.critical(self, "매입처 검색 오류", self._error_text(exc))

    def search_products(self, combo):
        keyword = combo.currentText().strip()
        if not keyword: return
        try:
            rows = self._option_request(product_query=keyword).get("products", [])
            combo.clear()
            for value in rows:
                combo.addItem(f"{value['product_name']} ({value['product_code']})", value["product_id"])
                combo.setItemData(combo.count() - 1, value, Qt.UserRole + 1)
            if rows: combo.showPopup()
            else: QMessageBox.information(self, "검색 결과", "조건에 맞는 사용 중인 상품이 없습니다.")
        except Exception as exc:
            QMessageBox.critical(self, "상품 검색 오류", self._error_text(exc))

    def add_row(self, value=None):
        value = value or {}; row = self.table.rowCount(); self.table.insertRow(row)
        product = SearchCombo(self.search_products, "상품명·코드 입력 후 Enter")
        self.table.setCellWidget(row, 0, product)
        if value.get("product_id") is not None:
            product.set_result(f"{value.get('product_name')} ({value.get('product_code')})",
                               value["product_id"])
        warehouse = QComboBox(); self.table.setCellWidget(row, 1, warehouse)
        self._fill_warehouse(row, value.get("warehouse_id"))
        taxable = QCheckBox(); taxable.setChecked(value.get("tax_code_snapshot", "EXEMPT") == "VAT10")
        taxable.setToolTip("미체크=면세, 체크=과세 10%"); self.table.setCellWidget(row, 6, taxable)
        taxable.stateChanged.connect(lambda _, r=row: self._recalculate(r))
        lookup = QPushButton("BL 조회"); self.table.setCellWidget(row, 12, lookup)
        lookup.clicked.connect(lambda _, r=row: self.lookup_bl(r))
        for col in (2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14):
            self.table.setItem(row, col, QTableWidgetItem(""))
        defaults = {2:value.get("box_qty", 0), 4:value.get("weight", "0.00"),
                    5:value.get("unit_price", 0), 7:value.get("supply_amount", 0),
                    8:value.get("tax_amount", 0), 9:value.get("total_amount", 0),
                    10:value.get("history_no", ""), 11:value.get("bl_no", ""),
                    13:value.get("lot_code", ""), 14:value.get("memo", "")}
        for col, cell in defaults.items(): self.table.item(row, col).setText(str(cell or ""))
        for col in (3, 7, 8, 9, 13):
            self.table.item(row, col).setFlags(self.table.item(row, col).flags() & ~Qt.ItemIsEditable)
        self._recalculate(row)

    def _fill_warehouse(self, row, selected=None):
        combo = self.table.cellWidget(row, 1)
        if not isinstance(combo, QComboBox): return
        current = selected if selected is not None else combo.currentData(); combo.clear()
        for value in self.warehouses:
            combo.addItem(f"{value['warehouse_name']} ({value['warehouse_code']})", value["warehouse_id"])
        if current is not None: combo.setCurrentIndex(max(0, combo.findData(current)))

    def _item_changed(self, item):
        if not self._loading and item.column() in (2, 4, 5): self._recalculate(item.row())

    def _recalculate(self, row):
        try:
            box = int(self._text(row, 2) or 0); weight = Decimal(self._text(row, 4) or 0)
            price = Decimal(self._text(row, 5) or 0)
            average = (weight / box).quantize(Decimal("0.01")) if box else Decimal("0.00")
            supply = _won(weight * price)
            tax = _won(Decimal(supply) * 10 / 100) if self.table.cellWidget(row, 6).isChecked() else 0
            self._loading = True
            self.table.item(row, 3).setText(f"{average:,.2f}")
            self.table.item(row, 7).setText(f"{supply:,}")
            self.table.item(row, 8).setText(f"{tax:,}")
            self.table.item(row, 9).setText(f"{supply + tax:,}")
        except Exception:
            pass
        finally:
            self._loading = False; self.update_totals()

    def update_totals(self):
        def number(row, col):
            try: return Decimal(self._text(row, col) or 0)
            except Exception: return Decimal(0)
        boxes = sum(int(number(r, 2)) for r in range(self.table.rowCount()))
        weight = sum((number(r, 4) for r in range(self.table.rowCount())), Decimal(0))
        amount = sum(int(number(r, 9)) for r in range(self.table.rowCount()))
        self.total_label.setText(f"전체 합계  BOX {boxes:,} / 중량 {weight:,.2f} KG / 매입액 {amount:,}")
        self._show_current_payable(amount)

    def load_payable_summary(self):
        account_id = self.supplier.currentData()
        if account_id is None:
            self._payable_values = (0, 0); self._show_current_payable(); return
        try:
            response = httpx.get(
                f"{API_BASE_URL}/companies/{app_context.company_code}/purchase-payable-summary",
                params={"account_id": account_id,
                        "transaction_date": self.purchase_date.date().toString("yyyy-MM-dd")},
                timeout=10)
            response.raise_for_status(); value = response.json()
            self._payable_values = (int(value["previous_payable"]), int(value["today_payment"]))
            self._show_current_payable()
        except Exception as exc:
            QMessageBox.critical(self, "미지급 조회 오류", self._error_text(exc))

    def _show_current_payable(self, current=None):
        previous, payment = self._payable_values
        if current is None:
            try: current = sum(int(self._text(r, 9) or 0) for r in range(self.table.rowCount()))
            except Exception: current = 0
        self.previous_payable.setText(f"전미지급금 {previous:,}")
        self.current_purchase.setText(f"현매입액 {current:,}")
        self.today_payment.setText(f"당일출금액 {payment:,}")
        self.current_payable.setText(f"현미지급금 {previous + current - payment:,}")

    def lookup_bl(self, row):
        history_no = self._text(row, 10)
        if not history_no:
            QMessageBox.warning(self, "입력 확인", "이력번호를 먼저 입력하세요."); return
        try:
            response = httpx.get(
                f"{API_BASE_URL}/companies/{app_context.company_code}/meatwatch/bl-lookup",
                params={"history_no": history_no}, timeout=20)
            response.raise_for_status(); self.table.item(row, 11).setText(response.json()["bl_no"])
        except Exception as exc:
            QMessageBox.warning(self, "미트와치 BL 조회", self._error_text(exc))

    def _row_payload(self, row):
        product = self.table.cellWidget(row, 0); warehouse = self.table.cellWidget(row, 1)
        if product.currentData() is None: raise ValueError(f"{row + 1}행 상품을 검색하여 선택하세요.")
        if warehouse.currentData() is None: raise ValueError(f"{row + 1}행 입고창고를 선택하세요.")
        try:
            box = int(self._text(row, 2)); weight = Decimal(self._text(row, 4))
            price = int(self._text(row, 5))
        except Exception as exc:
            raise ValueError(f"{row + 1}행 BOX·중량·단가를 확인하세요.") from exc
        if box < 0 or weight <= 0 or weight.as_tuple().exponent < -2 or price < 0:
            raise ValueError(f"{row + 1}행은 BOX 정수, 중량 소수점 2자리, 단가 원 단위로 입력하세요.")
        return {"line_no":row + 1, "product_id":product.currentData(),
                "warehouse_id":warehouse.currentData(), "box_qty":box,
                "weight":str(weight), "unit_price":price,
                "taxable_yn":self.table.cellWidget(row, 6).isChecked(),
                "history_no":self._text(row, 10) or None, "bl_no":self._text(row, 11) or None,
                "supply_amount":int(self._text(row, 7) or 0),
                "tax_amount":int(self._text(row, 8) or 0),
                "total_amount":int(self._text(row, 9) or 0),
                "memo":self._text(row, 14) or None}

    def save_data(self):
        if self.supplier.currentData() is None:
            QMessageBox.warning(self, "입력 확인", "매입처를 검색하여 선택하세요."); return
        try: items = [self._row_payload(row) for row in range(self.table.rowCount())]
        except ValueError as exc:
            QMessageBox.warning(self, "입력 확인", str(exc)); return
        payload = {"purchase_date":self.purchase_date.date().toString("yyyy-MM-dd"),
                   "account_id":self.supplier.currentData(),
                   "memo":self.memo.toPlainText().strip() or None, "items":items}
        try:
            base = f"{API_BASE_URL}/companies/{app_context.company_code}/purchases"
            response = (httpx.put(f"{base}/{self.current_id}", json=payload, timeout=25)
                        if self.current_id else httpx.post(base, json=payload, timeout=25))
            response.raise_for_status(); result = response.json(); self.current_id = result["purchase_id"]
            QMessageBox.information(self, "저장 완료", f"상품매입전표 {result['purchase_no']}가 작성중 상태로 저장되었습니다.")
            self.load_all(); self._select(self.current_id)
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", self._error_text(exc))

    def load_all(self):
        try:
            response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases", timeout=15)
            response.raise_for_status(); self.saved = response.json(); self.saved_table.setRowCount(0)
            for value in self.saved:
                row = self.saved_table.rowCount(); self.saved_table.insertRow(row)
                lots = ", ".join(filter(None, (x.get("lot_code") for x in value.get("items", []))))
                bls = ", ".join(dict.fromkeys(filter(None, (x.get("bl_no") for x in value.get("items", [])))))
                cells = (value["purchase_no"], value["purchase_date"], value.get("account_name"),
                         value["document_status"], value["total_box_qty"], value["total_weight"],
                         value["total_amount"], lots, bls)
                for col, cell in enumerate(cells):
                    self.saved_table.setItem(row, col, QTableWidgetItem(str(cell or "")))
                self.saved_table.item(row, 0).setData(Qt.UserRole, value["purchase_id"])
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", self._error_text(exc))

    def load_selected(self):
        row = self.saved_table.currentRow()
        if row < 0 or not self.saved_table.item(row, 0): return
        purchase_id = self.saved_table.item(row, 0).data(Qt.UserRole)
        value = next((x for x in self.saved if x["purchase_id"] == purchase_id), None)
        if not value: return
        self.current_id = purchase_id
        self.purchase_date.setDate(QDate.fromString(value["purchase_date"], "yyyy-MM-dd"))
        self.supplier.set_result(f"{value.get('account_name')} ({value.get('account_code')})",
                                 value["account_id"])
        self.memo.setPlainText(value.get("memo") or ""); self.table.setRowCount(0); self._loading = True
        for item in value.get("items", []): self.add_row(item)
        self._loading = False; self._set_status(value["document_status"])
        self.update_totals(); self.load_payable_summary()

    def new_document(self):
        self.current_id = None; self.purchase_date.setDate(QDate.currentDate())
        self.supplier.clear(); self.supplier.setEditText(""); self.memo.clear()
        self.table.setRowCount(0); self.add_row(); self._set_status("DRAFT")
        self._payable_values = (0, 0); self.update_totals()

    def remove_rows(self):
        for row in sorted({x.row() for x in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        if self.table.rowCount() == 0: self.add_row()
        self.update_totals()

    def delete_document(self):
        if not self.current_id: return
        if QMessageBox.question(self, "전표 삭제", "작성 중인 상품매입전표를 삭제하시겠습니까?") != QMessageBox.Yes: return
        try:
            response = httpx.delete(
                f"{API_BASE_URL}/companies/{app_context.company_code}/purchases/{self.current_id}",
                timeout=15)
            response.raise_for_status(); self.load_all(); self.new_document()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def change_status(self, action):
        if not self.current_id:
            QMessageBox.warning(self, "선택 확인", "저장된 전표를 선택하세요."); return
        message = ("확정하면 입고·LOT·재고와 미지급금이 함께 생성됩니다. 계속하시겠습니까?"
                   if action == "confirm" else
                   "생성된 입고·LOT·미지급 원거래를 회수하고 취소하시겠습니까?")
        if QMessageBox.question(self, "상품매입 상태 변경", message) != QMessageBox.Yes: return
        try:
            response = httpx.post(
                f"{API_BASE_URL}/companies/{app_context.company_code}/purchases/{self.current_id}/{action}",
                timeout=25)
            response.raise_for_status(); result = response.json(); self.load_all()
            self._select(result["purchase_id"])
            lot_count = len([x for x in result["items"] if x.get("lot_code")])
            QMessageBox.information(self, "처리 완료", f"상태 {result['document_status']} / LOT {lot_count}건")
        except Exception as exc:
            QMessageBox.critical(self, "상태 변경 오류", self._error_text(exc))

    def _set_status(self, status):
        self.status.setText({"DRAFT":"작성중", "CONFIRMED":"확정", "CANCELLED":"취소"}.get(status, status))
        editable = status == "DRAFT"
        for widget in (self.table, self.purchase_date, self.supplier, self.memo,
                       self.btn_save, self.btn_delete, self.btn_add, self.btn_remove):
            widget.setEnabled(editable)
        self.btn_confirm.setEnabled(status == "DRAFT")
        self.btn_cancel.setEnabled(status == "CONFIRMED")

    def _select(self, purchase_id):
        for row in range(self.saved_table.rowCount()):
            if self.saved_table.item(row, 0).data(Qt.UserRole) == purchase_id:
                self.saved_table.selectRow(row); return

    def _text(self, row, col):
        item = self.table.item(row, col)
        return (item.text() if item else "").replace(",", "").strip()

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
