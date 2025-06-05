# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit,
                             QVBoxLayout, QFileDialog)



class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setWindowTitle('登录账号')
        # 设置对话框固定大小
        self.setFixedSize(400, 300)
        
        # 设置字体大小
        font = QtGui.QFont()
        font.setPointSize(12)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 增加边距

        self.label1 = QLabel(self)
        self.label1.setText('账号')
        self.label1.setFont(font)

        self.label2 = QLabel(self)
        self.label2.setText('密码')
        self.label2.setFont(font)

        self.account = QLineEdit(self)
        self.account.setEchoMode(QLineEdit.Normal)
        self.account.setFont(font)
        self.account.setMinimumHeight(35)  # 增加输入框高度

        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setFont(font)
        self.password.setMinimumHeight(35)  # 增加输入框高度

        layout.addWidget(self.label1)
        layout.addWidget(self.account)
        layout.addSpacing(15)  # 增加间距
        layout.addWidget(self.label2)
        layout.addWidget(self.password)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttons.setFont(font)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(15)  # 增加间距
        layout.addWidget(buttons)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 1200)  # 增加窗口大小

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # 主布局 - 水平布局
        self.mainLayout = QtWidgets.QHBoxLayout(self.centralwidget)

        # 左侧日志区域
        self.logGroup = QtWidgets.QGroupBox("运行日志", self.centralwidget)
        self.logText = QtWidgets.QTextBrowser()
        self.logText.setObjectName("logText")

        logLayout = QtWidgets.QVBoxLayout(self.logGroup)
        logLayout.addWidget(self.logText)
        self.mainLayout.addWidget(self.logGroup, stretch=3)  # 左侧占3份空间

        # 右侧控制区域
        self.controlGroup = QtWidgets.QGroupBox("控制面板", self.centralwidget)
        controlLayout = QtWidgets.QVBoxLayout(self.controlGroup)

        # 账号设置分组
        self.accountGroup = QtWidgets.QGroupBox("账号设置")
        accountLayout = QtWidgets.QFormLayout(self.accountGroup)

        self.label = QtWidgets.QLabel("登录B站账户:")
        self.loginBiliBtn = QtWidgets.QPushButton("点击登录")
        self.loginBiliBtn.setMaximumSize(QtCore.QSize(200, 16777215))
        accountLayout.addRow(self.label, self.loginBiliBtn)

        # 新增：配置游戏路径
        self.gamePathLabel = QtWidgets.QLabel("配置游戏路径:")
        self.configGamePathBtn = QtWidgets.QPushButton("点击配置")
        self.configGamePathBtn.setMaximumSize(QtCore.QSize(200, 16777215))
        # 将按钮和状态标签放在一个水平布局中
        gamePathLayout = QtWidgets.QHBoxLayout()
        gamePathLayout.addWidget(self.configGamePathBtn)
        accountLayout.addRow(self.gamePathLabel, gamePathLayout)

        # 新增：一键登录崩坏3按钮
        self.oneClickLoginLabel = QtWidgets.QLabel("一键登录崩坏3:")
        self.oneClickLoginBtn = QtWidgets.QPushButton("启动游戏")
        self.oneClickLoginBtn.setMaximumSize(QtCore.QSize(200, 16777215))
        accountLayout.addRow(self.oneClickLoginLabel, self.oneClickLoginBtn)

        controlLayout.addWidget(self.accountGroup)

        # 功能设置分组
        self.featureGroup = QtWidgets.QGroupBox("功能设置")
        featureLayout = QtWidgets.QFormLayout(self.featureGroup)

        self.label_2 = QtWidgets.QLabel("解析二维码:")
        self.clipCheck = QtWidgets.QCheckBox("当前状态:关闭")
        featureLayout.addRow(self.label_2, self.clipCheck)

        self.autoClipLabel = QtWidgets.QLabel("自动尝试截屏:")
        self.autoClipCheck = QtWidgets.QCheckBox("当前状态:关闭")
        featureLayout.addRow(self.autoClipLabel, self.autoClipCheck)

        self.label_4 = QtWidgets.QLabel("扫码完成后自动退出:")
        self.autoCloseCheck = QtWidgets.QCheckBox("当前状态:关闭")
        featureLayout.addRow(self.label_4, self.autoCloseCheck)

        controlLayout.addWidget(self.featureGroup)

        # 关于信息
        self.aboutGroup = QtWidgets.QGroupBox("关于")
        aboutLayout = QtWidgets.QVBoxLayout(self.aboutGroup)

        self.label_3 = QtWidgets.QLabel("Powered By Hao_cen")
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        aboutLayout.addWidget(self.label_3)

        # 使用说明
        self.helpLabel = QtWidgets.QLabel()
        self.helpLabel.setWordWrap(True)
        self.helpLabel.setText("""
            <b>简易使用说明：</b><br>
            1. 第一次使用需要点击登录按钮登录B站账号<br>
            2. 账号密码会储存在配置文件内<br>
            3. 启用解析二维码功能后，会读取剪贴板内二维码<br>
            4. 如果为崩坏3登录二维码则执行扫码<br>
            5. 自动截屏仅在崩坏3为焦点窗口时可用<br>
            6. 使用"一键登陆崩坏3"需要配置游戏路径，请选择"BH3.exe"而不是其他程序
            7. “BH3.exe”参考路径：米哈游启动器安装路径\\miHoYo Launcher\\games\\Honkai Impact 3rd Game\\BH3.exe
        """)
        aboutLayout.addWidget(self.helpLabel)

        controlLayout.addWidget(self.aboutGroup)
        controlLayout.addStretch()  # 添加弹性空间

        self.mainLayout.addWidget(self.controlGroup, stretch=2)  # 右侧占2份空间

        MainWindow.setCentralWidget(self.centralwidget)

        # 菜单栏
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 30))
        MainWindow.setMenuBar(self.menubar)

        self.retranslateUi(MainWindow)
        self.loginBiliBtn.clicked.connect(MainWindow.login)  # type: ignore
        self.clipCheck.clicked['bool'].connect(MainWindow.qrCodeSwitch)  # type: ignore
        self.autoCloseCheck.clicked['bool'].connect(MainWindow.autoCloseSwitch)  # type: ignore
        self.autoClipCheck.clicked['bool'].connect(MainWindow.autoClipSwitch)  # type: ignore
        # 新增：连接新按钮的信号
        self.configGamePathBtn.clicked.connect(MainWindow.configGamePath)  # type: ignore
        self.oneClickLoginBtn.clicked.connect(MainWindow.launchGame)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "崩坏3外置扫码器 v.1.4.9"))

        # 初始化日志区域（使用纯文本）
        self.logText.setPlainText("系统初始化完成，等待操作...")