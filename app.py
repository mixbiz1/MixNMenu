from api_config import API_BASE_URL
import sys
import api_client as httpx

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
    QStyleFactory,
    QComboBox,
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QPalette, QColor

# 메인 윈도우
from views.mxmn_main_window import MixNMainWindow

# MXMN 프로그램 전체 공유 Context
from app_context import app_context


# ============================================================
# 1. 비동기 로그인 통신 워커
# ============================================================

class LoginWorker(QThread):
    finished = Signal(bool, object)

    def __init__(self, user_id, password):
        super().__init__()

        self.user_id = user_id
        self.password = password

    def run(self):
        try:
            payload = {
                "user_id": self.user_id,
                "password": self.password,
            }

            response = httpx.post(
                f"{API_BASE_URL}/auth/login",
                json=payload,
                timeout=15.0,
            )

            if response.status_code == 200:
                data = response.json()

                user_name = data.get(
                    "user_name",
                    self.user_id,
                )

                self.finished.emit(True, data)

            else:
                try:
                    err_msg = response.json().get(
                        "detail",
                        "사용자 ID 또는 암호가 일치하지 않습니다.",
                    )
                except Exception:
                    err_msg = (
                        f"로그인 실패 "
                        f"(HTTP {response.status_code})"
                    )

                self.finished.emit(False, {"detail": err_msg})

        except Exception as e:
            self.finished.emit(False, {"detail": f"서버 연결 실패: {str(e)}"})


# ============================================================
# 2. 커스텀 알림 창
# ============================================================

def show_custom_message(
    parent,
    title,
    message,
    icon=QMessageBox.Information,
):
    msg_box = QMessageBox(parent)

    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(icon)

    msg_box.setStyleSheet(
        """
        QMessageBox {
            background-color: #ffffff;
        }

        QLabel {
            color: #1a1a1a;
            font-family: '맑은 고딕';
            font-size: 10pt;
            font-weight: bold;
            padding: 10px;
        }

        QPushButton {
            background-color: #0d47a1;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 6px 20px;
            font-family: '맑은 고딕';
            font-size: 10pt;
            font-weight: bold;
            min-width: 70px;
        }

        QPushButton:hover {
            background-color: #1565c0;
        }
        """
    )

    msg_box.exec()


# ============================================================
# 3. MXMN 로그인 GUI
# ============================================================

class LoginDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("MXMN ERP")
        self.setFixedSize(650, 480)

        self.setStyleSheet(
            "background-color: #ffffff; color: #000000;"
        )

        self.user_id = ""
        self.user_name = ""

        self.init_ui()

    def init_ui(self):

        main_layout = QVBoxLayout()

        main_layout.setContentsMargins(
            40,
            30,
            40,
            20,
        )

        main_layout.setSpacing(15)

        # ----------------------------------------------------
        # 상단 로고
        # ----------------------------------------------------

        logo_frame = QFrame()

        logo_frame.setStyleSheet(
            """
            QFrame {
                border: 1px solid #a0a0a0;
                background-color: #ffffff;
            }
            """
        )

        logo_layout = QVBoxLayout(logo_frame)

        logo_label = QLabel("MXMN")

        logo_label.setFont(
            QFont(
                "Segoe UI",
                32,
                QFont.Bold,
            )
        )

        logo_label.setStyleSheet(
            """
            color: #0d47a1;
            border: none;
            background-color: transparent;
            """
        )

        logo_label.setAlignment(
            Qt.AlignCenter
        )

        logo_layout.addWidget(
            logo_label
        )

        main_layout.addWidget(
            logo_frame,
            alignment=Qt.AlignCenter,
        )

        main_layout.addSpacing(10)

        # ----------------------------------------------------
        # 입력 폼
        # ----------------------------------------------------

        form_layout = QVBoxLayout()

        form_layout.setSpacing(8)

        # 사용자 ID

        id_layout = QHBoxLayout()

        id_label = QLabel("사용자 ID")

        id_label.setFixedWidth(80)

        id_label.setFont(
            QFont(
                "맑은 고딕",
                10,
                QFont.Bold,
            )
        )

        id_label.setStyleSheet(
            """
            color: #800000;
            background-color: transparent;
            """
        )

        id_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )

        self.id_input = QLineEdit()

        self.id_input.setFixedWidth(180)

        self.id_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #fffff0;
                border: 1px solid #a0a0a0;
                padding: 4px;
                color: #000000;
                font-size: 10pt;
                font-weight: bold;
            }
            """
        )

        id_layout.addStretch()
        id_layout.addWidget(id_label)
        id_layout.addSpacing(10)
        id_layout.addWidget(self.id_input)
        id_layout.addStretch()

        # 암호

        pw_layout = QHBoxLayout()

        pw_label = QLabel("암    호")

        pw_label.setFixedWidth(80)

        pw_label.setFont(
            QFont(
                "맑은 고딕",
                10,
                QFont.Bold,
            )
        )

        pw_label.setStyleSheet(
            """
            color: #800000;
            background-color: transparent;
            """
        )

        pw_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )

        self.pw_input = QLineEdit()

        self.pw_input.setEchoMode(
            QLineEdit.Password
        )

        self.pw_input.setFixedWidth(180)

        self.pw_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #fffff0;
                border: 1px solid #a0a0a0;
                padding: 4px;
                color: #000000;
                font-size: 10pt;
                font-weight: bold;
            }
            """
        )

        self.pw_input.returnPressed.connect(
            self.start_login
        )

        pw_layout.addStretch()
        pw_layout.addWidget(pw_label)
        pw_layout.addSpacing(10)
        pw_layout.addWidget(self.pw_input)
        pw_layout.addStretch()

        form_layout.addLayout(
            id_layout
        )

        form_layout.addLayout(
            pw_layout
        )

        main_layout.addLayout(
            form_layout
        )

        # ----------------------------------------------------
        # 버튼
        # ----------------------------------------------------

        btn_layout = QHBoxLayout()

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #707070;
                padding: 4px 20px;
                font-family: '맑은 고딕';
                font-size: 10pt;
                color: #000000;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #e5f1fb;
                border: 1px solid #0078d7;
            }
        """

        self.btn_confirm = QPushButton(
            "확    인"
        )

        self.btn_confirm.setStyleSheet(
            btn_style
        )

        self.btn_confirm.clicked.connect(
            self.start_login
        )

        self.btn_cancel = QPushButton(
            "취    소"
        )

        self.btn_cancel.setStyleSheet(
            btn_style
        )

        self.btn_cancel.clicked.connect(
            self.reject
        )

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()

        main_layout.addLayout(
            btn_layout
        )

        main_layout.addStretch()

        # ----------------------------------------------------
        # 버전
        # ----------------------------------------------------

        version_label = QLabel(
            "믹스앤메뉴 Ver.1.00"
        )

        version_label.setFont(
            QFont(
                "맑은 고딕",
                10,
                QFont.Bold,
            )
        )

        version_label.setStyleSheet(
            """
            color: #000080;
            background-color: transparent;
            """
        )

        version_label.setAlignment(
            Qt.AlignCenter
        )

        main_layout.addWidget(
            version_label
        )

        self.setLayout(
            main_layout
        )

    # --------------------------------------------------------
    # 로그인 시작
    # --------------------------------------------------------

    def start_login(self):

        user_id = (
            self.id_input
            .text()
            .strip()
        )

        user_pw = (
            self.pw_input
            .text()
            .strip()
        )

        if not user_id or not user_pw:

            show_custom_message(
                self,
                "알림",
                "사용자 ID와 암호를 입력해 주세요.",
                QMessageBox.Warning,
            )

            return

        self.btn_confirm.setEnabled(
            False
        )

        self.worker = LoginWorker(
            user_id,
            user_pw,
        )

        self.worker.finished.connect(
            self.on_login_finished
        )

        self.worker.start()

    # --------------------------------------------------------
    # 로그인 결과
    # --------------------------------------------------------

    def on_login_finished(
        self,
        success: bool,
        result: object,
    ):

        self.btn_confirm.setEnabled(
            True
        )

        if success:
            self.user_id = self.id_input.text().strip()
            self.user_name = result.get("user_name", self.user_id)

            # 현재 로그인 사용자 Context 저장
            app_context.set_user(
                self.user_id,
                self.user_name,
                result.get("access_token"),
                result.get("is_admin", False),
                result.get("permissions", {}),
            )

            welcome_text = (
                f"🎉 환영합니다!\n\n"
                f"[{self.user_name}] 님, "
                f"MixNMenu 시스템 접속이 승인되었습니다.\n"
                f"확인을 누르시면 회사 선택 화면으로 이동합니다."
            )

            show_custom_message(
                self,
                "로그인 성공",
                welcome_text,
                QMessageBox.Information,
            )

            self.accept()

        else:

            show_custom_message(
                self,
                "로그인 실패",
                result.get("detail", "로그인에 실패했습니다."),
                QMessageBox.Critical,
            )


# ============================================================
# 4. 현재 업무 회사 선택 GUI
# ============================================================

class CompanySelectDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "MXMN - 회사 선택"
        )

        self.setFixedSize(
            430,
            190,
        )

        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            """
        )

        self.init_ui()

        self.load_companies()

    def init_ui(self):

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            30,
            25,
            30,
            25,
        )

        layout.setSpacing(
            15
        )

        title = QLabel(
            "업무를 수행할 회사를 선택하십시오."
        )

        title.setFont(
            QFont(
                "맑은 고딕",
                11,
                QFont.Bold,
            )
        )

        layout.addWidget(
            title
        )

        self.company_combo = QComboBox()

        self.company_combo.setMinimumHeight(
            32
        )

        self.company_combo.setFont(
            QFont(
                "맑은 고딕",
                10,
            )
        )

        self.company_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #808080;
                padding: 4px 8px;
            }

            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0d47a1;
                selection-color: #ffffff;
            }
            """
        )

        layout.addWidget(
            self.company_combo
        )

        btn_layout = QHBoxLayout()

        btn_confirm = QPushButton(
            "확    인"
        )

        btn_cancel = QPushButton(
            "취    소"
        )

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #707070;
                padding: 5px 20px;
                font-family: '맑은 고딕';
                font-size: 10pt;
                color: #000000;
                font-weight: bold;
                min-width: 80px;
            }

            QPushButton:hover {
                background-color: #e5f1fb;
                border: 1px solid #0078d7;
            }
        """

        btn_confirm.setStyleSheet(
            btn_style
        )

        btn_cancel.setStyleSheet(
            btn_style
        )

        btn_confirm.clicked.connect(
            self.select_company
        )

        btn_cancel.clicked.connect(
            self.reject
        )

        btn_layout.addStretch()
        btn_layout.addWidget(btn_confirm)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()

        layout.addLayout(
            btn_layout
        )

    # --------------------------------------------------------
    # 회사 목록 조회
    # --------------------------------------------------------

    def load_companies(self):

        try:

            response = httpx.get(
                f"{API_BASE_URL}/companies",
                timeout=10.0,
            )

            if response.status_code != 200:

                raise Exception(
                    "회사 목록 조회 실패 "
                    f"(HTTP {response.status_code})"
                )

            companies = (
                response.json()
            )

            self.company_combo.clear()

            for company in companies:

                comp_code = company.get(
                    "comp_code"
                )

                comp_name = company.get(
                    "comp_name"
                )

                if not comp_code:
                    continue

                self.company_combo.addItem(
                    f"{comp_code}  {comp_name}",
                    {
                        "comp_code": comp_code,
                        "comp_name": comp_name,
                    },
                )

            if self.company_combo.count() == 0:

                raise Exception(
                    "등록된 회사가 없습니다."
                )

        except Exception as e:

            show_custom_message(
                self,
                "회사 조회 오류",
                str(e),
                QMessageBox.Critical,
            )

            self.reject()

    # --------------------------------------------------------
    # 현재 회사 확정
    # --------------------------------------------------------

    def select_company(self):

        company = (
            self.company_combo
            .currentData()
        )

        if not company:

            show_custom_message(
                self,
                "알림",
                "회사를 선택해 주세요.",
                QMessageBox.Warning,
            )

            return

        app_context.set_company(
            company["comp_code"],
            company["comp_name"],
        )

        self.accept()


# ============================================================
# 5. Light Palette
# ============================================================

def apply_light_palette(app):

    app.setStyle(
        QStyleFactory.create(
            "Fusion"
        )
    )

    palette = QPalette()

    palette.setColor(
        QPalette.Window,
        QColor(255, 255, 255),
    )

    palette.setColor(
        QPalette.WindowText,
        QColor(0, 0, 0),
    )

    palette.setColor(
        QPalette.Base,
        QColor(255, 255, 255),
    )

    palette.setColor(
        QPalette.AlternateBase,
        QColor(245, 245, 245),
    )

    palette.setColor(
        QPalette.ToolTipBase,
        QColor(255, 255, 255),
    )

    palette.setColor(
        QPalette.ToolTipText,
        QColor(0, 0, 0),
    )

    palette.setColor(
        QPalette.Text,
        QColor(0, 0, 0),
    )

    palette.setColor(
        QPalette.Button,
        QColor(240, 240, 240),
    )

    palette.setColor(
        QPalette.ButtonText,
        QColor(0, 0, 0),
    )

    palette.setColor(
        QPalette.BrightText,
        QColor(255, 0, 0),
    )

    palette.setColor(
        QPalette.Link,
        QColor(13, 71, 161),
    )

    palette.setColor(
        QPalette.Highlight,
        QColor(13, 71, 161),
    )

    palette.setColor(
        QPalette.HighlightedText,
        QColor(255, 255, 255),
    )

    app.setPalette(
        palette
    )


# ============================================================
# 6. MXMN 시작
# ============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    apply_light_palette(
        app
    )

    # 이전 실행 Context 초기화
    app_context.clear()

    # --------------------------------------------------------
    # STEP 1 : 로그인
    # --------------------------------------------------------

    login_dialog = LoginDialog()

    if login_dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    # --------------------------------------------------------
    # STEP 2 : 회사 선택
    # --------------------------------------------------------

    company_dialog = CompanySelectDialog()

    if company_dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    # --------------------------------------------------------
    # STEP 3 : 메인 프로그램
    # --------------------------------------------------------

    main_win = MixNMainWindow()

    main_win.show()

    sys.exit(
        app.exec()
    )
