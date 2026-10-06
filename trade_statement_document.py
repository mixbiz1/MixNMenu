"""Snapshot-only HTML and Qt print/PDF rendering; paths are never document identities."""
from decimal import Decimal
from html import escape
import os
from pathlib import Path
import tempfile


def statement_html(document):
    snapshot = document['snapshot']
    def text(value): return escape(str(value or ''))
    def number(value): return f"{Decimal(str(value or 0)):,.2f}".rstrip('0').rstrip('.')
    def party(value):
        return '<br/>'.join(text(value.get(key)) for key in ('name','biz_no','ceo_name','address','address_detail','uptae','upjong','tel','phone','fax','email','tax_email') if value.get(key))
    status = {'PREVIEW':'미발행 미리보기', 'ISSUED':'발행본', 'SUPERSEDED':'정정 전 과거 발행본', 'CANCELLED':'취소된 매출의 발행본'}[document['status']]
    rows = []
    for item in snapshot['items']:
        values = (item['line_no'], item['product_name'], item.get('specification'), item.get('lot_code'),
                  number(item['box_qty']), number(item['weight']), number(item['unit_price']),
                  number(item['supply_amount']), number(item['tax_amount']), number(item['discount_amount']), number(item['total_amount']))
        rows.append('<tr>'+''.join('<td>'+text(v)+'</td>' for v in values)+'</tr>')
    headings = ('순번','상품','규격','LOT','BOX','KG','단가','공급가액','세액','할인/할증','합계')
    totals = ' / '.join(f'{label}: {number(snapshot[key])}' for label,key in
        (('BOX','total_box_qty'),('KG','total_weight'),('공급가액','total_supply_amount'),('세액','total_tax_amount'),('할인/할증','total_discount_amount'),('합계','total_amount')))
    return f'''<html><head><meta charset="utf-8"/><style>
    body {{font-family:'Malgun Gothic','NanumGothic',sans-serif;font-size:9pt;}}
    td,th {{padding:4px;}} h1 {{font-size:20pt;}}
    </style></head><body><h1>거래명세표</h1>
    <p>{text(status)} — 문서 ID {text(document.get('statement_id'))} / Version {text(document.get('version'))}<br/>
    매출 {text(snapshot['sale_no'])} / {text(snapshot['sale_date'])}<br/>
    발행일 {text(document.get('issued_at'))} / 발행자 {text(document.get('issued_by'))}</p>
    <table width="100%" border="1" cellspacing="0"><tr><th>공급자</th><th>공급받는자</th></tr>
    <tr><td>{party(snapshot['company'])}</td><td>{party(snapshot['customer'])}</td></tr></table>
    <br/><table width="100%" border="1" cellspacing="0"><thead><tr>{''.join('<th>'+x+'</th>' for x in headings)}</tr></thead>
    <tbody>{''.join(rows)}</tbody></table><p>{text(totals)}</p><p>비고: {text(snapshot.get('memo'))}</p>
    <p>거래처·상품 표시정보는 발행 시점 Master 값이며 과거 거래일 당시 Master 값의 복원을 의미하지 않습니다.</p></body></html>'''


def korean_font_family():
    """Select installed known Korean families; Qt script/glyph probes are not guards."""
    from PySide6.QtGui import QFontDatabase
    installed = QFontDatabase.families()
    by_name = {family.casefold(): family for family in installed}
    preferred = ('Malgun Gothic', '맑은 고딕', 'NanumGothic', '나눔고딕',
                 'Noto Sans CJK KR', 'Noto Sans KR', 'Apple SD Gothic Neo',
                 'AppleGothic', 'Gulim', '굴림', 'Dotum', '돋움')
    for name in preferred:
        family = by_name.get(name.casefold())
        if family is not None:
            return family
    raise RuntimeError('한글 출력 글꼴이 없습니다. 맑은 고딕 또는 나눔고딕을 설치한 뒤 재출력하세요.')


def print_document(document, printer):
    from PySide6.QtGui import QTextDocument, QFont
    family = korean_font_family()
    rendered = QTextDocument()
    rendered.setDefaultFont(QFont(family, 9))
    html = statement_html(document)
    # The selected family must also win over the HTML body's old fixed font list.
    html = html.replace("font-family:'Malgun Gothic','NanumGothic',sans-serif;", '')
    rendered.setHtml(html)
    rendered.print_(printer)


def _write_pdf(document, filename):
    from PySide6.QtGui import QPdfWriter, QPageSize, QPageLayout
    # PDF does not require Windows default-printer/COM discovery. Native printing
    # still uses QPrinter through the existing GUI print action.
    writer = QPdfWriter(str(filename))
    try:
        writer.setResolution(1200)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageOrientation(QPageLayout.Landscape)
        print_document(document, writer)
    finally:
        # Close the output device before replace/unlink, including on Windows.
        del writer


def export_pdf(document, filename):
    """Atomic export; an interrupted render cannot replace an existing PDF."""
    korean_font_family()  # Fail before creating any native output device or file.
    destination = Path(filename)
    fd, temporary = tempfile.mkstemp(suffix='.pdf', dir=destination.parent)
    os.close(fd)
    try:
        _write_pdf(document, temporary)
        with open(temporary, 'rb') as output:
            valid = output.read(5) == b'%PDF-'
        if not valid or Path(temporary).stat().st_size < 100:
            raise RuntimeError('PDF 생성에 실패했습니다. 발행본은 보존되어 다시 출력할 수 있습니다.')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
