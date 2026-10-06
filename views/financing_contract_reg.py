"""Financing contract master: agree goods first, then assign ERP LOTs later."""

from datetime import date
from decimal import Decimal, InvalidOperation

import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


from views.lookup_dialog import LookupDialog


class SelectAllLineEdit(QLineEdit):
    """Replace an existing numeric value immediately when the field receives focus."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()


class FinancingContractWindow(QWidget):
    COLUMNS = ("계약번호", "계약일", "계약업체", "유형", "상품수", "LOT수", "상태")
    TYPES = (("수입대행", "IMPORT_AGENCY"), ("BL양수도", "BL_TRANSFER"), ("국내매입", "DOMESTIC_PURCHASE"))
    TEMPLATES = (("모두포함형", "ALL_IN"), ("중개수수료 제외형", "EXCLUDE_BROKERAGE"),
        ("중개수수료·창고료 제외형", "EXCLUDE_BROKERAGE_STORAGE"), ("이자형", "INTEREST_ONLY"),
        ("원가형", "COST_ONLY"), ("자유형", "FREE"))
    BASES = (("KG", "KG"), ("KG·일", "KG_DAY"), ("Box", "BOX"), ("건", "SHIPMENT"), ("정액", "FLAT"), ("%", "PERCENT"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.contracts, self.current, self.accounts, self.products, self.lots = [], None, [], [], []
        self.setWindowTitle("파이낸싱 계약관리")
        self.resize(1320, 900)
        self._build_ui()
        self._load_options()
        self.refresh()

    @property
    def base_url(self):
        return f"{API_BASE_URL}/companies/{app_context.company_code}/financing-contracts"

    def _get(self, path, **params):
        response = httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/{path}", params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _date():
        field = QDateEdit(QDate.currentDate())
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        field.setKeyboardTracking(False)
        field.setMinimumWidth(125)
        return field

    @staticmethod
    def _number(placeholder="0"):
        field = SelectAllLineEdit()
        field.setPlaceholderText(placeholder)
        field.setMinimumWidth(85)
        return field

    @staticmethod
    def _pair(left, right):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(left); layout.addWidget(right)
        return widget

    @staticmethod
    def _labelled(text, field):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text); label.setBuddy(field)
        layout.addWidget(label); layout.addWidget(field)
        return widget

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"업무회사: {app_context.company_code} {app_context.company_name or ''}"))
        self.table = QTableWidget(0, len(self.COLUMNS)); self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True); self.table.itemSelectionChanged.connect(self._select_row)
        root.addWidget(self.table, 2)

        form_panel = QWidget(); form = QFormLayout(form_panel)
        self.contract_no = QLineEdit(); self.contract_no.setReadOnly(True); self.contract_no.setPlaceholderText("저장 시 자동발번")
        self.contract_date = self._date()
        self.contract_type = QComboBox()
        for label, code in self.TYPES: self.contract_type.addItem(label, code)
        self.contractor = QComboBox(); self.memo = QLineEdit()
        self.deposit_required = QCheckBox("보증금 조건 있음")
        self.deposit_amount = self._number("없으면 비움")
        self.deposit_memo = QLineEdit(); self.deposit_memo.setPlaceholderText("보증금 조건 / 반환·재배정 참고")
        form.addRow("계약번호 (자동)", self.contract_no)
        form.addRow("계약일", self.contract_date)
        form.addRow("계약유형", self.contract_type)
        self.contractor_search = QPushButton("계약업체 검색")
        self.contractor_search.clicked.connect(lambda: self.lookup_account(self.contractor, "CONTRACT"))
        form.addRow("최초 계약업체 (1차 책임)", self._pair(self.contractor, self.contractor_search))
        form.addRow("보증금", self._pair(self.deposit_required, self.deposit_amount))
        form.addRow("보증금 비고", self.deposit_memo)
        form.addRow("계약 비고", self.memo)

        self.product_search = QPushButton("상품 검색")
        self.product_search.clicked.connect(self.lookup_product)
        self.product = QComboBox(); self.item_box = self._number("Box"); self.item_kg = self._number("Kg")
        self.item_price = self._number("계약단가 선택")
        self.item_memo = QLineEdit(); self.item_memo.setPlaceholderText("계약상품 특이사항")
        self.add_item_button = QPushButton("계약상품 추가")
        self.item_table = QTableWidget(0, 6)
        self.item_table.setHorizontalHeaderLabels(("상품", "계약 Box", "계약 Kg", "기준단가", "LOT 배정 Box/Kg", "비고"))
        self.item_table.setMaximumHeight(145)
        item_row = QWidget(); item_layout = QHBoxLayout(item_row); item_layout.setContentsMargins(0, 0, 0, 0)
        for text, field in (("계약상품", self.product), ("계약 Box", self.item_box), ("계약 Kg", self.item_kg),
                            ("기준단가 (원/Kg)", self.item_price), ("비고", self.item_memo)):
            item_layout.addWidget(self._labelled(text, field))
            if field is self.product: item_layout.addWidget(self.product_search, alignment=Qt.AlignBottom)
        item_layout.addWidget(self.add_item_button, alignment=Qt.AlignBottom)
        form.addRow("계약상품 입력", item_row); form.addRow("계약상품 목록", self.item_table)

        self.template = QComboBox()
        for label, code in self.TEMPLATES: self.template.addItem(label, code)
        self.interest_1 = self._number("연 이자율 %"); self.interest_days_1 = self._number("1차 적용 일수")
        self.interest_2 = self._number("연장 이자율 %"); self.interest_days_2 = self._number("2차 적용 일수")
        self.brokerage_1 = self._number("1차 수수료율 %"); self.brokerage_2 = self._number("2차 수수료율 %")
        self.brokerage_tax = QComboBox(); self.brokerage_tax.addItem("세무 선택", None)
        self.brokerage_tax.addItem("과세", "TAXABLE"); self.brokerage_tax.addItem("면세", "EXEMPT")
        self.brokerage_payer = QComboBox(); self.brokerage_payer.addItem("부담주체 선택", None)
        for label, code in (("최초 계약업체", "ORIGINAL_CONTRACTOR"), ("실제 출고업체", "ACTUAL_SHIPPER"), ("당사", "MXMN")):
            self.brokerage_payer.addItem(label, code)
        self.storage = self._number("KG·일 단가"); self.inout = self._number("KG 단가")
        self.weighing = self._number("Box 단가"); self.work = self._number("작업 단가"); self.inspection = self._number("검역 단가"); self.other = self._number("기타 단가")
        self.expense_fields = {}
        for name, field in (("storage", self.storage), ("inbound_outbound", self.inout), ("weighing", self.weighing),
                            ("work", self.work), ("inspection", self.inspection), ("other", self.other)):
            basis = QComboBox()
            for label, code in self.BASES: basis.addItem(label, code)
            default_basis = {"storage": "KG_DAY", "inbound_outbound": "KG", "weighing": "BOX"}.get(name)
            if default_basis: basis.setCurrentIndex(basis.findData(default_basis))
            tax = QComboBox(); tax.addItem("세무 선택", None); tax.addItem("과세", "TAXABLE"); tax.addItem("면세", "EXEMPT")
            payer = QComboBox()
            payer.addItem("부담주체 선택", None)
            for label, code in (("최초 계약업체", "ORIGINAL_CONTRACTOR"), ("실제 출고업체", "ACTUAL_SHIPPER"), ("당사", "MXMN")):
                payer.addItem(label, code)
            memo = QLineEdit(); memo.setPlaceholderText("비용 조건 비고")
            self.expense_fields[name] = (field, basis, tax, payer, memo)
        self.term_effective_from = self._date()
        self.cost_return_management_approved = QCheckBox("원가 반품 경영자 승인")
        self.cost_return_agreement_confirmed = QCheckBox("계약자 합의 확인")
        self.cost_return_approval_memo = QLineEdit(); self.cost_return_approval_memo.setPlaceholderText("이자형 사용 시 승인·합의 근거")
        form.addRow("출고가 회수 유형", self.template)
        form.addRow("이자 1차: 연율 / 적용 일수", self._pair(self.interest_1, self.interest_days_1))
        form.addRow("이자 2차: 연율 / 적용 일수", self._pair(self.interest_2, self.interest_days_2))
        form.addRow("중개수수료 1차 / 2차 / 세무 / 부담", self._row(self.brokerage_1, self.brokerage_2, self.brokerage_tax, self.brokerage_payer))
        for name, label in (("storage", "보관비"), ("inbound_outbound", "입출고비"), ("weighing", "계근비"),
                            ("work", "작업비"), ("inspection", "검역비"), ("other", "기타비용")):
            field, basis, tax, payer, memo = self.expense_fields[name]
            form.addRow(label, self._row(field, basis, tax, payer, memo))
        form.addRow("계약상 조건 적용 기준일", self.term_effective_from)
        form.addRow("이자형 국내매입 승인", self._pair(self.cost_return_management_approved, self.cost_return_agreement_confirmed))
        form.addRow("이자형 승인 메모", self.cost_return_approval_memo)

        self.shipper = QComboBox(); self.agreement_date = self._date(); self.agreement_confirmed = QCheckBox("서명된 특별출고약정 수취")
        self.shipper_search = QPushButton("출고업체 검색")
        self.shipper_search.clicked.connect(lambda: self.lookup_account(self.shipper, "SALE"))
        form.addRow("추가 출고업체", self._pair(self.shipper, self.shipper_search))
        form.addRow("특별약정 확인일", self._pair(self.agreement_date, self.agreement_confirmed))
        self.participant_table = QTableWidget(0, 4)
        self.participant_table.setHorizontalHeaderLabels(("거래처", "역할", "특별약정", "적용일"))
        self.participant_table.setMaximumHeight(100)
        form.addRow("계약 책임·출고업체", self.participant_table)

        self.lot = QComboBox(); self.lot_item = QComboBox(); self.lot_box = self._number("배정 Box"); self.lot_kg = self._number("배정 Kg")
        self.lot_date = self._date(); self.add_lot_button = QPushButton("실제 ERP LOT 배정")
        lot_row = QWidget(); lot_layout = QHBoxLayout(lot_row); lot_layout.setContentsMargins(0, 0, 0, 0)
        for text, field in (("배정할 계약상품", self.lot_item), ("실제 ERP LOT", self.lot),
                            ("LOT 배정 Box", self.lot_box), ("LOT 배정 Kg", self.lot_kg), ("연결일", self.lot_date)):
            lot_layout.addWidget(self._labelled(text, field))
        lot_layout.addWidget(self.add_lot_button, alignment=Qt.AlignBottom)
        form.addRow("입고 후 계약상품 ↔ ERP LOT", lot_row)
        self.lot_table = QTableWidget(0, 5)
        self.lot_table.setHorizontalHeaderLabels(("ERP LOT", "계약상품", "Box", "Kg", "연결일"))
        self.lot_table.setMaximumHeight(125)
        form.addRow("현재 계약 LOT 배정", self.lot_table)
        form_scroll = QScrollArea(); form_scroll.setWidgetResizable(True); form_scroll.setWidget(form_panel)
        root.addWidget(form_scroll, 4)

        buttons = QHBoxLayout()
        self.create_button = QPushButton("계약 초안 등록")
        self.update_button = QPushButton("선택 초안 수정")
        self.add_shipper_button = QPushButton("특별약정 출고업체 추가")
        self.add_term_button = QPushButton("조건 버전 추가")
        self.confirm_button = QPushButton("계약 확정")
        self.refresh_button = QPushButton("새로고침"); self.clear_button = QPushButton("신규 입력")
        for button in (self.create_button, self.update_button, self.add_shipper_button, self.add_term_button,
                       self.confirm_button, self.refresh_button, self.clear_button): buttons.addWidget(button)
        root.addLayout(buttons)
        self.message = QLabel("계약과 상품수량을 먼저 등록하고, 매입·통관·입고 후 생성된 ERP LOT를 연결합니다. 재고·매출·입금 원장은 기존 ERP를 사용합니다.")
        root.addWidget(self.message)
        self.create_button.clicked.connect(self.create_contract); self.update_button.clicked.connect(self.update_contract)
        self.refresh_button.clicked.connect(self.refresh); self.clear_button.clicked.connect(self.clear_form)
        self.add_shipper_button.clicked.connect(self.add_shipper); self.add_term_button.clicked.connect(self.add_term_version)
        self.add_item_button.clicked.connect(self.add_item_row); self.add_lot_button.clicked.connect(self.add_lot)
        self.confirm_button.clicked.connect(self.confirm_contract)

    @staticmethod
    def _triple(first, second, third):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        for field in (first, second, third): layout.addWidget(field)
        return widget

    @staticmethod
    def _row(*fields):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        for field in fields: layout.addWidget(field)
        return widget

    def _load_options(self):
        try:
            self.accounts = self._get("accounts", purpose="CONTRACT", limit=1, lookup_for="FINANCING_CONTRACT")
            products_response = httpx.get(f"{API_BASE_URL}/products", params={"limit": 1, "lookup_for": "FINANCING_CONTRACT"}, timeout=15)
            products_response.raise_for_status(); self.products = products_response.json()
            self.lots = self._get("lots")
            for account in self.accounts:
                label = f"{account.get('account_name')} ({account.get('account_code')})"
                self.contractor.addItem(label, account["account_id"])
            self.shipper.addItem("출고업체 검색 후 선택", None)
            for product in self.products:
                self.product.addItem(f"{product.get('product_code')} / {product.get('product_name')}", product["product_id"])
            self._refresh_lot_options()
        except Exception as exc:
            self.message.setText(f"거래처·상품·LOT 선택자료를 불러오지 못했습니다: {exc}")

    def _refresh_lot_options(self):
        selected = self.lot.currentData()
        self.lot.clear()
        for lot in self.lots:
            label = f"{lot.get('lot_code')} / {lot.get('product_name') or ''} / {lot.get('warehouse_name') or ''}"
            self.lot.addItem(label, lot["lot_id"])
        idx = self.lot.findData(selected)
        if idx >= 0: self.lot.setCurrentIndex(idx)

    def _items_payload(self):
        items = []
        for row in range(self.item_table.rowCount()):
            item_id = self.item_table.item(row, 0).data(Qt.UserRole)
            if item_id:
                continue
            product_id = self.item_table.item(row, 0).data(Qt.UserRole + 1)
            items.append({"product_id": product_id, "contract_box_qty": int(self.item_table.item(row, 1).text()),
                "contract_weight": self.item_table.item(row, 2).text(),
                "contract_unit_price": self.item_table.item(row, 3).text() or None,
                "memo": self.item_table.item(row, 5).text() or None})
        return items

    def add_item_row(self):
        if self.product.currentData() is None:
            QMessageBox.warning(self, "계약상품", "상품 Master를 먼저 선택하십시오."); return
        try:
            box_text, kg_text = self.item_box.text().strip(), self.item_kg.text().strip()
            box, kg = int(box_text or 0), Decimal(kg_text or 0)
            price = Decimal(self.item_price.text()) if self.item_price.text().strip() else None
            if box < 0 or kg < 0 or (box == 0 and kg == 0) or (price is not None and price < 0): raise ValueError
        except (ValueError, InvalidOperation):
            QMessageBox.warning(self, "계약상품", "Box, Kg, 단가를 확인하십시오. Box 또는 Kg 수량은 하나 이상 입력해야 합니다."); return
        row = self.item_table.rowCount(); self.item_table.insertRow(row)
        values = (self.product.currentText(), str(box), str(kg), str(price or ""), "0 / 0", self.item_memo.text().strip())
        for column, value in enumerate(values):
            cell = QTableWidgetItem(value)
            if column == 0: cell.setData(Qt.UserRole + 1, self.product.currentData())
            self.item_table.setItem(row, column, cell)
        self.item_table.resizeColumnsToContents()
        self.item_box.clear(); self.item_kg.clear(); self.item_price.clear(); self.item_memo.clear()

    def _term_payload(self):
        def decimal_value(field, label):
            value = field.text().strip()
            if not value: return None
            try:
                number = Decimal(value)
                if number < 0: raise InvalidOperation
                return number
            except (InvalidOperation, ValueError): raise ValueError(f"{label} 숫자를 확인하십시오.")
        def integer_value(field, label):
            value = field.text().strip()
            if not value: return None
            try:
                number = int(value)
                if number < 1: raise ValueError
                return number
            except ValueError: raise ValueError(f"{label}은 1 이상이어야 합니다.")
        r1 = decimal_value(self.interest_1, "1차 이자율"); d1 = integer_value(self.interest_days_1, "1차 적용일수")
        r2 = decimal_value(self.interest_2, "2차 이자율"); d2 = integer_value(self.interest_days_2, "2차 적용일수")
        if r2 is not None and (r1 is None or d1 is None): raise ValueError("2차 이자율을 쓰려면 1차 이자율과 1차 적용일수를 입력하십시오.")
        b1 = decimal_value(self.brokerage_1, "1차 중개수수료율"); b2 = decimal_value(self.brokerage_2, "2차 중개수수료율")
        expenses = []
        for code, (field, basis, tax, payer, memo) in self.expense_fields.items():
            rate = decimal_value(field, code)
            if rate is not None:
                if tax.currentData() is None or payer.currentData() is None:
                    raise ValueError(f"{code}의 세무구분과 부담주체를 선택하십시오.")
                expenses.append({"code": code.upper(), "basis": basis.currentData(), "unit_rate": str(rate),
                    "tax_treatment": tax.currentData(), "payer": payer.currentData(), "memo": memo.text().strip()})
        if b1 is not None or b2 is not None:
            if self.brokerage_tax.currentData() is None or self.brokerage_payer.currentData() is None:
                raise ValueError("중개수수료의 세무구분과 부담주체를 선택하십시오.")
            expenses.append({"code": "BROKERAGE", "basis": "PERCENT", "rate_1": str(b1) if b1 is not None else None,
                "rate_2": str(b2) if b2 is not None else None, "tax_treatment": self.brokerage_tax.currentData(),
                "payer": self.brokerage_payer.currentData(), "memo": ""})
        effective = self.term_effective_from.date().toString("yyyy-MM-dd")
        return {"effective_from": effective, "recovery_template": self.template.currentData(),
            "annual_interest_rate": str(r1 or 0), "interest_rate_1": str(r1) if r1 is not None else None,
            "interest_period_days_1": d1, "interest_rate_2": str(r2) if r2 is not None else None,
            "interest_period_days_2": d2, "brokerage_rate": str(b1 or 0),
            "brokerage_rate_1": str(b1) if b1 is not None else None, "brokerage_rate_2": str(b2) if b2 is not None else None,
            "storage_rate_per_kg_day": str(decimal_value(self.storage, "보관비") or 0),
            "inbound_outbound_rate_per_kg": str(decimal_value(self.inout, "입출고비") or 0),
            "weighing_rate_per_box": str(decimal_value(self.weighing, "계근비") or 0),
            "conditions": {"expense_conditions": expenses,
                "interest_tax_treatment": "EXEMPT",
                "cost_return_management_approved": self.cost_return_management_approved.isChecked(),
                "counterparty_agreement_confirmed": self.cost_return_agreement_confirmed.isChecked(),
                "management_approval_memo": self.cost_return_approval_memo.text().strip() or None}}

    def _base_payload(self):
        if self.contractor.currentData() is None: raise ValueError("최초 계약업체를 선택하십시오.")
        items = self._items_payload()
        if not self.current and not items: raise ValueError("계약상품과 계약수량을 하나 이상 추가하십시오.")
        terms = self._term_payload()
        return {"contract_type": self.contract_type.currentData(), "contract_date": self.contract_date.date().toString("yyyy-MM-dd"),
            "contractor_account_id": self.contractor.currentData(), "deposit_required": self.deposit_required.isChecked(),
            "deposit_amount": str(Decimal(self.deposit_amount.text().strip() or 0)),
            "deposit_memo": self.deposit_memo.text().strip() or None, "memo": self.memo.text().strip() or None,
            "items": items, "lots": [], "terms": [terms]}

    def refresh(self):
        try:
            response = httpx.get(self.base_url, timeout=15); response.raise_for_status(); self.contracts = response.json()
            self.table.setRowCount(len(self.contracts))
            for row_index, contract in enumerate(self.contracts):
                values = (contract["contract_no"], str(contract["contract_date"]), contract.get("contractor_name") or "",
                    contract["contract_type"], len(contract.get("items", [])), len(contract.get("lots", [])), contract["status"])
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value)); cell.setData(Qt.UserRole, contract["contract_id"])
                    self.table.setItem(row_index, col, cell)
            self.table.resizeColumnsToContents()
        except Exception as exc: self.message.setText(f"계약 조회 오류: {exc}")

    def _select_row(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.contracts): return
        row = self.contracts[index]; self.current = row
        self.contract_no.setText(row["contract_no"])
        self.contract_date.setDate(QDate.fromString(str(row["contract_date"]), "yyyy-MM-dd"))
        self.contract_type.setCurrentIndex(max(0, self.contract_type.findData(row["contract_type"])))
        if self.contractor.findData(row["contractor_account_id"]) < 0:
            self.contractor.addItem(row.get("contractor_name") or str(row["contractor_account_id"]), row["contractor_account_id"])
        self.contractor.setCurrentIndex(self.contractor.findData(row["contractor_account_id"]))
        self.deposit_required.setChecked(bool(row.get("deposit_required")))
        self.deposit_amount.setText(str(row.get("deposit_amount") or "")); self.deposit_memo.setText(row.get("deposit_memo") or "")
        self.memo.setText(row.get("memo") or "")
        self.item_table.setRowCount(0)
        for item in row.get("items", []):
            idx = self.item_table.rowCount(); self.item_table.insertRow(idx)
            vals = (f"{item.get('product_code')} / {item.get('product_name')}", str(item["contract_box_qty"]),
                str(item["contract_weight"]), str(item.get("contract_unit_price") or ""),
                f"{item.get('allocated_box_qty', 0)} / {item.get('allocated_weight', 0)}", item.get("memo") or "")
            for col, value in enumerate(vals):
                cell = QTableWidgetItem(value)
                if col == 0: cell.setData(Qt.UserRole, item["contract_item_id"])
                self.item_table.setItem(idx, col, cell)
        self.participant_table.setRowCount(0)
        for participant in row.get("participants", []):
            idx = self.participant_table.rowCount(); self.participant_table.insertRow(idx)
            role = "최초 계약업체 (1차 책임)" if participant["role"] == "ORIGINAL_CONTRACTOR" else "추가 출고업체"
            agreement = "특별약정 확인" if participant.get("agreement_status") == "CONFIRMED" else participant.get("agreement_status", "")
            values = (participant.get("account_name") or "", role, agreement, str(participant.get("effective_date") or ""))
            for col, value in enumerate(values): self.participant_table.setItem(idx, col, QTableWidgetItem(str(value)))
        self.lot_table.setRowCount(0)
        item_names = {item["contract_item_id"]: item.get("product_name") or "" for item in row.get("items", [])}
        for link in row.get("lots", []):
            idx = self.lot_table.rowCount(); self.lot_table.insertRow(idx)
            values = (link.get("lot_code") or "", item_names.get(link.get("contract_item_id"), ""),
                str(link.get("contract_box_qty", 0)), str(link.get("contract_weight", 0)), str(link.get("linked_date") or ""))
            for col, value in enumerate(values): self.lot_table.setItem(idx, col, QTableWidgetItem(value))
        if row.get("terms"):
            term = row["terms"][-1]; self.template.setCurrentIndex(max(0, self.template.findData(term["recovery_template"])))
            self.interest_1.setText(str(term.get("interest_rate_1") or term.get("annual_interest_rate") or ""))
            self.interest_days_1.setText(str(term.get("interest_period_days_1") or ""))
            self.interest_2.setText(str(term.get("interest_rate_2") or "")); self.interest_days_2.setText(str(term.get("interest_period_days_2") or ""))
            self.brokerage_1.setText(str(term.get("brokerage_rate_1") or term.get("brokerage_rate") or "")); self.brokerage_2.setText(str(term.get("brokerage_rate_2") or ""))
            brokerage_condition = next((x for x in term.get("conditions", {}).get("expense_conditions", []) if x.get("code") == "BROKERAGE"), {})
            self.brokerage_tax.setCurrentIndex(max(0, self.brokerage_tax.findData(brokerage_condition.get("tax_treatment"))))
            self.brokerage_payer.setCurrentIndex(max(0, self.brokerage_payer.findData(brokerage_condition.get("payer"))))
            self.term_effective_from.setDate(QDate.fromString(str(term["effective_from"]), "yyyy-MM-dd"))
            for name, fieldset in self.expense_fields.items():
                for field in (fieldset[0], fieldset[4]): field.clear()
                for combo in fieldset[1:4]: combo.setCurrentIndex(0)
            for expense in term.get("conditions", {}).get("expense_conditions", []):
                fieldset = self.expense_fields.get(str(expense.get("code", "")).lower())
                if not fieldset: continue
                field, basis, tax, payer, memo = fieldset
                field.setText(str(expense.get("unit_rate", "")))
                basis.setCurrentIndex(max(0, basis.findData(expense.get("basis"))))
                tax.setCurrentIndex(max(0, tax.findData(expense.get("tax_treatment"))))
                payer.setCurrentIndex(max(0, payer.findData(expense.get("payer"))))
                memo.setText(expense.get("memo") or "")
        self.lot_item.clear()
        for item in row.get("items", []):
            self.lot_item.addItem(f"{item.get('product_name')} / {item['contract_box_qty']} Box / {item['contract_weight']} Kg", item["contract_item_id"])
        self.message.setText(f"{row['contract_no']} / {row['status']} 선택. 계약상품은 계약 시 저장되고 ERP LOT는 입고 후 배정합니다.")

    def create_contract(self):
        try:
            payload = self._base_payload()
            response = httpx.post(self.base_url, json=payload, timeout=20); response.raise_for_status()
            created = response.json(); self.contract_no.setText(created["contract_no"])
            self.message.setText(f"계약 초안 {created['contract_no']}을 등록했습니다.")
            self.refresh(); self._select_created(created["contract_id"])
        except Exception as exc: QMessageBox.warning(self, "계약 등록", str(exc))

    def _select_created(self, contract_id):
        for i, row in enumerate(self.contracts):
            if row["contract_id"] == contract_id:
                self.table.selectRow(i); return

    def update_contract(self):
        if not self.current: QMessageBox.information(self, "계약 수정", "수정할 계약을 먼저 선택하십시오."); return
        try:
            payload = self._base_payload()
            contract_id = self.current["contract_id"]
            update_payload = {k: v for k, v in payload.items() if k not in {"items", "terms"}}
            for field in ("customs_date", "cost_finalized_date", "warehouse_arrival_date", "financing_start_date"):
                update_payload[field] = self.current.get(field)
            response = httpx.put(f"{self.base_url}/{contract_id}", json=update_payload, timeout=20)
            response.raise_for_status(); self.contract_no.setText(response.json()["contract_no"])
            unsaved_rows = [row for row in range(self.item_table.rowCount())
                if not self.item_table.item(row, 0).data(Qt.UserRole)]
            for row_index, item in zip(unsaved_rows, payload["items"]):
                add_response = httpx.post(f"{self.base_url}/{contract_id}/items", json=item, timeout=20)
                add_response.raise_for_status()
                self.item_table.item(row_index, 0).setData(Qt.UserRole, add_response.json()["contract_item_id"])
            self.refresh(); self._select_created(contract_id)
            self.message.setText("계약 초안을 수정했습니다.")
        except Exception as exc: QMessageBox.warning(self, "계약 수정", str(exc))

    def add_shipper(self):
        if not self.current or self.current.get("status") != "DRAFT":
            QMessageBox.information(self, "출고업체 추가", "계약 초안에서 출고업체를 추가하십시오."); return
        if not self.agreement_confirmed.isChecked():
            QMessageBox.warning(self, "특별출고약정", "서명된 특별출고약정을 수취한 뒤 확인을 선택하십시오."); return
        try:
            account_id = self.shipper.currentData()
            if account_id == self.current["contractor_account_id"]: raise ValueError("최초 계약업체는 별도 출고업체로 추가할 수 없습니다.")
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/participants", json={
                "account_id": account_id, "agreement_status": "CONFIRMED", "agreement_date": self.agreement_date.date().toString("yyyy-MM-dd")}, timeout=20)
            response.raise_for_status(); self.refresh(); self._select_created(self.current["contract_id"])
        except Exception as exc: QMessageBox.warning(self, "출고업체 추가", str(exc))

    def add_term_version(self):
        if not self.current or self.current.get("status") not in {"DRAFT", "CONFIRMED", "ACTIVE"}:
            QMessageBox.information(self, "조건 버전", "진행 가능한 계약을 선택하십시오."); return
        try:
            payload = self._term_payload(); payload["change_reason"] = "화면에서 조건 버전 추가"
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/terms", json=payload, timeout=20); response.raise_for_status()
            self.refresh(); self._select_created(self.current["contract_id"])
        except Exception as exc: QMessageBox.warning(self, "조건 버전", str(exc))

    def add_lot(self):
        if not self.current or self.current.get("status") not in {"DRAFT", "CONFIRMED", "ACTIVE"}:
            QMessageBox.information(self, "ERP LOT 배정", "진행 중인 계약에서 실제 ERP LOT가 생성되면 배정할 수 있습니다."); return
        try:
            box, kg = int(self.lot_box.text().strip() or 0), Decimal(self.lot_kg.text().strip() or 0)
            if box < 0 or kg < 0 or box == 0 and kg == 0: raise ValueError("배정 Box/Kg를 확인하십시오.")
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/lots", json={
                "contract_item_id": self.lot_item.currentData(), "lot_id": self.lot.currentData(),
                "contract_box_qty": box, "contract_weight": str(kg),
                "linked_date": self.lot_date.date().toString("yyyy-MM-dd")}, timeout=20)
            response.raise_for_status(); self.refresh(); self._select_created(self.current["contract_id"])
        except Exception as exc: QMessageBox.warning(self, "ERP LOT 배정", str(exc))

    def confirm_contract(self):
        if not self.current: QMessageBox.information(self, "계약 확정", "확정할 계약을 선택하십시오."); return
        try:
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/confirm", timeout=20)
            response.raise_for_status(); self.refresh(); self._select_created(self.current["contract_id"])
            self.message.setText("계약상품과 조건을 확정했습니다. 실제 ERP LOT는 입고 후 계속 배정할 수 있습니다.")
        except Exception as exc: QMessageBox.warning(self, "계약 확정", str(exc))

    def clear_form(self):
        self.current = None; self.contract_no.clear(); self.contract_date.setDate(QDate.currentDate())
        self.deposit_required.setChecked(False); self.deposit_amount.clear(); self.deposit_memo.clear(); self.memo.clear()
        self.item_table.setRowCount(0); self.lot_table.setRowCount(0); self.participant_table.setRowCount(0)
        self.interest_1.clear(); self.interest_days_1.clear(); self.interest_2.clear(); self.interest_days_2.clear()
        self.brokerage_1.clear(); self.brokerage_2.clear()
        self.brokerage_tax.setCurrentIndex(0); self.brokerage_payer.setCurrentIndex(0)
        for name, (field, basis, tax, payer, memo) in self.expense_fields.items():
            field.clear(); memo.clear(); tax.setCurrentIndex(0); payer.setCurrentIndex(0)
            basis_code = {"storage": "KG_DAY", "inbound_outbound": "KG", "weighing": "BOX"}.get(name)
            basis.setCurrentIndex(max(0, basis.findData(basis_code)) if basis_code else 0)
        self.term_effective_from.setDate(QDate.currentDate()); self.agreement_date.setDate(QDate.currentDate()); self.lot_date.setDate(QDate.currentDate())
        self.agreement_confirmed.setChecked(False); self.cost_return_management_approved.setChecked(False)
        self.cost_return_agreement_confirmed.setChecked(False); self.cost_return_approval_memo.clear()

    @staticmethod
    def _select_lookup(combo, value, pk, label):
        index = combo.findData(value[pk])
        if index < 0:
            combo.addItem(label, value[pk]); index = combo.count() - 1
        combo.setCurrentIndex(index)

    def lookup_account(self, combo, purpose):
        dialog = LookupDialog(self, '거래처 검색', '',
            [('코드', 'account_code'), ('거래처명', 'account_name'), ('사업자번호', 'biz_no')],
            lambda keyword: self._get('accounts', search=keyword, purpose=purpose, limit=50, lookup_for='FINANCING_CONTRACT'))
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            value = dialog.selected
            self._select_lookup(combo, value, 'account_id', f"{value['account_name']} ({value['account_code']})")

    def lookup_product(self):
        def fetch(keyword):
            response = httpx.get(f'{API_BASE_URL}/products', params={'search': keyword, 'limit': 50, 'lookup_for': 'FINANCING_CONTRACT'}, timeout=15)
            response.raise_for_status(); return response.json()
        dialog = LookupDialog(self, '계약상품 검색', '',
            [('코드', 'product_code'), ('상품명', 'product_name'), ('규격', 'specification')], fetch)
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            value = dialog.selected
            self._select_lookup(self.product, value, 'product_id', f"{value['product_code']} / {value['product_name']}")
