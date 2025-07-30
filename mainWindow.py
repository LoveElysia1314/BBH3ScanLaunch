# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, QMetaObject, QCoreApplication
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit,
                               QVBoxLayout, QHBoxLayout, QTextBrowser, QWidget, QTabWidget,
                               QMenuBar, QGroupBox, QGridLayout, QPushButton, QCheckBox,)

from version_utils import version_manager

class LoginDialog(QDialog):
    """
    账号登录对话框
    提供B站账号和密码输入表单，用于用户认证
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('登陆账号')
        
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

    def create_form_controls(self, layout):
        """创建账号密码输入表单控件"""
        fields = [
            ("账号:", "account", "请输入账号"),
            ("密码:", "password", "请输入密码")
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
        
        # 添加关于组（移动到自动化组下方）
        self.create_about_group(right_layout)
        
        # 添加到主布局
        self.mainLayout.addWidget(self.rightContainer)
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
        self.helpText.setHtml(self.get_help_text())
        helpLayout.addWidget(self.helpText)
        self.infoTabWidget.addTab(self.helpTab, "程序说明")
        
        # 第三页：更新日志
        self.changelogTab = QWidget()
        changelogLayout = QVBoxLayout(self.changelogTab)
        self.changelogText = QTextBrowser()
        self.changelogText.setOpenExternalLinks(True)
        self.changelogText.setPlainText(version_manager.read_changelog())
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
            ("配置游戏路径:", "configGamePathBtn", "点击配置")
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
        
        # 复选框配置
        checkboxes = [
            ("解析二维码:", "clipCheck"),
            ("自动截屏:", "autoClip"),
            ("自动退出:", "autoClose"),
            ("自动点击:", "autoClick"),
            ("DEBUG:", "debugPrint")
        ]
        
        for row, (label_text, attr_name) in enumerate(checkboxes):
            label = QLabel(label_text)
            checkbox = QCheckBox()
            setattr(self, attr_name, checkbox)
            
            gridLayout.addWidget(label, row, 0)
            gridLayout.addWidget(checkbox, row, 1)
            
        layout.addWidget(self.featureGroup)

    def create_auto_login_group(self, layout):
        """创建游戏启动和一键登录按钮区域"""
        self.autoLoginGroup = QGroupBox("自动化")
        autoLoginLayout = QVBoxLayout(self.autoLoginGroup)
        # 按钮配置
        buttons = [
            ("打开崩坏3", "launchGameBtn"),
            ("一键登陆崩坏3", "oneClickLoginBtn")
        ]
        for btn_text, attr_name in buttons:
            btn = QPushButton(btn_text)
            btn.setMinimumHeight(30)
            setattr(self, attr_name, btn)
            autoLoginLayout.addWidget(btn)
        layout.addWidget(self.autoLoginGroup)

    def create_about_group(self, layout):
        """创建包含检查更新功能的'关于'组（简化版）"""
        self.aboutGroup = QGroupBox("关于")
        gridLayout = QGridLayout(self.aboutGroup)
        
        # 只保留"检查更新"按钮
        self.checkUpdateBtn = QPushButton("检查更新")
        gridLayout.addWidget(self.checkUpdateBtn, 0, 0)
        
        # 更新状态标签
        self.updateStatusLabel = QLabel(f"当前版本：{version_manager.get_version_info('current')}")
        self.updateStatusLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gridLayout.addWidget(self.updateStatusLabel, 0, 1, 1, 2)  # 跨两列显示
        
        layout.addWidget(self.aboutGroup)

    def get_help_text(self):
        """返回程序使用说明的HTML格式文本"""
        return (
            "第一次使用需要点击登陆按钮登陆B站账号，账号密码会储存在配置文件内；<br>"
            "第一次使用\"一键登陆崩坏3\"（需要以管理员身份运行）需要点击\"配置路径\"并选择\"BH3.exe\；<br>"
            "\"BH3.exe\"参考路径：C:\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe；<br>"
            "“解析二维码”会读取剪贴板中崩坏3登陆码并扫码；<br>"
            "“自动截屏”会自动截取崩坏3窗口，不论其在前台还是后台；<br>"
            "“自动退出”会在完成扫码后自动退出程序；<br>"
            "“自动点击”（需要以管理员身份运行）会自动将游戏登陆模式切换为扫码登陆,并在扫码后点击屏幕进入游戏。<br><br>"
            "Powered By Hao_cen & LoveElysia1314"
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
            lambda checked: MainWindow.toggle_feature('clip_check', self.clipCheck, "当前状态")
        )
        self.autoClip.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_clip', self.autoClip, "当前状态")
        )
        self.autoClose.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_close', self.autoClose, "当前状态")
        )
        self.autoClick.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_click', self.autoClick, "当前状态")
        )
        self.debugPrint.clicked.connect(
            lambda checked: MainWindow.toggle_feature('debug_print', self.debugPrint, "当前状态")
        )
        self.configGamePathBtn.clicked.connect(MainWindow.configGamePath)
        self.launchGameBtn.clicked.connect(MainWindow.launchGame)
        self.oneClickLoginBtn.clicked.connect(MainWindow.oneClickLogin)
        
        # 连接关于组按钮信号
        self.checkUpdateBtn.clicked.connect(MainWindow.check_for_updates)

ui = Ui_MainWindow()  # 实例化 UI