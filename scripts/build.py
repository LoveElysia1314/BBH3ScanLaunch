import argparse
import hashlib
import os
import sys
import subprocess
import shutil
import tempfile
import time
import json
import zipfile
from pathlib import Path
from datetime import datetime

# 添加项目路径到系统路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "src" / "bbh3_scan_launch" / "utils"))

from bbh3_scan_launch.utils.version_utils import VersionManager

# 配置常量
USE_ONEFILE = False  # True=单文件，False=多文件
BLACKLIST_FILES = []
PYINSTALLER_EXCLUDES = (
    "PyQt5",
    "PyQt6",
)
version_manager = VersionManager()
VERSION = version_manager.get_version_info("current")


class BuildConfig:
    """构建配置类"""

    def __init__(self, command_timeout=1800, project_root=None):
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).parent.parent.resolve()
        )
        self.script_dir = Path(__file__).parent.resolve()
        self.output_dir = self.project_root / "dist"
        self.exe_name = "BBH3ScanLaunch.exe"
        self.app_dir = (
            self.output_dir if USE_ONEFILE else self.output_dir / "BBH3ScanLaunch"
        )
        self.build_dir = self.project_root / "build_pyinstaller"
        self.requirements_file = self.project_root / "requirements.txt"
        self.build_venv_dir = self.project_root / ".build-venv"
        self.build_venv_bin_dir = self.build_venv_dir / (
            "Scripts" if sys.platform == "win32" else "bin"
        )
        self.bootstrap_python = Path(sys.executable)
        self.python_exe = self.build_venv_bin_dir / (
            "python.exe" if sys.platform == "win32" else "python"
        )
        self.dependency_stamp = self.build_venv_dir / ".requirements.sha256"
        self.python_stamp = self.build_venv_dir / ".python-version"
        self.pyinstaller_stamp = self.build_venv_dir / ".pyinstaller-inputs.sha256"
        self.command_timeout = command_timeout


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="构建 BBH3ScanLaunch")
    parser.add_argument(
        "--recreate-build-env",
        action="store_true",
        help="删除并重新创建专用 .build-venv",
    )
    parser.add_argument(
        "--refresh-deps",
        action="store_true",
        help="在现有 .build-venv 中强制重新安装依赖",
    )
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="仅构建 PyInstaller 产物，不调用 Inno Setup",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="忽略输入哈希缓存，强制重新执行 PyInstaller",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        metavar="SECONDS",
        help="单个外部命令的超时秒数，0 表示不限制（默认 1800）",
    )
    return parser.parse_args(argv)


def run_command(label, command, *, cwd=None, timeout=1800, env=None):
    """运行外部命令，继承当前终端输出并报告耗时。"""
    started_at = time.monotonic()
    command = [str(arg) for arg in command]
    print(f"\n[{label}] 开始", flush=True)
    print(
        f"[{label}] 命令: {subprocess.list2cmdline(command)}",
        flush=True,
    )
    try:
        subprocess.run(
            command,
            cwd=cwd,
            check=True,
            timeout=timeout or None,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started_at
        raise RuntimeError(f"{label} 超时（{elapsed:.1f}s，限制 {timeout}s）") from exc
    except subprocess.CalledProcessError as exc:
        elapsed = time.monotonic() - started_at
        raise RuntimeError(
            f"{label} 失败（退出码 {exc.returncode}，耗时 {elapsed:.1f}s）"
        ) from exc

    print(
        f"[{label}] 完成，耗时 {time.monotonic() - started_at:.1f}s",
        flush=True,
    )


def run_stage(label, action):
    """执行 Python 内部阶段并报告耗时。"""
    started_at = time.monotonic()
    print(f"\n[{label}] 开始", flush=True)
    result = action()
    print(
        f"[{label}] 完成，耗时 {time.monotonic() - started_at:.1f}s",
        flush=True,
    )
    return result


def main(argv=None):
    """主函数"""
    args = parse_args(argv)
    config = BuildConfig(command_timeout=args.timeout)

    run_stage(
        "准备构建环境",
        lambda: ensure_build_environment(
            config,
            recreate=args.recreate_build_env,
            refresh=args.refresh_deps,
        ),
    )

    run_stage(
        "PyInstaller 构建",
        lambda: build_or_reuse_pyinstaller(config, force=args.rebuild),
    )
    run_stage("复制资源", lambda: copy_resources(config))

    if sys.platform == "win32":
        run_stage("创建快捷方式", lambda: create_windows_shortcuts(config))

    if args.skip_installer:
        print("\n[安装包] 已按参数跳过 Inno Setup")
    elif not run_stage("Inno Setup 安装包", lambda: build_installer(config)):
        raise RuntimeError("Inno Setup 安装包构建失败")

    run_stage("清理临时目录", lambda: cleanup_temp_directories(config))

    print(f"\n构建成功 v{VERSION}")
    print(f"程序目录: {config.app_dir}")


def dependency_fingerprint(config):
    """根据 Python 版本和依赖文件计算构建环境指纹。"""
    digest = hashlib.sha256()
    digest.update(
        f"{sys.version_info.major}.{sys.version_info.minor}\n".encode("ascii")
    )
    digest.update(config.requirements_file.read_bytes())
    return digest.hexdigest()


def ensure_build_environment(config, *, recreate=False, refresh=False):
    """创建并按需更新可缓存的专用构建虚拟环境。"""
    expected_python_version = f"{sys.version_info.major}.{sys.version_info.minor}\n"
    recorded_python_version = (
        config.python_stamp.read_text(encoding="ascii")
        if config.python_stamp.exists()
        else ""
    )
    if (
        config.python_exe.exists()
        and recorded_python_version != expected_python_version
    ):
        print("系统 Python 小版本已变化，将重建构建环境")
        recreate = True

    if recreate and config.build_venv_dir.exists():
        shutil.rmtree(config.build_venv_dir)

    if not config.python_exe.exists():
        run_command(
            "创建构建虚拟环境",
            [
                config.bootstrap_python,
                "-m",
                "venv",
                config.build_venv_dir,
            ],
            timeout=config.command_timeout,
        )
        config.python_stamp.write_text(
            expected_python_version,
            encoding="ascii",
        )
        refresh = True

    expected_fingerprint = dependency_fingerprint(config)
    recorded_fingerprint = (
        config.dependency_stamp.read_text(encoding="ascii").strip()
        if config.dependency_stamp.exists()
        else ""
    )
    if refresh or recorded_fingerprint != expected_fingerprint:
        install_dependencies(config)
        config.dependency_stamp.write_text(
            expected_fingerprint + "\n",
            encoding="ascii",
        )
    else:
        print(f"构建依赖未变化，复用环境: {config.build_venv_dir}")

    verify_dependencies(config)


def install_dependencies(config):
    """在专用构建虚拟环境中安装项目依赖。"""
    run_command(
        "安装构建依赖",
        [
            config.python_exe,
            "-m",
            "pip",
            "install",
            "-r",
            config.requirements_file,
        ],
        timeout=config.command_timeout,
    )


def verify_dependencies(config):
    """在构建环境内部检查关键打包依赖。"""
    imports = (
        "import PyInstaller, flask, PySide6, cv2, numpy, PIL, pyautogui, "
        "pyzbar, win32api, cryptography, requests, markdown, psutil"
    )
    run_command(
        "检查构建依赖",
        [config.python_exe, "-c", imports],
        timeout=config.command_timeout,
    )
    print(f"构建环境可用: {config.build_venv_dir}")


def get_build_environment_identity(config):
    """获取构建环境中实际安装的依赖版本，纳入产物指纹。"""
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [str(config.python_exe), "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env,
        timeout=config.command_timeout or None,
    )
    return result.stdout.replace("\r\n", "\n")


def iter_pyinstaller_inputs(config):
    """枚举所有会影响 PyInstaller 产物的项目文件。"""
    fixed_files = (
        config.project_root / "run.py",
        config.requirements_file,
        config.project_root / "BHimage.ico",
        config.project_root / "scripts" / "build.py",
    )
    roots = (
        config.project_root / "src",
        config.project_root / "resources" / "templates",
        config.project_root / "resources" / "pictures_to_match",
    )
    files = [path for path in fixed_files if path.is_file()]
    for root in roots:
        if root.exists():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix.casefold() not in {".pyc", ".pyo"}
            )
    return sorted(files, key=lambda path: path.as_posix().lower())


def calculate_pyinstaller_fingerprint(config, environment_identity=None):
    """计算源码、打包配置、资源和构建依赖的稳定哈希。"""
    digest = hashlib.sha256()
    digest.update(f"onefile={USE_ONEFILE}\n".encode("ascii"))
    identity = (
        get_build_environment_identity(config)
        if environment_identity is None
        else environment_identity
    )
    digest.update(identity.encode("utf-8"))

    for path in iter_pyinstaller_inputs(config):
        relative_path = path.relative_to(config.project_root).as_posix()
        digest.update(f"\nfile:{relative_path}\n".encode("utf-8"))
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def build_or_reuse_pyinstaller(config, *, force=False):
    """输入未变化且产物有效时复用 dist，否则执行完整 PyInstaller。"""
    fingerprint = calculate_pyinstaller_fingerprint(config)
    cached_fingerprint = (
        config.pyinstaller_stamp.read_text(encoding="ascii").strip()
        if config.pyinstaller_stamp.exists()
        else ""
    )
    executable = config.app_dir / config.exe_name

    if not force and fingerprint == cached_fingerprint and executable.is_file():
        print(f"输入未变化，复用 PyInstaller 产物: {executable}")
        return False

    if force:
        print("已要求强制重建 PyInstaller 产物")
    elif cached_fingerprint and fingerprint != cached_fingerprint:
        print("检测到源码、资源、构建配置或依赖变化，将重新打包")
    else:
        print("未找到可复用的 PyInstaller 产物，将执行打包")

    clean_build_cache(config)
    run_pyinstaller_build(config)
    if not executable.is_file():
        raise RuntimeError(f"PyInstaller 未生成预期程序: {executable}")
    config.pyinstaller_stamp.parent.mkdir(parents=True, exist_ok=True)
    config.pyinstaller_stamp.write_text(fingerprint + "\n", encoding="ascii")
    return True


def clean_build_cache(config):
    """清理构建缓存"""
    for cache_dir in [
        config.project_root / "__pycache__",
        config.project_root / "build",
        config.project_root / "dist",
    ]:
        shutil.rmtree(cache_dir, ignore_errors=True)
        if cache_dir.exists():
            raise RuntimeError(
                f"无法清理构建目录: {cache_dir}\n"
                "请关闭正在运行的 BBH3ScanLaunch 或占用该目录的程序后重试。"
            )


def run_pyinstaller_build(config):
    """执行PyInstaller构建"""
    pyzbar_dir = get_build_package_dir(config, "pyzbar")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 准备构建目录
        shutil.rmtree(config.build_dir, ignore_errors=True)
        config.build_dir.mkdir(parents=True, exist_ok=True)

        cmd = build_pyinstaller_command(config, tmpdir, pyzbar_dir)
        child_env = os.environ.copy()
        # Windows 本地工具通常输出 CP936。强制 UTF-8 会导致 PyInstaller
        # 内部 subprocess 读取线程出现 UnicodeDecodeError。
        child_env.pop("PYTHONUTF8", None)
        child_env.pop("PYTHONIOENCODING", None)

        run_command(
            "PyInstaller",
            cmd,
            cwd=config.build_dir,
            timeout=config.command_timeout,
            env=child_env,
        )


def get_build_package_dir(config, package_name):
    """查询构建虚拟环境中的包目录。"""
    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            str(config.python_exe),
            "-c",
            (
                "import importlib.util, pathlib; "
                f"spec = importlib.util.find_spec({package_name!r}); "
                "assert spec and spec.origin; "
                "print(pathlib.Path(spec.origin).parent)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env,
        timeout=config.command_timeout or None,
    )
    return Path(result.stdout.strip())


def build_pyinstaller_command(config, spec_dir, pyzbar_dir):
    """构造由专用虚拟环境执行的最小化 PyInstaller 命令。"""
    cmd = [
        str(config.python_exe),
        "-m",
        "PyInstaller",
        "--name=BBH3ScanLaunch",
        "--noconfirm",
        "--workpath",
        str(config.project_root / "build"),
        "--distpath",
        str(config.output_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(config.project_root / "src"),
        "--noconsole",
        "--uac-admin",
        "-i",
        str(config.project_root / "BHimage.ico"),
        "--hidden-import",
        "bbh3_scan_launch",
        "--hidden-import",
        "bbh3_scan_launch.main",
        "--add-binary",
        f"{pyzbar_dir / 'libiconv.dll'};.",
        "--add-binary",
        f"{pyzbar_dir / 'libzbar-64.dll'};.",
        "--add-data",
        f"{config.project_root / 'resources' / 'templates'};resources/templates",
        "--add-data",
        f"{config.project_root / 'resources' / 'pictures_to_match'};resources/pictures_to_match",
    ]
    for module in PYINSTALLER_EXCLUDES:
        cmd.extend(("--exclude-module", module))
    if USE_ONEFILE:
        cmd.append("--onefile")
    cmd.append(str(config.project_root / "run.py"))
    return cmd


def copy_resources(config):
    """复制资源文件"""
    resource_pairs = [
        (
            config.project_root / "resources" / "templates",
            config.app_dir / "resources" / "templates",
        ),
        (
            config.project_root / "resources" / "pictures_to_match",
            config.app_dir / "resources" / "pictures_to_match",
        ),
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
    shortcuts = [("BBH3ScanLaunch.lnk", ""), ("AutoLoginBBH3.lnk", "--auto-login")]

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
        run_command(
            "Inno Setup",
            [str(inno_compiler), str(iss_file)],
            cwd=config.project_root / "scripts",
            timeout=config.command_timeout,
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
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

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
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  legacyConfigPath: string;
  userDataPath: string;
  persistentConfigPath: string;
begin
  Result := '';
  legacyConfigPath := ExpandConstant('{{app}}\\BBH3ScanLaunch\\config\\config.json');
  userDataPath := ExpandConstant('{{localappdata}}\\BBH3ScanLaunch');
  persistentConfigPath := userDataPath + '\\config.json';

  if FileExists(legacyConfigPath) and not FileExists(persistentConfigPath) then
  begin
    if not ForceDirectories(userDataPath) then
    begin
      Result := '无法创建用户配置目录: ' + userDataPath;
      exit;
    end;
    if not CopyFile(legacyConfigPath, persistentConfigPath, False) then
      Result := '无法迁移旧版配置文件: ' + legacyConfigPath;
  end;
end;

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
                new_url = version_path_pattern.sub(f"/download/v{VERSION}/", new_url)
                existing_data["sources"]["download_url"][source] = new_url

    # 写入更新后的数据
    try:
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
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
