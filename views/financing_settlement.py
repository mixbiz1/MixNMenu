"""Deposit and final-close screens over existing shared Qt workflow UX."""
import json
from uuid import uuid4
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit,QCheckBox,QComboBox,QFileDialog,QTableWidgetItem,QHBoxLayout
from views.financing_intake import WorkWindow,line


class FinancingDepositWindow(WorkWindow):
    resource='financing-deposits';menu='FINANCING_DEPOSIT';pk='deposit_id'
    def __init__(self):
        super().__init__();self.request_key=uuid4().hex
        self.account=line();self.day=line('yyyy-MM-dd');self.amount=line('실수취/배정/충당/반환 금액(원)')
        self.reference=line('은행 거래 고유식별근거');self.reason=line('상계/반환/취소 합의 근거')
        self.contract=line();self.release=line();self.assignment=QComboBox();self.movement=QComboBox()
        self.form.addRow('보증금 소유업체',self.picker(self.account,self.pick_account))
        self.form.addRow('업무일',self.day);self.form.addRow('금액',self.amount);self.form.addRow('은행 거래근거',self.reference)
        self.form.addRow('배정 계약',self.picker(self.contract,self.pick_contract));self.form.addRow('출고정산',self.picker(self.release,self.pick_release))
        self.form.addRow('배정 선택',self.assignment);self.form.addRow('충당 이동 선택',self.movement);self.form.addRow('사유',self.reason)
        self.result=QPlainTextEdit();self.result.setReadOnly(True);self.form.addRow('독립 보증금 원장',self.result)
        self.add_button('실수취 등록',self.receive,'create');self.add_button('계약 배정',self.assign,'update')
        self.add_button('담보해제',self.unassign,'update');self.add_button('출고정산 충당',self.apply,'update')
        self.buttons=QHBoxLayout();self.root.addLayout(self.buttons)
        self.add_button('실제 반환',self.give_back,'update');self.add_button('미출고 충당 취소',self.cancel_movement,'update')
        self.add_button('수취 정정취소',self.cancel_root,'update');self.add_button('보증금 PDF',self.export_pdf)
        self.table.setHorizontalHeaderLabels(['보증금 ID','상태','소유업체','미충당 잔액'])
        self.run(self.refresh)
    def refresh(self):
        self.rows=self.request('get');self.table.blockSignals(True);self.table.setRowCount(0)
        try:
            for row in self.rows:
                i=self.table.rowCount();self.table.insertRow(i)
                for col,value in enumerate([row['deposit_id'],row['status'],row['account_name'],row['balance']]):self.table.setItem(i,col,QTableWidgetItem(str(value)))
                self.table.item(i,0).setData(Qt.UserRole,row['deposit_id'])
        finally:self.table.blockSignals(False)
    def pick_account(self):self.pick(self.account,'accounts','보증금 소유업체',[('업체','account_name'),('사업자번호','biz_no')],'account_id','account_name',{'purpose':'CONTRACT'})
    def pick_contract(self):self.pick(self.contract,'financing-contracts','확정/진행 계약',[('계약번호','contract_no'),('업체','contractor_name'),('상태','status')],'contract_id','contract_no')
    def pick_release(self):self.pick(self.release,'financing-releases','충당할 확정 요청',[('요청 ID','release_id'),('상태','status'),('계약 ID','contract_id'),('금액','total_amount')],'release_id','release_id',{'contract_id':self.contract.property('pk')} if self.contract.property('pk') else None)
    def require(self):
        if not self.current:raise ValueError('실수취 보증금을 먼저 선택하십시오.')
        return self.current['deposit_id']
    def reload(self,identity):self.refresh();self.load(self.request('get',f'/{identity}'))
    def receive(self):
        if self.current:raise ValueError('새 입력에서 실제 은행수취를 등록하십시오.')
        row=self.request('post',json={'account_id':self.account.property('pk'),'received_on':self.day.text(),'amount':int(self.amount.text()),
            'bank_reference':self.reference.text(),'request_key':self.request_key});self.reload(row['deposit_id'])
    def assign(self):
        identity=self.require();self.request('post',f'/{identity}/assign',json={'contract_id':self.contract.property('pk'),'assigned_on':self.day.text(),'amount':int(self.amount.text()),'request_key':uuid4().hex});self.reload(identity)
    def unassign(self):
        identity=self.require();assignment=self.assignment.currentData()
        if not assignment:raise ValueError('배정행을 선택하십시오.')
        self.request('post',f'/{identity}/assignments/{assignment}/cancel',json={'reason':self.reason.text()});self.reload(identity)
    def apply(self):
        identity=self.require();self.request('post',f'/{identity}/apply',json={'assignment_id':self.assignment.currentData(),'release_id':self.release.property('pk'),
            'movement_date':self.day.text(),'amount':int(self.amount.text()),'request_key':uuid4().hex,'reason':self.reason.text()});self.reload(identity)
    def give_back(self):
        identity=self.require();self.request('post',f'/{identity}/return',json={'movement_date':self.day.text(),'amount':int(self.amount.text()),
            'request_key':uuid4().hex,'reason':self.reason.text(),'bank_reference':self.reference.text()});self.reload(identity)
    def cancel_movement(self):
        identity=self.require();movement=self.movement.currentData()
        if not movement:raise ValueError('충당 이동을 선택하십시오.')
        self.request('post',f'/{identity}/movements/{movement}/cancel',json={'reason':self.reason.text()});self.reload(identity)
    def cancel_root(self):
        identity=self.require();self.request('post',f'/{identity}/cancel',json={'reason':self.reason.text()});self.reload(identity)
    def load(self,row):
        super().load(row);self.account.setProperty('pk',row['account_id']);self.account.setText(row['account_name']);self.assignment.clear();self.movement.clear()
        for assignment in row['assignments']:
            if assignment['status']=='ACTIVE':self.assignment.addItem(f"{assignment['assignment_id']} / 계약 {assignment['contract_id']} / 배정 {assignment['amount']}원",assignment['assignment_id'])
        for movement in row['movements']:
            if movement['status']=='CONFIRMED' and movement['kind']=='APPLY':self.movement.addItem(f"{movement['movement_id']} / 요청 {movement['release_id']} / {movement['amount']}원",movement['movement_id'])
        lines=[f"실수취 {row['received_amount']}원 / 충당 {row['applied_amount']}원 / 반환 {row['returned_amount']}원",
               f"잔액 {row['balance']}원 / 미배정 {row['unassigned_amount']}원"]
        lines += [f"배정 {x['assignment_id']} / 계약 {x['contract_id']} / {x['assigned_on']} / {x['amount']}원 / {x['status']}" for x in row['assignments']]
        lines += [f"이동 {x['movement_id']} / {'충당' if x['kind']=='APPLY' else '반환'} / 출고정산 {x.get('release_id') or '-'} / {x['movement_date']} / {x['amount']}원 / {x['status']}" for x in row['movements']]
        self.result.setPlainText('\n'.join(lines))
    def open_source_id(self,identity):self.load(self.request('get',f'/{identity}'))
    def clear(self):
        super().clear();self.request_key=uuid4().hex
        for field in [self.account,self.day,self.amount,self.reference,self.reason,self.contract,self.release]:field.clear();field.setProperty('pk',None)
        self.assignment.clear();self.movement.clear();self.result.clear()
    def export_pdf(self):
        identity=self.require();row=self.request('get',f'/{identity}')
        filename,_=QFileDialog.getSaveFileName(self,'보증금 원장 PDF',f'보증금_{identity}.pdf','PDF (*.pdf)')
        if filename:
            from financing_settlement_document import export_deposit_pdf
            export_deposit_pdf(row,filename)


class FinancingClosureWindow(WorkWindow):
    resource='financing-closures';menu='FINANCING_CLOSE';pk='closure_id'
    def __init__(self):
        super().__init__();self.reconciliation=None;self.contract=line();self.day=line('yyyy-MM-dd')
        self.reason=line('최종 마감사유');self.reference=line('최종 대사/별도증빙 확인근거')
        self.cost_review=QCheckBox('미청구 비용/타법인 증빙 대사 완료');self.bank_review=QCheckBox('은행입금/초과입금 귀속 확인 완료')
        self.form.addRow('마감 계약',self.picker(self.contract,self.pick_contract));self.form.addRow('마감일',self.day)
        self.form.addRow('검토근거',self.reference);self.form.addRow('사유',self.reason);self.form.addRow(self.cost_review);self.form.addRow(self.bank_review)
        self.result=QPlainTextEdit();self.result.setReadOnly(True);self.form.addRow('최종 대사 / 마감차단 항목',self.result)
        self.add_button('계약 대사 조회',self.reconcile);self.add_button('최종 CLOSED',self.close_contract,'update');self.add_button('최종정산 PDF',self.export_pdf)
        self.run(self.refresh)
    def refresh(self):
        self.rows=self.request('get');self.table.blockSignals(True);self.table.setRowCount(0)
        try:
            for row in self.rows:
                i=self.table.rowCount();self.table.insertRow(i)
                for col,value in enumerate([row['closure_id'],'CLOSED',row['closed_on'],row['contract_id']]):self.table.setItem(i,col,QTableWidgetItem(str(value)))
                self.table.item(i,0).setData(Qt.UserRole,row['closure_id'])
        finally:self.table.blockSignals(False)
    def pick_contract(self):
        self.pick(self.contract,'financing-contracts','마감 대상 계약',[('계약번호','contract_no'),('업체','contractor_name'),('상태','status')],'contract_id','contract_no')
        self.current=None;self.cost_review.setChecked(False);self.bank_review.setChecked(False);self.reconcile()
    def reconcile(self):
        identity=self.contract.property('pk')
        if not identity:raise ValueError('대사할 계약을 선택하십시오.')
        self.reconciliation=self.request('get',f'/contracts/{identity}')
        self.result.setPlainText(self.format_result(self.reconciliation))
    def close_contract(self):
        identity=self.contract.property('pk')
        if not identity:raise ValueError('마감할 계약을 선택하십시오.')
        row=self.request('post',f'/contracts/{identity}/close',json={'closed_on':self.day.text(),'reason':self.reason.text(),
            'unbilled_costs_reviewed':self.cost_review.isChecked(),'bank_and_overpayments_reviewed':self.bank_review.isChecked(),'review_reference':self.reference.text()})
        self.refresh();self.load(row)
    def load(self,row):
        self.current=row;self.reconciliation=row['snapshot'];self.contract.setProperty('pk',row['contract_id']);self.contract.setText(row['snapshot']['contract_no'])
        self.day.setText(row['closed_on']);self.summary.setText(f"계약 CLOSED / 마감 ID {row['closure_id']}")
        self.result.setPlainText(self.format_result(row['snapshot']))
    def format_result(self,data):
        from financing_release_document import LABELS
        lines=[f"계약 {data['contract_no']} / 청구 {data['billed_amount']}원 / 반제 {data['settled_amount']}원 / 미수 {data['remaining_receivable']}원",
               ' / '.join(f"{LABELS.get(key,key)} {value}원" for key,value in data['components'].items())]
        lines += [f"LOT {x['lot_code']} / 배정 {x['assigned_box']} Box {x['assigned_weight']} Kg / 출고 {x['shipped_box']} Box {x['shipped_weight']} Kg / 잔량 {x['remaining_box']} Box {x['remaining_weight']} Kg" for x in data['lots']]
        lines += [f"보증금 배정 {x['assignment_id']} / 배정 {x['amount']}원 / 충당 {x['applied']}원 / 잔액 {x['remaining']}원" for x in data['deposit_assignments']]
        lines += ['마감 차단: '+issue for issue in data['issues']]
        if not data['issues']:lines.append('전산 대사 정상. 은행/초과입금 및 미청구 비용을 별도로 확인하십시오.')
        return '\n'.join(lines)
    def clear(self):
        super().clear();self.reconciliation=None
        for field in [self.contract,self.day,self.reason,self.reference]:field.clear();field.setProperty('pk',None)
        self.cost_review.setChecked(False);self.bank_review.setChecked(False);self.result.clear()
    def export_pdf(self):
        if self.current:source=self.request('get',f"/{self.current['closure_id']}")['snapshot'];status='CLOSED'
        else:
            self.reconcile();source=self.reconciliation;status='PREVIEW'
        filename,_=QFileDialog.getSaveFileName(self,'최종정산 PDF','최종정산.pdf','PDF (*.pdf)')
        if filename:
            from financing_settlement_document import export_closure_pdf
            export_closure_pdf(source,filename,status)
