; Inno Setup Script for Dota 2 Chat Translator
#define MyAppName "Dota2ChatTranslator"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Bamsemats"
#define MyAppURL "https://github.com/bamsemats/Dota2Translator"
#define MyAppExeName "Dota2ChatTranslator.exe"

[Setup]
AppId={{DOTA2CHATTRANSLATOR-BAMSEMATS}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=Dota2ChatTranslator_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Dota2ChatTranslator\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Dota2ChatTranslator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Rename template to actual if it doesn't exist (handled by app normally, but good to have)
Source: "client_secret_template.json"; DestDir: "{app}"; DestName: "client_secret.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
