"""Single sale statement surface: preview, issue, historical reprint and native output."""
import api_client as httpx
from api_config import API_BASE_URL
from app_context import app_context
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QTextBrowser, QFileDialog, QMessageBox
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtGui import QPageLayout, QPageSize
from trade_statement_document import statement_html, print_document, export_pdf


class TradeStatementDialog(QDialog):
    def __init__(self, parent, sale_id):
        super().__init__(parent)
        self.setWindowTitle('거래명세표 — 미리보기 / 발행 / 재출력'); self.resize(1120, 760)
        self.url = f'{API_BASE_URL}/companies/{app_context.company_code}/sales/{sale_id}/statements'
        self.document = None
        root = QVBoxLayout(self); buttons = QHBoxLayout()
        self.versions = QComboBox(); self.issue_button = QPushButton('현재 매출로 발행')
        self.pdf_button = QPushButton('PDF 저장'); self.print_button = QPushButton('인쇄')
        for widget in (self.versions, self.issue_button, self.pdf_button, self.print_button): buttons.addWidget(widget)
        root.addLayout(buttons); self.browser = QTextBrowser(); root.addWidget(self.browser)
        self.versions.currentIndexChanged.connect(self.show_version)
        self.issue_button.clicked.connect(self.issue); self.pdf_button.clicked.connect(self.pdf); self.print_button.clicked.connect(self.print_current)
        self.refresh()

    def get(self, suffix=''):
        response = httpx.get(self.url+suffix, timeout=15)
        response.raise_for_status(); return response.json()

    def refresh(self, selected=None):
        documents = self.get()
        self.versions.blockSignals(True); self.versions.clear()
        try:
            preview = self.get('/preview')
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409: raise
            preview = None
        if preview: self.versions.addItem('현재 매출 미리보기 (미발행)', preview)
        for document in documents:
            self.versions.addItem(f"발행본 v{document['version']} · ID {document['statement_id']} · {document['status']}", document)
        self.versions.blockSignals(False)
        index = next((i for i in range(self.versions.count()) if self.versions.itemData(i).get('statement_id') == selected), 0) if selected else (1 if preview and documents else 0)
        self.versions.setCurrentIndex(index); self.issue_button.setEnabled(bool(preview) and app_context.can("SALES_GENERAL", "create")); self.show_version()

    def show_version(self, *_):
        self.document = self.versions.currentData()
        self.browser.setHtml(statement_html(self.document) if self.document else '발행된 거래명세표가 없습니다.')
        issued = bool(self.document and self.document.get('statement_id'))
        self.pdf_button.setEnabled(issued); self.print_button.setEnabled(issued)

    def error(self, exc): QMessageBox.warning(self, '거래명세표', str(exc))

    def issue(self):
        try:
            response = httpx.post(self.url, timeout=15); response.raise_for_status()
            self.refresh(response.json()['statement_id'])
        except Exception as exc: self.error(exc)

    def current(self):
        # Re-read status before output (another user may have corrected/cancelled Sale).
        document = self.get('/'+str(self.document['statement_id']))
        self.document = document; self.browser.setHtml(statement_html(document))
        return document

    def pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'PDF 저장', f"거래명세표_{self.document['statement_id']}_v{self.document['version']}.pdf", 'PDF (*.pdf)')
        if not filename: return
        try: export_pdf(self.current(), filename if filename.lower().endswith('.pdf') else filename+'.pdf')
        except Exception as exc: self.error(exc)

    def print_current(self):
        try:
            document = self.current()
            printer = QPrinter(QPrinter.HighResolution); printer.setPageSize(QPageSize(QPageSize.A4)); printer.setPageOrientation(QPageLayout.Landscape)
            if QPrintDialog(printer, self).exec() == QDialog.Accepted: print_document(document, printer)
        except Exception as exc: self.error(exc)
