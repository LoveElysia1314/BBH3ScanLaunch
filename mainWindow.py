# -*- coding: utf-8 -*-
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit,
                               QVBoxLayout, QHBoxLayout, QTextBrowser)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle('登陆账号')
        
        # 使用垂直布局并启用自动大小调整
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)  # 设置合理的边距
        
        # 创建表单布局（垂直布局）
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)  # 控制行间距

        # 账号行
        account_row = QHBoxLayout()
        self.account = QLineEdit()
        self.account.setPlaceholderText("请输入账号")
        self.account.setMinimumHeight(30)
        account_row.addWidget(QLabel("账号:"), alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        account_row.addWidget(self.account)
        account_row.setSpacing(12)

        # 密码行
        password_row = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMinimumHeight(30)
        password_row.addWidget(QLabel("密码:"), alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        password_row.addWidget(self.password)
        password_row.setSpacing(12)

        # 将每行加入到表单布局中
        form_layout.addLayout(account_row)
        form_layout.addLayout(password_row)

        # 添加到主布局
        main_layout.addLayout(form_layout)
        
        # 按钮框
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 自动调整窗口大小
        self.adjustSize()


class Ui_MainWindow:
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setAttribute(Qt.WidgetAttribute.WA_Resized, True)
        
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        # 主水平布局
        self.mainLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.mainLayout.setSpacing(15)  # 全局控件间距
        self.mainLayout.setContentsMargins(15, 15, 15, 15)  # 设置合理边距
        
        # 左侧区域（垂直布局：日志 + 简易说明）
        self.leftContainer = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(self.leftContainer)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 运行日志区域
        self.logGroup = QtWidgets.QGroupBox("运行日志")
        logLayout = QtWidgets.QVBoxLayout(self.logGroup)
        logLayout.setContentsMargins(10, 15, 10, 10)
        
        self.logText = QTextBrowser()
        self.logText.setOpenExternalLinks(True)
        logLayout.addWidget(self.logText)
        left_layout.addWidget(self.logGroup, 3)  # 日志区域占3份
        
        # 简易说明组（原关于组）
        self.suggestionGroup = QtWidgets.QGroupBox("简易说明")
        suggestionLayout = QtWidgets.QVBoxLayout(self.suggestionGroup)
        suggestionLayout.setContentsMargins(10, 12, 10, 12)
        suggestionLayout.setSpacing(8)

        # 添加帮助文本
        self.helpLabel = QtWidgets.QLabel()
        self.helpLabel.setWordWrap(True)  # 自动换行
        self.helpLabel.setText(self.get_help_text())
        suggestionLayout.addWidget(self.helpLabel)
        
        left_layout.addWidget(self.suggestionGroup, 2)  # 简易说明组占2份
        
        # 右侧控制区域
        self.controlGroup = QtWidgets.QGroupBox("控制面板")
        controlLayout = QtWidgets.QVBoxLayout(self.controlGroup)
        controlLayout.setSpacing(15)
        controlLayout.setContentsMargins(12, 15, 12, 12)
        
        # 创建各功能模块
        self.create_account_group(controlLayout)
        self.create_features_group(controlLayout)
        self.create_auto_login_group(controlLayout)
        
        # 添加Powered By标签到控制面板底部
        powered_label = QtWidgets.QLabel("Powered By<br> Hao_cen & LoveElysia1314")
        powered_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        powered_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        controlLayout.addWidget(powered_label)
        
        # 关键修改：让控制面板先根据内容自适应宽度
        self.controlGroup.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred
        )
        
        # 关键修改：使用QWidget容器包装左侧区域
        self.leftContainer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        
        # 添加到主布局
        self.mainLayout.addWidget(self.leftContainer, 3)  # 左侧整体占3份
        self.mainLayout.addWidget(self.controlGroup, 1)  # 控制面板占1份
        
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 菜单栏
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        MainWindow.setMenuBar(self.menubar)
        
        self.retranslateUi(MainWindow)
        self.connectSignals(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def create_account_group(self, layout):
        """创建账号设置组 - 使用网格布局对齐按钮"""
        self.accountGroup = QtWidgets.QGroupBox("账号设置")
        gridLayout = QtWidgets.QGridLayout(self.accountGroup)
        gridLayout.setContentsMargins(10, 10, 10, 10)
        gridLayout.setHorizontalSpacing(10)
        gridLayout.setVerticalSpacing(8)

        row = 0

        # 登陆B站账户
        login_label = QtWidgets.QLabel("登陆B站账户:")
        login_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.loginBiliBtn = QtWidgets.QPushButton("点击登陆")
        self.loginBiliBtn.setMinimumHeight(32)
        
        gridLayout.addWidget(login_label, row, 0)
        gridLayout.addWidget(self.loginBiliBtn, row, 1)
        row += 1

        # 配置游戏路径
        path_label = QtWidgets.QLabel("配置游戏路径:")
        path_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.configGamePathBtn = QtWidgets.QPushButton("点击配置")
        self.configGamePathBtn.setMinimumHeight(32)
        
        gridLayout.addWidget(path_label, row, 0)
        gridLayout.addWidget(self.configGamePathBtn, row, 1)
        row += 1

        # 设置列拉伸比例：标签列自动适应，按钮列固定宽度（根据内容）
        gridLayout.setColumnStretch(0, 1)  # 标签列可扩展，有助于对齐
        gridLayout.setColumnStretch(1, 0)  # 按钮列保持自然宽度

        layout.addWidget(self.accountGroup)

    def create_auto_login_group(self, layout):
        """创建自动化组"""
        self.autoLoginGroup = QtWidgets.QGroupBox("自动化")
        autoLoginLayout = QVBoxLayout(self.autoLoginGroup)
        autoLoginLayout.setContentsMargins(10, 10, 10, 10)
        autoLoginLayout.setSpacing(8)  # 设置按钮间距
        
        # 打开崩坏3按钮
        self.launchGameBtn = QtWidgets.QPushButton("打开崩坏3")
        self.launchGameBtn.setMinimumHeight(32)
        autoLoginLayout.addWidget(self.launchGameBtn)
        
        # 一键登陆崩坏3按钮
        self.oneClickLoginBtn = QtWidgets.QPushButton("一键登陆崩坏3")
        self.oneClickLoginBtn.setMinimumHeight(32)  # 设置最小高度
        autoLoginLayout.addWidget(self.oneClickLoginBtn)
        
        layout.addWidget(self.autoLoginGroup)

    def create_features_group(self, layout):
        """创建功能设置组 - 使用网格布局对齐复选框"""
        self.featureGroup = QtWidgets.QGroupBox("功能设置")
        gridLayout = QtWidgets.QGridLayout(self.featureGroup)
        gridLayout.setContentsMargins(10, 12, 10, 12)
        gridLayout.setHorizontalSpacing(10)
        gridLayout.setVerticalSpacing(8)
        
        # 第一列标签右对齐，第二列复选框左对齐
        row = 0
        
        # 解析二维码
        qr_label = QtWidgets.QLabel("解析二维码:")
        self.clipCheck = QtWidgets.QCheckBox()
        gridLayout.addWidget(qr_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.clipCheck, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row += 1

        # 自动尝试截屏
        auto_clip_label = QtWidgets.QLabel("自动截屏:")
        self.autoClipCheck = QtWidgets.QCheckBox()
        gridLayout.addWidget(auto_clip_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.autoClipCheck, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row += 1

        # 自动退出
        auto_close_label = QtWidgets.QLabel("自动退出:")
        self.autoCloseCheck = QtWidgets.QCheckBox()
        gridLayout.addWidget(auto_close_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.autoCloseCheck, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row += 1
        
        # 自动切换扫码模式和点击进入游戏
        auto_switch_label = QtWidgets.QLabel("自动点击:")
        self.autoClick = QtWidgets.QCheckBox()
        gridLayout.addWidget(auto_switch_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.autoClick, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 设置列拉伸比例
        gridLayout.setColumnStretch(0, 1)  # 标签列可扩展
        gridLayout.setColumnStretch(1, 0)  # 复选框列固定宽度
        
        layout.addWidget(self.featureGroup)

    def create_labeled_widget(self, label_text, widget):
        """创建带标签的控件组合"""
        container = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QtWidgets.QLabel(label_text)
        h_layout.addWidget(label)
        h_layout.addWidget(widget, 1)  # 弹性空间分配
        
        return container

    def get_help_text(self):
        return (
            "第一次使用需要点击登陆按钮登陆B站账号，账号密码会储存在配置文件内；<br>"
            "使用\"一键登陆崩坏3\"需要点击\"配置路径\"并选择\"BH3.exe\"；<br>"
            "\"BH3.exe\"参考路径：C:\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe；<br>"
            "“解析二维码”会读取剪贴板中崩坏3登陆码并扫码；<br>"
            "“自动截屏”会自动截取崩坏3窗口，不论其在前台还是后台；<br>"
            "“自动退出”会在完成扫码后自动退出程序；<br>"
            "“自动点击”会自动将游戏登陆模式切换为扫码登陆,并在扫码后点击屏幕进入游戏。"
        )

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "B服崩坏3扫码登陆器 v.2.0"))
        self.logText.setPlainText("系统初始化完成，等待操作...")

    def connectSignals(self, MainWindow):
        self.loginBiliBtn.clicked.connect(MainWindow.login)
        # 使用 MainWindow 中统一的 toggle_feature 方法来处理复选框状态和文本
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
