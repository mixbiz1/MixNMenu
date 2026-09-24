from api_config import API_BASE_URL
"""레거시 국내입고 흐름을 반영한 상품매입 입력·조회 화면."""

from decimal import Decimal, ROUND_CEILING
import api_client as httpx
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit,
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
from app_context import app_context

COLUMNS = ["상품코드/상품명 *", "입고창고 *", "BOX *", "평균중량", "중량(KG) *", "단가 *",
           "세액", "공급가액", "합계금액", "할인(+)/할증(-)", "이력번호", "BL번호",
           "LOT 결과", "메모", "과세"]

def _number(text): return (text or "").replace(",", "").strip()
def _won(value): return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_CEILING))


class AdvanceCombo(QComboBox):
    def __init__(self, advance):
        super().__init__(); self.advance = advance

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.advance(); return
        super().keyPressEvent(event)


class LookupDialog(QDialog):
    def __init__(self, parent, title, keyword, columns, fetch):
        super().__init__(parent); self.setWindowTitle(title); self.resize(820, 520)
        self.fetch, self.columns, self.selected = fetch, columns, None
        root = QVBoxLayout(self); line = QHBoxLayout(); line.addWidget(QLabel("코드·명칭 키워드"))
        self.keyword = QLineEdit(keyword); self.keyword.setPlaceholderText("일부만 입력해도 검색됩니다.")
        button = QPushButton("조회"); line.addWidget(self.keyword, 1); line.addWidget(button); root.addLayout(line)
        self.table = QTableWidget(0, len(columns)); self.table.setHorizontalHeaderLabels([x[0] for x in columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); root.addWidget(self.table)
        root.addWidget(QLabel("행을 더블클릭하거나 선택 후 Enter를 누르세요."))
        button.clicked.connect(self.search); self.keyword.returnPressed.connect(self.search)
        self.table.doubleClicked.connect(self.accept_current); self.table.itemActivated.connect(self.accept_current)
        self.search(); self.keyword.setFocus(); self.keyword.selectAll()

    def search(self):
        try:
            rows = self.fetch(self.keyword.text().strip()); self.table.setRowCount(0)
            for value in rows:
                row = self.table.rowCount(); self.table.insertRow(row)
                for col, (_, key) in enumerate(self.columns): self.table.setItem(row, col, QTableWidgetItem(str(value.get(key) or "")))
                self.table.item(row, 0).setData(Qt.UserRole, value)
            if rows: self.table.selectRow(0); self.table.setFocus()
        except Exception as exc: QMessageBox.critical(self, "조회 오류", PurchaseRegWindow._error_text(exc))

    def accept_current(self, *_):
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 0): self.selected = self.table.item(row, 0).data(Qt.UserRole); self.accept()


class PurchaseRegWindow(QWidget):
    def __init__(self):
        super().__init__(); self.current_id = None; self.saved = []; self.warehouses = []
        self._payable_values = (0, 0); self._supplier = None
        self._build_ui(); self.load_base_options(); self.load_all(); self.new_document()

    def _build_ui(self):
        root = QVBoxLayout(self); title = QLabel("상품매입등록/수정")
        title.setStyleSheet("font-size:20px;font-weight:700;"); root.addWidget(title)
        root.addWidget(QLabel("저장하면 매입전표·입고·LOT·재고·미지급 원거래가 한 번에 생성됩니다."))
        top = QHBoxLayout(); left = QGroupBox("매입일자별 전표"); ll = QVBoxLayout(left)
        dl = QHBoxLayout(); dl.addWidget(QLabel("매입일자")); self.purchase_date = QDateEdit(QDate.currentDate())
        self.purchase_date.setCalendarPopup(True); self.purchase_date.setDisplayFormat("yyyy-MM-dd")
        dl.addWidget(self.purchase_date); dl.addStretch(); ll.addLayout(dl)
        self.today_table = QTableWidget(0, 4); self.today_table.setHorizontalHeaderLabels(["순번", "거래처", "거래처명", "금액"])
        self.today_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.today_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.today_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch); self.today_table.setMaximumHeight(175)
        ll.addWidget(self.today_table); top.addWidget(left, 2)
        right = QGroupBox("전표 입력 / 조회"); form = QFormLayout(right)
        self.document_no, self.status = QLabel("신규"), QLabel("신규입력")
        sl = QHBoxLayout(); self.supplier_edit = QLineEdit(); self.supplier_edit.setPlaceholderText("거래처 코드·상호 입력 후 Enter")
        self.supplier_button = QPushButton("거래처 조회"); sl.addWidget(self.supplier_edit, 1); sl.addWidget(self.supplier_button)
        form.addRow("전표번호", self.document_no); form.addRow("상태", self.status); form.addRow("매입처 *", sl)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(55); self.memo.setPlaceholderText("전표 메모"); form.addRow("메모", self.memo)
        top.addWidget(right, 3); root.addLayout(top)
        buttons = QHBoxLayout(); self.btn_search = QPushButton("조회 [F7]"); self.btn_new = QPushButton("신규 [F2]")
        self.btn_add = QPushButton("행 추가"); self.btn_remove = QPushButton("행 삭제")
        self.btn_save = QPushButton("저장 [F4]"); self.btn_reset = QPushButton("입력취소 [F5]")
        self.btn_cancel = QPushButton("전표취소"); self.btn_history_lookup = QPushButton("이력번호 → BL 조회")
        for button in (self.btn_search, self.btn_new, self.btn_add, self.btn_remove,
                       self.btn_save, self.btn_reset, self.btn_cancel): buttons.addWidget(button)
        buttons.addStretch(); buttons.addWidget(self.btn_history_lookup); root.addLayout(buttons)
        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems); self.table.setAlternatingRowColors(True)
        for col, width in enumerate((220,135,55,70,85,85,75,95,100,100,110,120,120,120,42)):
            self.table.setColumnWidth(col, width)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(13, QHeaderView.Stretch)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root.addWidget(self.table, 1); totals = QHBoxLayout(); totals.addStretch(); self.total_label = QLabel()
        self.total_label.setStyleSheet("font-size:16px;font-weight:700;"); totals.addWidget(self.total_label); root.addLayout(totals)
        payable = QGroupBox("매입처 미지급 현황"); pl = QHBoxLayout(payable)
        self.previous_payable, self.current_purchase, self.today_payment, self.current_payable = QLabel(), QLabel(), QLabel(), QLabel()
        for label in (self.previous_payable,self.current_purchase,self.today_payment,self.current_payable):
            label.setStyleSheet("font-size:14px;font-weight:700;padding:4px 12px;"); pl.addWidget(label)
        pl.addStretch(); root.addWidget(payable)
        self.purchase_date.dateChanged.connect(self._date_changed); self.today_table.itemSelectionChanged.connect(self.load_selected)
        self.supplier_button.clicked.connect(self.lookup_supplier); self.supplier_edit.returnPressed.connect(self.lookup_supplier)
        self.supplier_edit.textEdited.connect(lambda _: self._clear_supplier_selection())
        self.btn_search.clicked.connect(self.load_all); self.btn_new.clicked.connect(self.new_document)
        self.btn_add.clicked.connect(self.add_row); self.btn_remove.clicked.connect(self.remove_rows)
        self.btn_save.clicked.connect(self.save_data); self.btn_reset.clicked.connect(self.reset_input)
        self.btn_cancel.clicked.connect(self.cancel_document); self.btn_history_lookup.clicked.connect(self.lookup_all_bl)
        for key, callback in (("F2", self.new_document), ("F4", self.save_data),
                              ("F5", self.reset_input), ("F7", self.load_all)):
            shortcut = QShortcut(QKeySequence(key), self); shortcut.activated.connect(callback)

    def _option_request(self, **params):
        params["transaction_date"] = self.purchase_date.date().toString("yyyy-MM-dd")
        response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchase-options", params=params, timeout=15)
        response.raise_for_status(); return response.json()

    def load_base_options(self):
        try: self.warehouses = self._option_request().get("warehouses", [])
        except Exception as exc: QMessageBox.critical(self, "기준자료 조회 오류", self._error_text(exc))

    def lookup_supplier(self):
        dialog = LookupDialog(self, "매입처 조회", self.supplier_edit.text(),
            [("거래처코드","account_code"),("거래처명","account_name")],
            lambda q: self._option_request(supplier_query=q).get("suppliers", []))
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            self._supplier = dialog.selected; self.supplier_edit.setText(f"{self._supplier['account_name']} ({self._supplier['account_code']})")
            self.load_payable_summary(); self._focus_product()

    def lookup_product(self, row):
        editor = self.table.cellWidget(row, 0)
        dialog = LookupDialog(self, "상품 조회", editor.text(), [("상품코드","product_code"),("상품명","product_name")],
            lambda q: self._option_request(product_query=q).get("products", []))
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            value = dialog.selected; editor.setProperty("selected", value); editor.setText(f"{value['product_code']}  {value['product_name']}")
            self.table.cellWidget(row, 14).setChecked(str(value.get("tax_type")) in {"1","VAT10"})
            self._recalculate(row); self.table.cellWidget(row, 1).setFocus()

    def add_row(self, value=None):
        value = value or {}; row = self.table.rowCount(); self.table.insertRow(row)
        product = QLineEdit(); product.setPlaceholderText("코드·상품명 입력 후 Enter")
        if value.get("product_id"):
            product.setProperty("selected", {"product_id":value["product_id"],"product_code":value.get("product_code"),"product_name":value.get("product_name")})
            product.setText(f"{value.get('product_code') or ''}  {value.get('product_name') or ''}")
        product.returnPressed.connect(lambda r=row: self.lookup_product(r))
        product.textEdited.connect(lambda _, r=row: self._clear_product_selection(r)); self.table.setCellWidget(row, 0, product)
        warehouse = AdvanceCombo(lambda r=row: self._focus_cell(r, 2))
        for option in self.warehouses: warehouse.addItem(option["warehouse_name"], option["warehouse_id"])
        if value.get("warehouse_id") is not None: warehouse.setCurrentIndex(max(0, warehouse.findData(value["warehouse_id"])))
        self.table.setCellWidget(row, 1, warehouse)
        for col, default in ((2,value.get("box_qty","")),(4,value.get("weight","0.00")),(5,value.get("unit_price","")),
                             (9,value.get("discount_amount",0)),(10,value.get("history_no","")),
                             (11,value.get("bl_no","")),(13,value.get("memo",""))):
            editor = QLineEdit(str(default or "")); self.table.setCellWidget(row, col, editor); editor.textChanged.connect(lambda _, r=row: self._recalculate(r))
        taxable = QCheckBox(); taxable.setChecked(value.get("tax_code_snapshot","EXEMPT") == "VAT10")
        taxable.setEnabled(False); taxable.setToolTip("상품코드의 과세구분과 자동 연동됩니다."); self.table.setCellWidget(row, 14, taxable)
        for col in (3,6,7,8,12): self.table.setItem(row, col, QTableWidgetItem(""))
        self.table.item(row, 12).setText(str(value.get("lot_code") or "")); self._wire_enter(row); self._recalculate(row)

    def _wire_enter(self, row):
        widgets = [self.table.cellWidget(row, col) for col in (2,4,5,9,10,11,13)]
        for index, editor in enumerate(widgets):
            def advance(i=index, r=row):
                self._format_row(r)
                if i+1 < len(widgets): widgets[i+1].setFocus(); widgets[i+1].selectAll()
                else:
                    if r == self.table.rowCount()-1: self.add_row()
                    self.table.cellWidget(r+1,0).setFocus()
            editor.returnPressed.connect(advance)

    def _focus_cell(self, row, col):
        widget = self.table.cellWidget(row, col)
        if widget:
            widget.setFocus()
            if isinstance(widget, QLineEdit): widget.selectAll()

    def _clear_supplier_selection(self):
        self._supplier = None; self._payable_values = (0, 0); self._show_current_payable()

    def _clear_product_selection(self, row):
        editor = self.table.cellWidget(row, 0)
        if editor:
            editor.setProperty("selected", None); self.table.cellWidget(row, 14).setChecked(False)
            self._recalculate(row)

    def _format_row(self, row):
        try:
            for col in (2,5,9):
                editor = self.table.cellWidget(row,col); editor.setText(f"{int(_number(editor.text()) or 0):,}")
            editor = self.table.cellWidget(row,4); editor.setText(f"{Decimal(_number(editor.text()) or 0):,.2f}")
        except Exception: pass

    def _text(self, row, col):
        widget = self.table.cellWidget(row,col)
        if isinstance(widget,QLineEdit): return _number(widget.text())
        item = self.table.item(row,col); return _number(item.text() if item else "")

    def _recalculate(self, row):
        try:
            box=int(self._text(row,2) or 0); weight=Decimal(self._text(row,4) or 0); price=Decimal(self._text(row,5) or 0)
            discount=int(self._text(row,9) or 0)
            average=(weight/box).quantize(Decimal("0.01")) if box else Decimal("0.00"); supply=_won(weight*price)
            tax=_won(Decimal(supply)/10) if self.table.cellWidget(row,14).isChecked() else 0
            total=supply+tax-discount
            for col,text in ((3,f"{average:,.2f}"),(6,f"{tax:,}" if tax else ""),
                             (7,f"{supply:,}"),(8,f"{total:,}")): self.table.item(row,col).setText(text)
        except Exception: pass
        self.update_totals()

    def update_totals(self):
        boxes=sum(int(self._text(r,2) or 0) for r in range(self.table.rowCount()))
        weight=sum((Decimal(self._text(r,4) or 0) for r in range(self.table.rowCount())),Decimal(0))
        amount=sum(int(self._text(r,8) or 0) for r in range(self.table.rowCount()))
        self.total_label.setText(f"합계  BOX {boxes:,} / 중량 {weight:,.2f} KG / 매입액 {amount:,}"); self._show_current_payable(amount)

    def lookup_all_bl(self):
        targets = [row for row in range(self.table.rowCount())
                   if self._text(row,10) and not self._text(row,11)]
        if not targets:
            QMessageBox.information(self,"이력번호 조회","이력번호가 입력되고 BL번호가 비어 있는 행이 없습니다."); return
        completed, failures = 0, []
        for row in targets:
            try:
                response=httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/meatwatch/bl-lookup",
                    params={"history_no":self._text(row,10)},timeout=20)
                response.raise_for_status(); self.table.cellWidget(row,11).setText(response.json()["bl_no"]); completed += 1
            except Exception as exc: failures.append(f"{row+1}행: {self._error_text(exc)}")
        message=f"BL번호 {completed}건을 입력했습니다."
        if failures: message += "\n\n조회 실패\n" + "\n".join(failures)
        QMessageBox.information(self,"이력번호 조회",message)

    def _row_payload(self,row):
        selected=self.table.cellWidget(row,0).property("selected"); warehouse=self.table.cellWidget(row,1)
        if not selected: raise ValueError(f"{row+1}행 상품을 조회하여 선택하세요.")
        if warehouse.currentData() is None: raise ValueError(f"{row+1}행 입고창고를 선택하세요.")
        try: box=int(self._text(row,2)); weight=Decimal(self._text(row,4)); price=int(self._text(row,5))
        except Exception as exc: raise ValueError(f"{row+1}행 BOX·중량·단가를 확인하세요.") from exc
        if box<0 or weight<=0 or weight.as_tuple().exponent < -2 or price<0: raise ValueError(f"{row+1}행은 BOX 정수, 중량 소수점 2자리, 단가 원 단위로 입력하세요.")
        return {"line_no":row+1,"product_id":selected["product_id"],"warehouse_id":warehouse.currentData(),"box_qty":box,
            "weight":str(weight),"unit_price":price,"taxable_yn":self.table.cellWidget(row,14).isChecked(),
            "history_no":self._text(row,10) or None,"bl_no":self._text(row,11) or None,"supply_amount":int(self._text(row,7) or 0),
            "tax_amount":int(self._text(row,6) or 0),"discount_amount":int(self._text(row,9) or 0),
            "total_amount":int(self._text(row,8) or 0),"memo":self._text(row,13) or None}

    def save_data(self):
        if not self._supplier: QMessageBox.warning(self,"입력 확인","매입처를 조회하여 선택하세요."); return
        try: items=[self._row_payload(row) for row in range(self.table.rowCount()) if self.table.cellWidget(row,0).property("selected")]
        except ValueError as exc: QMessageBox.warning(self,"입력 확인",str(exc)); return
        if not items: QMessageBox.warning(self,"입력 확인","상품을 한 행 이상 입력하세요."); return
        verb="수정 저장" if self.current_id else "저장"
        if QMessageBox.question(self,"상품매입 저장",f"입력한 상품매입을 {verb}하시겠습니까?\n저장과 동시에 LOT와 재고가 반영됩니다.") != QMessageBox.Yes: return
        payload={"purchase_date":self.purchase_date.date().toString("yyyy-MM-dd"),"account_id":self._supplier["account_id"],
            "memo":self.memo.toPlainText().strip() or None,"finalize":True,"items":items}
        try:
            base=f"{API_BASE_URL}/companies/{app_context.company_code}/purchases"
            response=httpx.put(f"{base}/{self.current_id}",json=payload,timeout=30) if self.current_id else httpx.post(base,json=payload,timeout=30)
            response.raise_for_status(); result=response.json(); lot_count=sum(bool(x.get("lot_code")) for x in result["items"])
            self.load_all(); QMessageBox.information(self,"저장 완료",f"{result['purchase_no']} / LOT {lot_count}건이 저장되었습니다."); self.new_document(keep_date=True)
        except Exception as exc: QMessageBox.critical(self,"저장 오류",self._error_text(exc))

    def load_all(self):
        try:
            response=httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases",timeout=15)
            response.raise_for_status(); self.saved=response.json(); self.refresh_today()
        except Exception as exc: QMessageBox.critical(self,"조회 오류",self._error_text(exc))

    def refresh_today(self):
        selected_date=self.purchase_date.date().toString("yyyy-MM-dd")
        rows=[x for x in self.saved if str(x["purchase_date"])==selected_date and x["document_status"]!="CANCELLED"]
        self.today_table.setRowCount(0)
        for index,value in enumerate(rows,1):
            row=self.today_table.rowCount(); self.today_table.insertRow(row)
            for col,cell in enumerate((index,value.get("account_code"),value.get("account_name"),f"{int(value['total_amount']):,}")): self.today_table.setItem(row,col,QTableWidgetItem(str(cell or "")))
            self.today_table.item(row,0).setData(Qt.UserRole,value["purchase_id"])

    def load_selected(self):
        row=self.today_table.currentRow()
        if row<0 or not self.today_table.item(row,0): return
        purchase_id=self.today_table.item(row,0).data(Qt.UserRole); value=next((x for x in self.saved if x["purchase_id"]==purchase_id),None)
        if not value: return
        self.current_id=purchase_id; self.document_no.setText(value["purchase_no"]); self.status.setText("확정 / 수정조회")
        self._supplier={"account_id":value["account_id"],"account_code":value.get("account_code"),"account_name":value.get("account_name")}
        self.supplier_edit.setText(f"{value.get('account_name')} ({value.get('account_code')})"); self.memo.setPlainText(value.get("memo") or ""); self.table.setRowCount(0)
        for item in value.get("items",[]): self.add_row(item)
        self.update_totals(); self.load_payable_summary(); self.btn_cancel.setEnabled(True)

    def new_document(self, keep_date=False):
        self.current_id=None
        if not keep_date: self.purchase_date.setDate(QDate.currentDate())
        self._supplier=None; self.supplier_edit.clear(); self.document_no.setText("신규"); self.status.setText("신규입력"); self.memo.clear()
        self.table.setRowCount(0); self.add_row(); self._payable_values=(0,0); self.btn_cancel.setEnabled(False)
        self.update_totals(); self.today_table.clearSelection(); self.supplier_edit.setFocus()

    def remove_rows(self):
        for row in sorted({x.row() for x in self.table.selectedIndexes()},reverse=True): self.table.removeRow(row)
        if self.table.rowCount()==0: self.add_row()
        self.update_totals()

    def reset_input(self):
        if QMessageBox.question(self,"입력 취소","현재 입력 또는 수정 중인 내용을 취소하시겠습니까?") == QMessageBox.Yes:
            self.new_document(keep_date=True)

    def cancel_document(self):
        if not self.current_id: return
        if QMessageBox.question(self,"전표 취소","입고·LOT·미지급 원거래를 함께 회수하고 취소하시겠습니까?") != QMessageBox.Yes: return
        try:
            response=httpx.post(f"{API_BASE_URL}/companies/{app_context.company_code}/purchases/{self.current_id}/cancel",timeout=25)
            response.raise_for_status(); self.load_all(); self.new_document(keep_date=True)
        except Exception as exc: QMessageBox.critical(self,"취소 오류",self._error_text(exc))

    def _date_changed(self): self.refresh_today(); self.load_payable_summary()
    def _focus_product(self):
        if not self.table.rowCount(): self.add_row()
        self.table.cellWidget(0,0).setFocus()

    def load_payable_summary(self):
        if not self._supplier: self._payable_values=(0,0); self._show_current_payable(); return
        try:
            response=httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/purchase-payable-summary",
                params={"account_id":self._supplier["account_id"],"transaction_date":self.purchase_date.date().toString("yyyy-MM-dd")},timeout=10)
            response.raise_for_status(); value=response.json(); self._payable_values=(int(value["previous_payable"]),int(value["today_payment"])); self._show_current_payable()
        except Exception as exc: QMessageBox.critical(self,"미지급 조회 오류",self._error_text(exc))

    def _show_current_payable(self,current=None):
        previous,payment=self._payable_values
        if current is None: current=sum(int(self._text(r,8) or 0) for r in range(self.table.rowCount()))
        self.previous_payable.setText(f"전미지급금 {previous:,}"); self.current_purchase.setText(f"현매입액 {current:,}")
        self.today_payment.setText(f"당일출금액 {payment:,}"); self.current_payable.setText(f"현미지급금 {previous+current-payment:,}")

    @staticmethod
    def _error_text(exc):
        if isinstance(exc,httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail",exc))
            except Exception: pass
        return str(exc)
