# main.py
import sys
from threading import Thread
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from mainWindow import ui
from utils import EmittingStream
from config_utils import config_manager
from ui_handlers import SelfMainWindow
from callbacks import login_accept
from flask_app import fapp

# ========== 主程序入口 ==========

if __name__ == '__main__':
    stream = EmittingStream()
    config = config_manager.config
    stream.show_debug_gui = config['debug_print']  # 调整信息输出级别
    sys.stdout = stream

    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui.setupUi(window)  # 设置 UI 到窗口
    # 连接信号流到print
    stream.textWritten.connect(lambda text: ui.logText.append(text))

    # 启动Flask线程（使用flask_app.py中的fapp）
    flaskThread = Thread(
        target=fapp.run,
        daemon=True,
        kwargs={'host': '0.0.0.0', 'port': 12983, 'threaded': True, 'use_reloader': False, 'debug': False}
    )
    flaskThread.start()

    # 绑定UI事件处理函数
    # 注意：事件绑定已在 mainWindow.py 中的 connectSignals 方法完成
    # 此处不需要重复绑定

    # --- 在显示窗口前应用配置 ---
    # 尝试自动登录
    if config['account']:
        print("[INFO] 配置文件已有账号，尝试登陆中...")
        # 注意：此时UI控件已创建，可以安全调用
        login_accept(ui, window)  # 传入ui和window参数

    # 应用配置到UI控件
    for checkbox, feature, prefix in [
        (ui.clipCheck, 'clip_check', "当前状态"),
        (ui.autoClose, 'auto_close', "当前状态"),
        (ui.autoClip, 'auto_clip', "当前状态"),
        (ui.autoClick, 'auto_click', "当前状态"),
        (ui.debugPrint, 'debug_print', "当前状态")
    ]:
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    # 更新游戏路径按钮文本
    ui.configGamePathBtn.setText("路径已配置" if config.get('game_path') else "点击配置")

    # 显示窗口
    window.show()

    # 处理命令行参数
    if '--auto-login' in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        print("[INFO] 检测到自动登陆参数，将启动一键登陆模式")

    sys.exit(app.exec())
