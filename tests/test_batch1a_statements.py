import json
from decimal import Decimal
from unittest.mock import Mock
import pytest
from test_sales_outbound import api, payload, URL
import models
from audit_service import AuditEvent


def sale_and_url(client, data=None):
    response = client.post(URL, json=data or payload())
    assert response.status_code == 201, response.text
    sale = response.json()
    return sale, f"{URL}/{sale['sale_id']}/statements"


def test_snapshot_multi_lines_totals_master_change_reprint_duplicate(api):
    client, factory = api
    data = payload(1, '10')
    data['items'].append({**data['items'][0], 'line_no': 2, 'box_qty': 0, 'weight': '2.34', 'unit_price': 1234})
    sale, endpoint = sale_and_url(client, data)
    preview = client.get(endpoint+'/preview').json()
    assert preview['status'] == 'PREVIEW'
    with factory() as db: assert db.query(models.TradeStatement).count() == 0
    response = client.post(endpoint)
    assert response.status_code == 200, response.text
    document = response.json(); snap = document['snapshot']
    assert len(snap['items']) == 2
    for line, expected in zip(snap['items'], sale['items']):
        for key in ('box_qty','weight','unit_price','supply_amount','tax_amount','discount_amount','total_amount'):
            assert Decimal(str(line[key])) == Decimal(str(expected[key]))
    for key in ('total_box_qty','total_weight','total_supply_amount','total_tax_amount','total_discount_amount','total_amount'):
        assert Decimal(snap[key]) == Decimal(str(sale[key]))
    with factory() as db:
        db.get(models.Company,'00001').comp_name = 'CHANGED'
        db.get(models.Account,1).account_name = 'CHANGED'
        db.get(models.Product,1).product_name = 'CHANGED'
        db.commit()
    assert client.get(endpoint+'/'+str(document['statement_id'])).json()['snapshot'] == snap
    assert client.post(endpoint).json()['statement_id'] == document['statement_id']
    with factory() as db:
        assert db.query(models.TradeStatement).count() == 1
        assert db.query(AuditEvent).filter_by(entity_type='TRADE_STATEMENT', action='ISSUE').count() == 1
        assert db.query(models.Outbound).count() == 1
        assert db.query(models.AccountTransaction).count() == 1


def test_version_correction_cancel_and_company_isolation(api):
    client, factory = api
    sale, endpoint = sale_and_url(client)
    first = client.post(endpoint).json()
    corrected = client.put(URL+'/'+str(sale['sale_id']),json=payload(3,'30'))
    assert corrected.status_code == 200, corrected.text
    second = client.post(endpoint).json()
    assert second['version'] == 2
    assert client.post(endpoint).json()['statement_id'] == second['statement_id']
    previous = client.get(endpoint+'/'+str(first['statement_id'])).json()
    assert previous['status'] == 'SUPERSEDED' and previous['snapshot'] == first['snapshot']
    other = endpoint.replace('00001','OTHER')
    for method in (client.get,client.post): assert method(other).status_code == 404
    assert client.get(other+'/'+str(first['statement_id'])).status_code == 404
    assert client.post(URL+'/'+str(sale['sale_id'])+'/cancel',json={'reason':'취소검증'}).status_code == 200
    assert client.post(endpoint).status_code == 409
    assert client.get(endpoint+'/preview').status_code == 409
    documents = client.get(endpoint).json()
    assert len(documents) == 2 and all(d['status']=='CANCELLED' for d in documents)
    assert documents[-1]['snapshot'] == first['snapshot']


def test_issue_snapshot_failure_rolls_back_only_document(api, monkeypatch):
    client, factory = api
    sale, endpoint = sale_and_url(client)
    import trade_statement_routes as routes
    monkeypatch.setattr(routes, 'build_snapshot', Mock(side_effect=RuntimeError('renderer failed')))
    assert client.post(endpoint).status_code == 500
    with factory() as db:
        assert db.get(models.Sale,sale['sale_id']).document_status == 'CONFIRMED'
        assert db.query(models.TradeStatement).count() == 0
        assert db.query(models.Outbound).count() == 1
        assert db.query(models.AccountTransaction).count() == 1


def test_pdf_failure_keeps_sale_and_issued_snapshot(api,monkeypatch,tmp_path):
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    import trade_statement_document as renderer
    client, factory = api
    sale, endpoint = sale_and_url(client)
    document = client.post(endpoint).json()
    target = tmp_path/'saved.pdf'; target.write_bytes(b'previous document')
    def failed_write(document, filename):
        from pathlib import Path
        Path(filename).write_bytes(b'partial output')
        raise RuntimeError('PDF failure')
    # Inject failure at the output boundary; do not initialize native printers.
    monkeypatch.setattr(renderer,'_write_pdf',failed_write)
    with pytest.raises(RuntimeError): renderer.export_pdf(document,target)
    assert target.read_bytes() == b'previous document'
    assert list(tmp_path.iterdir()) == [target]
    assert client.get(endpoint+'/'+str(document['statement_id'])).json()['snapshot'] == document['snapshot']
    with factory() as db:
        assert db.get(models.Sale,sale['sale_id']).document_status == 'CONFIRMED'
        assert db.query(models.OutboundItem).count() == 1


def test_pdf_many_rows_korean_and_snapshot_only(api, tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    from trade_statement_document import statement_html

    client, _ = api
    _, endpoint = sale_and_url(client)
    document = client.post(endpoint).json()
    snapshot = document['snapshot']
    snapshot['items'] = [{**snapshot['items'][0], 'line_no': i+1, 'product_name': '한글상품 육류'} for i in range(100)]
    source = tmp_path / 'snapshot.json'
    source.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    target = tmp_path / 'statement.pdf'
    # QApplication/font caches are process-global. Exercise the real renderer in
    # a fresh process so earlier GUI tests cannot change this test's Qt state.
    script = r"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtPdf import QPdfDocument
import PySide6.QtPrintSupport as print_support
from trade_statement_document import export_pdf, korean_font_family
application = QApplication([])
def families_for_test(writing_system=QFontDatabase.Any):
    return [] if writing_system == QFontDatabase.Korean else ['Malgun Gothic']
with patch.object(QFontDatabase, 'families', staticmethod(families_for_test)), patch.object(
    print_support, 'QPrinter', Mock(side_effect=AssertionError('PDF must not discover native printers'))
) as printer:
    assert QFontDatabase.families() == ['Malgun Gothic']
    assert QFontDatabase.families(QFontDatabase.Any) == ['Malgun Gothic']
    assert QFontDatabase.families(QFontDatabase.Korean) == []
    assert korean_font_family() == 'Malgun Gothic'
    document = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    export_pdf(document, sys.argv[2])
    reader = QPdfDocument()
    assert reader.load(sys.argv[2]) == QPdfDocument.Error.None_
    assert reader.pageCount() > 1
    text = '\n'.join(reader.getAllText(page).text() for page in range(reader.pageCount()))
    assert '거래명세표' in text and text.count('한글상품') == 100
    assert 'BOX' in text and 'KG' in text
    printer.assert_not_called()
    reader.close()
"""
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run(
        [sys.executable, '-c', script, str(source), str(target)],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_bytes().startswith(b'%PDF-')
    html = statement_html(document)
    assert '현재 Master' not in html
    snapshot['memo'] = '<script>alert(1)</script>'
    assert '<script>' not in statement_html(document)


def test_taxable_amounts_and_issue_permission(api):
    client,factory=api
    from datetime import date
    from permissions import issue_token
    with factory() as db:
        db.get(models.Product,1).tax_type='1'
        db.add(models.TaxCode(tax_code='VAT10',tax_name='부가세',tax_kind='TAXABLE',tax_rate=10,valid_from=date(2000,1,1)))
        db.commit()
    data=payload(1,'1.01'); data['items'][0]['unit_price']=1001
    sale,endpoint=sale_and_url(client,data)
    doc=client.post(endpoint).json()
    assert Decimal(doc['snapshot']['items'][0]['tax_amount'])>0
    assert Decimal(doc['snapshot']['total_tax_amount'])==Decimal(str(sale['total_tax_amount']))
    with factory() as db:
        db.add(models.User(user_id='read',user_name='R',password_hash='x',is_admin=False)); db.commit()
        db.add_all([models.UserCompanyAccess(user_id='read',comp_code='00001'),models.UserMenuPermission(user_id='read',menu_code='SALES_GENERAL',can_read=True,can_create=False)])
        db.commit()
    client.headers['Authorization']='Bearer '+issue_token('read')
    assert client.get(endpoint).status_code==200 and client.post(endpoint).status_code==403


def test_statement_gui_no_reentry_issue_reprint_and_cancel(api,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app_context import app_context
    import views.trade_statement as ui
    application=QApplication.instance() or QApplication([])
    client,_=api
    sale,endpoint=sale_and_url(client)
    monkeypatch.setattr(app_context,'can',lambda *args:True)
    monkeypatch.setattr(app_context,'_company_code','00001')
    def get(url,**kwargs): return client.get(url[url.index('/api/v1'):])
    def post(url,**kwargs): return client.post(url[url.index('/api/v1'):])
    monkeypatch.setattr(ui.httpx,'get',get); monkeypatch.setattr(ui.httpx,'post',post)
    window=ui.TradeStatementDialog(None,sale['sale_id'])
    assert window.document['status']=='PREVIEW' and not window.pdf_button.isEnabled()
    window.issue()
    assert window.document['version']==1 and window.pdf_button.isEnabled()
    window.issue(); assert window.document['version']==1 and window.versions.count()==2
    assert window.current()['snapshot']['sale_id']==sale['sale_id']
    client.post(URL+'/'+str(sale['sale_id'])+'/cancel',json={'reason':'취소'})
    window.refresh()
    assert window.document['status']=='CANCELLED' and not window.issue_button.isEnabled()
    assert window.pdf_button.isEnabled() and window.versions.count()==1
    assert '취소된 매출' in window.browser.toPlainText()
    window.close()


def test_missing_korean_font_fails_before_export(api,monkeypatch,tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from trade_statement_document import export_pdf
    application=QApplication.instance() or QApplication([])
    client,_=api
    _,endpoint=sale_and_url(client)
    doc=client.post(endpoint).json()
    monkeypatch.setattr(QFontDatabase,'families',lambda *args:[])
    import trade_statement_document as renderer
    write = Mock(side_effect=AssertionError('font preflight must precede output'))
    monkeypatch.setattr(renderer, '_write_pdf', write)
    with pytest.raises(RuntimeError,match='한글 출력 글꼴'): export_pdf(doc,tmp_path/'bad.pdf')
    assert not (tmp_path/'bad.pdf').exists()
    write.assert_not_called()


@pytest.mark.parametrize('installed,expected', [
    (['Arial', '맑은 고딕', 'Malgun Gothic', 'NanumGothic'], 'Malgun Gothic'),
    (['Arial', '맑은 고딕'], '맑은 고딕'),
    (['Arial', 'Noto Sans CJK KR'], 'Noto Sans CJK KR'),
    (['Arial', '나눔고딕'], '나눔고딕'),
    (['Arial', 'Apple SD Gothic Neo'], 'Apple SD Gothic Neo'),
])
def test_font_selection_from_full_registry_without_korean_classification(monkeypatch, installed, expected):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QRawFont
    from trade_statement_document import korean_font_family
    application = QApplication.instance() or QApplication([])
    families = Mock(side_effect=lambda *args: [] if args else installed)
    monkeypatch.setattr(QFontDatabase, 'families', families)
    probe = Mock(side_effect=AssertionError('Known installed fonts must not be rejected by glyph probing'))
    monkeypatch.setattr(QRawFont, 'fromFont', probe)
    assert korean_font_family() == expected
    families.assert_called_once_with()
    probe.assert_not_called()


@pytest.mark.parametrize('installed', [[], ['Arial'], ['Arial', 'Custom Korean']])
def test_no_known_korean_candidate_is_rejected(monkeypatch, installed):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from trade_statement_document import korean_font_family
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QFontDatabase, 'families', lambda *args: installed)
    with pytest.raises(RuntimeError, match='한글 출력 글꼴이 없습니다'):
        korean_font_family()


def test_document_source_keeps_utf8_korean_literals():
    from pathlib import Path
    import trade_statement_document as renderer
    source = Path(renderer.__file__).read_bytes().decode('utf-8', errors='strict')
    for text in ('거래명세표', '맑은 고딕', '나눔고딕', '한글 출력 글꼴이 없습니다'):
        assert text in source
    assert '??' not in source and '\ufffd' not in source
