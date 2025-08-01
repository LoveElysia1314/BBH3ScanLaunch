# main.py
import ctypes
import sys
import asyncio
import subprocess
import webbrowser
from threading import Thread
from flask import Flask, abort, render_template, request
import logging
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
import bsgamesdk
import mihoyosdk
import mainWindow
from bh3_utils import image_processor, is_game_window_exist, click_center_of_game_window
from utils import EmittingStream
# ========== 初始化配置管理器和版本更新工具 ==========
from network_utils import network_manager
from config_utils import config_manager
from version_utils import version_manager  # 导入版本管理器和版本变量

BH_VER = version_manager.get_version_info("bh_ver") # 当前崩坏三版本
OA_TOKEN = version_manager.get_version_info("oa_token") # 当前oa_token

# ========== 登陆线程 ==========
class LoginThread(QThread):  
    update_log = Signal(str)
    login_complete = Signal(bool) # 登录完成信号，传递成功/失败状态

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
                    # 发出信号，即使失败也要通知主线程登录流程结束
                    self.login_complete.emit(False)
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
            print("[INFO] 登陆成功！获取OA服务器信息中...")
            # 获取服务器版本号
            server_bh_ver = await mihoyosdk.getBHVer(BH_VER)
            # 检查版本是否匹配
            if server_bh_ver != BH_VER:
                print(f"[INFO] 版本不匹配 (本地: {BH_VER}, 服务器: {server_bh_ver})！")
            print(f"[INFO] 当前崩坏3版本: {server_bh_ver}")
            oa = await mihoyosdk.getOAServer(OA_TOKEN) 
            if len(oa) < 100:
                print("[INFO] 获取OA服务器失败！请检查Token后重试")
                self.login_complete.emit(False)
                return
            print("[INFO] 获取OA服务器成功！")
            config['account_login'] = True
            config_manager.write_conf(config)
            self.login_complete.emit(True)
        except Exception as e:
            print(f"[ERROR] 登陆过程中发生错误: {str(e)}")
            self.login_complete.emit(False) # 异常时也发出信号

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

    def run(self):
        asyncio.run(self.login())

# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = Signal(str)
    exit_app = Signal()
    should_stop = False  # 新增：控制线程停止的标志

    def is_admin(self):
        """使用Windows API检查管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    async def periodic_check(self):
        """定期执行检查任务"""
        while not self.should_stop:
            try:
                # 每次循环都获取最新的配置
                config = config_manager.config
                
                # 处理自动点击
                if config['auto_click']:
                    if not self.is_admin():
                        # 管理员权限检查只打印一次警告
                        if not hasattr(self, 'admin_warning_printed'):
                            print("[INFO] 没有管理员权限，跳过图形识别和点击")
                            self.admin_warning_printed = True
                    elif is_game_window_exist():
                        image_processor.match_and_click()
                
                # 处理自动截屏
                if config['auto_clip']:
                    if is_game_window_exist():
                        screenshot = image_processor.capture_screen()
                        if screenshot:
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
                
                # 处理剪贴板检查
                if config['clip_check'] and config.get('account_login', False):
                    await image_processor.parse_qr_code(
                        image_source='clipboard',
                        config=config,
                        bh_info=config_manager.bh_info
                    )
                
                # 根据配置的间隔时间等待
                await asyncio.sleep(config['sleep_time'])
                
            except Exception as e:
                print(f"[ERROR] 检查过程中发生错误: {str(e)}")
                # 短暂等待后继续，避免频繁报错
                await asyncio.sleep(1)

    def stop(self):
        """停止线程"""
        self.should_stop = True

    def run(self):
        asyncio.run(self.periodic_check())

# ========== 登陆按钮点击回调 ==========
def login_accept():
    # 创建并启动登录线程
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(print)
    # 连接登录完成信号到主窗口的处理函数
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    # 连接登录完成信号到启动解析线程的函数
    ui.backendLogin.login_complete.connect(start_parse_thread_after_login)
    ui.backendLogin.start()

# ========== 新增：启动解析线程的函数 ==========
def start_parse_thread_after_login(success):
    # 无论登录成功与否，都启动 ParseThread
    # 如果有特定逻辑需要登录成功才启动，可以在这里添加 if success: 判断
    print("[INFO] 登录流程完成，准备启动解析线程...")
    # 确保旧的线程被正确处理（如果存在）
    if hasattr(ui, 'backendClipCheck') and ui.backendClipCheck.isRunning():
        print("[WARNING] 解析线程已在运行中？")
        return
    # 创建并启动解析线程
    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(print)
    ui.backendClipCheck.exit_app.connect(lambda: (window.restoreOriginalSettings(), app.quit()))
    ui.backendClipCheck.start()
    print("[INFO] 解析线程已启动")

# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"./BHimage.ico"))
        self.prev_settings = {}
        self.temp_mode = False

    def handle_login_complete(self, success):
        # 登录完成后，解析线程将在 start_parse_thread_after_login 中启动,这里只负责更新UI状态
        status = "账号已登陆" if success else "登陆失败"
        ui.loginBiliBtn.setText(status)
        ui.loginBiliBtn.setDisabled(False)
        # print(f"[INFO] 登录UI状态已更新为: {status}")

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
        for feature in ['clip_check', 'auto_clip', 'auto_close', 'auto_click', 'debug_print']:
            self.prev_settings[feature] = config.get(feature, False)
            config[feature] = True
        config_manager.write_conf(config)
        for checkbox, prefix in [
            (ui.clipCheck, "当前状态"),
            (ui.autoClip, "当前状态"),
            (ui.autoClose, "当前状态"),
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
            (ui.autoClip, 'auto_clip', "当前状态"),
            (ui.autoClose, 'auto_close', "当前状态"),
            (ui.autoClick, 'auto_click', "当前状态"),
        ]:
            checkbox.setChecked(config.get(feature, False))
            self.update_status_text(checkbox, prefix)
        print("[INFO] 一键登陆模式已结束，恢复原始设置")

    def check_and_display_updates(self):
        """检查更新并更新UI标签（用于程序初始化）"""
        ui.updateStatusLabel.setText("正在检查更新...")
        has_update = version_manager.has_update()
        if has_update:
            latest_version = version_manager.get_version_info('remote')
            ui.updateStatusLabel.setText(f"更新可用: {latest_version}")
        else:
            current_version = version_manager.get_version_info('current')
            ui.updateStatusLabel.setText(f"暂无更新：{current_version}")
        return has_update

    def check_for_updates(self):
        """检查更新并弹窗询问（用户手动触发）"""
        has_update = self.check_and_display_updates()
        if has_update:
            latest_version = version_manager.get_version_info('remote')
            reply = QMessageBox.question(self, '更新', f'发现新版本 {latest_version}，是否前往下载？',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                network_manager.open_browser_for_download(source='gitee')

# ========== Flask 启动 ==========
if __name__ == '__main__':
    stream = EmittingStream()
    config = config_manager.config
    stream.show_debug_gui = config['debug_print'] # 调整信息输出级别
    sys.stdout = stream

    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow() # 实例化 UI
    ui.setupUi(window) # 设置 UI 到窗口
    # 连接信号流到print 
    stream.textWritten.connect(lambda text: ui.logText.append(text))

    # Flask 应用设置
    fapp = Flask(__name__)
    # 禁用 Werkzeug 的日志
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    # 禁用 Flask 的启动信息
    cli = sys.modules['flask.cli']
    cli.show_server_banner = lambda *x: None

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

    # --- 在显示窗口前应用配置 ---
    # 尝试自动登录
    if config['account']:
        print("[INFO] 配置文件已有账号，尝试登陆中...")
        # 注意：此时UI控件已创建，可以安全调用
        login_accept()

    # 应用配置到UI控件 (移到 setupUi 之后)
    for checkbox, feature, prefix in [
        (ui.clipCheck, 'clip_check', "当前状态"),
        (ui.autoClose, 'auto_close', "当前状态"),
        (ui.autoClip, 'auto_clip', "当前状态"),
        (ui.autoClick, 'auto_click', "当前状态"),
        (ui.debugPrint, 'debug_print', "当前状态")
    ]:
        # 使用 config.get 并提供默认值 False，确保不会因键缺失出错
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    # 更新游戏路径按钮文本
    ui.configGamePathBtn.setText("路径已配置" if config.get('game_path') else "点击配置")

    # 显示窗口
    window.show()

    # 程序启动时自动检查更新（不弹窗）
    window.check_and_display_updates()

    # 处理命令行参数
    if '--auto-login' in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        print("[INFO] 检测到自动登陆参数，将启动一键登陆模式")

    sys.exit(app.exec())
