from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHeaderView, QTableWidgetItem


class ListTableItem(QTableWidgetItem):
    """표시문자와 별개로 날짜·숫자·금액의 실제 값 정렬을 지원한다."""

    def __init__(self, text="", sort_value=None):
        super().__init__(str(text or ""))
        self.sort_value = str(text or "").casefold() if sort_value is None else sort_value
        self.setToolTip(str(text or ""))

    def __lt__(self, other):
        if isinstance(other, ListTableItem):
            try:
                return self.sort_value < other.sort_value
            except TypeError:
                return str(self.sort_value) < str(other.sort_value)
        return super().__lt__(other)


def configure_list_table(table, widths):
    """조회목록에 제목 정렬과 사용자 열 너비 조정을 활성화한다."""
    table.setSortingEnabled(True)
    header = table.horizontalHeader()
    header.setSectionsClickable(True)
    header.setSectionResizeMode(QHeaderView.Interactive)
    for column, width in enumerate(widths):
        table.setColumnWidth(column, width)


def fit_list_columns(table, minimums, maximums):
    """내용에 따라 열을 조정하되 화면 독점을 막기 위해 최소·최대 폭을 둔다."""
    metrics = QFontMetrics(table.font())
    for column, (minimum, maximum) in enumerate(zip(minimums, maximums)):
        header_item = table.horizontalHeaderItem(column)
        texts = [header_item.text() if header_item else ""]
        for row in range(table.rowCount()):
            item = table.item(row, column)
            if item:
                texts.append(item.text())
        content_width = max((metrics.horizontalAdvance(text) for text in texts), default=0) + 30
        table.setColumnWidth(column, max(minimum, min(content_width, maximum)))


def begin_list_update(table):
    table.setSortingEnabled(False)


def end_list_update(table, minimums, maximums):
    fit_list_columns(table, minimums, maximums)
    table.setSortingEnabled(True)
