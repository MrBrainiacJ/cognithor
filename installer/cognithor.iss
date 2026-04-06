; Cognithor Installer — Inno Setup Script
; Built by build_installer.py
;
; Inspired by Git for Windows installer architecture.
; Uses embedded Python (no system Python required).

#ifndef MyAppVersion
  #define MyAppVersion "0.75.0"
#endif

#ifndef BuildDir
  #define BuildDir SourcePath + "\build"
#endif

#ifndef ProjectRoot
  #define ProjectRoot SourcePath + "\.."
#endif

#ifndef PythonDir
  #define PythonDir BuildDir + "\python"
#endif

#ifndef OllamaDir
  #define OllamaDir BuildDir + "\ollama"
#endif

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-COGNITHOR0001}
AppName=Cognithor
AppVersion={#MyAppVersion}
AppVerName=Cognithor {#MyAppVersion}
AppPublisher=Alexander Soellner
AppPublisherURL=https://github.com/Alex8791-cyber/cognithor
AppSupportURL=https://github.com/Alex8791-cyber/cognithor/issues
DefaultDirName={localappdata}\Cognithor
DefaultGroupName=Cognithor
AllowNoIcons=yes
LicenseFile={#ProjectRoot}\LICENSE
OutputDir=dist
OutputBaseFilename=CognithorSetup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile={#ProjectRoot}\flutter_app\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
UninstallDisplayName=Cognithor {#MyAppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Types]
Name: "full"; Description: "Full installation (recommended)"
Name: "compact"; Description: "Cognithor only (no Ollama, no UI)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "Cognithor Core (Python + Dependencies)"; Types: full compact custom; Flags: fixed
Name: "ollama"; Description: "Ollama (Local LLM Runtime)"; Types: full custom
Name: "flutter"; Description: "Flutter Command Center (Web UI)"; Types: full custom
Name: "addpath"; Description: "Add cognithor to PATH"; Types: full custom

[Files]
; Core: Embedded Python + cognithor
Source: "{#PythonDir}\*"; DestDir: "{app}\python"; Components: core; Flags: ignoreversion recursesubdirs createallsubdirs

; Launcher
Source: "{#BuildDir}\cognithor.bat"; DestDir: "{app}"; Components: core; Flags: ignoreversion

; Ollama
Source: "{#OllamaDir}\*"; DestDir: "{app}\ollama"; Components: ollama; Flags: ignoreversion recursesubdirs createallsubdirs

; Flutter UI — always include from build dir if present
Source: "{#BuildDir}\flutter_web\*"; DestDir: "{app}\flutter_app\web"; Components: flutter; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; First-run setup script
Source: "{#ProjectRoot}\installer\first_run.py"; DestDir: "{app}"; Components: core; Flags: ignoreversion

; Default agents config
Source: "{#ProjectRoot}\installer\agents.yaml.default"; DestDir: "{app}"; Components: core; Flags: ignoreversion

; Config template
Source: "{#ProjectRoot}\config.yaml.example"; DestDir: "{app}"; DestName: "config.yaml"; Flags: onlyifdoesntexist

; App icon for shortcuts
Source: "{#ProjectRoot}\flutter_app\windows\runner\resources\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Cognithor"; Filename: "{app}\cognithor.bat"; Parameters: "--ui"; IconFilename: "{app}\app_icon.ico"; Comment: "Start Cognithor with Web UI"
Name: "{group}\Cognithor CLI"; Filename: "cmd.exe"; Parameters: "/k ""{app}\cognithor.bat"""; IconFilename: "{app}\app_icon.ico"; Comment: "Cognithor Command Line"
Name: "{group}\Uninstall Cognithor"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Cognithor"; Filename: "{app}\cognithor.bat"; Parameters: "--ui"; IconFilename: "{app}\app_icon.ico"; Comment: "Start Cognithor"

[Registry]
; Add to PATH if selected
Root: HKCU; Subkey: "Environment"; \
    ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; \
    Components: addpath; Check: NeedsAddPath('{app}')

[Run]
; Post-install: offer to start Cognithor
Filename: "{cmd}"; Parameters: "/k ""{app}\cognithor.bat"" --ui"; Description: "Start Cognithor"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python\__pycache__"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\__pycache__"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\ollama"
Type: filesandordirs; Name: "{app}\flutter_app"
Type: files; Name: "{app}\cognithor.bat"
Type: files; Name: "{app}\first_run.py"
Type: files; Name: "{app}\agents.yaml.default"
Type: files; Name: "{app}\config.yaml"

[Code]
// Check if directory is already in PATH
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER,
    'Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;

// Remove from PATH on uninstall + optional user data cleanup
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Path: string;
  AppDir: string;
  JarvisHome: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Remove from PATH
    AppDir := ExpandConstant('{app}');
    if RegQueryStringValue(HKEY_CURRENT_USER,
      'Environment',
      'Path', Path) then
    begin
      StringChangeEx(Path, ';' + AppDir, '', True);
      StringChangeEx(Path, AppDir + ';', '', True);
      StringChangeEx(Path, AppDir, '', True);
      RegWriteStringValue(HKEY_CURRENT_USER,
        'Environment',
        'Path', Path);
    end;

    // Stop Ollama if running
    Exec('taskkill', '/F /IM ollama.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Ask user: remove user data?
    JarvisHome := ExpandConstant('{userprofile}\.jarvis');
    if DirExists(JarvisHome) then
    begin
      if MsgBox(
        'Do you want to remove all Cognithor user data?' + #13#10 +
        '(Memory, Vault, Skills, Configuration, Databases)' + #13#10 + #13#10 +
        'Location: ' + JarvisHome + #13#10 + #13#10 +
        'Click "No" to keep your data for a future reinstallation.',
        mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(JarvisHome, True, True, True);
      end;
    end;

    // Clean up install directory
    DelTree(AppDir, True, True, True);
  end;
end;
