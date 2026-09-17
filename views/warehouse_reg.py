import webbrowser
import httpx
from PySide6.QtCore import QDate, QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QApplication, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QMdiSubWindow,
    QTextEdit, QVBoxLayout, QWidget,
)

from app_context import app_context
from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update

API_BASE_URL = "http://127.0.0.1:8000/api/v1"
CALC_UNITS = (("KG당", "KG"), ("BOX당", "BOX"), ("KG·일당", "KG_DAY"), ("건당 정액", "FIXED"))
DEFAULT_CHARGES = (("보관비", "KG_DAY"), ("입출고비", "KG"), ("상하차비", "BOX"), ("계근비", "BOX"))


class ReadableCheckBox(QCheckBox):
    def __init__(self, label, parent=None):
        super().__init__(parent); self._label = label
        self.toggled.connect(self._show_state); self._show_state(False)

    def _show_state(self, checked):
        self.setText(f"{'☑' if checked else '□'} {self._label}")


class WarehouseRegWindow(QWidget):
    """창고 공통 Master + 회사별 사용/기간별 가변 비용항목 입력 화면."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None; self.rows = []; self._loading = False; self.nav = []
        self.setWindowTitle("창고입력"); self.resize(1280, 800)
        self._build_ui(); self._connect_events(); self._setup_enter_navigation()
        QTimer.singleShot(50, self.load_warehouses)

    def _build_ui(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText("창고명 / 코드 / 주소")
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.btn_search = QPushButton("조회 [F7]"); self.btn_refresh = QPushButton("새로고침")
        self.btn_new = QPushButton("신규 [F2]"); self.btn_save = QPushButton("저장 [F4]")
        self.btn_stop = QPushButton("사용중지 [F6]"); self.btn_close = QPushButton("닫기")
        top.addWidget(QLabel("검색")); top.addWidget(self.search, 1); top.addWidget(self.include_inactive)
        for button in (self.btn_search, self.btn_refresh, self.btn_new, self.btn_save, self.btn_stop, self.btn_close): top.addWidget(button)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal); root.addWidget(splitter, 1)
        left = QWidget(); ll = QVBoxLayout(left); ll.addWidget(QLabel("창고 목록"))
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["창고명", "코드", "보관유형", "창고구분"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.table, (260, 100, 100, 100))
        ll.addWidget(self.table); splitter.addWidget(left)

        right = QWidget(); rl = QVBoxLayout(right)
        master = QGroupBox("창고 공통정보 (회사 간 공유)"); g = QGridLayout(master)
        self.code = QLineEdit(); self.code.setReadOnly(True); self.code.setPlaceholderText("자동발번"); self.name = QLineEdit()
        self.warehouse_type = QComboBox(); self.warehouse_type.addItem("보세창고", "BONDED"); self.warehouse_type.addItem("일반창고", "GENERAL")
        self.storage_type = QComboBox()
        for label, value in (("혼합", "MIXED"), ("냉동", "FROZEN"), ("냉장", "CHILLED"), ("상온", "AMBIENT")): self.storage_type.addItem(label, value)
        self.biz_no = QLineEdit(); self.zip_code = QLineEdit(); self.address = QLineEdit(); self.phone = QLineEdit(); self.fax = QLineEdit()
        self.contact = QLineEdit(); self.meatwatch = QLineEdit(); self.web_url = QLineEdit(); self.web_url.setPlaceholderText("https://...")
        self.web_user_id = QLineEdit(); self.web_user_id.setPlaceholderText("입출고지시 사이트 사용자 ID")
        self.btn_open_web = QPushButton("웹주소 이동"); self.btn_open_web.setMaximumWidth(105)
        self.btn_open_web.setToolTip("창고 사이트를 열고 저장된 ID를 클립보드에 복사합니다.")
        self.web_id_label = QLabel("ID")
        g.addWidget(QLabel("창고코드"), 0, 0); g.addWidget(self.code, 0, 1); g.addWidget(QLabel("창고명 *"), 0, 2); g.addWidget(self.name, 0, 3)
        g.addWidget(QLabel("창고구분"), 1, 0); g.addWidget(self.warehouse_type, 1, 1); g.addWidget(QLabel("보관유형"), 1, 2); g.addWidget(self.storage_type, 1, 3)
        g.addWidget(QLabel("사업자번호"), 2, 0); g.addWidget(self.biz_no, 2, 1); g.addWidget(QLabel("우편번호"), 2, 2); g.addWidget(self.zip_code, 2, 3)
        g.addWidget(QLabel("주소"), 3, 0); g.addWidget(self.address, 3, 1, 1, 3)
        g.addWidget(QLabel("전화"), 4, 0); g.addWidget(self.phone, 4, 1); g.addWidget(QLabel("팩스"), 4, 2); g.addWidget(self.fax, 4, 3)
        g.addWidget(QLabel("담당자"), 5, 0); g.addWidget(self.contact, 5, 1); g.addWidget(QLabel("축산물이력제 사업장번호"), 5, 2); g.addWidget(self.meatwatch, 5, 3)
        web_row = QHBoxLayout(); web_row.setContentsMargins(0, 0, 0, 0)
        web_row.addWidget(self.web_url, 3); web_row.addWidget(self.btn_open_web)
        web_row.addWidget(self.web_id_label); web_row.addWidget(self.web_user_id, 1)
        g.addWidget(QLabel("입출고 웹주소"), 6, 0); g.addLayout(web_row, 6, 1, 1, 3); rl.addWidget(master)

        company = QGroupBox("현재 업무회사별 사용 및 비용 적용기간"); cg = QGridLayout(company)
        self.company_label = QLabel(f"{app_context.company_code} {app_context.company_name}")
        self.company_use = ReadableCheckBox("현재 회사에서 사용"); self.company_use.setChecked(True)
        self.valid_from = QDateEdit(QDate.currentDate()); self.valid_from.setCalendarPopup(True); self.valid_from.setDisplayFormat("yyyy-MM-dd")
        self.valid_to = QDateEdit(); self.valid_to.setCalendarPopup(True); self.valid_to.setDisplayFormat("yyyy-MM-dd")
        self.valid_to.setSpecialValueText("없음"); self.valid_to.setMinimumDate(QDate(1900, 1, 1)); self.valid_to.setDate(self.valid_to.minimumDate())
        self.vat_yn = ReadableCheckBox("부가세 별도"); self.vat_yn.setChecked(True)
        cg.addWidget(QLabel("업무회사"), 0, 0); cg.addWidget(self.company_label, 0, 1); cg.addWidget(self.company_use, 0, 2, 1, 2)
        cg.addWidget(QLabel("적용 시작일"), 1, 0); cg.addWidget(self.valid_from, 1, 1); cg.addWidget(QLabel("적용 종료일"), 1, 2); cg.addWidget(self.valid_to, 1, 3)
        cg.addWidget(QLabel("부가세"), 2, 0); cg.addWidget(self.vat_yn, 2, 1); rl.addWidget(company)

        charge_box = QGroupBox("창고 비용항목 (창고별 추가·삭제 가능)"); charge_layout = QVBoxLayout(charge_box)
        buttons = QHBoxLayout(); self.btn_add_charge = QPushButton("＋ 비용항목 추가"); self.btn_remove_charge = QPushButton("－ 선택항목 삭제")
        buttons.addWidget(self.btn_add_charge); buttons.addWidget(self.btn_remove_charge); buttons.addStretch(); charge_layout.addLayout(buttons)
        self.charge_table = QTableWidget(0, 3); self.charge_table.setHorizontalHeaderLabels(["비용항목", "계산기준", "요율/금액(원)"])
        ch = self.charge_table.horizontalHeader(); ch.setSectionResizeMode(0, QHeaderView.Stretch); ch.setSectionResizeMode(1, QHeaderView.ResizeToContents); ch.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.charge_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.charge_table.setMinimumHeight(155); charge_layout.addWidget(self.charge_table); rl.addWidget(charge_box)

        memo_box = QGroupBox("메모"); ml = QVBoxLayout(memo_box); self.memo = QTextEdit(); self.memo.setMaximumHeight(75); ml.addWidget(self.memo)
        rl.addWidget(memo_box); splitter.addWidget(right); splitter.setSizes([430, 850])

    def _connect_events(self):
        self.btn_search.clicked.connect(self.load_warehouses); self.btn_refresh.clicked.connect(self.refresh_view); self.search.returnPressed.connect(self.load_warehouses)
        self.include_inactive.toggled.connect(self.load_warehouses); self.btn_new.clicked.connect(self.new_warehouse)
        self.btn_save.clicked.connect(self.save_warehouse); self.btn_stop.clicked.connect(self.deactivate_warehouse); self.btn_close.clicked.connect(self.close_window)
        self.table.itemSelectionChanged.connect(self.on_selected); self.btn_add_charge.clicked.connect(lambda: self.add_charge_row()); self.btn_remove_charge.clicked.connect(self.remove_charge_row)
        self.btn_open_web.clicked.connect(self.open_web_url)
        self.btn_new.setShortcut("F2"); self.btn_save.setShortcut("F4"); self.btn_stop.setShortcut("F6"); self.btn_search.setShortcut("F7")

    def _setup_enter_navigation(self):
        self.nav = [self.name, self.warehouse_type, self.storage_type, self.biz_no, self.zip_code, self.address, self.phone, self.fax,
                    self.contact, self.meatwatch, self.web_url, self.web_user_id, self.company_use, self.valid_from, self.valid_to, self.vat_yn]
        for widget in self.nav: widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and obj in self.nav:
            index = self.nav.index(obj); (self.nav[index + 1] if index + 1 < len(self.nav) else self.btn_add_charge).setFocus(); return True
        return super().eventFilter(obj, event)

    def _url(self, suffix=""): return f"{API_BASE_URL}/companies/{app_context.company_code}/warehouses{suffix}"

    def refresh_view(self):
        self.search.clear()
        if self.include_inactive.isChecked():
            self.include_inactive.setChecked(False)  # toggled 신호가 1회 조회
        else:
            self.load_warehouses()

    def open_web_url(self):
        url = self.web_url.text().strip()
        if not url: QMessageBox.information(self, "웹주소 확인", "입출고 웹주소를 입력해 주세요."); self.web_url.setFocus(); return
        web_user_id = self.web_user_id.text().strip()
        if web_user_id:
            QApplication.clipboard().setText(web_user_id)
        if not url.lower().startswith(("http://", "https://")): url = "https://" + url
        webbrowser.open(url)

    def close_window(self):
        parent = self.parentWidget()
        if isinstance(parent, QMdiSubWindow): parent.close()
        else: self.close()

    def load_warehouses(self):
        if self._loading: return
        self._loading = True; self.btn_search.setText("조회 중..."); self.btn_search.setEnabled(False)
        try:
            response = httpx.get(self._url(), params={"search": self.search.text(), "include_inactive": self.include_inactive.isChecked()}, timeout=10)
            response.raise_for_status(); self.rows = response.json(); begin_list_update(self.table); self.table.setRowCount(len(self.rows))
            storage = {"FROZEN":"냉동", "CHILLED":"냉장", "AMBIENT":"상온", "MIXED":"혼합"}; kind = {"GENERAL":"일반", "BONDED":"보세"}
            for row, item in enumerate(self.rows):
                for col, value in enumerate((item["warehouse_name"], item["warehouse_code"], storage.get(item["storage_type"], item["storage_type"]), kind.get(item["warehouse_type"], item["warehouse_type"]))): self.table.setItem(row, col, ListTableItem(str(value or "")))
                self.table.item(row, 0).setData(Qt.UserRole, item)
            end_list_update(self.table, (160, 85, 85, 85), (360, 140, 130, 130))
        except Exception as exc: QMessageBox.critical(self, "조회 오류", self._error_text(exc))
        finally: self._loading = False; self.btn_search.setText("조회"); self.btn_search.setEnabled(True)

    def new_warehouse(self):
        self.current_id = None
        for field in (self.code, self.name, self.biz_no, self.zip_code, self.address, self.phone, self.fax, self.contact, self.meatwatch, self.web_url, self.web_user_id): field.clear()
        self.warehouse_type.setCurrentIndex(0); self.storage_type.setCurrentIndex(0); self.company_use.setChecked(True)
        self.valid_from.setDate(QDate.currentDate()); self.valid_to.setDate(self.valid_to.minimumDate()); self.vat_yn.setChecked(True); self.memo.clear(); self.charge_table.setRowCount(0)
        for name, unit in DEFAULT_CHARGES: self.add_charge_row(name, unit, 0)
        self.name.setFocus()

    def add_charge_row(self, name="", unit="KG", amount=0):
        row = self.charge_table.rowCount(); self.charge_table.insertRow(row); self.charge_table.setItem(row, 0, QTableWidgetItem(name))
        combo = QComboBox()
        for label, value in CALC_UNITS: combo.addItem(label, value)
        combo.setCurrentIndex(max(0, combo.findData(unit))); self.charge_table.setCellWidget(row, 1, combo)
        spin = QDoubleSpinBox(); spin.setDecimals(4); spin.setMaximum(99999999); spin.setGroupSeparatorShown(True); spin.setValue(float(amount or 0)); self.charge_table.setCellWidget(row, 2, spin)
        if not name: self.charge_table.setCurrentCell(row, 0); self.charge_table.editItem(self.charge_table.item(row, 0))

    def remove_charge_row(self):
        rows = sorted({index.row() for index in self.charge_table.selectedIndexes()}, reverse=True)
        if not rows: QMessageBox.information(self, "선택 확인", "삭제할 비용항목을 선택해 주세요."); return
        for row in rows: self.charge_table.removeRow(row)

    def on_selected(self):
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None: return
        item = self.table.item(row, 0).data(Qt.UserRole)
        if not isinstance(item, dict): return
        self.current_id = item["warehouse_id"]; self.code.setText(item["warehouse_code"]); self.name.setText(item["warehouse_name"])
        self._set_combo(self.warehouse_type, item["warehouse_type"]); self._set_combo(self.storage_type, item["storage_type"])
        for widget, key in ((self.biz_no,"biz_no"),(self.zip_code,"zip_code"),(self.address,"address"),(self.phone,"phone"),(self.fax,"fax"),(self.contact,"contact_name"),(self.meatwatch,"meatwatch_bplc_no"),(self.web_url,"web_url"),(self.web_user_id,"web_user_id")): widget.setText(item.get(key) or "")
        self.company_use.setChecked(item.get("company_use_yn", False)); self._set_date(self.valid_from, item.get("valid_from"), QDate.currentDate()); self._set_date(self.valid_to, item.get("valid_to"), self.valid_to.minimumDate())
        self.vat_yn.setChecked(item.get("vat_yn", True)); self.memo.setPlainText(item.get("memo") or ""); self.charge_table.setRowCount(0)
        charges = item.get("charges") or []
        if not charges and any(float(item.get(key, 0) or 0) for key in ("inbound_rate","outbound_rate","storage_rate","weighing_rate")):
            charges = [{"charge_name":name,"calc_unit":unit,"unit_rate":item.get(key,0)} for (name,unit),key in zip(DEFAULT_CHARGES,("inbound_rate","outbound_rate","storage_rate","weighing_rate")) if float(item.get(key,0) or 0) != 0]
        for charge in charges: self.add_charge_row(charge["charge_name"], charge["calc_unit"], charge["unit_rate"])

    def save_warehouse(self):
        if not self.name.text().strip(): QMessageBox.warning(self, "입력 확인", "창고명을 입력해 주세요."); self.name.setFocus(); return
        if self.valid_to.date() != self.valid_to.minimumDate() and self.valid_to.date() < self.valid_from.date(): QMessageBox.warning(self, "입력 확인", "적용 종료일은 시작일보다 빠를 수 없습니다."); return
        try: charges = self._charges_payload()
        except ValueError as exc: QMessageBox.warning(self, "입력 확인", str(exc)); return
        try:
            data = self._payload(charges); response = httpx.put(self._url(f"/{self.current_id}"), json=data, timeout=10) if self.current_id else httpx.post(self._url(), json=data, timeout=10)
            response.raise_for_status(); saved = response.json(); self.current_id = saved["warehouse_id"]; self.code.setText(saved["warehouse_code"])
            self.load_warehouses(); self._select_id(self.current_id); QMessageBox.information(self, "저장 완료", "창고 정보가 저장되었습니다.")
        except Exception as exc: QMessageBox.critical(self, "저장 오류", self._error_text(exc))

    def _charges_payload(self):
        result = []; names = set()
        for row in range(self.charge_table.rowCount()):
            name = (self.charge_table.item(row, 0).text() if self.charge_table.item(row, 0) else "").strip()
            if not name: raise ValueError(f"비용항목 {row + 1}행의 항목명을 입력해 주세요.")
            key = name.casefold()
            if key in names: raise ValueError(f"비용항목 '{name}'이 중복되었습니다.")
            names.add(key); combo = self.charge_table.cellWidget(row, 1); spin = self.charge_table.cellWidget(row, 2)
            result.append({"charge_name":name,"calc_unit":combo.currentData(),"unit_rate":spin.value(),"sort_order":row + 1,"use_yn":True})
        return result

    def deactivate_warehouse(self):
        if not self.current_id: QMessageBox.warning(self, "선택 확인", "사용중지할 창고를 선택해 주세요."); return
        if QMessageBox.question(self, "사용중지", "현재 업무회사에서 이 창고의 사용을 중지하시겠습니까?") != QMessageBox.Yes: return
        try: response = httpx.delete(self._url(f"/{self.current_id}"), timeout=10); response.raise_for_status(); self.new_warehouse(); self.load_warehouses()
        except Exception as exc: QMessageBox.critical(self, "처리 오류", self._error_text(exc))

    def _payload(self, charges):
        return {"warehouse_code":self.code.text(),"warehouse_name":self.name.text().strip(),"warehouse_type":self.warehouse_type.currentData(),"storage_type":self.storage_type.currentData(),
                "biz_no":self.biz_no.text().strip() or None,"zip_code":self.zip_code.text().strip() or None,"address":self.address.text().strip() or None,
                "phone":self.phone.text().strip() or None,"fax":self.fax.text().strip() or None,"contact_name":self.contact.text().strip() or None,
                "meatwatch_bplc_no":self.meatwatch.text().strip() or None,"web_url":self.web_url.text().strip() or None,"web_user_id":self.web_user_id.text().strip() or None,
                "memo":self.memo.toPlainText().strip() or None,"use_yn":True,"company_use_yn":self.company_use.isChecked(),
                "valid_from":self.valid_from.date().toString("yyyy-MM-dd"),"valid_to":None if self.valid_to.date()==self.valid_to.minimumDate() else self.valid_to.date().toString("yyyy-MM-dd"),
                "inbound_rate":0,"outbound_rate":0,"storage_rate":0,"weighing_rate":0,"vat_yn":self.vat_yn.isChecked(),"charges":charges}

    def _select_id(self, warehouse_id):
        for row, item in enumerate(self.rows):
            if item["warehouse_id"] == warehouse_id: self.table.selectRow(row); return

    @staticmethod
    def _set_combo(combo, value): combo.setCurrentIndex(max(0, combo.findData(value)))

    @staticmethod
    def _set_date(widget, value, fallback):
        parsed = QDate.fromString(value or "", "yyyy-MM-dd"); widget.setDate(parsed if parsed.isValid() else fallback)

    @staticmethod
    def _error_text(exc):
        if isinstance(exc, httpx.HTTPStatusError):
            try: return exc.response.json().get("detail", str(exc))
            except Exception: pass
        return str(exc)
