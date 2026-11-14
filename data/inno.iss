[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; URH-NG uses its own AppId (the original URH uses 8A0E36A6-...) so both can
; be installed side by side and installing one never replaces the other.
AppId={{5B7C2E41-9A3D-4F6B-8C1E-2D7A9F0B3E64}
AppName=URH-NG
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName=URH-NG
AppPublisher=PentHertz
AppPublisherURL=https://github.com/PentHertz/urh-ng
AppSupportURL=https://github.com/PentHertz/urh-ng
AppUpdatesURL=https://github.com/PentHertz/urh-ng
; Per-user install by default (%LOCALAPPDATA%\Programs\URH-NG): no Windows
; permission (UAC) prompt. "dialog" / /ALLUSERS still lets an administrator
; install it for all users in Program Files.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
UsePreviousPrivileges=no
DefaultDirName={autopf}\URH-NG
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=URH-NG-{#MyAppVersion}-{#Arch}
Compression=lzma2/ultra
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\pyinstaller\urh\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\URH-NG"; Filename: "{app}\urh.exe"
Name: "{autodesktop}\URH-NG"; Filename: "{app}\urh.exe"; Tasks: desktopicon

[Run]
; Install the bundled decoders into the user's %APPDATA%\urh (only when the
; build included them, see data\windows\build_windows.ps1)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\decoders\install-decoders.ps1"" -Silent"; Flags: runhidden runasoriginaluser; StatusMsg: "Installing decoders..."; Check: DecodersBundled
Filename: "{app}\urh.exe"; Description: "{cm:LaunchProgram,URH-NG}"; Flags: nowait postinstall skipifsilent

[Code]
function DecodersBundled: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\decoders\install-decoders.ps1'));
end;
