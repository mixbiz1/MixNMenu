"""Snapshot-only contract output. Sample template; no legal clause engine."""
from html import escape
from pathlib import Path
import os
import tempfile
from trade_statement_document import korean_font_family


def document_html(document):
    snapshot = document.get('snapshot') or {}
    body = snapshot.get('body', document['body'])
    return f"<h1>계약서 / Version {document['version']}</h1><p>{escape(document['status'])}</p><p>{escape(body).replace(chr(10), '<br/>')}</p>"


def print_contract(document, device):
    from PySide6.QtGui import QTextDocument, QFont
    rendered = QTextDocument()
    rendered.setDefaultFont(QFont(korean_font_family(), 10))
    rendered.setHtml(document_html(document))
    rendered.print_(device)


def export_contract_pdf(document, filename):
    from PySide6.QtGui import QPdfWriter, QPageSize
    if document['status'] == 'DRAFT': raise RuntimeError('확정된 계약서만 출력할 수 있습니다.')
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
