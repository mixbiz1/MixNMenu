"""공통 MDI 자식창과 넓은 테두리 크기 조절 영역."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMdiArea, QMdiSubWindow


class ResizableMdiSubWindow(QMdiSubWindow):
    """얇은 프레임은 유지하면서 가장자리 안쪽에 8px resize hit 영역을 둔다."""

    RESIZE_MARGIN = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(
            self.RESIZE_MARGIN,
            self.RESIZE_MARGIN,
            self.RESIZE_MARGIN,
            self.RESIZE_MARGIN,
        )
        self.setMouseTracking(True)
        self._resize_origin = None

    def showEvent(self, event):
        """Restore a retained child widget when a closed MDI frame is reopened."""
        super().showEvent(event)
        widget = self.widget()
        # QMdiSubWindow can close its child widget while keeping both objects
        # alive. Showing the frame alone then leaves an empty-looking window.
        if widget is not None and widget.isHidden():
            widget.show()

    def _edges_at(self, point):
        margin = self.RESIZE_MARGIN
        edges = ""
        if point.x() <= margin:
            edges += "l"
        elif point.x() >= self.width() - margin:
            edges += "r"
        if point.y() <= margin:
            edges += "t"
        elif point.y() >= self.height() - margin:
            edges += "b"
        return edges

    @staticmethod
    def _cursor_for(edges):
        return {
            "l": Qt.SizeHorCursor,
            "r": Qt.SizeHorCursor,
            "t": Qt.SizeVerCursor,
            "b": Qt.SizeVerCursor,
            "lt": Qt.SizeFDiagCursor,
            "rb": Qt.SizeFDiagCursor,
            "rt": Qt.SizeBDiagCursor,
            "lb": Qt.SizeBDiagCursor,
        }.get(edges)

    def mousePressEvent(self, event):
        edges = self._edges_at(event.position().toPoint())
        if event.button() == Qt.LeftButton and edges:
            self._resize_origin = (
                event.globalPosition().toPoint(),
                self.geometry(),
                edges,
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_origin is not None:
            origin, geometry, edges = self._resize_origin
            delta = event.globalPosition().toPoint() - origin
            left, top = geometry.x(), geometry.y()
            right, bottom = geometry.right(), geometry.bottom()
            if "l" in edges:
                left = min(left + delta.x(), right - self.minimumWidth() + 1)
            if "r" in edges:
                right = max(right + delta.x(), left + self.minimumWidth() - 1)
            if "t" in edges:
                top = min(top + delta.y(), bottom - self.minimumHeight() + 1)
            if "b" in edges:
                bottom = max(bottom + delta.y(), top + self.minimumHeight() - 1)
            self.setGeometry(left, top, right - left + 1, bottom - top + 1)
            event.accept()
            return

        cursor = self._cursor_for(self._edges_at(event.position().toPoint()))
        if cursor is None:
            self.unsetCursor()
        else:
            self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resize_origin is not None and event.button() == Qt.LeftButton:
            self._resize_origin = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ResizableMdiArea(QMdiArea):
    """Automatically wraps every widget added as an MDI child."""

    def addSubWindow(self, widget, flags=Qt.WindowFlags()):
        if isinstance(widget, QMdiSubWindow):
            return super().addSubWindow(widget, flags)
        subwindow = ResizableMdiSubWindow()
        subwindow.setWidget(widget)
        return super().addSubWindow(subwindow, flags)
