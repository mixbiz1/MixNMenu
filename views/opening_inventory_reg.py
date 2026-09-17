import httpx

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QMdiSubWindow,
)

from app_context import app_context


API_BASE_URL = "http://127.0.0.1:8000/api/v1"
COLUMNS = [
    "상품 *", "구분 *", "공급자 LOT", "BL번호", "컨테이너", "이력번호",
    "원산지", "EST", "생산일", "소비기한", "BOX *", "KG *", "개별원가 *", "메모",
]


class OpeningInventoryRegWindow(QWidget):
    """기준일 현재 최초재고를 LOT와 입고 원장으로 함께 생성한다."""

    def __init__(self):
        super().__init__()
        self.products = []
        self.warehouses = []
        self._saving = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("최초재고 등록")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)
        info = QLabel("기준일 현재 실재고를 입력합니다. 저장하면 각 행의 LOT와 최초입고 Transaction이 하나의 작업으로 생성됩니다.")
        info.setStyleSheet("color: #475569;")
        root.addWidget(info)

        header = QGroupBox("최초재고 Header")
        hl = QHBoxLayout(header)
        hl.addWidget(QLabel("업무회사")); hl.addWidget(QLabel(app_context.company_name or app_context.company_code))
        hl.addSpacing(20); hl.addWidget(QLabel("기준일 *"))
        self.base_date = QDateEdit(QDate.currentDate()); self.base_date.setCalendarPopup(True); self.base_date.setDisplayFormat("yyyy-MM-dd")
        hl.addWidget(self.base_date); hl.addSpacing(20); hl.addWidget(QLabel("창고 *"))
        self.warehouse = QComboBox(); self.warehouse.setMinimumWidth(220); hl.addWidget(self.warehouse)
        hl.addStretch(); root.addWidget(header)

        buttons = QHBoxLayout()
        self.btn_load = QPushButton("기준정보 조회 [F7]")
        self.btn_add = QPushButton("＋ 행 추가")
        self.btn_remove = QPushButton("－ 선택행 삭제")
        self.btn_save = QPushButton("저장 [F4]")
        self.btn_close = QPushButton("닫기")
        for button in (self.btn_load, self.btn_add, self.btn_remove, self.btn_save, self.btn_close): buttons.addWidget(button)
        buttons.addStretch(); root.addLayout(buttons)

        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setMinimumHeight(330); root.addWidget(self.table)
        memo_box = QGroupBox("Header 메모"); ml = QVBoxLayout(memo_box); self.memo = QTextEdit(); self.memo.setMaximumHeight(65); ml.addWidget(self.memo); root.addWidget(memo_box)

        self.btn_load.clicked.connect(self.load_master_data); self.btn_add.clicked.connect(self.add_row)
        self.btn_remove.clicked.connect(self.remove_rows); self.btn_save.clicked.connect(self.save_data); self.btn_close.clicked.connect(self.close_window)
        self.btn_load.setShortcut("F7"); self.btn_save.setShortcut("F4")

    def showEvent(self, event):
        super().showEvent(event)
        if not self.products:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.load_master_data)

    def load_master_data(self):
        self.btn_load.setEnabled(False); self.btn_load.setText("조회 중...")
        try:
            products = httpx.get(f"{API_BASE_URL}/products", timeout=10); products.raise_for_status()
            warehouses = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses", timeout=10); warehouses.raise_for_status()
            self.products = [x for x in products.json() if x.get("use_yn", True)]
            self.warehouses = [x for x in warehouses.json() if x.get("company_use_yn", True) and x.get("use_yn", True)]
            selected = self.warehouse.currentData(); self.warehouse.clear()
            for item in self.warehouses: self.warehouse.addItem(f"{item['warehouse_name']} ({item['warehouse_code']})", item["warehouse_id"])
            if selected is not None: self.warehouse.setCurrentIndex(max(0, self.warehouse.findData(selected)))
            if self.table.rowCount() == 0: self.add_row()
            else: self._refresh_product_combos()
        except Exception as exc:
            QMessageBox.critical(self, "기준정보 조회 오류", self._error_text(exc))
        finally:
            self.btn_load.setEnabled(True); self.btn_load.setText("기준정보 조회")

    def add_row(self):
        row = self.table.rowCount(); self.table.insertRow(row)
        product = QComboBox(); self._fill_product_combo(product); self.table.setCellWidget(row, 0, product)
        source = QComboBox(); source.addItem("수입", "IMPORT"); source.addItem("국내매입", "DOMESTIC"); self.table.setCellWidget(row, 1, source)
        for col in range(2, len(COLUMNS)): self.table.setItem(row, col, QTableWidgetItem(""))
        for col, value in ((10, "0"), (11, "0.00"), (12, "0")): self.table.item(row, col).setText(value)
        self.table.scrollToBottom()

    def _fill_product_combo(self, combo, selected=None):
        combo.clear(); combo.addItem("선택", None)
        for item in self.products: combo.addItem(f"{item['product_name']} ({item['product_code']})", item["product_id"])
        if selected is not None: combo.setCurrentIndex(max(0, combo.findData(selected)))

    def _refresh_product_combos(self):
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0); selected = combo.currentData(); self._fill_product_combo(combo, selected)

    def remove_rows(self):
        rows = sorted({x.row() for x in self.table.selectedIndexes()}, reverse=True)
        if not rows: QMessageBox.information(self, "선택 확인", "삭제할 행을 선택해 주세요."); return
        for row in rows: self.table.removeRow(row)
        if self.table.rowCount() == 0: self.add_row()

    def save_data(self):
        if self._saving: return
        if self.warehouse.currentData() is None: QMessageBox.warning(self, "입력 확인", "창고를 선택해 주세요."); return
        try: items = [self._row_payload(row) for row in range(self.table.rowCount())]
        except ValueError as exc: QMessageBox.warning(self, "입력 확인", str(exc)); return
        if QMessageBox.question(self, "최초재고 저장", f"{len(items)}개 LOT와 최초입고를 생성하시겠습니까?") != QMessageBox.Yes: return
        payload = {"base_date":self.base_date.date().toString("yyyy-MM-dd"), "warehouse_id":self.warehouse.currentData(), "memo":self.memo.toPlainText().strip() or None, "items":items}
        self._saving = True; self.btn_save.setEnabled(False); self.btn_save.setText("저장 중...")
        try:
            response = httpx.post(f"{API_BASE_URL}/companies/{app_context.company_code}/opening-inventories", json=payload, timeout=30)
            response.raise_for_status(); result = response.json()
            QMessageBox.information(self, "저장 완료", f"최초입고 {result['inbound_no']}와 LOT {len(result['items'])}건이 생성되었습니다.")
            self.table.setRowCount(0); self.add_row(); self.memo.clear()
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))
        finally: self._saving = False; self.btn_save.setEnabled(True); self.btn_save.setText("저장")

    def _row_payload(self, row):
        def value(col): return (self.table.item(row, col).text() if self.table.item(row, col) else "").strip()
        product_id = self.table.cellWidget(row, 0).currentData()
        if product_id is None: raise ValueError(f"{row + 1}행의 상품을 선택해 주세요.")
        try: box_qty = int(value(10).replace(",", "")); weight = float(value(11).replace(",", "")); cost = float(value(12).replace(",", ""))
        except ValueError as exc: raise ValueError(f"{row + 1}행의 BOX·KG·개별원가는 숫자로 입력해 주세요.") from exc
        if box_qty < 0 or weight <= 0 or cost < 0: raise ValueError(f"{row + 1}행의 BOX·KG·개별원가를 확인해 주세요.")
        for col, label in ((8,"생산일"),(9,"소비기한")):
            if value(col) and QDate.fromString(value(col), "yyyy-MM-dd").isValid() is False: raise ValueError(f"{row + 1}행 {label}은 yyyy-MM-dd 형식으로 입력해 주세요.")
        return {"product_id":product_id,"source_type":self.table.cellWidget(row,1).currentData(),"business_lot_no":value(2) or None,"bl_no":value(3) or None,"container_no":value(4) or None,"history_no":value(5) or None,"origin":value(6) or None,"est_no":value(7) or None,"production_date":value(8) or None,"expiry_date":value(9) or None,"box_qty":box_qty,"weight":weight,"individual_cost":cost,"memo":value(13) or None}

    def close_window(self):
        parent = self.parentWidget(); parent.close() if isinstance(parent, QMdiSubWindow) else self.close()

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return str(exc.response.json().get("detail", exc))
            except Exception: pass
        return str(exc)
