import os
import sys
import subprocess
import shutil
import json
import zipfile
from datetime import datetime
from pathlib import Path

# 导入版本管理（调整为相对导入）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(
    0, str(Path(__file__).parent.parent / "src" / "bbh3_scan_launch" / "utils")
)
from bbh3_scan_launch.dependency_container import get_version_manager

version_manager = get_version_manager()

version = version_manager.get_version_info("current")

# 定义黑名单文件（移除 config.json，因为不再复制）
BLACKLIST_FILES = []


def generate_iss_file(project_root, current_version):
    """动态生成 setup.iss 文件"""
    print("正在生成安装脚本...")

    # 计算相对路径
    dist_path = project_root / "dist" / "BBH3ScanLaunch"
    icon_path = dist_path / "BHimage.ico"

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

    # 格式化版本号和路径
    iss_content = iss_content_template.format(
        version=current_version,
        icon_path=str(icon_path).replace("\\", "\\\\"),
        dist_path=str(dist_path).replace("\\", "\\\\"),
    )

    iss_file = project_root / "scripts" / "setup.iss"
    with open(iss_file, "w", encoding="utf-8") as f:
        f.write(iss_content)
    return iss_file


def check_required_files(project_root):
    """检查必要的文件是否存在"""
    app_dir = project_root / "dist" / "BBH3ScanLaunch"
    required_paths = [
        app_dir / "BBH3ScanLaunch.exe",
        app_dir / "BHimage.ico",
        app_dir,
        app_dir / "resources" / "pictures_to_match",
        app_dir / "resources" / "templates",
        app_dir / "updates",
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


def generate_version_info(project_root, setup_filename, current_version):
    """生成版本信息JSON - 只更新指定字段"""
    release_date = datetime.now().strftime("%Y-%m-%d")
    setup_path = project_root / setup_filename

    size = "0MB"
    if setup_path.exists():
        size = format_file_size(setup_path.stat().st_size)

    # 构建新的app_info数据
    new_app_info = {
        "version": current_version,
        "release_date": release_date,
        "size": size,
    }

    updates_dir = project_root / "updates"
    updates_dir.mkdir(exist_ok=True)
    version_file = updates_dir / "version.json"

    # 如果version.json存在，读取现有内容并更新app_info部分
    existing_data = {}
    if version_file.exists():
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"警告：读取现有version.json失败，将创建新文件: {e}")
            existing_data = {}

    # 更新app_info部分，保持其他字段不变
    if "app_info" in existing_data:
        # 保留原有的app_info中除指定字段外的其他字段
        for key, value in new_app_info.items():
            existing_data["app_info"][key] = value
    else:
        # 如果没有app_info，创建新的
        existing_data["app_info"] = new_app_info

    # 写入更新后的数据
    try:
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"版本信息已更新到: {version_file}")
    except Exception as e:
        print(f"错误：写入version.json失败: {e}")

    return existing_data


def move_output_to_app(project_root):
    """将Output文件夹中的文件移动到项目根目录"""
    output_dir = project_root / "scripts" / "Output"

    if not output_dir.exists():
        print("警告：Output目录不存在")
        return None

    setup_files = []

    for item in output_dir.iterdir():
        if item.is_file():
            dest = project_root / item.name
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


def find_inno_compiler():
    """查找 Inno Setup 编译器"""
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


def build_installer():
    """构建安装包"""
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent.resolve()
    print(f"脚本目录: {script_dir}")
    print(f"项目根目录: {project_root}")

    if not check_required_files(project_root):
        print("错误：缺少必要文件")
        return False

    # 获取当前版本号
    current_version = version
    print(f"当前版本: {current_version}")

    app_dir = project_root / "dist" / "BBH3ScanLaunch"

    inno_compiler = find_inno_compiler()
    if not inno_compiler:
        print("错误：未找到 Inno Setup 编译器")
        return False
    print(f"找到编译器: {inno_compiler}")

    iss_file = generate_iss_file(project_root, current_version)

    try:
        output_dir = project_root / "scripts" / "Output"
        output_dir.mkdir(exist_ok=True)

        print("正在编译安装包...")
        result = subprocess.run(
            [str(inno_compiler), str(iss_file)],
            check=True,
            capture_output=True,
            text=True,
            cwd=project_root / "scripts",
            encoding="utf-8",
        )
        print("编译完成")

        try:
            iss_file.unlink()
            print("临时ISS文件已删除")
        except Exception as e:
            print(f"警告：删除临时ISS文件失败: {e}")

        setup_filename = move_output_to_app(project_root)
        print(f"安装包文件名: {setup_filename}")

        if setup_filename:
            # 创建压缩包
            zip_file = project_root / f"BBH3ScanLaunch_Setup_v{current_version}.zip"
            zip_file.unlink(missing_ok=True)
            setup_path = project_root / setup_filename
            with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(setup_path, setup_filename)
            print(f"压缩包已创建: {zip_file}")

            version_info = generate_version_info(
                project_root, setup_filename, current_version
            )
            if "app_info" in version_info:
                print(f"安装包版本: {version_info['app_info']['version']}")
                print(f"安装包大小: {version_info['app_info']['size']}")
            else:
                print("版本信息生成完成")

            # 自动更新 version.json 的 download_url 字段（兼容所有 BBH3ScanLaunch_Setup*.zip 文件名）
            import re

            version_file = project_root / "updates" / "version.json"
            if version_file.exists():
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                zip_name = f"BBH3ScanLaunch_Setup_v{current_version}.zip"
                pattern = re.compile(r"BBH3ScanLaunch_Setup[^/]*?\.zip")
                version_path_pattern = re.compile(r"/download/[^/]+/")
                for source in ["gitee", "github"]:
                    if (
                        "sources" in data
                        and "download_url" in data["sources"]
                        and source in data["sources"]["download_url"]
                    ):
                        old_url = data["sources"]["download_url"][source]
                        # 替换文件名部分
                        new_url = pattern.sub(zip_name, old_url)
                        # 将 /download/ 后面的版本路径替换为新版本
                        new_url = version_path_pattern.sub(
                            f"/download/v{current_version}/", new_url
                        )
                        data["sources"]["download_url"][source] = new_url
                with open(version_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                print(
                    f"version.json download_url 已自动更新为: {zip_name}，版本路径已更新为 v{current_version}"
                )

        return True

    except subprocess.CalledProcessError as e:
        print(f"编译失败: {e.stderr if e.stderr else e.stdout}")
        return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        import traceback

        traceback.print_exc()
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
