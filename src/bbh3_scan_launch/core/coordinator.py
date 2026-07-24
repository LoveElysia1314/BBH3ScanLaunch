# -*- coding: utf-8 -*-
"""应用生命周期协调器。"""

import logging

from PySide6.QtCore import QObject, Signal
from .workers import LoginThread, ParseThread


class AppCoordinator(QObject):
    """协调认证与监控流程，并将外部线程事件切回 Qt 主线程。"""

    captcha_completed = Signal()

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.window = None
        self.app = None
        self.captcha_completed.connect(self.start_login)

    def attach(self, window, app):
        self.window = window
        self.app = app

    def _thread_owner(self):
        owner = self.window
        if owner is None:
            raise RuntimeError("窗口未初始化")
        return owner

    @property
    def config_manager(self):
        return self.context.config_manager

    @property
    def game_manager(self):
        return self.context.game_manager

    @property
    def version_manager(self):
        return self.context.version_manager

    def start_login(self):
        if self.window is None:
            logging.warning("窗口未初始化，无法启动登录线程")
            return
        owner = self._thread_owner()

        old_login_thread = getattr(owner, "backendLogin", None)
        if old_login_thread is not None and old_login_thread.isRunning():
            logging.info("登录线程已在运行，忽略重复请求")
            return

        if getattr(self.window, "is_manual_login", False):
            config = self.config_manager.config
            config["access_key"] = ""
            config["uid"] = ""
            config["uname"] = ""
            config["last_login_succ"] = False
            self.config_manager.write_conf(config)
            self.window.is_manual_login = False

        owner.backendLogin = LoginThread(self.context.auth_service)
        owner.backendLogin.update_log.connect(lambda s: logging.info(s))
        owner.backendLogin.login_complete.connect(self.window.handle_login_complete)
        owner.backendLogin.login_complete.connect(self.start_parse_after_login)
        owner.backendLogin.start()

    def start_parse_after_login(self, success):
        if not success:
            logging.warning("登录失败，解析线程未启动")
            return

        if self.window is None:
            logging.warning("窗口未初始化，无法启动解析线程")
            return
        owner = self._thread_owner()

        logging.info("登录流程完成，准备启动解析线程...")
        if hasattr(owner, "backendClipCheck") and owner.backendClipCheck.isRunning():
            logging.warning("解析线程已在运行中？")
            return

        owner.backendClipCheck = ParseThread(
            self.game_manager,
            self.config_manager,
            self.context.image_processor,
        )
        owner.backendClipCheck.update_log.connect(lambda s: logging.info(s))
        owner.backendClipCheck.exit_app.connect(self._exit_app)
        owner.backendClipCheck.start()
        logging.info("登录完成，解析线程已启动")

    def _exit_app(self):
        if self.window:
            self.window.restore_original_settings()
        if self.app:
            self.app.quit()

    def apply_captcha(self, input_data):
        self.config_manager.cap = input_data
