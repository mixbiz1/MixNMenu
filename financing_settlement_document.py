"""A4 multipage financing reconciliation and independent deposit output."""
from decimal import Decimal
from html import escape
from pathlib import Path
import tempfile
import os
from trade_statement_document import korean_font_family


def text(value):return escape(str(value if value is not None else ''))
def number(value):return format(Decimal(str(value or 0)),',.2f').rstrip('0').rstrip('.')
def table(headers,rows):
    return '<table width="100%" border="1" cellspacing="0"><thead><tr>'+''.join('<th>'+text(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+text(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def html(title,body):return '<html><head><meta charset="utf-8"/><style>body{font-size:9pt;}td,th{padding:4px;}h1{font-size:20pt;}p{margin-top:6px;margin-bottom:6px;}</style></head><body><h1>'+text(title)+'</h1>'+body+'</body></html>'


def closure_html(snapshot,status='PREVIEW'):
    state='최종 마감 Snapshot' if status=='CLOSED' else '미마감 대사 미리보기'
    rows=[[x['lot_code'],x['assigned_box'],number(x['assigned_weight']),x['shipped_box'],number(x['shipped_weight']),x['remaining_box'],number(x['remaining_weight'])] for x in snapshot['lots']]
    sources=[[{'SALE':'상품매출','FINANCING_CHARGE':'별도비용'}.get(x['source_type'],x['source_type']),x['source_id'],number(x['amount']),number(x['settled']),number(x['remaining'])] for x in snapshot['receivables']]
    deposits=[[x['deposit_id'],x['assignment_id'],number(x['amount']),number(x['applied']),number(x['remaining'])] for x in snapshot['deposit_assignments']]
    from financing_release_document import LABELS
    components=' / '.join(text(LABELS.get(k,k))+' '+text(number(v))+'원' for k,v in snapshot['components'].items())
    body=f"<p><b>{text(state)}</b><br/>계약: {text(snapshot['contract_no'])}<br/>당사: {text(snapshot.get('company',{}).get('name'))} / 계약업체: {text(snapshot.get('contractor',{}).get('name'))}<br/>실제 출고업체: {text(' / '.join(snapshot.get('shippers',[])))}<br/>상품 청구액/원가 항목과 별도비용은 아래 구분 기준입니다.</p>"
    body+=table(['LOT','배정 BOX','배정 KG','출고 BOX','출고 KG','잔 BOX','잔 KG'],rows)
    body+='<h3>원가 및 정산항목</h3><p>'+components+'</p>'
    fees=snapshot['separate_charge_totals']
    body+=f"<p>별도비용 공급가액 {text(number(fees['supply_amount']))}원 / 세액 {text(number(fees['tax_amount']))}원 / 합계 {text(number(fees['total_amount']))}원</p>"
    body+=table(['채권유형','원전표 ID','청구액','반제액','미수잔액'],sources)
    body+=f"<p><b>전체 청구액 {text(number(snapshot['billed_amount']))}원 / 반제액 {text(number(snapshot['settled_amount']))}원 / 미수 {text(number(snapshot['remaining_receivable']))}원</b></p>"
    body+='<h3>보증금 배정/충당</h3>'+table(['보증금 ID','배정 ID','배정액','충당액','배정잔액'],deposits)
    body+='<h3>마감 차단사항</h3><p>'+text(' / '.join(snapshot['issues']) or '전산 대사 차단사항 없음')+'</p>'
    review=snapshot.get('review') or {}
    body+='<p>검토근거: '+text(review.get('review_reference') or '은행/미청구비용 별도 확인 필요')+'<br/>마감일: '+text(review.get('closed_on') or '-')+'</p>'
    body+='<p>일반 미수/미지급과 보증금 잔액은 구분됩니다. 타법인 증빙 및 계약 귀속이 불명확한 초과입금은 검토근거로 확인합니다.</p>'
    return html('Financing 최종정산내역',body)


def deposit_html(deposit):
    body=f"<p>보증금 ID {text(deposit['deposit_id'])} / {text(deposit['status'])}<br/>소유업체: {text(deposit['account_name'])}<br/>실수취일: {text(deposit['received_on'])} / 은행근거: {text(deposit['bank_reference'])}</p>"
    body+='<p>'+ ' / '.join(text(label)+' '+text(number(deposit[key]))+'원' for label,key in [('실수취','received_amount'),('충당','applied_amount'),('반환','returned_amount'),('잔액','balance'),('미배정','unassigned_amount')])+'</p>'
    body+='<h3>계약 배정</h3>'+table(['배정 ID','계약 ID','배정일','금액','상태'],[[x['assignment_id'],x['contract_id'],x['assigned_on'],number(x['amount']),x['status']] for x in deposit['assignments']])
    body+='<h3>충당/반환 이력</h3>'+table(['이동 ID','유형','요청 ID','일자','금액','상태'],[[x['movement_id'],{'APPLY':'충당','RETURN':'반환'}.get(x['kind'],x['kind']),x.get('release_id') or '-',x['movement_date'],number(x['amount']),x['status']] for x in deposit['movements']])
    body+='<p>보증금 실수취는 일반 RECEIPT FIFO에서 제외되며, 충당은 지정 출고채권에 한 번만 반영됩니다.<br/>이 문서는 현재 독립 보증금 원장 조회이며 은행잔고/입금영수증/세금계산서가 아닙니다.</p>'
    return html('Financing 보증금 원장',body)


def export_html_pdf(content,filename):
    from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QTextDocument,QFont
    from PySide6.QtCore import QMarginsF
    family=korean_font_family();destination=Path(filename)
    fd,temporary=tempfile.mkstemp(suffix='.pdf',dir=destination.parent);os.close(fd)
    try:
        writer=QPdfWriter(temporary)
        try:
            writer.setResolution(300);writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4),QPageLayout.Portrait,QMarginsF(12,12,12,12)))
            document=QTextDocument();document.setDefaultFont(QFont(family,9));document.setHtml(content);document.print_(writer)
        finally:del writer
        if not Path(temporary).read_bytes().startswith(b'%PDF-'):raise RuntimeError('Financing PDF 생성 실패')
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def export_closure_pdf(snapshot,filename,status='PREVIEW'):export_html_pdf(closure_html(snapshot,status),filename)
def export_deposit_pdf(deposit,filename):export_html_pdf(deposit_html(deposit),filename)
