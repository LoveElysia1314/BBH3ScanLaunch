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


# 开关配置：是否使用单文件模式
USE_ONEFILE = False  # 修改此值切换模式：True=单文件，False=多文件


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
    
    # 屏蔽除虚拟环境外的所有环境变量
    clean_environment(VENV_DIR)

    # 清理旧的构建缓存
    for cache_dir in ["__pycache__", "build", "dist"]:
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

    # 安装依赖
    install_dependencies(SCRIPT_DIR)

    # 设置输出目录和程序路径
    OUTPUT_DIR = SCRIPT_DIR / "dist"
    EXE_NAME = "BBH3ScanLaunch.exe"

    # 根据模式选择程序主目录
    if USE_ONEFILE:
        APP_DIR = OUTPUT_DIR  # 单文件模式下，EXE直接在dist目录
    else:
        APP_DIR = OUTPUT_DIR / "BBH3ScanLaunch"  # 多文件模式下，EXE在子目录

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
            "--noconsole",
            "-i", str(SCRIPT_DIR / "BHimage.ico"),
            "--exclude-module", "PyQt5",
            "--exclude-module", "PyQt6", 
            "--add-binary", f"{VENV_DIR / 'Lib' / 'site-packages' / 'pyzbar' / 'libiconv.dll'};.",
            "--add-binary", f"{VENV_DIR / 'Lib' / 'site-packages' / 'pyzbar' / 'libzbar-64.dll'};.",
            "--add-data", f"{SCRIPT_DIR / 'templates'};templates",
            "--add-data", f"{SCRIPT_DIR / 'Pictures_to_Match'};Pictures_to_Match",
            str(SCRIPT_DIR / "main.py")
        ]

        # 动态添加 --onefile 参数
        if USE_ONEFILE:
            pyinstaller_cmd.insert(4, "--onefile")
        
        print("\n运行 PyInstaller 命令...")
        print(" ".join(pyinstaller_cmd))

        result = subprocess.run(pyinstaller_cmd, check=True)
        if result.returncode != 0:
            print("PyInstaller 打包失败！")
            sys.exit(1)

    # 回到原目录
    os.chdir(SCRIPT_DIR)

    # 复制资源目录、图标等（排除 config.json）
    RESOURCE_DIRS = ["templates"]
    for resource in RESOURCE_DIRS:
        src = SCRIPT_DIR / resource
        dst = APP_DIR / resource
        if src.exists():
            print(f"正在复制资源目录: {resource}")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            print(f"警告：找不到资源目录: {resource}")

    # 仅复制 Pictures_to_Match/Default 子目录
    pics_src = SCRIPT_DIR / "Pictures_to_Match" / "Default"
    pics_dst = APP_DIR / "Pictures_to_Match" / "Default"
    if pics_src.exists():
        print("正在复制资源目录: Pictures_to_Match/Default")
        if pics_dst.exists():
            shutil.rmtree(pics_dst)
        shutil.copytree(pics_src, pics_dst)
    else:
        print("警告：找不到资源目录: Pictures_to_Match/Default")

    # 图标文件
    icon_src = SCRIPT_DIR / "BHimage.ico"
    icon_dst = APP_DIR / "BHimage.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dst)

    # 创建快捷方式 (仅 Windows)，生成在 dist/ 根目录下
    if sys.platform == "win32":
        create_windows_shortcuts(APP_DIR, EXE_NAME)

    # 创建纯净压缩包（直接打包整个 dist/ 目录）
    create_clean_package(SCRIPT_DIR, OUTPUT_DIR, EXE_NAME, APP_DIR)

    print("\n============= 构建成功 =============")
    if USE_ONEFILE:
        print(f"单文件EXE: {APP_DIR / EXE_NAME}")
    else:
        print(f"程序目录: {APP_DIR}")
    print(f"资源目录: {APP_DIR / 'Pictures_to_Match'} 和 {APP_DIR / 'templates'}")
    print(f"压缩包位置: {OUTPUT_DIR.parent / 'BBH3ScanLaunch_v8.3.zip'}")
    print("===================================")


def clean_environment(venv_dir):
    """屏蔽除虚拟环境外的所有环境变量"""
    print("\n===== 清理环境变量 =====")
    
    # 获取系统主目录路径
    if sys.platform == "win32":
        user_profile = os.environ.get("USERPROFILE", "")
    else:
        user_profile = os.environ.get("HOME", "") or os.environ.get("USERPROFILE", "")

    # 保留的关键环境变量
    keep_envs = {
        "PATH": str(venv_dir / "Scripts") + os.pathsep + str(venv_dir / "bin"),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "PYTHONUTF8": "1",
        "USERPROFILE": user_profile,
        "HOME": user_profile
    }
    
    # 对于Windows系统，添加必要的系统路径
    if sys.platform == "win32":
        sys_paths = [
            os.environ.get("SystemRoot", ""),
            os.path.join(os.environ.get("SystemRoot", ""), "System32"),
            os.path.join(os.environ.get("SystemRoot", ""), "SysWOW64")
        ]
        keep_envs["PATH"] = os.pathsep.join(
            [str(venv_dir / "Scripts")] + 
            [p for p in sys_paths if p] + 
            [keep_envs["PATH"]]
        )
    
    # 清除非必要的环境变量
    for key in list(os.environ.keys()):
        if key not in keep_envs:
            del os.environ[key]
    
    # 设置保留的环境变量
    for key, value in keep_envs.items():
        if value:
            os.environ[key] = value
    
    print("当前环境变量:")
    for key, value in os.environ.items():
        print(f"{key}: {value}")


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


def create_windows_shortcuts(app_dir, exe_name):
    """使用 Python 创建 Windows 快捷方式 (.lnk)"""
    if not WIN_SHORTCUT_AVAILABLE:
        print("警告：未安装 pywin32，跳过创建快捷方式")
        return

    TARGET_EXE = app_dir / exe_name
    ICON_FILE = app_dir / "BHimage.ico"

    def create_shortcut(target_path, shortcut_path, arguments="", icon_path=None, workdir=None):
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(target_path)
        shortcut.Arguments = arguments
        if icon_path and icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        shortcut.WorkingDirectory = str(workdir or app_dir)
        shortcut.save()

    # 快捷方式生成在 dist/ 根目录下
    shortcut1 = app_dir.parent / "[仅B服] 崩坏3扫码器 [限v8.3].lnk"
    shortcut2 = app_dir.parent / "[仅B服] 一键登陆崩坏3 [限v8.3].lnk"

    # 创建第一个快捷方式（普通启动）
    create_shortcut(
        target_path=TARGET_EXE,
        shortcut_path=shortcut1,
        icon_path=ICON_FILE,
        workdir=app_dir
    )

    # 创建第二个快捷方式（带自动登陆参数）
    create_shortcut(
        target_path=TARGET_EXE,
        shortcut_path=shortcut2,
        arguments="--auto-login",
        icon_path=ICON_FILE,
        workdir=app_dir
    )

    print("已创建快捷方式")


def create_clean_package(script_dir, output_dir, exe_name, app_dir):
    """创建纯净压缩包：直接打包 dist 目录中的所有内容"""
    ZIP_FILE = output_dir.parent / "BBH3ScanLaunch_v8.3.zip"
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()

    print(f"正在创建压缩包，内容来自: {output_dir}")
    shutil.make_archive(str(ZIP_FILE.with_suffix('')), 'zip', output_dir)
    print(f"已创建压缩包: {ZIP_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)