@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取当前脚本目录
set "SCRIPT_DIR=%~dp0"

:: 自动获取Qt插件路径
for /f "delims=" %%i in ('python -c "from PySide6.QtCore import QLibraryInfo; import os; path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath); print(os.path.normpath(path))"') do (
    set "QT_PLUGINS=%%i"
)

if not defined QT_PLUGINS (
    echo 错误：未找到Qt插件路径！
    echo 请确保PySide6已正确安装
    exit /b 1
)

echo 检测到Qt插件路径: %QT_PLUGINS%

:: 定义插件子目录列表
set PLUGIN_SUBDIRS=platforms imageformats styles tls

:: 构建包含数据目录的参数 - 修复空目录警告
set INCLUDE_DATA_ARGS=
for %%s in (%PLUGIN_SUBDIRS%) do (
    set "source_dir=%QT_PLUGINS%\%%s"
    if exist "!source_dir!" (
        :: 检查目录是否为空
        dir /b "!source_dir!" 2>nul | findstr . >nul
        if !errorlevel! == 0 (
            set "INCLUDE_DATA_ARGS=!INCLUDE_DATA_ARGS! --include-data-dir=!source_dir!=qt6_plugins/%%s"
        ) else (
            echo 警告：Qt插件目录 !source_dir! 为空，跳过
        )
    )
)

:: 设置输出目录
set "OUTPUT_DIR=%SCRIPT_DIR%dist"
set "EXE_NAME=BBH3ScanLaunch.exe"

:: 清理旧目录
if exist "%OUTPUT_DIR%" rd /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"

:: 修复Nuitka控制台模式警告
nuitka --onefile ^
    --output-dir="%OUTPUT_DIR%" ^
    --output-filename=%EXE_NAME% ^
    --windows-icon-from-ico="%SCRIPT_DIR%BHimage.ico" ^
    --windows-console-mode=disable ^
    --enable-plugin=pyside6 ^
    --include-package=PySide6.QtWidgets ^
    --include-package=PySide6.QtGui ^
    --include-package=PySide6.QtCore ^
    --assume-yes-for-downloads ^
    %INCLUDE_DATA_ARGS% ^
    "%SCRIPT_DIR%main.py"

:: 修复资源复制问题
set "RESOURCE_DIRS=Pictures_to_Match templates"
for %%d in (%RESOURCE_DIRS%) do (
    if exist "%SCRIPT_DIR%%%d" (
        echo 正在复制资源目录：%%d
        xcopy /e /i /y "%SCRIPT_DIR%%%d" "%OUTPUT_DIR%\%%d\" 
    ) else (
        echo 警告：找不到资源目录：%%d
    )
)

:: 复制配置文件
if exist "%SCRIPT_DIR%config.json" (
    copy /y "%SCRIPT_DIR%config.json" "%OUTPUT_DIR%\"
)

:: 复制图标
copy /y "%SCRIPT_DIR%BHimage.ico" "%OUTPUT_DIR%\"

:: 创建快捷方式
set "TARGET_EXE=%OUTPUT_DIR%\%EXE_NAME%"
set "ICON_FILE=%OUTPUT_DIR%\BHimage.ico"

(
echo var sh = new ActiveXObject("WScript.Shell"); 
echo var sc1 = sh.CreateShortcut("%OUTPUT_DIR%\\[仅B服] 崩坏3扫码器 [限v8.3].lnk"); 
echo sc1.TargetPath = "%TARGET_EXE%"; 
echo sc1.IconLocation = "%ICON_FILE%"; 
echo sc1.WorkingDirectory = "%OUTPUT_DIR%"; 
echo sc1.Save(); 
echo var sc2 = sh.CreateShortcut("%OUTPUT_DIR%\\[仅B服] 一键登录崩坏3 [限v8.3].lnk"); 
echo sc2.TargetPath = "%TARGET_EXE%"; 
echo sc2.Arguments = "--auto-login"; 
echo sc2.IconLocation = "%ICON_FILE%"; 
echo sc2.WorkingDirectory = "%OUTPUT_DIR%"; 
echo sc2.Save(); 
echo close();
)>"%TEMP%\create_shortcuts.hta"

mshta "%TEMP%\create_shortcuts.hta"

:: 创建纯净压缩包
set "PACKAGE_DIR=%OUTPUT_DIR%\BBH3ScanLaunch_Package"
mkdir "%PACKAGE_DIR%" 2>nul

:: 复制EXE文件
copy /y "%OUTPUT_DIR%\%EXE_NAME%" "%PACKAGE_DIR%\" >nul

:: 特殊处理Pictures_to_Match目录（只复制Default子目录）
if exist "%SCRIPT_DIR%Pictures_to_Match\Default" (
    echo 正在复制资源目录：Pictures_to_Match\Default
    mkdir "%OUTPUT_DIR%\Pictures_to_Match" 2>nul
    xcopy /e /i /y "%SCRIPT_DIR%Pictures_to_Match\Default" "%OUTPUT_DIR%\Pictures_to_Match\Default\"
)

:: 正常处理其他资源目录（如templates）
for %%d in (%RESOURCE_DIRS%) do (
    if /i not "%%d"=="Pictures_to_Match" (
        if exist "%SCRIPT_DIR%%%d" (
            echo 正在复制资源目录：%%d
            xcopy /e /i /y "%SCRIPT_DIR%%%d" "%OUTPUT_DIR%\%%d\" 
        )
    )
)

:: 复制配置文件
if exist "%OUTPUT_DIR%\config.json" (
    copy /y "%OUTPUT_DIR%\config.json" "%PACKAGE_DIR%\" >nul
)

:: 复制图标文件
copy /y "%ICON_FILE%" "%PACKAGE_DIR%\" >nul

:: 创建压缩包（仅包含必要文件）
set "ZIP_FILE=%OUTPUT_DIR%\BBH3ScanLaunch_v8.3.zip"
if exist "%ZIP_FILE%" del "%ZIP_FILE%"
cd /d "%PACKAGE_DIR%"
powershell -Command "Get-ChildItem -Path '.' | Compress-Archive -DestinationPath '%ZIP_FILE%' -Force"

:: 清理临时打包目录
rd /s /q "%PACKAGE_DIR%"

echo.
echo ============= 构建成功 =============
echo 单文件EXE: %OUTPUT_DIR%\%EXE_NAME%
echo 资源目录: %OUTPUT_DIR%\Pictures_to_Match 和 %OUTPUT_DIR%\templates
echo 压缩包位置: %ZIP_FILE%
echo ===================================

:: 解决PyQt5冲突警告
echo.
echo 注意：发现PyQt5与PySide6冲突警告
echo 建议运行以下命令解决冲突：
echo     pip uninstall -y PyQt5 PyQt5-Qt5 PyQt5-sip
pause