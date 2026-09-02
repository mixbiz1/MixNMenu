import sys
import httpx
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QTextEdit, QLabel
)
from PySide6.QtCore import QThread, Signal

# 1. API 통신을 전담할 백그라운드 워커 스레드
class ApiWorker(QThread):
    # 통신 결과를 전달할 커스텀 시그널 (성공 여부, 메세지)
    finished = Signal(bool, str)

    def run(self):
        try:
            # FastAPI 서버의 DB 체크 엔드포인트 호출
            response = httpx.get("http://127.0.0.1:8000/api/db-check", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                msg = (
                    f"✅ [통신 성공]\n"
                    f"- 상태: {data.get('status')}\n"
                    f"- 메세지: {data.get('db_response')}\n"
                    f"- DB 버전: {data.get('version')}"
                )
                self.finished.emit(True, msg)
            else:
                self.finished.emit(False, f"❌ HTTP 오류 코드: {response.status_code}")
        except Exception as e:
            self.finished.emit(False, f"❌ 접속 실패: FastAPI 서버가 꺼져있는지 확인하세요.\n({str(e)})")

# 2. PySide6 메인 윈도우
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MixNMenu ERP - Step 12 비동기 통신 검증")
        self.resize(500, 350)

        # UI 레이아웃 구성
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.info_label = QLabel("아래 버튼을 눌러 FastAPI 및 MS SQL DB 연결 상태를 확인하세요.")
        layout.addWidget(self.info_label)

        self.btn_check = QPushButton("FastAPI 서버 연결 확인")
        self.btn_check.clicked.connect(self.check_server_status)
        layout.addWidget(self.btn_check)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def check_server_status(self):
        self.btn_check.setEnabled(False)
        self.log_text.append("🔄 FastAPI 서버와 DB 연결 확인 중...")

        # 워커 스레드 생성 및 실행
        self.worker = ApiWorker()
        self.worker.finished.connect(self.on_check_finished)
        self.worker.start()

    def on_check_finished(self, success: bool, message: str):
        self.log_text.append(message + "\n")
        self.btn_check.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())