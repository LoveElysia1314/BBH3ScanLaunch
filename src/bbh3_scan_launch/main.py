# main.py
import ctypes
import sys
import asyncio
import webbrowser
import atexit
from threading import Thread
from flask import Flask, abort, render_template, request
import logging
from PySide6.QtCore import QThread, Signal, QTimer, QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from .core.sdk import bsgamesdk
from .core.sdk import mihoyosdk
from .gui import main_window as mainWindow
from .core.bh3_utils import (
    image_processor,
    click_center_of_game_window,
)
from .core.bh3_utils import BH3GameManager
from .constants import TEMPLATE_WEB_DIR
from .utils.exception_utils import handle_exceptions

# ========== 初始化配置管理器和版本更新工具 ==========
from .dependency_container import (
    get_version_manager,
    get_config_manager,
    get_network_manager,
)

# 获取全局管理器实例
network_manager = get_network_manager()
config_manager = get_config_manager()
version_manager = get_version_manager()

# ========== 全局变量 ==========
ui = None
window = None
app = None
game_manager = BH3GameManager()

# 获取默认版本信息（使用最新的支持版本）
oa_versions = version_manager.get_version_info("oa_versions")
BH_VER = (
    max(oa_versions.keys()) if oa_versions else version_manager.DEFAULT_BHVER
)  # 当前崩坏三版本
OA_TOKEN = version_manager.get_oa_token_for_version(BH_VER)  # 当前oa_token


# ========== 更新下载线程 ==========
class UpdateDownloadThread(QThread):
    """后台线程：执行更新下载操作，避免阻塞主线程"""

    update_status = Signal(str)  # 发送状态更新信号

    @handle_exceptions("更新下载失败", None)
    def run(self):
        # 检查是否已被请求停止
        if self.isInterruptionRequested():
            return

        self.update_status.emit("正在准备下载...")
        # 使用全局导入的network_manager

        # 尝试按优先级下载
        success = network_manager.try_download_by_priority()

        # 再次检查是否已被请求停止
        if self.isInterruptionRequested():
            return

        if success:
            self.update_status.emit("已在浏览器中打开下载链接")
        else:
            self.update_status.emit("所有下载源均不可用")


# ========== 更新检查线程 ==========
class UpdateCheckThread(QThread):
    """后台线程：检查更新并发射结果信号"""

    update_result = Signal(bool, str)  # has_update, version_info
    update_status = Signal(str)  # 发送状态更新信号

    @handle_exceptions("更新检查失败", None)
    def run(self):
        # 发送状态：开始检查更新
        self.update_status.emit("正在获取远程版本信息...")

        # 使用全局导入的config_manager检查更新
        update_info = config_manager.check_program_update()

        if update_info.get("has_update"):
            self.update_status.emit("发现新版本")
            self.update_result.emit(True, update_info["remote_version"])
        else:
            self.update_status.emit("当前已是最新版本")
            self.update_result.emit(False, update_info.get("current_version", "未知"))


# ========== 登陆线程 ==========
class LoginThread(QThread):
    update_log = Signal(str)
    login_complete = Signal(bool)  # 登录完成信号，传递成功/失败状态

    @handle_exceptions("登陆过程中发生错误", None)
    async def login(self):
        logging.info("正在登录B站账号...")
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
                # 缓存验证失败后，重新进行完整登录流程
                logging.info(f"重新登陆B站账号 {config['account']} 中...")
                bs_info = await bsgamesdk.login(
                    config["account"], config["password"], config_manager.cap
                )
                if not bs_info:
                    logging.error("登录请求失败，返回结果为空")
                    self.login_complete.emit(False)
                    return
                if "access_key" not in bs_info:
                    self.handle_login_failure(bs_info)
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
                logging.info(f"重新登陆B站账号 {bs_user_info['uname']} 成功！")
                config.update(
                    {
                        "uid": bs_info["uid"],
                        "access_key": bs_info["access_key"],
                        "last_login_succ": True,
                        "uname": bs_user_info["uname"],
                    }
                )
                config_manager.write_conf(config)
        else:
            logging.info(f"登陆B站账号 {config['account']} 中...")
            bs_info = await bsgamesdk.login(
                config["account"], config["password"], config_manager.cap
            )
            if not bs_info:
                logging.error("登录请求失败，返回结果为空")
                self.login_complete.emit(False)
                return
            if "access_key" not in bs_info:
                self.handle_login_failure(bs_info)
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
            logging.error(f"登录失败！{bh_info}")
            self.login_complete.emit(False)
            return
        logging.info("登录成功，账号：LoveElysia1314，开始获取OA服务器信息...")
        # 获取服务器版本号
        server_bh_ver = await mihoyosdk.getBHVer(BH_VER)
        # 检查版本是否匹配
        if server_bh_ver != BH_VER:
            logging.warning(f"版本不匹配 (本地: {BH_VER}, 服务器: {server_bh_ver})！")

        # 刷新 OA 版本信息，如果为空则更新远程文件
        version_manager.refresh_oa_info()
        if not version_manager.oa_versions:
            # 检查远程版本信息，确保 oa_versions 已更新
            update_result = config_manager.check_program_update()
            if "error" in update_result:
                logging.error(
                    f"获取远程版本信息失败，无法继续获取OA服务器: {update_result['error']}"
                )
                self.login_complete.emit(False)
                return
            # 重新刷新 OA 版本信息
            version_manager.refresh_oa_info()

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

    def handle_login_failure(self, bs_info):
        if not bs_info:
            logging.error("登录失败：未收到有效的响应数据")
            return

        # 如果使用了验证码但仍然登录失败，说明验证码正确但账号密码错误
        if config_manager.cap is not None and "access_key" not in bs_info:
            logging.info("验证码验证成功，但账号或密码错误！")
            # 清空验证码，避免无限循环
            config_manager.cap = None
            # 重新弹出登录框
            self.login()
            return

        if bs_info.get("ssl_error"):
            logging.error("网络连接异常，清空账号信息并弹出登录框")
            # 清空账号密码
            config = config_manager.config
            config.update(
                {
                    "account": "",
                    "password": "",
                    "last_login_succ": False,
                    "uid": "",
                    "access_key": "",
                    "uname": "",
                    "account_login": False,
                }
            )
            config_manager.write_conf(config)
            # 弹出登录框
            self.login()
            return

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
        elif "message" not in bs_info:
            logging.info(f"登陆失败！{bs_info}")

    def run(self):
        asyncio.run(self.login())


# ========== 解析线程 ==========
class ParseThread(QThread):
    update_log = Signal(str)
    exit_app = Signal()

    async def periodic_check(self):
        """定期执行检查任务"""
        await game_manager.auto_monitor(
            config_manager.get_effective_config(),
            image_processor,
            click_center_of_game_window,
            self.exit_app.emit if hasattr(self, "exit_app") else None,
        )

    def run(self):
        asyncio.run(self.periodic_check())


# ========== 登陆按钮点击回调 ==========
def login_accept():
    # 仅在手动登录时清除缓存，自动登录不受影响
    if hasattr(window, "is_manual_login") and window.is_manual_login:
        config = config_manager.config
        config["access_key"] = ""
        config["uid"] = ""
        config["uname"] = ""
        config["last_login_succ"] = False
        config_manager.write_conf(config)
        window.is_manual_login = False  # 重置标志
    # 创建并启动登录线程
    ui.backendLogin = LoginThread()
    ui.backendLogin.update_log.connect(lambda s: logging.info(s))
    ui.backendLogin.login_complete.connect(window.handle_login_complete)
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

    @handle_exceptions("日志输出失败", None)
    def emit(self, record):
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
        self.update_check_thread.update_status.connect(self.on_update_status_changed)
        # 初始化更新下载线程
        self.update_download_thread = None

    def reset_login_button(self):
        """重置登录按钮状态"""
        ui.loginBiliBtn.setText("点击登陆")
        ui.loginBiliBtn.setDisabled(False)
        ui.loginBiliBtn.setDown(False)

    def handle_login_complete(self, success):
        # 登录完成后，解析线程将在 start_parse_thread_after_login 中启动,这里只负责更新UI状态
        if success:
            status = "账号已登陆"
            ui.loginBiliBtn.setText(status)
        else:
            status = "点击登陆"
            ui.loginBiliBtn.setText(status)
        ui.loginBiliBtn.setDisabled(False)
        ui.loginBiliBtn.setDown(False)  # 确保按钮不会保持按下状态
        # print(f"[INFO] 登录UI状态已更新为: {status}")

    def login(self):
        config = config_manager.config
        logging.info("开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)
        dialog = mainWindow.LoginDialog(self)
        dialog.account.textChanged.connect(self.deal_config_update("account"))
        dialog.password.textChanged.connect(self.deal_config_update("password"))
        dialog.show()
        dialog.accepted.connect(login_accept)
        # 标记为手动登录
        self.is_manual_login = True

    def deal_config_update(self, key):
        def update(value):
            config = config_manager.config
            config[key] = value
            # 当账号或密码改变时，强制标记为未登录，防止使用缓存（重要：确保用户能登录其他账号）
            if key in ["account", "password"]:
                config["last_login_succ"] = False
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

    def launch_game_unified(self):
        """
        统一的游戏启动方法，包含路径检查和消息提示
        """
        game_manager.launch_game(show_messages=True)

    def launchGame(self):
        self.launch_game_unified()

    def open_template_folder(self):
        """打开图片模板文件夹"""
        import os

        template_dir = os.path.join(os.getcwd(), "resources", "pictures_to_match")
        if os.path.exists(template_dir):
            os.startfile(template_dir)
            logging.info("已打开模板文件夹")
        else:
            logging.warning("模板文件夹不存在")

    def oneClickLogin(self, skip_launch=False):
        """
        一键登录模式，支持跳过游戏启动（防止重复打开游戏）
        :param skip_launch: 如果为 True，则不执行 launchGame
        """
        if game_manager.one_click_login(skip_launch=skip_launch):
            self.temp_mode = True
            # 记录原始设置用于UI复原（不持久化）
            base_config = config_manager.config
            self.prev_settings = {
                k: base_config.get(k, False)
                for k in [
                    "clip_check",
                    "auto_clip",
                    "auto_close",
                    "auto_click",
                    "debug_print",
                ]
            }
            # 启用临时覆盖（不写入文件）
            config_manager.begin_temp_overrides(
                {
                    "clip_check": True,
                    "auto_clip": True,
                    "auto_close": True,
                    "auto_click": True,
                    "debug_print": True,
                }
            )
            for checkbox, prefix in [
                (ui.clipCheck, "当前"),
                (ui.autoClip, "当前"),
                (ui.autoClose, "当前"),
                (ui.autoClick, "当前"),
            ]:
                checkbox.setChecked(True)
                self.update_status_text(checkbox, prefix)
            logging.info("一键进入舰桥模式已启用")

    def restoreOriginalSettings(self):
        if not self.temp_mode:
            return
        # 清除临时覆盖，恢复真实配置视图
        config_manager.clear_temp_overrides()
        # 将 UI 勾选状态恢复为原始设置（不改变磁盘文件）
        for checkbox, feature, prefix in [
            (ui.clipCheck, "clip_check", "当前"),
            (ui.autoClip, "auto_clip", "当前"),
            (ui.autoClose, "auto_close", "当前"),
            (ui.autoClick, "auto_click", "当前"),
        ]:
            checkbox.setChecked(self.prev_settings.get(feature, False))
            self.update_status_text(checkbox, prefix)
        logging.info("一键进入舰桥模式已结束，恢复原始设置")

    def on_update_status_changed(self, status):
        """处理更新状态变化的槽函数"""
        ui.updateStatusLabel.setText(status)
        logging.info(f"更新状态: {status}")

    def on_update_download_finished(self):
        """处理更新下载线程完成"""
        logging.info("更新下载线程已完成")
        # 清理线程引用
        if self.update_download_thread:
            self.update_download_thread = None

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
        self.update_check_thread.update_status.connect(self.on_update_status_changed)

    def check_and_display_updates(self):
        """启动后台线程检查更新并更新UI标签（用于程序初始化和手动检查）"""
        if self.update_check_thread.isRunning():
            return  # 如果线程正在运行，不重复启动
        # 不再在这里设置初始状态，由线程内部的状态信号处理
        self.update_check_thread.start()

    def perform_update(self):
        """直接调用更新逻辑：自动择优源并在默认浏览器打开下载链接"""
        # 检查是否已有下载线程在运行
        if self.update_download_thread and self.update_download_thread.isRunning():
            logging.info("更新下载线程正在运行中，请等待完成")
            self.on_update_status_changed("请等待当前下载操作完成...")
            return

        # 创建新的下载线程
        self.update_download_thread = UpdateDownloadThread()
        self.update_download_thread.update_status.connect(self.on_update_status_changed)
        self.update_download_thread.finished.connect(self.on_update_download_finished)
        self.update_download_thread.start()

    def check_for_updates(self):
        """检查更新（用户手动触发）——不再弹窗，按钮状态将由 check_and_display_updates 决定"""
        self.check_and_display_updates()


# ========== 应用启动函数 ==========
def main():
    """运行应用程序的核心逻辑"""
    # 设置全局变量
    global ui, window, app
    global auto_login_triggered

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = config_manager.config
    # 根据配置切换日志级别（启用 DEBUG 时显示更多线程日志）
    root_logger = logging.getLogger()
    root_logger.setLevel(
        logging.DEBUG if config.get("debug_print", False) else logging.INFO
    )

    app = QApplication(sys.argv)
    window = SelfMainWindow()
    ui = mainWindow.Ui_MainWindow()  # 实例化 UI
    ui.setupUi(window)  # 设置 UI 到窗口
    # 添加 GUI 日志处理器
    handler = GuiHandler(ui.logText)
    logging.getLogger().addHandler(handler)

    # 只允许 auto-login 参数自动触发一次登录流程
    auto_login_triggered = False
    if "--auto-login" in sys.argv and not auto_login_triggered:
        auto_login_triggered = True
        QTimer.singleShot(100, lambda: window.oneClickLogin(skip_launch=False))
        logging.info("检测到自动登陆参数，将启动一键进入舰桥模式")

    # 应用配置到UI控件 (移到 setupUi 之后)
    for checkbox, feature, prefix in [
        (ui.clipCheck, "clip_check", "当前"),
        (ui.autoClose, "auto_close", "当前"),
        (ui.autoClip, "auto_clip", "当前"),
        (ui.autoClick, "auto_click", "当前"),
        (ui.debugPrint, "debug_print", "当前"),
    ]:
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    ui.configGamePathBtn.setText(
        "路径已配置" if config.get("game_path") else "点击配置"
    )

    window.show()

    # Flask 应用设置（回退到v1.3.2：启动时直接启动Flask线程）
    fapp = Flask(__name__, template_folder=TEMPLATE_WEB_DIR)
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    # Flask 路由定义（重要：删除会导致验证码网页 Not Found）
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
        logging.debug(f"验证码数据接收: {input_data}")
        config_manager.cap = input_data
        # 延迟调用login_accept，避免与当前请求冲突
        import threading

        threading.Timer(1.0, login_accept).start()
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
        (ui.clipCheck, "clip_check", "当前"),
        (ui.autoClose, "auto_close", "当前"),
        (ui.autoClip, "auto_clip", "当前"),
        (ui.autoClick, "auto_click", "当前"),
        (ui.debugPrint, "debug_print", "当前"),
    ]:
        # 使用 config.get 并提供默认值 False，确保不会因键缺失出错
        checkbox.setChecked(config.get(feature, False))
        window.update_status_text(checkbox, prefix)

    # 更新游戏路径按钮文本
    ui.configGamePathBtn.setText(
        "路径已配置" if config.get("game_path") else "点击配置"
    )

    # 初始化登录按钮状态
    if config.get("account_login", False):
        ui.loginBiliBtn.setText("账号已登陆")
    else:
        ui.loginBiliBtn.setText("点击登陆")

    # 显示窗口
    window.show()

    # 程序启动时自动检查更新（不弹窗）
    window.check_and_display_updates()

    # 处理命令行参数
    if "--auto-login" in sys.argv:
        QTimer.singleShot(100, window.oneClickLogin)
        logging.info("检测到自动登陆参数，将启动一键登陆模式")

    # 注册退出时恢复设置的函数
    atexit.register(window.restoreOriginalSettings)

    sys.exit(app.exec())


# ========== Flask 启动 ==========
if __name__ == "__main__":
    main()
