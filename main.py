# main.py
import sys
import asyncio
import subprocess
import webbrowser
from threading import Thread
from flask import Flask, abort, render_template, request
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

import bsgamesdk
import mihoyosdk
import mainWindow
from bh3_utils import image_processor, is_game_window_exist, click_center_of_game_window
from utils import set_qt_env, EmittingStream
from config_utils import ConfigManager

# ========== 初始化配置管理器 ==========
config_manager = ConfigManager()

# ========== 登录线程 ==========
class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)
    
    async def login(self):
        print("[INFO] 登录B站账号中...")
        try:
            config = config_manager.config
            if config['last_login_succ']:
                print(f"[INFO] 验证缓存账号 {config['uname']} 中...")
                bs_user_info = await bsgamesdk.getUserInfo(config['uid'], config['access_key'])
                if 'uname' in bs_user_info:
                    print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                    bs_info = {'uid': config['uid'], 'access_key': config['access_key']}
                else:
                    config['last_login_succ'] = False
                    config['uid'] = config['access_key'] = config['uname'] = ""
                    config_manager.write_conf(config)
            else:
                print(f"[INFO] 登录B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(config['account'], config['password'], config_manager.cap)
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
                    return
                
                bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                config.update({
                    'uid': bs_info['uid'],
                    'access_key': bs_info['access_key'],
                    'last_login_succ': True,
                    'uname': bs_user_info["uname"]
                })
                config_manager.write_conf(config)
            
            print("[INFO] 登录崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
            config_manager.bh_info = bh_info
            
            if bh_info['retcode'] != 0:
                print(f"[INFO] 登录失败！{bh_info}")
                self.login_complete.emit(False)
                return
            
            print("[INFO] 登录成功！")
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
            ui.loginBiliBtn.setText("账号已登录")
            config['account_login'] = True
            config_manager.write_conf(config)
            self.login_complete.emit(True)
        
        except Exception as e:
            print(f"[ERROR] 登录过程中发生错误: {str(e)}")
            ui.loginBiliBtn.setText("登录失败")
            ui.loginBiliBtn.setDisabled(False)
            self.login_complete.emit(False)
    
    def handle_login_failure(self, bs_info):
        if 'message' in bs_info:
            print("[INFO] 登录失败！")
            if bs_info['message'] == 'PWD_INVALID':
                print("[INFO] 账号或密码错误！")
            else:
                print(f"[INFO] 原始返回：{bs_info['message']}")
        
        if 'need_captch' in bs_info:
            print("[INFO] 需要验证码！请打开下方网址进行操作！")
            print(f"[INFO] {bs_info['cap_url']}")
            webbrowser.open_new(bs_info['cap_url'])
        else:
            print(f"[INFO] 登录失败！{bs_info}")
        
        ui.loginBiliBtn.setText("登陆账号")
        ui.loginBiliBtn.setDisabled(False)
        self.login_complete.emit(False)
    
    def run(self):
        asyncio.run(self.login())

# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = Signal(str)
    
    async def check(self):
        while True:
            config = config_manager.config

            # 自动切换模式处理
            if config['auto_close'] and config['auto_switch_mode']:
                if is_game_window_exist():
                    image_processor.match_and_click()
                else:
                    print("[DEBUG] 崩坏3窗口不存在，跳过图像识别和点击")

            # 自动截屏处理
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
                        print('[INFO] 扫码成功，4秒后将自动点击窗口中心')
                        await asyncio.sleep(4)
                        click_center_of_game_window()
                        
                    if config['auto_close']:
                        print('[INFO] 已启用自动退出，2秒后将关闭扫码器')
                        QTimer.singleShot(2000, QApplication.instance().quit)
                        return
                except Exception as e:
                    print(f"[ERROR] 自动截屏时出错: {str(e)}")

            # 剪贴板检测
            if config['clip_check'] and config.get('account_login', False):
                await image_processor.parse_qr_code(
                    image_source='clipboard',
                    config=config,
                    bh_info=config_manager.bh_info
                )

            await asyncio.sleep(config['sleep_time'])
    
    def run(self):
        asyncio.run(self.check())

# ========== 登录按钮点击回调 ==========
def login_accept():
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    ui.backendLogin.start()

# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r".\BHimage.ico"))
        self.prev_settings = {
            'clip_check': config_manager.config['clip_check'],
            'auto_clip': config_manager.config['auto_clip'],
            'auto_close': config_manager.config['auto_close'],
            'auto_switch_mode': config_manager.config.get('auto_switch_mode', False)
        }
    
    def handle_login_complete(self, success):
        status = "账号已登录" if success else "登录失败"
        ui.loginBiliBtn.setText(status)
        ui.loginBiliBtn.setDisabled(False)
    
    def login(self):
        config = config_manager.config
        if config.get('account_login', False):
            print("[INFO] 账号已登录")
            ui.loginBiliBtn.setText("账号已登录")
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
        status = "启用" if checkbox.isChecked() else "关闭"
        checkbox.setText(f"{prefix}:{status}")
    
    def toggle_feature(self, feature, checkbox, prefix):
        config = config_manager.config
        config[feature] = checkbox.isChecked()
        config_manager.write_conf(config)
        self.update_status_text(checkbox, prefix)
    
    def qrCodeSwitch(self, boolean):
        self.toggle_feature('clip_check', ui.clipCheck, "当前状态")
    
    def autoCloseSwitch(self, boolean):
        self.toggle_feature('auto_close', ui.autoCloseCheck, "当前状态")
    
    def autoClipSwitch(self, boolean):
        self.toggle_feature('auto_clip', ui.autoClipCheck, "当前状态")
    
    def autoSwitchModeSwitch(self, boolean):
        self.toggle_feature('auto_switch_mode', ui.autoSwitchModeCheck, "当前状态")
    
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
        """一键登录功能"""
        self.launchGame()
        
        # 保存当前设置并启用所有功能
        config = config_manager.config
        for feature in ['clip_check', 'auto_clip', 'auto_close', 'auto_switch_mode']:
            self.prev_settings[feature] = config.get(feature, False)
            config[feature] = True
        
        config_manager.write_conf(config)
        
        # 更新UI状态
        for checkbox, prefix in [
            (ui.clipCheck, "当前状态"),
            (ui.autoClipCheck, "当前状态"),
            (ui.autoCloseCheck, "当前状态"),
            (ui.autoSwitchModeCheck, "当前状态")
        ]:
            checkbox.setChecked(True)
            self.update_status_text(checkbox, prefix)
        
        print("[INFO] 一键登录模式已启用")
        print("[INFO] 已临时启用所有功能")
        QTimer.singleShot(120000, self.restoreOriginalSettings)
    
    def restoreOriginalSettings(self):
        config = config_manager.config
        for feature, value in self.prev_settings.items():
            config[feature] = value
        
        config_manager.write_conf(config)
        
        # 更新UI状态
        for checkbox, prefix in [
            (ui.clipCheck, "当前状态"),
            (ui.autoClipCheck, "当前状态"),
            (ui.autoCloseCheck, "当前状态"),
            (ui.autoSwitchModeCheck, "当前状态")
        ]:
            checkbox.setChecked(self.prev_settings[feature])
            self.update_status_text(checkbox, prefix)
        
        print("[INFO] 一键登录模式已结束，恢复原始设置")

# ========== Flask 启动 ==========
if __name__ == '__main__':
    # 设置 stdout 重定向
    stream = EmittingStream()
    sys.stdout = stream
    stream.textWritten.connect(lambda text: ui.logText.append(text))

    # 初始化配置
    set_qt_env()
    
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
    
    # 启动Flask线程
    flaskThread = Thread(
        target=fapp.run,
        daemon=True,
        kwargs={'host': '0.0.0.0', 'port': 12983, 'threaded': True, 'use_reloader': False, 'debug': False}
    )
    flaskThread.start()
    
    # ========== GUI 初始化 ==========
    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow()
    ui.setupUi(window)
    
    try:
        config = config_manager.config
        if config['account']:
            print("[INFO] 配置文件已有账号，尝试登录中...")
            login_accept()
        
        # 初始化UI状态
        for checkbox, feature, prefix in [
            (ui.clipCheck, 'clip_check', "当前状态"),
            (ui.autoCloseCheck, 'auto_close', "当前状态"),
            (ui.autoClipCheck, 'auto_clip', "当前状态"),
            (ui.autoSwitchModeCheck, 'auto_switch_mode', "当前状态")
        ]:
            checkbox.setChecked(config.get(feature, False))
            window.update_status_text(checkbox, prefix)
        
        ui.configGamePathBtn.setText("路径已配置" if config.get('game_path') else "点击配置")
    
    except KeyError:
        config_manager.write_conf(config)
        print("[INFO] 配置文件异常，重置并跳过登录")
    
    # 启动解析线程
    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(print)
    ui.backendClipCheck.start()
    
    # 显示窗口
    window.show()
    print(f"启动参数: {sys.argv}")
    
    # 自动登录处理
    if '--auto-login' in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        print("[INFO] 检测到自动登录参数，将启动一键登录模式")
    
    sys.exit(app.exec())