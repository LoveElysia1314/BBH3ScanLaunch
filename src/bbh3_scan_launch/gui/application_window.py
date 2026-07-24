# -*- coding: utf-8 -*-
"""应用主窗口及其交互流程。"""

import logging
import os
from typing import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFileDialog, QMainWindow

from ..core.workers import UpdateCheckThread, UpdateDownloadThread
from . import main_window as main_window_ui


class ApplicationWindow(QMainWindow):
    """承载 Qt 控件交互，并把业务操作委托给注入的服务。"""

    def __init__(self, context: object, ui, on_login_submit: Callable[[], None]):
        super().__init__()
        self._context = context
        self._window = self
        self.ui = ui
        self._on_login_submit = on_login_submit
        self.setWindowIcon(QIcon(r"./BHimage.ico"))

        self._prev_settings = {}
        self._temp_mode = False
        self._download_source_list_widget = None
        self._download_priority_bound = False

        self._update_check_thread = self._build_update_check_thread()
        self._update_download_thread = None
        self._is_manual_login = False

    def reset_login_button(self) -> None:
        """重置登录按钮状态"""
        self._window.ui.loginBiliBtn.setText("点击登陆")
        self._window.ui.loginBiliBtn.setDisabled(False)
        self._window.ui.loginBiliBtn.setDown(False)

    def handle_login_complete(self, success: bool) -> None:
        status = "账号已登陆" if success else "点击登陆"
        self._window.ui.loginBiliBtn.setText(status)
        self._window.ui.loginBiliBtn.setDisabled(False)
        self._window.ui.loginBiliBtn.setDown(False)

    def login(self) -> None:
        logging.info("开始登陆账号")
        self.ui.loginBiliBtn.setText("登陆中")
        self.ui.loginBiliBtn.setDisabled(True)
        dialog = main_window_ui.LoginDialog(
            self,
            config_manager=self._context.config_manager,
        )
        dialog.account.textChanged.connect(self.deal_config_update("account"))
        dialog.password.textChanged.connect(self.deal_config_update("password"))
        dialog.accepted.connect(self._on_login_submit)
        dialog.show()
        self.is_manual_login = True

    @property
    def is_manual_login(self):
        return self._is_manual_login

    @is_manual_login.setter
    def is_manual_login(self, value):
        self._is_manual_login = bool(value)

    def _build_update_check_thread(self):
        thread = UpdateCheckThread(self._context.update_service)
        thread.update_result.connect(self.on_update_check_finished)
        thread.update_status.connect(self.on_update_status_changed)
        thread.update_failed.connect(self.on_update_check_failed)
        thread.finished.connect(self._on_update_check_thread_finished)
        return thread

    def _on_update_check_thread_finished(self) -> None:
        self._update_check_thread = self._build_update_check_thread()

    def bind_download_priority_widget(self, source_list_widget=None) -> None:
        """绑定下载源优先级列表控件并注册持久化回调。"""
        self._download_source_list_widget = (
            source_list_widget or self.ui.sourceListWidget
        )

        download_priority = self._context.config_manager.get_config(
            "download_priority", ["gitee", "github"]
        )
        self._download_source_list_widget.clear()
        self._download_source_list_widget.addItems(download_priority)

        if not self._download_priority_bound:
            self._download_source_list_widget.model().rowsMoved.connect(
                self._on_download_priority_moved
            )
            self._download_priority_bound = True

    def _on_download_priority_moved(self, *_args) -> None:
        if self._download_source_list_widget is None:
            return
        new_priority = [
            self._download_source_list_widget.item(i).text()
            for i in range(self._download_source_list_widget.count())
        ]
        self._context.config_manager.set_config("download_priority", new_priority)

    @staticmethod
    def update_status_text(checkbox, prefix: str) -> None:
        checkbox.setText(f"{prefix}:{'启用' if checkbox.isChecked() else '关闭'}")

    @staticmethod
    def _deal_config_update_callback(config_manager, key: str) -> Callable[[str], None]:
        def update(value):
            config = config_manager.config
            config[key] = value
            if key in ["account", "password"]:
                config["last_login_succ"] = False
            config_manager.write_conf(config)

        return update

    def deal_config_update(self, key: str):
        return self._deal_config_update_callback(self._context.config_manager, key)

    def bind_update_button(self, text: str, handler) -> None:
        try:
            self._window.ui.checkUpdateBtn.clicked.disconnect()
        except Exception:
            pass
        self._window.ui.checkUpdateBtn.setText(text)
        self._window.ui.checkUpdateBtn.clicked.connect(handler)

    def toggle_feature(self, feature: str, checkbox, prefix: str) -> None:
        config = self._context.config_manager.config
        config[feature] = checkbox.isChecked()
        self._context.config_manager.write_conf(config)
        self.update_status_text(checkbox, prefix)

    def config_game_path(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self._window, "选择崩坏3执行文件", "", "Executable Files (*.exe)"
        )
        if file_path:
            config = self._context.config_manager.config
            config["game_path"] = file_path
            self._context.config_manager.write_conf(config)
            self._window.ui.configGamePathBtn.setText("路径已配置")

    def launch_game(self) -> None:
        self._context.game_manager.launch_game(show_messages=True)

    def open_template_folder(self):
        """打开图片模板文件夹"""
        template_dir = os.path.join(os.getcwd(), "resources", "pictures_to_match")
        if os.path.exists(template_dir):
            os.startfile(template_dir)
            logging.info("已打开模板文件夹")
        else:
            logging.warning("模板文件夹不存在")

    def one_click_login(self, skip_launch: bool = False) -> None:
        """
        一键登录模式，支持跳过游戏启动（防止重复打开游戏）
        :param skip_launch: 如果为 True，则不执行 launch_game
        """
        if self._context.game_manager.one_click_login(skip_launch=skip_launch):
            self._temp_mode = True
            base_config = self._context.config_manager.config
            self._prev_settings = {
                k: base_config.get(k, False)
                for k in [
                    "clip_check",
                    "auto_clip",
                    "auto_close",
                    "auto_click",
                    "debug_print",
                ]
            }
            self._context.config_manager.begin_temp_overrides(
                {
                    "clip_check": True,
                    "auto_clip": True,
                    "auto_close": True,
                    "auto_click": True,
                    "debug_print": True,
                }
            )
            for checkbox in (
                self._window.ui.clipCheck,
                self._window.ui.autoClip,
                self._window.ui.autoClose,
                self._window.ui.autoClick,
            ):
                checkbox.setChecked(True)
                self.update_status_text(checkbox, "当前")
            logging.info("一键进入舰桥模式已启用")

    def restore_original_settings(self) -> None:
        if not self._temp_mode:
            return
        self._context.config_manager.clear_temp_overrides()
        for checkbox, feature in (
            (self._window.ui.clipCheck, "clip_check"),
            (self._window.ui.autoClip, "auto_clip"),
            (self._window.ui.autoClose, "auto_close"),
            (self._window.ui.autoClick, "auto_click"),
        ):
            checkbox.setChecked(self._prev_settings.get(feature, False))
            self.update_status_text(checkbox, "当前")
        logging.info("一键进入舰桥模式已结束，恢复原始设置")
        self._temp_mode = False

    def apply_initial_state(self, config: dict[str, object]) -> None:
        for checkbox, feature in (
            (self._window.ui.clipCheck, "clip_check"),
            (self._window.ui.autoClose, "auto_close"),
            (self._window.ui.autoClip, "auto_clip"),
            (self._window.ui.autoClick, "auto_click"),
            (self._window.ui.debugPrint, "debug_print"),
        ):
            checkbox.setChecked(config.get(feature, False))
            self.update_status_text(checkbox, "当前")

        self._window.ui.configGamePathBtn.setText(
            "路径已配置" if config.get("game_path") else "点击配置"
        )
        self._window.ui.loginBiliBtn.setText(
            "账号已登陆" if config.get("account_login") else "点击登陆"
        )

    def on_update_status_changed(self, status: str) -> None:
        """处理更新状态变化的槽函数"""
        self._window.ui.updateStatusLabel.setText(status)
        logging.info(f"更新状态: {status}")

    def on_update_download_finished(self) -> None:
        """处理更新下载线程完成"""
        logging.info("更新下载线程已完成")
        if self._update_download_thread:
            self._update_download_thread = None

    def on_update_check_finished(self, has_update: bool, version_info) -> None:
        """处理更新检查结果的槽函数"""
        if has_update:
            self._window.ui.updateStatusLabel.setText(f"更新可用: {version_info}")
            self.bind_update_button("更新", self.perform_update)
        else:
            self._window.ui.updateStatusLabel.setText(f"暂无更新：{version_info}")
            self.bind_update_button("检查更新", self.check_for_updates)

    def on_update_check_failed(self, message: str) -> None:
        self._window.ui.updateStatusLabel.setText(f"更新检查失败：{message}")
        self.bind_update_button("重试", self.check_for_updates)

    def check_and_display_updates(self) -> None:
        """启动后台线程检查更新并更新UI标签（用于程序初始化和手动检查）"""
        if self._update_check_thread.isRunning():
            return
        self._update_check_thread.start()

    def perform_update(self) -> None:
        """调用更新逻辑：自动择优源并在默认浏览器打开下载链接"""
        if (
            self._update_download_thread is not None
            and self._update_download_thread.isRunning()
        ):
            logging.info("更新下载线程正在运行中，请等待完成")
            self.on_update_status_changed("请等待当前下载操作完成...")
            return

        self._update_download_thread = UpdateDownloadThread(
            self._context.update_service
        )
        self._update_download_thread.update_status.connect(
            self.on_update_status_changed
        )
        self._update_download_thread.finished.connect(self.on_update_download_finished)
        self._update_download_thread.start()

    def check_for_updates(self) -> None:
        self.check_and_display_updates()
