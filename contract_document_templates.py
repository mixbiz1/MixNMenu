"""Five user supplied contract forms. Mapping is separate from the HTML templates.

Contract prices are KRW/kg. An unknown USD offer is deliberately left blank;
no sample company's bank, signature, price, or invoice is used as actual data.
"""
from datetime import date
from decimal import Decimal, ROUND_CEILING
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re

REVISION = '20261008.v1'
FORMS = {
    'IMPORT_AGENCY': ('수입대행계약서', 'IMPORT_AGENCY', 'import_agency.html'),
    'BL_TRANSFER': ('BL양수도 기본계약서', 'BL_TRANSFER', 'bl_transfer.html'),
    'BL_TRANSFER_TAX': ('BL양수도계약서 — 세무사용', 'BL_TRANSFER', 'bl_transfer_tax.html'),
    'BL_TRANSFER_CUSTOMS': ('BL양수도계약서 — 관세사용', 'BL_TRANSFER', 'bl_transfer_customs.html'),
    'DOMESTIC_PURCHASE': ('국내매입계약서', 'DOMESTIC_PURCHASE', 'domestic_purchase.html'),
}
TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates' / 'contracts'
BLANK = '________'


def text(value):
    return escape(str(value)) if value is not None and str(value).strip() else BLANK


def number(value, places=2):
    if value is None: return BLANK
    return f'{Decimal(str(value)):,.{places}f}'


def rate(value):
    return number(value) + '%' if value is not None else BLANK


def difference(first, second):
    if first is None or second is None: return BLANK
    return rate(Decimal(str(second)) - Decimal(str(first)))


def party_block(party, signature=False):
    address = ' '.join(str(party.get(k) or '') for k in ['address','address_detail']).strip()
    lines = ['사업자등록번호: ' + text(party.get('biz_no')), text(party.get('name')),
             text(address), '대표이사 ' + text(party.get('ceo_name'))]
    return '<br/>'.join(lines) + ('　(인)<br/><br/>' if signature else '')


def active_term(contract):
    day = str(contract.get('contract_date') or '')[:10]
    terms = [t for t in contract.get('terms', []) if str(t['effective_from'])[:10] <= day]
    return max(terms, key=lambda t: (str(t['effective_from']), t['version'])) if terms else {}


def contract_amount(items):
    if not items or any(i.get('contract_unit_price') is None for i in items): return None
    return sum(((Decimal(str(i['contract_weight'])) * Decimal(str(i['contract_unit_price']))).quantize(
                Decimal(1), rounding=ROUND_CEILING) for i in items), Decimal(0))


def goods_rows(source, domestic=False):
    rows = []
    for item in source['contract']['items']:
        metadata = source.get('document_goods', {}).get(str(item['contract_item_id']), {})
        quantity = number(item['contract_weight'])
        if not domestic: quantity += '<br/>' + number(item['contract_box_qty'], 0) + ' BOX'
        cells = [text(item.get('product_name')), text(metadata.get('origin'))]
        if domestic:
            cells += [number(item['contract_box_qty'],0), quantity, number(item.get('contract_unit_price'),0),
                      number(contract_amount([item]),0), text(metadata.get('bl_no'))]
        else:
            # No currency in the Phase 1 KRW price. Never label it as a USD offer.
            cells += [quantity, BLANK, BLANK, text(metadata.get('invoice_reference'))]
        cells += [text(metadata.get('warehouse_name'))]
        rows.append('<tr>' + ''.join('<td>' + cell + '</td>' for cell in cells) + '</tr>')
    return ''.join(rows)


def extras(source, term):
    """Human labels only. Arbitrary condition keys/objects are not legal prose."""
    contract = source['contract']; lines = []
    conditions = term.get('conditions') or {}
    codes = {'INOUT':'입출고비','INBOUND_OUTBOUND':'입출고비','WEIGHING':'계근비','WORK':'작업비','INSPECTION':'검역비','OTHER':'기타비용','STORAGE':'창고료','BROKERAGE':'중개수수료'}
    bases = {'KG':'Kg','KG_DAY':'Kg·일','BOX':'Box','SHIPMENT':'건','FLAT':'정액','PERCENT':'%'}
    taxes = {'TAXABLE':'부가세 별도','EXEMPT':'면세','INCLUDED':'부가세 포함'}
    payers = {'MXMN':'판매사','ORIGINAL_CONTRACTOR':'고객사','ACTUAL_SHIPPER':'출고업체','CONTRACTOR':'고객사','SHIPPER':'출고업체','SUPPLIER':'공급업체'}
    expense_rows = conditions.get('expense_conditions', [])
    if term.get('storage_rate_per_kg_day') is not None and not any(row.get('code') == 'STORAGE' for row in expense_rows):
        lines.append('창고료 기준: ' + number(term['storage_rate_per_kg_day']) + '원/Kg·일')
    for row in expense_rows:
        if not isinstance(row,dict) or row.get('code') not in codes: continue
        if row['code'] == 'BROKERAGE':
            lines.append('중개수수료 부담: ' + payers.get(row.get('payer'), BLANK))
            continue
        value = row.get('unit_rate')
        if value is None: continue
        label = codes[row['code']] + ': ' + number(value) + '원/' + bases.get(row.get('basis'), BLANK)
        label += ' / ' + taxes.get(row.get('tax_treatment'), BLANK) + ' / 부담: ' + payers.get(row.get('payer'), BLANK)
        if row.get('memo'): label += ' / ' + str(row['memo'])
        lines.append(label)
    for key, label in [('inbound_outbound_rate_per_kg','입출고비'),('weighing_rate_per_box','계근비')]:
        codes_for_rate = {'INOUT','INBOUND_OUTBOUND'} if key.endswith('kg') else {'WEIGHING'}
        if any(row.get('code') in codes_for_rate for row in expense_rows): continue
        if term.get(key) not in {None,0,Decimal(0)}:
            lines.append(label + ': ' + number(term[key]) + ('원/Kg' if key.endswith('kg') else '원/Box'))
    recovery = {'ALL_IN':'모두포함형','EXCLUDE_BROKERAGE':'중개수수료 제외형','EXCLUDE_BROKERAGE_STORAGE':'중개수수료·창고료 제외형',
                'INTEREST_ONLY':'이자형','COST_ONLY':'원가형','FREE':'자유형'}
    if term.get('recovery_template') in recovery: lines.append('회수유형: ' + recovery[term['recovery_template']])
    if term.get('interest_period_days_1') is not None: lines.append('1차 이자 적용기간: ' + str(term['interest_period_days_1']) + '일')
    if term.get('interest_period_days_2') is not None: lines.append('2차 이자 적용기간: ' + str(term['interest_period_days_2']) + '일')
    if contract.get('memo'): lines.append('특약사항: ' + str(contract['memo']))
    if contract.get('deposit_required'):
        lines.append('계약 보증금: ' + number(contract.get('deposit_amount'),0) + '원')
        if contract.get('deposit_memo'): lines.append(str(contract['deposit_memo']))
    for item in contract['items']:
        if item.get('memo'): lines.append(str(item.get('product_name') or '') + ': ' + str(item['memo']))
    for participant in contract.get('participants', []):
        if participant.get('role') == 'AUTHORIZED_SHIPPER' and participant.get('status') == 'ACTIVE':
            lines.append('추가 출고업체: ' + str(participant.get('account_name') or BLANK))
            if participant.get('memo'): lines.append(str(participant['memo']))
    return '<p>' + '<br/>'.join(text(x) for x in lines) + '</p>' if lines else ''


def render(source, form):
    if form not in FORMS: raise ValueError('지원하지 않는 계약서 양식입니다.')
    contract = source['contract']; term = active_term(contract)
    initial_interest = term.get('interest_rate_1')
    if initial_interest is None: initial_interest = term.get('annual_interest_rate')
    brokerage = term.get('brokerage_rate_1')
    if brokerage is None: brokerage = term.get('brokerage_rate')
    day = date.fromisoformat(str(contract['contract_date'])[:10])
    items = contract['items']; metadata = source.get('document_goods', {})
    distinct = lambda key: ' / '.join(dict.fromkeys(str(x[key]) for x in metadata.values() if x.get(key)))
    values = {
        'contract_no':text(contract['contract_no']), 'company_name':text(source['company']['name']),
        'partner_name':text(source['partner']['name']), 'company_party':party_block(source['company']),
        'partner_party':party_block(source['partner']), 'company_signature':party_block(source['company'],True),
        'partner_signature':party_block(source['partner'],True), 'contract_date':day.isoformat(),
        'contract_date_ko':f'{day.year}년 {day.month:02d}월 {day.day:02d}일',
        'goods_rows':goods_rows(source,form=='DOMESTIC_PURCHASE'),
        'product_names':text(' / '.join(i.get('product_name') or BLANK for i in items)),
        'bl_no':text(distinct('bl_no')), 'container_no':text(distinct('container_no')),
        'total_box':number(sum(i['contract_box_qty'] for i in items),0),
        'total_kg':number(sum(Decimal(str(i['contract_weight'])) for i in items)),
        'transfer_amount':number(contract_amount(items),0), 'brokerage_1':rate(brokerage),
        'brokerage_2':rate(term.get('brokerage_rate_2')), 'brokerage_increment':difference(brokerage,term.get('brokerage_rate_2')),
        'interest_1':rate(initial_interest), 'interest_2':rate(term.get('interest_rate_2')),
        'interest_increment':difference(initial_interest,term.get('interest_rate_2')),
        'contract_days':text(term.get('contract_days')), 'bank_account':text(source['company'].get('bank1')),
        'extras':extras(source,term),
    }
    brokerage_condition = next((row for row in (term.get('conditions') or {}).get('expense_conditions', [])
                                if row.get('code') == 'BROKERAGE'), {})
    values['brokerage_tax'] = {'TAXABLE':'VAT별도','EXEMPT':'면세'}.get(
        brokerage_condition.get('tax_treatment'), BLANK)
    body = (TEMPLATE_DIR / FORMS[form][2]).read_text(encoding='utf-8')
    body = re.sub(r'\{\{(\w+)\}\}',lambda match:values[match[1]],body)
    style = CSS
    if form in {'BL_TRANSFER_TAX','BL_TRANSFER_CUSTOMS'}:
        style += 'body { font-size:11pt; } td, th { padding:8px; } p { margin-top:12px; margin-bottom:12px; }'
    return '<html><head><style>' + style + '</style></head><body>' + body + '</body></html>'


CSS = '''body { font-size:9pt; } h1 { font-size:15pt; text-align:center; margin-bottom:14px; }
h2 { font-size:11pt; text-align:center; } p { margin-top:4px; margin-bottom:4px; }
td, th { padding:4px; } th { font-weight:normal; } .goods { border-collapse:collapse; }
.goods td, .goods th { border:1px solid black; } .signature td { vertical-align:top; }
'''


class SafeDocumentParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag not in {'html','head','meta','style','body','p','br','span','div','h1','h2','h3','b','i','u','strong','em',
                       'table','thead','tbody','tfoot','tr','td','th','font','a','hr','ol','ul','li','sub','sup'}:
            raise ValueError('계약서에는 텍스트와 표만 저장할 수 있습니다.')
        for key, value in attrs:
            if key.lower().startswith('on') or key.lower() in {'src','href','background'}:
                raise ValueError('계약서에는 외부 링크·이미지를 포함할 수 없습니다.')
            if value and re.search(r'url\s*\(',value,re.I): raise ValueError('외부 리소스를 포함할 수 없습니다.')


def is_html(body):
    return bool(re.match(r'\s*(?:<!DOCTYPE[^>]*>\s*)?<html\b',body,re.I))


def validate_html(body):
    parser=SafeDocumentParser(); parser.feed(body)
    if re.search(r'@import|url\s*\(',body,re.I): raise ValueError('외부 리소스를 포함할 수 없습니다.')
