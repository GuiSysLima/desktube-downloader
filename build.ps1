# Gera o executável localmente:  .\build.ps1
# Resultado: dist\VidNeon.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -U -r requirements.txt pyinstaller

git fetch --tags --quiet 2>$null   # traz as tags do GitHub (a versão vem da tag, ex.: v2.0.0)
$version = (git describe --tags --always 2>$null)
if (-not $version) { $version = "local" }
# Descobre "usuario/repositorio" a partir do remote origin (para o botão de atualizações)
$repo = ""
$remote = (git remote get-url origin 2>$null)
if ($remote -match 'github\.com[:/](.+?)(\.git)?$') { $repo = $Matches[1] }
"VERSION = `"$version`"`nREPO = `"$repo`"" | Out-File -Encoding utf8 app\_build_info.py
Write-Host "Versão: $version   Repositório: $repo"

python -m PyInstaller --noconfirm --onefile --windowed --name VidNeon `
    --icon assets\icon.ico --add-data "assets;assets" --add-data "LICENSE;." --add-data "NOTICE;." `
    --collect-all customtkinter --collect-all yt_dlp_ejs --collect-submodules yt_dlp `
    run.py

Write-Host "`nPronto: dist\VidNeon.exe" -ForegroundColor Green

# Instalador (opcional): precisa do Inno Setup 6  ->  winget install JRSoftware.InnoSetup
$iscc = Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup*\ISCC.exe", "$env:ProgramFiles\Inno Setup*\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($iscc) {
    $appVersion = $version.TrimStart('v')
    & $iscc.FullName "/DMyAppVersion=$appVersion" installer.iss
    Write-Host "Pronto: dist\VidNeon-Setup.exe" -ForegroundColor Green
} else {
    Write-Host "Inno Setup não encontrado: instalador não gerado (winget install JRSoftware.InnoSetup)" -ForegroundColor Yellow
}
