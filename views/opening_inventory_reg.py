import math
import httpx

from PySide6.QtCore import QDate, QEvent, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QMdiSubWindow,
)

from app_context import app_context

API_BASE_URL = "http://127.0.0.1:8000/api/v1"
COLUMNS = [
    "상품 *", "구분 *", "LOT번호", "공급자 LOT(포장표기)", "BL번호", "컨테이너",
    "이력번호", "생산일 *", "자동 소비기한", "BOX *", "KG *",
    "개별원가 *", "재고금액", "메모",
]


class EnterTableWidget(QTableWidget):
    """Enter를 오른쪽 다음 입력칸 이동으로 사용하는 업무형 표."""
    editable_columns = (0, 1, 3, 4, 5, 6, 7, 9, 10, 11, 13)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.move_next_input()
            return
        super().keyPressEvent(event)

    def move_next_input(self, row=None, column=None):
        row = self.currentRow() if row is None else row
        column = self.currentColumn() if column is None else column
        positions = [(r, c) for r in range(self.rowCount()) for c in self.editable_columns]
        try:
            index = positions.index((row, column)) + 1
        except ValueError:
            index = 0
        if index >= len(positions):
            return
        next_row, next_col = positions[index]
        self.setCurrentCell(next_row, next_col)
        widget = self.cellWidget(next_row, next_col)
        if widget:
            widget.setFocus()
        else:
            self.editItem(self.item(next_row, next_col))


class OpeningInventoryRegWindow(QWidget):
    """최초재고 조회·신규·수정·삭제와 LOT/입고 원자 저장 화면."""

    def __init__(self):
        super().__init__()
        self.products = []
        self.product_by_id = {}
        self.warehouses = []
        self.saved_headers = []
        self.current_id = None
        self._saving = False
        self._loading_row = False
        self._formatting_money = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("최초재고 등록")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        info = QLabel("상품의 원산지·EST와 소비기한 규칙을 자동 적용하며 LOT와 최초입고를 함께 저장합니다.")
        info.setStyleSheet("color:#475569;")
        root.addWidget(info)

        header = QGroupBox("최초재고 Header")
        hl = QHBoxLayout(header)
        hl.addWidget(QLabel("업무회사")); hl.addWidget(QLabel(app_context.company_name or app_context.company_code))
        hl.addSpacing(20); hl.addWidget(QLabel("기준일 *"))
        self.base_date = self._date_edit(QDate.currentDate()); hl.addWidget(self.base_date)
        hl.addSpacing(20); hl.addWidget(QLabel("창고 *"))
        self.warehouse = QComboBox(); self.warehouse.setMinimumWidth(230); hl.addWidget(self.warehouse)
        hl.addStretch(); root.addWidget(header)

        buttons = QHBoxLayout()
        self.btn_search = QPushButton("조회 [F7]"); self.btn_new = QPushButton("신규 [F2]")
        self.btn_add = QPushButton("＋ 행 추가"); self.btn_remove = QPushButton("－ 입력행 삭제")
        self.btn_save = QPushButton("저장 [F4]"); self.btn_delete = QPushButton("전표 삭제 [F6]")
        self.btn_close = QPushButton("닫기")
        for button in (self.btn_search, self.btn_new, self.btn_add, self.btn_remove,
                       self.btn_save, self.btn_delete, self.btn_close):
            buttons.addWidget(button)
        buttons.addStretch(); root.addLayout(buttons)

        splitter = QSplitter(Qt.Vertical); root.addWidget(splitter, 1)
        edit_box = QGroupBox("입력 / 수정 Detail"); el = QVBoxLayout(edit_box)
        self.table = EnterTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems); self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for col, width in enumerate((260, 75, 150, 170, 190, 125, 125, 115, 120, 70, 90, 115, 120, 150)):
            self.table.setColumnWidth(col, width)
        self.table.setMinimumHeight(240); el.addWidget(self.table); splitter.addWidget(edit_box)

        saved_box = QGroupBox("저장된 최초재고 — 선택하면 수정할 수 있습니다"); sl = QVBoxLayout(saved_box)
        self.saved_table = QTableWidget(0, 10)
        self.saved_table.setHorizontalHeaderLabels(
            ["전표번호", "기준일", "창고", "LOT번호", "상품", "BOX", "KG", "개별원가", "재고금액", "소비기한"]
        )
        self.saved_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.saved_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        sh = self.saved_table.horizontalHeader(); sh.setSectionResizeMode(QHeaderView.Interactive)
        self.saved_table.setMinimumHeight(165); sl.addWidget(self.saved_table); splitter.addWidget(saved_box)
        splitter.setSizes([350, 230])

        memo_box = QGroupBox("Header 메모"); ml = QVBoxLayout(memo_box)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(52); ml.addWidget(self.memo); root.addWidget(memo_box)

        self.btn_search.clicked.connect(self.load_all); self.btn_new.clicked.connect(self.new_document)
        self.btn_add.clicked.connect(self.add_row); self.btn_remove.clicked.connect(self.remove_rows)
        self.btn_save.clicked.connect(self.save_data); self.btn_delete.clicked.connect(self.delete_document)
        self.btn_close.clicked.connect(self.close_window); self.saved_table.itemSelectionChanged.connect(self.load_selected_document)
        self.table.itemChanged.connect(self._on_item_changed)
        self.btn_search.setShortcut("F7"); self.btn_new.setShortcut("F2")
        self.btn_save.setShortcut("F4"); self.btn_delete.setShortcut("F6")
        self.base_date.installEventFilter(self); self.warehouse.installEventFilter(self)

    @staticmethod
    def _date_edit(value):
        edit = QDateEdit(value)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-M-d")
        edit.setKeyboardTracking(False)
        return edit

    def showEvent(self, event):
        super().showEvent(event)
        if not self.products:
            QTimer.singleShot(0, self.load_all)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj is self.base_date:
                self.warehouse.setFocus()
            elif obj is self.warehouse:
                if self.table.rowCount() == 0: self.add_row()
                self.table.cellWidget(0, 0).setFocus()
            else:
                position = self._widget_position(obj)
                if position: self.table.move_next_input(*position)
            return True
        return super().eventFilter(obj, event)

    def _widget_position(self, widget):
        for row in range(self.table.rowCount()):
            for col in (0, 1, 7):
                if self.table.cellWidget(row, col) is widget:
                    return row, col
        return None

    def load_all(self):
        self.btn_search.setEnabled(False); self.btn_search.setText("조회 중...")
        try:
            products = httpx.get(f"{API_BASE_URL}/products", timeout=10); products.raise_for_status()
            warehouses = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses", timeout=10); warehouses.raise_for_status()
            saved = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/opening-inventories", timeout=15); saved.raise_for_status()
            self.products = [x for x in products.json() if x.get("use_yn", True)]
            self.product_by_id = {x["product_id"]: x for x in self.products}
            self.warehouses = [x for x in warehouses.json() if x.get("company_use_yn", True) and x.get("use_yn", True)]
            selected = self.warehouse.currentData(); self.warehouse.clear()
            for item in self.warehouses:
                self.warehouse.addItem(f"{item['warehouse_name']} ({item['warehouse_code']})", item["warehouse_id"])
            if selected is not None: self.warehouse.setCurrentIndex(max(0, self.warehouse.findData(selected)))
            self.saved_headers = saved.json(); self._fill_saved_table()
            if self.table.rowCount() == 0: self.new_document()
            else: self._refresh_product_combos()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally:
            self.btn_search.setEnabled(True); self.btn_search.setText("조회")

    def _fill_saved_table(self):
        rows = [(header, item) for header in self.saved_headers for item in header.get("items", [])]
        self.saved_table.setRowCount(len(rows))
        for row, (header, item) in enumerate(rows):
            values = (header["inbound_no"], header["base_date"], header["warehouse_name"],
                      item["lot_code"], item["product_name"], item["box_qty"], item["weight"],
                      item["individual_cost"], item["amount"], item.get("expiry_date"))
            for col, value in enumerate(values):
                if col in (5, 7, 8): display = f"{int(value):,}"
                elif col == 6: display = f"{float(value):,.2f}"
                else: display = str(value or "")
                cell = QTableWidgetItem(display); cell.setToolTip(display)
                self.saved_table.setItem(row, col, cell)
            self.saved_table.item(row, 0).setData(Qt.UserRole, header["inbound_id"])
        self._fit_columns(
            self.saved_table,
            (135, 90, 100, 145, 180, 60, 75, 100, 110, 100),
            (175, 110, 180, 210, 380, 75, 100, 140, 150, 125),
        )

    def new_document(self):
        self.current_id = None; self.base_date.setDate(QDate.currentDate()); self.memo.clear()
        self.table.setRowCount(0); self.add_row(); self.saved_table.clearSelection(); self.base_date.setFocus()

    def add_row(self, item=None):
        item = item or {}; self._loading_row = True
        try:
            row = self.table.rowCount(); self.table.insertRow(row)
            product = QComboBox(); self._fill_product_combo(product, item.get("product_id"))
            product.setProperty("inbound_item_id", item.get("inbound_item_id")); product.setProperty("lot_id", item.get("lot_id"))
            product.setToolTip(product.currentText())
            product.currentIndexChanged.connect(lambda _, w=product: self._product_changed(w)); product.installEventFilter(self)
            self.table.setCellWidget(row, 0, product)
            source = QComboBox(); source.addItem("수입", "IMPORT"); source.addItem("국내매입", "DOMESTIC")
            source.setCurrentIndex(max(0, source.findData(item.get("source_type", "IMPORT")))); source.installEventFilter(self)
            self.table.setCellWidget(row, 1, source)
            for col in range(2, len(COLUMNS)): self.table.setItem(row, col, QTableWidgetItem(""))
            self.table.item(row, 2).setText(item.get("lot_code") or "자동생성")
            self.table.item(row, 2).setToolTip(self.table.item(row, 2).text())
            self.table.item(row, 2).setFlags(self.table.item(row, 2).flags() & ~Qt.ItemIsEditable)
            mapping = {3:"business_lot_no", 4:"bl_no", 5:"container_no", 6:"history_no", 9:"box_qty", 10:"weight", 11:"individual_cost", 13:"memo"}
            for col, key in mapping.items():
                default = "0.00" if col == 10 else "0" if col in (9, 11) else ""
                value = item.get(key) if item.get(key) is not None else default
                display = f"{math.ceil(float(value)):,}" if col == 11 else str(value)
                self.table.item(row, col).setText(display); self.table.item(row, col).setToolTip(display)
            production = QDate.fromString(str(item.get("production_date") or self.base_date.date().toString("yyyy-MM-dd")), "yyyy-MM-dd")
            date_edit = self._date_edit(production if production.isValid() else self.base_date.date())
            date_edit.dateChanged.connect(lambda _, w=date_edit: self._update_expiry_for_widget(w)); date_edit.installEventFilter(self)
            self.table.setCellWidget(row, 7, date_edit)
            for col in (8, 12): self.table.item(row, col).setFlags(self.table.item(row, col).flags() & ~Qt.ItemIsEditable)
            self._update_expiry(row); self._update_amount(row); self.table.scrollToBottom()
        finally:
            self._loading_row = False
        QTimer.singleShot(0, self._fit_input_columns)

    def _fill_product_combo(self, combo, selected=None):
        combo.clear(); combo.addItem("선택", None)
        for item in self.products: combo.addItem(f"{item['product_name']} ({item['product_code']})", item["product_id"])
        if selected is not None: combo.setCurrentIndex(max(0, combo.findData(selected)))

    def _refresh_product_combos(self):
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0); selected = combo.currentData(); self._fill_product_combo(combo, selected)

    def _product_changed(self, combo):
        combo.setToolTip(combo.currentText())
        self._update_expiry_for_widget(combo)
        QTimer.singleShot(0, self._fit_input_columns)

    def _update_expiry(self, row):
        if row < 0 or row >= self.table.rowCount() or self.table.item(row, 8) is None: return
        product = self.product_by_id.get(self.table.cellWidget(row, 0).currentData())
        production = self.table.cellWidget(row, 7).date(); expiry = None
        if product:
            rule = product.get("expiry_rule") or "AUTO"
            if rule == "FROZEN_2Y": expiry = production.addYears(2).addDays(-1)
            elif rule == "DAYS" and product.get("shelf_life_days"): expiry = production.addDays(int(product["shelf_life_days"]) - 1)
            elif rule == "AUTO":
                storage = next((x.get("code_name", "") for x in product.get("attributes", []) if x.get("group_code") == "PC004"), "")
                if "냉동" in storage: expiry = production.addYears(2).addDays(-1)
        self.table.item(row, 8).setText(expiry.toString("yyyy-MM-dd") if expiry else "상품규칙 없음")

    def _update_expiry_for_widget(self, widget):
        position = self._widget_position(widget)
        if position: self._update_expiry(position[0])

    def _on_item_changed(self, item):
        if self._loading_row or self._formatting_money:
            return
        if item.column() == 11:
            try:
                display = f"{math.ceil(float(item.text().replace(',', ''))):,}"
                if item.text() != display:
                    self._formatting_money = True; item.setText(display); item.setToolTip(display)
            except ValueError:
                pass
            finally:
                self._formatting_money = False
        if item.column() in (10, 11): self._update_amount(item.row())
        if item.column() in (3, 4, 5, 6, 13):
            item.setToolTip(item.text()); QTimer.singleShot(0, self._fit_input_columns)

    def _update_amount(self, row):
        try:
            weight = round(float(self.table.item(row, 10).text().replace(",", "")), 2)
            cost = math.ceil(float(self.table.item(row, 11).text().replace(",", "")))
            self.table.item(row, 12).setText(f"{math.ceil(weight * cost):,}")
        except (ValueError, AttributeError):
            if self.table.item(row, 12): self.table.item(row, 12).setText("0")

    def _fit_input_columns(self):
        self._fit_columns(
            self.table,
            (190, 70, 145, 150, 170, 120, 120, 115, 120, 65, 75, 105, 110, 120),
            (340, 85, 190, 260, 300, 190, 190, 125, 145, 80, 105, 145, 155, 300),
        )

    @staticmethod
    def _fit_columns(table, minimums, maximums):
        """고정형 항목은 좁게, 가변형 항목은 내용에 맞춰 제한 범위 안에서 조정한다."""
        metrics = QFontMetrics(table.font())
        for col, (minimum, maximum) in enumerate(zip(minimums, maximums)):
            header_item = table.horizontalHeaderItem(col)
            texts = [header_item.text() if header_item else ""]
            for row in range(table.rowCount()):
                widget = table.cellWidget(row, col)
                if isinstance(widget, QComboBox):
                    texts.append(widget.currentText())
                else:
                    item = table.item(row, col)
                    if item: texts.append(item.text())
            content_width = max((metrics.horizontalAdvance(text) for text in texts), default=0) + 30
            table.setColumnWidth(col, max(minimum, min(content_width, maximum)))

    def load_selected_document(self):
        row = self.saved_table.currentRow()
        if row < 0: return
        inbound_id = self.saved_table.item(row, 0).data(Qt.UserRole)
        header = next((x for x in self.saved_headers if x["inbound_id"] == inbound_id), None)
        if not header: return
        self.current_id = inbound_id; self.base_date.setDate(QDate.fromString(header["base_date"], "yyyy-MM-dd"))
        self.warehouse.setCurrentIndex(max(0, self.warehouse.findData(header["warehouse_id"])))
        self.memo.setPlainText(header.get("memo") or ""); self.table.setRowCount(0)
        for item in header.get("items", []): self.add_row(item)

    def remove_rows(self):
        rows = sorted({x.row() for x in self.table.selectedIndexes()}, reverse=True)
        if not rows: QMessageBox.information(self, "선택 확인", "삭제할 입력행을 선택해 주세요."); return
        for row in rows: self.table.removeRow(row)
        if self.table.rowCount() == 0: self.add_row()

    def save_data(self):
        if self._saving: return
        if self.warehouse.currentData() is None: QMessageBox.warning(self, "입력 확인", "창고를 선택해 주세요."); return
        try: items = [self._row_payload(row) for row in range(self.table.rowCount())]
        except ValueError as exc: QMessageBox.warning(self, "입력 확인", str(exc)); return
        action = "수정" if self.current_id else "생성"
        if QMessageBox.question(self, "최초재고 저장", f"{len(items)}개 LOT와 최초입고를 {action}하시겠습니까?") != QMessageBox.Yes: return
        payload = {"base_date":self.base_date.date().toString("yyyy-MM-dd"), "warehouse_id":self.warehouse.currentData(), "memo":self.memo.toPlainText().strip() or None, "items":items}
        self._saving = True; self.btn_save.setEnabled(False); self.btn_save.setText("저장 중...")
        try:
            url = f"{API_BASE_URL}/companies/{app_context.company_code}/opening-inventories"
            response = httpx.put(f"{url}/{self.current_id}", json=payload, timeout=30) if self.current_id else httpx.post(url, json=payload, timeout=30)
            response.raise_for_status(); result = response.json()
            QMessageBox.information(self, "저장 완료", f"최초입고 {result['inbound_no']}와 LOT {len(result['items'])}건이 저장되었습니다.")
            self.current_id = result["inbound_id"]; self.load_all(); self._select_saved(self.current_id)
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))
        finally: self._saving = False; self.btn_save.setEnabled(True); self.btn_save.setText("저장")

    def delete_document(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "삭제할 저장 전표를 목록에서 선택해 주세요."); return
        if QMessageBox.warning(self, "전표 삭제", "선택한 최초입고와 연결 LOT를 삭제합니다.\n후속 입출고에 연결된 LOT는 삭제되지 않습니다. 계속하시겠습니까?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/companies/{app_context.company_code}/opening-inventories/{self.current_id}", timeout=20)
            response.raise_for_status(); QMessageBox.information(self, "삭제 완료", response.json().get("message", "삭제되었습니다."))
            self.current_id = None; self.load_all(); self.new_document()
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def _select_saved(self, inbound_id):
        for row in range(self.saved_table.rowCount()):
            if self.saved_table.item(row, 0).data(Qt.UserRole) == inbound_id:
                self.saved_table.selectRow(row); return

    def _row_payload(self, row):
        def value(col): return (self.table.item(row, col).text() if self.table.item(row, col) else "").strip()
        product = self.table.cellWidget(row, 0); product_id = product.currentData()
        if product_id is None: raise ValueError(f"{row + 1}행의 상품을 선택해 주세요.")
        try:
            box_qty = int(value(9).replace(",", "")); weight = float(value(10).replace(",", "")); cost = float(value(11).replace(",", ""))
        except ValueError as exc:
            raise ValueError(f"{row + 1}행의 BOX·KG·개별원가는 숫자로 입력해 주세요.") from exc
        if box_qty < 0 or weight <= 0 or cost < 0: raise ValueError(f"{row + 1}행의 BOX·KG·개별원가를 확인해 주세요.")
        return {"inbound_item_id":product.property("inbound_item_id"), "lot_id":product.property("lot_id"), "product_id":product_id,
                "source_type":self.table.cellWidget(row,1).currentData(), "business_lot_no":value(3) or None, "bl_no":value(4) or None,
                "container_no":value(5) or None, "history_no":value(6) or None, "production_date":self.table.cellWidget(row,7).date().toString("yyyy-MM-dd"),
                "box_qty":box_qty, "weight":weight, "individual_cost":cost, "memo":value(13) or None}

    def close_window(self):
        parent = self.parentWidget(); parent.close() if isinstance(parent, QMdiSubWindow) else self.close()

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
