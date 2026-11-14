"""Baixador de YouTube — aplicação desktop baseada no yt-dlp."""

APP_NAME = "Baixador de YouTube"
APP_ID = "BaixadorYouTube"

# Valores padrão; o build do GitHub Actions sobrescreve via _build_info.py
__version__ = "0.0.0-dev"
GITHUB_REPO = ""  # ex.: "usuario/baixador-youtube" (usado para checar atualizações)

try:  # gerado automaticamente no build
    from ._build_info import VERSION as __version__, REPO as GITHUB_REPO  # type: ignore # noqa
except Exception:
    pass
