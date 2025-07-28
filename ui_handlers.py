from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from PySide6.QtGui import QIcon
from mainWindow import ui , LoginDialog
from config_utils import config_manager
from network_utils import network_manager
from version_utils import version_manager
from callbacks import login_accept
import subprocess

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

    def login(self):
        config = config_manager.config
        if config.get('account_login', False):
            print("[INFO] 账号已登陆")
            ui.loginBiliBtn.setText("账号已登陆")
            return
        print("[INFO] 开始登陆账号")
        ui.loginBiliBtn.setText("登陆中")
        ui.loginBiliBtn.setDisabled(True)
        dialog = LoginDialog(self)
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

    def check_for_updates(self):
        """检查更新"""
        ui.updateStatusLabel.setText("正在检查更新...")
        
        check_result = network_manager.check_program_update()

        latest_version = check_result.get('version')
        download_url = check_result.get('download_url')

        if check_result.get('has_update'):
            ui.updateStatusLabel.setText(f"发现新版本: {latest_version}")
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '更新', f'发现新版本 {latest_version}，是否前往下载？',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                 network_manager.download_update(download_url)

        elif check_result.get('error'):
            print(f"[WARNING] 检查更新失败，请访问GitHub项目主页。")
        else:
             ui.updateStatusLabel.setText(f"当前版本：{version_manager.get_current_version()}")