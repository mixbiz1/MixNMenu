import httpx
from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
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


class WarehouseRegWindow(QWidget):
    """창고 공통 Master + 현재 업무회사 사용/요율 입력 화면."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        self.rows = []
        self._loading = False
        self.setWindowTitle("창고입력")
        self.resize(1280, 760)
        self._build_ui()
        self._connect_events()
        QTimer.singleShot(50, self.load_warehouses)

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("창고명 / 코드 / 주소")
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.btn_search = QPushButton("조회")
        self.btn_new = QPushButton("신규")
        self.btn_save = QPushButton("저장")
        self.btn_stop = QPushButton("사용중지")
        self.btn_close = QPushButton("닫기")
        top.addWidget(QLabel("검색")); top.addWidget(self.search, 1); top.addWidget(self.include_inactive)
        for button in (self.btn_search, self.btn_new, self.btn_save, self.btn_stop, self.btn_close):
            top.addWidget(button)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal); root.addWidget(splitter, 1)
        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.addWidget(QLabel("창고 목록"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["창고명", "코드", "보관유형", "창고구분"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3): header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        left_layout.addWidget(self.table); splitter.addWidget(left)

        right = QWidget(); right_layout = QVBoxLayout(right)
        master = QGroupBox("창고 공통정보 (회사 간 공유)"); grid = QGridLayout(master)
        self.code = QLineEdit(); self.code.setReadOnly(True); self.code.setPlaceholderText("자동발번")
        self.name = QLineEdit()
        self.warehouse_type = QComboBox(); self.warehouse_type.addItem("일반창고", "GENERAL"); self.warehouse_type.addItem("보세창고", "BONDED")
        self.storage_type = QComboBox()
        for label, value in (("냉동", "FROZEN"), ("냉장", "CHILLED"), ("상온", "AMBIENT"), ("혼합", "MIXED")):
            self.storage_type.addItem(label, value)
        self.biz_no = QLineEdit(); self.zip_code = QLineEdit(); self.address = QLineEdit()
        self.phone = QLineEdit(); self.contact = QLineEdit(); self.meatwatch = QLineEdit()
        grid.addWidget(QLabel("창고코드"), 0, 0); grid.addWidget(self.code, 0, 1)
        grid.addWidget(QLabel("창고명 *"), 0, 2); grid.addWidget(self.name, 0, 3)
        grid.addWidget(QLabel("창고구분"), 1, 0); grid.addWidget(self.warehouse_type, 1, 1)
        grid.addWidget(QLabel("보관유형"), 1, 2); grid.addWidget(self.storage_type, 1, 3)
        grid.addWidget(QLabel("사업자번호"), 2, 0); grid.addWidget(self.biz_no, 2, 1)
        grid.addWidget(QLabel("우편번호"), 2, 2); grid.addWidget(self.zip_code, 2, 3)
        grid.addWidget(QLabel("주소"), 3, 0); grid.addWidget(self.address, 3, 1, 1, 3)
        grid.addWidget(QLabel("전화"), 4, 0); grid.addWidget(self.phone, 4, 1)
        grid.addWidget(QLabel("담당자"), 4, 2); grid.addWidget(self.contact, 4, 3)
        grid.addWidget(QLabel("축산물이력제 사업장번호"), 5, 0); grid.addWidget(self.meatwatch, 5, 1, 1, 3)
        right_layout.addWidget(master)

        company = QGroupBox("현재 업무회사별 사용 및 기본요율"); rates = QGridLayout(company)
        self.company_label = QLabel(f"{app_context.company_code} {app_context.company_name}")
        self.company_use = ReadableCheckBox("현재 회사에서 사용"); self.company_use.setChecked(True)
        self.valid_from = QDateEdit(QDate.currentDate()); self.valid_from.setCalendarPopup(True); self.valid_from.setDisplayFormat("yyyy-MM-dd")
        self.valid_to = QDateEdit(); self.valid_to.setCalendarPopup(True); self.valid_to.setDisplayFormat("yyyy-MM-dd")
        self.valid_to.setSpecialValueText("없음"); self.valid_to.setMinimumDate(QDate(1900, 1, 1)); self.valid_to.setDate(self.valid_to.minimumDate())
        self.inbound_rate = self._money_spin(2); self.outbound_rate = self._money_spin(2)
        self.storage_rate = self._money_spin(4); self.weighing_rate = self._money_spin(2)
        self.vat_yn = ReadableCheckBox("부가세 별도"); self.vat_yn.setChecked(True)
        rates.addWidget(QLabel("업무회사"), 0, 0); rates.addWidget(self.company_label, 0, 1); rates.addWidget(self.company_use, 0, 2, 1, 2)
        rates.addWidget(QLabel("적용 시작일"), 1, 0); rates.addWidget(self.valid_from, 1, 1)
        rates.addWidget(QLabel("적용 종료일"), 1, 2); rates.addWidget(self.valid_to, 1, 3)
        rates.addWidget(QLabel("입고료(원/kg)"), 2, 0); rates.addWidget(self.inbound_rate, 2, 1)
        rates.addWidget(QLabel("출고료(원/kg)"), 2, 2); rates.addWidget(self.outbound_rate, 2, 3)
        rates.addWidget(QLabel("보관료(원/kg·일)"), 3, 0); rates.addWidget(self.storage_rate, 3, 1)
        rates.addWidget(QLabel("계근료(원/box)"), 3, 2); rates.addWidget(self.weighing_rate, 3, 3)
        rates.addWidget(QLabel("부가세"), 4, 0); rates.addWidget(self.vat_yn, 4, 1)
        right_layout.addWidget(company)

        memo_box = QGroupBox("메모"); memo_layout = QVBoxLayout(memo_box)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(90); memo_layout.addWidget(self.memo)
        right_layout.addWidget(memo_box); right_layout.addStretch()
        splitter.addWidget(right); splitter.setSizes([450, 830])

    def _money_spin(self, decimals):
        widget = QDoubleSpinBox(); widget.setDecimals(decimals); widget.setMaximum(99999999); widget.setGroupSeparatorShown(True)
        return widget

    def _connect_events(self):
        self.btn_search.clicked.connect(self.load_warehouses)
        self.search.returnPressed.connect(self.load_warehouses)
        self.include_inactive.toggled.connect(self.load_warehouses)
        self.btn_new.clicked.connect(self.new_warehouse)
        self.btn_save.clicked.connect(self.save_warehouse)
        self.btn_stop.clicked.connect(self.deactivate_warehouse)
        self.btn_close.clicked.connect(self.close)
        self.table.itemSelectionChanged.connect(self.on_selected)

    def _url(self, suffix=""):
        return f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses{suffix}"

    def load_warehouses(self):
        if self._loading: return
        self._loading = True; self.btn_search.setText("조회 중..."); self.btn_search.setEnabled(False)
        try:
            response = httpx.get(self._url(), params={"search": self.search.text(), "include_inactive": self.include_inactive.isChecked()}, timeout=10)
            response.raise_for_status(); self.rows = response.json(); self.table.setRowCount(len(self.rows))
            storage_names = {"FROZEN":"냉동", "CHILLED":"냉장", "AMBIENT":"상온", "MIXED":"혼합"}
            type_names = {"GENERAL":"일반", "BONDED":"보세"}
            for row, item in enumerate(self.rows):
                values = (item["warehouse_name"], item["warehouse_code"], storage_names.get(item["storage_type"], item["storage_type"]), type_names.get(item["warehouse_type"], item["warehouse_type"]))
                for col, value in enumerate(values): self.table.setItem(row, col, QTableWidgetItem(str(value or "")))
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally:
            self._loading = False; self.btn_search.setText("조회"); self.btn_search.setEnabled(True)

    def new_warehouse(self):
        self.current_id = None
        for field in (self.code, self.name, self.biz_no, self.zip_code, self.address, self.phone, self.contact, self.meatwatch): field.clear()
        self.warehouse_type.setCurrentIndex(0); self.storage_type.setCurrentIndex(0)
        self.company_use.setChecked(True); self.valid_from.setDate(QDate.currentDate()); self.valid_to.setDate(self.valid_to.minimumDate())
        for spin in (self.inbound_rate, self.outbound_rate, self.storage_rate, self.weighing_rate): spin.setValue(0)
        self.vat_yn.setChecked(True); self.memo.clear(); self.name.setFocus()

    def on_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows): return
        item = self.rows[row]; self.current_id = item["warehouse_id"]
        self.code.setText(item["warehouse_code"]); self.name.setText(item["warehouse_name"])
        self._set_combo(self.warehouse_type, item["warehouse_type"]); self._set_combo(self.storage_type, item["storage_type"])
        self.biz_no.setText(item.get("biz_no") or ""); self.zip_code.setText(item.get("zip_code") or ""); self.address.setText(item.get("address") or "")
        self.phone.setText(item.get("phone") or ""); self.contact.setText(item.get("contact_name") or ""); self.meatwatch.setText(item.get("meatwatch_bplc_no") or "")
        self.company_use.setChecked(item.get("company_use_yn", False)); self._set_date(self.valid_from, item.get("valid_from"), QDate.currentDate())
        self._set_date(self.valid_to, item.get("valid_to"), self.valid_to.minimumDate())
        self.inbound_rate.setValue(item.get("inbound_rate", 0)); self.outbound_rate.setValue(item.get("outbound_rate", 0)); self.storage_rate.setValue(item.get("storage_rate", 0)); self.weighing_rate.setValue(item.get("weighing_rate", 0))
        self.vat_yn.setChecked(item.get("vat_yn", True)); self.memo.setPlainText(item.get("memo") or "")

    def save_warehouse(self):
        if not self.name.text().strip(): QMessageBox.warning(self, "입력 확인", "창고명을 입력해 주세요."); self.name.setFocus(); return
        if self.valid_to.date() != self.valid_to.minimumDate() and self.valid_to.date() < self.valid_from.date():
            QMessageBox.warning(self, "입력 확인", "적용 종료일은 시작일보다 빠를 수 없습니다."); return
        data = self._payload()
        try:
            if self.current_id:
                response = httpx.put(self._url(f"/{self.current_id}"), json=data, timeout=10)
            else:
                response = httpx.post(self._url(), json=data, timeout=10)
            response.raise_for_status(); saved = response.json(); self.current_id = saved["warehouse_id"]; self.code.setText(saved["warehouse_code"])
            self.load_warehouses(); self._select_id(self.current_id); QMessageBox.information(self, "저장 완료", "창고 정보가 저장되었습니다.")
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", self._error_text(exc))

    def deactivate_warehouse(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "사용중지할 창고를 선택해 주세요."); return
        if QMessageBox.question(self, "사용중지", "현재 업무회사에서 이 창고의 사용을 중지하시겠습니까?") != QMessageBox.Yes: return
        try:
            response = httpx.delete(self._url(f"/{self.current_id}"), timeout=10); response.raise_for_status(); self.new_warehouse(); self.load_warehouses()
        except Exception as exc: QMessageBox.critical(self, "처리 오류", self._error_text(exc))

    def _payload(self):
        return {
            "warehouse_code": self.code.text(), "warehouse_name": self.name.text().strip(),
            "warehouse_type": self.warehouse_type.currentData(), "storage_type": self.storage_type.currentData(),
            "biz_no": self.biz_no.text().strip() or None, "zip_code": self.zip_code.text().strip() or None,
            "address": self.address.text().strip() or None, "phone": self.phone.text().strip() or None,
            "contact_name": self.contact.text().strip() or None, "meatwatch_bplc_no": self.meatwatch.text().strip() or None,
            "memo": self.memo.toPlainText().strip() or None, "use_yn": True, "company_use_yn": self.company_use.isChecked(),
            "valid_from": self.valid_from.date().toString("yyyy-MM-dd"),
            "valid_to": None if self.valid_to.date() == self.valid_to.minimumDate() else self.valid_to.date().toString("yyyy-MM-dd"),
            "inbound_rate": self.inbound_rate.value(), "outbound_rate": self.outbound_rate.value(),
            "storage_rate": self.storage_rate.value(), "weighing_rate": self.weighing_rate.value(), "vat_yn": self.vat_yn.isChecked(),
        }

    def _select_id(self, warehouse_id):
        for row, item in enumerate(self.rows):
            if item["warehouse_id"] == warehouse_id: self.table.selectRow(row); return

    @staticmethod
    def _set_combo(combo, value):
        index = combo.findData(value); combo.setCurrentIndex(max(0, index))

    @staticmethod
    def _set_date(widget, value, fallback):
        parsed = QDate.fromString(value or "", "yyyy-MM-dd"); widget.setDate(parsed if parsed.isValid() else fallback)

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return exc.response.json().get("detail", str(exc))
            except Exception: pass
        return str(exc)
