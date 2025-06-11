import os
import sys
import subprocess
import shutil
import tempfile
from pathlib import Path
import site
site.ENABLE_USER_SITE = False

# 尝试导入 win32com（仅限 Windows）
try:
    from win32com.client import Dispatch
    WIN_SHORTCUT_AVAILABLE = True
except ImportError:
    WIN_SHORTCUT_AVAILABLE = False


def main():
    # 设置UTF-8编码
    os.environ["PYTHONUTF8"] = "1"
    
    # 获取当前脚本目录
    SCRIPT_DIR = Path(__file__).parent.resolve()
    print(f"脚本目录: {SCRIPT_DIR}")
    
    # 检查并激活虚拟环境
    VENV_DIR = SCRIPT_DIR / "venv"
    activate_script = VENV_DIR / "Scripts" / "activate.bat" if sys.platform == "win32" else VENV_DIR / "bin" / "activate"
    
    if not activate_script.exists():
        print("错误：未找到虚拟环境！")
        print(f"请确保在脚本目录下创建了venv环境: {VENV_DIR}")
        sys.exit(1)
    
    # 在Windows上设置虚拟环境
    if sys.platform == "win32":
        os.environ["PATH"] = f"{VENV_DIR / 'Scripts'};{os.environ['PATH']}"

    # 清理旧的构建缓存
    for cache_dir in ["__pycache__", "build", "dist"]:
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

    # 安装依赖
    install_dependencies(SCRIPT_DIR)

    # 获取Qt插件路径
    QT_PLUGINS = get_qt_plugins_path()
    PLUGIN_SUBDIRS = ["platforms", "imageformats", "styles", "tls"]

    # 构建包含数据目录的参数
    ADD_DATA_ARGS = []
    for subdir in PLUGIN_SUBDIRS:
        source_dir = Path(QT_PLUGINS) / subdir
        if source_dir.exists() and any(source_dir.iterdir()):
            if sys.platform == "win32":
                arg = f"--add-data={source_dir};qt6_plugins/{subdir}"
            else:
                arg = f"--add-data={source_dir}:qt6_plugins/{subdir}"
            ADD_DATA_ARGS.append(arg)
        else:
            print(f"警告：Qt插件目录 {source_dir} 不存在或为空，跳过")

    # 设置输出目录
    OUTPUT_DIR = SCRIPT_DIR / "dist"
    EXE_NAME = "BBH3ScanLaunch.exe"

    # 创建临时目录用于 spec 文件生成
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        WORK_DIR = SCRIPT_DIR / "build_pyinstaller"
        if WORK_DIR.exists():
            shutil.rmtree(WORK_DIR)
        WORK_DIR.mkdir(parents=True, exist_ok=True)

        os.chdir(WORK_DIR)
        
        pyinstaller_cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name=BBH3ScanLaunch",
            "--workpath", str(SCRIPT_DIR / "build"),
            "--distpath", str(OUTPUT_DIR),
            "--specpath", tmpdir,
            "--onefile",
            "--windowed" if sys.platform == "win32" else "",
            "-i", str(SCRIPT_DIR / "BHimage.ico"),
        ] + ADD_DATA_ARGS + [
            "--add-data", f"{SCRIPT_DIR / 'templates'};templates",
            "--add-data", f"{SCRIPT_DIR / 'Pictures_to_Match'};Pictures_to_Match",
            "--hidden-import=PySide6.QtNetwork",
            "--hidden-import=PySide6.QtSvg",
            str(SCRIPT_DIR / "main.py")
        ]

        print("\n运行 PyInstaller 命令...")
        print(" ".join(pyinstaller_cmd))

        result = subprocess.run(pyinstaller_cmd, check=True)
        if result.returncode != 0:
            print("PyInstaller 打包失败！")
            sys.exit(1)

    # 回到原目录
    os.chdir(SCRIPT_DIR)

    # 复制资源目录、配置文件、图标等
    RESOURCE_DIRS = ["Pictures_to_Match", "templates"]
    for resource in RESOURCE_DIRS:
        src = SCRIPT_DIR / resource
        dst = OUTPUT_DIR / resource
        if src.exists():
            print(f"正在复制资源目录: {resource}")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            print(f"警告：找不到资源目录: {resource}")

    config_src = SCRIPT_DIR / "config.json"
    config_dst = OUTPUT_DIR / "config.json"
    if config_src.exists():
        shutil.copy2(config_src, config_dst)

    icon_src = SCRIPT_DIR / "BHimage.ico"
    icon_dst = OUTPUT_DIR / "BHimage.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dst)

    # 创建快捷方式 (仅 Windows)
    if sys.platform == "win32":
        create_windows_shortcuts(OUTPUT_DIR, EXE_NAME)

    # 创建纯净压缩包
    create_clean_package(SCRIPT_DIR, OUTPUT_DIR, EXE_NAME)

    print("\n============= 构建成功 =============")
    print(f"单文件EXE: {OUTPUT_DIR / EXE_NAME}")
    print(f"资源目录: {OUTPUT_DIR / 'Pictures_to_Match'} 和 {OUTPUT_DIR / 'templates'}")
    print(f"压缩包位置: {OUTPUT_DIR / 'BBH3ScanLaunch_v8.3.zip'}")
    print("===================================")


def install_dependencies(script_dir):
    """安装依赖"""
    print("\n===== 安装依赖 =====")
    
    # 安装requirements.txt中的依赖
    requirements_file = script_dir / "requirements.txt"
    if requirements_file.exists():
        print(f"安装依赖文件: {requirements_file}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"安装依赖失败: {e}")
            sys.exit(1)
    else:
        print(f"未找到 requirements.txt 文件，跳过依赖安装")


def get_qt_plugins_path():
    """获取Qt插件路径"""
    cmd = [
        sys.executable,
        "-c",
        "from PySide6.QtCore import QLibraryInfo; "
        "import os; "
        "path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath); "
        "print(os.path.normpath(path))"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def create_windows_shortcuts(output_dir, exe_name):
    """使用 Python 创建 Windows 快捷方式 (.lnk)"""
    if not WIN_SHORTCUT_AVAILABLE:
        print("警告：未安装 pywin32，跳过创建快捷方式")
        return

    TARGET_EXE = output_dir / exe_name
    ICON_FILE = output_dir / "BHimage.ico"

    def create_shortcut(target_path, shortcut_path, arguments="", icon_path=None, workdir=None):
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(target_path)
        shortcut.Arguments = arguments
        if icon_path and icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        shortcut.WorkingDirectory = str(workdir or output_dir)
        shortcut.save()

    # 快捷方式路径
    shortcut1 = output_dir / "[仅B服] 崩坏3扫码器 [限v8.3].lnk"
    shortcut2 = output_dir / "[仅B服] 一键登录崩坏3 [限v8.3].lnk"

    # 创建第一个快捷方式（普通启动）
    create_shortcut(
        target_path=TARGET_EXE,
        shortcut_path=shortcut1,
        icon_path=ICON_FILE,
        workdir=output_dir
    )

    # 创建第二个快捷方式（带自动登录参数）
    create_shortcut(
        target_path=TARGET_EXE,
        shortcut_path=shortcut2,
        arguments="--auto-login",
        icon_path=ICON_FILE,
        workdir=output_dir
    )

    print("已创建快捷方式")


def create_clean_package(script_dir, output_dir, exe_name):
    """创建纯净压缩包"""
    PACKAGE_DIR = output_dir / "BBH3ScanLaunch_Package"
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 复制EXE文件
    exe_src = output_dir / exe_name
    exe_dst = PACKAGE_DIR / exe_name
    shutil.copy2(exe_src, exe_dst)
    
    # 特殊处理Pictures_to_Match目录（只复制Default子目录）
    default_pics_src = script_dir / "Pictures_to_Match" / "Default"
    if default_pics_src.exists():
        print("正在复制资源目录: Pictures_to_Match/Default")
        default_pics_dst = PACKAGE_DIR / "Pictures_to_Match" / "Default"
        shutil.copytree(default_pics_src, default_pics_dst)
    
    # 复制templates目录
    templates_src = script_dir / "templates"
    templates_dst = PACKAGE_DIR / "templates"
    if templates_src.exists():
        shutil.copytree(templates_src, templates_dst)
    
    # 复制配置文件
    config_src = output_dir / "config.json"
    config_dst = PACKAGE_DIR / "config.json"
    if config_src.exists():
        shutil.copy2(config_src, config_dst)
    
    # 复制图标
    icon_src = output_dir / "BHimage.ico"
    icon_dst = PACKAGE_DIR / "BHimage.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dst)
    
    # 创建压缩包
    ZIP_FILE = output_dir / "BBH3ScanLaunch_v8.3.zip"
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()
    
    shutil.make_archive(str(ZIP_FILE.with_suffix('')), 'zip', PACKAGE_DIR)
    
    # 清理临时打包目录
    shutil.rmtree(PACKAGE_DIR)
    print(f"已创建压缩包: {ZIP_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)