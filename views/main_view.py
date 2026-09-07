import os
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile
from PySide6.QtWidgets import QMainWindow

# views 폴더 내의 company_reg.py에서 위젯 임포트
from views.company_reg import CompanyRegWidget

def load_main_window(user_name=""):
    """
    ui/mxmn_main_window.ui 파일에 정의된 QMainWindow 객체를 직접 로드하여 반환합니다.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ui_path = os.path.join(base_dir, "ui", "mxmn_main_window.ui")

    ui_file = QFile(ui_path)
    if not ui_file.open(QFile.ReadOnly):
        print(f"[Error] UI 파일을 열 수 없습니다: {ui_path}")
        return None

    loader = QUiLoader()
    main_window = loader.load(ui_file)
    ui_file.close()

    if main_window:
        current_title = main_window.windowTitle() or "MixNMenu ERP"
        if user_name:
            main_window.setWindowTitle(f"{current_title} - [{user_name}] 접속 중")
        else:
            main_window.setWindowTitle(current_title)

        # --- [확정] '1.업체등록' 액션(action_company_reg)과 업체등록 창 연결 ---
        try:
            if hasattr(main_window, "action_company_reg"):
                main_window.action_company_reg.triggered.connect(lambda: open_company_reg(main_window))
        except Exception as e:
            print(f"[Notice] 메뉴 액션 연결 중 예외 발생: {e}")

    return main_window

def open_company_reg(parent_window):
    """업체등록 창을 생성하고 화면에 띄우는 함수"""
    parent_window.company_reg_win = CompanyRegWidget(parent_window)
    parent_window.company_reg_win.show()