# -*- coding: utf-8 -*-
# 标准库 imports
import json
from json.decoder import JSONDecodeError
import os
import subprocess
import sys
import time
import webbrowser
from threading import Thread
import asyncio
from flask import Flask, abort, render_template, request
# 第三方库 imports
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox

# 自定义模块 imports
import bsgamesdk
import mihoyosdk
import mainWindow
from image_processor import image_processor, is_game_window_exist

# 解决打包后Qt插件加载问题
if getattr(sys, 'frozen', False):
    # 单文件打包模式
    plugin_path = os.path.join(sys._MEIPASS, 'qt6_plugins')
    os.environ['QT_PLUGIN_PATH'] = plugin_path
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(plugin_path, 'platforms')
    
    # 添加插件路径到库搜索路径
    if sys.platform == 'win32':
        os.add_dll_directory(plugin_path)

# ========== EmittingStream 类：用于拦截 stdout 输出 ==========
class EmittingStream(QObject):
    textWritten = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.original_stdout = sys.stdout

    def write(self, text):
        self.original_stdout.write(text)
        self.textWritten.emit(text)

    def flush(self):
        self.original_stdout.flush()
        

# ========== 全局变量 ==========
m_cast_group_ip = '239.0.1.255'
m_cast_group_port = 12585
bh_info = {}
config = {}
data = {}
cap = None  # 确保在全局作用域定义

# ========== 初始化配置文件 ==========
def init_conf():
    global config
    conf_loop = True
    while conf_loop:
        if not os.path.isfile('./config.json'):
            write_conf()
        try:
            with open('./config.json') as fp:
                config = json.loads(fp.read())
                try:
                    if config['ver'] != 6:
                        print('配置文件已更新，请注意重新修改文件')
                        write_conf(config)
                        continue
                except KeyError:
                    print('配置文件已更新，请注意重新修改文件')
                    write_conf(config)
                    continue
        except JSONDecodeError:
            print('配置文件格式不正确 重新写入中...')
            write_conf()
            continue
        conf_loop = False
    print("配置文件检查完成")
    config['account_login'] = False

# ========== 写入配置文件 ==========
def write_conf(old=None):
    config_temp = json.loads('{"account":"","password":"","sleep_time":1,"ver":6,'
                             '"clip_check":false,"auto_close":false,"uid":0,'
                             '"access_key":"","last_login_succ":false,"bh_ver":"7.8.0",'
                             '"uname":"","auto_clip":false,"oa_token":"ebdda08dce6feb6bc552d393bae58c81",'
                             '"game_path":"","auto_switch_mode":false}')  # 添加 auto_switch_mode 字段
    if old is not None:
        for key in config_temp:
            try:
                config_temp[key] = old[key]
            except KeyError:
                continue
    config_temp['ver'] = 6
    with open('./config.json', 'w') as f:
        output = json.dumps(config_temp, sort_keys=True, indent=4, separators=(',', ': '))
        f.write(output)

# ========== 登录线程 ==========
class LoginThread(QThread):
    update_log = pyqtSignal(str)
    login_complete = pyqtSignal(bool)  # 新增登录完成信号

    def run(self):
        asyncio.run(self.login())

    async def login(self):
        global config, bh_info, cap
        print("[INFO] 登录B站账号中...")
        try:
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
                    write_conf(config)
                    print(f"[INFO] 缓存已失效，重新登录B站账号 {config['account']} 中...")
                    bs_info = await bsgamesdk.login(config['account'], config['password'], cap)
                    if "access_key" not in bs_info:
                        self.handle_login_failure(bs_info)
                        return
                    bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                    print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                    config['uid'] = bs_info['uid']
                    config['access_key'] = bs_info['access_key']
                    config['last_login_succ'] = True
                    config['uname'] = bs_user_info["uname"]
                    write_conf(config)
            else:
                print(f"[INFO] 登录B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(config['account'], config['password'], cap)
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
                    return
                bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
                print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
                config['uid'] = bs_info['uid']
                config['access_key'] = bs_info['access_key']
                config['last_login_succ'] = True
                config['uname'] = bs_user_info["uname"]
                write_conf(config)
            
            print("[INFO] 登录崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
            if bh_info['retcode'] != 0:
                print("[INFO] 登录失败！")
                print("[INFO]" + str(bh_info))
                self.login_complete.emit(False)
                return
            
            print("[INFO] 登录成功！")
            print("[INFO] 获取OA服务器信息中...")
            bh_ver = await mihoyosdk.getBHVer(config)
            config['bh_ver'] = bh_ver
            write_conf(config)
            print(f"[INFO] 当前崩坏3版本: {bh_ver}")
            oa = await mihoyosdk.getOAServer(config['oa_token'])
            if len(oa) < 100:
                print("[INFO] 获取OA服务器失败！请检查Token后重试")
                self.login_complete.emit(False)
                return
            
            print("[INFO] 获取OA服务器成功！")
            ui.loginBiliBtn.setText("账号已登录")
            config['account_login'] = True
            write_conf(config)
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
    update_log = pyqtSignal(str)

    def run(self):
        asyncio.run(self.check())

    async def check(self):
        global config, bh_info
        while True:
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
                            await image_processor.parse_qr_code(image_source='game_window', config=config, bh_info=bh_info)
                    else:
                        print("[DEBUG] 崩坏3窗口不存在，跳过自动截屏")
                except Exception as e:
                    print("[INFO] 自动截屏时出错: %s", str(e))
            
            if config['clip_check'] and config.get('account_login', False):
                await image_processor.parse_qr_code(image_source='clipboard', config=config, bh_info=bh_info)
            
            time.sleep(config['sleep_time'])

# ========== 登录按钮点击回调 ==========
def login_accept():
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(window.printLog)
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    ui.backendLogin.start()

# ========== 账号/密码输入回调 ==========
def deal_password(string):
    global config
    config['password'] = string

def deal_account(string):
    global config
    config['account'] = string

# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(SelfMainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(r".\BHimage.ico"))
        self.prev_clip_check = False
        self.prev_auto_clip = False
        self.prev_auto_close = False
        self.prev_auto_switch = False

    @staticmethod
    def printLog(msg):
        print(msg)
        ui.logText.append(msg)

    def handle_login_complete(self, success):
        """处理登录完成信号"""
        if success:
            ui.loginBiliBtn.setText("账号已登录")
            ui.loginBiliBtn.setDisabled(False)
        else:
            ui.loginBiliBtn.setText("登录失败")
            ui.loginBiliBtn.setDisabled(False)

    def login(self):
        global config
        if config.get('account_login', False):
            print("[INFO] 账号已登录")
            ui.loginBiliBtn.setText("账号已登录")
            return
            
        print("[INFO] 开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)
        dialog = mainWindow.LoginDialog(window)
        dialog.account.textChanged.connect(deal_account)
        dialog.password.textChanged.connect(deal_password)
        dialog.show()
        dialog.accepted.connect(login_accept)

    def qrCodeSwitch(self, boolean):
        if boolean:
            ui.clipCheck.setText("当前状态:启用")
        else:
            ui.clipCheck.setText("当前状态:关闭")
        config['clip_check'] = boolean
        write_conf(config)

    def autoCloseSwitch(self, boolean):
        if boolean:
            ui.autoCloseCheck.setText("当前状态:启用")
        else:
            ui.autoCloseCheck.setText("当前状态:关闭")
        config['auto_close'] = boolean
        write_conf(config)

    def autoClipSwitch(self, boolean):
        if boolean:
            ui.autoClipCheck.setText("当前状态:启用")
        else:
            ui.autoClipCheck.setText("当前状态:关闭")
        config['auto_clip'] = boolean
        write_conf(config)

    def autoSwitchModeSwitch(self, boolean):
        if boolean:
            ui.autoSwitchModeCheck.setText("当前状态:启用")
        else:
            ui.autoSwitchModeCheck.setText("当前状态:关闭")
        config['auto_switch_mode'] = boolean
        write_conf(config)

    def configGamePath(self):
        filePath, _ = QFileDialog.getOpenFileName(window, "选择崩坏3执行文件", "", "Executable Files (*.exe)")
        if filePath:
            global config
            config['game_path'] = filePath
            write_conf(config)
            ui.configGamePathBtn.setText("路径已配置")

    def launchGame(self):
        global config
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
        config['clip_check'] = True
        config['auto_clip'] = True
        config['auto_close'] = True
        config['auto_switch_mode'] = True
        
        ui.clipCheck.setText("当前状态:启用")
        ui.autoClipCheck.setText("当前状态:启用")
        ui.autoCloseCheck.setText("当前状态:启用")
        ui.autoSwitchModeCheck.setText("当前状态:启用")
        
        print("[INFO] 一键登录模式已启用")
        print("[INFO] 已开启: 解析二维码, 自动截屏, 扫码完成后自动退出, 自动切换扫码模式")
        print("[INFO] 这些设置仅在当前会话有效，不会写入配置文件")
        
        QTimer.singleShot(120000, self.restoreOriginalSettings)

    def restoreOriginalSettings(self):
        """恢复原始设置"""
        config['clip_check'] = self.prev_clip_check
        config['auto_clip'] = self.prev_auto_clip
        config['auto_close'] = self.prev_auto_close
        config['auto_switch_mode'] = self.prev_auto_switch
        
        ui.clipCheck.setText("当前状态:启用" if self.prev_clip_check else "当前状态:关闭")
        ui.autoClipCheck.setText("当前状态:启用" if self.prev_auto_clip else "当前状态:关闭")
        ui.autoCloseCheck.setText("当前状态:启用" if self.prev_auto_close else "当前状态:关闭")
        ui.autoSwitchModeCheck.setText("当前状态:启用" if self.prev_auto_switch else "当前状态:关闭")
        
        print("一键登录模式已结束，恢复原始设置")


def resource_path(relative_path):
    """获取资源绝对路径，支持开发模式和PyInstaller单文件模式"""
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# ========== Flask 启动 ==========
if __name__ == '__main__':

    # ============ 解决Qt插件问题 ============
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
        plugin_path = os.path.join(base_dir, 'qt6_plugins')
        
        # 设置环境变量
        os.environ['QT_PLUGIN_PATH'] = plugin_path
        if sys.platform == 'win32':
            os.add_dll_directory(plugin_path)
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(plugin_path, 'platforms')
    
    # ============ 解决工作目录问题 ============
    # 获取可执行文件真实目录
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.argv[0])
        # 切换到可执行文件所在目录（可选）
        os.chdir(app_dir)


    init_conf()

    auto_login = False
    if len(sys.argv) > 1 and sys.argv[1] == '--auto-login':
        auto_login = True
        print("[INFO] 检测到自动登录参数，将启动一键登录模式")
        
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
        global cap
        cap = request.json
        ui.backendLogin = LoginThread()
        ui.backendLogin.update_log.connect(window.printLog)
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
        if config['account'] != '':
            print("[INFO] 配置文件已有账号，尝试登录中...")
            ui.backendLogin = LoginThread()
            ui.backendLogin.update_log.connect(window.printLog)
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
        write_conf(config)
        print("[INFO] 配置文件异常，重置并跳过登录")

    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(window.printLog)
    ui.backendClipCheck.start()

    # ========== 设置 stdout 重定向 ==========
    stream = EmittingStream()
    sys.stdout = stream
    stream.textWritten.connect(lambda text: ui.logText.append(text) if text.startswith("[INFO]") else None)

    window.show()
    
    if auto_login:
        QTimer.singleShot(1000, window.oneClickLogin)
    
    sys.exit(app.exec())