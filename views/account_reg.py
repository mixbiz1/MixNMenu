from api_config import API_BASE_URL
import webbrowser
import api_client as httpx
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import (
    QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel,QLineEdit,QTextEdit,
    QPushButton,QComboBox,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,
    QSplitter,QAbstractItemView,QMdiSubWindow,QCheckBox,QDialog,QDialogButtonBox,QApplication
)
from app_context import app_context
from views.table_utils import ListTableItem, begin_list_update, configure_list_table, end_list_update


class ReadableCheckBox(QCheckBox):
    """Light/Dark Mode에서 상태가 즉시 구분되는 MXMN 공통 체크박스."""
    def __init__(self,label,parent=None):
        super().__init__(parent)
        self._label=label
        self.setProperty("mxmnReadable",True)
        self.setAccessibleName(label)
        self.toggled.connect(self._update_state_text)
        self._update_state_text(self.isChecked())

    def _update_state_text(self,checked):
        self.setText(f"{'☑' if checked else '□'} {self._label}")

class AddressDialog(QDialog):
    """
    주소검색 보조창.
    별도 유료/인증 API 키를 코드에 박아 넣지 않는다.
    '주소검색 열기'로 국가 주소검색 사이트를 열고, 검색한 우편번호/주소를
    이 작은 창에 붙여 넣으면 원 화면에 즉시 반영한다.
    """
    def __init__(self,parent=None,zip_code="",address=""):
        super().__init__(parent)
        self.setWindowTitle("우편번호 / 주소 찾기")
        self.resize(570,190)
        lay=QVBoxLayout(self)
        note=QLabel("① 주소검색 열기 → ② 검색 결과의 우편번호와 주소 입력 → ③ 적용")
        lay.addWidget(note)
        btn=QPushButton("주소검색 열기")
        btn.clicked.connect(lambda: webbrowser.open("https://www.juso.go.kr/openIndexPage.do"))
        lay.addWidget(btn)
        g=QGridLayout()
        self.zip_edit=QLineEdit(zip_code); self.addr_edit=QLineEdit(address)
        g.addWidget(QLabel("우편번호"),0,0); g.addWidget(self.zip_edit,0,1)
        g.addWidget(QLabel("주소"),1,0); g.addWidget(self.addr_edit,1,1)
        lay.addLayout(g)
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

class AccountRegWindow(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.current_account_id=None
        self._loading_accounts=False
        self.setWindowTitle("거래처입력")
        self.resize(1280,760)
        self._build_ui()
        self._apply_style()
        self._setup_enter_navigation()
        # MDI 창을 먼저 표시한 뒤 초기 자료를 조회해 클릭 반응을 즉시 보여준다.
        QTimer.singleShot(50, self.load_accounts)

    def _field(self): return QLineEdit()

    def _build_ui(self):
        root=QVBoxLayout(self)
        top=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText("거래처명 / 코드 / 사업자번호")
        self.include_stopped=ReadableCheckBox("거래중단 포함")
        self.btn_search=QPushButton("조회"); self.btn_refresh=QPushButton("새로고침"); self.btn_new=QPushButton("신규")
        self.btn_save=QPushButton("저장"); self.btn_close=QPushButton("닫기")
        top.addWidget(QLabel("검색")); top.addWidget(self.search,1); top.addWidget(self.include_stopped)
        for b in (self.btn_search,self.btn_refresh,self.btn_new,self.btn_save,self.btn_close): top.addWidget(b)
        root.addLayout(top)

        sp=QSplitter(Qt.Horizontal); root.addWidget(sp,1)

        # 목록 폭 확대: 거래처명 식별이 최우선
        left=QWidget(); ll=QVBoxLayout(left); ll.addWidget(QLabel("거래처 목록"))
        self.table=QTableWidget(0,3)
        self.table.setHorizontalHeaderLabels(["거래처명","코드","사업자번호"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_list_table(self.table, (300, 110, 150))
        self.table.setMinimumWidth(430)
        ll.addWidget(self.table); sp.addWidget(left)

        right=QWidget(); rl=QVBoxLayout(right)
        master=QGroupBox("거래처 공통정보 (회사 간 공유)"); g=QGridLayout(master)

        self.account_code=self._field(); self.account_code.setReadOnly(True); self.account_code.setPlaceholderText("자동발번")
        self.account_name=self._field(); self.biz_no=self._field(); self.corp_no=self._field()
        self.ceo_name=self._field(); self.zip_code=self._field(); self.address=self._field()
        self.uptae=self._field(); self.upjong=self._field(); self.phone=self._field(); self.fax=self._field()
        self.contact_name=self._field(); self.tax_email=self._field()
        self.account_info=self._field()
        self.btn_address=QPushButton("주소찾기"); self.btn_address.setMaximumWidth(90)

        # 간소화된 실사용 항목
        g.addWidget(QLabel("거래처코드"),0,0); g.addWidget(self.account_code,0,1)
        g.addWidget(QLabel("거래처명 *"),0,2); g.addWidget(self.account_name,0,3)
        g.addWidget(QLabel("사업자번호"),1,0); g.addWidget(self.biz_no,1,1)
        g.addWidget(QLabel("법인번호"),1,2); g.addWidget(self.corp_no,1,3)
        g.addWidget(QLabel("대표자"),2,0); g.addWidget(self.ceo_name,2,1)
        g.addWidget(QLabel("우편번호"),2,2)
        z=QHBoxLayout(); z.addWidget(self.zip_code); z.addWidget(self.btn_address); g.addLayout(z,2,3)
        g.addWidget(QLabel("주소"),3,0); g.addWidget(self.address,3,1,1,3)
        g.addWidget(QLabel("업태"),4,0); g.addWidget(self.uptae,4,1)
        g.addWidget(QLabel("업종"),4,2); g.addWidget(self.upjong,4,3)
        g.addWidget(QLabel("전화"),5,0); g.addWidget(self.phone,5,1)
        g.addWidget(QLabel("팩스"),5,2); g.addWidget(self.fax,5,3)
        g.addWidget(QLabel("담당자"),6,0); g.addWidget(self.contact_name,6,1)
        g.addWidget(QLabel("전자(세금)계산서 이메일"),6,2); g.addWidget(self.tax_email,6,3)
        g.addWidget(QLabel("계좌정보"),7,0); g.addWidget(self.account_info,7,1,1,3)
        rl.addWidget(master)

        company=QGroupBox("현재 업무회사별 거래정보"); cg=QGridLayout(company)
        self.company_label=QLabel(f"{app_context.company_code} {app_context.company_name}")
        self.trade_status=QComboBox(); self.trade_status.addItem("거래처","TRADE"); self.trade_status.addItem("정보등록만","INFO")
        self.trade_type=QComboBox()
        for label,data in [("일반","GENERAL"),("계약","CONTRACT"),("유통","DISTRIBUTION"),
                           ("BL양수도","BL_TRANSFER"),("보증금","DEPOSIT"),("기타","OTHER")]:
            self.trade_type.addItem(label,data)
        self.purchase_yn=ReadableCheckBox("매입거래")
        self.sales_yn=ReadableCheckBox("매출거래")
        self.invoice_issue_yn=ReadableCheckBox("(세금)계산서 발행대상")
        self.trade_stop_yn=ReadableCheckBox("거래중단")
        self.trade_stop_yn.setToolTip("체크하면 일반 매입/매출 거래처 조회에서 제외됩니다.")

        cg.addWidget(QLabel("업무회사"),0,0); cg.addWidget(self.company_label,0,1)
        cg.addWidget(QLabel("거래상태"),0,2); cg.addWidget(self.trade_status,0,3)
        cg.addWidget(QLabel("업무유형"),1,0); cg.addWidget(self.trade_type,1,1)
        roles=QHBoxLayout()
        roles.setContentsMargins(0,0,0,0)
        roles.setSpacing(18)
        roles.addWidget(self.purchase_yn)
        roles.addWidget(self.sales_yn)
        roles.addStretch()
        cg.addWidget(QLabel("거래역할"),1,2); cg.addLayout(roles,1,3)
        cg.addWidget(QLabel("계산서"),2,0); cg.addWidget(self.invoice_issue_yn,2,1)
        cg.addWidget(QLabel("거래상태 관리"),2,2); cg.addWidget(self.trade_stop_yn,2,3)
        cg.addWidget(QLabel("※ 계산서 발행대상은 향후 단건발행 완료 건을 월합산에서 자동 제외하여 중복발행을 방지합니다."),3,0,1,4)
        rl.addWidget(company)

        memo=QGroupBox("공통 메모"); ml=QVBoxLayout(memo)
        self.memo=QTextEdit(); self.memo.setMaximumHeight(95); ml.addWidget(self.memo); rl.addWidget(memo)

        sp.addWidget(right)
        sp.setStretchFactor(0,3); sp.setStretchFactor(1,7)
        sp.setSizes([470,1050])

        self.btn_search.clicked.connect(self.load_accounts)
        self.btn_refresh.clicked.connect(self.reset_view)
        self.include_stopped.stateChanged.connect(self.load_accounts)
        self.search.returnPressed.connect(self.load_accounts)
        self.btn_new.clicked.connect(self.new_account)
        self.btn_save.clicked.connect(self.save_account)
        self.btn_close.clicked.connect(self.close_window)
        self.table.itemSelectionChanged.connect(self.on_selected)
        self.btn_address.clicked.connect(self.find_address)

    def _setup_enter_navigation(self):
        self.nav=[self.account_name,self.biz_no,self.corp_no,self.ceo_name,self.zip_code,self.address,
                  self.uptae,self.upjong,self.phone,self.fax,self.contact_name,self.tax_email,self.account_info,
                  self.trade_status,self.trade_type,self.purchase_yn,self.sales_yn,self.invoice_issue_yn,self.trade_stop_yn]
        for w in self.nav: w.installEventFilter(self)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Return,Qt.Key_Enter) and obj in self.nav:
            i=self.nav.index(obj)
            (self.nav[i+1] if i+1<len(self.nav) else self.btn_save).setFocus()
            return True
        return super().eventFilter(obj,event)

    def _is_dark_mode(self):
        """
        현재 Qt 애플리케이션 팔레트를 기준으로 Light/Dark Mode를 판별한다.
        Windows/Qt 테마가 바뀌어도 화면별 비즈니스 로직은 변경하지 않는다.
        """
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False

        window_color = app.palette().window().color()
        return window_color.lightness() < 128

    def _apply_style(self):
        """
        MXMN 공통 방향:
        - Light/Dark Mode 모두 동일한 레이아웃/기능 유지
        - 입력칸, 표, 버튼, 체크박스의 대비를 명확하게 유지
        - 체크박스는 상태기호와 배경 대비를 함께 사용해 OS 테마와 무관하게 구분한다.
        """
        dark = self._is_dark_mode()

        if dark:
            colors = {
                "window": "#202124",
                "panel": "#292a2d",
                "input": "#303134",
                "text": "#f1f3f4",
                "muted": "#bdc1c6",
                "border": "#5f6368",
                "header": "#35363a",
                "hover": "#3c4043",
                "selected": "#174ea6",
                "selected_text": "#ffffff",
                "focus": "#8ab4f8",
                "disabled": "#252629",
                "disabled_text": "#80868b",
            }
        else:
            colors = {
                "window": "#f4f6f8",
                "panel": "#f7f8fa",
                "input": "#ffffff",
                "text": "#111111",
                "muted": "#5f6368",
                "border": "#aeb6bf",
                "header": "#e9edf2",
                "hover": "#e8f2fc",
                "selected": "#cfe8ff",
                "selected_text": "#000000",
                "focus": "#0067c0",
                "disabled": "#eceff2",
                "disabled_text": "#73777c",
            }

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {colors["window"]};
                color: {colors["text"]};
                font-family: '맑은 고딕';
                font-size: 9pt;
            }}

            QLabel {{
                background-color: transparent;
                color: {colors["text"]};
            }}

            QGroupBox {{
                background-color: {colors["panel"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 4px;
                margin-top: 11px;
                padding-top: 9px;
                font-weight: bold;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 9px;
                padding: 0 4px;
                background-color: {colors["panel"]};
                color: {colors["text"]};
            }}

            QLineEdit,
            QComboBox,
            QTextEdit {{
                background-color: {colors["input"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 2px;
                min-height: 25px;
                padding: 2px 5px;
                selection-background-color: {colors["selected"]};
                selection-color: {colors["selected_text"]};
            }}

            QLineEdit:focus,
            QComboBox:focus,
            QTextEdit:focus {{
                border: 1px solid {colors["focus"]};
            }}

            QLineEdit:read-only {{
                background-color: {colors["disabled"]};
                color: {colors["disabled_text"]};
            }}

            QComboBox QAbstractItemView {{
                background-color: {colors["input"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                selection-background-color: {colors["selected"]};
                selection-color: {colors["selected_text"]};
            }}

            QPushButton {{
                background-color: {colors["input"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                border-radius: 3px;
                min-height: 28px;
                padding: 3px 12px;
            }}

            QPushButton:hover {{
                background-color: {colors["hover"]};
                border: 1px solid {colors["focus"]};
            }}

            QPushButton:focus {{
                border: 1px solid {colors["focus"]};
            }}

            QPushButton:pressed {{
                padding-left: 13px;
                padding-top: 4px;
            }}

            QTableWidget {{
                background-color: {colors["input"]};
                alternate-background-color: {colors["panel"]};
                color: {colors["text"]};
                gridline-color: {colors["border"]};
                border: 1px solid {colors["border"]};
                selection-background-color: {colors["selected"]};
                selection-color: {colors["selected_text"]};
            }}

            QTableWidget::item:selected {{
                background-color: {colors["selected"]};
                color: {colors["selected_text"]};
            }}

            QHeaderView::section {{
                background-color: {colors["header"]};
                color: {colors["text"]};
                border: 0px;
                border-right: 1px solid {colors["border"]};
                border-bottom: 1px solid {colors["border"]};
                padding: 5px;
                font-weight: bold;
            }}

            QCheckBox {{
                background-color: transparent;
                color: {colors["text"]};
                spacing: 8px;
                min-height: 24px;
                padding: 1px 2px;
            }}

            QCheckBox:hover {{
                color: {colors["focus"]};
            }}

            QCheckBox[mxmnReadable="true"] {{
                background-color: {colors["input"]};
                border: 1px solid {colors["border"]};
                border-radius: 4px;
                min-height: 24px;
                padding: 2px 8px;
                font-weight: 600;
            }}

            QCheckBox[mxmnReadable="true"]:checked {{
                background-color: {colors["selected"]};
                color: {colors["selected_text"]};
                border: 2px solid {colors["focus"]};
                padding: 1px 7px;
            }}

            QCheckBox[mxmnReadable="true"]:hover {{
                background-color: {colors["hover"]};
                border-color: {colors["focus"]};
            }}

            QCheckBox[mxmnReadable="true"]:checked:hover {{
                background-color: {colors["selected"]};
            }}

            QCheckBox[mxmnReadable="true"]:focus {{
                border-color: {colors["focus"]};
            }}

            QCheckBox[mxmnReadable="true"]::indicator {{
                width: 0px;
                height: 0px;
            }}

            QSplitter::handle {{
                background-color: {colors["border"]};
                width: 1px;
            }}

            QToolTip {{
                background-color: {colors["input"]};
                color: {colors["text"]};
                border: 1px solid {colors["border"]};
                padding: 4px;
            }}
            """
        )

    def _set_combo(self,combo,data):
        i=combo.findData(data); combo.setCurrentIndex(i if i>=0 else 0)

    def find_address(self):
        d=AddressDialog(self,self.zip_code.text(),self.address.text())
        if d.exec()==QDialog.Accepted:
            self.zip_code.setText(d.zip_edit.text().strip())
            self.address.setText(d.addr_edit.text().strip())
            self.address.setFocus()

    def load_accounts(self):
        if self._loading_accounts:
            return
        self._loading_accounts=True
        self.btn_search.setEnabled(False)
        self.btn_search.setText("조회 중...")
        QApplication.processEvents()
        try:
            # 거래처 등록 화면은 공통 Master 전체를 보되, 회사관계가 있고 중단된 거래처는 기본 제외
            include_stopped=self.include_stopped.isChecked()
            with ThreadPoolExecutor(max_workers=3) as executor:
                master_future=executor.submit(httpx.get,f"{API_BASE_URL}/accounts",timeout=10)
                active_future=None
                linked_future=None
                if not include_stopped:
                    active_future=executor.submit(
                        httpx.get,
                        f"{API_BASE_URL}/companies/{app_context.company_code}/accounts",
                        params={"include_stopped":"false"},timeout=10,
                    )
                    linked_future=executor.submit(
                        httpx.get,
                        f"{API_BASE_URL}/companies/{app_context.company_code}/accounts",
                        params={"include_stopped":"true","include_inactive":"true"},timeout=10,
                    )
                r=master_future.result()
                cr=active_future.result() if active_future else None
                allcr=linked_future.result() if linked_future else None
            r.raise_for_status()
            rows=r.json()
            if not include_stopped:
                try:
                    if cr is not None and cr.status_code==200:
                        allowed={x["account_id"] for x in cr.json()}
                        # 아직 회사관계가 없는 공통 Master도 등록/연결을 위해 표시
                        linked={x["account_id"] for x in allcr.json()} if allcr is not None and allcr.status_code==200 else set()
                        rows=[x for x in rows if x["account_id"] in allowed or x["account_id"] not in linked]
                except Exception:
                    pass
            q=self.search.text().strip().lower()
            if q:
                rows=[x for x in rows if q in str(x.get("account_name","")).lower()
                      or q in str(x.get("account_code","")).lower()
                      or q in str(x.get("biz_no","")).lower()]
            begin_list_update(self.table); self.table.setRowCount(len(rows))
            for row,x in enumerate(rows):
                for col,val in enumerate([x.get("account_name",""),x.get("account_code",""),x.get("biz_no","")]):
                    self.table.setItem(row,col,ListTableItem(str(val or "")))
                self.table.item(row,0).setData(Qt.UserRole,x.get("account_id"))
            end_list_update(self.table, (180, 90, 120), (380, 140, 190))
        except Exception as e:
            QMessageBox.critical(self,"조회 오류",str(e))
        finally:
            self._loading_accounts=False
            self.btn_search.setEnabled(True)
            self.btn_search.setText("조회")

    def reset_view(self):
        self.search.clear()
        self.table.clearSelection()
        self.load_accounts()

    def new_account(self):
        self.current_account_id=None
        for w in [self.account_code,self.account_name,self.biz_no,self.corp_no,self.ceo_name,self.zip_code,self.address,
                  self.uptae,self.upjong,self.phone,self.fax,self.contact_name,self.tax_email,self.account_info]:
            w.clear()
        self.memo.clear()
        self._set_combo(self.trade_status,"TRADE"); self._set_combo(self.trade_type,"GENERAL")
        self.purchase_yn.setChecked(True); self.sales_yn.setChecked(True)
        self.invoice_issue_yn.setChecked(True); self.trade_stop_yn.setChecked(False)
        try:
            r=httpx.get(f"{API_BASE_URL}/accounts/next-code",timeout=10); r.raise_for_status()
            self.account_code.setText(r.json()["account_code"])
        except Exception as e:
            QMessageBox.warning(self,"자동발번 오류",str(e))
        self.account_name.setFocus()

    def _master_payload(self):
        # 기존 V2 DB 컬럼은 삭제하지 않고, 화면에서 안 쓰는 값은 기존 호환용 null/빈값으로 둔다.
        return dict(
            account_code=self.account_code.text().strip(), account_name=self.account_name.text().strip(),
            biz_no=self.biz_no.text().strip() or None, corp_no=self.corp_no.text().strip() or None,
            ceo_name=self.ceo_name.text().strip() or None, zip_code=self.zip_code.text().strip() or None,
            address=self.address.text().strip() or None, address_detail=None,
            uptae=self.uptae.text().strip() or None, upjong=self.upjong.text().strip() or None,
            phone=self.phone.text().strip() or None, fax=self.fax.text().strip() or None,
            contact_name=self.contact_name.text().strip() or None, contact_mobile=None,
            tax_email=self.tax_email.text().strip() or None,
            bank_name=None, bank_account_no=self.account_info.text().strip() or None, bank_account_holder=None,
            meatwatch_cust_no=None, memo=self.memo.toPlainText().strip() or None, use_yn=True)

    def _company_payload(self):
        # 기존 세부 계산서 필드는 향후 계산서 모듈에서 사용 가능하도록 유지하되 UI에서는 단순 체크만 노출
        return dict(
            trade_status=self.trade_status.currentData(), trade_type=self.trade_type.currentData(),
            purchase_yn=self.purchase_yn.isChecked(), sales_yn=self.sales_yn.isChecked(),
            tax_doc_type="NONE", sales_tax_auto_yn=False, purchase_tax_manage_yn=False,
            trade_stop_yn=self.trade_stop_yn.isChecked(),
            invoice_issue_yn=self.invoice_issue_yn.isChecked(),
            use_yn=True, memo=None)

    def save_account(self):
        if not self.account_name.text().strip():
            QMessageBox.warning(self,"입력 확인","거래처명은 필수입니다."); self.account_name.setFocus(); return
        if self.invoice_issue_yn.isChecked() and not self.sales_yn.isChecked():
            QMessageBox.warning(self,"설정 확인","(세금)계산서 발행대상은 '매출거래' 거래처에만 설정할 수 있습니다."); return
        try:
            if self.current_account_id:
                r=httpx.put(f"{API_BASE_URL}/accounts/{self.current_account_id}",json=self._master_payload(),timeout=10)
            else:
                r=httpx.post(f"{API_BASE_URL}/accounts",json=self._master_payload(),timeout=10)
            r.raise_for_status(); self.current_account_id=r.json()["account_id"]
            cr=httpx.post(f"{API_BASE_URL}/companies/{app_context.company_code}/accounts/{self.current_account_id}",
                          json=self._company_payload(),timeout=10)
            cr.raise_for_status()
            QMessageBox.information(self,"저장 완료","거래처 정보가 저장되었습니다.")
            self.load_accounts()
        except Exception as e:
            detail=""
            try: detail=r.json().get("detail","")
            except Exception: pass
            QMessageBox.critical(self,"저장 오류",detail or str(e))

    def on_selected(self):
        items=self.table.selectedItems()
        if not items: return
        account_id=self.table.item(self.table.currentRow(),0).data(Qt.UserRole)
        try:
            r=httpx.get(f"{API_BASE_URL}/accounts/{account_id}",timeout=10); r.raise_for_status(); x=r.json()
            self.current_account_id=account_id
            mapping={"account_code":self.account_code,"account_name":self.account_name,"biz_no":self.biz_no,
                     "corp_no":self.corp_no,"ceo_name":self.ceo_name,"zip_code":self.zip_code,"address":self.address,
                     "uptae":self.uptae,"upjong":self.upjong,"phone":self.phone,"fax":self.fax,
                     "contact_name":self.contact_name,"tax_email":self.tax_email,"bank_account_no":self.account_info}
            for k,w in mapping.items(): w.setText(str(x.get(k) or ""))
            self.memo.setPlainText(str(x.get("memo") or ""))

            cr=httpx.get(f"{API_BASE_URL}/companies/{app_context.company_code}/accounts/{account_id}",timeout=10)
            if cr.status_code==200:
                c=cr.json()
                self._set_combo(self.trade_status,c.get("trade_status"))
                self._set_combo(self.trade_type,c.get("trade_type"))
                self.purchase_yn.setChecked(bool(c.get("purchase_yn")))
                self.sales_yn.setChecked(bool(c.get("sales_yn")))
                self.invoice_issue_yn.setChecked(bool(c.get("invoice_issue_yn")))
                self.trade_stop_yn.setChecked(bool(c.get("trade_stop_yn")))
            else:
                self._set_combo(self.trade_status,"INFO"); self._set_combo(self.trade_type,"GENERAL")
                self.purchase_yn.setChecked(False); self.sales_yn.setChecked(False)
                self.invoice_issue_yn.setChecked(False); self.trade_stop_yn.setChecked(False)
        except Exception as e:
            QMessageBox.critical(self,"조회 오류",str(e))

    def close_window(self):
        p=self.parentWidget()
        while p is not None:
            if isinstance(p,QMdiSubWindow):
                p.close(); return
            p=p.parentWidget()
        self.close()
