from PySide6.QtWidgets import QApplication
from threads import LoginThread, ParseThread

def login_accept(ui, window):
    # 创建并启动登录线程
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    # 连接登录完成信号到主窗口的处理函数
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    # 连接登录完成信号到启动解析线程的函数
    ui.backendLogin.login_complete.connect(lambda success: start_parse_thread_after_login(success, ui, window))
    ui.backendLogin.start()

def start_parse_thread_after_login(success, ui, window):
    if success:
        print("[INFO] 登录流程完成，准备启动解析线程...")
        # 确保旧的线程被正确处理（如果存在）
        if hasattr(ui, 'backendClipCheck') and ui.backendClipCheck.isRunning():
            print("[WARNING] 解析线程已在运行中？")
            return
        # 创建并启动解析线程
        ui.backendClipCheck = ParseThread()
        ui.backendClipCheck.update_log.connect(print)
        ui.backendClipCheck.exit_app.connect(lambda: (window.restoreOriginalSettings(), QApplication.instance().quit()))
        ui.backendClipCheck.start()
        print("[INFO] 解析线程已启动")
    else:
        print("[INFO] 登录流程未完成，不启动解析线程")