; BBH3ScanLaunch 安装包脚本
#define MyAppName "BBH3ScanLaunch"
#define MyAppVersion "1.1"
#define MyAppExeName "BBH3ScanLaunch.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=BBH3ScanLaunch_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=dist\BBH3ScanLaunch\BHimage.ico
AppPublisher=BBH3ScanLaunch
AppPublisherURL=https://github.com/your-repo
AppSupportURL=https://github.com/your-repo
AppUpdatesURL=https://github.com/your-repo

[Files]
Source: "dist\BBH3ScanLaunch\*"; Excludes: "config.json"; DestDir: "{app}\BBH3ScanLaunch"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单快捷方式（带UAC）
Name: "{group}\[仅B服] 崩坏3扫码器"; Filename: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; IconFilename: "{app}\BBH3ScanLaunch\BHimage.ico"
Name: "{group}\[仅B服] 一键登陆崩坏3"; Filename: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; Parameters: "--auto-login"; IconFilename: "{app}\BBH3ScanLaunch\BHimage.ico"

; 桌面快捷方式（带UAC） - 直接创建不询问
Name: "{autodesktop}\[仅B服] 崩坏3扫码器"; Filename: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; IconFilename: "{app}\BBH3ScanLaunch\BHimage.ico"
Name: "{autodesktop}\[仅B服] 一键登陆崩坏3"; Filename: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; Parameters: "--auto-login"; IconFilename: "{app}\BBH3ScanLaunch\BHimage.ico"

[Run]
Filename: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Registry]
; 为EXE添加UAC清单（如果程序本身没有）
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; \
    ValueType: String; ValueName: "{app}\BBH3ScanLaunch\{#MyAppExeName}"; ValueData: "RUNASADMIN"; Flags: uninsdeletevalue