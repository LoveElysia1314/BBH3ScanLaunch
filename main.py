# main.py
import sys
import os
import asyncio
import json
from threading import Thread
from functools import partial

# 标准库 imports
import subprocess
import time
import webbrowser
from threading import Thread
import asyncio
from flask import Flask, abort, render_template, request
# 第三方库 imports
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
# 自定义模块 imports
import bsgamesdk
import mihoyosdk
import mainWindow
from bh3_utils import image_processor, is_game_window_exist
from utils import set_qt_env, EmittingStream

# 导入配置管理器
from config_utils import ConfigManager

# ========== 初始化配置管理器 ==========
config_manager = ConfigManager()  # 单例模式

# ========== 登录线程 ==========
class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)
    
    def run(self):
        asyncio.run(self.login())
    
    async def login(self):
        print("[INFO] 登录B站账号中...")
        try:
            config = config_manager.config  # 获取当前配置
            if config['last_login_succ']:
                print(f"[INFO] 验证缓存账号 {config['uname']} 中...")
                bs_user_info = await bsgamesdk.getUserInfo(config['uid'], config['access_key'])
                if 'uname' in bs_user_info:
                    print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                    bs_info = {'uid': config['uid'], 'access_key': config['access_key']}
                else:
                    config['last_login_succ'] = False
                    config['uid'] = 0
                    config['access_key'] = ""
                    config['uname'] = ""
                    config_manager.write_conf(config)
            else:
                print(f"[INFO] 登录B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(config['account'], config['password'], config_manager.cap)
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
                    return
                bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                config['uid'] = bs_info['uid']
                config['access_key'] = bs_info['access_key']
                config['last_login_succ'] = True
                config['uname'] = bs_user_info["uname"]
                config_manager.write_conf(config)
            
            print("[INFO] 登录崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
            config_manager.bh_info = bh_info  # 更新 bh_info
            if bh_info['retcode'] != 0:
                print("[INFO] 登录失败！")
                print("[INFO]" + str(bh_info))
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
                print("[INFO] 原始返回：" + bs_info['message'])
        if 'need_captch' in bs_info:
            print("[INFO] 需要验证码！请打开下方网址进行操作！")
            print("[INFO]" + bs_info['cap_url'])
            webbrowser.open_new(bs_info['cap_url'])
        else:
            print("[INFO] 登录失败！")
            print("[INFO]" + str(bs_info))
        ui.loginBiliBtn.setText("登陆账号")
        ui.loginBiliBtn.setDisabled(False)
        self.login_complete.emit(False)

# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = Signal(str)
    
    def run(self):
        asyncio.run(self.check())
    
    async def check(self):
        while True:
            config = config_manager.config
            if config['auto_close'] and config['auto_switch_mode']:
                if is_game_window_exist():
                    image_processor.match_and_click()
                else:
                    print("[DEBUG] 崩坏3窗口不存在，跳过图像识别和点击")
            if config['auto_clip']:
                try:
                    if is_game_window_exist():
                        screenshot = image_processor.capture_screen()
                        if screenshot is not None:
                            await image_processor.parse_qr_code(
                                image_source='game_window',
                                config=config,
                                bh_info=config_manager.bh_info
                            )
                    else:
                        print("[DEBUG] 崩坏3窗口不存在，跳过自动截屏")
                except Exception as e:
                    print("[ERROR] 自动截屏时出错: %s", str(e))
            if config['clip_check'] and config.get('account_login', False):
                await image_processor.parse_qr_code(
                    image_source='clipboard',
                    config=config,
                    bh_info=config_manager.bh_info
                )
            time.sleep(config['sleep_time'])

# ========== 登录按钮点击回调 ==========
def login_accept():
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    ui.backendLogin.start()


# ========== 登录按钮点击回调 ==========
def login_accept():
    global config, bh_info, cap
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    ui.backendLogin.start()

# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(SelfMainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(r".\BHimage.ico"))
        self.prev_clip_check = config_manager.config['clip_check']
        self.prev_auto_clip = config_manager.config['auto_clip']
        self.prev_auto_close = config_manager.config['auto_close']
        self.prev_auto_switch = config_manager.config.get('auto_switch_mode', False)
    
    def handle_login_complete(self, success):
        if success:
            ui.loginBiliBtn.setText("账号已登录")
            ui.loginBiliBtn.setDisabled(False)
        else:
            ui.loginBiliBtn.setText("登录失败")
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
        dialog = mainWindow.LoginDialog(window)
        dialog.account.textChanged.connect(self.deal_account)
        dialog.password.textChanged.connect(self.deal_password)
        dialog.show()
        dialog.accepted.connect(login_accept)
    
    def deal_account(self, string):
        config = config_manager.config
        config['account'] = string
        config_manager.write_conf(config)
    
    def deal_password(self, string):
        config = config_manager.config
        config['password'] = string
        config_manager.write_conf(config)
    
    def qrCodeSwitch(self, boolean):
        if boolean:
            ui.clipCheck.setText("当前状态:启用")
        else:
            ui.clipCheck.setText("当前状态:关闭")
        config = config_manager.config
        config['clip_check'] = boolean
        config_manager.write_conf(config)
    
    def autoCloseSwitch(self, boolean):
        if boolean:
            ui.autoCloseCheck.setText("当前状态:启用")
        else:
            ui.autoCloseCheck.setText("当前状态:关闭")
        config = config_manager.config
        config['auto_close'] = boolean
        config_manager.write_conf(config)
    
    def autoClipSwitch(self, boolean):
        if boolean:
            ui.autoClipCheck.setText("当前状态:启用")
        else:
            ui.autoClipCheck.setText("当前状态:关闭")
        config = config_manager.config
        config['auto_clip'] = boolean
        config_manager.write_conf(config)
    
    def autoSwitchModeSwitch(self, boolean):
        if boolean:
            ui.autoSwitchModeCheck.setText("当前状态:启用")
        else:
            ui.autoSwitchModeCheck.setText("当前状态:关闭")
        config = config_manager.config
        config['auto_switch_mode'] = boolean
        config_manager.write_conf(config)
    
    def configGamePath(self):
        filePath, _ = QFileDialog.getOpenFileName(window, "选择崩坏3执行文件", "", "Executable Files (*.exe)")
        if filePath:
            config = config_manager.config
            config['game_path'] = filePath
            config_manager.write_conf(config)
            ui.configGamePathBtn.setText("路径已配置")
    
    def launchGame(self):
        config = config_manager.config
        if 'game_path' in config and config['game_path']:
            try:
                subprocess.Popen([config['game_path']])
                print("[INFO] 正在启动崩坏3...")
            except Exception as e:
                print(f"[ERROR] 启动失败: {str(e)}")
        else:
            print("[INFO] 请先配置游戏路径！")
            QMessageBox.warning(window, "路径未配置", "请先配置游戏路径！")
    
    def oneClickLogin(self):
        """一键登录功能"""
        self.launchGame()
        config = config_manager.config
        config['clip_check'] = True
        config['auto_clip'] = True
        config['auto_close'] = True
        config['auto_switch_mode'] = True
        config_manager.write_conf(config)
        ui.clipCheck.setText("当前状态:启用")
        ui.autoClipCheck.setText("当前状态:启用")
        ui.autoCloseCheck.setText("当前状态:启用")
        ui.autoSwitchModeCheck.setText("当前状态:启用")
        print("[INFO] 一键登录模式已启用")
        print("[INFO] 已临时启用所有功能")
        QTimer.singleShot(120000, self.restoreOriginalSettings)
    
    def restoreOriginalSettings(self):
        config = config_manager.config
        config['clip_check'] = self.prev_clip_check
        config['auto_clip'] = self.prev_auto_clip
        config['auto_close'] = self.prev_auto_close
        config['auto_switch_mode'] = self.prev_auto_switch
        config_manager.write_conf(config)
        ui.clipCheck.setText("当前状态:启用" if self.prev_clip_check else "当前状态:关闭")
        ui.autoClipCheck.setText("当前状态:启用" if self.prev_auto_clip else "当前状态:关闭")
        ui.autoCloseCheck.setText("当前状态:启用" if self.prev_auto_close else "当前状态:关闭")
        ui.autoSwitchModeCheck.setText("当前状态:启用" if self.prev_auto_switch else "当前状态:关闭")
        print("[INFO] 一键登录模式已结束，即将恢复原始设置")

# ========== Flask 启动 ==========
if __name__ == '__main__':

    # ========== 设置 stdout 重定向 ==========
    stream = EmittingStream()
    sys.stdout = stream
    stream.textWritten.connect(lambda text: ui.logText.append(text))

    #初始化配置
    set_qt_env()
    
    fapp = Flask(__name__)
    @fapp.route("/")
    def index():
        return render_template("index.html")
    
    @fapp.route("/geetest")
    def geetest():
        return render_template("geetest.html")
    
    @fapp.route('/ret', methods=["GET", "POST"])
    def ret():
        if not request.json:
            print("[INFO] 请求错误")
            abort(400)
        print("[INFO] Input = " + str(request.json))
        config_manager.cap = request.json  # 更新 cap
        ui.backendLogin = LoginThread()
        ui.backendLogin.update_log.connect(print)
        ui.backendLogin.login_complete.connect(window.handle_login_complete)
        ui.backendLogin.start()
        return "1"
    
    kwargs = {'host': '0.0.0.0', 'port': 12983, 'threaded': True, 'use_reloader': False, 'debug': False}
    flaskThread = Thread(target=fapp.run, daemon=True, kwargs=kwargs).start()
    
    # ========== GUI 初始化 ==========
    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow()
    ui.setupUi(window)
    
    try:
        config = config_manager.config
        if config['account'] != '':
            print("[INFO] 配置文件已有账号，尝试登录中...")
            ui.backendLogin = LoginThread()
            ui.backendLogin.update_log.connect(print)
            ui.backendLogin.login_complete.connect(window.handle_login_complete)
            ui.backendLogin.start()
        
        ui.clipCheck.setChecked(config['clip_check'])
        ui.autoCloseCheck.setChecked(config['auto_close'])
        ui.autoClipCheck.setChecked(config['auto_clip'])
        ui.autoSwitchModeCheck.setChecked(config.get('auto_switch_mode', False))
        window.qrCodeSwitch(config['clip_check'])
        window.autoCloseSwitch(config['auto_close'])
        window.autoClipSwitch(config['auto_clip'])
        window.autoSwitchModeSwitch(config.get('auto_switch_mode', False))
        
        if 'game_path' in config and config['game_path']:
            ui.configGamePathBtn.setText("路径已配置")
        else:
            ui.configGamePathBtn.setText("点击配置")
    
    except KeyError:
        config_manager.write_conf(config)
        print("[INFO] 配置文件异常，重置并跳过登录")
    
    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(print)
    ui.backendClipCheck.start()
    
    #显示窗口
    window.show()
    print(sys.argv)
    if '--auto-login' in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        print("[INFO] 检测到自动登录参数，将启动一键登录模式")
    else:
        print("NO")
    sys.exit(app.exec())