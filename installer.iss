; Instalador do VidNeon (Inno Setup 6)
; Compilar:  ISCC.exe /DMyAppVersion=2.0.0 installer.iss
; Pré-requisito: dist\VidNeon.exe já gerado pelo PyInstaller

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif
#define MyAppName "VidNeon"
#define MyAppExe "VidNeon.exe"

[Setup]
; Mesmo AppId da v1 ("Baixador de YouTube"): o Windows trata como atualização do mesmo app
AppId={{8F2C5B1E-6A4D-4C3B-9E7A-2D1F0B5C9A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppName}
; Pasta padrão; o usuário pode escolher outra na tela "Selecione o local de destino"
DefaultDirName={autopf}\VidNeon
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Instala sem pedir administrador; o usuário pode escolher instalar para todos
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=VidNeon-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
CloseApplications=yes
; Mostra a escolha de idioma ao abrir o instalador (pré-seleciona o idioma do Windows)
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
brazilianportuguese.AppTagline=Baixe vídeos e áudios
english.AppTagline=Download videos and audio

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove o executável e os atalhos da v1 (nome antigo "Baixador de YouTube" / "YouTube Downloader")
Type: files; Name: "{app}\BaixadorYouTube.exe"
Type: files; Name: "{autoprograms}\Baixador de YouTube.lnk"
Type: files; Name: "{autoprograms}\YouTube Downloader.lnk"
Type: files; Name: "{autodesktop}\Baixador de YouTube.lnk"
Type: files; Name: "{autodesktop}\YouTube Downloader.lnk"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; O app usa o idioma escolhido aqui como padrão (pode ser trocado depois em Configurações)
Root: HKCU; Subkey: "Software\VidNeon"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletekey

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Comment: "{cm:AppTagline}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Comment: "{cm:AppTagline}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
