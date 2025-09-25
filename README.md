# BBH3ScanLaunch v1.3.4.2

一个用于B服崩坏三扫码和一键登录的工具，旨在简化登录流程并提供自动化功能。项目源码源自 [scannerHelper-memories](https://github.com/HonkaiScanner/scannerHelper-memories)，特别鸣谢 [Hao_cen@bilibili](https://space.bilibili.com/269140934?spm_id_from=333.1387)。

## 功能特点

- **B站账号登录**：首次手动登录后缓存信息，后续快速登录。
- **快捷启动游戏**：配置 `BH3.exe` 路径后，可快捷打开崩坏3或一键登录（需管理员权限）。
- **二维码解析**：与手机端B服崩坏3扫码功能相同。
- **自动化功能**：
  - 自动截屏：后台监控游戏窗口，自动截取内容。
  - 自动退出：扫码完成后自动退出程序。
  - 自动点击：自动切换登录模式并确认（需管理员权限）。
- **多分辨率支持**：支持不同屏幕分辨率的模板匹配，用户可自行添加素材。
- **模板管理**：提供“管理模板”按钮，快速打开模板图片文件夹，便于添加和管理分辨率模板。
- **图形用户界面**：基于 PySide6 构建，支持暗色和亮色模式。
- **命令行参数支持**：通过 `--auto-login` 参数触发一键登录流程。
- **跨版本支持**：自动从远程获取 `oa_token.json` 文件，确保兼容性。
- **Markdown 渲染**：程序说明与更新日志支持 Markdown 格式展示。
- **网络错误处理**：自动处理 SSL 连接错误，提升稳定性。

## 安装与使用

### 环境要求
- **操作系统**：Windows 10/11
- **Python版本**：3.10+
- **依赖库**：详见 `requirements.txt`。主要依赖包括 `PySide6`、`opencv-python-headless`、`pillow`、`pyautogui`、`pyzbar`、`flask`、`requests`、`cryptography`、`markdown`、`psutil`。

### 使用源码
1. 克隆仓库：
   ```bash
   git clone https://github.com/LoveElysia1314/BBH3ScanLaunch.git
   cd BBH3ScanLaunch
   ```
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. 运行程序：
   ```bash
   python run.py
   ```

### 从源码编译
1. 安装 `pyinstaller`：
   ```bash
   pip install pyinstaller
   ```
2. 打包为可执行文件：
   ```bash
   python scripts/build.py
   ```
   - 输出位置：`dist/` 目录。
   - 包含快捷方式：
     - `[仅B服] 崩坏3扫码器.lnk`：标准模式。
     - `[仅B服] 一键登录崩坏3.lnk`：全自动模式。

### 使用说明
1. **首次配置**：
   - 运行程序后点击"登录账号"输入B站账号密码。
   - 点击"配置游戏路径"选择 `BH3.exe` 文件。
   - 推荐路径：`C:\miHoYo Launcher\games\Honkai Impact 3rd Game\BH3.exe`。

2. **功能开关**：
   - `解析二维码`：读取剪贴板中的登录码。
   - `自动截屏`：后台监控游戏窗口。
   - `自动退出`：扫码成功后自动关闭程序。
   - `自动点击`：自动切换登录方式并确认。
   - `管理模板`：打开模板图片文件夹，便于管理和添加匹配模板。

3. **图片匹配与自动点击原理**：
   - 程序会遍历 `resources/pictures_to_match/` 文件夹中的所有模板图片。
   - 自动在游戏窗口中寻找与模板图片匹配的界面元素。
   - 匹配成功后，自动点击匹配区域的中心位置。
   - 用户可按需添加相关图片模板（如登录按钮、确认按钮等），实现更完善的自动化流程。
   - 模板图片命名规则：`{屏幕高}p_{序号}.png`，如 `1920p_1.png`。

4. **一键登录**：
   - 点击"一键登录崩坏3"启动全自动流程：
     1. 自动启动游戏。
     2. 后台监控扫码。
     3. 自动点击确认。
     4. 完成后自动退出。

## 项目结构

```
BBH3ScanLaunch/
├── src/
│   └── bbh3_scan_launch/
│       ├── main.py                    # 主程序入口，GUI事件处理
│       ├── constants.py               # 常量定义
│       ├── dependency_container.py    # 依赖注入容器
│       ├── gui/
│       │   └── main_window.py         # PySide6界面实现
│       ├── core/
│       │   ├── bh3_utils.py           # 图像处理/窗口操作核心，包含BH3GameManager类
│       │   └── sdk/
│       │       ├── mihoyosdk.py       # 米哈游登录接口封装
│       │       └── bsgamesdk.py       # B站登录接口封装
│       └── utils/
│           ├── config_utils.py        # 配置管理
│           ├── exception_utils.py     # 异常处理
│           ├── network_utils.py       # 网络工具
│           ├── rsacr.py               # RSA 加密工具
│           └── version_utils.py       # 版本管理
├── resources/                        # 资源文件
│   ├── pictures_to_match/            # 模板图片（多分辨率支持）
│   │   ├── 1260p_1.png
│   │   ├── 1260p_2.png
│   │   ├── 4000p_1.png
│   │   ├── 4000p_2.png
│   │   └── 4000p_3.png
│   └── templates/                    # HTML模板
│       ├── geetest.html
│       └── index.html
├── config/                           # 配置文件（运行时生成）
│   └── config.json
├── scripts/                          # 构建脚本
│   └── build.py                      # PyInstaller 打包和安装包构建脚本
├── updates/                          # 更新相关文件
│   ├── CHANGELOG.md                  # 更新日志
│   └── version.json                  # 版本信息
├── run.py                            # 主入口文件
├── requirements.txt                  # Python 依赖
├── LICENSE                           # 许可证文件
├── README.md                         # 项目说明
└── BHimage.ico                       # 程序图标
```

## 核心模块

| 模块 | 功能描述 |
|------|----------|
| `main.py` | 主程序入口，GUI 事件处理和 Flask 服务器管理 |
| `main_window.py` | PySide6 图形界面实现 |
| `bh3_utils.py` | 游戏窗口操作、图像处理、自动化点击核心逻辑，包含 BH3GameManager 类 |
| `mihoyosdk.py` | 米哈游登录接口封装 |
| `bsgamesdk.py` | B站游戏登录接口封装 |
| `config_utils.py` | 配置文件读取和管理 |
| `version_utils.py` | 版本管理和远程更新检查 |
| `network_utils.py` | 网络请求和错误处理 |
| `exception_utils.py` | 统一异常处理装饰器 |
| `rsacr.py` | RSA 加密工具 |
| `build.py` | PyInstaller 自动化构建和 Windows 安装包构建脚本 |

## 注意事项

1. **管理员权限**：
   - 自动截屏/点击功能需要管理员权限运行。
   - 首次使用需右键"以管理员身份运行"。

2. **游戏版本兼容性**：
   - 通过访问远程 `oa_token.json` 实现多版本支持。
   - 支持最新版本的崩坏3游戏，自动适配版本更新。

3. **分辨率适配**：
   - 支持绝大部分分辨率（1260p、4000p 等）。
   - 其他分辨率需添加模板图片到 `resources/pictures_to_match/` 目录。
   - 命名规则：屏幕高度 + 编号，如 `1920p_1.png`。
   - 注意：部分图片模板，例如“登录其他账号”，主要为文字内容，会受屏幕分辨率、比例及Windows缩放影响。若无法识别，请自行截取并裁剪图片，按照命名规则 `{屏幕高}p_{图片序号}` 放置在 `resources/pictures_to_match/` 目录中。点击“管理模板”按钮打开模板文件夹。

4. **网络要求**：
   - 需要稳定的网络连接进行登录验证。
   - 程序会自动处理网络错误并重试。

## 常见问题

**Q："自动点击"功能无效？**  
A：请确保以管理员权限运行程序，检查游戏窗口是否正确识别。

**Q：一键登录模式异常？**  
A：检查游戏路径配置是否正确，确保选择的是 `BH3.exe` 文件。确认游戏已安装且可正常启动。

**Q：二维码无法识别？**  
A：确保屏幕分辨率受支持，或手动添加相应模板图片。

**Q：无法识别“登录其他账号”控件？**  
A：该控件主要为文字内容，会受屏幕分辨率、比例及Windows缩放影响。若无法识别，请自行截取并裁剪图片，按照命名规则 `{屏幕高}p_{图片序号}` 放置在 `resources/pictures_to_match/` 目录中。点击“管理模板”按钮打开模板文件夹。

**Q：登录信息缓存问题？**  
A：更换账号密码后，程序会自动清理缓存。也可手动删除 `config/config.json` 文件重置配置。

**Q：网络连接错误？**  
A：检查网络连接，程序会自动重试。如遇 SSL 错误，程序会自动处理并弹出登录框。

**Q：程序卡死或无响应？**  
A：检查是否有多个程序实例运行，尝试重启程序。如问题持续，可查看日志文件排查。

## 贡献指南

欢迎提交 Pull Request，请确保：
1. 遵循现有代码风格。
2. 更新相关文档。
3. 通过基础功能测试。

## 更新日志

查看完整更新日志：[CHANGELOG.md](./updates/CHANGELOG.md)

## 许可证

[GPLv3 License](./LICENSE)
