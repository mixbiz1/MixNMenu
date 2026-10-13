"""Payment request output from the stored release snapshot, no ledger writes."""
from decimal import Decimal
from html import escape
from pathlib import Path
import os
import tempfile
from trade_statement_document import korean_font_family

LABELS={'COST':'원가','INTEREST':'이자','STORAGE':'창고료','INOUT':'입출고비','WEIGHING':'계근비','BROKERAGE':'수수료'}


def request_html(release):
    snapshot=release['snapshot']
    text=lambda value:escape(str(value if value is not None else ''))
    number=lambda value:format(Decimal(str(value or 0)),',.2f').rstrip('0').rstrip('.')
    if release['status'] not in {'DRAFT','CONFIRMED','PAID','SHIPPED','CANCELLED'}:
        raise ValueError('입금요청 상태를 확인하십시오.')
    status={'DRAFT':'초안 / 검토용','CONFIRMED':'확정 입금요청','PAID':'입금확인 완료 / 원요청 재출력',
            'SHIPPED':'출고 완료 / 원요청 재출력','CANCELLED':'취소된 입금요청'}[release['status']]
    rows=[];details=[]
    for i,item in enumerate(snapshot['lines'],1):
        prepared=snapshot['prepared_lines'][i-1]
        values=[i,item['product_name'],item['lot_code'],number(item['box_qty']),number(item['weight']),
                number(prepared['supply_amount']),number(prepared['tax_amount']),number(prepared['total_amount'])]
        rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
        components=' / '.join(f'{LABELS.get(key,key)} {number(value)}원' for key,value in item['components'].items())
        details.append(f"<p><b>{text(item['lot_code'])}</b>: {text(components)}<br/>가격조정 {text(number(item['adjustment']))}원 / 단가 올림차이 {text(number(item['rounding_difference']))}원<br/>조정근거: {text(item.get('adjustment_reason') or '-')}</p>")
    separate=snapshot.get('separate_charges',[])
    separate_html=''
    if separate:
        from financing_settlement_document import table
        separate_html='<h3>별도청구 내역 - 상품 입금요청액에서 제외</h3>'+table(
            ['항목','청구법인','증빙대상','공급가액','세액','합계'],
            [[x['name'],x['issuer_comp_code'],{'TAX_INVOICE':'세금계산서 발행대상','INVOICE':'계산서 발행대상'}.get(x['evidence_type'],x['evidence_type']),number(x['supply_amount']),number(x['tax_amount']),number(x['total_amount'])] for x in separate])
    funding=release.get('funding') or {}
    funding_html=''
    if funding.get('deposit_applied'):
        funding_html=f"<p>현재 보증금 충당 {text(number(funding['deposit_applied']))}원 / 실제 은행 확인 필요액 {text(number(funding['cash_required']))}원<br/>충당 이동은 독립 원장에 보존되며 원 정산 Snapshot 금액을 변경하지 않습니다.</p>"
    totals=snapshot['totals'];company=snapshot['source']['company'];bank=snapshot.get('bank_account')
    return f'''<html><head><meta charset="utf-8"/><style>
    body {{font-size:9pt;}} h1 {{font-size:20pt;}} td,th {{padding:4px;}} p {{margin-top:6px;margin-bottom:6px;}}
    </style></head><body><h1>입금요청서</h1><p><b>{text(status)}</b><br/>
    요청번호: {text(release['release_id'])} / 계약번호: {text(snapshot['source']['contract']['contract_no'])}<br/>
    출고예정일: {text(release['release_date'])} / 이자기산일: {text(snapshot['accrual_start'])}</p>
    <p>요청업체: {text(company.get('name'))} / 사업자번호: {text(company.get('biz_no'))}<br/>
    계약업체: {text(snapshot['source']['partner'].get('name'))}<br/>
    실제 출고업체 / 입금자: <b>{text(snapshot['shipper']['name'])}</b></p>
    <table width="100%" border="1" cellspacing="0"><thead><tr>
    {''.join('<th>'+x+'</th>' for x in ['순번','상품','LOT','BOX','KG','공급가액','세액','합계'])}
    </tr></thead><tbody>{''.join(rows)}</tbody></table>
    <p>공급가액 {text(number(totals['total_supply_amount']))}원 / 세액 {text(number(totals['total_tax_amount']))}원<br/>
    <b>원 입금요청액: {text(number(release['total_amount']))}원</b><br/>
    입금계좌: {text(bank or '미입력 - 확정용 출력 불가')}</p>
    {funding_html}{separate_html}<h3>정산항목 및 근거</h3>{''.join(details)}
    <p>세무구분은 저장된 매출 정산항목 기준입니다. 상품가격은 면세상품/면세 포함비용이며 과세/면세 별도비용은 위에 구분합니다.<br/>
    본 문서는 계산서/세금계산서 또는 입금영수증이 아닙니다. 기수금/잔여미수는 거래처원장으로 확인하십시오.<br/>
    확정 정산 Snapshot을 재출력하며 현재 Master 변경으로 재계산하지 않습니다.</p></body></html>'''


def export_request_pdf(release,filename):
    from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QTextDocument,QFont
    from PySide6.QtCore import QMarginsF
    family=korean_font_family()
    if release['status'] not in {'DRAFT','CANCELLED'} and not (release['snapshot'].get('bank_account') or '').strip():
        raise ValueError('저장된 입금계좌가 없습니다. 기존 Snapshot을 수정하지 말고 새 정산으로 확인하십시오.')
    html=request_html(release);destination=Path(filename)
    fd,temporary=tempfile.mkstemp(suffix='.pdf',dir=destination.parent);os.close(fd)
    try:
        writer=QPdfWriter(temporary)
        try:
            writer.setResolution(300)
            writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4),QPageLayout.Portrait,QMarginsF(12,12,12,12)))
            document=QTextDocument();document.setDefaultFont(QFont(family,9));document.setHtml(html)
            document.print_(writer)
        finally:del writer
        if not Path(temporary).read_bytes().startswith(b'%PDF-'):raise RuntimeError('입금요청서 PDF 생성 실패')
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
