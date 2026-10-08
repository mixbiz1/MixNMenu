"""Session ownership and native Windows font backend must precede collection."""
import gc
import os
from pathlib import Path
import subprocess
import sys


def test_qt_session_keeps_application_alive_and_uses_platform_fonts(qt_application):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from trade_statement_document import korean_font_family
    initial=korean_font_family()
    alias=QApplication.instance(); del alias; gc.collect()
    assert QApplication.instance() is qt_application
    assert korean_font_family()==initial
    assert initial in QFontDatabase.families()
    if sys.platform=='win32':
        assert qt_application.platformName()=='windows'
        assert os.environ['QT_QPA_PLATFORM']=='windows'


def test_registry_monkeypatch_is_restored_without_cached_fake_font(qt_application,monkeypatch):
    from PySide6.QtGui import QFontDatabase
    from trade_statement_document import korean_font_family
    actual=korean_font_family()
    with monkeypatch.context() as patch:
        patch.setattr(QFontDatabase,'families',lambda:[])
        import pytest
        with pytest.raises(RuntimeError,match='한글 출력 글꼴'):
            korean_font_family()
    assert korean_font_family()==actual


def test_missing_application_is_reported_before_native_font_registry_query():
    script="""
from unittest.mock import patch
from PySide6.QtGui import QFontDatabase
from trade_statement_document import korean_font_family
with patch.object(QFontDatabase,'families',side_effect=AssertionError('native query without application')):
    try:
        korean_font_family()
    except RuntimeError as exc:
        assert 'QApplication' in str(exc)
    else:
        raise AssertionError('missing GUI context was not rejected')
"""
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
