import os
import shutil
import subprocess
import sys
from pathlib import Path
from win32com.client import Dispatch

# ------------------ 配置项 ------------------
ENTRY_SCRIPT = "main.py"  # 主脚本文件
ICON_FILE = "BHimage.ico"
DIST_DIR = Path("dist") / Path(ENTRY_SCRIPT).stem
SHORTCUTS = {
    "[仅B服] 崩坏3扫码器 [限v8.3].lnk": "",
    "[仅B服] 一键登录崩坏3 [限v8.3].lnk": "--auto-login",
}
RESOURCES = [
    ("templates", DIST_DIR / "templates"),
    ("Pictures_to_Match", DIST_DIR / "Pictures_to_Match"),
    (ICON_FILE, DIST_DIR / ICON_FILE),
]
VENV_PYTHON = Path("venv") / "Scripts" / "python.exe"

# ------------------ 编译函数 ------------------
def build():
    print("[*] 检查 PyInstaller 是否已安装...")
    try:
        subprocess.run([str(VENV_PYTHON), "-m", "PyInstaller", "--version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("[!] 未检测到 PyInstaller，正在安装...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "pyinstaller"], check=True)

    print("[*] 确保 pycryptodome 存在...")
    try:
        subprocess.run([str(VENV_PYTHON), "-c", "import Crypto"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("[!] 缺少 pycryptodome，正在安装...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "pycryptodome"], check=True)

    print("[*] 开始编译...")
    cmd = [
        str(VENV_PYTHON),
        "-m", "PyInstaller",
        ENTRY_SCRIPT,
        "--onedir",
        f"--icon={ICON_FILE}",
        "--noconfirm",
        "--clean",
        f"--paths=venv/Lib/site-packages",
        f"--paths=venv/Lib/site-packages/PySide6/Qt/plugins",
        f"--paths=venv/Lib/site-packages/PySide6/Qt/qml",
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("[!] 编译失败：")
        print(e)
        print("[!] 请尝试手动运行以下命令调试：")
        print(" ".join(cmd))
        sys.exit(1)

    print("[*] 备份资源文件...")
    for src, dst in RESOURCES:
        src_path = Path(src)
        dst_path = Path(dst)
        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
        elif src_path.exists():
            shutil.copy2(src_path, dst_path)
        else:
            print(f"[!] 警告：资源 {src_path} 不存在，跳过。")

    print("[*] 创建快捷方式...")
    for name, arg in SHORTCUTS.items():
        create_shortcut(name, arg)

    print("[\u2714] 编译和部署完成！")

# ------------------ 快捷方式函数 ------------------
def create_shortcut(name, args):
    desktop = Path(".")
    target = DIST_DIR / f"{Path(ENTRY_SCRIPT).stem}.exe"
    shortcut_path = desktop / name

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.TargetPath = str(target.resolve())
    shortcut.WorkingDirectory = str(DIST_DIR.resolve())
    shortcut.Arguments = args
    shortcut.IconLocation = str((DIST_DIR / ICON_FILE).resolve())
    shortcut.save()

# ------------------ 主入口 ------------------
if __name__ == "__main__":
    build()
