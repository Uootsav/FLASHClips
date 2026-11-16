; Inno Setup script -> FLASHClips-Setup.exe  (built automatically by GitHub Actions)
#define AppVer GetEnv("APP_VERSION")
[Setup]
AppId={{6C1F0B7E-3E4A-4F7B-9F55-0F1A5C11B5A1}
AppName=FLASHClips
AppVersion={#AppVer}
AppPublisher=Utsav Patel
DefaultDirName={autopf}\FLASHClips
DefaultGroupName=FLASHClips
OutputBaseFilename=FLASHClips-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Files]
Source: "dist\FLASHClips\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\FLASHClips"; Filename: "{app}\FLASHClips.exe"
Name: "{autodesktop}\FLASHClips"; Filename: "{app}\FLASHClips.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"

[Run]
Filename: "{app}\FLASHClips.exe"; Description: "Launch FLASHClips"; Flags: nowait postinstall skipifsilent
