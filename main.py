# -*- coding: utf-8 -*-
import sys
import asyncio
import json
import os.path
import time
import webbrowser
from json.decoder import JSONDecodeError
from threading import Thread
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PIL import ImageGrab
from pyzbar.pyzbar import decode
import subprocess
import mainWindow
from flask import Flask, abort, render_template, request
from PIL import Image, ImageGrab


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
cap = None


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
                        print('[INFO] 配置文件已更新，请注意重新修改文件')
                        write_conf(config)
                        continue
                except KeyError:
                    print('[INFO] 配置文件已更新，请注意重新修改文件')
                    write_conf(config)
                    continue
        except JSONDecodeError:
            print('[INFO] 配置文件格式不正确 重新写入中...')
            write_conf()
            continue
        conf_loop = False
    print("[INFO] 配置文件检查完成")
    config['account_login'] = False


# ========== 写入配置文件 ==========
def write_conf(old=None):
    config_temp = json.loads('{"account":"","password":"","sleep_time":3,"ver":5,'
                             '"clip_check":false,"auto_close":false,"uid":0,'
                             '"access_key":"","last_login_succ":false,"bh_ver":"7.8.0",'
                             '"uname":"","auto_clip":false,"oa_token":"ebdda08dce6feb6bc552d393bae58c81",'
                             '"game_path":""}')
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

    def run(self):
        asyncio.run(self.login())

    async def login(self):
        global config, bh_info
        print("[INFO] 登录B站账号中...")
        import bsgamesdk
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
                    if 'need_captch' in bs_info:
                        print("[INFO] 需要验证码！请打开下方网址进行操作！")
                        print("[INFO]" + bs_info['cap_url'])
                        webbrowser.open_new(bs_info['cap_url'])
                    else:
                        print("[INFO] 登录失败！")
                        print("[INFO]" + str(bs_info))
                    ui.loginBiliBtn.setText("登陆账号")
                    ui.loginBiliBtn.setDisabled(False)
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
                if 'message' in bs_info:
                    print("[INFO] 登录失败！")
                    if bs_info['message'] == 'PWD_INVALID':
                        print("[INFO] 账号或密码错误！")
                        ui.loginBiliBtn.setText("登陆账号")
                        ui.loginBiliBtn.setDisabled(False)
                        return
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
                return
            bs_user_info = await bsgamesdk.getUserInfo(bs_info['uid'], bs_info['access_key'])
            print(f"[INFO] 登录B站账号 {bs_user_info['uname']} 成功！")
            config['uid'] = bs_info['uid']
            config['access_key'] = bs_info['access_key']
            config['last_login_succ'] = True
            config['uname'] = bs_user_info["uname"]
            write_conf(config)
        print("[INFO] 登录崩坏3账号中...")
        import mihoyosdk
        bh_info = await mihoyosdk.verify(bs_info['uid'], bs_info['access_key'])
        if bh_info['retcode'] != 0:
            print("[INFO] 登录失败！")
            print("[INFO]" + str(bh_info))
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
            return
        print("[INFO] 获取OA服务器成功！")
        ui.loginBiliBtn.setText("账号已登录")
        config['account_login'] = True
        write_conf(config)


# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = pyqtSignal(str)

    def run(self):
        asyncio.run(self.check())

    async def check(self):
        while True:
            if config['auto_close']:
                if config['auto_clip']:
                    import pyautogui
                    import pygetwindow as gw
                    if gw.getActiveWindowTitle() == '崩坏3':
                        window = gw.getWindowsWithTitle('崩坏3')[0]
                        if window:
                            left, top, right, bottom = window.left, window.top, window.right, window.bottom
                            screenshot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
                            await parse_pic_raw(screenshot, lambda msg: print(msg))
                if config['clip_check']:
                    await parse_pic(lambda msg: print(msg))
                time.sleep(config['sleep_time'])


# ========== 图像解析函数 ==========
async def parse_pic(printLog):
    if config['account_login']:
        im = ImageGrab.grabclipboard()
        if isinstance(im, Image.Image):
            return await parse_pic_raw(im, printLog)
    else:
        print("[DEBUG] 当前未登录或登陆中，跳过当前图片处理")


async def parse_pic_raw(im, printLog):
    if isinstance(im, Image.Image):
        printLog("[INFO] 识别到图片，开始检测是否为崩坏3登陆码")
        result = decode(im)
        if len(result) >= 1:
            url = result[0].data.decode('utf-8')
            param = url.split('?')[1]
            params = param.split('&')
            ticket = ''
            for element in params:
                if element.split('=')[0] == 'ticket':
                    ticket = element.split('=')[1]
                    break
            printLog("[INFO] 二维码识别成功，开始请求崩坏3服务器完成扫码")
            import mihoyosdk
            await mihoyosdk.scanCheck(lambda msg: print(msg), bh_info, ticket, config)
            time.sleep(1)
            clear_clipboard()
        else:
            printLog("[DEBUG] 非登陆码，跳过")


# ========== 清空剪贴板 ==========
def clear_clipboard():
    from ctypes import windll
    if windll.user32.OpenClipboard(None):
        windll.user32.EmptyClipboard()
        windll.user32.CloseClipboard()


# ========== 登录按钮点击回调 ==========
def login_accept():
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(window.printLog)
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

    @staticmethod
    def printLog(msg):
        print(msg)
        ui.logText.append(msg)

    @staticmethod
    def login():
        global config
        if config['account_login']:
            print("[INFO] 账号已登录")
            ui.loginBiliBtn.setText("账号已登录")
        print("[INFO] 开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)
        dialog = mainWindow.LoginDialog(window)
        dialog.account.textChanged.connect(deal_account)
        dialog.password.textChanged.connect(deal_password)
        dialog.show()
        dialog.accepted.connect(login_accept)

    @staticmethod
    def qrCodeSwitch(boolean):
        if boolean:
            ui.clipCheck.setText("当前状态:启用")
        else:
            ui.clipCheck.setText("当前状态:关闭")
        config['clip_check'] = boolean
        write_conf(config)

    @staticmethod
    def autoCloseSwitch(boolean):
        if boolean:
            ui.autoCloseCheck.setText("当前状态:启用")
        else:
            ui.autoCloseCheck.setText("当前状态:关闭")
        config['auto_close'] = boolean
        write_conf(config)

    @staticmethod
    def autoClipSwitch(boolean):
        if boolean:
            ui.autoClipCheck.setText("当前状态:启用")
        else:
            ui.autoClipCheck.setText("当前状态:关闭")
        config['auto_clip'] = boolean
        write_conf(config)

    @staticmethod
    def configGamePath():
        filePath, _ = QFileDialog.getOpenFileName(window, "选择崩坏3执行文件", "", "Executable Files (*.exe)")
        if filePath:
            global config
            config['game_path'] = filePath
            write_conf(config)
            ui.configGamePathBtn.setText("路径已配置")

    @staticmethod
    def launchGame():
        global config
        if 'game_path' in config and config['game_path']:
            try:
                subprocess.Popen([config['game_path']])
                print("[INFO] 正在启动崩坏3...")
            except Exception as e:
                print(f"[INFO] 启动失败: {e}")
        else:
            print("[INFO] 请先配置游戏路径！")


# ========== Flask 启动 ==========
if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    init_conf()
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
            ui.backendLogin.start()
        if config['clip_check']:
            ui.clipCheck.setText("当前状态:启用")
        else:
            ui.clipCheck.setText("当前状态:关闭")
        ui.clipCheck.setChecked(config['clip_check'])
        if config['auto_close']:
            ui.autoCloseCheck.setText("当前状态:启用")
        else:
            ui.autoCloseCheck.setText("当前状态:关闭")
        ui.autoCloseCheck.setChecked(config['auto_close'])
        if config['auto_clip']:
            ui.autoClipCheck.setText("当前状态:启用")
        else:
            ui.autoClipCheck.setText("当前状态:关闭")
        ui.autoClipCheck.setChecked(config['auto_clip'])
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
    sys.exit(app.exec())