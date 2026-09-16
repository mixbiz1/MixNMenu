import httpx

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMdiSubWindow,
)


API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class ReadableCheckBox(QCheckBox):
    """테마와 무관하게 선택 상태를 문자와 배경색으로 함께 표시한다."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.setProperty("mxmnReadable", True)
        self.stateChanged.connect(self._sync_text)
        self._sync_text()

    def _sync_text(self):
        self.setText(f"{'☑' if self.isChecked() else '□'} {self.label}")
        self.setAccessibleName(f"{self.label} {'선택' if self.isChecked() else '해제'}")


class CommonCodeWindow(QWidget):
    """공통코드 그룹과 코드값을 관리하는 Pure Python PySide6 화면."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_group_code = None
        self.current_value_id = None
        self.setWindowTitle("공통코드관리")
        self.resize(1280, 760)
        self._build_ui()
        self._apply_style()
        self.load_groups()

    def _build_ui(self):
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("그룹코드 / 그룹명 / 상세코드 / 코드명")
        self.search_input.setMinimumWidth(380)
        self.search_result_label = QLabel("전체 조회")
        self.search_result_label.setObjectName("searchResult")
        self.btn_refresh = QPushButton("조회")
        self.btn_reset = QPushButton("새로고침")
        self.btn_close = QPushButton("닫기")
        toolbar.addWidget(QLabel("공통코드 그룹 및 상세코드"))
        toolbar.addWidget(QLabel("검색"))
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.search_result_label)
        toolbar.addStretch()
        toolbar.addWidget(self.include_inactive)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_reset)
        toolbar.addWidget(self.btn_close)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # 왼쪽: 코드그룹
        left = QWidget()
        left_layout = QVBoxLayout(left)
        group_box = QGroupBox("코드그룹")
        group_layout = QVBoxLayout(group_box)
        self.group_table = QTableWidget(0, 4)
        self.group_table.setHorizontalHeaderLabels(["그룹코드", "그룹명", "정렬방식", "사용"])
        self.group_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.group_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.group_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.group_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.group_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        group_layout.addWidget(self.group_table)

        form = QGridLayout()
        self.group_code = QLineEdit()
        self.group_code.setReadOnly(True)
        self.group_code.setPlaceholderText("자동발번")
        self.group_name = QLineEdit()
        self.group_sort_direction = QComboBox()
        self.group_sort_direction.addItem("코드 오름차순 (001 → 999)", "ASC")
        self.group_sort_direction.addItem("코드 내림차순 (999 → 001)", "DESC")
        self.group_sort_direction.setToolTip("선택한 코드그룹의 상세코드 표시 순서입니다.")
        self.group_use = ReadableCheckBox("사용")
        self.group_use.setChecked(True)
        self.group_description = QTextEdit()
        self.group_description.setMaximumHeight(55)
        form.addWidget(QLabel("그룹코드 *"), 0, 0)
        form.addWidget(self.group_code, 0, 1)
        form.addWidget(QLabel("그룹명 *"), 1, 0)
        form.addWidget(self.group_name, 1, 1)
        form.addWidget(QLabel("상세코드 정렬"), 2, 0)
        form.addWidget(self.group_sort_direction, 2, 1)
        form.addWidget(QLabel("설명"), 3, 0)
        form.addWidget(self.group_description, 3, 1)
        form.addWidget(self.group_use, 4, 1)
        group_layout.addLayout(form)

        group_buttons = QHBoxLayout()
        self.btn_group_new = QPushButton("그룹 신규")
        self.btn_group_save = QPushButton("그룹 저장")
        self.btn_group_delete = QPushButton("그룹 삭제")
        group_buttons.addStretch()
        group_buttons.addWidget(self.btn_group_new)
        group_buttons.addWidget(self.btn_group_save)
        group_buttons.addWidget(self.btn_group_delete)
        group_layout.addLayout(group_buttons)
        left_layout.addWidget(group_box)
        splitter.addWidget(left)

        # 오른쪽: 선택 그룹의 코드값
        right = QWidget()
        right_layout = QVBoxLayout(right)
        value_box = QGroupBox("상세 코드")
        value_layout = QVBoxLayout(value_box)
        self.selected_group_label = QLabel("코드그룹을 선택하세요.")
        value_layout.addWidget(self.selected_group_label)

        legacy_hint = QLabel(
            "레거시 화면의 ‘코드구분 선택 → 목록 조회 → 신규·수정·저장’ 흐름을 유지합니다. "
            "삭제 대신 사용중지를 사용하며, 창고 주소·전화·보관료나 상품 브랜드·원산지처럼 "
            "전용 속성이 많은 정보는 각 전용 Master 화면에서 관리합니다."
        )
        legacy_hint.setObjectName("legacyHint")
        legacy_hint.setWordWrap(True)
        value_layout.addWidget(legacy_hint)

        self.value_table = QTableWidget(0, 4)
        self.value_table.setHorizontalHeaderLabels(
            ["코드", "코드명", "사용", "설명"]
        )
        self.value_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.value_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.value_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        value_layout.addWidget(self.value_table)

        value_form = QGridLayout()
        self.value_code = QLineEdit()
        self.value_code.setReadOnly(True)
        self.value_code.setPlaceholderText("자동발번")
        self.value_name = QLineEdit()
        self.value_use = ReadableCheckBox("사용")
        self.value_use.setChecked(True)
        self.value_description = QLineEdit()
        self.extra_value1 = QLineEdit()
        self.extra_value2 = QLineEdit()
        value_form.addWidget(QLabel("코드 *"), 0, 0)
        value_form.addWidget(self.value_code, 0, 1)
        value_form.addWidget(QLabel("코드명 *"), 0, 2)
        value_form.addWidget(self.value_name, 0, 3)
        value_form.addWidget(self.value_use, 1, 1)
        value_form.addWidget(QLabel("설명"), 2, 0)
        value_form.addWidget(self.value_description, 2, 1, 1, 3)
        value_form.addWidget(QLabel("추가값1"), 3, 0)
        value_form.addWidget(self.extra_value1, 3, 1)
        value_form.addWidget(QLabel("추가값2"), 3, 2)
        value_form.addWidget(self.extra_value2, 3, 3)
        value_layout.addLayout(value_form)

        value_buttons = QHBoxLayout()
        self.btn_value_new = QPushButton("코드 신규")
        self.btn_value_save = QPushButton("코드 저장")
        self.btn_value_delete = QPushButton("코드 삭제")
        value_buttons.addStretch()
        value_buttons.addWidget(self.btn_value_new)
        value_buttons.addWidget(self.btn_value_save)
        value_buttons.addWidget(self.btn_value_delete)
        value_layout.addLayout(value_buttons)
        right_layout.addWidget(value_box)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([480, 800])

        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset.clicked.connect(self.reset_view)
        self.search_input.returnPressed.connect(self.refresh_data)
        self.btn_close.clicked.connect(self.close_window)
        self.include_inactive.stateChanged.connect(self.load_groups)
        self.group_table.itemSelectionChanged.connect(self.on_group_selected)
        self.group_table.cellClicked.connect(self.on_group_clicked)
        self.value_table.itemSelectionChanged.connect(self.on_value_selected)
        self.btn_group_new.clicked.connect(self.new_group)
        self.btn_group_save.clicked.connect(self.save_group)
        self.btn_group_delete.clicked.connect(self.delete_group)
        self.btn_value_new.clicked.connect(self.new_value)
        self.btn_value_save.clicked.connect(self.save_value)
        self.btn_value_delete.clicked.connect(self.delete_value)
        self.group_sort_direction.currentIndexChanged.connect(
            self.apply_value_sort
        )

    def _apply_style(self):
        dark = self.palette().window().color().lightness() < 128
        if dark:
            window, panel, field, text_color = "#202124", "#292a2d", "#303134", "#f1f3f4"
            border, selected = "#5f6368", "#174ea6"
        else:
            window, panel, field, text_color = "#f4f6f8", "#ffffff", "#ffffff", "#111111"
            border, selected = "#aeb6bf", "#cfe8ff"
        self.setStyleSheet(
            f"""
            QWidget {{ background:{window}; color:{text_color}; font-family:'맑은 고딕'; font-size:9pt; }}
            QGroupBox {{ background:{panel}; border:1px solid {border}; border-radius:4px;
                         margin-top:10px; padding-top:8px; font-weight:bold; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}
            QLineEdit, QTextEdit, QComboBox {{ background:{field}; color:{text_color};
                         border:1px solid {border}; border-radius:2px; min-height:25px; padding:2px 5px; }}
            QPushButton {{ background:{field}; color:{text_color}; border:1px solid {border};
                           border-radius:3px; min-height:28px; padding:3px 12px; }}
            QPushButton:hover {{ border-color:#0067c0; }}
            QTableWidget {{ background:{field}; color:{text_color}; gridline-color:{border};
                            border:1px solid {border}; selection-background-color:{selected}; }}
            QHeaderView::section {{ background:{panel}; color:{text_color}; border:0;
                                    border-right:1px solid {border}; border-bottom:1px solid {border};
                                    padding:5px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"] {{ background:{field}; color:{text_color};
                         border:1px solid {border}; border-radius:3px; min-height:28px;
                         padding:3px 10px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"]:checked {{ background:{selected};
                         border:2px solid #0067c0; }}
            QCheckBox[mxmnReadable="true"]::indicator {{ width:0px; height:0px; }}
            QLabel#legacyHint {{ background:{panel}; border:1px solid {border};
                         border-radius:3px; padding:6px; font-weight:normal; }}
            QLabel#searchResult {{ background:{panel}; border:1px solid {border};
                         border-radius:3px; padding:5px 8px; font-weight:bold; }}
            """
        )

    @staticmethod
    def _error_detail(response, fallback):
        try:
            return response.json().get("detail", fallback)
        except Exception:
            return fallback

    def load_groups(self):
        try:
            response = httpx.get(
                f"{API_BASE_URL}/code-groups",
                params={"include_inactive": str(self.include_inactive.isChecked()).lower()},
                timeout=10,
            )
            response.raise_for_status()
            rows = response.json()
            self.group_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                values = [
                    item.get("group_code", ""),
                    item.get("group_name", ""),
                    "오름차순" if item.get("sort_direction", "ASC") == "ASC" else "내림차순",
                    "사용" if item.get("use_yn") else "중지",
                ]
                for col, value in enumerate(values):
                    self.group_table.setItem(row, col, QTableWidgetItem(str(value)))
                self.group_table.item(row, 0).setData(Qt.UserRole, item)
            self._apply_search_filter()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

    def refresh_data(self):
        """선택 그룹이 있으면 상세코드, 없으면 그룹목록을 검색한다."""
        if self.current_group_code:
            self.load_values()
        else:
            self.load_groups()
        self._apply_search_filter()

    def reset_view(self):
        self.search_input.clear()
        self.search_result_label.setText("전체 조회")
        self.current_group_code = None
        self.current_value_id = None
        self.group_table.clearSelection()
        self.value_table.setRowCount(0)
        self.load_groups()

    def _apply_search_filter(self):
        keyword = self.search_input.text().strip().lower()
        tables = (self.value_table,) if self.current_group_code else (self.group_table,)
        visible_count = 0
        for table in tables:
            for row in range(table.rowCount()):
                row_text = " ".join(
                    table.item(row, col).text()
                    for col in range(table.columnCount())
                    if table.item(row, col) is not None
                ).lower()
                hidden = bool(keyword) and keyword not in row_text
                table.setRowHidden(row, hidden)
                if not hidden:
                    visible_count += 1
        if keyword:
            self.search_result_label.setText(
                f"‘{self.search_input.text().strip()}’ 검색 결과 {visible_count}건"
            )
        else:
            self.search_result_label.setText(f"전체 {visible_count}건")

    def apply_value_sort(self):
        """정렬방식 선택 즉시 현재 상세코드 목록에 반영한다."""
        if self.value_table.rowCount() == 0:
            return
        order = (
            Qt.DescendingOrder
            if self.group_sort_direction.currentData() == "DESC"
            else Qt.AscendingOrder
        )
        self.value_table.sortItems(0, order)

    def on_group_selected(self):
        row = self.group_table.currentRow()
        if row < 0 or self.group_table.item(row, 0) is None:
            return
        item = self.group_table.item(row, 0).data(Qt.UserRole)
        self.current_group_code = item["group_code"]
        self.group_code.setText(item["group_code"])
        self.group_name.setText(item["group_name"])
        self.group_description.setPlainText(item.get("description") or "")
        index = self.group_sort_direction.findData(item.get("sort_direction", "ASC"))
        self.group_sort_direction.setCurrentIndex(max(index, 0))
        self.group_use.setChecked(bool(item.get("use_yn")))
        self.selected_group_label.setText(
            f"{item['group_code']}  {item['group_name']}"
        )
        self.new_value()
        self.load_values()

    def on_group_clicked(self, row, column):
        """사용자가 그룹을 직접 누르면 이전 검색조건을 해제한다."""
        if self.search_input.text():
            self.search_input.clear()
            self.search_result_label.setText("전체 조회")
            self.load_values()

    def new_group(self):
        self.current_group_code = None
        self.group_code.clear()
        self.group_name.clear()
        self.group_description.clear()
        self.group_sort_direction.setCurrentIndex(0)
        self.group_use.setChecked(True)
        self.value_table.setRowCount(0)
        self.selected_group_label.setText("신규 코드그룹")
        try:
            response = httpx.get(f"{API_BASE_URL}/code-groups/next-code", timeout=10)
            response.raise_for_status()
            self.group_code.setText(response.json()["group_code"])
        except Exception as exc:
            QMessageBox.critical(self, "자동발번 오류", str(exc))
            return
        self.group_name.setFocus()

    def save_group(self):
        code = self.group_code.text().strip().upper()
        name = self.group_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "입력 확인", "그룹코드와 그룹명은 필수입니다.")
            return
        payload = {
            "group_code": code,
            "group_name": name,
            "description": self.group_description.toPlainText().strip() or None,
            "sort_order": 0,
            "sort_direction": self.group_sort_direction.currentData(),
            "system_yn": False,
            "use_yn": self.group_use.isChecked(),
        }
        try:
            if self.current_group_code:
                response = httpx.put(
                    f"{API_BASE_URL}/code-groups/{self.current_group_code}",
                    json=payload,
                    timeout=10,
                )
            else:
                response = httpx.post(
                    f"{API_BASE_URL}/code-groups", json=payload, timeout=10
                )
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            self.current_group_code = response.json()["group_code"]
            QMessageBox.information(self, "저장 완료", "코드그룹이 저장되었습니다.")
            self.load_groups()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def load_values(self):
        if not self.current_group_code:
            return
        try:
            response = httpx.get(
                f"{API_BASE_URL}/code-groups/{self.current_group_code}/values",
                params={"include_inactive": str(self.include_inactive.isChecked()).lower()},
                timeout=10,
            )
            response.raise_for_status()
            rows = response.json()
            self.value_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                values = [
                    item.get("code", ""),
                    item.get("code_name", ""),
                    "사용" if item.get("use_yn") else "중지",
                    item.get("description") or "",
                ]
                for col, value in enumerate(values):
                    self.value_table.setItem(row, col, QTableWidgetItem(str(value)))
                self.value_table.item(row, 0).setData(Qt.UserRole, item)
            self.apply_value_sort()
            self._apply_search_filter()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

    def delete_group(self):
        if not self.current_group_code:
            QMessageBox.warning(self, "삭제 확인", "삭제할 코드그룹을 선택하세요.")
            return
        if QMessageBox.question(
            self, "그룹 삭제 1차 확인",
            "그룹과 소속 상세코드를 사용중지하시겠습니까?\n기존 데이터는 물리삭제하지 않습니다.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        if QMessageBox.warning(
            self, "그룹 삭제 최종 확인",
            f"[{self.current_group_code} {self.group_name.text()}] 그룹을 정말 사용중지하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            response = httpx.delete(
                f"{API_BASE_URL}/code-groups/{self.current_group_code}", timeout=10
            )
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            self.reset_view()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", str(exc))

    def on_value_selected(self):
        row = self.value_table.currentRow()
        if row < 0 or self.value_table.item(row, 0) is None:
            return
        item = self.value_table.item(row, 0).data(Qt.UserRole)
        self.current_value_id = item["code_value_id"]
        self.value_code.setText(item["code"])
        self.value_name.setText(item["code_name"])
        self.value_description.setText(item.get("description") or "")
        self.extra_value1.setText(item.get("extra_value1") or "")
        self.extra_value2.setText(item.get("extra_value2") or "")
        self.value_use.setChecked(bool(item.get("use_yn")))

    def new_value(self):
        self.current_value_id = None
        for widget in (
            self.value_code,
            self.value_name,
            self.value_description,
            self.extra_value1,
            self.extra_value2,
        ):
            widget.clear()
        self.value_use.setChecked(True)
        if self.current_group_code:
            try:
                response = httpx.get(
                    f"{API_BASE_URL}/code-groups/{self.current_group_code}/values/next-code",
                    timeout=10,
                )
                response.raise_for_status()
                self.value_code.setText(response.json()["code"])
            except Exception as exc:
                QMessageBox.critical(self, "자동발번 오류", str(exc))
                return
        self.value_name.setFocus()

    def save_value(self):
        if not self.current_group_code:
            QMessageBox.warning(self, "입력 확인", "코드그룹을 먼저 선택하거나 저장하세요.")
            return
        code = self.value_code.text().strip().upper()
        name = self.value_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "입력 확인", "코드와 코드명은 필수입니다.")
            return
        payload = {
            "code": code,
            "code_name": name,
            "description": self.value_description.text().strip() or None,
            "sort_order": 0,
            "extra_value1": self.extra_value1.text().strip() or None,
            "extra_value2": self.extra_value2.text().strip() or None,
            "use_yn": self.value_use.isChecked(),
        }
        try:
            base = f"{API_BASE_URL}/code-groups/{self.current_group_code}/values"
            if self.current_value_id:
                response = httpx.put(
                    f"{base}/{self.current_value_id}", json=payload, timeout=10
                )
            else:
                response = httpx.post(base, json=payload, timeout=10)
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            QMessageBox.information(self, "저장 완료", "공통코드가 저장되었습니다.")
            self.new_value()
            self.load_values()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_value(self):
        if not self.current_group_code or not self.current_value_id:
            QMessageBox.warning(self, "삭제 확인", "삭제할 상세코드를 선택하세요.")
            return
        if QMessageBox.question(
            self, "코드 삭제 1차 확인",
            "선택한 코드를 사용중지하시겠습니까?\n기존 참조 데이터는 보존됩니다.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        if QMessageBox.warning(
            self, "코드 삭제 최종 확인",
            f"[{self.value_code.text()} {self.value_name.text()}] 코드를 정말 사용중지하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            response = httpx.delete(
                f"{API_BASE_URL}/code-groups/{self.current_group_code}/values/{self.current_value_id}",
                timeout=10,
            )
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            self.new_value()
            self.load_values()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", str(exc))

    def close_window(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QMdiSubWindow):
                parent.close()
                return
            parent = parent.parentWidget()
        self.close()
