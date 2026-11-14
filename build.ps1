# Gera o executável localmente:  .\build.ps1        (build de teste com alterações pendentes: -Force)
# Resultado: dist\VidNeon.exe e dist\VidNeon-Setup.exe
#
# A versão vem da tag do git. Para publicar a versão X: commit -> git tag vX -> git push origin vX -> build.
param([switch]$Force)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -U -r requirements.txt pyinstaller

git fetch --tags --quiet 2>$null   # traz as tags do GitHub (a versão vem da tag, ex.: v2.0.0)
$version = (git describe --tags --always 2>$null)
if (-not $version) { $version = "local" }

# Alterações não commitadas = o .exe teria o código NOVO com o número da versão ANTERIOR
# (foi o que aconteceu na 2.2.0: o instalador saiu como 2.1.0 e o app ficava pedindo atualização).
$pending = (git status --porcelain 2>$null)
if ($pending) {
    Write-Host "`nHá alterações não commitadas:" -ForegroundColor Red
    $pending | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" }
    if (-not $Force) {
        Write-Host "`nFaça o commit e crie a tag da nova versão antes do build (git tag vX.Y.Z; git push origin vX.Y.Z)." -ForegroundColor Red
        Write-Host "Para um build só de teste, use:  .\build.ps1 -Force" -ForegroundColor Yellow
        exit 1
    }
    $version = "$version-dirty"
}
if ($version -notmatch '^v\d+\.\d+\.\d+$') {
    Write-Host "`nBuild de DESENVOLVIMENTO ($version): o commit atual não tem uma tag vX.Y.Z. Não publique numa Release." -ForegroundColor Yellow
}
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
    Write-Host "`nVersão do app e do instalador: $version  ->  anexe na Release $version" -ForegroundColor Cyan
} else {
    Write-Host "Inno Setup não encontrado: instalador não gerado (winget install JRSoftware.InnoSetup)" -ForegroundColor Yellow
}
