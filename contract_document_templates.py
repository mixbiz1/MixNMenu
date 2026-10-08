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

REVISION = '20261008.v1.integrity'
FORMS = {
    'IMPORT_AGENCY': ('수입대행계약서', 'IMPORT_AGENCY', 'import_agency.html'),
    'BL_TRANSFER': ('BL양수도 기본계약서', 'BL_TRANSFER', 'bl_transfer.html'),
    'BL_TRANSFER_TAX': ('BL양수도계약서 — 세무사용', 'BL_TRANSFER', 'bl_transfer_tax.html'),
    'BL_TRANSFER_CUSTOMS': ('BL양수도계약서 — 관세사용', 'BL_TRANSFER', 'bl_transfer_customs.html'),
    'DOMESTIC_PURCHASE': ('국내매입계약서', 'DOMESTIC_PURCHASE', 'domestic_purchase.html'),
}
TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates' / 'contracts'
BLANK = '________'
RATE_INPUT_KEY = 'document_rate_inputs'
RATE_FIELDS = ('annual_interest_rate', 'brokerage_rate', 'storage_rate_per_kg_day',
               'inbound_outbound_rate_per_kg', 'weighing_rate_per_box')


def legal_name(party):
    """Do not guess a registered name by trimming an internal master label."""
    name = party.get('name')
    if name and str(name).strip().startswith('(계약)'):
        return None
    return name


def term_value(term, key):
    """Presentation only: persisted default zero is not evidence of agreement.

    Explicit expense rows and new presence metadata preserve agreed zero. Older
    unmarked flat zero cannot be reconstructed and must be reviewed, not guessed.
    """
    value = term.get(key)
    if value is None: return None
    inputs = (term.get('conditions') or {}).get(RATE_INPUT_KEY, {})
    canonical = {'interest_rate_1':'annual_interest_rate', 'brokerage_rate_1':'brokerage_rate'}.get(key,key)
    if canonical in RATE_FIELDS and Decimal(str(value)) == 0:
        if inputs.get(canonical) is not True: return None
    return value


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
    lines = ['사업자등록번호: ' + text(party.get('biz_no')), text(legal_name(party)),
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


def validation(source, form):
    """Read-only source review, separate from legal prose and manual body edits.

    Required means verify before signing, not a new contract state/approval rule.
    An edited body may supply a value absent from structured source; never parse
    that prose into financial conditions or silently certify it as reconciled.
    """
    required, optional = [], []
    contract = source.get('contract') or {}; term = active_term(contract)
    for field, label in [('contract_no','계약번호'), ('contract_date','계약일')]:
        if not contract.get(field): required.append(label)
    for key, label in [('company','당사'), ('partner','계약업체')]:
        party = source.get(key) or {}
        if not legal_name(party): required.append(label + ' 법적 상호 (Master 원본 확인 필요)')
        for field, name in [('biz_no','사업자번호'), ('ceo_name','대표자'), ('address','주소')]:
            if not party.get(field): required.append(label + ' ' + name)
    items = contract.get('items') or []
    if not items: required.append('계약상품')
    for index, item in enumerate(items, 1):
        if not item.get('product_name'): required.append(f'상품 {index} 상품명')
        if not (item.get('contract_box_qty') or Decimal(str(item.get('contract_weight') or 0))):
            required.append(f'상품 {index} Box/Kg 수량')
        if form in {'DOMESTIC_PURCHASE','BL_TRANSFER_TAX'} and item.get('contract_unit_price') is None:
            required.append(f'상품 {index} 원화 기준단가/금액')
    if form in {'BL_TRANSFER_TAX','BL_TRANSFER_CUSTOMS'}:
        metadata = source.get('document_goods') or {}
        for field, label in [('bl_no','BL 번호'), ('container_no','Container 번호')]:
            if not any(row.get(field) for row in metadata.values()): required.append(label)
    else:
        if not term: required.append('계약일 유효 조건')
        if term.get('contract_days') is None: required.append('출고약정기간 (이자 적용일수와 별도)')
        if not (source.get('company') or {}).get('bank1'): required.append('판매대금 입금계좌 (당사 bank1)')
        for first, fallback, label in [('interest_rate_1','annual_interest_rate','최초 이자율'),
                                        ('brokerage_rate_1','brokerage_rate','최초 계약수수료율')]:
            if term_value(term, first if term.get(first) is not None else fallback) is None:
                required.append(label + ' (미입력/과거 기본 0 여부 확인)')
        expenses = (term.get('conditions') or {}).get('expense_conditions', [])
        brokerage = next((x for x in expenses if x.get('code') == 'BROKERAGE'), {})
        if brokerage.get('tax_treatment') not in {'TAXABLE','EXEMPT'}:
            required.append('계약수수료 세무구분')
        if form in {'IMPORT_AGENCY','BL_TRANSFER'}:
            required.append('USD 오퍼단가/물품총액 (현재 구조화 출처 없음; KRW 대체 금지)')
            (required if contract.get('deposit_required') else optional).append(
                '보증금 비율 (약정액으로 비율 역산 금지; 구조화 출처 없음)')
        for field, codes, label in [('storage_rate_per_kg_day',{'STORAGE'},'창고료'),
                                  ('inbound_outbound_rate_per_kg',{'INOUT','INBOUND_OUTBOUND'},'입출고비'),
                                  ('weighing_rate_per_box',{'WEIGHING'},'계근비')]:
            rows = [x for x in expenses if x.get('code') in codes]
            if (rows and any(x.get('unit_rate') is None for x in rows)) or (not rows and term_value(term, field) is None):
                optional.append(label + ' (미확정; 실비/요율/0원 합의 확인)')
        for field, label in [('interest_rate_2','연장 이자율/적용조건'),
                             ('brokerage_rate_2','연장 계약수수료율')]:
            if term.get(field) is None: optional.append(label)
    return {'required': required, 'optional': optional,
            'notice':'자동승계 원본 기준 확인사항입니다. 문구에서 수동 보완한 값은 원계약 조건을 변경하지 않습니다.'}


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
    if not any(row.get('code') == 'STORAGE' for row in expense_rows):
        value = term_value(term, 'storage_rate_per_kg_day')
        lines.append('창고료 기준: ' + (number(value) + '원/Kg·일' if value is not None else '미확정'))
    for row in expense_rows:
        if not isinstance(row,dict) or row.get('code') not in codes: continue
        if row['code'] == 'BROKERAGE':
            lines.append('중개수수료 부담: ' + payers.get(row.get('payer'), BLANK))
            continue
        value = row.get('unit_rate')
        label = codes[row['code']] + ': ' + (number(value) + '원/' + bases.get(row.get('basis'), BLANK) if value is not None else '미확정')
        label += ' / ' + taxes.get(row.get('tax_treatment'), BLANK) + ' / 부담: ' + payers.get(row.get('payer'), BLANK)
        if row.get('memo'): label += ' / ' + str(row['memo'])
        lines.append(label)
    for key, label in [('inbound_outbound_rate_per_kg','입출고비'),('weighing_rate_per_box','계근비')]:
        codes_for_rate = {'INOUT','INBOUND_OUTBOUND'} if key.endswith('kg') else {'WEIGHING'}
        if any(row.get('code') in codes_for_rate for row in expense_rows): continue
        value = term_value(term, key)
        lines.append(label + ': ' + (number(value) + ('원/Kg' if key.endswith('kg') else '원/Box') if value is not None else '미확정'))
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
    initial_interest = term_value(term, 'interest_rate_1')
    if term.get('interest_rate_1') is None: initial_interest = term_value(term, 'annual_interest_rate')
    brokerage = term_value(term, 'brokerage_rate_1')
    if term.get('brokerage_rate_1') is None: brokerage = term_value(term, 'brokerage_rate')
    day = date.fromisoformat(str(contract['contract_date'])[:10])
    items = contract['items']; metadata = source.get('document_goods', {})
    distinct = lambda key: ' / '.join(dict.fromkeys(str(x[key]) for x in metadata.values() if x.get(key)))
    values = {
        'contract_no':text(contract['contract_no']), 'company_name':text(legal_name(source['company'])),
        'partner_name':text(legal_name(source['partner'])), 'company_party':party_block(source['company']),
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
