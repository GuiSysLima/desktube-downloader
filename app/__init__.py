# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""VidNeon — app desktop para baixar vídeos e áudios, baseado no yt-dlp."""

APP_NAME = "VidNeon"
APP_ID = "VidNeon"
OLD_APP_IDS = ("BaixadorYouTube",)  # nomes antigos (migração de dados)

# Autoria e licença (ver LICENSE e NOTICE). O crédito abaixo é exigido pelos termos
# adicionais da GPL-3.0 (seção 7b) e deve continuar visível na tela "Sobre".
AUTHOR = "Guilherme Felix (GuiSysLima)"
COPYRIGHT_YEAR = "2026"
PROJECT_URL = "https://github.com/GuiSysLima/desktube-downloader"
LICENSE_ID = "GPL-3.0-only"

# Valores padrão; o build do GitHub Actions sobrescreve via _build_info.py
__version__ = "0.0.0-dev"
GITHUB_REPO = "GuiSysLima/desktube-downloader"  # repositório das Releases (o build pode sobrescrever)

try:  # gerado automaticamente no build
    from ._build_info import VERSION as __version__, REPO as GITHUB_REPO  # type: ignore # noqa
except Exception:
    pass
