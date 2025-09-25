# -*- coding: utf-8 -*-
import logging
from PySide6.QtCore import Qt, QMetaObject, QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QWidget,
    QTabWidget,
    QMenuBar,
    QGroupBox,
    QGridLayout,
    QPushButton,
    QCheckBox,
)
import markdown

# 使用依赖注入容器获取管理器实例
from ..dependency_container import get_version_manager, get_config_manager

version_manager = get_version_manager()
config_manager = get_config_manager()


class LoginDialog(QDialog):
    """
    账号登录对话框
    提供B站账号和密码输入表单，用于用户认证
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登陆账号")

        # 主布局
        main_layout = QVBoxLayout(self)

        # 创建表单控件
        self.create_form_controls(main_layout)

        # 按钮框
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        self.adjustSize()

        # 预填账号密码
        self.prefill_credentials()

    def prefill_credentials(self):
        """预填账号密码"""
        try:
            from ..utils.config_utils import config_manager

            config = config_manager.config
            if config.get("account"):
                self.account.setText(config["account"])
            if config.get("password"):
                self.password.setText(config["password"])
        except Exception as e:
            logging.warning(f"预填账号密码失败: {e}")

    def reject(self):
        """重写reject方法，确保关闭对话框时重置按钮状态"""
        # 重置登录按钮状态
        if hasattr(self.parent(), "reset_login_button"):
            self.parent().reset_login_button()
        super().reject()

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 重置登录按钮状态
        if hasattr(self.parent(), "reset_login_button"):
            self.parent().reset_login_button()
        super().closeEvent(event)

    def create_form_controls(self, layout):
        """创建账号密码输入表单控件"""
        fields = [
            ("账号:", "account", "请输入账号"),
            ("密码:", "password", "请输入密码"),
        ]

        for label_text, attr_name, placeholder in fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            field = QLineEdit()
            field.setPlaceholderText(placeholder)

            if attr_name == "password":
                field.setEchoMode(QLineEdit.EchoMode.Password)

            setattr(self, attr_name, field)

            row.addWidget(label)
            row.addWidget(field)
            layout.addLayout(row)


class Ui_MainWindow:
    """
    主窗口UI布局
    包含日志显示区、功能说明区和控制面板，用于崩坏3扫码登录器
    """

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setAttribute(Qt.WidgetAttribute.WA_Resized, True)

        # 主控件和布局
        self.centralwidget = QWidget(MainWindow)
        self.mainLayout = QHBoxLayout(self.centralwidget)

        # 创建左侧区域
        self.create_left_area()

        # 创建右侧区域
        self.rightContainer = QWidget()
        right_layout = QVBoxLayout(self.rightContainer)

        # 添加功能组
        self.create_account_group(right_layout)
        self.create_features_group(right_layout)
        self.create_auto_login_group(right_layout)

        # 添加更新组（原关于组，移动到自动化组下方）
        self.create_update_group(right_layout)

        # 添加到主布局
        self.mainLayout.addWidget(self.rightContainer)
        # 设置左右栏宽度比例为5:3
        self.mainLayout.setStretch(0, 5)  # 左侧
        self.mainLayout.setStretch(1, 3)  # 右侧
        MainWindow.setCentralWidget(self.centralwidget)

        # 菜单栏
        self.menubar = QMenuBar(MainWindow)
        MainWindow.setMenuBar(self.menubar)

        self.retranslateUi(MainWindow)
        self.connectSignals(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

    def create_left_area(self):
        """创建包含信息展示的左侧面板（使用分页控件）"""
        self.leftContainer = QWidget()
        left_layout = QVBoxLayout(self.leftContainer)

        # 信息展示区域（使用分页控件）
        self.infoTabWidget = QTabWidget()
        self.infoTabWidget.setTabPosition(QTabWidget.TabPosition.North)

        # 第一页：运行日志
        self.logTab = QWidget()
        logLayout = QVBoxLayout(self.logTab)
        self.logText = QTextBrowser()
        self.logText.setOpenExternalLinks(True)
        logLayout.addWidget(self.logText)
        self.infoTabWidget.addTab(self.logTab, "运行日志")

        # 第二页：程序说明
        self.helpTab = QWidget()
        helpLayout = QVBoxLayout(self.helpTab)
        self.helpText = QTextBrowser()
        self.helpText.setOpenExternalLinks(True)
        # 将Markdown转换为HTML并设置
        help_markdown = self.get_help_text()
        help_html = markdown.markdown(help_markdown, extensions=["extra", "codehilite"])
        self.helpText.setHtml(help_html)
        helpLayout.addWidget(self.helpText)
        self.infoTabWidget.addTab(self.helpTab, "程序说明")

        # 第三页：更新日志
        self.changelogTab = QWidget()
        changelogLayout = QVBoxLayout(self.changelogTab)
        self.changelogText = QTextBrowser()
        self.changelogText.setOpenExternalLinks(True)
        # 将Markdown转换为HTML并设置
        changelog_markdown = version_manager.read_changelog()
        changelog_html = markdown.markdown(
            changelog_markdown, extensions=["extra", "codehilite"]
        )
        self.changelogText.setHtml(changelog_html)
        changelogLayout.addWidget(self.changelogText)
        self.infoTabWidget.addTab(self.changelogTab, "更新日志")

        left_layout.addWidget(self.infoTabWidget)

        # 添加到主布局
        self.mainLayout.addWidget(self.leftContainer)

    def create_account_group(self, layout):
        """创建B站账号和游戏路径设置区域"""
        self.accountGroup = QGroupBox("账号设置")
        gridLayout = QGridLayout(self.accountGroup)

        # 按钮配置
        buttons = [
            ("登陆B站账户:", "loginBiliBtn", "点击登陆"),
            ("配置游戏路径:", "configGamePathBtn", "点击配置"),
        ]

        for row, (label_text, attr_name, btn_text) in enumerate(buttons):
            label = QLabel(label_text)
            btn = QPushButton(btn_text)
            setattr(self, attr_name, btn)

            gridLayout.addWidget(label, row, 0)
            gridLayout.addWidget(btn, row, 1)

        layout.addWidget(self.accountGroup)

    def create_features_group(self, layout):
        """创建二维码解析和自动操作功能开关区域"""
        self.featureGroup = QGroupBox("功能设置")
        gridLayout = QGridLayout(self.featureGroup)

        # 添加打开模板文件夹按钮（放在最上面）
        label = QLabel("管理模板:")
        self.openTemplateBtn = QPushButton("打开文件夹")
        gridLayout.addWidget(label, 0, 0)
        gridLayout.addWidget(self.openTemplateBtn, 0, 1)

        # 复选框配置
        checkboxes = [
            ("解析二维码:", "clipCheck"),
            ("自动截屏:", "autoClip"),
            ("自动退出:", "autoClose"),
            ("自动点击:", "autoClick"),
            ("DEBUG:", "debugPrint"),
        ]

        for row, (label_text, attr_name) in enumerate(
            checkboxes, start=1
        ):  # 从第1行开始
            label = QLabel(label_text)
            checkbox = QCheckBox()
            setattr(self, attr_name, checkbox)

            gridLayout.addWidget(label, row, 0)
            gridLayout.addWidget(checkbox, row, 1)

        layout.addWidget(self.featureGroup)

    def create_auto_login_group(self, layout):
        """创建游戏启动和一键登录按钮区域（并排显示）"""
        self.autoLoginGroup = QGroupBox("自动化")
        autoLoginLayout = QHBoxLayout(self.autoLoginGroup)
        # 按钮配置
        buttons = [
            ("打开崩坏3", "launchGameBtn"),
            ("一键进入舰桥", "oneClickLoginBtn"),
        ]
        for btn_text, attr_name in buttons:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(30)
            setattr(self, attr_name, btn)
            autoLoginLayout.addWidget(btn)
        layout.addWidget(self.autoLoginGroup)

    def create_update_group(self, layout):
        """创建包含检查更新和下载源优先级调整控件的'更新'组"""
        self.updateGroup = QGroupBox("更新")
        gridLayout = QGridLayout(self.updateGroup)

        # 更新状态标签
        self.updateStatusLabel = QLabel(
            f"当前版本：{version_manager.get_version_info('current')}"
        )
        self.updateStatusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gridLayout.addWidget(self.updateStatusLabel, 0, 0, 1, 1)

        # 检查更新按钮
        self.checkUpdateBtn = QPushButton("检查更新")
        gridLayout.addWidget(self.checkUpdateBtn, 1, 0, 1, 1)

        # 下载源优先级调整控件（标签在上，控件在下）
        from PySide6.QtWidgets import QListWidget

        label = QLabel("下载源优先级调整（拖拽排序）：")
        gridLayout.addWidget(label, 2, 0, 1, 1)
        self.sourceListWidget = QListWidget()
        self.sourceListWidget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.sourceListWidget.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        # 读取config.json中的download_priority
        try:
            priority = config_manager.get_config(
                "download_priority", ["gitee", "github"]
            )
        except Exception:
            priority = ["gitee", "github"]
        self.sourceListWidget.addItems(priority)
        gridLayout.addWidget(self.sourceListWidget, 3, 0, 1, 1)

        # 绑定顺序变化事件，自动写入config.json
        def update_priority():
            new_priority = [
                self.sourceListWidget.item(i).text()
                for i in range(self.sourceListWidget.count())
            ]
            try:
                config_manager.set_config("download_priority", new_priority)
            except Exception:
                pass

        self.sourceListWidget.model().rowsMoved.connect(update_priority)

        layout.addWidget(self.updateGroup)

    def get_help_text(self):
        """返回程序使用说明的Markdown格式文本"""
        return (
            "### 登录B站账号\n\n"
            "- 点击“登陆B站账户”\n"
            "- 输入账号和密码\n"
            "- 信息会自动保存，后续可直接使用\n\n"
            "### 配置游戏路径\n\n"
            "- 点击“配置游戏路径”\n"
            "- 选择 BH3.exe\n"
            "- 参考：`C:\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe`\n\n"
            "### 常用操作\n\n"
            "- 解析二维码：自动读取剪贴板中的登录码并扫码\n"
            "- 自动截屏：自动截取游戏画面（支持前后台）\n"
            "- 自动退出：扫码完成后自动关闭程序\n"
            "- 自动点击：自动切换登录方式并进入游戏（需管理员权限）\n"
            "- DEBUG：显示详细日志，便于排查问题\n"
            "- 管理模板：打开模板图片文件夹，方便添加或管理分辨率模板\n"
            "- 打开崩坏3：直接启动游戏\n"
            "- 一键进入舰桥：启动并自动完成登录（需管理员权限）\n\n"
            "### 更新与下载源\n\n"
            "- 检查更新：点击“检查更新”，启动时也会自动检查\n"
            "- 下载源优先级：在“下载源优先级调整”中拖拽排序，自动保存\n"
            "- 建议：国内优先 Gitee，海外优先 GitHub\n\n"
            "### 权限与系统要求\n\n"
            "- 管理员权限：一键进入舰桥、自动点击需要\n"
            "- 以管理员运行：右键程序 → 以管理员身份运行\n"
            "- 系统：Windows 10/11；需网络；建议 1920x1080 分辨率及以上\n\n"
            "### 故障排除\n\n"
            "- 登录失败：检查网络/账号密码，重试\n"
            "- 找不到游戏窗口：确认已启动、未最小化，必要时重启游戏\n"
            "- 权限不足：以管理员身份运行\n"
            "- 更新失败：检查网络，调整下载源优先级，稍后重试\n"
            "- 配置异常：删除 `config` 文件夹并重启，系统会重建\n\n"
            "### 项目与支持\n\n"
            "- 当前版本：" + version_manager.get_version_info("current") + "\n"
            "- 项目主页：https://github.com/LoveElysia1314/BBH3ScanLaunch\n"
            "- 问题反馈：请在项目主页提交 Issue\n\n"
            "---\n\n"
            "Powered by LoveElysia1314  ·  Thanks to Hao_cen\n"
        )

    def retranslateUi(self, MainWindow):
        """设置窗口标题和初始化文本"""
        _translate = QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "B服崩坏3扫码登陆器"))
        self.logText.setPlainText("系统初始化完成，等待操作...")

    def connectSignals(self, MainWindow):
        """连接所有按钮和复选框的信号与槽函数"""
        self.loginBiliBtn.clicked.connect(MainWindow.login)
        self.clipCheck.clicked.connect(
            lambda: MainWindow.toggle_feature("clip_check", self.clipCheck, "当前")
        )
        self.autoClip.clicked.connect(
            lambda: MainWindow.toggle_feature("auto_clip", self.autoClip, "当前")
        )
        self.autoClose.clicked.connect(
            lambda: MainWindow.toggle_feature("auto_close", self.autoClose, "当前")
        )
        self.autoClick.clicked.connect(
            lambda: MainWindow.toggle_feature("auto_click", self.autoClick, "当前")
        )
        self.debugPrint.clicked.connect(
            lambda: MainWindow.toggle_feature("debug_print", self.debugPrint, "当前")
        )
        self.configGamePathBtn.clicked.connect(MainWindow.configGamePath)
        self.launchGameBtn.clicked.connect(MainWindow.launchGame)
        self.oneClickLoginBtn.clicked.connect(MainWindow.oneClickLogin)

        # 连接打开模板文件夹按钮
        self.openTemplateBtn.clicked.connect(MainWindow.open_template_folder)

        # 连接更新组按钮信号
        self.checkUpdateBtn.clicked.connect(MainWindow.check_for_updates)


ui = Ui_MainWindow()  # 实例化 UI
