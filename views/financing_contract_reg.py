"""Minimal contract setup/list screen for the Financing Phase 1 API."""

from datetime import date
from decimal import Decimal, InvalidOperation

import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class FinancingContractWindow(QWidget):
    COLUMNS = ("계약번호", "계약일", "계약업체", "유형", "상태")
    TYPES = (("수입대행", "IMPORT_AGENCY"), ("BL양수도", "BL_TRANSFER"), ("국내매입", "DOMESTIC_PURCHASE"))
    TEMPLATES = (("모두포함형", "ALL_IN"), ("중개수수료 제외형", "EXCLUDE_BROKERAGE"),
        ("중개수수료·창고료 제외형", "EXCLUDE_BROKERAGE_STORAGE"), ("이자형", "INTEREST_ONLY"),
        ("원가형", "COST_ONLY"), ("자유형", "FREE"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.contracts = []
        self.current = None
        self.accounts = []
        self.lots = []
        self.setWindowTitle("파이낸싱 계약관리")
        self.resize(1180, 740)
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

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"업무회사: {app_context.company_code} {app_context.company_name or ''}"))
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._select_row)
        root.addWidget(self.table, 2)

        form = QFormLayout()
        self.contract_no = QLineEdit(); self.contract_no.setMaxLength(30)
        self.contract_date = QLineEdit(date.today().isoformat())
        self.contract_type = QComboBox()
        for label, code in self.TYPES: self.contract_type.addItem(label, code)
        self.contractor = QComboBox()
        self.shipper = QComboBox()
        self.lot = QComboBox()
        self.box_qty = QLineEdit("0"); self.weight = QLineEdit("0.00")
        self.template = QComboBox()
        for label, code in self.TEMPLATES: self.template.addItem(label, code)
        self.interest = QLineEdit("0"); self.storage = QLineEdit("0")
        self.brokerage = QLineEdit("0"); self.inout = QLineEdit("0"); self.weighing = QLineEdit("0")
        self.memo = QLineEdit()
        self.agreement_date = QLineEdit(date.today().isoformat())
        self.agreement_confirmed = QCheckBox("서명된 특별출고약정 수취 확인")
        self.cost_return_management_approved = QCheckBox("원가 반품 경영자 승인")
        self.cost_return_agreement_confirmed = QCheckBox("계약자 합의 확인")
        self.cost_return_approval_memo = QLineEdit()
        self.cost_return_approval_memo.setPlaceholderText("이자형 선택 시 승인·합의 근거")
        self.term_effective_from = QLineEdit(date.today().isoformat())
        form.addRow("계약번호", self.contract_no); form.addRow("계약일 (YYYY-MM-DD)", self.contract_date)
        form.addRow("계약유형", self.contract_type); form.addRow("최초 계약업체", self.contractor)
        form.addRow("기존 LOT", self.lot); form.addRow("계약수량 Box / Kg", self._pair(self.box_qty, self.weight))
        form.addRow("출고가 회수유형", self.template)
        form.addRow("연 이자율 (%) / KG·일 창고료", self._pair(self.interest, self.storage))
        form.addRow("중개수수료율 (%) / KG 입출고비 / Box 계근비", self._triple(self.brokerage, self.inout, self.weighing))
        form.addRow("비고", self.memo)
        form.addRow("추가 출고업체", self.shipper)
        form.addRow("특별약정 확인일", self._pair(self.agreement_date, self.agreement_confirmed))
        form.addRow("국내매입 이자형 승인", self._pair(self.cost_return_management_approved, self.cost_return_agreement_confirmed))
        form.addRow("이자형 승인 메모", self.cost_return_approval_memo)
        form.addRow("조건 적용 시작일", self.term_effective_from)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.create_button = QPushButton("초안 등록")
        self.update_button = QPushButton("선택 초안 수정")
        self.refresh_button = QPushButton("새로고침")
        self.clear_button = QPushButton("신규 입력")
        self.add_shipper_button = QPushButton("확정 계약업체 추가")
        self.add_lot_button = QPushButton("선택 LOT 추가")
        self.add_term_button = QPushButton("새 조건버전 추가")
        self.term_effective_from.setPlaceholderText("조건 적용일 YYYY-MM-DD")
        self.message = QLabel("Financing은 계약조건만 기록합니다. 매입·재고·매출·입금 원장은 기존 ERP를 사용합니다.")
        for button in (self.create_button, self.update_button, self.add_shipper_button,
            self.add_lot_button, self.add_term_button, self.refresh_button, self.clear_button): buttons.addWidget(button)
        root.addLayout(buttons); root.addWidget(self.message)
        self.create_button.clicked.connect(self.create_contract)
        self.update_button.clicked.connect(self.update_contract)
        self.refresh_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_form)
        self.add_shipper_button.clicked.connect(self.add_shipper)
        self.add_lot_button.clicked.connect(self.add_lot)
        self.add_term_button.clicked.connect(self.add_term_version)

    @staticmethod
    def _pair(left, right):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(left); layout.addWidget(right); return widget

    @staticmethod
    def _triple(one, two, three):
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0)
        for item in (one, two, three): layout.addWidget(item)
        return widget

    def _load_options(self):
        try:
            self.accounts = self._get("accounts")
            self.lots = self._get("lots")
            for account in self.accounts:
                self.contractor.addItem(f"{account.get('account_name')} ({account.get('account_code')})", account["account_id"])
                self.shipper.addItem(f"{account.get('account_name')} ({account.get('account_code')})", account["account_id"])
            for lot in self.lots:
                label = f"{lot.get('lot_code')} / {lot.get('product_name') or ''} / {lot.get('warehouse_name') or ''}"
                self.lot.addItem(label, lot["lot_id"])
        except Exception as exc:
            self.message.setText(f"거래처/LOT 선택자료를 불러오지 못했습니다: {exc}")

    def refresh(self):
        try:
            response = httpx.get(self.base_url, timeout=15); response.raise_for_status()
            self.contracts = response.json()
            self.table.setRowCount(len(self.contracts))
            for row_index, contract in enumerate(self.contracts):
                values = (contract["contract_no"], str(contract["contract_date"]), contract.get("contractor_name") or "",
                    contract["contract_type"], contract["status"])
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value)); cell.setData(Qt.UserRole, contract["contract_id"])
                    self.table.setItem(row_index, col, cell)
            self.table.resizeColumnsToContents()
        except Exception as exc:
            self.message.setText(f"계약 조회 오류: {exc}")

    def _payload(self):
        if self.contractor.currentData() is None or self.lot.currentData() is None:
            raise ValueError("계약업체와 기존 LOT를 선택하십시오.")
        try:
            box = int(self.box_qty.text() or "0")
            kg = Decimal(self.weight.text() or "0")
            rates = [Decimal(field.text() or "0") for field in (self.interest, self.storage, self.brokerage, self.inout, self.weighing)]
        except (ValueError, InvalidOperation):
            raise ValueError("수량과 계약조건은 숫자로 입력하십시오.")
        if box < 0 or kg < 0 or (box == 0 and kg == 0) or any(value < 0 for value in rates):
            raise ValueError("계약수량은 0보다 커야 하며 조건값은 음수일 수 없습니다.")
        try: contract_day = date.fromisoformat(self.contract_date.text())
        except ValueError: raise ValueError("계약일을 YYYY-MM-DD 형식으로 입력하십시오.")
        return {"contract_no": self.contract_no.text().strip(), "contract_type": self.contract_type.currentData(),
            "contract_date": contract_day.isoformat(), "contractor_account_id": self.contractor.currentData(),
            "memo": self.memo.text().strip() or None,
            "lots": [{"lot_id": self.lot.currentData(), "contract_box_qty": box, "contract_weight": str(kg),
                "linked_date": contract_day.isoformat()}],
            "terms": [{"effective_from": contract_day.isoformat(), "recovery_template": self.template.currentData(),
                "annual_interest_rate": str(rates[0]), "storage_rate_per_kg_day": str(rates[1]),
                "brokerage_rate": str(rates[2]), "inbound_outbound_rate_per_kg": str(rates[3]),
                "weighing_rate_per_box": str(rates[4]), "conditions": {
                    "cost_return_management_approved": self.cost_return_management_approved.isChecked(),
                    "counterparty_agreement_confirmed": self.cost_return_agreement_confirmed.isChecked(),
                    "management_approval_memo": self.cost_return_approval_memo.text().strip() or None}}]}

    def create_contract(self):
        try:
            payload = self._payload()
            if not payload["contract_no"]: raise ValueError("계약번호를 입력하십시오.")
            response = httpx.post(self.base_url, json=payload, timeout=20); response.raise_for_status()
            self.message.setText(f"초안 계약 {response.json()['contract_no']}을 등록했습니다.")
            self.refresh(); self.clear_form()
        except Exception as exc:
            QMessageBox.warning(self, "계약 등록", str(exc))

    def _select_row(self):
        row_index = self.table.currentRow()
        if row_index < 0 or row_index >= len(self.contracts): return
        row = self.contracts[row_index]; self.current = row
        self.contract_no.setText(row["contract_no"])
        self.contract_date.setText(str(row["contract_date"]))
        self.contract_type.setCurrentIndex(max(0, self.contract_type.findData(row["contract_type"])))
        self.contractor.setCurrentIndex(max(0, self.contractor.findData(row["contractor_account_id"])))
        self.memo.setText(row.get("memo") or "")
        if row.get("lots"):
            lot = row["lots"][0]; self.lot.setCurrentIndex(max(0, self.lot.findData(lot["lot_id"])))
            self.box_qty.setText(str(lot["contract_box_qty"])); self.weight.setText(str(lot["contract_weight"]))
        if row.get("terms"):
            term = row["terms"][-1]
            self.template.setCurrentIndex(max(0, self.template.findData(term["recovery_template"])))
            for widget, key in ((self.interest, "annual_interest_rate"), (self.storage, "storage_rate_per_kg_day"),
                (self.brokerage, "brokerage_rate"), (self.inout, "inbound_outbound_rate_per_kg"), (self.weighing, "weighing_rate_per_box")):
                widget.setText(str(term[key]))
        self.message.setText(f"{row['contract_no']} / {row['status']} 선택. 확정 후 계약 기본정보·LOT는 수정할 수 없습니다.")

    def update_contract(self):
        if not self.current:
            QMessageBox.information(self, "계약 수정", "수정할 계약을 먼저 선택하십시오."); return
        try:
            payload = self._payload()
            # Phase 1 editable fields are the contract header. Existing LOT/terms are immutable snapshots;
            # edits are not allowed to replace their original links through this header endpoint.
            response = httpx.put(f"{self.base_url}/{self.current['contract_id']}", json={
                "contract_type": payload["contract_type"], "contract_date": payload["contract_date"],
                "contractor_account_id": payload["contractor_account_id"], "customs_date": self.current.get("customs_date"),
                "cost_finalized_date": self.current.get("cost_finalized_date"),
                "warehouse_arrival_date": self.current.get("warehouse_arrival_date"),
                "financing_start_date": self.current.get("financing_start_date"),
                "deposit_required": self.current.get("deposit_required", False), "deposit_amount": str(self.current.get("deposit_amount") or 0),
                "deposit_memo": self.current.get("deposit_memo"), "memo": self.memo.text().strip() or None}, timeout=20)
            response.raise_for_status(); self.message.setText("계약 초안을 수정했습니다."); self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "계약 수정", str(exc))

    def add_shipper(self):
        if not self.current or self.current.get("status") != "DRAFT":
            QMessageBox.information(self, "출고업체 추가", "출고업체는 계약 초안에서만 추가할 수 있습니다."); return
        if not self.agreement_confirmed.isChecked():
            QMessageBox.warning(self, "특별출고약정", "서명된 특별출고약정을 먼저 수취하고 확인란을 선택하십시오."); return
        try:
            agreement_date = date.fromisoformat(self.agreement_date.text()).isoformat()
            account_id = self.shipper.currentData()
            if account_id == self.current["contractor_account_id"]:
                raise ValueError("최초 계약업체는 추가 출고업체로 다시 등록할 수 없습니다.")
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/participants", json={
                "account_id": account_id, "agreement_status": "CONFIRMED", "agreement_date": agreement_date,
                "effective_date": agreement_date}, timeout=20)
            response.raise_for_status(); self.message.setText("특별출고약정 확인업체를 계약에 추가했습니다."); self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "출고업체 추가", str(exc))

    def add_lot(self):
        if not self.current or self.current.get("status") != "DRAFT":
            QMessageBox.information(self, "계약 LOT 추가", "LOT는 계약 초안에서만 연결할 수 있습니다."); return
        try:
            box = int(self.box_qty.text() or "0"); kg = Decimal(self.weight.text() or "0")
            linked_date = date.fromisoformat(self.contract_date.text()).isoformat()
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/lots", json={
                "lot_id": self.lot.currentData(), "contract_box_qty": box,
                "contract_weight": str(kg), "linked_date": linked_date}, timeout=20)
            response.raise_for_status(); self.message.setText("기존 LOT를 계약에 연결했습니다."); self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "계약 LOT 추가", str(exc))

    def add_term_version(self):
        if not self.current or self.current.get("status") not in {"DRAFT", "CONFIRMED", "ACTIVE"}:
            QMessageBox.information(self, "계약조건 변경", "진행 가능한 계약을 먼저 선택하십시오."); return
        try:
            effective_from = date.fromisoformat(self.term_effective_from.text()).isoformat()
            rates = [Decimal(field.text() or "0") for field in (self.interest, self.storage, self.brokerage, self.inout, self.weighing)]
            response = httpx.post(f"{self.base_url}/{self.current['contract_id']}/terms", json={
                "effective_from": effective_from, "recovery_template": self.template.currentData(),
                "annual_interest_rate": str(rates[0]), "storage_rate_per_kg_day": str(rates[1]),
                "brokerage_rate": str(rates[2]), "inbound_outbound_rate_per_kg": str(rates[3]),
                "weighing_rate_per_box": str(rates[4]), "conditions": {
                    "cost_return_management_approved": self.cost_return_management_approved.isChecked(),
                    "counterparty_agreement_confirmed": self.cost_return_agreement_confirmed.isChecked(),
                    "management_approval_memo": self.cost_return_approval_memo.text().strip() or None},
                "change_reason": "화면에서 조건버전 추가"}, timeout=20)
            response.raise_for_status(); self.message.setText(f"계약조건 version {response.json()['version']}을 추가했습니다."); self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "계약조건 변경", str(exc))

    def clear_form(self):
        self.current = None; self.contract_no.clear(); self.contract_date.setText(date.today().isoformat())
        self.memo.clear(); self.box_qty.setText("0"); self.weight.setText("0.00")
        self.agreement_date.setText(date.today().isoformat()); self.agreement_confirmed.setChecked(False)
        self.cost_return_management_approved.setChecked(False)
        self.cost_return_agreement_confirmed.setChecked(False); self.cost_return_approval_memo.clear()
        self.term_effective_from.setText(date.today().isoformat())
