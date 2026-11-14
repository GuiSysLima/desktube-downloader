# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
"""
Baixador gratuito de vídeos do YouTube (e de vários outros sites)
Usa o yt-dlp (open source). Requer: pip install -U yt-dlp
Opcional (recomendado): ffmpeg instalado, para juntar vídeo+áudio em alta qualidade e gerar MP3.
"""
import os
import shutil
import sys

try:
    import yt_dlp
except ImportError:
    print("O yt-dlp não está instalado. Rode:  pip install -U yt-dlp")
    sys.exit(1)

PASTA_SAIDA = os.path.join(os.path.expanduser("~"), "Downloads", "YouTube")

# Para erros de autenticação ("Sign in to confirm you're not a bot", idade, etc.)
# Coloque o navegador onde você está logado no YouTube: "operagx", "opera", "firefox", "chrome", "edge", "brave"...
# Deixe None para não usar cookies.
NAVEGADOR_COOKIES = "operagx"

# Alternativa: caminho para um arquivo cookies.txt exportado (ex.: "C:/Users/voce/cookies.txt")
ARQUIVO_COOKIES = None
TEM_FFMPEG = shutil.which("ffmpeg") is not None


def progresso(d):
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "").strip()
        vel = d.get("_speed_str", "").strip()
        print(f"\r  Baixando... {pct}  {vel}      ", end="", flush=True)
    elif d["status"] == "finished":
        print("\n  Download concluído, processando...")


def opcoes(modo):
    base = {
        "outtmpl": os.path.join(PASTA_SAIDA, "%(title)s.%(ext)s"),
        "progress_hooks": [progresso],
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
    }
    if ARQUIVO_COOKIES:
        base["cookiefile"] = ARQUIVO_COOKIES
    elif NAVEGADOR_COOKIES:
        nav = NAVEGADOR_COOKIES.lower().replace(" ", "")
        if nav in ("operagx", "opera_gx", "opera-gx"):
            # Opera GX usa o motor do Opera, mas com pasta de perfil própria
            perfil = os.path.join(os.environ.get("APPDATA", ""), "Opera Software", "Opera GX Stable")
            base["cookiesfrombrowser"] = ("opera", perfil)
        else:
            base["cookiesfrombrowser"] = (nav,)

    if modo == "1":  # Vídeo na melhor qualidade
        if TEM_FFMPEG:
            base["format"] = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b/best"
            base["merge_output_format"] = "mp4"
        else:
            # Sem ffmpeg só dá para baixar formatos que já vêm com áudio
            base["format"] = "b[ext=mp4]/b/best"
    elif modo == "2":  # Vídeo até 720p (arquivo menor)
        if TEM_FFMPEG:
            base["format"] = "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b/best"
            base["merge_output_format"] = "mp4"
        else:
            base["format"] = "b[height<=720]/b/best"
    elif modo == "3":  # Só áudio
        base["format"] = "ba/b/best"
        if TEM_FFMPEG:
            base["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
    return base


def main():
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    print("=== VidNeon — linha de comando (yt-dlp) ===")
    print(f"Arquivos salvos em: {PASTA_SAIDA}")
    if not TEM_FFMPEG:
        print("Aviso: ffmpeg não encontrado. Qualidade limitada e áudio sai em .m4a/.webm em vez de MP3.")

    while True:
        url = input("\nCole o link (ou Enter para sair): ").strip()
        if not url:
            break
        print("  1) Vídeo - melhor qualidade")
        print("  2) Vídeo - até 720p")
        print("  3) Somente áudio (MP3)")
        modo = input("Escolha [1]: ").strip() or "1"
        if modo not in ("1", "2", "3"):
            print("Opção inválida.")
            continue
        try:
            with yt_dlp.YoutubeDL(opcoes(modo)) as ydl:
                ydl.download([url])
            print("  Pronto!")
        except Exception as e:
            msg = str(e)
            print(f"\n  Erro: {msg}")
            if "format is not available" in msg.lower() or "only images" in msg.lower():
                print("  -> Formatos não encontrados. Instale o Deno:  winget install DenoLand.Deno")
                print("     e atualize:  pip install -U \"yt-dlp[default]\"  (depois reabra o terminal)")
            if any(t in msg.lower() for t in ("sign in", "bot", "cookies", "age", "login", "private")):
                print("  -> Erro de autenticação. Defina NAVEGADOR_COOKIES (ex.: \"firefox\")")
                print("     ou ARQUIVO_COOKIES no topo do script e tente de novo.")
            print("  Dica: atualize o yt-dlp com  pip install -U yt-dlp")


if __name__ == "__main__":
    main()
