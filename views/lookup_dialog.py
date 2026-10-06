"""Shared row lookup; selection carries the master PK, never a row index."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

class LookupDialog(QDialog):
    def __init__(self, parent, title, keyword, columns, fetch):
        super().__init__(parent); self.setWindowTitle(title); self.resize(820, 520)
        self.fetch, self.columns, self.selected = fetch, columns, None
        root = QVBoxLayout(self); line = QHBoxLayout(); line.addWidget(QLabel("코드·명칭 키워드"))
        self.keyword = QLineEdit(keyword); self.keyword.setPlaceholderText("일부만 입력해도 검색됩니다.")
        button = QPushButton("조회"); line.addWidget(self.keyword, 1); line.addWidget(button); root.addLayout(line)
        self.table = QTableWidget(0, len(columns)); self.table.setHorizontalHeaderLabels([x[0] for x in columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); root.addWidget(self.table)
        root.addWidget(QLabel("행을 더블클릭하거나 선택 후 Enter를 누르세요."))
        self.table.installEventFilter(self)
        button.clicked.connect(self.search); self.keyword.returnPressed.connect(self.search)
        self.table.doubleClicked.connect(self.accept_current); self.table.itemActivated.connect(self.accept_current)
        self.search(); self.keyword.setFocus(); self.keyword.selectAll()

    def search(self):
        try:
            rows = self.fetch(self.keyword.text().strip()); self.table.setRowCount(0)
            for value in rows:
                row = self.table.rowCount(); self.table.insertRow(row)
                for col, (_, key) in enumerate(self.columns): self.table.setItem(row, col, QTableWidgetItem(str(value.get(key) or "")))
                self.table.item(row, 0).setData(Qt.UserRole, value)
            if rows: self.table.selectRow(0); self.table.setFocus()
        except Exception as exc: QMessageBox.critical(self, "조회 오류", error_text(exc))

    def accept_current(self, *_):
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 0): self.selected = self.table.item(row, 0).data(Qt.UserRole); self.accept()

    def eventFilter(self, watched, event):
        if watched is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.accept_current()
                return True
            if key in (Qt.Key_Up, Qt.Key_Down) and self.table.rowCount():
                row = self.table.currentRow()
                if row < 0:
                    row = 0
                else:
                    row += -1 if key == Qt.Key_Up else 1
                    row = max(0, min(row, self.table.rowCount() - 1))
                self.table.setCurrentCell(row, 0)
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 0))
                return True
        return super().eventFilter(watched, event)



def error_text(exc):
    try:
        return str(exc.response.json().get('detail', exc))
    except (AttributeError, ValueError):
        return str(exc)
