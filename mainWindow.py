# -*- coding: utf-8 -*-
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit,
                               QVBoxLayout, QHBoxLayout, QTextBrowser)


class LoginDialog(QDialog):
    """
    账号登录对话框
    提供B站账号和密码输入表单，用于用户认证
    """
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle('登陆账号')
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 创建表单控件
        self.create_form_controls(main_layout)
        
        # 按钮框
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.adjustSize()
    
    def create_form_controls(self, layout):
        """创建账号密码输入表单控件"""
        fields = [
            ("账号:", "account", "请输入账号"),
            ("密码:", "password", "请输入密码")
        ]
        
        for label_text, attr_name, placeholder in fields:
            row = QHBoxLayout()
            row.setSpacing(12)
            
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setMinimumHeight(30)
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
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.mainLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.mainLayout.setSpacing(15)
        self.mainLayout.setContentsMargins(15, 15, 15, 15)
        
        # 创建左侧区域
        self.create_left_area()
        
        # 创建右侧控制面板
        self.create_control_panel()
        
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        MainWindow.setMenuBar(self.menubar)
        
        self.retranslateUi(MainWindow)
        self.connectSignals(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def create_left_area(self):
        """创建包含日志和说明的左侧面板"""
        self.leftContainer = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self.leftContainer)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 日志区域
        self.logGroup = QtWidgets.QGroupBox("运行日志")
        logLayout = QtWidgets.QVBoxLayout(self.logGroup)
        logLayout.setContentsMargins(10, 15, 10, 10)
        self.logText = QTextBrowser()
        self.logText.setOpenExternalLinks(True)
        logLayout.addWidget(self.logText)
        left_layout.addWidget(self.logGroup, 3)
        
        # 说明区域
        self.suggestionGroup = QtWidgets.QGroupBox("简易说明")
        suggestionLayout = QtWidgets.QVBoxLayout(self.suggestionGroup)
        suggestionLayout.setContentsMargins(10, 12, 10, 12)
        suggestionLayout.setSpacing(8)
        self.helpLabel = QtWidgets.QLabel()
        self.helpLabel.setWordWrap(True)
        self.helpLabel.setText(self.get_help_text())
        suggestionLayout.addWidget(self.helpLabel)
        left_layout.addWidget(self.suggestionGroup, 2)
        
        # 添加到主布局
        self.leftContainer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.mainLayout.addWidget(self.leftContainer, 3)

    def create_control_panel(self):
        """创建包含账号设置和功能控制的右侧面板"""
        self.controlGroup = QtWidgets.QGroupBox("控制面板")
        controlLayout = QtWidgets.QVBoxLayout(self.controlGroup)
        controlLayout.setSpacing(15)
        controlLayout.setContentsMargins(12, 15, 12, 12)
        
        # 创建各组
        self.create_account_group(controlLayout)
        self.create_features_group(controlLayout)
        self.create_auto_login_group(controlLayout)
        
        # 页脚
        powered_label = QtWidgets.QLabel("Powered By<br> Hao_cen & LoveElysia1314")
        powered_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        powered_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        controlLayout.addWidget(powered_label)
        
        # 添加到主布局
        self.controlGroup.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.mainLayout.addWidget(self.controlGroup, 1)

    def create_account_group(self, layout):
        """创建B站账号和游戏路径设置区域"""
        self.accountGroup = QtWidgets.QGroupBox("账号设置")
        gridLayout = QtWidgets.QGridLayout(self.accountGroup)
        gridLayout.setContentsMargins(10, 10, 10, 10)
        gridLayout.setHorizontalSpacing(10)
        gridLayout.setVerticalSpacing(8)
        
        # 按钮配置
        buttons = [
            ("登陆B站账户:", "loginBiliBtn", "点击登陆"),
            ("配置游戏路径:", "configGamePathBtn", "点击配置")
        ]
        
        for row, (label_text, attr_name, btn_text) in enumerate(buttons):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            btn = QtWidgets.QPushButton(btn_text)
            btn.setMinimumHeight(30)
            setattr(self, attr_name, btn)
            
            gridLayout.addWidget(label, row, 0)
            gridLayout.addWidget(btn, row, 1)
        
        gridLayout.setColumnStretch(0, 1)
        gridLayout.setColumnStretch(1, 0)
        layout.addWidget(self.accountGroup)

    def create_features_group(self, layout):
        """创建二维码解析和自动操作功能开关区域"""
        self.featureGroup = QtWidgets.QGroupBox("功能设置")
        gridLayout = QtWidgets.QGridLayout(self.featureGroup)
        gridLayout.setContentsMargins(10, 12, 10, 12)
        gridLayout.setHorizontalSpacing(10)
        gridLayout.setVerticalSpacing(8)
        
        # 复选框配置
        checkboxes = [
            ("解析二维码:", "clipCheck"),
            ("自动截屏:", "autoClipCheck"),
            ("自动退出:", "autoCloseCheck"),
            ("自动点击:", "autoClick")
        ]
        
        for row, (label_text, attr_name) in enumerate(checkboxes):
            label = QtWidgets.QLabel(label_text)
            checkbox = QtWidgets.QCheckBox()
            setattr(self, attr_name, checkbox)
            
            gridLayout.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            gridLayout.addWidget(checkbox, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        gridLayout.setColumnStretch(0, 1)
        gridLayout.setColumnStretch(1, 0)
        layout.addWidget(self.featureGroup)

    def create_auto_login_group(self, layout):
        """创建游戏启动和一键登录按钮区域"""
        self.autoLoginGroup = QtWidgets.QGroupBox("自动化")
        autoLoginLayout = QVBoxLayout(self.autoLoginGroup)
        autoLoginLayout.setContentsMargins(10, 10, 10, 10)
        autoLoginLayout.setSpacing(8)
        
        # 按钮配置
        buttons = [
            ("打开崩坏3", "launchGameBtn"),
            ("一键登陆崩坏3", "oneClickLoginBtn")
        ]
        
        for btn_text, attr_name in buttons:
            btn = QtWidgets.QPushButton(btn_text)
            btn.setMinimumHeight(30)
            setattr(self, attr_name, btn)
            autoLoginLayout.addWidget(btn)
        
        layout.addWidget(self.autoLoginGroup)

    def get_help_text(self):
        """返回程序使用说明的HTML格式文本"""
        return (
            "第一次使用需要点击登陆按钮登陆B站账号，账号密码会储存在配置文件内；<br>"
            "第一次使用“一键登陆崩坏3”（需要以管理员身份运行）需要点击\"配置路径\"并选择\"BH3.exe\；<br>"
            "\"BH3.exe\"参考路径：C:\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe；<br>"
            "“解析二维码”会读取剪贴板中崩坏3登陆码并扫码；<br>"
            "“自动截屏”会自动截取崩坏3窗口，不论其在前台还是后台；<br>"
            "“自动退出”会在完成扫码后自动退出程序；<br>"
            "“自动点击”（需要以管理员身份运行）会自动将游戏登陆模式切换为扫码登陆,并在扫码后点击屏幕进入游戏。"
        )

    def retranslateUi(self, MainWindow):
        """设置窗口标题和初始化文本"""
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "B服崩坏3扫码登陆器 v.2.1.2"))
        self.logText.setPlainText("系统初始化完成，等待操作...")

    def connectSignals(self, MainWindow):
        """连接所有按钮和复选框的信号与槽函数"""
        self.loginBiliBtn.clicked.connect(MainWindow.login)
        self.clipCheck.clicked.connect(
            lambda checked: MainWindow.toggle_feature('clip_check', self.clipCheck, "当前状态")
        )
        self.autoClipCheck.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_clip', self.autoClipCheck, "当前状态")
        )
        self.autoCloseCheck.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_close', self.autoCloseCheck, "当前状态")
        )
        self.autoClick.clicked.connect(
            lambda checked: MainWindow.toggle_feature('auto_switch_mode', self.autoClick, "当前状态")
        )
        self.configGamePathBtn.clicked.connect(MainWindow.configGamePath)
        self.launchGameBtn.clicked.connect(MainWindow.launchGame)
        self.oneClickLoginBtn.clicked.connect(MainWindow.oneClickLogin)
