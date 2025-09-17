import os
import sys
import subprocess
import shutil
import tempfile
import json
import zipfile
from pathlib import Path
from datetime import datetime
import site

# 禁用用户站点包
site.ENABLE_USER_SITE = False

# 添加项目路径到系统路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "src" / "bbh3_scan_launch" / "utils"))

from bbh3_scan_launch.dependency_container import get_version_manager

# 配置常量
USE_ONEFILE = False  # True=单文件，False=多文件
BLACKLIST_FILES = []
version_manager = get_version_manager()
VERSION = version_manager.get_version_info("current")


class BuildConfig:
    """构建配置类"""
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.resolve()
        self.script_dir = Path(__file__).parent.resolve()
        self.venv_dir = self.project_root / "venv"
        self.output_dir = self.project_root / "dist"
        self.exe_name = "BBH3ScanLaunch.exe"
        self.app_dir = self.output_dir if USE_ONEFILE else self.output_dir / "BBH3ScanLaunch"
        self.build_dir = self.project_root / "build_pyinstaller"
        
        # 设置虚拟环境路径
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        self.venv_bin_dir = self.venv_dir / bin_dir
        self.python_exe = self.venv_bin_dir / "python"
        self.pip_exe = self.venv_bin_dir / "pip"
        
        if sys.platform == "win32":
            self.python_exe = self.python_exe.with_suffix(".exe")
            self.pip_exe = self.pip_exe.with_suffix(".exe")


def main():
    """主函数"""
    os.environ["PYTHONUTF8"] = "1"
    config = BuildConfig()
    
    # 设置虚拟环境
    setup_virtual_environment(config)
    
    # 安装依赖
    install_dependencies(config)
    
    # 清理缓存
    clean_build_cache(config)
    
    # 执行PyInstaller构建
    run_pyinstaller_build(config)
    
    # 复制资源文件
    copy_resources(config)
    
    # 创建快捷方式 (Windows)
    if sys.platform == "win32":
        create_windows_shortcuts(config)
    
    # 创建安装文件
    build_installer(config)
    
    # 清理临时文件夹
    cleanup_temp_directories(config)
    
    print(f"\n构建成功 v{VERSION}")
    print(f"程序目录: {config.app_dir}")


def setup_virtual_environment(config):
    """设置虚拟环境"""
    activate_script = config.venv_bin_dir / "activate"
    
    # 检查并创建虚拟环境（如果不存在）
    if not activate_script.exists():
        print(f"创建虚拟环境: {config.venv_dir}")
        subprocess.run([sys.executable, "-m", "venv", str(config.venv_dir)], check=True)
    
    # 配置环境
    clean_environment(config)
    
    # 检查Python和Pip是否存在
    if not config.python_exe.exists():
        sys.exit(f"错误：未找到Python: {config.python_exe}")
    
    if not config.pip_exe.exists():
        sys.exit(f"错误：未找到Pip: {config.pip_exe}")


def clean_environment(config):
    """清理环境变量，只保留必要的"""
    keep_envs = {
        "PATH": str(config.venv_bin_dir),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "PYTHONUTF8": "1",
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    
    if sys.platform == "win32":
        sys_paths = [
            os.environ.get(p, "")
            for p in ["SystemRoot", "SystemRoot/System32", "SystemRoot/SysWOW64"]
            if p in os.environ
        ]
        keep_envs["PATH"] = os.pathsep.join(
            [str(config.venv_bin_dir)] + sys_paths + [os.environ.get("PATH", "")]
        )
    
    os.environ.clear()
    os.environ.update({k: v for k, v in keep_envs.items() if v})


def install_dependencies(config):
    """安装项目依赖"""
    print("更新pip...")
    subprocess.run([
        str(config.python_exe), "-m", "pip", "install", "--upgrade", "pip"
    ], check=True)
    
    print("安装依赖...")
    subprocess.run([
        str(config.pip_exe), "install", "-r", str(config.project_root / "requirements.txt")
    ], check=True)


def clean_build_cache(config):
    """清理构建缓存"""
    for cache_dir in [
        config.project_root / "__pycache__",
        config.project_root / "build",
        config.project_root / "dist",
    ]:
        shutil.rmtree(cache_dir, ignore_errors=True)


def run_pyinstaller_build(config):
    """执行PyInstaller构建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 准备构建目录
        shutil.rmtree(config.build_dir, ignore_errors=True)
        config.build_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建命令
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name=BBH3ScanLaunch",
            "--workpath", str(config.project_root / "build"),
            "--distpath", str(config.output_dir),
            "--specpath", tmpdir,
            "--paths", str(config.project_root / "src"),
            "--noconsole",
            "--uac-admin",
            "-i", str(config.project_root / "BHimage.ico"),
            "--exclude-module", "PyQt5",
            "--exclude-module", "PyQt6",
            "--hidden-import", "bbh3_scan_launch",
            "--hidden-import", "bbh3_scan_launch.main",
            "--add-binary", f"{config.venv_dir / 'Lib' / 'site-packages' / 'pyzbar' / 'libiconv.dll'};.",
            "--add-binary", f"{config.venv_dir / 'Lib' / 'site-packages' / 'pyzbar' / 'libzbar-64.dll'};.",
            "--add-data", f"{config.project_root / 'resources' / 'templates'};resources/templates",
            "--add-data", f"{config.project_root / 'resources' / 'pictures_to_match'};resources/pictures_to_match",
            str(config.project_root / "run.py"),
        ]
        
        if USE_ONEFILE:
            cmd.insert(4, "--onefile")
        
        # 执行构建
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=config.build_dir)
            if result.stderr:
                print("PyInstaller 警告:", result.stderr)
            print("PyInstaller 构建成功")
        except subprocess.CalledProcessError as e:
            print(f"PyInstaller 失败: {e.returncode}")
            print("输出:", e.stdout)
            print("错误:", e.stderr)
            raise


def copy_resources(config):
    """复制资源文件"""
    resource_pairs = [
        (config.project_root / "resources" / "templates", config.app_dir / "resources" / "templates"),
        (config.project_root / "resources" / "pictures_to_match", config.app_dir / "resources" / "pictures_to_match"),
        (config.project_root / "updates", config.app_dir / "updates"),
        (config.project_root / "BHimage.ico", config.app_dir / "BHimage.ico"),
    ]
    
    for src, dst in resource_pairs:
        if not src.exists():
            print(f"警告：找不到资源: {src}")
            continue
        
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def create_windows_shortcuts(config):
    """创建Windows快捷方式"""
    try:
        from win32com.client import Dispatch
    except ImportError:
        print("警告：未安装 pywin32，跳过创建快捷方式")
        return
    
    target_exe = config.app_dir / config.exe_name
    icon_file = config.app_dir / "BHimage.ico"
    shortcuts = [
        ("BBH3ScanLaunch.lnk", ""),
        ("AutoLoginBBH3.lnk", "--auto-login")
    ]
    
    shell = Dispatch("WScript.Shell")
    for name, args in shortcuts:
        shortcut = shell.CreateShortcut(str(config.output_dir.parent / name))
        shortcut.TargetPath = str(target_exe)
        shortcut.Arguments = args
        if icon_file.exists():
            shortcut.IconLocation = str(icon_file)
        shortcut.WorkingDirectory = str(config.app_dir)
        shortcut.save()
    
    print(f"创建 {len(shortcuts)} 个快捷方式")


def cleanup_temp_directories(config):
    """清理临时文件夹"""
    temp_dirs = [
        config.build_dir,  # build_pyinstaller
        config.project_root / "scripts" / "Output",  # Inno Setup输出目录
        config.project_root / "build",  # PyInstaller工作目录
    ]
    
    for temp_dir in temp_dirs:
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                print(f"已清理临时目录: {temp_dir}")
            except Exception as e:
                print(f"警告：清理临时目录失败 {temp_dir}: {e}")


def build_installer(config):
    """构建安装包"""
    if not check_required_files(config):
        print("错误：缺少必要文件")
        return False
    
    print(f"当前版本: {VERSION}")
    
    # 查找Inno Setup编译器
    inno_compiler = find_inno_compiler()
    if not inno_compiler:
        print("错误：未找到 Inno Setup 编译器")
        return False
    
    print(f"找到编译器: {inno_compiler}")
    
    # 生成ISS文件
    iss_file = generate_iss_file(config)
    
    try:
        # 创建输出目录
        output_dir = config.project_root / "scripts" / "Output"
        output_dir.mkdir(exist_ok=True)
        
        print("正在编译安装包...")
        result = subprocess.run(
            [str(inno_compiler), str(iss_file)],
            check=True,
            capture_output=True,
            text=True,
            cwd=config.project_root / "scripts",
            encoding="utf-8",
        )
        print("编译完成")
        
        # 清理临时文件
        try:
            iss_file.unlink()
            print("临时ISS文件已删除")
        except Exception as e:
            print(f"警告：删除临时ISS文件失败: {e}")
        
        # 移动输出文件
        setup_filename = move_output_to_app(config)
        if setup_filename:
            create_zip_package(config, setup_filename)
            update_version_info(config, setup_filename)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"编译失败: {e.stderr if e.stderr else e.stdout}")
        return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_required_files(config):
    """检查必要的文件是否存在"""
    required_paths = [
        config.app_dir / "BBH3ScanLaunch.exe",
        config.app_dir / "BHimage.ico",
        config.app_dir,
        config.app_dir / "resources" / "pictures_to_match",
        config.app_dir / "resources" / "templates",
        config.app_dir / "updates",
    ]
    
    missing_files = [path for path in required_paths if not path.exists()]
    
    if missing_files:
        print("缺少以下文件:")
        for path in missing_files:
            print(f"  - {path}")
        return False
    
    return True


def find_inno_compiler():
    """查找Inno Setup编译器"""
    possible_paths = [
        "D:/Program Files (x86)/Inno Setup 6/ISCC.exe",
        "C:/Program Files (x86)/Inno Setup 6/ISCC.exe",
        "C:/Program Files/Inno Setup 6/ISCC.exe",
        "D:/Program Files/Inno Setup 6/ISCC.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return Path(path)
    
    try:
        result = subprocess.run(
            ["where", "ISCC.exe"], capture_output=True, text=True, shell=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().split("\n")[0])
    except:
        pass
    
    return None


def generate_iss_file(config):
    """生成Inno Setup脚本文件"""
    print("正在生成安装脚本...")
    
    dist_path = config.project_root / "dist" / "BBH3ScanLaunch"
    icon_path = dist_path / "BHimage.ico"
    
    iss_content = f"""; BBH3ScanLaunch 安装包脚本
#define MyAppName "BBH3ScanLaunch"
#define MyAppVersion "{VERSION}"
#define MyAppExeName "BBH3ScanLaunch.exe"

[Setup]
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{#MyAppName}} {{#MyAppVersion}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
VersionInfoVersion={VERSION}
VersionInfoCompany=BBH3ScanLaunch
VersionInfoDescription=BBH3ScanLaunch Installer
VersionInfoTextVersion={VERSION}
OutputBaseFilename=BBH3ScanLaunch_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile={icon_path}
AppPublisher=BBH3ScanLaunch
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

[Files]
Source: "{dist_path}\\*"; DestDir: "{{app}}\\BBH3ScanLaunch"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\BBH3ScanLaunch"; Filename: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\BBH3ScanLaunch\\BHimage.ico"
Name: "{{group}}\\AutoLoginBBH3"; Filename: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; Parameters: "--auto-login"; IconFilename: "{{app}}\\BBH3ScanLaunch\\BHimage.ico"
Name: "{{autodesktop}}\\BBH3ScanLaunch"; Filename: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\BBH3ScanLaunch\\BHimage.ico"
Name: "{{autodesktop}}\\AutoLoginBBH3"; Filename: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; Parameters: "--auto-login"; IconFilename: "{{app}}\\BBH3ScanLaunch\\BHimage.ico"

[Run]
Filename: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#MyAppName}}}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Registry]
Root: HKLM; Subkey: "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers"; \\
    ValueType: String; ValueName: "{{app}}\\BBH3ScanLaunch\\{{#MyAppExeName}}"; ValueData: "RUNASADMIN"; Flags: uninsdeletevalue

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  appDataPath: string;
  userDataPath: string;
  choice: Integer;
begin
  case CurUninstallStep of
    usPostUninstall:
      begin
        appDataPath := ExpandConstant('{{localappdata}}');
        userDataPath := appDataPath + '\\\\BBH3ScanLaunch';
        if DirExists(userDataPath) then
        begin
          choice := MsgBox('是否删除用户配置数据？' #13#13 '路径: ' + userDataPath, 
            mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
          if choice = IDYES then
          begin
            if not DelTree(userDataPath, True, True, True) then
              MsgBox('无法完全删除用户配置数据，部分文件可能被占用。', mbError, MB_OK);
          end;
        end;
      end;
  end;
end;
"""
    
    iss_file = config.project_root / "scripts" / "setup.iss"
    with open(iss_file, "w", encoding="utf-8") as f:
        f.write(iss_content)
    
    return iss_file


def move_output_to_app(config):
    """移动输出文件到应用程序目录"""
    output_dir = config.project_root / "scripts" / "Output"
    
    if not output_dir.exists():
        print("警告：Output目录不存在")
        return None
    
    setup_files = []
    
    for item in output_dir.iterdir():
        if item.is_file():
            dest = config.project_root / item.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(item), str(dest))
            setup_files.append(dest)
    
    try:
        shutil.rmtree(output_dir)
    except Exception as e:
        print(f"警告：删除Output目录失败: {e}")
    
    for file in setup_files:
        if file.name == "BBH3ScanLaunch_Setup.exe":
            return file.name
    
    return None


def create_zip_package(config, setup_filename):
    """创建ZIP压缩包"""
    zip_file = config.project_root / f"BBH3ScanLaunch_Setup_v{VERSION}.zip"
    zip_file.unlink(missing_ok=True)
    
    setup_path = config.project_root / setup_filename
    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(setup_path, setup_filename)
    
    print(f"压缩包已创建: {zip_file}")


def update_version_info(config, setup_filename):
    """更新版本信息"""
    release_date = datetime.now().strftime("%Y-%m-%d")
    setup_path = config.project_root / setup_filename
    
    # 计算文件大小
    size = "0MB"
    if setup_path.exists():
        size_in_mb = setup_path.stat().st_size / (1024 * 1024)
        size = f"{round(size_in_mb)}MB"
    
    # 构建版本信息
    version_info = {
        "version": VERSION,
        "release_date": release_date,
        "size": size,
    }
    
    # 读取现有版本文件（如果存在）
    version_file = config.project_root / "updates" / "version.json"
    existing_data = {}
    
    if version_file.exists():
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"警告：读取现有version.json失败，将创建新文件: {e}")
    
    # 更新或创建app_info部分
    if "app_info" in existing_data:
        existing_data["app_info"].update(version_info)
    else:
        existing_data["app_info"] = version_info
    
    # 更新下载URL
    if "sources" in existing_data and "download_url" in existing_data["sources"]:
        import re
        zip_name = f"BBH3ScanLaunch_Setup_v{VERSION}.zip"
        pattern = re.compile(r"BBH3ScanLaunch_Setup[^/]*?\.zip")
        version_path_pattern = re.compile(r"/download/[^/]+/")
        
        for source in ["gitee", "github"]:
            if source in existing_data["sources"]["download_url"]:
                old_url = existing_data["sources"]["download_url"][source]
                # 替换文件名部分
                new_url = pattern.sub(zip_name, old_url)
                # 将/download/后面的版本路径替换为新版本
                new_url = version_path_pattern.sub(
                    f"/download/v{VERSION}/", new_url
                )
                existing_data["sources"]["download_url"][source] = new_url
    
    # 写入更新后的数据
    try:
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"版本信息已更新到: {version_file}")
    except Exception as e:
        print(f"错误：写入version.json失败: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        
        # 即使出错也要尝试清理临时文件夹
        try:
            config = BuildConfig()
            cleanup_temp_directories(config)
        except:
            pass
        
        sys.exit(1)