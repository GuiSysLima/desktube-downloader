; Instalador do Baixador de YouTube / YouTube Downloader (Inno Setup 6)
; Compilar:  ISCC.exe /DMyAppVersion=1.0.0 installer.iss
; Pré-requisito: dist\BaixadorYouTube.exe já gerado pelo PyInstaller

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppExe "BaixadorYouTube.exe"

[Setup]
AppId={{8F2C5B1E-6A4D-4C3B-9E7A-2D1F0B5C9A11}
AppName={cm:AppName}
AppVersion={#MyAppVersion}
AppVerName={cm:AppName} {#MyAppVersion}
AppPublisher={cm:AppName}
; Pasta padrão; o usuário pode escolher outra na tela "Selecione o local de destino"
DefaultDirName={autopf}\BaixadorYouTube
DisableDirPage=no
DefaultGroupName={cm:AppName}
DisableProgramGroupPage=yes
; Instala sem pedir administrador; o usuário pode escolher instalar para todos
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=BaixadorYouTube-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={cm:AppName}
CloseApplications=yes
; Mostra a escolha de idioma ao abrir o instalador (pré-seleciona o idioma do Windows)
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
brazilianportuguese.AppName=Baixador de YouTube
english.AppName=YouTube Downloader

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; O app usa o idioma escolhido aqui como padrão (pode ser trocado depois em Configurações)
Root: HKCU; Subkey: "Software\BaixadorYouTube"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletekey

[Icons]
Name: "{autoprograms}\{cm:AppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{cm:AppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{cm:AppName}}"; Flags: nowait postinstall skipifsilent
