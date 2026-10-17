; Inno Setup Script for Desktop GIF Sticker
; Modern, lightweight installer with desktop shortcut and uninstaller

#define MyAppName "Desktop GIF Sticker"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Desktop Sticker Studio"
#define MyAppExeName "DesktopSticker.exe"

[Setup]
; Unique AppId for clean upgrade and uninstall registry
AppId={{8F5B7B12-4E38-4C21-998A-387E88F93A4B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; PrivilegesRequired=lowest enables 1-click install without needing Windows admin prompt
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=DesktopSticker_Setup_v1.0
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Opsi Tambahan:"; Flags: unchecked
Name: "startupicon"; Description: "Jalankan otomatis saat komputer dinyalakan (Startup)"; GroupDescription: "Opsi Tambahan:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan {#MyAppName} sekarang"; Flags: nowait postinstall skipifsilent
