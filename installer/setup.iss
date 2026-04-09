; ================================================================
; PDF Editor – Inno Setup Installer Script
; Requires: Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
;
; Usage:
;   1. Build the exe first:  pyinstaller DocumentProcessor.spec --noconfirm
;   2. Open this file in Inno Setup Compiler and press Compile (Ctrl+F9)
;   3. The installer will be in installer\Output\PDFEditor_Setup.exe
; ================================================================

#define AppName      "PDF Editor"
#define AppVersion   "1.0.0"
#define AppPublisher "PDFEditor"
#define AppURL       "https://github.com/balazs565/document-processor"
#define AppExeName   "PDFEditor.exe"
#define SourceDir    "..\dist\PDFEditor"

[Setup]
; Basic metadata
AppId={{A3F2C8D1-4E7B-4F0A-9C2D-6E8F1A3B5C7D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Install directory
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Output
OutputDir=Output
OutputBaseFilename=PDFEditor_Setup
SetupIconFile=..\assets\styles\text-document-outlined-symbol_icon-icons.com_57756.ico
Compression=lzma2/ultra64
SolidCompression=yes

; UI
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no
LicenseFile=

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Misc
ShowLanguageDialog=no
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "Create a &desktop shortcut";       GroupDescription: "Additional icons:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application – copy the entire PyInstaller output folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";                 Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";       Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#AppName}";           Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Associate .pdf files with the app (optional – opens PDF Editor for .pdf)
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFEditor.AssocFile.PDF"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\PDFEditor.AssocFile.PDF"; ValueType: string; ValueName: ""; ValueData: "PDF File"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PDFEditor.AssocFile.PDF\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"
Root: HKA; Subkey: "Software\Classes\PDFEditor.AssocFile.PDF\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""

[Run]
; Offer to launch the app after installation
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Optional: check if Tesseract is installed and warn user
procedure InitializeWizard();
begin
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;
