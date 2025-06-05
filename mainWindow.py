# -*- coding: utf-8 -*-
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit,
                             QVBoxLayout, QHBoxLayout, QTextBrowser, QGridLayout)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle('登录账号')
        
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
        
        # 左侧日志区域
        self.logGroup = QtWidgets.QGroupBox("运行日志")
        logLayout = QtWidgets.QVBoxLayout(self.logGroup)
        logLayout.setContentsMargins(10, 15, 10, 10)
        
        self.logText = QTextBrowser()
        self.logText.setOpenExternalLinks(True)
        logLayout.addWidget(self.logText)
        
        # 右侧控制区域
        self.controlGroup = QtWidgets.QGroupBox("控制面板")
        controlLayout = QtWidgets.QVBoxLayout(self.controlGroup)
        controlLayout.setSpacing(15)
        controlLayout.setContentsMargins(12, 15, 12, 12)
        
        # 创建各功能模块（注意顺序调整）
        self.create_account_group(controlLayout)
        self.create_auto_login_group(controlLayout)  # 新增的自动登录组
        self.create_features_group(controlLayout)
        self.create_about_group(controlLayout)
        
        # 弹性空间分配
        self.mainLayout.addWidget(self.logGroup, 3)  # 日志区域占更多空间
        self.mainLayout.addWidget(self.controlGroup, 2)
        
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 菜单栏
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        MainWindow.setMenuBar(self.menubar)
        
        self.retranslateUi(MainWindow)
        self.connectSignals(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def create_account_group(self, layout):
        """创建账号设置组"""
        self.accountGroup = QtWidgets.QGroupBox("账号设置")
        accountLayout = QtWidgets.QVBoxLayout(self.accountGroup)
        accountLayout.setContentsMargins(10, 10, 10, 10)
        
        self.loginBiliBtn = QtWidgets.QPushButton("点击登录")
        self.configGamePathBtn = QtWidgets.QPushButton("点击配置")
        
        accountLayout.addWidget(self.create_labeled_widget("登录B站账户:", self.loginBiliBtn))
        accountLayout.addWidget(self.create_labeled_widget("配置游戏路径:", self.configGamePathBtn))
        
        layout.addWidget(self.accountGroup)

    def create_auto_login_group(self, layout):
        """创建自动化组"""
        self.autoLoginGroup = QtWidgets.QGroupBox("自动化")
        autoLoginLayout = QVBoxLayout(self.autoLoginGroup)
        autoLoginLayout.setContentsMargins(10, 10, 10, 10)
        
        # 保留原有接口名称，仅修改显示文本
        self.oneClickLoginBtn = QtWidgets.QPushButton("一键进入崩坏3")
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
        auto_clip_label = QtWidgets.QLabel("自动尝试截屏:")
        self.autoClipCheck = QtWidgets.QCheckBox()
        gridLayout.addWidget(auto_clip_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.autoClipCheck, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row += 1

        # 自动退出
        auto_close_label = QtWidgets.QLabel("扫码完成后自动退出:")
        self.autoCloseCheck = QtWidgets.QCheckBox()
        gridLayout.addWidget(auto_close_label, row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gridLayout.addWidget(self.autoCloseCheck, row, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # 设置列拉伸比例
        gridLayout.setColumnStretch(0, 1)  # 标签列可扩展
        gridLayout.setColumnStretch(1, 0)  # 复选框列固定宽度
        
        layout.addWidget(self.featureGroup)

    def create_about_group(self, layout):
        """创建关于信息组，高度自适应内容"""
        self.aboutGroup = QtWidgets.QGroupBox("关于")
        aboutLayout = QtWidgets.QVBoxLayout(self.aboutGroup)
        aboutLayout.setContentsMargins(10, 12, 10, 12)
        aboutLayout.setSpacing(8)

        # 添加标题
        self.label_3 = QtWidgets.QLabel("Powered By Hao_cen")
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_3.setStyleSheet("font-weight: bold;")
        aboutLayout.addWidget(self.label_3)

        # 添加帮助文本
        self.helpLabel = QtWidgets.QLabel()
        self.helpLabel.setWordWrap(True)  # 自动换行
        self.helpLabel.setText(self.get_help_text())
        self.helpLabel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred
        )
        aboutLayout.addWidget(self.helpLabel, 1)  # 添加拉伸因子
        
        layout.addWidget(self.aboutGroup, 1)  # 设置拉伸因子

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
        return """
            <b>简易使用说明：</b><br>
            1. 第一次使用需要点击登录按钮登录B站账号<br>
            2. 账号密码会储存在配置文件内<br>
            3. 启用解析二维码功能后，会读取剪贴板内二维码<br>
            4. 如果为崩坏3登录二维码则执行扫码<br>
            5. 自动截屏仅在崩坏3为焦点窗口时可用<br>
            6. 使用"一键登陆崩坏3"需要配置游戏路径，请选择"BH3.exe"而不是其他程序
            7. “BH3.exe”参考路径：米哈游启动器安装路径\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe
        """

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "崩坏3外置扫码器 v.1.4.9"))
        self.logText.setPlainText("系统初始化完成，等待操作...")

    def connectSignals(self, MainWindow):
        self.loginBiliBtn.clicked.connect(MainWindow.login)
        self.clipCheck.clicked.connect(MainWindow.qrCodeSwitch)
        self.autoCloseCheck.clicked.connect(MainWindow.autoCloseSwitch)
        self.autoClipCheck.clicked.connect(MainWindow.autoClipSwitch)
        self.configGamePathBtn.clicked.connect(MainWindow.configGamePath)
        self.oneClickLoginBtn.clicked.connect(MainWindow.launchGame)