from decimal import Decimal, ROUND_CEILING
from collections import defaultdict
import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QDateEdit,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QComboBox,QMessageBox,QInputDialog

class SaleRegWindow(QWidget):
    def __init__(self):
        super().__init__(); self.sale_id=None; self.lots=[]; self.accounts=[]; self.original={}; self.loading=False; self.header_memo=None; self.line_extras=[]
        layout=QVBoxLayout(self); head=QHBoxLayout(); self.date=QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.account=QComboBox(); self.btn_load=QPushButton('거래처/LOT 조회'); self.btn_load.clicked.connect(self.load_options)
        head.addWidget(QLabel('매출일자'));head.addWidget(self.date);head.addWidget(QLabel('거래처'));head.addWidget(self.account,1);head.addWidget(self.btn_load);layout.addLayout(head)
        browse=QHBoxLayout(); self.documents=QComboBox(); self.btn_query=QPushButton('매출전표 조회'); self.btn_query.clicked.connect(self.query_sales); self.btn_open=QPushButton('선택 전표 열기'); self.btn_open.clicked.connect(self.open_sale); self.btn_new=QPushButton('신규'); self.btn_new.clicked.connect(self.new_sale)
        for widget in (self.documents,self.btn_query,self.btn_open,self.btn_new): browse.addWidget(widget)
        layout.addLayout(browse); self.status=QLabel('신규 전표'); layout.addWidget(self.status)
        self.summary=QLabel(); layout.addWidget(self.summary)
        self.table=QTableWidget(0,11);self.table.setHorizontalHeaderLabels(['LOT','상품','창고','BOX','중량(KG)','판매단가','공급금액(예상)','가용 BOX','가용 KG','출고 후 BOX','출고 후 KG']);layout.addWidget(self.table)
        self.table.itemChanged.connect(self.recalculate)
        self.warning=QLabel(); layout.addWidget(self.warning)
        reason_row=QHBoxLayout(); reason_row.addWidget(QLabel('예외출고 사유')); self.reason=QLineEdit(); self.reason.setMaxLength(1000); reason_row.addWidget(self.reason); layout.addLayout(reason_row)
        self.btn_remove=QPushButton('선택 행 삭제'); self.btn_remove.clicked.connect(self.remove_row); layout.addWidget(self.btn_remove)
        self.account.currentIndexChanged.connect(self.refresh_summary); self.date.dateChanged.connect(self.refresh_summary)
        buttons=QHBoxLayout(); self.btn_add=QPushButton('LOT 행 추가');self.btn_add.clicked.connect(self.add_row);self.btn_save=QPushButton('저장');self.btn_save.clicked.connect(self.save);self.btn_cancel=QPushButton('취소');self.btn_cancel.clicked.connect(self.cancel);self.btn_cancel.setEnabled(False);buttons.addWidget(self.btn_add);buttons.addStretch();buttons.addWidget(self.btn_save);buttons.addWidget(self.btn_cancel);layout.addLayout(buttons)
        self.load_options()
    def _get(self,path,**params):
        r=httpx.get(f'{API_BASE_URL}/companies/{app_context.company_code}/{path}',params=params,timeout=15);r.raise_for_status();return r.json()
    def load_options(self):
        try:
            self.refresh_inventory(); self.accounts=self._get('accounts')
            selected=self.account.currentData(); self.account.blockSignals(True)
            self.account.clear()
            for a in self.accounts:
                if a.get('sales_yn') and a.get('use_yn',True): self.account.addItem(f"{a.get('account_name')} ({a.get('account_code')})",a['account_id'])
            self.account.setCurrentIndex(max(0,self.account.findData(selected))); self.account.blockSignals(False)
            if not self.table.rowCount(): self.add_row()
            self.refresh_summary()
        except Exception as e: QMessageBox.warning(self,'조회 오류',str(e))
    def add_row(self):
        r=self.table.rowCount();self.table.insertRow(r); lot=QComboBox()
        for x in self.lots:
            if not x.get('use_yn',True) and x['lot_id'] not in self.original: continue
            lot.addItem(f"{x['lot_code']} | {x['product_name']} | {x['warehouse_name']}",x)
        lot.currentIndexChanged.connect(lambda _,row=r:self.fill_lot(row));self.table.setCellWidget(r,0,lot)
        self.loading=True
        for c in range(1,11):
            item=QTableWidgetItem('0' if c>=3 else '')
            if c not in (3,4,5): item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r,c,item)
        self.loading=False; self.line_extras.append({})
        self.fill_lot(r)
    def fill_lot(self,row):
        x=self.table.cellWidget(row,0).currentData() or {};self.table.item(row,1).setText(x.get('product_name',''));self.table.item(row,2).setText(x.get('warehouse_name','')); self.recalculate()
    def payload(self):
        items=[]
        for r in range(self.table.rowCount()):
            lot=self.table.cellWidget(r,0).currentData(); box=int(self.table.item(r,3).text()); weight=Decimal(self.table.item(r,4).text()); price=int(self.table.item(r,5).text())
            if not lot or box<0 or not weight.is_finite() or weight<=0 or weight.as_tuple().exponent < -2 or price<0: raise ValueError(f'{r+1}행 LOT/BOX/KG/단가를 확인하세요.')
            items.append({**self.line_extras[r], 'line_no':r+1,'product_id':lot['product_id'],'lot_id':lot['lot_id'],'box_qty':box,'weight':str(weight),'unit_price':price})
        if not items or self.account.currentData() is None: raise ValueError('거래처와 출고 행을 입력하세요.')
        if self.recalculate() and not self.reason.text().strip(): raise ValueError('마이너스 재고 출고 사유를 입력하세요.')
        return {'memo':self.header_memo, 'inventory_exception_reason':self.reason.text().strip() or None, 'sale_date':self.date.date().toString('yyyy-MM-dd'),'account_id':self.account.currentData(),'items':items}
    def save(self):
        try:
            self.refresh_inventory(); data=self.payload();base=f'{API_BASE_URL}/companies/{app_context.company_code}/sales';r=httpx.put(f'{base}/{self.sale_id}',json=data,timeout=30) if self.sale_id else httpx.post(base,json=data,timeout=30);r.raise_for_status();saved=r.json(); self.load_sale(saved); self.query_sales(); QMessageBox.information(self,'저장 완료',f"{saved['sale_no']} 확정 저장되었습니다.")
        except Exception as e: QMessageBox.warning(self,'저장 오류',str(e))
    def cancel(self):
        if not self.sale_id:return
        reason,ok=QInputDialog.getText(self,'매출 취소','취소 사유');
        if ok and reason.strip():
            try: httpx.post(f'{API_BASE_URL}/companies/{app_context.company_code}/sales/{self.sale_id}/cancel',json={'reason':reason.strip()},timeout=20).raise_for_status();self.new_sale(); self.query_sales(); QMessageBox.information(self,'완료','취소되었습니다.')
            except Exception as e: QMessageBox.warning(self,'취소 오류',str(e))

    def refresh_inventory(self):
        params={'editing_sale_id':self.sale_id} if self.sale_id else {}
        self.lots=self._get('sales/lot-availability',**params)
        self.recalculate()

    def refresh_summary(self,*_):
        if self.loading: return
        self.summary.setText('미수 조회 중...')
        try:
            if self.account.currentData() is None:
                self.summary.setText('거래처를 선택하세요.'); return
            value=self._get('sales-receivable-summary',account_id=self.account.currentData(),transaction_date=self.date.date().toString('yyyy-MM-dd'))
            self.summary.setText(' | '.join(f'{label}: {value[key]:,}원' for key,label in [('previous_receivable','이전 미수'),('today_sales','금일 매출'),('today_receipt','금일 수금'),('current_receivable','현재 미수')]))
        except Exception as e: self.summary.setText(f'미수 조회 실패: {e}')

    def recalculate(self,*_):
        if self.loading: return False
        totals=defaultdict(lambda:[0,Decimal(0)]); invalid=False
        for row in range(self.table.rowCount()):
            lot=self.table.cellWidget(row,0).currentData()
            if not lot: continue
            try:
                box=int(self.table.item(row,3).text()); kg=Decimal(self.table.item(row,4).text())
                if not kg.is_finite(): raise ValueError()
                totals[lot['lot_id']][0]+=box; totals[lot['lot_id']][1]+=kg
            except Exception: invalid=True
        negative=[]; self.table.blockSignals(True)
        try:
            current={x['lot_id']:x for x in self.lots}
            for row in range(self.table.rowCount()):
                selected=self.table.cellWidget(row,0).currentData()
                if not selected: continue
                lot=current[selected['lot_id']]; box=lot['available_box_qty']; kg=Decimal(str(lot['available_weight']))
                issued=totals[lot['lot_id']]
                after_box=box+lot['editing_box_qty']-issued[0]; after_kg=kg+Decimal(str(lot['editing_weight']))-issued[1]
                for col,value in [(7,str(box)),(8,f'{kg:.2f}'),(9,str(after_box)),(10,f'{after_kg:.2f}')]:
                    self.table.item(row,col).setText(value)
                    self.table.item(row,col).setForeground(Qt.GlobalColor.red if (col>=9 and (after_box<0 or after_kg<0)) else Qt.GlobalColor.black)
                try:
                    amount=(Decimal(self.table.item(row,4).text())*int(self.table.item(row,5).text())).quantize(Decimal('1'),rounding=ROUND_CEILING)
                    self.table.item(row,6).setText(f'{amount:,}')
                except Exception: self.table.item(row,6).setText('입력 확인')
                if after_box<0 or after_kg<0: negative.append(lot['lot_code'])
        finally: self.table.blockSignals(False)
        self.warning.setStyleSheet('color:red; font-weight:bold')
        self.warning.setText(('마이너스 재고: '+', '.join(sorted(set(negative)))+' — 예외출고 사유 필수. ' if negative else '')+('BOX/KG 입력을 확인하세요.' if invalid else '')+('수정 예상재고 = 현재 가용 + 기존 전표 출고 − 이번 전표 합계' if self.sale_id else '예상재고 = 현재 가용 − 동일 LOT 전표 합계'))
        return bool(negative)

    def query_sales(self):
        try:
            rows=self._get('sales'); self.documents.clear()
            for sale in rows: self.documents.addItem(f"{sale['sale_date']} | {sale['sale_no']} | {sale['account_name']} | {sale['document_status']}",sale)
        except Exception as e: QMessageBox.warning(self,'조회 오류',str(e))

    def open_sale(self):
        sale=self.documents.currentData()
        if sale:
            try: self.load_sale(sale)
            except Exception as e: QMessageBox.warning(self,'전표 로딩 오류',str(e))

    def load_sale(self,sale):
        self.sale_id=sale['sale_id']; self.original={x['lot_id']:True for x in sale['items']}; self.header_memo=sale.get('memo')
        self.refresh_inventory(); self.loading=True; self.table.setRowCount(0); self.line_extras=[]
        self.date.setDate(QDate.fromString(sale['sale_date'],'yyyy-MM-dd'))
        index=self.account.findData(sale['account_id'])
        if index<0:
            self.account.addItem(sale['account_name'] or str(sale['account_id']),sale['account_id']); index=self.account.count()-1
        self.account.setCurrentIndex(index); self.reason.setText(sale.get('inventory_exception_reason') or '')
        for item in sale['items']:
            self.add_row(); self.loading=True; row=self.table.rowCount()-1; combo=self.table.cellWidget(row,0)
            index=next((i for i in range(combo.count()) if combo.itemData(i)['lot_id']==item['lot_id']),-1)
            if index<0: raise ValueError('전표 LOT를 조회할 수 없습니다.')
            combo.setCurrentIndex(index)
            for col,key in [(3,'box_qty'),(4,'weight'),(5,'unit_price')]: self.table.item(row,col).setText(str(item[key]))
            self.line_extras[row]={key:item.get(key) for key in ('discount_amount','memo')}
        self.loading=False; self.status.setText(f"{sale['sale_no']} | {sale['document_status']}")
        active=sale['document_status']=='CONFIRMED'; self.btn_save.setEnabled(active); self.btn_cancel.setEnabled(active)
        self.recalculate(); self.refresh_summary()

    def new_sale(self):
        self.sale_id=None; self.original={}; self.header_memo=None; self.table.setRowCount(0); self.line_extras=[]; self.reason.clear(); self.status.setText('신규 전표'); self.btn_save.setEnabled(True); self.btn_cancel.setEnabled(False)
        self.load_options()

    def remove_row(self):
        row=self.table.currentRow()
        if row<0: return
        self.table.removeRow(row); self.line_extras.pop(row)
        for r in range(self.table.rowCount()):
            combo=self.table.cellWidget(r,0); combo.currentIndexChanged.disconnect(); combo.currentIndexChanged.connect(lambda _,row=r:self.fill_lot(row))
        self.recalculate()
