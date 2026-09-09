import os
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMdiArea, QMdiSubWindow, QMessageBox

from views.main_dashboard import MainDashboard

try:
    from views.company_reg import CompanyRegWidget as CompanyRegView
except ImportError:
    try:
        from views.company_reg import CompanyRegView
    except ImportError:
        CompanyRegView = None


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

    if not main_window:
        return None

    # 1. 창 타이틀 설정
    current_title = main_window.windowTitle() or "MixNMenu ERP"
    if user_name:
        main_window.setWindowTitle(f"{current_title} - [{user_name}] 접속 중")
    else:
        main_window.setWindowTitle(current_title)

    # 2. MDI Area 구성 (centralwidget 내부에 안전하게 배치)
    central_widget = main_window.findChild(QWidget, "centralwidget")
    if central_widget:
        layout = central_widget.layout()
        if not layout:
            layout = QVBoxLayout(central_widget)
            layout.setContentsMargins(0, 0, 0, 0)

        mdi_area = QMdiArea()
        mdi_area.setViewMode(QMdiArea.SubWindowView)
        mdi_area.setStyleSheet("background-color: #2D2D2D;")
        layout.addWidget(mdi_area)

        # 메인 윈도우 객체에 mdi_area와 서브창 참조 변수 직접 저장 (가비지 컬렉션 방지)
        main_window.mdi_area = mdi_area
        main_window.sub_dashboard = None
        main_window.sub_company = None

    # 3. 상단 메뉴 액션 연결 (기존 작동 방식 복원)
    try:
        # 1.업체등록
        if hasattr(main_window, "action_company_reg"):
            main_window.action_company_reg.triggered.connect(lambda: open_company_reg(main_window))

        # 5.단축메뉴
        if hasattr(main_window, "action_shortcut"):
            main_window.action_shortcut.triggered.connect(lambda: open_dashboard(main_window))

        # 9.종료
        if hasattr(main_window, "action_exit"):
            main_window.action_exit.triggered.connect(main_window.close)

    except Exception as e:
        print(f"[Notice] 메뉴 액션 연결 중 예외 발생: {e}")

    # 4. 프로그램 시작 시 단축메뉴(대시보드) 자동으로 MDI 영역에 열기
    open_dashboard(main_window)

    return main_window


def open_dashboard(main_window):
    """단축메뉴 대시보드 서브 창 오픈"""
    if not hasattr(main_window, "mdi_area") or not main_window.mdi_area:
        return

    try:
        # 이미 열려있으면 해당 창으로 활성화
        if getattr(main_window, "sub_dashboard", None) and main_window.sub_dashboard.isVisible():
            main_window.mdi_area.setActiveSubWindow(main_window.sub_dashboard)
            return

        dashboard_widget = MainDashboard()
        sub_dashboard = QMdiSubWindow()
        sub_dashboard.setWidget(dashboard_widget)
        sub_dashboard.setWindowTitle("바탕화면 - 단축메뉴")

        sub_dashboard.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub_dashboard.destroyed.connect(lambda: setattr(main_window, 'sub_dashboard', None))

        main_window.mdi_area.addSubWindow(sub_dashboard)
        sub_dashboard.resize(1050, 600)
        sub_dashboard.show()
        main_window.sub_dashboard = sub_dashboard
        print(">>> [성공] 단축메뉴 대시보드 열림")
    except Exception as e:
        print(f"[Error] 단축메뉴 열기 실패: {e}")


def open_company_reg(main_window):
    """업체등록 서브 창 오픈"""
    if not hasattr(main_window, "mdi_area") or not main_window.mdi_area:
        return

    if CompanyRegView:
        try:
            # 이미 열려있으면 해당 창으로 활성화
            if getattr(main_window, "sub_company", None) and main_window.sub_company.isVisible():
                main_window.mdi_area.setActiveSubWindow(main_window.sub_company)
                return

            company_widget = CompanyRegView()
            sub_company = QMdiSubWindow()
            sub_company.setWidget(company_widget)
            sub_company.setWindowTitle("업체등록")

            sub_company.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            sub_company.destroyed.connect(lambda: setattr(main_window, 'sub_company', None))

            main_window.mdi_area.addSubWindow(sub_company)
            sub_company.resize(900, 550)
            sub_company.show()
            main_window.sub_company = sub_company
            print(">>> [성공] 업체등록 창 열림")
        except Exception as e:
            print(f"[Error] 업체등록 열기 실패: {e}")
    else:
        QMessageBox.information(
            main_window,
            "안내",
            "1.업체등록 모듈(CompanyRegView)을 가져올 수 없거나 연동 파일 준비 중입니다."
        )