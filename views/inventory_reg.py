"""거래 원장에서 계산하는 LOT/창고/상품 재고 조회 화면."""

import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class InventoryHistoryDialog(QDialog):
    COLUMNS = (("date", "일자"), ("direction", "구분"), ("transaction_no", "입출고번호"),
               ("source", "원전표"), ("box_delta", "Box 증감"),
               ("weight_delta", "Kg 증감"), ("balance_box_qty", "잔량 Box"),
               ("balance_weight", "잔량 Kg"))

    def __init__(self, lot, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"LOT 입출고 이력 - {lot.get('lot_code', '')}")
        self.resize(1050, 520)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"{lot.get('product_name', '')}  /  LOT {lot.get('lot_code', '')}"))
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in self.COLUMNS])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.rows = rows
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            source = f"{row.get('source_no') or ''} [{row.get('source_type') or ''}:{row.get('source_id') or ''}]"
            for column, (key, _) in enumerate(self.COLUMNS):
                value = source if key == "source" else row.get(key)
                if key == "direction":
                    value = "입고" if value == "INBOUND" else "출고"
                if key in {"box_delta", "balance_box_qty"} and value is not None:
                    value = f"{int(value):,}"
                elif key in {"weight_delta", "balance_weight"} and value is not None:
                    value = f"{float(value):,.2f}"
                cell = QTableWidgetItem("" if value is None else str(value))
                if key in {"box_delta", "balance_box_qty", "weight_delta", "balance_weight"}:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(index, column, cell)
        self.table.resizeColumnsToContents()
        root.addWidget(self.table, 1)
        note = QLabel("원전표의 source_type/source_id를 보존합니다. 전표 입력화면 Drill-down은 후속 단계에서 연결할 수 있습니다.")
        note.setWordWrap(True)
        root.addWidget(note)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        root.addWidget(close, 0, Qt.AlignRight)


class InventoryRegWindow(QWidget):
    LOT_COLUMNS = (
        ("warehouse_name", "창고"), ("product_name", "상품명"), ("lot_code", "LOT"),
        ("source_type", "LOT구분"), ("status", "LOT상태"),
        ("storage_type", "보관구분"), ("production_date", "생산일"), ("expiry_date", "소비기한"),
        ("beginning_box_qty", "전재고 Box"), ("beginning_weight", "전재고 Kg"),
        ("inbound_box_qty", "입고 Box"), ("inbound_weight", "입고 Kg"),
        ("outbound_box_qty", "출고 Box"), ("outbound_weight", "출고 Kg"),
        ("current_box_qty", "현재고 Box"), ("current_weight", "현재고 Kg"),
        ("average_weight", "평균중량"), ("individual_cost", "개별원가/Kg"),
        ("inventory_amount", "참고금액"), ("bl_no", "BL"), ("container_no", "Container"),
        ("history_no", "이력번호"), ("supplier_name", "매입처"), ("memo", "비고"),
    )
    GROUP_COLUMNS = (
        ("warehouse_name", "창고"), ("product_name", "상품"), ("source_lot_count", "LOT 수"),
        ("beginning_box_qty", "전재고 Box"), ("beginning_weight", "전재고 Kg"),
        ("inbound_box_qty", "입고 Box"), ("inbound_weight", "입고 Kg"),
        ("outbound_box_qty", "출고 Box"), ("outbound_weight", "출고 Kg"),
        ("current_box_qty", "현재고 Box"), ("current_weight", "현재고 Kg"),
        ("average_weight", "평균중량"), ("inventory_amount", "참고금액"),
    )

    def __init__(self):
        super().__init__()
        self.rows = []
        self._loading = False
        self._build_ui()
        self.load_warehouses()
        self.load_inventory()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("재고수불 조회")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        form = QFormLayout()
        self.company = QLabel(app_context.company_name or app_context.company_code or "업무회사 미선택")
        today = QDate.currentDate()
        self.start_date = QDateEdit(today.addDays(1 - today.day()))
        self.end_date = QDateEdit(today)
        for date_edit in (self.start_date, self.end_date):
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("yyyy-MM-dd")
            date_edit.setKeyboardTracking(False)
        self.warehouse = QComboBox()
        self.warehouse.addItem("전체 창고", None)
        self.storage_type = QComboBox()
        self.storage_type.addItem("전체 보관유형", None)
        for label, value in (("냉동", "FROZEN"), ("냉장", "CHILLED"),
                             ("상온", "AMBIENT"), ("혼합", "MIXED")):
            self.storage_type.addItem(label, value)
        self.product_search = QWidget()
        search_line = QHBoxLayout(self.product_search); search_line.setContentsMargins(0, 0, 0, 0)
        from PySide6.QtWidgets import QLineEdit
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("상품명, 상품코드, LOT, BL, Container, 이력번호")
        search_line.addWidget(self.search_edit)
        self.group_by = QComboBox()
        for label, key in (("LOT별 상세", "LOT"), ("창고별", "WAREHOUSE"), ("상품별", "PRODUCT")):
            self.group_by.addItem(label, key)
        self.zero_exclude = QCheckBox("현재고 0 제외")
        self.zero_exclude.setChecked(True)
        self.btn_search = QPushButton("조회")
        self.btn_close = QPushButton("닫기")
        form.addRow("업무회사", self.company)
        form.addRow("시작일", self.start_date)
        form.addRow("종료일", self.end_date)
        form.addRow("창고", self.warehouse)
        form.addRow("보관유형", self.storage_type)
        form.addRow("검색", self.product_search)
        form.addRow("조회관점", self.group_by)
        actions = QHBoxLayout(); actions.addWidget(self.zero_exclude); actions.addStretch(1)
        actions.addWidget(self.btn_search); actions.addWidget(self.btn_close)
        root.addLayout(form); root.addLayout(actions)
        self.summary = QLabel("전재고 + 기간입고 - 기간출고 = 현재고")
        self.summary.setStyleSheet("font-weight:700;padding:6px;")
        root.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.LOT_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in self.LOT_COLUMNS])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.open_lot_history)
        root.addWidget(self.table, 1)
        self.btn_search.clicked.connect(self.load_inventory)
        self.search_edit.returnPressed.connect(self.load_inventory)
        self.btn_close.clicked.connect(self.close)
        self.group_by.currentIndexChanged.connect(self._set_columns)
        self._set_columns()

    def _url(self, suffix=""):
        return f"{API_BASE_URL}/companies/{app_context.company_code}/inventory{suffix}"

    def load_warehouses(self):
        if not app_context.company_code:
            return
        try:
            response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses", timeout=10)
            response.raise_for_status()
            for row in response.json():
                if row.get("use_yn", True) and row.get("company_use_yn", True):
                    self.warehouse.addItem(row["warehouse_name"], row["warehouse_id"])
        except Exception as exc:
            QMessageBox.critical(self, "창고 조회 오류", str(exc))

    def _set_columns(self, *_):
        columns = self.LOT_COLUMNS if self.group_by.currentData() == "LOT" else self.GROUP_COLUMNS
        self._columns = columns
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])

    @staticmethod
    def _format(key, value):
        if value is None:
            return ""
        if key.endswith("weight") or key in {"average_weight"}:
            return f"{float(value):,.2f}"
        if key in {"individual_cost", "inventory_amount", "current_box_qty", "beginning_box_qty", "inbound_box_qty", "outbound_box_qty", "source_lot_count"}:
            return f"{int(value):,}"
        return str(value)

    def load_inventory(self):
        if self._loading or not app_context.company_code:
            return
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        if start > end:
            QMessageBox.warning(self, "조회조건 확인", "시작일은 종료일보다 늦을 수 없습니다.")
            return
        params = {"start_date": start, "end_date": end,
                  "product_search": self.search_edit.text().strip(),
                  "include_zero": not self.zero_exclude.isChecked(),
                  "group_by": self.group_by.currentData()}
        if self.storage_type.currentData() is not None:
            params["storage_type"] = self.storage_type.currentData()
        if self.warehouse.currentData() is not None:
            params["warehouse_id"] = self.warehouse.currentData()
        self._loading = True; self.btn_search.setEnabled(False)
        try:
            response = httpx.get(self._url(), params=params, timeout=30)
            response.raise_for_status(); result = response.json(); self.rows = result["rows"]
            self._set_columns()
            self.table.setRowCount(len(self.rows))
            for row_index, row in enumerate(self.rows):
                for column, (key, _) in enumerate(self._columns):
                    cell = QTableWidgetItem(self._format(key, row.get(key)))
                    if key.endswith("weight") or key in {"average_weight", "inventory_amount", "individual_cost"} or key.endswith("box_qty"):
                        cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if column == 0:
                        cell.setData(Qt.UserRole, row)
                    self.table.setItem(row_index, column, cell)
            self.table.resizeColumnsToContents()
            summary = result["summary"]
            self.summary.setText(
                f"전재고 {summary['beginning_box_qty']:,} Box / {float(summary['beginning_weight']):,.2f} Kg   +   "
                f"입고 {summary['inbound_box_qty']:,} Box / {float(summary['inbound_weight']):,.2f} Kg   −   "
                f"출고 {summary['outbound_box_qty']:,} Box / {float(summary['outbound_weight']):,.2f} Kg   =   "
                f"현재고 {summary['current_box_qty']:,} Box / {float(summary['current_weight']):,.2f} Kg   ·   "
                f"참고금액 {summary['inventory_amount']:,}원"
            )
        except Exception as exc:
            QMessageBox.critical(self, "재고 조회 오류", str(exc))
        finally:
            self._loading = False; self.btn_search.setEnabled(True)

    def open_lot_history(self, item):
        if self.group_by.currentData() != "LOT" or item.row() < 0 or item.row() >= len(self.rows):
            return
        lot = self.rows[item.row()]
        if not lot.get("lot_id"):
            return
        try:
            response = httpx.get(self._url(f"/lots/{lot['lot_id']}/transactions"),
                                 params={"end_date": self.end_date.date().toString("yyyy-MM-dd")}, timeout=20)
            response.raise_for_status(); history = response.json()
            InventoryHistoryDialog(lot, history["rows"], self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "LOT 이력 조회 오류", str(exc))
