# main.py
import sys
import asyncio
import subprocess
import webbrowser
from threading import Thread
from flask import Flask, abort, render_template, request
import PySide6
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

import bsgamesdk
import mihoyosdk
import mainWindow
from bh3_utils import image_processor, is_game_window_exist, click_center_of_game_window
from utils import EmittingStream # ,set_qt_env
from config_utils import ConfigManager

# ========== 初始化配置管理器 ==========
config_manager = ConfigManager()

# ========== 登陆线程 ==========
class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)

    async def login(self):
        print("[INFO] 登陆B站账号中...")
        try:
            config = config_manager.config
            if config['last_login_succ']:
                print(f"[INFO] 验证缓存账号 {config['uname']} 中...")
                bs_user_info = await bsgamesdk.getUserInfo(config['uid'], config['access_key'])
                if 'uname' in bs_user_info:
                    print(f"[INFO] 登陆B站账号 {bs_user_info['uname']} 成功！")
                    bs_info = {'uid': config['uid'], 'access_key': config['access_key']}
                else:
                    config.update({'last_login_succ': False, 'uid': '', 'access_key': '', 'uname': ''})
                    config_manager.write_conf(config)
            else:
                print(f"[INFO] 登陆B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(config['account'], config['password'], config_manager.cap)
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
                    return
                bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                print(f"[INFO] 登陆B站账号 {bs_user_info['uname']} 成功！")
                config.update({
                    'uid': bs_info['uid'],
                    'access_key': bs_info['access_key'],
                    'last_login_succ': True,
                    'uname': bs_user_info["uname"]
                })
                config_manager.write_conf(config)

            print("[INFO] 登陆崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
            config_manager.bh_info = bh_info
            if bh_info['retcode'] != 0:
                print(f"[INFO] 登陆失败！{bh_info}")
                self.login_complete.emit(False)
                return

            print("[INFO] 登陆成功！")
            print("[INFO] 获取OA服务器信息中...")
            bh_ver = await mihoyosdk.getBHVer(config)
            config['bh_ver'] = bh_ver
            config_manager.write_conf(config)
            print(f"[INFO] 当前崩坏3版本: {bh_ver}")
            oa = await mihoyosdk.getOAServer(config['oa_token'])
            if len(oa) < 100:
                print("[INFO] 获取OA服务器失败！请检查Token后重试")
                self.login_complete.emit(False)
                return

            print("[INFO] 获取OA服务器成功！")
            ui.loginBiliBtn.setText("账号已登陆")
            config['account_login'] = True
            config_manager.write_conf(config)
            self.login_complete.emit(True)

        except Exception as e:
            print(f"[ERROR] 登陆过程中发生错误: {str(e)}")
            ui.loginBiliBtn.setText("登陆失败")
            ui.loginBiliBtn.setDisabled(False)
            self.login_complete.emit(False)

    def handle_login_failure(self, bs_info):
        if 'message' in bs_info:
            print("[INFO] 登陆失败！")
            if bs_info['message'] == 'PWD_INVALID':
                print("[INFO] 账号或密码错误！")
            else:
                print(f"[INFO] 原始返回：{bs_info['message']}")

        if 'need_captch' in bs_info:
            print("[INFO] 需要验证码！请打开下方网址进行操作！")
            print(f"[INFO] {bs_info['cap_url']}")
            webbrowser.open_new(bs_info['cap_url'])
        else:
            print(f"[INFO] 登陆失败！{bs_info}")

        ui.loginBiliBtn.setText("登陆账号")
        ui.loginBiliBtn.setDisabled(False)
        self.login_complete.emit(False)

    def run(self):
        asyncio.run(self.login())

# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = Signal(str)
    exit_app = Signal()

    async def check(self):
        while True:
            config = config_manager.config
            if config['auto_click']:
                if is_game_window_exist():
                    image_processor.match_and_click()
                else:
                    print("[DEBUG] 崩坏3窗口不存在，跳过图像识别和点击")

            if config['auto_clip']:
                try:
                    if not is_game_window_exist():
                        print("[DEBUG] 崩坏3窗口不存在，跳过自动截屏")
                        await asyncio.sleep(config['sleep_time'])
                        continue
                    screenshot = image_processor.capture_screen()
                    if screenshot is None:
                        await asyncio.sleep(config['sleep_time'])
                        continue
                    qr_parsed = await image_processor.parse_qr_code(
                        image_source='game_window',
                        config=config,
                        bh_info=config_manager.bh_info
                    )
                    if qr_parsed:
                        if config['auto_click']:
                            print('[INFO] 扫码成功，4秒后将自动点击窗口中心')
                            await asyncio.sleep(4)
                            click_center_of_game_window()
                        if config['auto_close']:
                            print('[INFO] 已启用自动退出，2秒后将关闭扫码器')
                            await asyncio.sleep(2)
                            self.exit_app.emit()
                            return
                except Exception as e:
                    print(f"[ERROR] 自动截屏时出错: {str(e)}")

            if config['clip_check'] and config.get('account_login', False):
                await image_processor.parse_qr_code(
                    image_source='clipboard',
                    config=config,
                    bh_info=config_manager.bh_info
                )

            await asyncio.sleep(config['sleep_time'])

    def run(self):
        asyncio.run(self.check())

# ========== 登陆按钮点击回调 ==========
def login_accept():
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    ui.backendLogin.start()

# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"./BHimage.ico"))
        self.prev_settings = {}
        self.temp_mode = False

    def handle_login_complete(self, success):
        status = "账号已登陆" if success else "登陆失败"
        ui.loginBiliBtn.setText(status)
        ui.loginBiliBtn.setDisabled(False)

    def login(self):
        config = config_manager.config
        if config.get('account_login', False):
            print("[INFO] 账号已登陆")
            ui.loginBiliBtn.setText("账号已登陆")
            return

        print("[INFO] 开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)

        dialog = mainWindow.LoginDialog(self)
        dialog.account.textChanged.connect(self.deal_config_update('account'))
        dialog.password.textChanged.connect(self.deal_config_update('password'))
        dialog.show()
        dialog.accepted.connect(login_accept)

    def deal_config_update(self, key):
        def update(value):
            config = config_manager.config
            config[key] = value
            config_manager.write_conf(config)
        return update

    def update_status_text(self, checkbox, prefix):
        checkbox.setText(f"{prefix}:{'启用' if checkbox.isChecked() else '关闭'}")

    def toggle_feature(self, feature, checkbox, prefix):
        config = config_manager.config
        config[feature] = checkbox.isChecked()
        config_manager.write_conf(config)
        self.update_status_text(checkbox, prefix)

    def configGamePath(self):
        filePath, _ = QFileDialog.getOpenFileName(self, "选择崩坏3执行文件", "", "Executable Files (*.exe)")
        if filePath:
            config = config_manager.config
            config['game_path'] = filePath
            config_manager.write_conf(config)
            ui.configGamePathBtn.setText("路径已配置")

    def launchGame(self):
        config = config_manager.config
        if config.get('game_path'):
            try:
                subprocess.Popen([config['game_path']])
                print("[INFO] 正在启动崩坏3...")
            except Exception as e:
                print(f"[ERROR] 启动失败: {str(e)}")
        else:
            print("[INFO] 请先配置游戏路径！")
            QMessageBox.warning(self, "路径未配置", "请先配置游戏路径！")

    def oneClickLogin(self):
        self.launchGame()
        self.temp_mode = True
        config = config_manager.config
        for feature in ['clip_check', 'auto_clip', 'auto_close', 'auto_click']:
            self.prev_settings[feature] = config.get(feature, False)
            config[feature] = True
        config_manager.write_conf(config)
        for checkbox, prefix in [
            (ui.clipCheck, "当前状态"),
            (ui.autoClipCheck, "当前状态"),
            (ui.autoCloseCheck, "当前状态"),
            (ui.autoClick, "当前状态")
        ]:
            checkbox.setChecked(True)
            self.update_status_text(checkbox, prefix)
        print("[INFO] 一键登陆模式已启用")

    def restoreOriginalSettings(self):
        if not self.temp_mode:
            return
        config = config_manager.config
        for feature, value in self.prev_settings.items():
            config[feature] = value
        config_manager.write_conf(config)
        for checkbox, feature, prefix in [
            (ui.clipCheck, 'clip_check', "当前状态"),
            (ui.autoClipCheck, 'auto_clip', "当前状态"),
            (ui.autoCloseCheck, 'auto_close', "当前状态"),
            (ui.autoClick, 'auto_click', "当前状态")
        ]:
            checkbox.setChecked(config.get(feature, False))
            self.update_status_text(checkbox, prefix)
        print("[INFO] 一键登陆模式已结束，恢复原始设置")

# ========== Flask 启动 ==========
if __name__ == '__main__':
    stream = EmittingStream()
    sys.stdout = stream

    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow()
    ui.setupUi(window)

    stream.textWritten.connect(lambda text: ui.logText.append(text))
#    set_qt_env()

    fapp = Flask(__name__)

    @fapp.route("/")
    def index():
        return render_template("index.html")

    @fapp.route("/geetest")
    def geetest():
        return render_template("geetest.html")

    @fapp.route('/ret', methods=["POST"])
    def ret():
        if not request.json:
            print("[INFO] 请求错误")
            abort(400)
        print(f"[INFO] Input = {request.json}")
        config_manager.cap = request.json
        login_accept()
        return "1"

    flaskThread = Thread(
        target=fapp.run,
        daemon=True,
        kwargs={'host': '0.0.0.0', 'port': 12983, 'threaded': True, 'use_reloader': False, 'debug': False}
    )
    flaskThread.start()

    config = config_manager.config
    if config['account']:
        print("[INFO] 配置文件已有账号，尝试登陆中...")
        login_accept()

    for checkbox, feature, prefix in [
        (ui.clipCheck, 'clip_check', "当前状态"),
        (ui.autoCloseCheck, 'auto_close', "当前状态"),
        (ui.autoClipCheck, 'auto_clip', "当前状态"),
        (ui.autoClick, 'auto_click', "当前状态")
    ]:
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    ui.configGamePathBtn.setText("路径已配置" if config.get('game_path') else "点击配置")

    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(print)
    ui.backendClipCheck.exit_app.connect(lambda: (window.restoreOriginalSettings(), app.quit()))
    ui.backendClipCheck.start()

    window.show()

    if '--auto-login' in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        print("[INFO] 检测到自动登陆参数，将启动一键登陆模式")

    sys.exit(app.exec())
