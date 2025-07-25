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

# 开关配置
USE_ONEFILE = False  # True=单文件，False=多文件

def main():
    os.environ["PYTHONUTF8"] = "1"
    script_dir = Path(__file__).parent.resolve()
    print(f"脚本目录: {script_dir}")
    
    # 设置虚拟环境路径
    venv_dir = script_dir / "venv"
    activate_script = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "activate"
    
    if not activate_script.exists():
        sys.exit(f"错误：未找到虚拟环境！\n请确保在脚本目录下创建了venv环境: {venv_dir}")
    
    # 配置环境
    if sys.platform == "win32":
        os.environ["PATH"] = f"{venv_dir / 'Scripts'};{os.environ['PATH']}"
    clean_environment(venv_dir)
    
    # 清理缓存
    for cache_dir in ["__pycache__", "build", "dist"]:
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    # 安装依赖
    install_dependencies(script_dir)
    
    # 构建路径
    output_dir = script_dir / "dist"
    exe_name = "BBH3ScanLaunch.exe"
    app_dir = output_dir if USE_ONEFILE else output_dir / "BBH3ScanLaunch"
    
    # 执行PyInstaller构建
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        build_dir = script_dir / "build_pyinstaller"
        shutil.rmtree(build_dir, ignore_errors=True)
        build_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(build_dir)
        
        run_pyinstaller(script_dir, venv_dir, output_dir, tmpdir)
    
    os.chdir(script_dir)
    
    # 复制资源文件
    copy_resources(script_dir, app_dir)
    
    # 创建快捷方式
    if sys.platform == "win32":
        create_windows_shortcuts(app_dir, exe_name)
    
    # 创建压缩包
    create_clean_package(output_dir)
    
    print("\n============= 构建成功 =============")
    print(f"程序目录: {app_dir}")
    print(f"资源目录: {app_dir / 'Pictures_to_Match'} 和 {app_dir / 'templates'}")
    print(f"压缩包位置: {output_dir.parent / 'BBH3ScanLaunch_v8.3.zip'}")
    print("===================================")

def clean_environment(venv_dir):
    """屏蔽除虚拟环境外的所有环境变量"""
    print("\n===== 清理环境变量 =====")
    keep_envs = {
        "PATH": str(venv_dir / "Scripts") + os.pathsep + str(venv_dir / "bin"),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "PYTHONUTF8": "1",
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "HOME": os.environ.get("HOME", "")
    }
    
    if sys.platform == "win32":
        sys_paths = [os.environ.get(p, "") for p in ["SystemRoot", "SystemRoot/System32", "SystemRoot/SysWOW64"]]
        keep_envs["PATH"] = os.pathsep.join(filter(None, [
            str(venv_dir / "Scripts"), 
            *sys_paths, 
            os.environ.get("PATH", "")
        ]))
    
    os.environ.clear()
    os.environ.update({k: v for k, v in keep_envs.items() if v})
    
    print("当前环境变量:")
    for key, value in os.environ.items():
        print(f"{key}: {value}")

def install_dependencies(script_dir):
    """安装依赖"""
    print("\n===== 安装依赖 =====")
    req_file = script_dir / "requirements.txt"
    if req_file.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], check=True)
    else:
        print(f"未找到 requirements.txt 文件，跳过依赖安装")

def run_pyinstaller(script_dir, venv_dir, output_dir, tmpdir):
    """执行PyInstaller构建命令"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=BBH3ScanLaunch",
        "--workpath", str(script_dir / "build"),
        "--distpath", str(output_dir),
        "--specpath", tmpdir,
        "--noconsole",
        "--uac-admin",
        "-i", str(script_dir / "BHimage.ico"),
        "--exclude-module", "PyQt5",
        "--exclude-module", "PyQt6", 
        "--add-binary", f"{venv_dir / 'Lib' / 'site-packages' / 'pyzbar' / 'libiconv.dll'};.",
        "--add-binary", f"{venv_dir / 'Lib' / 'site-packages' / 'pyzbar' / 'libzbar-64.dll'};.",
        "--add-data", f"{script_dir / 'templates'};templates",
        "--add-data", f"{script_dir / 'Pictures_to_Match'};Pictures_to_Match",
        str(script_dir / "main.py")
    ]
    
    if USE_ONEFILE:
        cmd.insert(4, "--onefile")
    
    print("\n运行 PyInstaller 命令...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

def copy_resources(script_dir, app_dir):
    """复制所有资源文件"""
    resources = [
        ("templates", "目录"),
        ("Pictures_to_Match", "目录"),
        ("BHimage.ico", "文件"),
        ("oa_token.json", "文件")
    ]
    
    for src_path, res_type in resources:
        src = script_dir / src_path
        dst = app_dir / src_path
        
        if not src.exists():
            print(f"警告：找不到资源: {src_path}")
            continue
            
        print(f"正在复制资源: {src_path}")
        if res_type == "目录":
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

def create_windows_shortcuts(app_dir, exe_name):
    """创建Windows快捷方式"""
    if not WIN_SHORTCUT_AVAILABLE:
        print("警告：未安装 pywin32，跳过创建快捷方式")
        return

    target_exe = app_dir / exe_name
    icon_file = app_dir / "BHimage.ico"
    shortcuts = [
        ("[仅B服] 崩坏3扫码器.lnk", ""),
        ("[仅B服] 一键登陆崩坏3.lnk", "--auto-login")
    ]

    shell = Dispatch('WScript.Shell')
    for name, args in shortcuts:
        shortcut = shell.CreateShortcut(str(app_dir.parent / name))
        shortcut.TargetPath = str(target_exe)
        shortcut.Arguments = args
        if icon_file.exists():
            shortcut.IconLocation = str(icon_file)
        shortcut.WorkingDirectory = str(app_dir)
        shortcut.save()
    
    print(f"已创建 {len(shortcuts)} 个快捷方式")

def create_clean_package(output_dir):
    """创建压缩包"""
    zip_file = output_dir.parent / "BBH3ScanLaunch v1.0.zip"
    zip_file.unlink(missing_ok=True)
    
    print(f"正在创建压缩包: {zip_file}")
    shutil.make_archive(str(zip_file.with_suffix('')), 'zip', output_dir)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)