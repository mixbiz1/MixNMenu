import httpx

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QVBoxLayout,
    QWidget,
    QMdiSubWindow,
    QApplication,
)

try:
    from views.common_code_reg import API_BASE_URL, ReadableCheckBox
except ImportError:
    from common_code_reg import API_BASE_URL, ReadableCheckBox
from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update


PRODUCT_CODE_GROUPS = (
    ("PC001", "브랜드", "상품 브랜드/제조사 구분"),
    ("PC002", "등급", "육류 품질 및 상품 등급"),
    ("PC003", "원산지", "국가 또는 원산지 구분"),
    ("PC004", "냉장구분", "냉장·냉동 등 보관상태"),
    ("PC005", "식육종류", "소·돼지·양 등 축종 구분"),
    ("PC006", "수불단위", "Kg·Box·EA 등 재고 수불단위"),
    ("PC007", "표준부위", "Tenderloin·Short Rib 등 표준부위"),
    ("PC008", "EST NO", "해외 생산공장 Establishment Number"),
    ("PC009", "포장상태", "IW·VP·벌크 등 포장형태"),
    ("PC010", "납품상품분류", "납품 및 판매 목적의 상품분류"),
    ("PC011", "품목구분", "상품 Master의 상위 품목구분"),
    ("PC012", "성별", "Steer·Cow·Bull 등 축종 성별"),
)


class GoodsCommonCodeWindow(QWidget):
    """상품 Master가 공통으로 사용하는 분류별 상세코드 관리 화면."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_group_code = None
        self.current_group_name = None
        self.current_group_description = None
        self.current_group_exists = False
        self.current_value_id = None
        self.setWindowTitle("상품공통코드관리")
        self.resize(1280, 760)
        self._build_ui()
        self._apply_style()
        # MDI 창을 먼저 표시한 뒤 초기 자료를 조회해 클릭 반응을 즉시 보여준다.
        QTimer.singleShot(50, self._initial_load)

    def _build_ui(self):
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("코드 / 코드명 / 설명")
        self.search_input.setMinimumWidth(360)
        self.search_result_label = QLabel("전체 조회")
        self.search_result_label.setObjectName("searchResult")
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.btn_refresh = QPushButton("조회")
        self.btn_reset = QPushButton("새로고침")
        self.btn_close = QPushButton("닫기")
        toolbar.addWidget(QLabel("상품 관련 공통코드"))
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

        category_box = QGroupBox("상품 코드구분")
        category_layout = QVBoxLayout(category_box)
        self.category_table = QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["코드구분", "기능 설명"])
        self.category_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.category_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.category_table, (150, 250))
        category_layout.addWidget(self.category_table)
        category_form = QGridLayout()
        self.category_code = QLineEdit()
        self.category_code.setReadOnly(True)
        self.category_code.setPlaceholderText("자동발번")
        self.category_name = QLineEdit()
        self.category_description = QLineEdit()
        self.category_use = ReadableCheckBox("사용")
        self.category_use.setChecked(True)
        category_form.addWidget(QLabel("분류코드"), 0, 0)
        category_form.addWidget(self.category_code, 0, 1)
        category_form.addWidget(QLabel("분류명 *"), 1, 0)
        category_form.addWidget(self.category_name, 1, 1)
        category_form.addWidget(QLabel("설명"), 2, 0)
        category_form.addWidget(self.category_description, 2, 1)
        category_form.addWidget(self.category_use, 3, 1)
        category_layout.addLayout(category_form)
        category_buttons = QHBoxLayout()
        self.btn_category_new = QPushButton("분류 신규")
        self.btn_category_save = QPushButton("분류 저장")
        self.btn_category_delete = QPushButton("분류 삭제")
        category_buttons.addWidget(self.btn_category_new)
        category_buttons.addWidget(self.btn_category_save)
        category_buttons.addWidget(self.btn_category_delete)
        category_layout.addLayout(category_buttons)
        category_hint = QLabel(
            "레거시 상품공통코드의 코드구분 선택 방식을 유지했습니다. "
            "왼쪽 구분을 선택하면 오른쪽에 해당 코드만 표시됩니다."
        )
        category_hint.setObjectName("hint")
        category_hint.setWordWrap(True)
        category_layout.addWidget(category_hint)
        splitter.addWidget(category_box)

        value_box = QGroupBox("상품 상세코드")
        value_layout = QVBoxLayout(value_box)
        self.selected_group_label = QLabel("상품 코드구분을 선택하세요.")
        self.selected_group_label.setObjectName("selectedGroup")
        value_layout.addWidget(self.selected_group_label)

        self.value_table = QTableWidget(0, 4)
        self.value_table.setHorizontalHeaderLabels(["코드", "코드명", "사용", "설명"])
        self.value_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.value_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.value_table, (100, 200, 70, 240))
        value_layout.addWidget(self.value_table)

        form = QGridLayout()
        self.value_code = QLineEdit()
        self.value_code.setReadOnly(True)
        self.value_code.setPlaceholderText("자동발번")
        self.value_name = QLineEdit()
        self.value_use = ReadableCheckBox("사용")
        self.value_use.setChecked(True)
        self.value_description = QLineEdit()
        self.extra_value1 = QLineEdit()
        self.extra_value2 = QLineEdit()
        form.addWidget(QLabel("코드 *"), 0, 0)
        form.addWidget(self.value_code, 0, 1)
        form.addWidget(QLabel("코드명 *"), 0, 2)
        form.addWidget(self.value_name, 0, 3)
        form.addWidget(self.value_use, 1, 1)
        form.addWidget(QLabel("설명"), 2, 0)
        form.addWidget(self.value_description, 2, 1, 1, 3)
        form.addWidget(QLabel("추가값1"), 3, 0)
        form.addWidget(self.extra_value1, 3, 1)
        form.addWidget(QLabel("추가값2"), 3, 2)
        form.addWidget(self.extra_value2, 3, 3)
        value_layout.addLayout(form)

        buttons = QHBoxLayout()
        self.btn_new = QPushButton("코드 신규")
        self.btn_save = QPushButton("코드 저장")
        self.btn_delete = QPushButton("코드 삭제")
        buttons.addStretch()
        buttons.addWidget(self.btn_new)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_delete)
        value_layout.addLayout(buttons)
        splitter.addWidget(value_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([360, 920])

        self.category_table.itemSelectionChanged.connect(self.on_category_selected)
        self.category_table.cellClicked.connect(self.on_category_clicked)
        self.value_table.itemSelectionChanged.connect(self.on_value_selected)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset.clicked.connect(self.reset_view)
        self.search_input.returnPressed.connect(self.refresh_data)
        self.include_inactive.stateChanged.connect(self.load_categories)
        self.btn_new.clicked.connect(self.new_value)
        self.btn_save.clicked.connect(self.save_value)
        self.btn_delete.clicked.connect(self.delete_value)
        self.btn_category_new.clicked.connect(self.new_category)
        self.btn_category_save.clicked.connect(self.save_category)
        self.btn_category_delete.clicked.connect(self.delete_category)
        self.btn_close.clicked.connect(self.close_window)

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
            QLineEdit {{ background:{field}; color:{text_color}; border:1px solid {border};
                         border-radius:2px; min-height:25px; padding:2px 5px; }}
            QPushButton {{ background:{field}; color:{text_color}; border:1px solid {border};
                           border-radius:3px; min-height:28px; padding:3px 12px; }}
            QPushButton:hover {{ border-color:#0067c0; }}
            QTableWidget {{ background:{field}; color:{text_color}; gridline-color:{border};
                            border:1px solid {border}; selection-background-color:{selected};
                            selection-color:{text_color}; }}
            QHeaderView::section {{ background:{panel}; color:{text_color}; border:0;
                                    border-right:1px solid {border}; border-bottom:1px solid {border};
                                    padding:5px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"] {{ background:{field}; color:{text_color};
                         border:1px solid {border}; border-radius:3px; min-height:28px;
                         padding:3px 10px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"]:checked {{ background:{selected};
                         border:2px solid #0067c0; }}
            QCheckBox[mxmnReadable="true"]::indicator {{ width:0px; height:0px; }}
            QLabel#hint {{ background:{panel}; border:1px solid {border}; border-radius:3px;
                           padding:7px; font-weight:normal; }}
            QLabel#selectedGroup {{ font-weight:bold; padding:5px; }}
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

    def load_categories(self):
        try:
            response = httpx.get(
                f"{API_BASE_URL}/code-groups",
                params={"include_inactive": "true"},
                timeout=10,
            )
            response.raise_for_status()
            all_groups = response.json()
            existing_codes = {item.get("group_code") for item in all_groups}

            # 기존 고정 12개 분류를 최초 1회 실제 DB 그룹으로 전환한다.
            for code, name, description in PRODUCT_CODE_GROUPS:
                if code not in existing_codes:
                    created = httpx.post(
                        f"{API_BASE_URL}/code-groups",
                        json={
                            "group_code": code,
                            "group_name": name,
                            "description": description,
                            "sort_order": 0,
                            "sort_direction": "ASC",
                            "system_yn": False,
                            "use_yn": True,
                        },
                        timeout=10,
                    )
                    if created.status_code >= 400:
                        raise RuntimeError(self._error_detail(created, created.text))
            if any(code not in existing_codes for code, _, _ in PRODUCT_CODE_GROUPS):
                response = httpx.get(
                    f"{API_BASE_URL}/code-groups",
                    params={"include_inactive": "true"},
                    timeout=10,
                )
                response.raise_for_status()
                all_groups = response.json()

            rows = [
                item for item in all_groups
                if str(item.get("group_code", "")).startswith("PC")
                and (self.include_inactive.isChecked() or item.get("use_yn"))
            ]
            rows.sort(key=lambda item: item.get("group_code", ""))
            begin_list_update(self.category_table); self.category_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                self.category_table.setItem(row, 0, ListTableItem(item.get("group_name", "")))
                self.category_table.setItem(row, 1, ListTableItem(item.get("description") or ""))
                self.category_table.item(row, 0).setData(Qt.UserRole, item)
            end_list_update(self.category_table, (120, 180), (240, 420))
            if rows:
                self.category_table.selectRow(0)
        except Exception as exc:
            QMessageBox.critical(self, "분류 조회 오류", str(exc))

    def on_category_selected(self):
        row = self.category_table.currentRow()
        if row < 0 or self.category_table.item(row, 0) is None:
            return
        category = self.category_table.item(row, 0).data(Qt.UserRole)
        self.current_group_code = category["group_code"]
        self.current_group_name = category["group_name"]
        self.current_group_description = category.get("description") or ""
        self.category_code.setText(self.current_group_code)
        self.category_name.setText(self.current_group_name)
        self.category_description.setText(self.current_group_description)
        self.category_use.setChecked(bool(category.get("use_yn")))
        self.selected_group_label.setText(
            f"{self.current_group_name}  |  {self.current_group_description}"
        )
        self.new_value()
        self.load_values()

    def on_category_clicked(self, row, column):
        """사용자가 다른 분류를 직접 누르면 이전 검색조건을 해제한다."""
        if self.search_input.text():
            self.search_input.clear()
            self.search_result_label.setText("전체 조회")
            self.load_values()

    def new_category(self):
        self.current_group_code = None
        self.current_group_name = None
        self.current_group_description = None
        self.current_group_exists = False
        self.category_code.clear()
        self.category_name.clear()
        self.category_description.clear()
        self.category_use.setChecked(True)
        self.value_table.setRowCount(0)
        try:
            response = httpx.get(
                f"{API_BASE_URL}/code-groups/next-code",
                params={"prefix": "PC"},
                timeout=10,
            )
            response.raise_for_status()
            self.category_code.setText(response.json()["group_code"])
        except Exception as exc:
            QMessageBox.critical(self, "자동발번 오류", str(exc))
            return
        self.category_name.setFocus()

    def save_category(self):
        code = self.category_code.text().strip().upper()
        name = self.category_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "입력 확인", "분류명은 필수입니다.")
            return
        payload = {
            "group_code": code,
            "group_name": name,
            "description": self.category_description.text().strip() or None,
            "sort_order": 0,
            "sort_direction": "ASC",
            "system_yn": False,
            "use_yn": self.category_use.isChecked(),
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
            QMessageBox.information(self, "저장 완료", "상품 코드분류가 저장되었습니다.")
            self.load_categories()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_category(self):
        if not self.current_group_code:
            QMessageBox.warning(self, "삭제 확인", "삭제할 상품 코드분류를 선택하세요.")
            return
        first = QMessageBox.question(
            self,
            "분류 삭제 1차 확인",
            "이 분류와 소속 상세코드를 사용중지하시겠습니까?\n기존 자료 보존을 위해 물리삭제하지 않습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if first != QMessageBox.Yes:
            return
        second = QMessageBox.warning(
            self,
            "분류 삭제 최종 확인",
            f"[{self.current_group_name}] 분류를 정말 사용중지하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if second != QMessageBox.Yes:
            return
        try:
            response = httpx.delete(
                f"{API_BASE_URL}/code-groups/{self.current_group_code}", timeout=10
            )
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            self.current_group_code = None
            self.load_categories()
        except Exception as exc:
            QMessageBox.critical(self, "삭제 오류", str(exc))

    def reset_view(self):
        self.search_input.clear()
        self.search_result_label.setText("전체 조회")
        self.current_value_id = None
        self.load_categories()

    def _check_group_exists(self):
        response = httpx.get(
            f"{API_BASE_URL}/code-groups",
            params={"include_inactive": "true"},
            timeout=10,
        )
        response.raise_for_status()
        self.current_group_exists = any(
            item.get("group_code") == self.current_group_code
            for item in response.json()
        )

    def _ensure_group(self):
        self._check_group_exists()
        if self.current_group_exists:
            return
        response = httpx.post(
            f"{API_BASE_URL}/code-groups",
            json={
                "group_code": self.current_group_code,
                "group_name": self.current_group_name,
                "description": self.current_group_description,
                "sort_order": 0,
                "sort_direction": "ASC",
                "system_yn": True,
                "use_yn": True,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(self._error_detail(response, response.text))
        self.current_group_exists = True

    def refresh_data(self):
        self._set_lookup_busy(True)
        try:
            if self.current_group_code:
                self.load_values()
            else:
                self.load_categories()
        finally:
            self._set_lookup_busy(False)

    def _initial_load(self):
        self._set_lookup_busy(True)
        try:
            self.load_categories()
        finally:
            self._set_lookup_busy(False)

    def _set_lookup_busy(self, busy):
        self.btn_refresh.setEnabled(not busy)
        self.btn_refresh.setText("조회 중..." if busy else "조회")
        self.search_input.setEnabled(not busy)
        QApplication.processEvents()

    def load_values(self):
        if not self.current_group_code:
            return
        try:
            self._check_group_exists()
            if not self.current_group_exists:
                self.value_table.setRowCount(0)
                self.search_result_label.setText("검색 결과 없음")
                self.new_value()
                return
            response = httpx.get(
                f"{API_BASE_URL}/code-groups/{self.current_group_code}/values",
                params={"include_inactive": str(self.include_inactive.isChecked()).lower()},
                timeout=10,
            )
            response.raise_for_status()
            keyword = self.search_input.text().strip().lower()
            rows = []
            for item in response.json():
                searchable = " ".join(
                    str(item.get(key) or "")
                    for key in ("code", "code_name", "description")
                ).lower()
                if not keyword or keyword in searchable:
                    rows.append(item)
            begin_list_update(self.value_table); self.value_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                values = [
                    item.get("code", ""),
                    item.get("code_name", ""),
                    "사용" if item.get("use_yn") else "중지",
                    item.get("description") or "",
                ]
                for col, value in enumerate(values):
                    self.value_table.setItem(row, col, ListTableItem(str(value)))
                self.value_table.item(row, 0).setData(Qt.UserRole, item)
            end_list_update(self.value_table, (85, 130, 60, 130), (160, 320, 90, 380))
            if keyword:
                self.search_result_label.setText(
                    f"‘{self.search_input.text().strip()}’ 검색 결과 {len(rows)}건"
                )
            else:
                self.search_result_label.setText(f"전체 {len(rows)}건")
            if rows:
                self.value_table.setFocus()
        except Exception as exc:
            QMessageBox.critical(self, "조회 오류", str(exc))

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
        if not self.current_group_code:
            return
        try:
            self._check_group_exists()
            if self.current_group_exists:
                response = httpx.get(
                    f"{API_BASE_URL}/code-groups/{self.current_group_code}/values/next-code",
                    timeout=10,
                )
                response.raise_for_status()
                self.value_code.setText(response.json()["code"])
            else:
                self.value_code.setText("001")
        except Exception as exc:
            QMessageBox.critical(self, "자동발번 오류", str(exc))
            return
        self.value_name.setFocus()

    def save_value(self):
        if not self.current_group_code:
            QMessageBox.warning(self, "입력 확인", "상품 코드구분을 먼저 선택하세요.")
            return
        name = self.value_name.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 확인", "코드명은 필수입니다.")
            return
        try:
            self._ensure_group()
            code = self.value_code.text().strip().upper()
            if not code:
                response = httpx.get(
                    f"{API_BASE_URL}/code-groups/{self.current_group_code}/values/next-code",
                    timeout=10,
                )
                response.raise_for_status()
                code = response.json()["code"]
            payload = {
                "code": code,
                "code_name": name,
                "description": self.value_description.text().strip() or None,
                "sort_order": 0,
                "extra_value1": self.extra_value1.text().strip() or None,
                "extra_value2": self.extra_value2.text().strip() or None,
                "use_yn": self.value_use.isChecked(),
            }
            base = f"{API_BASE_URL}/code-groups/{self.current_group_code}/values"
            if self.current_value_id:
                response = httpx.put(
                    f"{base}/{self.current_value_id}", json=payload, timeout=10
                )
            else:
                response = httpx.post(base, json=payload, timeout=10)
            if response.status_code >= 400:
                raise RuntimeError(self._error_detail(response, response.text))
            QMessageBox.information(self, "저장 완료", "상품 공통코드가 저장되었습니다.")
            self.new_value()
            self.load_values()
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_value(self):
        if not self.current_group_code or not self.current_value_id:
            QMessageBox.warning(self, "삭제 확인", "삭제할 상세코드를 선택하세요.")
            return
        first = QMessageBox.question(
            self,
            "코드 삭제 1차 확인",
            "선택한 코드를 사용중지하시겠습니까?\n기존 상품에서 사용 중일 수 있으므로 데이터는 보존됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if first != QMessageBox.Yes:
            return
        second = QMessageBox.warning(
            self,
            "코드 삭제 최종 확인",
            f"[{self.value_code.text()} {self.value_name.text()}] 코드를 정말 사용중지하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if second != QMessageBox.Yes:
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
