import sys
import os

# 모듈 단독 실행 시에도 상위 경로 참조 가능하도록 설정
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import requests
from PySide6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox, QDialog, QStyleFactory
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont, QPalette, QColor

# ... (이하 기존 company_reg.py 코드 동일 유지)