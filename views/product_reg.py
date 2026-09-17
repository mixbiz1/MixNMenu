import math
import httpx
import re
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QInputDialog, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget, QMdiSubWindow, QApplication,
    QToolButton, QMenu,
)

try:
    from views.common_code_reg import API_BASE_URL, ReadableCheckBox
except ImportError:
    from common_code_reg import API_BASE_URL, ReadableCheckBox

try:
    from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update
except ImportError:
    from table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update


class ProductRegWindow(QWidget):
    """계층형 상품분류와 상품공통코드 조합을 지원하는 상품 Master 화면."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_category_id = None
        self.selected_leaf_category_id = None
        self.current_product_id = None
        self.categories = []
        self.attribute_combos = {}
        self.attribute_group_names = {}
        self.loading_product = False
        self._loading_lookup = False
        self.setWindowTitle("상품입력")
        self.resize(1400, 820)
        self._build_ui()
        self._apply_style()
        # MDI 창을 먼저 표시한 뒤 초기 자료를 조회해 클릭 반응을 즉시 보여준다.
        QTimer.singleShot(50, self.refresh_all)

    def _build_ui(self):
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("상품명")
        self.include_inactive = ReadableCheckBox("사용중지 포함")
        self.btn_search = QPushButton("조회")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_new = QPushButton("신규")
        self.btn_edit = QPushButton("수정")
        self.btn_cancel = QPushButton("취소")
        self.btn_save = QPushButton("저장")
        self.btn_delete = QPushButton("삭제")
        self.btn_close = QPushButton("닫기")
        toolbar.addWidget(QLabel("검색")); toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.include_inactive)
        shortcuts = (
            (self.btn_search, "조회 [F7]", "F7"),
            (self.btn_new, "신규 [F2]", "F2"),
            (self.btn_edit, "수정 [F3]", "F3"),
            (self.btn_delete, "삭제 [F6]", "F6"),
            (self.btn_cancel, "취소 [F5]", "F5"),
            (self.btn_save, "저장 [F4]", "F4"),
        )
        for button, text, shortcut in shortcuts:
            button.setText(text); button.setShortcut(shortcut)
        self.btn_close.setText("닫기"); self.btn_close.setShortcut("Esc")
        for button in (self.btn_search, self.btn_refresh, self.btn_new, self.btn_edit,
                       self.btn_delete, self.btn_cancel, self.btn_save, self.btn_close):
            toolbar.addWidget(button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        category_box = QGroupBox("상품분류 (대 → 중 → 소)")
        category_layout = QVBoxLayout(category_box)
        self.category_tree = QTreeWidget()
        self.category_tree.setColumnCount(1)
        self.category_tree.setHeaderLabels(["상품분류 / 세부부위"])
        self.category_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        category_layout.addWidget(self.category_tree, 1)
        category_form = QGridLayout()
        self.category_code = QLineEdit(); self.category_code.setReadOnly(True)
        self.category_code.setPlaceholderText("자동발번")
        self.category_name = QLineEdit()
        self.parent_category = QComboBox()
        self.category_description = QLineEdit()
        self.category_use = ReadableCheckBox("사용"); self.category_use.setChecked(True)
        category_form.addWidget(QLabel("분류명 *"), 0, 0); category_form.addWidget(self.category_name, 0, 1)
        category_form.addWidget(QLabel("상위분류"), 1, 0); category_form.addWidget(self.parent_category, 1, 1)
        category_form.addWidget(QLabel("설명"), 2, 0); category_form.addWidget(self.category_description, 2, 1)
        category_form.addWidget(self.category_use, 3, 1)
        category_layout.addLayout(category_form)
        category_buttons = QHBoxLayout()
        self.btn_category_new = QPushButton("분류 신규")
        self.btn_add_child = QPushButton("하위부위 추가")
        self.btn_category_save = QPushButton("분류 저장")
        self.btn_category_delete = QPushButton("분류 삭제")
        for button in (self.btn_category_new, self.btn_add_child,
                       self.btn_category_save, self.btn_category_delete):
            category_buttons.addWidget(button)
        category_layout.addLayout(category_buttons)
        splitter.addWidget(category_box)

        center = QWidget(); center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel("상품 목록"))
        self.product_table = QTableWidget(0, 2)
        self.product_table.setHorizontalHeaderLabels(["상품명", "사용"])
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.product_table, (330, 85))
        center_layout.addWidget(self.product_table)
        splitter.addWidget(center)

        detail_box = QGroupBox("상품 Master")
        detail_layout = QVBoxLayout(detail_box)
        form = QGridLayout()
        self.product_code = QLineEdit(); self.product_code.setReadOnly(True)
        self.product_code.setPlaceholderText("자동발번")
        self.product_name = QLineEdit()
        self.selected_part_label = QLabel("선택 부위: 없음")
        self.selected_part_label.setObjectName("selectedPart")
        self.product_category = QComboBox()
        self.specification = QLineEdit()
        self.tax_type = QComboBox(); self.tax_type.addItem("면세", "2"); self.tax_type.addItem("과세", "1")
        self.unit_price = QDoubleSpinBox(); self.unit_price.setRange(0, 9999999999); self.unit_price.setDecimals(0)
        self.unit_price.setSingleStep(1); self.unit_price.setGroupSeparatorShown(True)
        self.expiry_rule = QComboBox()
        self.expiry_rule.addItem("자동판단 (냉동은 2년-1일)", "AUTO")
        self.expiry_rule.addItem("냉동 2년-1일", "FROZEN_2Y")
        self.expiry_rule.addItem("상품별 지정일수-1일", "DAYS")
        self.expiry_rule.addItem("자동계산 안 함", "NONE")
        self.shelf_life_days = QSpinBox(); self.shelf_life_days.setRange(1, 5000); self.shelf_life_days.setValue(730)
        self.meat_regn_code = QLineEdit(); self.meat_regn_name = QLineEdit()
        self.product_use = ReadableCheckBox("사용"); self.product_use.setChecked(True)
        self.memo = QTextEdit(); self.memo.setMaximumHeight(70)
        form.addWidget(self.selected_part_label, 0, 0, 1, 4)
        form.addWidget(QLabel("상품명 *"), 1, 0); form.addWidget(self.product_name, 1, 1, 1, 3)
        form.addWidget(QLabel("상품분류"), 2, 0); form.addWidget(self.product_category, 2, 1, 1, 3)
        form.addWidget(QLabel("과세구분"), 3, 0); form.addWidget(self.tax_type, 3, 1)
        form.addWidget(QLabel("기본단가"), 3, 2); form.addWidget(self.unit_price, 3, 3)
        form.addWidget(QLabel("소비기한 규칙"), 4, 0); form.addWidget(self.expiry_rule, 4, 1)
        form.addWidget(QLabel("지정일수"), 4, 2); form.addWidget(self.shelf_life_days, 4, 3)
        form.addWidget(QLabel("이력부위코드"), 5, 0); form.addWidget(self.meat_regn_code, 5, 1)
        form.addWidget(QLabel("이력부위명"), 5, 2); form.addWidget(self.meat_regn_name, 5, 3)
        form.addWidget(self.product_use, 6, 1)
        form.addWidget(QLabel("메모"), 7, 0); form.addWidget(self.memo, 7, 1, 1, 3)
        detail_layout.addLayout(form)

        attributes_box = QGroupBox("상품공통코드 조합 (선택하지 않아도 단독 상품 등록 가능)")
        attributes_layout = QVBoxLayout(attributes_box)
        self.attribute_table = QTableWidget(0, 2)
        self.attribute_table.setHorizontalHeaderLabels(["코드그룹", "선택값"])
        self.attribute_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.attribute_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attribute_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        attributes_layout.addWidget(self.attribute_table)
        other_layout = QHBoxLayout()
        other_layout.addWidget(QLabel("기타 상품명"))
        self.other_name = QLineEdit()
        self.other_name.setPlaceholderText("조합 상품명 뒤에 붙일 내용을 직접 입력")
        other_layout.addWidget(self.other_name, 1)
        attributes_layout.addLayout(other_layout)
        detail_layout.addWidget(attributes_box, 1)
        splitter.addWidget(detail_box)
        splitter.setSizes([330, 460, 610])

        self.btn_search.clicked.connect(self.query_products)
        self.search.returnPressed.connect(self.query_products)
        self.btn_refresh.clicked.connect(self.refresh_all)
        self.include_inactive.stateChanged.connect(self.load_products)
        self.btn_new.clicked.connect(self.new_product)
        self.btn_edit.clicked.connect(self.edit_product)
        self.btn_cancel.clicked.connect(self.cancel_edit)
        self.btn_save.clicked.connect(self.save_product)
        self.btn_delete.clicked.connect(self.delete_product)
        self.btn_close.clicked.connect(self.close_window)
        self.category_tree.itemClicked.connect(self.on_category_selected)
        self.product_table.itemSelectionChanged.connect(self.on_product_selected)
        self.btn_category_new.clicked.connect(self.new_category)
        self.btn_add_child.clicked.connect(self.add_child_category)
        self.btn_category_save.clicked.connect(self.save_category)
        self.btn_category_delete.clicked.connect(self.delete_category)
        self.product_category.currentIndexChanged.connect(self.update_combination_name_live)
        self.expiry_rule.currentIndexChanged.connect(self._update_expiry_rule_state)
        self.other_name.textChanged.connect(self.update_combination_name_live)
        self._setup_enter_navigation()

    def _apply_style(self):
        dark = self.palette().window().color().lightness() < 128
        if dark:
            window, panel, field, text_color, border, selected = "#202124", "#292a2d", "#303134", "#f1f3f4", "#5f6368", "#174ea6"
        else:
            window, panel, field, text_color, border, selected = "#f4f6f8", "#ffffff", "#ffffff", "#111111", "#aeb6bf", "#cfe8ff"
        self.setStyleSheet(f"""
            QWidget {{ background:{window}; color:{text_color}; font-family:'맑은 고딕'; font-size:9pt; }}
            QGroupBox {{ background:{panel}; border:1px solid {border}; border-radius:4px; margin-top:10px; padding-top:8px; font-weight:bold; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}
            QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QSpinBox {{ background:{field}; color:{text_color}; border:1px solid {border}; border-radius:2px; min-height:25px; padding:2px 5px; }}
            QPushButton {{ background:{field}; color:{text_color}; border:1px solid {border}; border-radius:3px; min-height:28px; padding:3px 10px; }}
            QPushButton:pressed, QPushButton[mxmnCommandActive="true"] {{ background:#0067c0; color:#ffffff; border:2px solid #003f78; }}
            QTableWidget, QTreeWidget {{ background:{field}; color:{text_color}; gridline-color:{border}; border:1px solid {border}; selection-background-color:{selected}; selection-color:{text_color}; }}
            QHeaderView::section {{ background:{panel}; color:{text_color}; border:0; border-right:1px solid {border}; border-bottom:1px solid {border}; padding:5px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"] {{ background:{field}; color:{text_color}; border:1px solid {border}; border-radius:3px; min-height:28px; padding:3px 10px; font-weight:bold; }}
            QCheckBox[mxmnReadable="true"]:checked {{ background:{selected}; border:2px solid #0067c0; }}
            QCheckBox[mxmnReadable="true"]::indicator {{ width:0px; height:0px; }}
            QLabel#selectedPart {{ background:{selected}; border:1px solid {border};
                                  border-radius:3px; padding:7px; font-weight:bold; }}
        """)

    @staticmethod
    def _detail(response, fallback):
        try: return response.json().get("detail", fallback)
        except Exception: return fallback

    @staticmethod
    def _set_combo(combo, data):
        index = combo.findData(data)
        combo.setCurrentIndex(index if index >= 0 else 0)

    @staticmethod
    def _natural_key(value):
        """한글/영문 명칭과 숫자가 섞인 코드를 사람이 읽는 순서로 정렬한다."""
        return [(0, int(part)) if part.isdigit() else (1, part.casefold())
                for part in re.split(r"(\d+)", str(value or ""))]

    def _sort_attribute_combo(self, combo, mode):
        current_id = combo.currentData()
        entries = [
            (combo.itemText(index), combo.itemData(index),
             combo.itemData(index, Qt.UserRole + 1) or "")
            for index in range(1, combo.count())
        ]
        by_code = mode.startswith("code")
        reverse = mode.endswith("desc")
        entries.sort(
            key=lambda entry: self._natural_key(entry[2] if by_code else entry[0]),
            reverse=reverse,
        )
        combo.blockSignals(True)
        combo.clear(); combo.addItem("선택 안 함", None)
        for name, value_id, code in entries:
            combo.addItem(name, value_id)
            combo.setItemData(combo.count() - 1, code, Qt.UserRole + 1)
        self._set_combo(combo, current_id)
        combo.blockSignals(False)
        self.update_combination_name_live()

    def _attribute_selector(self, combo):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        layout.addWidget(combo, 1)
        sort_button = QToolButton()
        sort_button.setText("⇅")
        sort_button.setToolTip("정렬방식 선택")
        sort_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(sort_button)
        options = (
            ("이름 오름차순 (가나다/ABC)", "name_asc"),
            ("이름 내림차순", "name_desc"),
            ("코드 오름차순", "code_asc"),
            ("코드 내림차순", "code_desc"),
        )
        for label, mode in options:
            action = menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, selected_mode=mode: self._sort_attribute_combo(
                    combo, selected_mode
                )
            )
        sort_button.setMenu(menu)
        layout.addWidget(sort_button)
        return container

    def _setup_enter_navigation(self):
        """단일행 입력에서 Enter를 Tab처럼 다음 입력항목 이동으로 사용한다."""
        widgets = [
            self.search, self.category_name, self.parent_category,
            self.category_description, self.product_name, self.product_category,
            self.tax_type, self.unit_price,
            self.expiry_rule, self.shelf_life_days,
            self.meat_regn_code, self.meat_regn_name, self.other_name,
        ]
        for widget in widgets:
            widget.installEventFilter(self)
        for first, second in zip(widgets, widgets[1:]):
            QWidget.setTabOrder(first, second)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if obj is self.search:
                self.query_products()
            else:
                self.focusNextChild()
            return True
        return super().eventFilter(obj, event)

    def _update_expiry_rule_state(self):
        self.shelf_life_days.setEnabled(self.expiry_rule.currentData() == "DAYS")

    def refresh_all(self):
        if self._loading_lookup:
            return
        self._set_lookup_busy(True)
        try:
            self.search.clear()
            self.current_category_id = None
            self.load_categories()
            self.load_attributes()
            self.load_products()
            self.new_product()
        finally:
            self._set_lookup_busy(False)

    def query_products(self):
        if self._loading_lookup:
            return
        self._set_lookup_busy(True)
        try:
            self.load_products()
        finally:
            self._set_lookup_busy(False)

    def _set_lookup_busy(self, busy):
        self._loading_lookup = busy
        self.btn_search.setEnabled(not busy)
        self.btn_search.setText("조회 중..." if busy else "조회 [F7]")
        self.search.setEnabled(not busy)
        QApplication.processEvents()

    def load_categories(self):
        try:
            response = httpx.get(f"{API_BASE_URL}/product-categories", params={"include_inactive": "true"}, timeout=10)
            response.raise_for_status(); self.categories = response.json()
            self.category_tree.clear()
            root = QTreeWidgetItem(["전체 상품"]); root.setData(0, Qt.UserRole, None)
            self.category_tree.addTopLevelItem(root)
            items = {}
            for category in self.categories:
                if not category.get("use_yn") and not self.include_inactive.isChecked(): continue
                item = QTreeWidgetItem([category["category_name"]])
                item.setData(0, Qt.UserRole, category); items[category["category_id"]] = item
            for category in self.categories:
                item = items.get(category["category_id"])
                if item is None: continue
                parent = items.get(category.get("parent_category_id"))
                (parent.addChild(item) if parent else self.category_tree.addTopLevelItem(item))
            self.category_tree.expandAll(); self.category_tree.setCurrentItem(root)
            self._fill_category_combos()
        except Exception as exc: QMessageBox.critical(self, "분류 조회 오류", str(exc))

    def _fill_category_combos(self):
        self.parent_category.clear(); self.parent_category.addItem("상위분류 없음 (대분류)", None)
        self.product_category.clear(); self.product_category.addItem("분류 없음 (단독 상품)", None)
        parent_ids = {
            category.get("parent_category_id")
            for category in self.categories
            if category.get("parent_category_id") is not None and category.get("use_yn")
        }
        for category in self.categories:
            if not category.get("use_yn"): continue
            indent = "　" * max(0, category.get("category_level", 1) - 1)
            label = f"{indent}{category['category_name']}"
            if category["category_id"] not in parent_ids:
                self.product_category.addItem(label, category["category_id"])
            if category.get("category_level", 1) < 3:
                self.parent_category.addItem(label, category["category_id"])

    def on_category_selected(self, item, column):
        category = item.data(0, Qt.UserRole)
        self.search.clear()
        if category is None:
            self.current_category_id = None
            self.selected_leaf_category_id = None
            self.selected_part_label.setText("선택 부위: 없음 (단독 상품)")
            self.new_category(clear_selection=False)
        else:
            self.current_category_id = category["category_id"]
            has_children = any(
                item.get("parent_category_id") == self.current_category_id
                and item.get("use_yn")
                for item in self.categories
            )
            if has_children:
                self.selected_leaf_category_id = None
                self.selected_part_label.setText(
                    f"선택 분류: {category['category_name']} / 최종 세부부위를 선택하세요"
                )
            else:
                self.selected_leaf_category_id = self.current_category_id
                self.selected_part_label.setText(f"선택 부위: {category['category_name']}")
                if self.current_product_id is None:
                    self._set_combo(self.product_category, self.selected_leaf_category_id)
                    self.update_combination_name_live()
            self.category_code.setText(category["category_code"])
            self.category_name.setText(category["category_name"])
            self.category_description.setText(category.get("description") or "")
            self.category_use.setChecked(bool(category.get("use_yn")))
            self._set_combo(self.parent_category, category.get("parent_category_id"))
        self.load_products()

    def add_child_category(self):
        if not self.current_category_id:
            QMessageBox.warning(self, "하위부위 추가", "상위 상품분류를 먼저 선택하세요.")
            return
        parent = next(
            (item for item in self.categories if item["category_id"] == self.current_category_id),
            None,
        )
        if not parent or parent.get("category_level", 1) >= 3:
            QMessageBox.warning(self, "하위부위 추가", "상품분류는 최대 3단계까지만 만들 수 있습니다.")
            return
        name, accepted = QInputDialog.getText(
            self,
            "하위부위 추가",
            f"[{parent['category_name']}] 아래에 추가할 세부부위명:",
        )
        name = name.strip()
        if not accepted or not name:
            return
        try:
            code_response = httpx.get(
                f"{API_BASE_URL}/product-categories/next-code", timeout=10
            )
            code_response.raise_for_status()
            response = httpx.post(
                f"{API_BASE_URL}/product-categories",
                json={
                    "category_code": code_response.json()["category_code"],
                    "category_name": name,
                    "parent_category_id": self.current_category_id,
                    "description": None,
                    "sort_order": 0,
                    "use_yn": True,
                },
                timeout=10,
            )
            if response.status_code >= 400:
                raise RuntimeError(self._detail(response, response.text))
            self.load_categories()
        except Exception as exc:
            QMessageBox.critical(self, "하위부위 저장 오류", str(exc))

    def new_category(self, clear_selection=True):
        self.current_category_id = None
        self.category_code.clear(); self.category_name.clear(); self.category_description.clear()
        self.parent_category.setCurrentIndex(0); self.category_use.setChecked(True)
        try:
            response = httpx.get(f"{API_BASE_URL}/product-categories/next-code", timeout=10)
            response.raise_for_status(); self.category_code.setText(response.json()["category_code"])
        except Exception as exc: QMessageBox.critical(self, "자동발번 오류", str(exc))
        self.category_name.setFocus()

    def save_category(self):
        name = self.category_name.text().strip()
        if not name: QMessageBox.warning(self, "입력 확인", "분류명은 필수입니다."); return
        payload = {"category_code": self.category_code.text().strip(), "category_name": name,
                   "parent_category_id": self.parent_category.currentData(),
                   "description": self.category_description.text().strip() or None,
                   "sort_order": 0, "use_yn": self.category_use.isChecked()}
        try:
            if self.current_category_id:
                response = httpx.put(f"{API_BASE_URL}/product-categories/{self.current_category_id}", json=payload, timeout=10)
            else: response = httpx.post(f"{API_BASE_URL}/product-categories", json=payload, timeout=10)
            if response.status_code >= 400: raise RuntimeError(self._detail(response, response.text))
            self.load_categories(); QMessageBox.information(self, "저장 완료", "상품분류가 저장되었습니다.")
        except Exception as exc: QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_category(self):
        if not self.current_category_id: QMessageBox.warning(self, "삭제 확인", "삭제할 분류를 선택하세요."); return
        if QMessageBox.question(self, "분류 삭제 1차 확인", "선택 분류와 하위분류를 사용중지하시겠습니까?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        if QMessageBox.warning(self, "분류 삭제 최종 확인", "분류를 참조하는 상품은 보존됩니다. 정말 진행하시겠습니까?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/product-categories/{self.current_category_id}", timeout=10)
            if response.status_code >= 400: raise RuntimeError(self._detail(response, response.text))
            self.load_categories(); self.load_products()
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", str(exc))

    def load_attributes(self):
        try:
            response = httpx.get(f"{API_BASE_URL}/code-groups", timeout=10); response.raise_for_status()
            aliases = {
                "브랜드": "브랜드", "등급": "등급", "원산지": "원산지",
                "EST NO": "공장번호", "포장상태": "포장",
            }
            order = {name: index for index, name in enumerate(aliases)}
            groups = [
                g for g in response.json()
                if g.get("group_code", "").startswith("PC")
                and g.get("group_name") in aliases
            ]
            groups.sort(key=lambda g: order[g["group_name"]])
            self.attribute_table.setRowCount(len(groups)); self.attribute_combos = {}
            self.attribute_group_names = {}
            def fetch_values(group):
                values = httpx.get(
                    f"{API_BASE_URL}/code-groups/{group['group_code']}/values",
                    timeout=10,
                )
                values.raise_for_status()
                return values.json()

            with ThreadPoolExecutor(max_workers=max(1, min(5, len(groups)))) as executor:
                group_values = list(executor.map(fetch_values, groups))

            for row, (group, values) in enumerate(zip(groups, group_values)):
                self.attribute_table.setItem(row, 0, QTableWidgetItem(aliases[group["group_name"]]))
                combo = QComboBox(); combo.addItem("선택 안 함", None)
                values.sort(key=lambda value: self._natural_key(value.get("code_name")))
                for value in values:
                    combo.addItem(value["code_name"], value["code_value_id"])
                    combo.setItemData(combo.count() - 1, value.get("code") or "", Qt.UserRole + 1)
                self.attribute_table.setCellWidget(row, 1, self._attribute_selector(combo))
                self.attribute_combos[group["group_code"]] = combo
                self.attribute_group_names[group["group_code"]] = group["group_name"]
                combo.currentIndexChanged.connect(self.update_combination_name_live)
        except Exception as exc: QMessageBox.critical(self, "상품공통코드 조회 오류", str(exc))

    def load_products(self):
        try:
            params = {"search": self.search.text().strip(), "include_inactive": str(self.include_inactive.isChecked()).lower()}
            if self.current_category_id: params["category_id"] = self.current_category_id
            response = httpx.get(f"{API_BASE_URL}/products", params=params, timeout=10); response.raise_for_status()
            rows = response.json(); category_names = {c["category_id"]: c["category_name"] for c in self.categories}
            begin_list_update(self.product_table); self.product_table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                values = [item.get("product_name", ""), "☑ 사용" if item.get("use_yn") else "□ 중지"]
                for col, value in enumerate(values): self.product_table.setItem(row, col, ListTableItem(str(value)))
                self.product_table.item(row, 0).setData(Qt.UserRole, item)
            end_list_update(self.product_table, (200, 75), (430, 100))
        except Exception as exc: QMessageBox.critical(self, "상품 조회 오류", str(exc))

    def new_product(self):
        self.loading_product = True
        try:
            self.current_product_id = None
            for widget in (self.product_code, self.product_name, self.specification, self.meat_regn_code, self.meat_regn_name): widget.clear()
            self.memo.clear(); self.product_category.setCurrentIndex(0); self.tax_type.setCurrentIndex(0)
            self.other_name.clear()
            if self.selected_leaf_category_id is not None:
                self._set_combo(self.product_category, self.selected_leaf_category_id)
            self.unit_price.setValue(0); self.product_use.setChecked(True)
            self._set_combo(self.expiry_rule, "AUTO"); self.shelf_life_days.setValue(730)
            for combo in self.attribute_combos.values(): combo.setCurrentIndex(0)
        finally:
            self.loading_product = False
        try:
            response = httpx.get(f"{API_BASE_URL}/products/next-code", timeout=10); response.raise_for_status()
            self.product_code.setText(response.json()["product_code"])
        except Exception as exc: QMessageBox.critical(self, "자동발번 오류", str(exc))
        self.update_combination_name_live()
        self.product_name.setFocus()

    def edit_product(self):
        if not self.current_product_id:
            QMessageBox.warning(self, "수정 확인", "수정할 상품을 먼저 선택하세요.")
            return
        self.product_name.setFocus()

    def cancel_edit(self):
        row = self.product_table.currentRow()
        if row >= 0 and self.product_table.item(row, 0) is not None:
            self.on_product_selected()
        else:
            self.new_product()

    def on_product_selected(self):
        row = self.product_table.currentRow()
        if row < 0 or self.product_table.item(row, 0) is None: return
        self.loading_product = True
        try:
            item = self.product_table.item(row, 0).data(Qt.UserRole); self.current_product_id = item["product_id"]
            self.product_code.setText(item["product_code"]); self.product_name.setText(item["product_name"])
            self.specification.setText(item.get("specification") or ""); self._set_combo(self.product_category, item.get("category_id"))
            category_name = next(
                (category["category_name"] for category in self.categories
                 if category["category_id"] == item.get("category_id")),
                "없음 (단독 상품)",
            )
            self.selected_part_label.setText(f"선택 부위: {category_name}")
            self._set_combo(self.tax_type, item.get("tax_type", "2")); self.unit_price.setValue(float(item.get("unit_price") or 0))
            self._set_combo(self.expiry_rule, item.get("expiry_rule", "AUTO"))
            self.shelf_life_days.setValue(int(item.get("shelf_life_days") or 730)); self._update_expiry_rule_state()
            self.meat_regn_code.setText(item.get("meat_regn_code") or ""); self.meat_regn_name.setText(item.get("meat_regn_name") or "")
            self.memo.setPlainText(item.get("memo") or ""); self.product_use.setChecked(bool(item.get("use_yn")))
            self.other_name.clear()
            selected = set(item.get("code_value_ids") or [])
            for combo in self.attribute_combos.values():
                combo.setCurrentIndex(0)
                for index in range(combo.count()):
                    if combo.itemData(index) in selected: combo.setCurrentIndex(index); break
        finally:
            self.loading_product = False

    def update_combination_name_live(self, *args):
        if self.loading_product:
            return
        selected_by_name = {
            self.attribute_group_names.get(code): combo.currentText()
            for code, combo in self.attribute_combos.items()
            if combo.currentData() is not None
        }
        part_name = self.product_category.currentText().strip()
        if self.product_category.currentData() is None:
            part_name = ""
        names = [
            selected_by_name.get("브랜드", ""),
            selected_by_name.get("등급", ""),
            part_name,
            selected_by_name.get("원산지", ""),
            selected_by_name.get("EST NO", ""),
            selected_by_name.get("포장상태", ""),
            self.other_name.text().strip(),
        ]
        names = [name for name in names if name]
        if names: self.product_name.setText(" ".join(names))

    def save_product(self):
        if self.current_product_id is None and self.selected_leaf_category_id is not None:
            self._set_combo(self.product_category, self.selected_leaf_category_id)
        if self.current_product_id is None and self.current_category_id is not None and self.selected_leaf_category_id is None:
            QMessageBox.warning(self, "입력 확인", "상품을 등록할 최종 세부부위를 선택하세요.")
            return
        name = self.product_name.text().strip()
        if not name: QMessageBox.warning(self, "입력 확인", "상품명은 필수입니다."); return
        payload = {"product_code": self.product_code.text().strip(), "product_name": name,
                   "category_id": self.product_category.currentData(), "specification": self.specification.text().strip() or None,
                   "meat_regn_code": self.meat_regn_code.text().strip() or None, "meat_regn_name": self.meat_regn_name.text().strip() or None,
                   "tax_type": self.tax_type.currentData(), "unit_price": math.ceil(self.unit_price.value()),
                   "expiry_rule": self.expiry_rule.currentData(),
                   "shelf_life_days": self.shelf_life_days.value() if self.expiry_rule.currentData() == "DAYS" else None,
                   "memo": self.memo.toPlainText().strip() or None, "use_yn": self.product_use.isChecked(),
                   "code_value_ids": [combo.currentData() for combo in self.attribute_combos.values() if combo.currentData() is not None]}
        try:
            if self.current_product_id: response = httpx.put(f"{API_BASE_URL}/products/{self.current_product_id}", json=payload, timeout=10)
            else: response = httpx.post(f"{API_BASE_URL}/products", json=payload, timeout=10)
            if response.status_code >= 400: raise RuntimeError(self._detail(response, response.text))
            QMessageBox.information(self, "저장 완료", "상품이 저장되었습니다."); self.load_products(); self.new_product()
        except Exception as exc: QMessageBox.critical(self, "저장 오류", str(exc))

    def delete_product(self):
        if not self.current_product_id: QMessageBox.warning(self, "삭제 확인", "삭제할 상품을 선택하세요."); return
        if QMessageBox.question(self, "상품 삭제 1차 확인", "선택 상품을 사용중지하시겠습니까?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        if QMessageBox.warning(self, "상품 삭제 최종 확인", "입출고 참조를 위해 데이터는 보존됩니다. 정말 진행하시겠습니까?", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        try:
            response = httpx.delete(f"{API_BASE_URL}/products/{self.current_product_id}", timeout=10)
            if response.status_code >= 400: raise RuntimeError(self._detail(response, response.text))
            self.load_products(); self.new_product()
        except Exception as exc: QMessageBox.critical(self, "삭제 오류", str(exc))

    def close_window(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QMdiSubWindow): parent.close(); return
            parent = parent.parentWidget()
        self.close()
