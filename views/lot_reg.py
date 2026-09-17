import httpx
from PySide6.QtCore import QDate, QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QMdiSubWindow, QTextEdit, QVBoxLayout, QWidget,
)

from app_context import app_context

API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class ReadableCheckBox(QCheckBox):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._label = label
        self.toggled.connect(self._show_state)
        self._show_state(False)

    def _show_state(self, checked):
        self.setText(f"{'☑' if checked else '□'} {self._label}")


class LotRegWindow(QWidget):
    """Transaction이 생성한 LOT의 조회·추적정보 보정 화면."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        self.rows = []
        self._loading = False
        self.nav = []
        self.setWindowTitle("LOT조회/보정")
        self.resize(1320, 790)
        self._build_ui()
        self._connect_events()
        self._setup_enter_navigation()
        self.clear_form()
        QTimer.singleShot(50, self.initial_load)

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("LOT번호 / 상품명 / BL / 컨테이너 / 이력번호")
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.btn_search = QPushButton("조회 [F7]")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_save = QPushButton("저장 [F4]")
        self.btn_delete = QPushButton("삭제 [F5]")
        self.btn_stop = QPushButton("사용중지 [F6]")
        self.btn_close = QPushButton("닫기")
        top.addWidget(QLabel("검색")); top.addWidget(self.search, 1); top.addWidget(self.include_inactive)
        for button in (self.btn_search, self.btn_refresh, self.btn_save, self.btn_delete, self.btn_stop, self.btn_close):
            top.addWidget(button)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)
        left = QWidget(); ll = QVBoxLayout(left); ll.addWidget(QLabel("LOT 목록"))
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["LOT번호", "상품명", "창고", "BL", "컨테이너", "이력번호", "상태"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5, 6): header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        ll.addWidget(self.table); splitter.addWidget(left)

        right = QWidget(); rl = QVBoxLayout(right)
        identity = QGroupBox("LOT 기본정보")
        g = QGridLayout(identity)
        self.company_label = QLabel(f"{app_context.company_code} {app_context.company_name}")
        self.lot_code = QLineEdit(); self.lot_code.setReadOnly(True); self.lot_code.setPlaceholderText("자동발번")
        self.business_lot_no = QLineEdit(); self.business_lot_no.setPlaceholderText("공급자/포장지 LOT번호 (선택)")
        self.source_type = QComboBox(); self.source_type.addItem("수입", "IMPORT"); self.source_type.addItem("국내매입", "DOMESTIC")
        self.status = QComboBox(); self.status.addItem("사용중", "OPEN"); self.status.addItem("보류", "HOLD"); self.status.addItem("마감", "CLOSED")
        self.product = QComboBox(); self.product.setEditable(True); self.product.setInsertPolicy(QComboBox.NoInsert)
        self.warehouse = QComboBox(); self.warehouse.setEditable(True); self.warehouse.setInsertPolicy(QComboBox.NoInsert)
        g.addWidget(QLabel("업무회사"), 0, 0); g.addWidget(self.company_label, 0, 1)
        g.addWidget(QLabel("LOT번호"), 0, 2); g.addWidget(self.lot_code, 0, 3)
        g.addWidget(QLabel("LOT구분 *"), 1, 0); g.addWidget(self.source_type, 1, 1)
        g.addWidget(QLabel("업무상 LOT번호"), 1, 2); g.addWidget(self.business_lot_no, 1, 3)
        g.addWidget(QLabel("상품 *"), 2, 0); g.addWidget(self.product, 2, 1, 1, 3)
        g.addWidget(QLabel("최초 입고창고 *"), 3, 0); g.addWidget(self.warehouse, 3, 1)
        g.addWidget(QLabel("LOT상태"), 3, 2); g.addWidget(self.status, 3, 3)
        rl.addWidget(identity)

        trace = QGroupBox("수입·추적정보")
        tg = QGridLayout(trace)
        self.bl_no = QLineEdit(); self.container_no = QLineEdit(); self.history_no = QLineEdit()
        self.origin = QLineEdit(); self.est_no = QLineEdit()
        self.production_date = self._optional_date(); self.expiry_date = self._optional_date()
        tg.addWidget(QLabel("BL번호"), 0, 0); tg.addWidget(self.bl_no, 0, 1)
        tg.addWidget(QLabel("컨테이너번호"), 0, 2); tg.addWidget(self.container_no, 0, 3)
        tg.addWidget(QLabel("축산물이력번호"), 1, 0); tg.addWidget(self.history_no, 1, 1)
        tg.addWidget(QLabel("원산지"), 1, 2); tg.addWidget(self.origin, 1, 3)
        tg.addWidget(QLabel("EST NO"), 2, 0); tg.addWidget(self.est_no, 2, 1)
        tg.addWidget(QLabel("생산일"), 2, 2); tg.addWidget(self.production_date, 2, 3)
        tg.addWidget(QLabel("소비기한"), 3, 2); tg.addWidget(self.expiry_date, 3, 3)
        rl.addWidget(trace)

        cost_box = QGroupBox("LOT별 개별원가")
        cg = QGridLayout(cost_box)
        self.individual_cost = QDoubleSpinBox(); self.individual_cost.setDecimals(0)
        self.individual_cost.setSingleStep(1)
        self.individual_cost.setMaximum(999999999); self.individual_cost.setGroupSeparatorShown(True)
        self.individual_cost.setToolTip("가격과 개별원가는 소수점 없이 원 단위로 관리하며 소수점 이하는 올림합니다.")
        cg.addWidget(QLabel("개별원가(원/KG)"), 0, 0); cg.addWidget(self.individual_cost, 0, 1)
        cg.addWidget(QLabel("※ 입고 BOX·KG와 현재고는 다음 입출고 Transaction에서 관리합니다."), 1, 0, 1, 4)
        rl.addWidget(cost_box)

        memo_box = QGroupBox("메모"); ml = QVBoxLayout(memo_box)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(105); ml.addWidget(self.memo)
        rl.addWidget(memo_box); rl.addStretch()
        splitter.addWidget(right); splitter.setSizes([620, 700])

    @staticmethod
    def _optional_date():
        widget = QDateEdit()
        widget.setCalendarPopup(True); widget.setDisplayFormat("yyyy-MM-dd")
        widget.setMinimumDate(QDate(1900, 1, 1)); widget.setSpecialValueText("없음")
        widget.setDate(widget.minimumDate())
        return widget

    def _connect_events(self):
        self.btn_search.clicked.connect(self.load_lots); self.search.returnPressed.connect(self.load_lots)
        self.btn_refresh.clicked.connect(self.refresh_view); self.include_inactive.toggled.connect(self.load_lots)
        self.btn_save.clicked.connect(self.save_lot); self.btn_delete.clicked.connect(self.delete_lot)
        self.btn_stop.clicked.connect(self.deactivate_lot); self.btn_close.clicked.connect(self.close_window)
        self.table.itemSelectionChanged.connect(self.on_selected); self.product.currentIndexChanged.connect(self._product_changed)
        self.btn_save.setShortcut("F4"); self.btn_delete.setShortcut("F5")
        self.btn_stop.setShortcut("F6"); self.btn_search.setShortcut("F7")

    def _setup_enter_navigation(self):
        self.nav = [self.source_type, self.business_lot_no, self.product, self.warehouse, self.status,
                    self.bl_no, self.container_no, self.history_no, self.origin, self.est_no,
                    self.production_date, self.expiry_date, self.individual_cost]
        for widget in self.nav: widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and obj in self.nav:
            index = self.nav.index(obj)
            (self.nav[index + 1] if index + 1 < len(self.nav) else self.memo).setFocus()
            return True
        return super().eventFilter(obj, event)

    def _url(self, suffix=""):
        return f"{API_BASE_URL}/companies/{app_context.company_code}/lots{suffix}"

    def initial_load(self):
        if not app_context.company_code:
            QMessageBox.warning(self, "업무회사 확인", "먼저 업무회사를 선택해 주세요.")
            return
        try:
            products = httpx.get(f"{API_BASE_URL}/products", timeout=10); products.raise_for_status()
            warehouses = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses", timeout=10); warehouses.raise_for_status()
            self.product.clear()
            for item in sorted(products.json(), key=lambda row: (row.get("product_name") or "", row.get("product_code") or "")):
                self.product.addItem(f"{item['product_name']} [{item['product_code']}]", item)
            self.warehouse.clear()
            for item in warehouses.json(): self.warehouse.addItem(f"{item['warehouse_name']} [{item['warehouse_code']}]", item["warehouse_id"])
            self.clear_form(); self.load_lots()
        except Exception as exc:
            QMessageBox.critical(self, "초기자료 조회 오류", self._error_text(exc))

    def refresh_view(self):
        self.search.clear()
        if self.include_inactive.isChecked(): self.include_inactive.setChecked(False)
        else: self.initial_load()

    def load_lots(self):
        if self._loading or not app_context.company_code: return
        self._loading = True; self.btn_search.setText("조회 중..."); self.btn_search.setEnabled(False)
        try:
            response = httpx.get(self._url(), params={"search": self.search.text(), "include_inactive": self.include_inactive.isChecked()}, timeout=10)
            response.raise_for_status(); self.rows = response.json(); self.table.setRowCount(len(self.rows))
            status_names = {"OPEN":"사용중", "HOLD":"보류", "CLOSED":"마감"}
            for row, item in enumerate(self.rows):
                values = (item["lot_code"], item["product_name"], item["warehouse_name"], item.get("bl_no"),
                          item.get("container_no"), item.get("history_no"), status_names.get(item["status"], item["status"]))
                for col, value in enumerate(values): self.table.setItem(row, col, QTableWidgetItem(str(value or "")))
        except Exception as exc: QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally:
            self._loading = False; self.btn_search.setText("조회 [F7]"); self.btn_search.setEnabled(True)

    def clear_form(self):
        self.current_id = None; self.lot_code.clear(); self.business_lot_no.clear()
        self.source_type.setCurrentIndex(0); self.status.setCurrentIndex(0)
        for field in (self.bl_no, self.container_no, self.history_no, self.origin, self.est_no): field.clear()
        self.production_date.setDate(self.production_date.minimumDate()); self.expiry_date.setDate(self.expiry_date.minimumDate())
        self.individual_cost.setValue(0); self.memo.clear(); self.table.clearSelection()
        self.product.setCurrentIndex(-1); self.warehouse.setCurrentIndex(-1)
        self.btn_save.setEnabled(False); self.btn_delete.setEnabled(False); self.btn_stop.setEnabled(False)

    def _product_changed(self):
        item = self.product.currentData()
        if isinstance(item, dict) and not self.current_id and not self.origin.text().strip():
            self.origin.setText(item.get("origin") or "")

    def on_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows): return
        item = self.rows[row]; self.current_id = item["lot_id"]
        self.lot_code.setText(item["lot_code"]); self.business_lot_no.setText(item.get("business_lot_no") or "")
        self._set_combo(self.source_type, item["source_type"]); self._set_combo(self.status, item["status"])
        self._set_combo(self.product, item["product_id"], dict_key="product_id"); self._set_combo(self.warehouse, item["warehouse_id"])
        for widget, key in ((self.bl_no,"bl_no"),(self.container_no,"container_no"),(self.history_no,"history_no"),(self.origin,"origin"),(self.est_no,"est_no")):
            widget.setText(item.get(key) or "")
        self._set_date(self.production_date, item.get("production_date")); self._set_date(self.expiry_date, item.get("expiry_date"))
        self.individual_cost.setValue(float(item.get("individual_cost") or 0)); self.memo.setPlainText(item.get("memo") or "")
        self.btn_save.setEnabled(True); self.btn_delete.setEnabled(True); self.btn_stop.setEnabled(True)

    def save_lot(self):
        if not self.current_id:
            QMessageBox.warning(self, "선택 확인", "보정할 LOT를 목록에서 선택해 주세요."); return
        if self.product.currentIndex() < 0: QMessageBox.warning(self, "입력 확인", "상품을 선택해 주세요."); return
        if self.warehouse.currentIndex() < 0: QMessageBox.warning(self, "입력 확인", "창고를 선택해 주세요."); return
        if self.expiry_date.date() != self.expiry_date.minimumDate() and self.production_date.date() != self.production_date.minimumDate() and self.expiry_date.date() < self.production_date.date():
            QMessageBox.warning(self, "입력 확인", "소비기한은 생산일보다 빠를 수 없습니다."); return
        try:
            data = self._payload()
            response = httpx.put(self._url(f"/{self.current_id}"), json=data, timeout=10)
            response.raise_for_status(); saved = response.json(); self.current_id = saved["lot_id"]; self.lot_code.setText(saved["lot_code"])
            self.load_lots(); self._select_id(self.current_id); QMessageBox.information(self, "저장 완료", "LOT 정보가 저장되었습니다.")
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))

    def deactivate_lot(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "사용중지할 LOT를 선택해 주세요."); return
        if QMessageBox.question(self, "사용중지", "이 LOT를 사용중지하시겠습니까?") != QMessageBox.Yes: return
        try:
            response = httpx.delete(self._url(f"/{self.current_id}"), timeout=10); response.raise_for_status()
            self.clear_form(); self.load_lots()
        except Exception as exc: QMessageBox.critical(self, "처리 오류", self._error_text(exc))

    def delete_lot(self):
        if not self.current_id:
            QMessageBox.warning(self, "선택 확인", "삭제할 LOT를 선택해 주세요."); return
        if QMessageBox.question(
            self, "LOT 삭제 확인",
            "입고·출고·재고 등 연결자료가 없는 LOT만 삭제할 수 있습니다.\n\n선택한 LOT를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        ) != QMessageBox.Yes: return
        if QMessageBox.question(
            self, "LOT 삭제 최종 확인",
            f"LOT번호: {self.lot_code.text()}\n\n삭제 후 복구할 수 없습니다. 계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
        ) != QMessageBox.Yes: return
        try:
            response = httpx.delete(self._url(f"/{self.current_id}"), params={"permanent": True}, timeout=10)
            response.raise_for_status(); self.clear_form(); self.load_lots()
            QMessageBox.information(self, "삭제 완료", "연결자료가 없는 LOT가 삭제되었습니다.")
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", self._error_text(exc))

    def close_window(self):
        parent = self.parentWidget()
        if isinstance(parent, QMdiSubWindow): parent.close()
        else: self.close()

    def _payload(self):
        product = self.product.currentData()
        return {
            "lot_code": self.lot_code.text(), "business_lot_no": self.business_lot_no.text().strip() or None,
            "source_type": self.source_type.currentData(), "product_id": product["product_id"],
            "warehouse_id": self.warehouse.currentData(), "bl_no": self.bl_no.text().strip() or None,
            "container_no": self.container_no.text().strip().upper() or None, "history_no": self.history_no.text().strip() or None,
            "origin": self.origin.text().strip() or None, "est_no": self.est_no.text().strip() or None,
            "production_date": self._date_value(self.production_date), "expiry_date": self._date_value(self.expiry_date),
            "individual_cost": self.individual_cost.value(), "status": self.status.currentData(),
            "memo": self.memo.toPlainText().strip() or None, "use_yn": True,
        }

    def _select_id(self, lot_id):
        for row, item in enumerate(self.rows):
            if item["lot_id"] == lot_id: self.table.selectRow(row); return

    @staticmethod
    def _set_combo(combo, value, dict_key=None):
        index = -1
        for row in range(combo.count()):
            data = combo.itemData(row)
            candidate = data.get(dict_key) if dict_key and isinstance(data, dict) else data
            if candidate == value: index = row; break
        combo.setCurrentIndex(max(0, index))

    @staticmethod
    def _set_date(widget, value):
        parsed = QDate.fromString(value or "", "yyyy-MM-dd")
        widget.setDate(parsed if parsed.isValid() else widget.minimumDate())

    @staticmethod
    def _date_value(widget):
        return None if widget.date() == widget.minimumDate() else widget.date().toString("yyyy-MM-dd")

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return exc.response.json().get("detail", str(exc))
            except Exception: pass
        return str(exc)
