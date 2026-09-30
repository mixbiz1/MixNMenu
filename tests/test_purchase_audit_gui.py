"""Offscreen GUI checks; all HTTP and interactive dialogs are isolated."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
from views.purchase_reg import PurchaseRegWindow
import views.purchase_reg as view


@pytest.mark.parametrize('reason,accepted,expected', [(' 정정 ',True,'정정'),('   ',True,None),('정정',False,None),('x'*1001,True,None)])
def test_cancel_dialog_passes_reason_or_does_not_send(monkeypatch, reason, accepted, expected):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(PurchaseRegWindow,'load_base_options',lambda self:None)
    monkeypatch.setattr(PurchaseRegWindow,'load_all',lambda self:None)
    monkeypatch.setattr(QMessageBox,'question',lambda *_:QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox,'warning',lambda *_:None)
    monkeypatch.setattr(QInputDialog,'getText',lambda *_:(reason,accepted))
    sent=[]
    def post(url, **kwargs):
        sent.append(kwargs['json'])
        return SimpleNamespace(raise_for_status=lambda:None)
    monkeypatch.setattr(view.httpx,'post',post)
    window=PurchaseRegWindow(); window.current_id=1
    window.cancel_document()
    assert sent==([] if expected is None else [{'reason':expected}])
    window.close()
