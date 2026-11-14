"""Ponto de entrada do aplicativo."""
import os
import sys


def main():
    # No .exe sem console, stdout/stderr são None; o yt-dlp precisa de algo válido
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BaixadorYouTube.App")
        except Exception:
            pass

    from .gui import App
    App().mainloop()


if __name__ == "__main__":
    main()
