"""A single work screen: contract -> saved quote -> bank check -> ERP sale."""
from uuid import uuid4
from PySide6.QtWidgets import QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox
from PySide6.QtCore import Qt
from views.financing_intake import WorkWindow,line
from app_context import app_context

class FinancingReleaseWindow(WorkWindow):
    resource='financing-releases';menu='FINANCING_RELEASE';pk='release_id'
    def __init__(self):
        super().__init__();self.request_key=uuid4().hex
        self.contract=line();self.shipper=line();self.day=line('yyyy-MM-dd');self.year_days=line('365 또는 366: 약정 기준 확인')
        self.form.addRow('계약',self.picker(self.contract,self.pick_contract))
        self.form.addRow('실제 출고업체',self.picker(self.shipper,self.pick_shipper))
        self.start=line('yyyy-MM-dd: 실제 이자 기산일');self.start_reason=line('계약 미입력/변경 기산일 근거')
        self.form.addRow('이자 기산일',self.start);self.form.addRow('기산일 근거',self.start_reason)
        self.form.addRow('출고일',self.day);self.form.addRow('연이자 기준일수',self.year_days)
        self.goods=QTableWidget(0,6);self.goods.setHorizontalHeaderLabels(['계약 LOT','Box','Kg','± 면세가격 조정(원)','조정 근거','상품'])
        self.goods.setMinimumHeight(160);self.form.addRow('부분출고 수량 (필요 행만 남김)',self.goods)
        self.add_button('선택행 제외',self.remove_line,'create')
        self.result=QPlainTextEdit();self.result.setReadOnly(True);self.result.setMinimumHeight(180)
        self.form.addRow('계산 / 입금요청 / SALE 연결',self.result)
        self.evidence=line('실제 은행입금 확인 근거');self.received=line('확인한 실제 금액(원)');self.reason=line('취소 사유')
        self.form.addRow('은행입금 근거',self.evidence);self.form.addRow('입금 확인액',self.received);self.form.addRow('사유',self.reason)
        self.add_button('출고정산 초안 생성',self.create,'create')
        self.add_button('입금요청 확정',self.confirm,'update')
        self.add_button('은행입금 확인',self.check_payment,'update')
        self.add_button('SALE / 출고 생성',self.ship,'update')
        self.add_button('취소 / 출고 복원',self.cancel,'update')
        self.add_button('연결 매출 열기',self.open_sale)
        self.run(self.refresh)
    def pick_contract(self):
        if self.current:raise ValueError('저장된 정산은 변경할 수 없습니다. 새 입력을 선택하십시오.')
        row=self.pick(self.contract,'financing-contracts','확정 계약 검색',
            [('계약번호','contract_no'),('업체','contractor_name'),('상태','status')],'contract_id','contract_no')
        if not row:return
        self.goods.setRowCount(0)
        self.shipper.setProperty('pk',row['contractor_account_id']);self.shipper.setText(row.get('contractor_name') or '')
        for link in row['lots']:
            if link['status']!='ACTIVE':continue
            index=self.goods.rowCount();self.goods.insertRow(index)
            for column,value in enumerate([link.get('lot_code') or link['lot_id'],'','','0','',link.get('product_name') or '']):
                cell=QTableWidgetItem(str(value))
                if column in {0,5}:cell.setFlags(cell.flags()&~Qt.ItemIsEditable)
                self.goods.setItem(index,column,cell)
            self.goods.item(index,0).setData(Qt.UserRole,link['lot_id'])
        self.start.setText(row.get('financing_start_date') or '')
        previous=next((x for x in self.request('get',params={'contract_id':row['contract_id']}) if x['status'] in {'CONFIRMED','PAID','SHIPPED'}),None)
        if previous:
            self.start.setText(previous['snapshot']['accrual_start'])
            self.year_days.setText(str(previous['snapshot']['input']['interest_year_days']))
            self.start_reason.setText(previous['snapshot']['input'].get('interest_start_reason') or '이전 확정 정산의 기산일 승계')
        self.request_key=uuid4().hex
        self.result.setPlainText('입금요청 확정 전 계산결과를 검토하십시오. 미지원 과세·기간·회수 조건은 서버에서 차단합니다.\n기존 초안은 취소 후 새 요청으로 정정합니다. 입금확인은 RECEIPT 등록과 별개입니다.')
    def pick_shipper(self):
        if self.current:raise ValueError('저장된 정산은 변경할 수 없습니다. 새 입력을 선택하십시오.')
        self.pick(self.shipper,'accounts','실제 출고업체 검색',[('업체','account_name'),('사업자번호','biz_no')],
                  'account_id','account_name',{'purpose':'CONTRACT'})
    def remove_line(self):
        if self.current:raise ValueError('저장된 정산은 취소 후 새 입력으로 정정하십시오.')
        if self.goods.currentRow()>=0:self.goods.removeRow(self.goods.currentRow())
    def payload(self):
        return {'contract_id':self.contract.property('pk'),'shipper_account_id':self.shipper.property('pk'),
            'release_date':self.day.text(),'interest_start_date':self.start.text() or None,'interest_start_reason':self.start_reason.text() or None,'interest_year_days':int(self.year_days.text()),'request_key':self.request_key,
            'lines':[{'lot_id':self.goods.item(i,0).data(Qt.UserRole),'box_qty':int(self.goods.item(i,1).text() or 0),
                'weight':self.goods.item(i,2).text(),'adjustment':int(self.goods.item(i,3).text() or 0),
                'adjustment_kind':'PRICE_ADJUSTMENT' if int(self.goods.item(i,3).text() or 0) else None,
                'adjustment_reason':self.goods.item(i,4).text() or None} for i in range(self.goods.rowCount())]}
    def create(self):
        if self.current:raise ValueError('기존 정산은 취소 후 새 입력으로 정정하십시오.')
        row=self.request('post',json=self.payload());self.refresh();self.load(row)
    def action(self,name,**kwargs):
        if self.current:
            row=self.request('post',f"/{self.current[self.pk]}/{name}",**kwargs);self.refresh();self.load(row)
    def confirm(self):self.action('confirm')
    def check_payment(self):self.action('payment-check',json={'reference':self.evidence.text(),'amount':int(self.received.text())})
    def ship(self):self.action('ship')
    def cancel(self):self.action('cancel',json={'reason':self.reason.text()})
    def load(self,row):
        super().load(row);snapshot=row['snapshot']
        self.contract.setProperty('pk',row['contract_id']);self.contract.setText(snapshot['source']['contract']['contract_no'])
        self.shipper.setProperty('pk',row['shipper_account_id'])
        self.shipper.setText(snapshot['shipper']['name']);self.day.setText(row['release_date'])
        self.year_days.setText(str(snapshot['input']['interest_year_days']))
        self.day.setReadOnly(True);self.year_days.setReadOnly(True)
        self.start.setText(snapshot['accrual_start']);self.start_reason.setText(snapshot['input'].get('interest_start_reason') or '')
        self.start.setReadOnly(True);self.start_reason.setReadOnly(True)
        self.goods.setRowCount(0)
        for item in snapshot['lines']:
            index=self.goods.rowCount();self.goods.insertRow(index)
            for column,value in enumerate([item['lot_code'],item['box_qty'],item['weight'],item['adjustment'],item.get('adjustment_reason') or '',item['product_name']]):
                self.goods.setItem(index,column,QTableWidgetItem(str(value)))
            self.goods.item(index,0).setData(Qt.UserRole,item['lot_id'])
        self.goods.setEditTriggers(QTableWidget.NoEditTriggers)
        self.evidence.setText(row.get('payment_evidence') or '')
        self.received.setText(str(row['total_amount']) if row.get('payment_evidence') else '')
        lines=[f"정산 {row['release_id']} / {row['status']} / 입금요청 {row['total_amount']}원 / SALE ID {row.get('sale_id') or '-'}",
               '계좌: '+str(snapshot.get('bank_account') or '미입력 — 당사 Master 확인')]
        for item in snapshot['lines']:
            lines.append(f"{item['lot_code']} {item['product_name']} / {item['box_qty']} Box / {item['weight']} Kg / {item['unit_price']}원/Kg")
            labels={'COST':'원가','INTEREST':'이자','STORAGE':'보관료','INOUT':'입출고비','WEIGHING':'계근비','BROKERAGE':'수수료'}
            lines.append(' / '.join(f"{labels[key]} {value}원" for key,value in item['components'].items()))
            lines.append(f"조정 {item['adjustment']}원 / 단가 원단위 올림 차이 {item['rounding_difference']}원")
        self.result.setPlainText('\n'.join(lines))
    def clear(self):
        super().clear();self.request_key=uuid4().hex
        for field in [self.contract,self.shipper,self.day,self.start,self.start_reason,self.year_days,self.evidence,self.received,self.reason]:field.clear();field.setProperty('pk',None)
        self.goods.setRowCount(0);self.goods.setEditTriggers(QTableWidget.DoubleClicked|QTableWidget.EditKeyPressed)
        self.day.setReadOnly(False);self.year_days.setReadOnly(False);self.start.setReadOnly(False);self.start_reason.setReadOnly(False);self.result.clear()
    def open_sale(self):
        if not self.current or not self.current.get('sale_id'):return
        # Reuse existing stable-ID drill-down entry point in the MDI owner.
        parent=self.parent()
        while parent and not hasattr(parent,'open_account_ledger_source'):parent=parent.parent()
        if hasattr(parent,'open_account_ledger_source'):parent.open_account_ledger_source('SALE',self.current['sale_id'])
        else:QMessageBox.information(self,'연결 매출',f"일반매출에서 SALE ID {self.current['sale_id']}를 조회하십시오.")


class SpecialShipperWindow(WorkWindow):
    resource='financing-special-shippers';menu='FINANCING_CONTRACT';pk='participant_id'
    def __init__(self):
        super().__init__();self.contract=line();self.account=line();self.signed=line('yyyy-MM-dd');self.effective=line('yyyy-MM-dd')
        self.reference=line('실제 서명된 특별출고약정서 번호/근거');self.reason=line('철회 사유')
        from PySide6.QtWidgets import QCheckBox
        self.joint=QCheckBox('최초 계약업체·추가 출고업체의 연대책임 약정 수취 확인')
        self.form.addRow('확정 계약',self.picker(self.contract,self.pick_contract))
        self.form.addRow('추가 출고업체',self.picker(self.account,self.pick_account))
        self.form.addRow('약정 확인일',self.signed);self.form.addRow('적용일',self.effective)
        self.form.addRow('서명 근거',self.reference);self.form.addRow(self.joint);self.form.addRow('철회 사유',self.reason)
        self.add_button('서명된 추가 약정 등록',self.create,'create')
        self.add_button('추가업체 출고권한 철회',self.revoke,'update');self.run(self.refresh)
    def pick_contract(self):
        self.pick(self.contract,'financing-contracts','확정 계약 검색',[('계약번호','contract_no'),('업체','contractor_name')],'contract_id','contract_no')
    def pick_account(self):
        self.pick(self.account,'accounts','추가 출고업체 검색',[('업체','account_name'),('사업자번호','biz_no')],'account_id','account_name',{'purpose':'CONTRACT'})
    def create(self):
        row=self.request('post',json={'contract_id':self.contract.property('pk'),'account_id':self.account.property('pk'),
            'agreement_date':self.signed.text(),'effective_date':self.effective.text(),'reference':self.reference.text(),
            'joint_liability_confirmed':self.joint.isChecked()});self.refresh();self.load(row)
    def load(self,row):
        super().load(row);self.contract.setText(row['contract_no']);self.contract.setProperty('pk',row['contract_id'])
        self.account.setText(row['account_name']);self.account.setProperty('pk',row['account_id'])
        self.signed.setText(row.get('agreement_date') or '');self.effective.setText(row.get('effective_date') or '')
        self.reference.setText(row.get('memo') or '')
    def revoke(self):
        if self.current:
            row=self.request('post',f"/{self.current[self.pk]}/revoke",json={'reason':self.reason.text()});self.refresh();self.load(row)
    def clear(self):
        super().clear()
        for field in [self.contract,self.account,self.signed,self.effective,self.reference,self.reason]:field.clear();field.setProperty('pk',None)
        self.joint.setChecked(False)
