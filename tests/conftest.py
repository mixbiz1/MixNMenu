"""Keep one Qt application/platform alive before GUI test modules are collected."""
import os
import sys

import pytest

# Several old GUI modules setdefault('offscreen') and one creates QApplication
# during collection. On Windows offscreen can hide installed Korean fonts.
# Select the real Windows font backend BEFORE either of those happens.
os.environ['QT_QPA_PLATFORM'] = 'windows' if sys.platform == 'win32' else os.environ.get('QT_QPA_PLATFORM', 'offscreen')
_QT_APPLICATION = None


def pytest_configure(config):
    global _QT_APPLICATION
    from PySide6.QtWidgets import QApplication
    _QT_APPLICATION = QApplication.instance() or QApplication([])
    _QT_APPLICATION.setQuitOnLastWindowClosed(False)


@pytest.fixture(scope='session', autouse=True)
def qt_application():
    """Strong ownership across all function fixtures; never quit/delete between tests."""
    return _QT_APPLICATION
