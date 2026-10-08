"""Snapshot-only output; standard HTML documents and historical plain text."""
from html import escape
from pathlib import Path
import os
import re
import tempfile
from trade_statement_document import korean_font_family


def document_html(document):
    snapshot = document.get('snapshot') or {}
    body = snapshot.get('body', document['body'])
    if snapshot.get('body_format') == 'HTML':
        from contract_document_templates import validate_html
        validate_html(body)
        labels = {'DRAFT':'초안 / 검토용', 'CANCELLED':'취소된 계약서', 'SUPERSEDED':'새 version으로 대체된 계약서'}
        if document['status'] in labels:
            notice = '<p align="center"><b>' + labels[document['status']] + '</b></p>'
            # QTextEdit saves <body style="...">; a literal <body> match misses it.
            body, count = re.subn(r'(<body\b[^>]*>)', lambda match: match[0] + notice, body, count=1, flags=re.I)
            if not count: body = notice + body
        return body
    status = '초안 / 검토용' if document['status'] == 'DRAFT' else document['status']
    return f"<h1>계약서 / Version {document['version']}</h1><p>{escape(status)}</p><p>{escape(body).replace(chr(10), '<br/>')}</p>"


# Same physical layout for PDF and actual printers. No QTextDocument.print_()
# pagination or screen-DPI layout is used for these single-page contracts.
LAYOUT_DPI = 96
MARGIN_MM = 12
MIN_BODY_POINT_SIZE = 8.5


def contract_page(document):
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QTextDocument, QFont, QImage
    family = korean_font_family()
    metrics = QImage(1, 1, QImage.Format_ARGB32)
    metrics.setDotsPerMeterX(round(LAYOUT_DPI / 0.0254))
    metrics.setDotsPerMeterY(round(LAYOUT_DPI / 0.0254))
    rendered = QTextDocument()
    rendered.documentLayout().setPaintDevice(metrics)
    rendered.setUseDesignMetrics(True)
    rendered.setDefaultFont(QFont(family, 9))
    rendered.setDocumentMargin(0)
    html = document_html(document)
    # Output-only spacing: do not rewrite stored HTML/Snapshot or legal prose.
    compact = '<style>p { margin-top:3px; margin-bottom:3px; } h1 { margin-top:6px; margin-bottom:8px; } td, th { padding:3px; }</style>'
    if '</head>' in html: html = html.replace('</head>', compact + '</head>', 1)
    else: html = compact + html
    rendered.setHtml(html)
    available = QSizeF((210 - 2*MARGIN_MM)*LAYOUT_DPI/25.4,
                      (297 - 2*MARGIN_MM)*LAYOUT_DPI/25.4)
    rendered.setTextWidth(available.width())
    size = rendered.documentLayout().documentSize()
    scale = min(1.0, available.height()/size.height(), available.width()/size.width())
    # Respect smaller explicit font sizes in edited documents when deciding
    # whether scaling would make the smallest contractual text unreadable.
    smallest = 9.0
    block = rendered.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            size = fragment.charFormat().fontPointSize()
            if fragment.isValid() and fragment.text().strip() and size > 0:
                smallest = min(smallest, size)
            iterator += 1
        block = block.next()
    if scale < 1.0 and smallest*scale < MIN_BODY_POINT_SIZE:
        raise RuntimeError('A4 1페이지 수용 한계를 초과했습니다. 상품 수·긴 특약·주소를 검토하거나 별도 약정으로 분리하십시오. 내용은 삭제되지 않았으며 확정 Snapshot은 보존됩니다.')
    # Keep the font metrics device alive for the document's entire render.
    rendered._metrics_device = metrics
    return rendered, scale, available


def print_contract(document, device):
    from PySide6.QtCore import QMarginsF, QRectF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter
    rendered, scale, available = contract_page(document)
    page = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait,
                       QMarginsF(0,0,0,0), QPageLayout.Millimeter)
    page.setMode(QPageLayout.FullPageMode)
    if not device.setPageLayout(page):
        raise RuntimeError('출력 장치에서 A4 세로 용지를 사용할 수 없습니다.')
    # Native printers otherwise use a hardware-dependent printable origin.
    if hasattr(device, 'setFullPage'): device.setFullPage(True)
    painter = QPainter()
    if not painter.begin(device): raise RuntimeError('계약서 출력 장치를 열 수 없습니다. 확정 Snapshot은 보존됩니다.')
    try:
        painter.translate(MARGIN_MM*device.logicalDpiX()/25.4, MARGIN_MM*device.logicalDpiY()/25.4)
        painter.scale(device.logicalDpiX()/LAYOUT_DPI*scale, device.logicalDpiY()/LAYOUT_DPI*scale)
        rendered.drawContents(painter, QRectF(0,0,available.width()/scale,available.height()/scale))
    finally:
        painter.end()


def export_contract_pdf(document, filename):
    from PySide6.QtGui import QPdfWriter, QPageSize
    korean_font_family()
    destination = Path(filename)
    fd, temporary = tempfile.mkstemp(suffix='.pdf', dir=destination.parent)
    os.close(fd)
    try:
        writer = QPdfWriter(temporary)
        try:
            writer.setPageSize(QPageSize(QPageSize.A4)); writer.setResolution(300)
            print_contract(document, writer)
        finally:
            del writer
        if not Path(temporary).read_bytes().startswith(b'%PDF-'): raise RuntimeError('계약서 PDF 생성에 실패했습니다. 확정본은 보존됩니다.')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
