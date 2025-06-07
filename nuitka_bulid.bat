@echo off
setlocal enabledelayedexpansion

:: 获取当前脚本目录
set "SCRIPT_DIR=%~dp0"

:: 自动获取Qt插件路径（使用短路径避免空格问题）
for /f "delims=" %%i in ('python -c "from PySide6.QtCore import QLibraryInfo; import os; path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath); print(os.path.normpath(path))"') do (
    set "QT_PLUGINS=%%~fi"
)

:: 检查是否找到Qt插件路径
if not defined QT_PLUGINS (
    echo 错误：未找到Qt插件路径！
    echo 请确保PySide6已正确安装
    exit /b 1
)

:: 转换为短路径格式（8.3格式）解决空格问题
for %%i in ("%QT_PLUGINS%") do set "QT_PLUGINS_SHORT=%%~si"

echo 检测到Qt插件路径: %QT_PLUGINS%
echo 使用短路径格式: %QT_PLUGINS_SHORT%

:: 定义插件子目录列表
set PLUGIN_SUBDIRS=platforms imageformats styles tls

:: 构建包含数据目录的参数
set INCLUDE_DATA_ARGS=
for %%s in (%PLUGIN_SUBDIRS%) do (
    set "source_dir=%QT_PLUGINS_SHORT%\%%s"
    if exist "!source_dir!" (
        set "INCLUDE_DATA_ARGS=!INCLUDE_DATA_ARGS! --include-data-dir=!source_dir!=qt6_plugins/%%s"
    )
)

:: 编译命令
nuitka --standalone^
	--standalone --output-dir=dist ^
       --output-filename=BBH3ScanLaunch.exe ^
       --windows-icon-from-ico="%SCRIPT_DIR%BHimage.ico" ^
       --windows-console-mode=disable ^
       --enable-plugin=pyside6 ^
       --include-package=PySide6.QtWidgets ^
       --include-package=PySide6.QtGui ^
       --include-package=PySide6.QtCore ^
       --windows-disable-console ^
       --remove-output ^
       --assume-yes-for-downloads ^
       %INCLUDE_DATA_ARGS% ^
       "%SCRIPT_DIR%main.py"

endlocal