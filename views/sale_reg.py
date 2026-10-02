"""상품매입 화면과 대칭인 일반매출 입력·조회 화면."""
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget)
from views.purchase_reg import LookupDialog, PurchaseRegWindow, _number, _won

COLUMNS = ['LOT *', '상품', '창고', '가용 BOX', '가용 KG', '출고 BOX *',
           '출고 중량(KG) *', '개별원가', '판매단가 *', '매출금액', '매출이익', '이익률(%)', '출고 후 BOX', '출고 후 KG', '메모']


class SaleRegWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_id = None
        self.lots, self.accounts, self.saved, self.line_extras = [], [], [], []
        self.original = {}
        self.customer = None
        self.loading = False
        self._build_ui()
        self.load_options()
        self.query_sales()
        self.new_sale()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel('상품매출등록/수정')
        title.setStyleSheet('font-size:20px;font-weight:700;')
        root.addWidget(title)
        root.addWidget(QLabel('저장하면 매출전표·출고·재고·미수 원거래가 한 번에 반영됩니다.'))
        top = QHBoxLayout()
        left = QGroupBox('매출일자별 전표'); ll = QVBoxLayout(left)
        dl = QHBoxLayout(); dl.addWidget(QLabel('매출일자'))
        self.date = QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True)
        self.date.setDisplayFormat('yyyy-MM-dd'); dl.addWidget(self.date); dl.addStretch(); ll.addLayout(dl)
        self.today_table = QTableWidget(0, 4)
        self.today_table.setHorizontalHeaderLabels(['순번', '거래처', '거래처명', '금액'])
        self.today_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.today_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.today_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.today_table.setMaximumHeight(175); ll.addWidget(self.today_table); top.addWidget(left, 2)
        right = QGroupBox('전표 입력 / 조회'); form = QFormLayout(right)
        self.document_no, self.status = QLabel('신규'), QLabel('신규입력')
        customer_line = QHBoxLayout(); self.customer_edit = QLineEdit()
        self.customer_edit.setPlaceholderText('거래처 코드·상호 입력 후 Enter')
        self.customer_button = QPushButton('거래처 조회')
        customer_line.addWidget(self.customer_edit, 1); customer_line.addWidget(self.customer_button)
        form.addRow('전표번호', self.document_no); form.addRow('상태', self.status)
        form.addRow('매출처 *', customer_line)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(55); self.memo.setPlaceholderText('전표 메모')
        form.addRow('메모', self.memo)
        contacts = QHBoxLayout()
        self.phone, self.fax, self.email = QLabel('—'), QLabel('—'), QLabel('—')
        for caption, label in (('전화', self.phone), ('FAX', self.fax), ('이메일', self.email)):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse); contacts.addWidget(QLabel(caption)); contacts.addWidget(label, 1)
        self.email.setToolTip('거래처 Master의 전자(세금)계산서 이메일 · 조회용')
        form.addRow('연락정보', contacts); top.addWidget(right, 3); root.addLayout(top)
        buttons = QHBoxLayout()
        self.btn_query, self.btn_new = QPushButton('조회 [F7]'), QPushButton('신규 [F2]')
        self.btn_add, self.btn_remove = QPushButton('행 추가'), QPushButton('행 삭제')
        self.btn_save, self.btn_reset = QPushButton('저장 [F4]'), QPushButton('입력취소 [F5]')
        self.btn_cancel = QPushButton('전표취소'); self.btn_cancel.setEnabled(False)
        for button in (self.btn_query, self.btn_new, self.btn_add, self.btn_remove,
                       self.btn_save, self.btn_reset, self.btn_cancel): buttons.addWidget(button)
        buttons.addStretch(); root.addLayout(buttons)
        self.table = QTableWidget(0, len(COLUMNS)); self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems); self.table.setAlternatingRowColors(True)
        for col, width in enumerate((170, 220, 135, 75, 90, 75, 110, 85, 85, 100, 100, 80, 95, 95, 120)):
            self.table.setColumnWidth(col, width)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(14, QHeaderView.Stretch)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root.addWidget(self.table, 1)
        totals = QHBoxLayout(); totals.addStretch(); self.total_label = QLabel()
        self.total_label.setStyleSheet('font-size:16px;font-weight:700;')
        totals.addWidget(self.total_label); root.addLayout(totals)
        self.warning = QLabel(); self.warning.setWordWrap(True)
        self.warning.setStyleSheet('color:#c62828;font-weight:700;'); root.addWidget(self.warning)
        self.exception_panel = QWidget(); exception_line = QHBoxLayout(self.exception_panel)
        exception_line.setContentsMargins(0, 0, 0, 0); exception_line.addWidget(QLabel('예외출고 사유 *'))
        self.reason = QLineEdit(); self.reason.setMaxLength(1000)
        self.reason.setPlaceholderText('마이너스 재고 출고 사유 입력'); exception_line.addWidget(self.reason, 1)
        root.addWidget(self.exception_panel); self.exception_panel.hide(); self.warning.hide()
        receivable = QGroupBox('매출처 미수 현황'); rl = QHBoxLayout(receivable)
        self.previous_receivable, self.current_sales = QLabel(), QLabel()
        self.today_receipt, self.current_receivable = QLabel(), QLabel()
        for label in (self.previous_receivable, self.current_sales, self.today_receipt, self.current_receivable):
            label.setStyleSheet('font-size:14px;font-weight:700;padding:4px 12px;'); rl.addWidget(label)
        rl.addStretch(); root.addWidget(receivable)
        self.date.dateChanged.connect(self._date_changed)
        self.today_table.itemSelectionChanged.connect(self.open_sale)
        self.customer_button.clicked.connect(self.lookup_customer)
        self.customer_edit.returnPressed.connect(self.lookup_customer)
        self.customer_edit.textEdited.connect(self.clear_customer)
        for button, callback in ((self.btn_query, self.load_all), (self.btn_new, self.new_sale),
                                 (self.btn_add, self.add_row), (self.btn_remove, self.remove_row),
                                 (self.btn_save, self.save), (self.btn_reset, self.reset_input),
                                 (self.btn_cancel, self.cancel)):
            button.clicked.connect(callback)
        for key, callback in (('F7', self.load_all), ('F2', self.new_sale), ('F4', self.save), ('F5', self.reset_input)):
            shortcut = QShortcut(QKeySequence(key), self); shortcut.activated.connect(callback)

    def _get(self, path, **params):
        r = httpx.get(f'{API_BASE_URL}/companies/{app_context.company_code}/{path}', params=params, timeout=15)
        r.raise_for_status(); return r.json()

    def load_options(self):
        try:
            self.accounts = self._get('accounts'); self.refresh_inventory()
        except Exception as exc: QMessageBox.warning(self, '기준자료 조회 오류', PurchaseRegWindow._error_text(exc))

    def lookup_customer(self):
        try: self.accounts = self._get('accounts')
        except Exception as exc:
            QMessageBox.warning(self, '거래처 조회 오류', PurchaseRegWindow._error_text(exc)); return
        def fetch(keyword):
            return [x for x in self.accounts if x.get('sales_yn') and x.get('use_yn', True)
                    and not x.get('trade_stop_yn', False)
                    and keyword.casefold() in f"{x.get('account_code', '')} {x.get('account_name', '')}".casefold()]
        dialog = LookupDialog(self, '매출처 조회', self.customer_edit.text(),
                              [('거래처코드', 'account_code'), ('거래처명', 'account_name')], fetch)
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            self.set_customer(dialog.selected); self.refresh_summary()
            if not self.table.rowCount(): self.add_row()
            self.table.cellWidget(0, 0).setFocus()

    def set_customer(self, value):
        self.customer = value
        self.customer_edit.setText(f"{value.get('account_name') or ''} ({value.get('account_code') or ''})")
        for label in (self.phone, self.fax, self.email): label.setText('—')
        try:
            info = self._get_account(value['account_id'])
            for label, key in ((self.phone, 'phone'), (self.fax, 'fax'), (self.email, 'tax_email')):
                label.setText(info.get(key) or '—')
        except Exception as exc:
            for label in (self.phone, self.fax, self.email): label.setText('조회 실패'); label.setToolTip(PurchaseRegWindow._error_text(exc))

    def _get_account(self, account_id):
        response = httpx.get(f'{API_BASE_URL}/accounts/{account_id}', timeout=15)
        response.raise_for_status(); return response.json()

    def clear_customer(self, *_):
        self.customer = None
        for label in (self.phone, self.fax, self.email): label.setText('—')
        self.refresh_summary()

    def lookup_lot(self, editor):
        row = self._editor_row(editor)
        if row < 0: return
        try: self.refresh_inventory()
        except Exception as exc:
            QMessageBox.warning(self, 'LOT 조회 오류', PurchaseRegWindow._error_text(exc)); return
        def fetch(keyword):
            result = []
            for value in self.lots:
                if not value.get('use_yn', True) and value['lot_id'] not in self.original: continue
                if keyword.casefold() not in ' '.join(str(value.get(k) or '') for k in ('lot_code', 'product_name', 'warehouse_name', 'history_no', 'bl_no')).casefold(): continue
                result.append({**value, 'box_display':f"{value['available_box_qty']:,}",
                               'kg_display':f"{Decimal(str(value['available_weight'])):,.2f}"})
            return result
        dialog = LookupDialog(self, 'LOT 조회', editor.text(), [('LOT', 'lot_code'), ('상품', 'product_name'),
                              ('창고', 'warehouse_name'), ('가용 BOX', 'box_display'), ('가용 KG', 'kg_display'), ('개별원가', 'individual_cost')], fetch)
        if dialog.exec() == QDialog.Accepted and dialog.selected:
            self.select_lot(row, dialog.selected); self._focus_cell(row, 5)

    def _editor_row(self, editor):
        return next((r for r in range(self.table.rowCount()) if self.table.cellWidget(r, 0) is editor), -1)

    def select_lot(self, row, lot):
        editor = self.table.cellWidget(row, 0); editor.setProperty('selected', lot); editor.setText(lot['lot_code'])
        self.fill_lot(row)

    def fill_lot(self, row):
        lot = self.table.cellWidget(row, 0).property('selected') or {}
        self.table.item(row, 1).setText(lot.get('product_name', ''))
        self.table.item(row, 2).setText(lot.get('warehouse_name', ''))
        self.recalculate()

    def add_row(self, value=None):
        value = value if isinstance(value, dict) else {}
        was_loading = self.loading; self.loading = True
        row = self.table.rowCount(); self.table.insertRow(row)
        editor = QLineEdit(); editor.setPlaceholderText('LOT·상품명 입력 후 Enter')
        editor.returnPressed.connect(lambda e=editor: self.lookup_lot(e))
        editor.textEdited.connect(lambda _, e=editor: self._clear_lot(e)); self.table.setCellWidget(row, 0, editor)
        for col in (1, 2, 3, 4, 7, 9, 10, 11, 12, 13):
            item = QTableWidgetItem(''); item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, col, item)
        for col, key, default in ((5, 'box_qty', ''), (6, 'weight', '0.00'), (8, 'unit_price', ''), (14, 'memo', '')):
            field = QLineEdit(str(value.get(key) or default)); self.table.setCellWidget(row, col, field)
            field.textChanged.connect(self.recalculate)
        self.line_extras.append({'discount_amount': value.get('discount_amount', 0),
                                 'tax_rate': Decimal('0.10') if value.get('tax_amount', 0) else Decimal(0)})
        if value.get('lot_id'):
            lot = next((x for x in self.lots if x['lot_id'] == value['lot_id']), None)
            if lot is None: raise ValueError('전표 LOT를 조회할 수 없습니다.')
            editor.setProperty('selected', lot); editor.setText(lot['lot_code'])
            self.table.item(row, 1).setText(lot['product_name']); self.table.item(row, 2).setText(lot['warehouse_name'])
        self._wire_enter(editor); self.loading = was_loading; self.recalculate()

    def _clear_lot(self, editor):
        editor.setProperty('selected', None)
        row = self._editor_row(editor)
        if row >= 0: self.fill_lot(row)

    def _wire_enter(self, lot_editor):
        row = self._editor_row(lot_editor)
        for index, col in enumerate((5, 6, 8, 14)):
            def advance(i=index, editor=lot_editor):
                r = self._editor_row(editor)
                if r < 0: return
                self._format_row(r)
                if i < 3: self._focus_cell(r, (5, 6, 8, 14)[i+1])
                else:
                    if r == self.table.rowCount()-1: self.add_row()
                    self._focus_cell(r+1, 0)
            self.table.cellWidget(row, col).returnPressed.connect(advance)

    def _focus_cell(self, row, col):
        editor = self.table.cellWidget(row, col)
        if editor: editor.setFocus(); editor.selectAll()

    def _format_row(self, row):
        try:
            for col in (5, 8): self.table.cellWidget(row, col).setText(f"{int(self._text(row, col) or 0):,}")
            self.table.cellWidget(row, 6).setText(f"{Decimal(self._text(row, 6) or 0):,.2f}")
        except Exception: pass

    def _text(self, row, col):
        return _number(self.table.cellWidget(row, col).text())

    def payload(self):
        items = []
        for row in range(self.table.rowCount()):
            lot_editor = self.table.cellWidget(row, 0); lot = lot_editor.property('selected')
            if not lot and not lot_editor.text().strip() and not any(self._text(row, c) for c in (5, 8, 14)) and Decimal(self._text(row, 6) or 0) == 0: continue
            if not lot: raise ValueError(f'{row+1}행 LOT를 조회하여 선택하세요.')
            box = int(self._text(row, 5)); weight = Decimal(self._text(row, 6)); price = int(self._text(row, 8))
            if box < 0 or not weight.is_finite() or weight <= 0 or weight.as_tuple().exponent < -2 or price < 0:
                raise ValueError(f'{row+1}행 BOX 정수·KG 소수점 2자리·단가 원 단위를 확인하세요.')
            items.append({'discount_amount':self.line_extras[row]['discount_amount'], 'memo':self.table.cellWidget(row, 14).text().strip() or None,
                          'line_no':len(items)+1, 'product_id':lot['product_id'], 'lot_id':lot['lot_id'],
                          'box_qty':box, 'weight':str(weight), 'unit_price':price})
        if not items or not self.customer: raise ValueError('매출처와 출고 행을 입력하세요.')
        if self.recalculate() and not self.reason.text().strip(): raise ValueError('마이너스 재고 출고 사유를 입력하세요.')
        return {'memo':self.memo.toPlainText().strip() or None, 'inventory_exception_reason':self.reason.text().strip() or None,
                'sale_date':self.date.date().toString('yyyy-MM-dd'), 'account_id':self.customer['account_id'], 'items':items}

    def save(self):
        if not self.btn_save.isEnabled(): return
        try:
            self.refresh_inventory(); data = self.payload()
            if QMessageBox.question(self, '상품매출 저장', '입력한 상품매출을 저장하시겠습니까?\n저장과 동시에 출고와 재고가 반영됩니다.') != QMessageBox.Yes: return
            base = f'{API_BASE_URL}/companies/{app_context.company_code}/sales'
            r = httpx.put(f'{base}/{self.sale_id}', json=data, timeout=30) if self.sale_id else httpx.post(base, json=data, timeout=30)
            r.raise_for_status(); saved = r.json(); self.load_sale(saved); self.query_sales()
            QMessageBox.information(self, '저장 완료', f"{saved['sale_no']} 확정 저장되었습니다.")
        except Exception as exc: QMessageBox.warning(self, '저장 오류', PurchaseRegWindow._error_text(exc))

    def cancel(self):
        if not self.sale_id or not self.btn_cancel.isEnabled(): return
        if QMessageBox.question(self, '전표 취소', '출고·재고·미수 원거래를 함께 회수하고 취소하시겠습니까?') != QMessageBox.Yes: return
        reason, ok = QInputDialog.getText(self, '전표 취소', '취소 사유를 입력하세요 (최대 1,000자).')
        if not ok: return
        reason = reason.strip()
        if not reason or len(reason) > 1000:
            QMessageBox.warning(self, '취소 사유', '취소 사유를 1~1,000자로 입력하세요.'); return
        try:
            httpx.post(f'{API_BASE_URL}/companies/{app_context.company_code}/sales/{self.sale_id}/cancel', json={'reason':reason}, timeout=20).raise_for_status()
            self.new_sale(keep_date=True); self.query_sales()
            QMessageBox.information(self, '완료', '취소되었습니다.')
        except Exception as exc: QMessageBox.warning(self, '취소 오류', PurchaseRegWindow._error_text(exc))

    def refresh_inventory(self):
        params = {'editing_sale_id':self.sale_id} if self.sale_id else {}
        self.lots = self._get('sales/lot-availability', **params); self.recalculate()

    def refresh_summary(self, *_):
        if self.loading: return
        if not self.customer:
            for label, text in ((self.previous_receivable, '전미수금'), (self.current_sales, '현매출액'),
                                (self.today_receipt, '당일수금액'), (self.current_receivable, '현미수금')): label.setText(f'{text} 0')
            return
        try:
            value = self._get('sales-receivable-summary', account_id=self.customer['account_id'], transaction_date=self.date.date().toString('yyyy-MM-dd'))
            for label, key, text in ((self.previous_receivable, 'previous_receivable', '전미수금'),
                                     (self.current_sales, 'today_sales', '현매출액'),
                                     (self.today_receipt, 'today_receipt', '당일수금액'),
                                     (self.current_receivable, 'current_receivable', '현미수금')): label.setText(f'{text} {value[key]:,}')
        except Exception as exc:
            for label in (self.previous_receivable, self.current_sales, self.today_receipt, self.current_receivable): label.setText('조회 실패')
            self.current_receivable.setToolTip(PurchaseRegWindow._error_text(exc))

    @staticmethod
    def profit_values(weight, price, cost):
        revenue = _won(weight * price)
        expense = _won(weight * cost)
        profit = revenue - expense
        margin = (Decimal(profit) / revenue * 100).quantize(Decimal('0.01')) if revenue else None
        return revenue, expense, profit, margin

    def recalculate(self, *_):
        if self.loading: return False
        totals = defaultdict(lambda: [0, Decimal(0)]); invalid = False
        boxes = 0; weight = Decimal(0); revenue_total = 0; cost_total = 0; missing_cost = False
        current = {x['lot_id']:x for x in self.lots}
        for row in range(self.table.rowCount()):
            selected = self.table.cellWidget(row, 0).property('selected')
            lot = current.get(selected['lot_id']) if selected else None
            loss = False
            try:
                box = int(self._text(row, 5) or 0); kg = Decimal(self._text(row, 6) or 0); price = int(self._text(row, 8) or 0)
                if not kg.is_finite(): raise ValueError()
                revenue = _won(kg * price); boxes += box; weight += kg; revenue_total += revenue
                self.table.item(row, 9).setText(f'{revenue:,}')
                if lot:
                    totals[lot['lot_id']][0] += box; totals[lot['lot_id']][1] += kg
                raw_cost = lot.get('individual_cost') if lot else None
                if raw_cost is None:
                    for col in (7, 10, 11): self.table.item(row, col).setText('미확인' if lot else '')
                    if lot: missing_cost = True
                else:
                    cost = _won(raw_cost)
                    revenue, expense, profit, margin = self.profit_values(kg, price, cost)
                    cost_total += expense; loss = profit < 0
                    for col, text in ((7, f'{cost:,}'), (10, f'{profit:,}'), (11, f'{margin:.2f}%' if margin is not None else '—')):
                        self.table.item(row, col).setText(text)
                    self.table.item(row, 7).setToolTip('LOT Master 개별원가 (원/KG)')
            except Exception:
                invalid = True
                for col in (9, 10, 11): self.table.item(row, col).setText('입력 확인')
            for col in (10, 11):
                self.table.item(row, col).setData(Qt.ForegroundRole, QColor('#b71c1c') if loss else None)
                self.table.item(row, col).setData(Qt.BackgroundRole, QColor('#fff3e0') if loss else None)
                self.table.item(row, col).setToolTip('손실거래' if loss else '')
        negative = []
        for row in range(self.table.rowCount()):
            selected = self.table.cellWidget(row, 0).property('selected')
            lot = current.get(selected['lot_id']) if selected else None
            is_negative = False
            if lot:
                box = lot['available_box_qty']; kg = Decimal(str(lot['available_weight'])); issued = totals[lot['lot_id']]
                after_box = box + lot['editing_box_qty'] - issued[0]
                after_kg = kg + Decimal(str(lot['editing_weight'])) - issued[1]
                for col, text in ((3, f'{box:,}'), (4, f'{kg:,.2f}'), (12, f'{after_box:,}'), (13, f'{after_kg:,.2f}')):
                    self.table.item(row, col).setText(text)
                is_negative = after_box < 0 or after_kg < 0
                if is_negative: negative.append(lot['lot_code'])
            else:
                for col in (3, 4, 12, 13): self.table.item(row, col).setText('')
            for col in (1, 2, 3, 4, 12, 13):
                item = self.table.item(row, col)
                item.setData(Qt.BackgroundRole, QColor('#ffebee') if is_negative else None)
                item.setData(Qt.ForegroundRole, QColor('#b71c1c') if is_negative and col in (12, 13) else None)
        cost_text = '미확인' if missing_cost else f'{cost_total:,}'
        profit_text = '미확인' if missing_cost else f'{revenue_total-cost_total:,}'
        self.total_label.setText(f'합계  BOX {boxes:,} / 중량 {weight:,.2f} KG / 매출액 {revenue_total:,} / 매출원가 {cost_text} / 매출이익 {profit_text}')
        self.total_label.setStyleSheet('font-size:16px;font-weight:700;' + ('color:#b71c1c;' if not missing_cost and revenue_total < cost_total else ''))
        message = ('마이너스 재고: '+', '.join(sorted(set(negative)))+' — 예외출고 사유 필수.' if negative else '')
        if invalid: message += ' BOX/KG/단가 입력을 확인하세요.'
        self.warning.setText(message); self.warning.setVisible(bool(message))
        self.exception_panel.setVisible(bool(negative) or bool(self.reason.text().strip()))
        self.reason.setEnabled(bool(negative) or bool(self.reason.text().strip()))
        self.table.setToolTip('수정 예상재고 = 현재 가용 + 기존 전표 출고 − 동일 LOT 입력량 합계' if self.sale_id else '예상재고 = 현재 가용 − 동일 LOT 입력량 합계')
        return bool(negative)

    def load_all(self):
        self.load_options(); self.query_sales(); self.refresh_summary()

    def query_sales(self):
        try: self.saved = self._get('sales'); self.refresh_today()
        except Exception as exc: QMessageBox.warning(self, '조회 오류', PurchaseRegWindow._error_text(exc))

    def refresh_today(self):
        day = self.date.date().toString('yyyy-MM-dd')
        rows = [x for x in self.saved if str(x['sale_date']) == day and x['document_status'] != 'CANCELLED']
        self.today_table.blockSignals(True)
        try:
            self.today_table.setRowCount(0)
            for index, sale in enumerate(rows, 1):
                row = self.today_table.rowCount(); self.today_table.insertRow(row)
                for col, text in enumerate((index, sale.get('account_code') or '', sale.get('account_name') or '', f"{int(sale['total_amount']):,}")):
                    self.today_table.setItem(row, col, QTableWidgetItem(str(text)))
                self.today_table.item(row, 0).setData(Qt.UserRole, sale['sale_id'])
        finally: self.today_table.blockSignals(False)

    def open_sale(self):
        row = self.today_table.currentRow()
        if row < 0 or not self.today_table.item(row, 0): return
        key = self.today_table.item(row, 0).data(Qt.UserRole)
        sale = next((x for x in self.saved if x['sale_id'] == key), None)
        if sale:
            try: self.load_sale(sale)
            except Exception as exc: QMessageBox.warning(self, '전표 로딩 오류', PurchaseRegWindow._error_text(exc))

    def load_sale(self, sale):
        self.sale_id = sale['sale_id']; self.original = {x['lot_id']:True for x in sale['items']}
        self.loading = True
        try:
            self.table.setRowCount(0); self.line_extras = []; self.refresh_inventory()
            self.date.setDate(QDate.fromString(sale['sale_date'], 'yyyy-MM-dd'))
            self.set_customer({'account_id':sale['account_id'], 'account_code':sale.get('account_code'), 'account_name':sale.get('account_name')})
            self.memo.setPlainText(sale.get('memo') or ''); self.reason.setText(sale.get('inventory_exception_reason') or '')
            for item in sale['items']: self.add_row(item)
            self.document_no.setText(sale['sale_no'])
            active = sale['document_status'] == 'CONFIRMED'
            self.status.setText('확정 / 수정조회' if active else '취소')
            self.btn_save.setEnabled(active); self.btn_cancel.setEnabled(active)
        finally: self.loading = False
        self.recalculate(); self.refresh_today(); self.refresh_summary()

    def new_sale(self, keep_date=False):
        self.loading = True
        self.sale_id = None; self.original = {}; self.customer = None
        self.table.setRowCount(0); self.line_extras = []; self.customer_edit.clear(); self.memo.clear(); self.reason.clear()
        for label in (self.phone, self.fax, self.email): label.setText('—')
        if not keep_date: self.date.setDate(QDate.currentDate())
        self.document_no.setText('신규'); self.status.setText('신규입력')
        self.btn_save.setEnabled(True); self.btn_cancel.setEnabled(False)
        try: self.refresh_inventory(); self.add_row()
        except Exception as exc: QMessageBox.warning(self, 'LOT 조회 오류', PurchaseRegWindow._error_text(exc))
        finally: self.loading = False
        self.today_table.clearSelection(); self.refresh_today(); self.recalculate(); self.refresh_summary(); self.customer_edit.setFocus()

    def remove_row(self):
        rows = {x.row() for x in self.table.selectedIndexes()}
        if not rows and self.table.currentRow() >= 0: rows.add(self.table.currentRow())
        for row in sorted(rows, reverse=True): self.table.removeRow(row); self.line_extras.pop(row)
        if not self.table.rowCount(): self.add_row()
        self.recalculate()

    def reset_input(self):
        if QMessageBox.question(self, '입력 취소', '현재 입력 또는 수정 중인 내용을 취소하시겠습니까?') == QMessageBox.Yes:
            self.new_sale(keep_date=True)

    def _date_changed(self, *_):
        if not self.loading: self.refresh_today(); self.refresh_summary()
