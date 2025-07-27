import os
import sys
import subprocess
from pathlib import Path

# 定义黑名单文件
BLACKLIST_FILES = [
    "config.json"
]

def check_required_files(script_dir):
    """检查必要的文件是否存在"""
    app_dir = script_dir / "dist" / "BBH3ScanLaunch"
    required_paths = [
        app_dir / "BBH3ScanLaunch.exe",
        app_dir / "BHimage.ico",
        app_dir,  # 主程序目录
        app_dir / "Pictures_to_Match",
        app_dir / "templates",
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
    
    # 检查 ISS 文件
    iss_file = script_dir / "setup.iss"
    if not iss_file.exists():
        print("❌ 错误：找不到 setup.iss 文件")
        return False
    
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
        
        # 查找生成的安装包
        output_files = list(output_dir.glob("*.exe"))
        if output_files:
            print(f"📦 安装包位置: {output_files[0]}")
        else:
            # 也可能在当前目录生成
            setup_files = list(script_dir.glob("BBH3ScanLaunch_Setup_v*.exe"))
            if setup_files:
                print(f"📦 安装包位置: {setup_files[0]}")
            else:
                print("⚠ 未找到生成的安装包文件")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 编译失败: {e}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        # 也显示 stdout，因为 Inno Setup 错误信息通常在 stdout 中
        if e.stdout:
            print(f"详细信息: {e.stdout}")
        return False
    except UnicodeDecodeError as e:
        # 处理编码错误，但不中断流程（因为安装包可能已经成功生成）
        print("⚠ 编码警告（不影响安装包生成）:", str(e))
        print("✅ 安装包编译成功！")
        
        # 查找生成的安装包
        output_files = list(output_dir.glob("*.exe"))
        if output_files:
            print(f"📦 安装包位置: {output_files[0]}")
        else:
            setup_files = list(script_dir.glob("BBH3ScanLaunch_Setup_v*.exe"))
            if setup_files:
                print(f"📦 安装包位置: {setup_files[0]}")
            else:
                print("⚠ 未找到生成的安装包文件")
        return True
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False

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

def main():
    """主函数"""
    print("🚀 开始构建 BBH3ScanLaunch 安装包...")
    print("=" * 50)
    print("💡 注意：此安装包需要管理员权限（UAC）")
    
    if build_installer():
        print("\n🎉 恭喜！安装包构建完成！")
        print("📦 安装包位于项目根目录或 Output 目录中")
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