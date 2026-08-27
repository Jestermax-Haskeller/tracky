; Tracky's Inno Setup recipe.
; This installer uses a normal machine-wide Windows uninstall registration so
; Windows Settings can reliably discover Tracky in Apps > Installed apps.

#define MyAppName "tracky"
#define MyAppVersion "0.3.5"
#define MyAppPublisher "Jestermax-Haskeller"
#define MyAppURL "https://github.com/Jestermax-Haskeller/Tracky"
#define MyAppExeName "tracky.exe"

[Setup]
; Keep this AppId stable between releases. Inno Setup uses it to identify an
; existing installation when the user upgrades Tracky later.
AppId={{7A97D1D3-3AB0-4B79-889D-2BB8D4C35256}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Program Files plus admin install means Inno writes its uninstall information
; to HKLM, which is the conventional registration read by Windows Installed apps.
DefaultDirName={autopf}\tracky
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

DisableProgramGroupPage=yes
OutputDir=installer_dist
OutputBaseFilename=TrackySetup
SetupIconFile=assets\tracky.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; These explicit directives make the intended Windows registration obvious.
; Inno creates the uninstall registry key and points Windows at unins000.exe.
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallDisplayName=tracky
UninstallDisplayIcon={app}\{#MyAppExeName}

; Version metadata also applies to TrackySetup.exe itself.
VersionInfoVersion=0.3.5.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=tracky installer
VersionInfoProductName=tracky
VersionInfoProductVersion={#MyAppVersion}

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\tracky"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Uninstall tracky"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch tracky"; Flags: nowait postinstall skipifsilent
