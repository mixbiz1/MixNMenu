"""거래 원장에서 계산하는 LOT/창고/상품 재고 조회 화면."""

from datetime import date
from decimal import Decimal, ROUND_CEILING

import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


SOURCE_ROLE = Qt.UserRole + 1


def _decimal_value(value):
    """Normalize API numeric values without assuming JSON decoded them as numbers."""
    if value is None or value == "":
        return Decimal(0)
    return Decimal(str(value))


def _integer_value(value):
    return int(_decimal_value(value))


class CalendarPicker(QDialog):
    """Calendar popup paired with a freely editable ISO date field."""

    def __init__(self, initial_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("날짜 선택")
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        self.calendar.setSelectedDate(initial_date)
        layout.addWidget(self.calendar)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_iso_date(self):
        return self.calendar.selectedDate().toString("yyyy-MM-dd")


class InventoryHistoryDialog(QDialog):
    COLUMNS = (
        ("date", "일자"), ("direction", "구분"), ("transaction_no", "전표번호"),
        ("account_name", "거래처"), ("beginning_box_qty", "전재고 Box"),
        ("beginning_weight", "전재고 Kg"), ("inbound_box_qty", "입고 Box"),
        ("inbound_weight", "입고 Kg"), ("outbound_box_qty", "출고 Box"),
        ("outbound_weight", "출고 Kg"), ("balance_box_qty", "잔량 Box"),
        ("balance_weight", "잔량 Kg"), ("unit_cost", "단가"), ("source", "원전표"),
    )

    def __init__(self, lot, rows, start_date="", end_date="", on_open_source=None, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.on_open_source = on_open_source
        self.setWindowTitle(f"LOT 수불원장 - {lot.get('lot_code', '')}")
        self.resize(1350, 620)
        root = QVBoxLayout(self)
        metadata = (
            f"상품 {lot.get('product_name') or '-'}   /   LOT {lot.get('lot_code') or '-'}   /   "
            f"창고 {lot.get('warehouse_name') or '-'}\n"
            f"BL {lot.get('bl_no') or '-'}   /   이력번호 {lot.get('history_no') or '-'}   /   "
            f"조회기간 {start_date or '-'} ~ {end_date or '-'}\n"
            f"보관 {lot.get('storage_type') or '-'}   /   LOT구분 {lot.get('source_type') or '-'}   /   "
            f"LOT상태 {lot.get('status') or '-'}   /   생산일 {lot.get('production_date') or '-'}   /   "
            f"소비기한 {lot.get('expiry_date') or '-'}\n"
            f"Container {lot.get('container_no') or '-'}   /   매입처 {lot.get('supplier_name') or '-'}   /   "
            f"비고 {lot.get('memo') or '-'}"
        )
        self.header = QLabel(metadata)
        self.header.setWordWrap(True)
        root.addWidget(self.header)
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in self.COLUMNS])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            direction = row.get("direction")
            inbound = direction == "INBOUND"
            beginning = direction == "BEGINNING"
            display = dict(row)
            display["direction"] = "이월재고" if beginning else "입고" if inbound else "출고"
            display["beginning_box_qty"] = _integer_value(row.get("beginning_box_qty")) if beginning else ""
            display["beginning_weight"] = _decimal_value(row.get("beginning_weight")) if beginning else ""
            display["inbound_box_qty"] = _integer_value(row.get("box_delta")) if inbound else ""
            display["inbound_weight"] = _decimal_value(row.get("weight_delta")) if inbound else ""
            display["outbound_box_qty"] = abs(_integer_value(row.get("box_delta"))) if direction == "OUTBOUND" else ""
            display["outbound_weight"] = abs(_decimal_value(row.get("weight_delta"))) if direction == "OUTBOUND" else ""
            if direction in {"BEGINNING", "INBOUND", "OUTBOUND"}:
                display["balance_box_qty"] = _integer_value(row.get("balance_box_qty"))
                display["balance_weight"] = _decimal_value(row.get("balance_weight"))
            source_type = row.get("source_type")
            source_no = row.get("source_no") or row.get("transaction_no")
            display["source"] = self._source_label(source_type, source_no, beginning)
            for column, (key, _) in enumerate(self.COLUMNS):
                value = display.get(key)
                cell = QTableWidgetItem(self._format(key, value))
                if key in {"source"}:
                    cell.setData(SOURCE_ROLE, (source_type, row.get("source_id")))
                if key in {
                    "beginning_box_qty", "beginning_weight", "inbound_box_qty", "inbound_weight",
                    "outbound_box_qty", "outbound_weight", "balance_box_qty", "balance_weight", "unit_cost",
                }:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(index, column, cell)
        self.table.resizeColumnsToContents()
        root.addWidget(self.table, 1)
        beginning_box = _integer_value(rows[0].get("beginning_box_qty")) if rows and rows[0].get("direction") == "BEGINNING" else 0
        beginning_kg = _decimal_value(rows[0].get("beginning_weight")) if rows and rows[0].get("direction") == "BEGINNING" else Decimal(0)
        inbound_box = sum(_integer_value(row.get("box_delta")) for row in rows if row.get("direction") == "INBOUND")
        inbound_kg = sum((_decimal_value(row.get("weight_delta")) for row in rows if row.get("direction") == "INBOUND"), Decimal(0))
        outbound_box = sum(abs(_integer_value(row.get("box_delta"))) for row in rows if row.get("direction") == "OUTBOUND")
        outbound_kg = sum((abs(_decimal_value(row.get("weight_delta"))) for row in rows if row.get("direction") == "OUTBOUND"), Decimal(0))
        current_box = _integer_value(rows[-1].get("balance_box_qty")) if rows else _integer_value(lot.get("current_box_qty"))
        current_kg = _decimal_value(rows[-1].get("balance_weight")) if rows else _decimal_value(lot.get("current_weight"))
        self.summary = QLabel(
            f"전재고 {beginning_box:,} Box / {beginning_kg:,.2f} Kg   +   "
            f"입고 {inbound_box:,} Box / {inbound_kg:,.2f} Kg   −   "
            f"출고 {outbound_box:,} Box / {outbound_kg:,.2f} Kg   =   "
            f"현재고 {current_box:,} Box / {current_kg:,.2f} Kg"
        )
        self.summary.setStyleSheet("font-weight:700;padding:6px;")
        root.addWidget(self.summary)
        note = QLabel("원전표 행을 더블클릭하거나 선택 후 ‘원전표 열기’를 누르면 매입·매출 전표를 엽니다.")
        note.setWordWrap(True)
        root.addWidget(note)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.open_source_button = QPushButton("원전표 열기")
        self.open_source_button.clicked.connect(self.open_selected_source)
        self.open_source_button.setEnabled(False)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        actions.addWidget(self.open_source_button)
        actions.addWidget(close)
        root.addLayout(actions)
        self.table.itemSelectionChanged.connect(self._update_source_button)
        self.table.itemDoubleClicked.connect(self.open_selected_source)

    @staticmethod
    def _format(key, value):
        if value is None or value == "":
            return ""
        if key in {"beginning_weight", "inbound_weight", "outbound_weight", "balance_weight"}:
            return f"{_decimal_value(value):,.2f}"
        if key in {"beginning_box_qty", "inbound_box_qty", "outbound_box_qty", "balance_box_qty", "unit_cost"}:
            if key == "unit_cost":
                won = _decimal_value(value).quantize(Decimal("1"), rounding=ROUND_CEILING)
                return f"{int(won):,}"
            return f"{_integer_value(value):,}"
        return str(value)

    @staticmethod
    def _source_label(source_type, source_no, beginning=False):
        if beginning:
            return "전재고 이월"
        labels = {"PURCHASE": "매입", "SALE": "매출", "OPENING_INVENTORY": "최초재고",
                  "INBOUND": "입고", "OUTBOUND": "출고"}
        label = labels.get(source_type, "원전표")
        return f"{label} {source_no}" if source_no else label

    def _update_source_button(self):
        self.open_source_button.setEnabled(self._selected_source() is not None)

    def _selected_source(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        for column, (key, _) in enumerate(self.COLUMNS):
            if key == "source":
                source = self.table.item(row, column).data(SOURCE_ROLE)
                if source and source[0] in {"PURCHASE", "SALE"} and source[1]:
                    return source
        return None

    def open_selected_source(self, *_):
        source = self._selected_source()
        if source and callable(self.on_open_source):
            self.on_open_source(*source)


class InventoryRegWindow(QWidget):
    LOT_COLUMNS = (
        ("warehouse_name", "창고"), ("product_name", "상품명"), ("lot_code", "LOT"),
        ("production_date", "생산일"), ("expiry_date", "소비기한"),
        ("beginning_box_qty", "전재고 Box"), ("beginning_weight", "전재고 Kg"),
        ("inbound_box_qty", "입고 Box"), ("inbound_weight", "입고 Kg"),
        ("outbound_box_qty", "출고 Box"), ("outbound_weight", "출고 Kg"),
        ("current_box_qty", "현재고 Box"), ("current_weight", "현재고 Kg"),
        ("average_weight", "평균중량"), ("individual_cost", "개별원가/Kg"),
        ("inventory_amount", "참고금액"), ("bl_no", "BL"), ("history_no", "이력번호"),
    )
    GROUP_METRIC_COLUMNS = (
        ("beginning_box_qty", "전재고 Box"), ("beginning_weight", "전재고 Kg"),
        ("inbound_box_qty", "입고 Box"), ("inbound_weight", "입고 Kg"),
        ("outbound_box_qty", "출고 Box"), ("outbound_weight", "출고 Kg"),
        ("current_box_qty", "현재고 Box"), ("current_weight", "현재고 Kg"),
        ("average_weight", "평균중량"), ("inventory_amount", "참고금액"),
    )
    WAREHOUSE_COLUMNS = (("warehouse_name", "창고"), ("source_lot_count", "LOT 수")) + GROUP_METRIC_COLUMNS
    PRODUCT_COLUMNS = (("product_name", "상품명"), ("source_lot_count", "LOT 수")) + GROUP_METRIC_COLUMNS
    STORAGE_LABELS = {None: "전체 보관유형", "FROZEN": "냉동", "CHILLED": "냉장",
                      "AMBIENT": "상온", "MIXED": "혼합"}

    def __init__(self):
        super().__init__()
        self.rows = []
        self._loading = False
        self._last_successful_request = None
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
        self.start_date = QLineEdit(date.today().replace(day=1).isoformat())
        self.start_date.setObjectName("inventoryStartDate")
        self.end_date = QLineEdit(date.today().isoformat())
        self.end_date.setObjectName("inventoryEndDate")
        self.start_date.setPlaceholderText("YYYY-MM-DD")
        self.end_date.setPlaceholderText("YYYY-MM-DD")
        self.start_date.setMaxLength(10)
        self.end_date.setMaxLength(10)
        self.start_date.setFixedWidth(112)
        self.end_date.setFixedWidth(112)
        self.start_calendar = QPushButton("달력")
        self.end_calendar = QPushButton("달력")
        self.start_calendar.clicked.connect(lambda: self._choose_date(self.start_date))
        self.end_calendar.clicked.connect(lambda: self._choose_date(self.end_date))
        start_field = QWidget(); start_line = QHBoxLayout(start_field); start_line.setContentsMargins(0, 0, 0, 0)
        start_line.addWidget(self.start_date); start_line.addWidget(self.start_calendar); start_line.addStretch(1)
        end_field = QWidget(); end_line = QHBoxLayout(end_field); end_line.setContentsMargins(0, 0, 0, 0)
        end_line.addWidget(self.end_date); end_line.addWidget(self.end_calendar); end_line.addStretch(1)
        self.warehouse = QComboBox()
        self.warehouse.addItem("전체 창고", None)
        self.storage_type = QComboBox()
        self.storage_type.addItem("전체 보관유형", None)
        for label, value in (("냉동", "FROZEN"), ("냉장", "CHILLED"),
                             ("상온", "AMBIENT"), ("혼합", "MIXED")):
            self.storage_type.addItem(label, value)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("상품명, 상품코드, LOT, BL, Container, 이력번호")
        self.group_by = QComboBox()
        for label, key in (("LOT별 상세", "LOT"), ("창고별", "WAREHOUSE"), ("상품별", "PRODUCT")):
            self.group_by.addItem(label, key)
        self.zero_exclude = QCheckBox("현재고 0 제외")
        self.zero_exclude.setChecked(True)
        self.btn_search = QPushButton("조회")
        self.btn_close = QPushButton("닫기")
        form.addRow("업무회사", self.company)
        form.addRow("시작일", start_field)
        form.addRow("종료일", end_field)
        form.addRow("창고", self.warehouse)
        form.addRow("보관유형", self.storage_type)
        form.addRow("상품·LOT 검색", self.search_edit)
        form.addRow("조회관점", self.group_by)
        actions = QHBoxLayout(); actions.addWidget(self.zero_exclude); actions.addStretch(1)
        actions.addWidget(self.btn_search); actions.addWidget(self.btn_close)
        root.addLayout(form); root.addLayout(actions)
        self.applied_conditions = QLabel("성공한 조회가 아직 없습니다.")
        self.applied_conditions.setObjectName("inventoryAppliedConditions")
        self.applied_conditions.setWordWrap(True)
        self.applied_conditions.setStyleSheet("font-weight:600;padding:6px;")
        root.addWidget(self.applied_conditions)
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
        self.start_date.returnPressed.connect(self.load_inventory)
        self.end_date.returnPressed.connect(self.load_inventory)
        self.btn_close.clicked.connect(self.close)
        self._set_columns()

    @staticmethod
    def _choose_date(field):
        current = InventoryRegWindow._parse_date(field.text()) or date.today()
        initial = QDate(current.year, current.month, current.day)
        dialog = CalendarPicker(initial, field.window())
        if dialog.exec() == QDialog.Accepted:
            field.setText(dialog.selected_iso_date())

    @staticmethod
    def _parse_date(value):
        try:
            parsed = date.fromisoformat(value.strip())
            if parsed.isoformat() != value.strip():
                return None
            return parsed
        except (TypeError, ValueError):
            return None

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

    def _columns_for_group(self, group):
        columns_by_group = {
            "LOT": self.LOT_COLUMNS,
            "WAREHOUSE": self.WAREHOUSE_COLUMNS,
            "PRODUCT": self.PRODUCT_COLUMNS,
        }
        try:
            return columns_by_group[group]
        except KeyError as exc:
            raise ValueError("조회 결과의 조회관점이 올바르지 않습니다.") from exc

    def _set_columns(self, group_by=None):
        group = group_by or self.group_by.currentData()
        columns = self._columns_for_group(group)
        self._columns = columns
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])

    @staticmethod
    def _format(key, value):
        if value is None:
            return ""
        if key.endswith("weight") or key == "average_weight":
            return f"{_decimal_value(value):,.2f}"
        if key in {"individual_cost", "inventory_amount", "current_box_qty", "beginning_box_qty",
                   "inbound_box_qty", "outbound_box_qty", "source_lot_count"}:
            return f"{_integer_value(value):,}"
        return str(value)

    def _query_params(self, start, end):
        params = {"start_date": start.isoformat(), "end_date": end.isoformat(),
                  "product_search": self.search_edit.text().strip(),
                  "include_zero": not self.zero_exclude.isChecked(),
                  "group_by": self.group_by.currentData()}
        if self.storage_type.currentData() is not None:
            params["storage_type"] = self.storage_type.currentData()
        if self.warehouse.currentData() is not None:
            params["warehouse_id"] = self.warehouse.currentData()
        return params

    def _format_applied_conditions(self, params, result, warehouse_label=None):
        start = str(result.get("start_date") or params["start_date"])
        end = str(result.get("end_date") or params["end_date"])
        warehouse = (warehouse_label or self.warehouse.currentText()) if params.get("warehouse_id") is not None else "전체 창고"
        storage = self.STORAGE_LABELS.get(params.get("storage_type"), "전체 보관유형")
        applied_group = str(result.get("group_by") or params["group_by"]).upper()
        group = {"LOT": "LOT별 상세", "WAREHOUSE": "창고별", "PRODUCT": "상품별"}.get(
            applied_group, applied_group
        )
        zero = "현재고 0 포함" if params["include_zero"] else "현재고 0 제외"
        search = f" / 검색 {params['product_search']}" if params["product_search"] else ""
        return f"마지막 성공 조회 · 조회기간 {start} ~ {end} / {warehouse} / {storage} / {zero} / {group}{search}"

    def load_inventory(self):
        if self._loading or not app_context.company_code:
            return
        start = self._parse_date(self.start_date.text())
        end = self._parse_date(self.end_date.text())
        if start is None or end is None:
            QMessageBox.warning(self, "조회조건 확인", "시작일과 종료일을 YYYY-MM-DD 형식의 실제 날짜로 입력해 주세요.")
            return
        if start > end:
            QMessageBox.warning(self, "조회조건 확인", "시작일은 종료일보다 늦을 수 없습니다.")
            return
        params = self._query_params(start, end)
        warehouse_label = self.warehouse.currentText()
        self._loading = True; self.btn_search.setEnabled(False)
        try:
            response = httpx.get(self._url(), params=params, timeout=30)
            response.raise_for_status(); result = response.json()
            applied_group = str(result.get("group_by") or params["group_by"]).upper()
            if applied_group != params["group_by"]:
                raise ValueError("서버 조회관점이 요청한 조회관점과 일치하지 않습니다.")
            columns = self._columns_for_group(applied_group)
            rows = result["rows"]
            prepared_rows = []
            for row in rows:
                cells = []
                for column, (key, _) in enumerate(columns):
                    cell = QTableWidgetItem(self._format(key, row.get(key)))
                    if key.endswith("weight") or key in {"average_weight", "inventory_amount", "individual_cost"} or key.endswith("box_qty"):
                        cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if column == 0:
                        cell.setData(Qt.UserRole, row)
                    cells.append(cell)
                prepared_rows.append(cells)
            summary = result["summary"]
            summary_text = (
                f"전재고 {_integer_value(summary['beginning_box_qty']):,} Box / {_decimal_value(summary['beginning_weight']):,.2f} Kg   +   "
                f"입고 {_integer_value(summary['inbound_box_qty']):,} Box / {_decimal_value(summary['inbound_weight']):,.2f} Kg   −   "
                f"출고 {_integer_value(summary['outbound_box_qty']):,} Box / {_decimal_value(summary['outbound_weight']):,.2f} Kg   =   "
                f"현재고 {_integer_value(summary['current_box_qty']):,} Box / {_decimal_value(summary['current_weight']):,.2f} Kg   ·   "
                f"참고금액 {_integer_value(summary['inventory_amount']):,}원"
            )
            conditions_text = self._format_applied_conditions(params, result, warehouse_label)
            request_snapshot = {
                "params": dict(params), "warehouse_label": warehouse_label,
                "group_by": applied_group,
            }

            self._set_columns(applied_group)
            self.table.setRowCount(len(prepared_rows))
            for row_index, cells in enumerate(prepared_rows):
                for column, cell in enumerate(cells):
                    self.table.setItem(row_index, column, cell)
            self.table.resizeColumnsToContents()
            self.summary.setText(summary_text)
            self._last_successful_request = request_snapshot
            self.rows = rows
            self.applied_conditions.setText(conditions_text)
        except Exception as exc:
            QMessageBox.critical(self, "재고 조회 오류", str(exc))
        finally:
            self._loading = False; self.btn_search.setEnabled(True)

    def _open_source(self, source_type, source_id):
        widget = self
        while widget is not None:
            opener = getattr(widget, "open_account_ledger_source", None)
            if callable(opener):
                opener(source_type, source_id)
                return
            widget = widget.parentWidget()

    def open_lot_history(self, item):
        if (not self._last_successful_request
                or self._last_successful_request.get("group_by") != "LOT"
                or item.row() < 0 or item.row() >= len(self.rows)):
            return
        lot = self.rows[item.row()]
        if not lot.get("lot_id"):
            return
        try:
            params = self._last_successful_request["params"] if self._last_successful_request else {}
            start = params.get("start_date", self.start_date.text())
            end = params.get("end_date", self.end_date.text())
            response = httpx.get(self._url(f"/lots/{lot['lot_id']}/transactions"),
                                 params={"start_date": start, "end_date": end}, timeout=20)
            response.raise_for_status(); history = response.json()
            InventoryHistoryDialog(history, history["rows"], start, end,
                                   self._open_source, self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "LOT 수불원장 조회 오류", str(exc))
