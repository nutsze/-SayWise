; Inno Setup 6: установщик GraspSetup.exe
; Собирается из build.py:  ISCC /DAppVersion=0.1.0 /DSourceDir=...\Grasp /DOutputDir=...\dist grasp.iss

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\pyinstaller\Grasp"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "Grasp"
#define AppPublisher "Grasp Project"
#define AppExe "Grasp.exe"

[Setup]
; AppId не менять между версиями — по нему работает обновление и удаление.
AppId={{6F1C4A52-8E3B-4C77-9F0A-2B7D5E1A9C43}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} — установщик
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=GraspSetup-{#AppVersion}
SetupIconFile=..\grasp\resources\icons\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Если программа запущена — предложить закрыть (мьютекс создаёт сам Grasp).
AppMutex=GraspAppMutex
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Прогресс пользователя лежит в %APPDATA%\Grasp и при обновлении не трогается.
// При удалении — спрашиваем, удалять ли его.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\Grasp');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Удалить также ваш прогресс, настройки и записи голоса?' + #13#10 + DataDir,
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
