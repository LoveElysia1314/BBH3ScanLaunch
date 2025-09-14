# main.py
import ctypes
import sys
import os
import asyncio
import subprocess
import webbrowser
from threading import Thread
from flask import Flask, abort, render_template, request
import logging
from PySide6.QtCore import QThread, Signal, QTimer, QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from .core.sdk import bsgamesdk
from .core.sdk import mihoyosdk
from .gui import main_window as mainWindow
from .core.bh3_utils import image_processor, is_game_window_exist, click_center_of_game_window
from .utils.utils import DummyWriter

# ========== 初始化配置管理器和版本更新工具 ==========
from .utils.network_utils import network_manager
from .utils.config_utils import config_manager
from .utils.version_utils import version_manager  # 导入版本管理器

# ========== 全局变量 ==========
ui = None
window = None
app = None

# 获取默认版本信息（使用最新的支持版本）
oa_versions = version_manager.get_version_info("oa_versions")
if oa_versions:
    default_bh_ver = max(oa_versions.keys())
    BH_VER = default_bh_ver  # 当前崩坏三版本
    OA_TOKEN = version_manager.get_oa_token_for_version(default_bh_ver)  # 当前oa_token
else:
    BH_VER = "8.4.0"  # 默认版本
    OA_TOKEN = "e257aaa274fb2239094cbe64d9f5ee3e"  # 默认token


# ========== 更新检查线程 ==========
class UpdateCheckThread(QThread):
    """后台线程：检查更新并发射结果信号"""

    update_result = Signal(bool, str)  # has_update, version_info

    def run(self):
        try:
            has_update = version_manager.has_update()
            if has_update:
                latest_version = version_manager.get_version_info("remote")
                self.update_result.emit(True, latest_version)
            else:
                current_version = version_manager.get_version_info("current")
                self.update_result.emit(False, current_version)
        except Exception as e:
            logging.error(f"更新检查失败: {e}")
            self.update_result.emit(False, "检查失败")


# ========== 登陆线程 ==========
class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)  # 登录完成信号，传递成功/失败状态

    async def login(self):
        logging.info("正在登录B站账号...")
        try:
            config = config_manager.config
            if config["last_login_succ"]:
                logging.info(f"验证缓存账号 {config['uname']} 中...")
                bs_user_info = await bsgamesdk.getUserInfo(
                    config["uid"], config["access_key"]
                )
                if bs_user_info and "uname" in bs_user_info:
                    logging.info(f"登陆B站账号 {bs_user_info['uname']} 成功！")
                    bs_info = {"uid": config["uid"], "access_key": config["access_key"]}
                else:
                    logging.warning("缓存账号验证失败，将重新登录")
                    config.update(
                        {
                            "last_login_succ": False,
                            "uid": "",
                            "access_key": "",
                            "uname": "",
                        }
                    )
                    config_manager.write_conf(config)
            else:
                logging.info(f"登陆B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(
                    config["account"], config["password"], config_manager.cap
                )
                if not bs_info or "access_key" not in bs_info:
                    self.handle_login_failure(bs_info or {})
                    # 发出信号，即使失败也要通知主线程登录流程结束
                    self.login_complete.emit(False)
                    return
                bs_user_info = await bsgamesdk.getUserInfo(
                    bs_info["uid"], bs_info["access_key"]
                )
                if not bs_user_info or "uname" not in bs_user_info:
                    logging.error("获取用户信息失败")
                    self.login_complete.emit(False)
                    return
                logging.info(f"登陆B站账号 {bs_user_info['uname']} 成功！")
                config.update(
                    {
                        "uid": bs_info["uid"],
                        "access_key": bs_info["access_key"],
                        "last_login_succ": True,
                        "uname": bs_user_info["uname"],
                    }
                )
                config_manager.write_conf(config)
            logging.info("登陆崩坏3账号中...")
            bh_info = await mihoyosdk.verify(bs_info["uid"], bs_info["access_key"])
            config_manager.bh_info = bh_info
            if bh_info["retcode"] != 0:
                logging.info(f"登陆失败！{bh_info}")
                self.login_complete.emit(False)
                return
            logging.info("登录成功，账号：LoveElysia1314")
            logging.info("登陆成功！获取OA服务器信息中...")
            # 获取服务器版本号
            server_bh_ver = await mihoyosdk.getBHVer(BH_VER)
            # 检查版本是否匹配
            if server_bh_ver != BH_VER:
                logging.info(f"版本不匹配 (本地: {BH_VER}, 服务器: {server_bh_ver})！")

            # 检查是否有对应版本的支持
            if not version_manager.has_version_support(server_bh_ver):
                logging.warning(f"警告：当前配置不支持游戏版本 {server_bh_ver}！")
                logging.warning("请更新 version.json 中的 oa_versions 配置以支持新版本")
                # 可以选择使用默认版本或提示用户
                if version_manager.oa_versions:
                    # 使用最新的支持版本
                    supported_ver = max(version_manager.oa_versions.keys())
                    logging.info(f"将使用支持的版本 {supported_ver} 继续")
                    server_bh_ver = supported_ver
                else:
                    logging.error("无任何支持的版本配置！")
                    self.login_complete.emit(False)
                    return

            logging.info(f"当前崩坏3版本: {server_bh_ver}")

            # 根据服务器版本获取对应的OA_TOKEN
            OA_TOKEN = version_manager.get_oa_token_for_version(server_bh_ver)

            oa = await mihoyosdk.getOAServer(OA_TOKEN)
            if len(oa) < 100:
                logging.info("获取OA服务器失败！请检查Token后重试")
                self.login_complete.emit(False)
                return
            logging.info("获取OA服务器成功！")
            config["account_login"] = True
            config_manager.write_conf(config)
            self.login_complete.emit(True)
        except Exception as e:
            logging.error(f"登陆过程中发生错误: {str(e)}")
            self.login_complete.emit(False)  # 异常时也发出信号

    def handle_login_failure(self, bs_info):
        if "message" in bs_info:
            logging.info("登陆失败！")
            if bs_info["message"] == "PWD_INVALID":
                logging.info("账号或密码错误！")
            else:
                logging.info(f"原始返回：{bs_info['message']}")
        if "need_captch" in bs_info:
            logging.info("需要验证码！请打开下方网址进行操作！")
            logging.info(f"{bs_info['cap_url']}")
            webbrowser.open_new(bs_info["cap_url"])
        else:
            logging.info(f"登陆失败！{bs_info}")

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
                if config["auto_click"]:
                    if not self.is_admin():
                        # 管理员权限检查只打印一次警告
                        if not hasattr(self, "admin_warning_printed"):
                            logging.debug("没有管理员权限，跳过图形识别和点击")
                            self.admin_warning_printed = True
                    elif is_game_window_exist():
                        image_processor.match_and_click()

                # 处理自动截屏
                if config["auto_clip"]:
                    if is_game_window_exist():
                        screenshot = image_processor.capture_screen()
                        if screenshot:
                            qr_parsed = await image_processor.parse_qr_code(
                                image_source="game_window",
                                config=config,
                                bh_info=config_manager.bh_info,
                            )
                            if qr_parsed:
                                if config["auto_click"]:
                                    logging.info("扫码成功，4秒后将自动点击窗口中心")
                                    await asyncio.sleep(4)
                                    click_center_of_game_window()
                                if config["auto_close"]:
                                    logging.info("已启用自动退出，2秒后将关闭扫码器")
                                    await asyncio.sleep(2)
                                    self.exit_app.emit()
                                    return

                # 处理剪贴板检查：无论是否开启自动截图，只要已登录就尝试从剪贴板识别二维码
                if config.get("account_login", False):
                    await image_processor.parse_qr_code(
                        image_source="clipboard",
                        config=config,
                        bh_info=config_manager.bh_info,
                    )

                # 根据配置的间隔时间等待
                await asyncio.sleep(config["sleep_time"])

            except Exception as e:
                logging.error(f"检查过程中发生错误: {str(e)}")
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
    # 将线程日志转发到 logging（再由 GUI 处理器显示）
    ui.backendLogin.update_log.connect(lambda s: logging.info(s))
    # 连接登录完成信号到主窗口的处理函数
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
    # 连接登录完成信号到启动解析线程的函数
    ui.backendLogin.login_complete.connect(start_parse_thread_after_login)
    ui.backendLogin.start()


# ========== 新增：启动解析线程的函数 ==========
def start_parse_thread_after_login(success):
    # 无论登录成功与否，都启动 ParseThread
    # 如果有特定逻辑需要登录成功才启动，可以在这里添加 if success: 判断
    logging.info("登录流程完成，准备启动解析线程...")
    # 确保旧的线程被正确处理（如果存在）
    if hasattr(ui, "backendClipCheck") and ui.backendClipCheck.isRunning():
        logging.warning("解析线程已在运行中？")
        return
    # 创建并启动解析线程
    ui.backendClipCheck = ParseThread()
    ui.backendClipCheck.update_log.connect(lambda s: logging.info(s))
    ui.backendClipCheck.exit_app.connect(
        lambda: (window.restoreOriginalSettings(), app.quit())
    )
    ui.backendClipCheck.start()
    logging.info("登录完成，解析线程已启动")


# ========== GUI 日志处理器 ==========
class _LogEmitter(QObject):
    sig = Signal(str)


class GuiHandler(logging.Handler):
    """将日志线程安全地追加到 QTextBrowser。

    通过 Qt 信号切换到主线程，避免在非GUI线程直接操作控件。
    """

    def __init__(self, text_widget):
        super().__init__()
        self._emitter = _LogEmitter()
        # 连接到 QTextBrowser.append（QueuedConnection，线程安全）
        self._emitter.sig.connect(text_widget.append)
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        # 新增：重复日志过滤缓冲区，长度为3
        from collections import deque
        self._log_buffer = deque(maxlen=3)
        self.filter_enabled = True  # 可加配置开关

    def emit(self, record):
        try:
            msg = self.format(record)
            # 忽略空行
            if not msg.strip():
                return
            # 仅过滤 INFO/DEBUG，ERROR/WARNING 不过滤
            if self.filter_enabled and record.levelno in (logging.INFO, logging.DEBUG):
                # 检查最近3条是否有重复（只要出现过就拦截）
                if msg in self._log_buffer:
                    return  # 拦截输出
                self._log_buffer.append(msg)
            self._emitter.sig.emit(msg)
        except Exception:
            # 确保日志系统自身不抛异常
            pass


# ========== 主窗口类 ==========
class SelfMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"./BHimage.ico"))
        self.prev_settings = {}
        self.temp_mode = False
        # 初始化更新检查线程
        self.update_check_thread = UpdateCheckThread()
        self.update_check_thread.update_result.connect(self.on_update_check_finished)

    def handle_login_complete(self, success):
        # 登录完成后，解析线程将在 start_parse_thread_after_login 中启动,这里只负责更新UI状态
        status = "账号已登陆" if success else "登陆失败"
        ui.loginBiliBtn.setText(status)
        ui.loginBiliBtn.setDisabled(False)
        # print(f"[INFO] 登录UI状态已更新为: {status}")

    def login(self):
        config = config_manager.config
        if config.get("account_login", False):
            logging.info("账号已登陆")
            ui.loginBiliBtn.setText("账号已登陆")
            return
        logging.info("开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)
        dialog = mainWindow.LoginDialog(self)
        dialog.account.textChanged.connect(self.deal_config_update("account"))
        dialog.password.textChanged.connect(self.deal_config_update("password"))
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
        filePath, _ = QFileDialog.getOpenFileName(
            self, "选择崩坏3执行文件", "", "Executable Files (*.exe)"
        )
        if filePath:
            config = config_manager.config
            config["game_path"] = filePath
            config_manager.write_conf(config)
            ui.configGamePathBtn.setText("路径已配置")

    def launchGame(self):
        config = config_manager.config
        if config.get("game_path"):
            try:
                subprocess.Popen([config["game_path"]])
                logging.info("正在启动崩坏3...")
            except Exception as e:
                logging.error(f"启动失败: {str(e)}")
        else:
            logging.info("请先配置游戏路径！")
            QMessageBox.warning(self, "路径未配置", "请先配置游戏路径！")

    def oneClickLogin(self):
        self.launchGame()
        self.temp_mode = True
        config = config_manager.config
        for feature in [
            "clip_check",
            "auto_clip",
            "auto_close",
            "auto_click",
            "debug_print",
        ]:
            self.prev_settings[feature] = config.get(feature, False)
            config[feature] = True
        config_manager.write_conf(config)
        for checkbox, prefix in [
            (ui.clipCheck, "当前状态"),
            (ui.autoClip, "当前状态"),
            (ui.autoClose, "当前状态"),
            (ui.autoClick, "当前状态"),
        ]:
            checkbox.setChecked(True)
            self.update_status_text(checkbox, prefix)
        logging.info("一键登陆模式已启用")

    def restoreOriginalSettings(self):
        if not self.temp_mode:
            return
        config = config_manager.config
        for feature, value in self.prev_settings.items():
            config[feature] = value
        config_manager.write_conf(config)
        for checkbox, feature, prefix in [
            (ui.clipCheck, "clip_check", "当前状态"),
            (ui.autoClip, "auto_clip", "当前状态"),
            (ui.autoClose, "auto_close", "当前状态"),
            (ui.autoClick, "auto_click", "当前状态"),
        ]:
            checkbox.setChecked(config.get(feature, False))
            self.update_status_text(checkbox, prefix)
        logging.info("一键登陆模式已结束，恢复原始设置")

    def on_update_check_finished(self, has_update, version_info):
        """处理更新检查结果的槽函数"""
        if has_update:
            ui.updateStatusLabel.setText(f"更新可用: {version_info}")
            # 按钮文案与行为：改为“更新”，点击直接执行更新
            try:
                ui.checkUpdateBtn.clicked.disconnect()
            except Exception:
                pass
            ui.checkUpdateBtn.setText("更新")
            ui.checkUpdateBtn.clicked.connect(self.perform_update)
        else:
            ui.updateStatusLabel.setText(f"暂无更新：{version_info}")
            # 恢复按钮为“检查更新”，点击执行检查
            try:
                ui.checkUpdateBtn.clicked.disconnect()
            except Exception:
                pass
            ui.checkUpdateBtn.setText("检查更新")
            ui.checkUpdateBtn.clicked.connect(self.check_for_updates)
        # 重新创建线程以支持下次检查
        self.update_check_thread = UpdateCheckThread()
        self.update_check_thread.update_result.connect(self.on_update_check_finished)

    def check_and_display_updates(self):
        """启动后台线程检查更新并更新UI标签（用于程序初始化和手动检查）"""
        if self.update_check_thread.isRunning():
            return  # 如果线程正在运行，不重复启动
        ui.updateStatusLabel.setText("正在检查更新...")
        self.update_check_thread.start()

    def perform_update(self):
        """直接调用更新逻辑：自动择优源并在默认浏览器打开下载链接"""
        network_manager.open_best_download_in_browser(
            package_name="BBH3ScanLaunch_Setup.exe",
            tag="latest",
            source_priority=["gitee", "github"],
            strategy="fastest",
        )

    def check_for_updates(self):
        """检查更新（用户手动触发）——不再弹窗，按钮状态将由 check_and_display_updates 决定"""
        self.check_and_display_updates()


# ========== 应用启动函数 ==========
def main():
    """运行应用程序的核心逻辑"""
    # 设置全局变量
    global ui, window, app

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = config_manager.config
    # 根据配置切换日志级别（启用 DEBUG 时显示更多线程日志）
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if config.get("debug_print", False) else logging.INFO)

    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow()  # 实例化 UI
    ui.setupUi(window)  # 设置 UI 到窗口
    # 添加 GUI 日志处理器
    handler = GuiHandler(ui.logText)
    logging.getLogger().addHandler(handler)

    # Flask 应用设置
    # 计算模板文件夹路径（相对于_internal/的resources/templates文件夹）
    template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "templates")
    fapp = Flask(__name__, template_folder=template_dir)
    # 禁用 Werkzeug 的日志
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    # 禁用 Flask 的启动信息
    cli = sys.modules["flask.cli"]
    cli.show_server_banner = lambda *x: None

    @fapp.route("/")
    def index():
        return render_template("index.html")

    @fapp.route("/geetest")
    def geetest():
        return render_template("geetest.html")

    @fapp.route("/ret", methods=["POST"])
    def ret():
        if not request.json:
            logging.info("请求错误")
            abort(400)
        input_data = request.json
        logging.debug(f"Input = {input_data}")
        config_manager.cap = input_data
        login_accept()
        return "1"

    flaskThread = Thread(
        target=fapp.run,
        daemon=True,
        kwargs={
            "host": "0.0.0.0",
            "port": 12983,
            "threaded": True,
            "use_reloader": False,
            "debug": False,
        },
    )
    flaskThread.start()

    # --- 在显示窗口前应用配置 ---
    # 尝试自动登录
    if config["account"]:
        logging.info("配置文件已有账号，尝试登陆中...")
        # 注意：此时UI控件已创建，可以安全调用
        login_accept()

    # 应用配置到UI控件 (移到 setupUi 之后)
    for checkbox, feature, prefix in [
        (ui.clipCheck, "clip_check", "当前状态"),
        (ui.autoClose, "auto_close", "当前状态"),
        (ui.autoClip, "auto_clip", "当前状态"),
        (ui.autoClick, "auto_click", "当前状态"),
        (ui.debugPrint, "debug_print", "当前状态"),
    ]:
        # 使用 config.get 并提供默认值 False，确保不会因键缺失出错
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    # 更新游戏路径按钮文本
    ui.configGamePathBtn.setText(
        "路径已配置" if config.get("game_path") else "点击配置"
    )

    # 显示窗口
    window.show()

    # 程序启动时自动检查更新（不弹窗）
    window.check_and_display_updates()

    # 处理命令行参数
    if "--auto-login" in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        logging.info("检测到自动登陆参数，将启动一键登陆模式")

    sys.exit(app.exec())


# ========== Flask 启动 ==========
if __name__ == "__main__":
    main()
