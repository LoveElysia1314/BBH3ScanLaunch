import os
import sys
import subprocess
import shutil
import json
from datetime import datetime
from pathlib import Path
from version_utils import version_manager

version = version_manager.CURRENT_VERSION

# 定义黑名单文件
BLACKLIST_FILES = [
    "config.json"
]

def generate_iss_file(script_dir, version):
    """动态生成 setup.iss 文件"""
    print("正在生成安装脚本...")
    
    # 使用普通字符串，然后通过替换来避免转义警告
    iss_content_template = """; BBH3ScanLaunch 安装包脚本
#define MyAppName "BBH3ScanLaunch"
#define MyAppVersion "{version}"
#define MyAppExeName "BBH3ScanLaunch.exe"

[Setup]
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{#MyAppName}} {{#MyAppVersion}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
VersionInfoVersion={version}
VersionInfoCompany=BBH3ScanLaunch
VersionInfoDescription=BBH3ScanLaunch Installer
VersionInfoTextVersion={version}
OutputBaseFilename=BBH3ScanLaunch_Setup_v{{#MyAppVersion}}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=dist\\BBH3ScanLaunch\\BHimage.ico
AppPublisher=BBH3ScanLaunch
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64

[Files]
Source: "dist\\BBH3ScanLaunch\\*"; Excludes: "config.json"; DestDir: "{{app}}\\BBH3ScanLaunch"; Flags: ignoreversion recursesubdirs createallsubdirs

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
    
    # 格式化版本号
    iss_content = iss_content_template.format(version=version)
    
    iss_file = script_dir / "setup.iss"
    with open(iss_file, 'w', encoding='utf-8') as f:
        f.write(iss_content)
    return iss_file

def check_required_files(script_dir):
    """检查必要的文件是否存在"""
    app_dir = script_dir / "dist" / "BBH3ScanLaunch"
    required_paths = [
        app_dir / "BBH3ScanLaunch.exe",
        app_dir / "BHimage.ico",
        app_dir,
        app_dir / "Pictures_to_Match",
        app_dir / "templates",
    ]
    
    missing_files = []
    for path in required_paths:
        if not path.exists():
            missing_files.append(path)
    
    return len(missing_files) == 0

def check_blacklist_files(app_dir):
    """检查黑名单文件"""
    for blacklist_file in BLACKLIST_FILES:
        file_path = app_dir / blacklist_file
        if file_path.exists():
            return True
    return False

def format_file_size(size_in_bytes):
    """格式化文件大小为MB字符串"""
    size_in_mb = size_in_bytes / (1024 * 1024)
    return f"{round(size_in_mb)}MB"

def generate_version_info(script_dir, setup_filename):
    """生成版本信息JSON"""
    release_date = datetime.now().strftime("%Y-%m-%d")
    setup_path = script_dir / "app" / setup_filename

    size = "0MB"
    if setup_path.exists():
        size = format_file_size(setup_path.stat().st_size)

    download_url = f"https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@main/app/{setup_filename}"
    changelog_url = "https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@main/updates/changelog.txt"

    version_info = {
        "version": version,
        "release_date": release_date,
        "download_url": download_url,
        "changelog": changelog_url,
        "size": size
    }

    updates_dir = script_dir / "updates"
    updates_dir.mkdir(exist_ok=True)

    version_file = updates_dir / "version.json"
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(version_info, f, indent=4, ensure_ascii=False)

    return version_info

def move_output_to_app(script_dir):
    """将Output文件夹中的文件移动到app文件夹"""
    output_dir = script_dir / "Output"
    app_dir = script_dir / "app"

    if not output_dir.exists():
        return None

    app_dir.mkdir(exist_ok=True)
    setup_files = []

    for item in output_dir.iterdir():
        if item.is_file():
            dest = app_dir / item.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(item), str(dest))
            setup_files.append(dest)

    try:
        shutil.rmtree(output_dir)
    except Exception:
        pass

    for file in setup_files:
        if file.name.startswith("BBH3ScanLaunch_Setup_v"):
            return file.name
    return None

def find_inno_compiler():
    """查找 Inno Setup 编译器"""
    possible_paths = [
        "D:/Program Files (x86)/Inno Setup 6/ISCC.exe",
        "C:/Program Files (x86)/Inno Setup 6/ISCC.exe",
        "C:/Program Files/Inno Setup 6/ISCC.exe",
        "D:/Program Files/Inno Setup 6/ISCC.exe"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return Path(path)

    try:
        result = subprocess.run(["where", "ISCC.exe"], capture_output=True, text=True, shell=True)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().split('\n')[0])
    except:
        pass

    return None

def build_installer():
    """构建安装包"""
    script_dir = Path(__file__).parent.resolve()

    if not check_required_files(script_dir):
        print("错误：缺少必要文件")
        return False

    app_dir = script_dir / "dist" / "BBH3ScanLaunch"

    inno_compiler = find_inno_compiler()
    if not inno_compiler:
        print("错误：未找到 Inno Setup 编译器")
        return False

    iss_file = generate_iss_file(script_dir, version)

    try:
        output_dir = script_dir / "Output"
        output_dir.mkdir(exist_ok=True)

        print("正在编译安装包...")
        result = subprocess.run(
            [str(inno_compiler), str(iss_file)],
            check=True,
            capture_output=True,
            text=True,
            cwd=script_dir,
            encoding='utf-8'
        )

        try:
            iss_file.unlink()
        except Exception:
            pass

        setup_filename = move_output_to_app(script_dir)

        if setup_filename:
            version_info = generate_version_info(script_dir, setup_filename)
            print(f"安装包版本: {version_info['version']}")
            print(f"安装包大小: {version_info['size']}")

        return True

    except subprocess.CalledProcessError as e:
        print(f"编译失败: {e.stderr if e.stderr else e.stdout}")
        return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return False

def main():
    print("开始构建安装包...")
    if build_installer():
        print("安装包构建成功")
    else:
        print("安装包构建失败")
        sys.exit(1)

if __name__ == "__main__":
    main()