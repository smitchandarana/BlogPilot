; BlogPilot Windows Installer — Inno Setup 6
; Compile with: iscc installer.iss
; Requires Inno Setup 6: https://jrsoftware.org/isinfo.php
;
; Run AFTER building the EXE:
;   cd ui && npm run build
;   pyinstaller blogpilot.spec
;   iscc installer.iss

#define AppName      "BlogPilot"
#define AppVersion   "1.0.0"
#define AppPublisher "BlogPilot"
#define AppURL       "http://localhost:8000"
#define AppExeName   "BlogPilot.exe"
#define SrcExe       "dist\BlogPilot.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=BlogPilot-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
; Show an EULA/risk warning before install
LicenseFile=NOTICE.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "{cm:CreateDesktopIcon}";  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon";  Description: "Launch BlogPilot when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Single self-contained EXE (onefile build — no _internal/ folder needed)
Source: "{#SrcExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#AppName}";  Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop shortcut (only if task selected)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Auto-start on Windows login (only if task selected)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Launch the app after installation finishes
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Nothing special needed — Playwright browser profile and user data are left intact
; so reinstalling doesn't lose the user's LinkedIn session or API keys.
