"""Three focused Batch 2A screens over shared lookup and existing ERP records."""
import json
from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QPlainTextEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFileDialog, QCheckBox, QScrollArea, QSplitter)
import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from views.lookup_dialog import LookupDialog, error_text
from contract_document_templates import FORMS


def line(placeholder=''):
    widget = QLineEdit(); widget.setPlaceholderText(placeholder); return widget


class WorkWindow(QWidget):
    resource = ''; menu = ''; pk = ''
    def __init__(self):
        super().__init__(); self.current = None; self.rows = []
        self.root = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['번호/ID', '상태', 'Version', '연결 계약/수입건'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMaximumHeight(155); self.table.itemSelectionChanged.connect(self.select)
        self.root.addWidget(self.table)
        self.summary = QLabel('선택한 앞 단계의 자료를 자동승계합니다.'); self.root.addWidget(self.summary)
        self.form_widget = QWidget(); self.form = QFormLayout(self.form_widget)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.form_widget)
        self.root.addWidget(scroll, 1)
        self.buttons = QHBoxLayout(); self.root.addLayout(self.buttons)
        self.add_button('새 입력', self.clear)
        self.add_button('조회/새로고침', self.refresh)

    @property
    def base(self): return f'{API_BASE_URL}/companies/{app_context.company_code}'

    def request(self, method, suffix='', **kwargs):
        response = getattr(httpx, method)(self.base + '/' + self.resource + suffix, timeout=25, **kwargs)
        response.raise_for_status(); return response.json()

    def run(self, operation):
        try: operation()
        except Exception as exc: QMessageBox.critical(self, '업무 처리 오류', error_text(exc))

    def add_button(self, label, operation, action=None):
        button = QPushButton(label)
        button.clicked.connect(lambda: self.run(operation))
        if action: button.setEnabled(app_context.can(self.menu, action))
        self.buttons.addWidget(button); return button

    def refresh(self):
        self.rows = self.request('get'); self.table.setRowCount(0)
        for data in self.rows:
            number = self.table.rowCount(); self.table.insertRow(number)
            values = [data.get('import_case_no') or data[self.pk], data['status'], data.get('version', ''),
                      data.get('contract_id') or data.get('import_case_id', '')]
            for col, value in enumerate(values): self.table.setItem(number, col, QTableWidgetItem(str(value)))
            self.table.item(number, 0).setData(Qt.UserRole, data[self.pk])

    def select(self):
        index = self.table.currentRow()
        if index >= 0 and self.table.item(index, 0):
            self.run(lambda: self.load(self.request('get', '/' + str(self.table.item(index, 0).data(Qt.UserRole)))))

    def load(self, value):
        self.current = value
        self.summary.setText(f"ID {value[self.pk]} / {value['status']}")

    def clear(self):
        self.current = None; self.table.clearSelection(); self.summary.setText('새 자료 입력')

    def choose(self, resource, title, columns, params=None):
        def fetch(keyword):
            response = httpx.get(self.base + '/' + resource, params={**(params or {}), 'lookup_for': self.menu}, timeout=20)
            response.raise_for_status()
            return [x for x in response.json() if keyword.casefold() in ' '.join(str(x.get(key) or '') for _, key in columns).casefold()][:50]
        dialog = LookupDialog(self, title, '', columns, fetch)
        return dialog.selected if dialog.exec() == QDialog.Accepted else None

    def pick(self, target, resource, title, columns, pk, label, params=None):
        value = self.choose(resource, title, columns, params)
        if value:
            target.setText(str(value.get(label, ''))); target.setProperty('pk', value[pk]); return value

    def picker(self, target, operation):
        row = QWidget(); layout = QHBoxLayout(row); layout.setContentsMargins(0,0,0,0)
        button = QPushButton('검색'); button.clicked.connect(lambda: self.run(operation))
        target.setReadOnly(True); layout.addWidget(target, 1); layout.addWidget(button); return row


class ContractDocumentWindow(WorkWindow):
    resource = 'contract-documents'; menu = 'FINANCING_DOCUMENT'; pk = 'document_id'
    def __init__(self):
        super().__init__(); self.contract = line(); self.template = QComboBox()
        self.set_templates()
        self.form.addRow('확정 계약', self.picker(self.contract, self.pick_contract))
        self.form.addRow('출력양식', self.template)
        self.body = QTextEdit(); self.body.setAcceptRichText(False); self.body.setMinimumHeight(400)
        self.form.addRow('표준 초안 / 문구·표 수정', self.body)
        self.form.addRow(QLabel('미입력 빈칸은 초안에서 확인·수정하십시오. 원화 기준단가는 USD 오퍼단가로 변환하지 않습니다.\n문서 편집은 원계약 조건을 변경하지 않습니다. 관세사용 양식에는 금액을 추가하지 마십시오.'))
        self.reason = line('수정/취소 사유'); self.form.addRow('사유', self.reason)
        self.add_button('자동초안 생성', self.create, 'create')
        self.add_button('표준양식 다시 작성', self.regenerate, 'update')
        self.add_button('문구 저장', self.save, 'update')
        self.add_button('확정', lambda: self.action('confirm'), 'update')
        self.add_button('취소', lambda: self.action('cancel'), 'update')
        self.add_button('PDF 저장', self.pdf)
        self.add_button('인쇄', self.print_document)
        self.run(self.refresh)

    def pick_contract(self):
        value = self.pick(self.contract, 'financing-contracts', '확정 계약 검색',
            [('계약번호','contract_no'),('업체','contractor_name'),('상태','status')], 'contract_id','contract_no')
        if value: self.set_templates(value['contract_type'])

    def set_templates(self, kind=None, selected=None):
        self.template.clear()
        for code, (label, contract_type, _) in FORMS.items():
            if kind is None or kind == contract_type: self.template.addItem(label, code)
        if selected: self.template.setCurrentIndex(self.template.findData(selected))

    def refresh(self):
        super().refresh()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['문서 ID','상태','Version','연결 계약','출력양식'])
        for index, value in enumerate(self.rows):
            self.table.setItem(index,4,QTableWidgetItem(FORMS.get(value['template_type'], (value['template_type'],))[0]))

    def clear(self):
        super().clear(); self.contract.clear(); self.contract.setProperty('pk', None); self.body.clear(); self.body.setReadOnly(False); self.reason.clear(); self.set_templates()

    def load(self, value):
        super().load(value); self.contract.setProperty('pk', value['contract_id'])
        self.contract.setText(value['snapshot']['contract']['contract_no'])
        self.set_templates(value['snapshot']['contract']['contract_type'], value['template_type'])
        if value['snapshot'].get('body_format') == 'HTML': self.body.setHtml(value['body'])
        else: self.body.setPlainText(value['body'])
        self.body.setReadOnly(value['status'] != 'DRAFT'); self.body.document().setModified(False)
        if not value['snapshot'].get('template_revision'):
            self.summary.setText(self.summary.text() + ' / 기존 예시 문서: 초안은 표준양식 다시 작성, 확정본은 새 version을 생성하십시오.')

    def create(self):
        value = self.request('post', json={'contract_id': self.contract.property('pk'), 'template_type': self.template.currentData()})
        self.refresh(); self.load(value)

    def save(self):
        if self.current:
            self.load(self.request('put', '/' + str(self.current[self.pk]), json={'body': self.body.toHtml(), 'reason': self.reason.text() or None}))

    def regenerate(self):
        if self.current:
            self.load(self.request('post', f"/{self.current[self.pk]}/regenerate", json={'reason':self.reason.text() or '표준양식으로 초안 재작성'}))

    def action(self, action):
        if self.current:
            if action == 'confirm' and self.body.document().isModified(): self.save()
            value = self.request('post', f"/{self.current[self.pk]}/{action}", **({'json': {'reason': self.reason.text()}} if action == 'cancel' else {}))
            self.refresh(); self.load(value)

    def pdf(self):
        if not self.current: return
        from financing_document import export_contract_pdf
        document = self.request('get', '/' + str(self.current[self.pk]))
        filename, _ = QFileDialog.getSaveFileName(self, '계약서 PDF 저장', f"계약서_{document[self.pk]}_v{document['version']}.pdf", 'PDF (*.pdf)')
        if filename: export_contract_pdf(document, filename)

    def print_document(self):
        if not self.current: return
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        from financing_document import print_contract
        document = self.request('get', '/' + str(self.current[self.pk]))
        printer = QPrinter(QPrinter.HighResolution)
        if QPrintDialog(printer, self).exec() == QDialog.Accepted: print_contract(document, printer)


class ImportCaseWindow(WorkWindow):
    resource = 'import-cases'; menu = 'IMPORT_INTAKE'; pk = 'import_case_id'
    def __init__(self):
        super().__init__(); self.contract = line('일반 수입건은 계약 선택 없이 상품 추가'); self.supplier = line()
        self.form.addRow('계약 (선택)', self.picker(self.contract, self.pick_contract))
        self.form.addRow('실제 공급업체 (계약업체와 별도)', self.picker(self.supplier, self.pick_supplier))
        self.bl = line(); self.reference = line(); self.currency = line('USD / KRW 등'); self.currency.setText('USD')
        self.customs = line('yyyy-MM-dd'); self.receipt = line('yyyy-MM-dd'); self.memo = line()
        for label, widget in [('BL',self.bl),('Container/Reference',self.reference),('통화',self.currency),('실제 통관일',self.customs),('실제 입고일',self.receipt),('비고',self.memo)]: self.form.addRow(label, widget)
        self.items = QTableWidget(0, 5); self.items.setHorizontalHeaderLabels(['상품','계약상품','BOX','KG','실제 LOT'])
        self.items.setMinimumHeight(160); self.form.addRow('계약상품 자동승계 / 실제 LOT 연결', self.items)
        self.add_button('상품 추가', self.add_product, 'create')
        self.add_button('선택행 LOT 검색', self.link_lot, 'update')
        self.add_button('선택행 분할', self.split, 'update')
        self.add_button('선택행 삭제', self.delete_item, 'update')
        self.add_button('수입건 저장', self.save, 'create')
        self.add_button('변경 저장', self.save, 'update')
        self.add_button('접수 진행', lambda: self.action('start'), 'update')
        self.add_button('원가확정 후 수입건 마감', lambda: self.action('close'), 'update')
        self.run(self.refresh)

    def pick_contract(self):
        value = self.pick(self.contract, 'financing-contracts', '계약 검색', [('계약번호','contract_no'),('업체','contractor_name')], 'contract_id', 'contract_no')
        if value:
            self.items.setRowCount(0)
            for item in value['items']: self.append_item({'contract_item_id': item['contract_item_id'], 'product_id': item['product_id'],
                'product_name': item.get('product_name'), 'box_qty': item['contract_box_qty'], 'weight': item['contract_weight']})
            self.summary.setText(f"계약 {value['contract_no']} 자동승계 / 실제 통관일·입고일은 별도 확인 입력")

    def pick_supplier(self):
        self.pick(self.supplier, 'accounts', '공급업체 검색', [('거래처','account_name'),('코드','account_code'),('사업자번호','biz_no')], 'account_id','account_name', {'purpose':'CONTRACT'})

    def append_item(self, data):
        index = self.items.rowCount(); self.items.insertRow(index)
        for col, value in enumerate([data.get('product_name') or data['product_id'], data.get('contract_item_id') or '', data.get('box_qty', 0), data.get('weight', 0), data.get('lot_code') or data.get('lot_id') or '']):
            cell = QTableWidgetItem(str(value))
            if col in {0,1,4}: cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            self.items.setItem(index, col, cell)
        self.items.item(index, 0).setData(Qt.UserRole, data)

    def add_product(self):
        if self.contract.property('pk'): raise ValueError('계약 수입건은 자동승계 계약상품을 분할하여 사용하세요.')
        def fetch(keyword):
            response = httpx.get(f'{API_BASE_URL}/products', params={'search':keyword,'limit':50,'lookup_for':self.menu}, timeout=20)
            response.raise_for_status(); return response.json()
        dialog = LookupDialog(self, '상품 검색', '', [('코드','product_code'),('상품명','product_name'),('규격','specification')], fetch)
        if dialog.exec() == QDialog.Accepted: self.append_item(dialog.selected)

    def link_lot(self):
        index = self.items.currentRow()
        if index < 0: return
        data = self.items.item(index, 0).data(Qt.UserRole)
        value = self.choose('lots','기존 ERP LOT 검색',[('LOT','lot_code'),('상품','product_name'),('BL','bl_no')])
        if value:
            if value['product_id'] != data['product_id']: raise ValueError('선택 상품과 LOT가 다릅니다.')
            data = {**data,'lot_id':value['lot_id'],'lot_code':value['lot_code']}
            self.items.item(index,0).setData(Qt.UserRole,data); self.items.item(index,4).setText(value['lot_code'])
            if not self.bl.text(): self.bl.setText(value.get('bl_no') or '')

    def split(self):
        index = self.items.currentRow()
        if index >= 0:
            data = dict(self.items.item(index,0).data(Qt.UserRole)); data.pop('lot_id',None); data.pop('lot_code',None)
            self.append_item(data)

    def delete_item(self):
        if self.items.currentRow() >= 0: self.items.removeRow(self.items.currentRow())

    def payload(self):
        items = []
        for index in range(self.items.rowCount()):
            data = self.items.item(index,0).data(Qt.UserRole)
            items.append({'contract_item_id':data.get('contract_item_id'), 'product_id':data['product_id'], 'lot_id':data.get('lot_id'),
                'box_qty':int(self.items.item(index,2).text() or '0'), 'weight':self.items.item(index,3).text() or '0'})
        return {'contract_id':self.contract.property('pk'), 'supplier_account_id':self.supplier.property('pk'),
            'bl_no':self.bl.text() or None,'reference':self.reference.text() or None,'currency':self.currency.text().upper(),
            'customs_date':self.customs.text() or None,'warehouse_receipt_date':self.receipt.text() or None,'memo':self.memo.text() or None,'items':items}

    def save(self):
        value = self.request('put' if self.current else 'post', '/' + str(self.current[self.pk]) if self.current else '', json=self.payload())
        self.refresh(); self.load(value)

    def load(self, value):
        super().load(value); self.contract.setProperty('pk',value['contract_id']); self.contract.setText(value.get('contract_no') or '일반 수입건')
        self.supplier.setProperty('pk',value['supplier_account_id']); self.supplier.setText(value.get('supplier_name') or '')
        for widget, key in [(self.bl,'bl_no'),(self.reference,'reference'),(self.currency,'currency'),(self.customs,'customs_date'),(self.receipt,'warehouse_receipt_date'),(self.memo,'memo')]: widget.setText(str(value.get(key) or ''))
        self.items.setRowCount(0)
        for item in value['items']: self.append_item(item)

    def clear(self):
        super().clear()
        for widget in [self.contract,self.supplier,self.bl,self.reference,self.customs,self.receipt,self.memo]: widget.clear(); widget.setProperty('pk',None)
        self.items.setRowCount(0); self.currency.setText('USD')

    def action(self, action):
        if self.current:
            kwargs = {'json':{'reason':'수입접수 업무 마감'}} if action == 'close' else {}
            value = self.request('post', f"/{self.current[self.pk]}/{action}", **kwargs); self.refresh(); self.load(value)


class ImportCostWindow(WorkWindow):
    resource = 'import-costs'; menu = 'IMPORT_COST'; pk = 'settlement_id'
    FIELDS = [('cost_name','비용명'),('cost_kind','EVENT/PERIOD'),('occurred_on','발생일'),
        ('amount','실제 금액 ±'),('currency','통화'),('exchange_rate','실제 환율'),('period_start','기간 시작'),
        ('period_end','기간 종료'),('rate','Rate'),('basis','Basis'),('basis_quantity','Basis 수량'),
        ('tax_kind','세무구분'),('tax_amount_krw','세액 KRW'),('payer','부담주체'),('product_id','배부 상품 (선택)'),('lot_id','배부 LOT (선택)'),('memo','비고')]
    def __init__(self):
        super().__init__(); self.case = line(); self.case_data = None
        self.form.addRow('수입건/BL', self.picker(self.case,self.pick_case))
        self.conditions = QPlainTextEdit(); self.conditions.setReadOnly(True); self.conditions.setMaximumHeight(90)
        self.form.addRow('자동승계 계약/상품/참고조건', self.conditions)
        self.cost_rows = QTableWidget(0, 7); self.cost_rows.setHorizontalHeaderLabels(['비용명','구분','발생일/기간','실제금액/통화','KRW','출처','배부 범위'])
        self.cost_rows.setEditTriggers(QTableWidget.NoEditTriggers); self.cost_rows.setSelectionBehavior(QTableWidget.SelectRows)
        self.cost_rows.itemSelectionChanged.connect(self.select_cost); self.form.addRow('실제 발생 원가행', self.cost_rows)
        self.fields = {}
        for key, label in self.FIELDS:
            if key in {'cost_kind','tax_kind','payer'}:
                widget = QComboBox()
                for value in {'cost_kind':['EVENT','PERIOD'],'tax_kind':['EXEMPT','TAXABLE','ZERO','OUT_OF_SCOPE'],'payer':['MXMN','CONTRACTOR','SUPPLIER','SHIPPER']}[key]: widget.addItem(value)
            else: widget = line('yyyy-MM-dd' if key in {'occurred_on','period_start','period_end'} else '')
            self.fields[key] = widget
            if key in {'product_id','lot_id'}:
                self.form.addRow(label, self.picker(widget, lambda field=key: self.pick_scope(field)))
            else: self.form.addRow(label, widget)
        self.capitalize = QCheckBox('세액을 원가에 포함 (기본 제외)'); self.form.addRow(self.capitalize)
        self.method = QComboBox(); self.method.addItems(['WEIGHT','DIRECT']); self.form.addRow('LOT 배부 방식', self.method)
        self.allocations = QTableWidget(0,5); self.allocations.setHorizontalHeaderLabels(['상품/LOT','Case Item','참고/확정 KG','배부 KRW (직접입력)','원/KG'])
        self.form.addRow('LOT 배부 (중량은 실제 입고원장 기준)', self.allocations)
        self.total = QLabel('원가합계 0원'); self.form.addRow(self.total)
        self.reason = line('정정/확정취소 사유'); self.form.addRow('사유',self.reason)
        self.add_button('기본 원가정산 생성', self.create, 'create')
        self.add_button('행 입력 초기화', self.clear_row)
        self.add_button('+ 자유항목 추가', self.add_row, 'update')
        self.add_button('선택행 저장', self.edit_row, 'update')
        self.add_button('선택행 삭제', self.delete_row, 'delete')
        self.add_button('확정 / LOT 원가배부', self.confirm, 'update')
        self.add_button('확정취소', self.cancel, 'update')
        self.clear_row(); self.run(self.refresh)

    def pick_case(self):
        value = self.pick(self.case, 'import-cases','수입건/BL 검색',[('수입건','import_case_no'),('BL','bl_no'),('상태','status')],'import_case_id','import_case_no')
        if value:
            self.case_data = value; self.conditions.setPlainText(json.dumps(value['source_snapshot'],ensure_ascii=False,indent=2))
            self.show_allocations(value['items'])

    def show_allocations(self, entries):
        self.allocations.setRowCount(0)
        for entry in entries:
            row = self.allocations.rowCount(); self.allocations.insertRow(row)
            values = [entry.get('lot_code') or entry.get('lot_id') or 'LOT 미연결', entry.get('case_item_id'), entry.get('actual_weight',entry.get('weight')),
                      entry.get('allocated_cost',0), entry.get('unit_cost','')]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value or ''))
                if col != 3: cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                self.allocations.setItem(row,col,cell)

    def create(self):
        value = self.request('post',json={'import_case_id':self.case.property('pk'),'basic_rows':True}); self.refresh(); self.load(value)

    def clear_row(self):
        for widget in self.fields.values():
            if isinstance(widget,QComboBox): widget.setCurrentIndex(0)
            else: widget.clear(); widget.setProperty('pk', None)
        self.fields['currency'].setText('KRW'); self.fields['tax_amount_krw'].setText('0'); self.capitalize.setChecked(False)

    def pick_scope(self, field):
        if not self.case_data: return
        entries = self.case_data['items']
        columns = [('상품','product_name'),('LOT','lot_code')]
        def fetch(keyword):
            return [x for x in entries if keyword.casefold() in (str(x.get('product_name') or '')+' '+str(x.get('lot_code') or '')).casefold()]
        dialog = LookupDialog(self, '수입건 내 상품/LOT 배부대상', '', columns, fetch)
        if dialog.exec() == QDialog.Accepted:
            value = dialog.selected
            self.fields[field].setProperty('pk',value[field]); self.fields[field].setText(value.get('product_name' if field == 'product_id' else 'lot_code') or '')

    def row_payload(self):
        data = {key: widget.currentText() if isinstance(widget,QComboBox) else widget.text() or None for key, widget in self.fields.items()}
        for key in ['product_id','lot_id']:
            data[key] = self.fields[key].property('pk')
        data.update({'capitalize_tax':self.capitalize.isChecked(),'reason':self.reason.text() or None})
        data['tax_amount_krw'] = data['tax_amount_krw'] or '0'
        return data

    def select_cost(self):
        index = self.cost_rows.currentRow()
        if self.current and 0 <= index < len(self.current['rows']):
            data = self.current['rows'][index]
            for key, widget in self.fields.items():
                if isinstance(widget,QComboBox): widget.setCurrentText(data[key])
                else:
                    widget.setText(str(data.get(key) or ''))
                    if key in {'product_id','lot_id'}: widget.setProperty('pk',data.get(key))
            self.capitalize.setChecked(data['capitalize_tax'])

    def selected_row_id(self):
        index = self.cost_rows.currentRow()
        return self.current['rows'][index]['cost_row_id'] if self.current and index >= 0 else None

    def add_row(self):
        if self.current: self.load(self.request('post', f"/{self.current[self.pk]}/rows", json=self.row_payload()))

    def edit_row(self):
        key = self.selected_row_id()
        if key: self.load(self.request('put',f"/{self.current[self.pk]}/rows/{key}",json=self.row_payload()))

    def delete_row(self):
        key = self.selected_row_id()
        if key: self.load(self.request('delete',f"/{self.current[self.pk]}/rows/{key}",params={'reason':self.reason.text()}))

    def confirm(self):
        if not self.current: return
        allocations = []
        if self.method.currentText() == 'DIRECT':
            for row in range(self.allocations.rowCount()): allocations.append({'case_item_id':int(self.allocations.item(row,1).text()),'amount':self.allocations.item(row,3).text() or '0'})
        value = self.request('post',f"/{self.current[self.pk]}/confirm",json={'allocation_method':self.method.currentText(),'allocations':allocations,'reason':self.reason.text() or None})
        self.refresh(); self.load(value)

    def cancel(self):
        if self.current:
            value = self.request('post',f"/{self.current[self.pk]}/cancel",json={'reason':self.reason.text()}); self.refresh(); self.load(value)

    def load(self, value):
        super().load(value); self.case.setProperty('pk',value['import_case_id'])
        response = httpx.get(self.base+'/import-cases/'+str(value['import_case_id']), params={'lookup_for': self.menu}, timeout=20); response.raise_for_status()
        self.case_data = response.json(); self.case.setText(self.case_data['import_case_no'] + ' / ' + str(self.case_data['bl_no'] or ''))
        self.conditions.setPlainText(json.dumps(self.case_data['source_snapshot'],ensure_ascii=False,indent=2))
        self.cost_rows.setRowCount(0)
        for entry in value['rows']:
            index = self.cost_rows.rowCount(); self.cost_rows.insertRow(index)
            values = [entry['cost_name'],entry['cost_kind'],entry['occurred_on'] or f"{entry['period_start']} ~ {entry['period_end']}",
                f"{entry['amount']} {entry['currency']}",entry['krw_amount'],entry['origin'],entry['lot_id'] or entry['product_id'] or 'BL 전체']
            for col,item in enumerate(values): self.cost_rows.setItem(index,col,QTableWidgetItem(str(item or '')))
        self.show_allocations(value['allocations'] or self.case_data['items']); self.total.setText(f"원가합계 ±조정 포함: {value['total_cost']}원 / {value['status']}")

    def clear(self):
        super().clear(); self.case.clear(); self.case.setProperty('pk',None); self.conditions.clear(); self.cost_rows.setRowCount(0); self.allocations.setRowCount(0); self.clear_row()
