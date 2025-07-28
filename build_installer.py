import os
import sys
import subprocess
import shutil
import re
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
    iss_content = f"""; BBH3ScanLaunch 安装包脚本 (动态生成)
#define MyAppName "BBH3ScanLaunch"
#define MyAppVersion "{version}"
#define MyAppExeName "BBH3ScanLaunch.exe"

[Setup]
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{autopf}}\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
OutputBaseFilename=BBH3ScanLaunch_Setup_v{{#MyAppVersion}}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=dist\BBH3ScanLaunch\BHimage.ico
AppPublisher=BBH3ScanLaunch
AppPublisherURL=https://github.com/your-repo
AppSupportURL=https://github.com/your-repo
AppUpdatesURL=https://github.com/your-repo

[Files]
Source: "dist\BBH3ScanLaunch\*"; Excludes: "config.json"; DestDir: "{{app}}\BBH3ScanLaunch"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单快捷方式（带UAC）
Name: "{{group}}\[仅B服] 崩坏3扫码器"; Filename: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; IconFilename: "{{app}}\BBH3ScanLaunch\BHimage.ico"
Name: "{{group}}\[仅B服] 一键登陆崩坏3"; Filename: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; Parameters: "--auto-login"; IconFilename: "{{app}}\BBH3ScanLaunch\BHimage.ico"

; 桌面快捷方式（带UAC） - 直接创建不询问
Name: "{{autodesktop}}\[仅B服] 崩坏3扫码器"; Filename: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; IconFilename: "{{app}}\BBH3ScanLaunch\BHimage.ico"
Name: "{{autodesktop}}\[仅B服] 一键登陆崩坏3"; Filename: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; Parameters: "--auto-login"; IconFilename: "{{app}}\BBH3ScanLaunch\BHimage.ico"

[Run]
Filename: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#MyAppName}}}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Registry]
; 为EXE添加UAC清单（如果程序本身没有）
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; \
    ValueType: String; ValueName: "{{app}}\BBH3ScanLaunch\{{#MyAppExeName}}"; ValueData: "RUNASADMIN"; Flags: uninsdeletevalue
"""

    iss_file = script_dir / "setup.iss"
    with open(iss_file, 'w', encoding='utf-8') as f:
        f.write(iss_content)
    print(f"✅ 已动态生成 setup.iss 文件，版本号: {version}")
    return iss_file

def check_required_files(script_dir):
    """检查必要的文件是否存在"""
    app_dir = script_dir / "dist" / "BBH3ScanLaunch"
    required_paths = [
        app_dir / "BBH3ScanLaunch.exe",
        app_dir / "BHimage.ico",
        app_dir,  # 主程序目录
        app_dir / "Pictures_to_Match",
        app_dir / "templates",
        app_dir / "updates",
    ]
    
    print("检查必要文件...")
    missing_files = []
    for path in required_paths:
        if not path.exists():
            print(f"❌ 错误：找不到必要路径 {path}")
            missing_files.append(path)
        else:
            if path.is_file():
                print(f"✓ 找到文件: {path.relative_to(script_dir)}")
            else:
                print(f"✓ 找到目录: {path.relative_to(script_dir)}")
    
    return len(missing_files) == 0

def check_blacklist_files(app_dir):
    """检查黑名单文件是否存在，如果存在则给出警告"""
    print("\n检查黑名单文件...")
    blacklist_found = []
    
    for blacklist_file in BLACKLIST_FILES:
        file_path = app_dir / blacklist_file
        if file_path.exists():
            print(f"⚠ 警告：黑名单文件存在 {file_path.relative_to(app_dir)}")
            blacklist_found.append(file_path)
    
    if blacklist_found:
        print("💡 这些文件将通过 Inno Setup 的 Excludes 选项自动排除")
        return True
    else:
        print("✓ 未发现黑名单文件")
        return False

def format_file_size(size_in_bytes):
    """格式化文件大小为MB字符串"""
    size_in_mb = size_in_bytes / (1024 * 1024)
    return f"{round(size_in_mb)}MB"

def generate_version_info(script_dir, setup_filename):
    """生成版本信息JSON"""
    
    # 当前日期
    release_date = datetime.now().strftime("%Y-%m-%d")
    
    # 文件大小
    setup_path = script_dir / "app" / setup_filename
    if setup_path.exists():
        size = format_file_size(setup_path.stat().st_size)
    else:
        size = "0MB"
    
    # 构建下载URL
    download_url = f"https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@latest/app/{setup_filename}"
    changelog_url = "https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@latest/updates/changelog.txt"
    
    # 创建版本信息字典
    version_info = {
        "version": version,
        "release_date": release_date,
        "download_url": download_url,
        "changelog": changelog_url,
        "size": size
    }
    
    # 创建updates目录并写入文件
    updates_dir = script_dir / "updates"
    updates_dir.mkdir(exist_ok=True)
    
    version_file = updates_dir / "version.json"
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(version_info, f, indent=4, ensure_ascii=False)
    
    print(f"✅ 已生成版本信息文件: {version_file}")
    print(json.dumps(version_info, indent=4, ensure_ascii=False))

def rename_output_to_app(script_dir):
    """将Output文件夹重命名为app（覆盖已有文件夹）"""
    output_dir = script_dir / "Output"
    app_dir = script_dir / "app"
    
    if not output_dir.exists():
        print("⚠ 警告：Output目录不存在，跳过重命名")
        return None
    
    # 删除现有的app目录（如果存在）
    if app_dir.exists():
        shutil.rmtree(app_dir)
        print("♻ 已删除现有的app目录")
    
    # 重命名Output为app
    output_dir.rename(app_dir)
    print(f"✅ 已将Output目录重命名为app")
    
    # 返回安装包文件名
    setup_files = list(app_dir.glob("BBH3ScanLaunch_Setup_v*.exe"))
    if setup_files:
        return setup_files[0].name
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
    
    # 尝试在 PATH 中查找
    try:
        result = subprocess.run(["where", "ISCC.exe"], capture_output=True, text=True, shell=True, encoding='utf-8')
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().split('\n')[0])
    except:
        pass
    
    return None

def build_installer():
    """构建安装包"""
    script_dir = Path(__file__).parent.resolve()
    
    # 检查必要的文件是否存在
    if not check_required_files(script_dir):
        return False
    
    app_dir = script_dir / "dist" / "BBH3ScanLaunch"
    
    # 检查 _internal 目录（如果存在）
    internal_dir = app_dir / "_internal"
    if internal_dir.exists():
        print(f"✓ 找到目录: {internal_dir.relative_to(script_dir)}")
    
    # 检查黑名单文件
    check_blacklist_files(app_dir)
    
    # 检查 Inno Setup 编译器
    inno_compiler = find_inno_compiler()
    if not inno_compiler:
        print("❌ 错误：未找到 Inno Setup 编译器")
        print("💡 请先安装 Inno Setup 6 或更高版本")
        return False
    
    # 动态生成 ISS 文件
    iss_file = generate_iss_file(script_dir, version)
    
    print(f"\n🚀 正在编译安装包...")
    try:
        # 确保输出目录存在
        output_dir = script_dir / "Output"
        output_dir.mkdir(exist_ok=True)
        
        # 使用正确的编码处理 subprocess 输出
        result = subprocess.run([
            str(inno_compiler),
            str(iss_file)
        ], check=True, capture_output=True, text=True, cwd=script_dir, encoding='utf-8')
        
        print("✅ 安装包编译成功！")
        
        # 编译完成后删除临时 ISS 文件
        try:
            iss_file.unlink()
            print("♻ 已删除临时 setup.iss 文件")
        except Exception as e:
            print(f"⚠ 警告：无法删除临时 setup.iss 文件: {e}")
        
        # 重命名Output为app并获取安装包文件名
        setup_filename = rename_output_to_app(script_dir)
        
        if setup_filename:
            # 生成版本信息文件
            generate_version_info(script_dir, setup_filename)
        else:
            print("⚠ 警告：未找到安装包文件，跳过生成版本信息")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 编译失败: {e}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        if e.stdout:
            print(f"详细信息: {e.stdout}")
        return False
    except UnicodeDecodeError as e:
        print("⚠ 编码警告（不影响安装包生成）:", str(e))
        print("✅ 安装包编译成功！")
        
        # 重命名Output为app并获取安装包文件名
        setup_filename = rename_output_to_app(script_dir)
        
        if setup_filename:
            # 生成版本信息文件
            generate_version_info(script_dir, setup_filename)
        else:
            print("⚠ 警告：未找到安装包文件，跳过生成版本信息")
            
        return True
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始构建 BBH3ScanLaunch 安装包...")
    print("=" * 50)
    print("💡 注意：此安装包需要管理员权限（UAC）")
    
    if build_installer():
        print("\n🎉 恭喜！安装包构建完成！")
        print("📦 安装包位于 app 目录中")
        print("📄 版本信息已保存到 updates/version.json")
        print("🛡️  安装时将要求管理员权限（UAC）")
        print("📋 安装后将自动创建以下快捷方式：")
        print("   - 开始菜单: [仅B服] 崩坏3扫码器")
        print("   - 开始菜单: [仅B服] 一键登陆崩坏3 (带--auto-login参数)")
        print("   - 桌面: [仅B服] 崩坏3扫码器")
        print("   - 桌面: [仅B服] 一键登陆崩坏3 (带--auto-login参数)")
    else:
        print("\n❌ 安装包构建失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()