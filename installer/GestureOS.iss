#define MyAppName "GestureOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "GestureOS"
#define MyAppExeName "GestureOS.exe"
[Setup]
AppId={{E5F5A1C2-7B45-4A70-9F13-5C6B8C7A1001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\GestureOS
DefaultGroupName=GestureOS
OutputDir=..\dist-installer
OutputBaseFilename=GestureOS-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
[Files]
Source: "..\dist\GestureOS\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{autoprograms}\GestureOS"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\GestureOS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch GestureOS"; Flags: nowait postinstall skipifsilent
