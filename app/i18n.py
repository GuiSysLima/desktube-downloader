"""Traduções da interface (português e inglês).

Uso:  from .i18n import t;  t("btn_download")  /  t("err_cookie_copy", browser="Opera GX")
Para adicionar um idioma: crie um novo dicionário em STRINGS e inclua em LANGUAGES.
"""
import locale
import sys

LANGUAGES = {"pt": "Português (Brasil)", "en": "English"}
DEFAULT = "pt"
_current = DEFAULT

STRINGS = {
    "pt": {
        "app_name": "Baixador de YouTube",
        # abas
        "tab_download": "Baixar",
        "tab_history": "Vídeos baixados",
        "tab_settings": "Configurações",
        # aba Baixar
        "url_placeholder": "Cole aqui o link do vídeo ou playlist (pode colar vários de uma vez)",
        "btn_paste": "Colar",
        "btn_download": "Baixar",
        "chk_playlist": "Playlist inteira",
        "chk_subtitles": "Legendas",
        "login_browser": "Login: {name}  ⚙",
        "login_file": "Login: cookies.txt  ⚙",
        "login_none": "Login: nenhum  ⚙",
        "btn_install_now": "Instalar agora",
        "queue_title": "Fila de downloads",
        "queue_empty": "Nenhum download ainda.\nCole um link acima e clique em Baixar.",
        "save_to": "Salvar em:",
        "btn_open": "Abrir",
        "btn_change_folder": "Alterar pasta...",
        "btn_clear_finished": "Limpar concluídos",
        "invalid_url": "Cole um link válido (começando com http).",
        "browser_open_download": ("O {name} está aberto. Para ler o seu login do YouTube ele precisa estar fechado.\n\n"
                                  "Sim: fechar o {name} agora e baixar\n"
                                  "Não: baixar mesmo assim (pode dar erro de cookies)\n"
                                  "Cancelar: não baixar agora"),
        "missing_banner": "Faltam componentes: {names}. Sem eles alguns vídeos não baixam ou ficam em qualidade baixa.",
        # qualidade
        "q_best": "Vídeo — melhor qualidade",
        "q_1080": "Vídeo — até 1080p",
        "q_720": "Vídeo — até 720p",
        "q_480": "Vídeo — até 480p",
        "q_mp3": "Áudio — MP3",
        "q_m4a": "Áudio — M4A (sem conversão)",
        # fila / status
        "btn_cancel": "Cancelar",
        "btn_open_folder": "Abrir pasta",
        "btn_retry": "Tentar de novo",
        "btn_remove": "Remover",
        "st_queued": "Na fila",
        "st_starting": "Iniciando...",
        "st_downloading": "Baixando",
        "st_downloading_audio": "Baixando (áudio)",
        "st_processing": "Processando...",
        "st_merging": "Juntando vídeo e áudio...",
        "st_converting": "Convertendo para MP3...",
        "st_thumbnail": "Inserindo miniatura...",
        "st_metadata": "Gravando metadados...",
        "st_subtitles": "Inserindo legendas...",
        "st_done": "Concluído ✓",
        "st_cancelled": "Cancelado",
        "st_error": "Erro: {msg}",
        "item_n": "item {n}",
        "eta": "faltam {eta}",
        "done_status": "Concluído: {title}",
        "failed_status": "Um download falhou — veja o motivo na fila.",
        # erros
        "err_login": ("O YouTube pediu login. Em Configurações, escolha o navegador em que você "
                      "está logado no YouTube e clique em 'Testar login'."),
        "err_cookie_copy": "Não foi possível ler os cookies: feche o {browser} por completo e tente de novo.",
        "err_decrypt": "O navegador criptografou os cookies. Use Firefox ou um arquivo cookies.txt (Configurações).",
        "err_no_format": ("Nenhum formato disponível. Instale o Deno em Configurações › Componentes, "
                          "reabra o app e tente de novo."),
        "err_private": "Vídeo privado: só funciona com o login de uma conta que tenha acesso.",
        "err_age": "Vídeo com restrição de idade: configure o login do navegador em Configurações.",
        "err_unavailable": "Vídeo indisponível (removido, bloqueado ou região restrita).",
        "err_unsupported": "Link não suportado.",
        "err_network": "Falha de conexão. Verifique a internet e tente de novo.",
        "err_partial": "Alguns itens não puderam ser baixados.",
        "err_generic": "{msg}",
        "the_browser": "navegador",
        # histórico
        "hist_search": "Buscar nos vídeos baixados...",
        "btn_clear_history": "Limpar lista",
        "hist_empty": "Nada por aqui ainda.",
        "hist_missing_file": "arquivo não está mais no computador",
        "btn_folder": "Pasta",
        "btn_redownload": "Baixar de novo",
        "btn_delete": "Excluir",
        "clear_history_confirm": ("Limpar toda a lista de vídeos baixados?\n\n"
                                  "Os arquivos NÃO são apagados do computador. Para apagar um arquivo, "
                                  "use o botão Excluir do vídeo."),
        "delete_error": "Não foi possível apagar o arquivo:\n{path}\n\n{err}\n\nFeche o vídeo se ele estiver aberto e tente de novo.",
        "deleted_to_trash": "Arquivo enviado para a Lixeira: {name}",
        "removed_from_list": "Removido da lista (o arquivo continua no computador).",
        # diálogo excluir
        "del_title": "Excluir vídeo",
        "del_question": "Excluir este vídeo?",
        "del_warning": ("⚠  \"Apagar arquivo\" REMOVE o vídeo do seu computador (ele vai para a Lixeira) "
                        "e tira da lista.\n\"Só da lista\" mantém o arquivo no computador."),
        "del_no_file": "O arquivo não está mais no computador, então só dá para remover da lista.",
        "btn_only_list": "Só da lista",
        "btn_delete_file": "Apagar arquivo",
        # configurações
        "sec_language": "Idioma",
        "language_label": "Idioma da interface:",
        "sec_folder": "Pasta de destino",
        "sec_folder_desc": "Onde os vídeos e áudios são salvos. Playlists ganham uma subpasta com o nome da playlist.",
        "btn_choose": "Escolher...",
        "choose_folder_title": "Escolha onde salvar os vídeos",
        "sec_login": "Login do YouTube (cookies)",
        "sec_login_desc": ("Use o login do seu navegador para baixar vídeos que pedem confirmação "
                           "('não sou um robô'), com restrição de idade ou de membros. Os cookies são "
                           "lidos só no seu computador."),
        "browser_label": "Navegador:",
        "browser_none": "Nenhum (sem login)",
        "browser_file": "Arquivo cookies.txt",
        "detected": "(detectado)",
        "btn_test_login": "Testar login",
        "file_label": "Arquivo:",
        "cookie_placeholder": "caminho do cookies.txt",
        "all_files": "Todos",
        "login_tip": ("Dica: Chrome, Edge, Opera e Opera GX bloqueiam os cookies enquanto estão abertos — "
                      "o app oferece fechar o navegador antes de baixar. Se a leitura falhar, use o Firefox "
                      "ou exporte um cookies.txt com a extensão 'Get cookies.txt LOCALLY'."),
        "choose_browser_first": "Escolha um navegador primeiro.",
        "choose_cookie_file": "Escolha o arquivo cookies.txt.",
        "browser_open_test": "O {name} está aberto e precisa ser fechado para ler os cookies.\n\nFechar o {name} agora?",
        "testing": "Testando...",
        "ck_ok": "Login do YouTube encontrado ({n} cookies).",
        "ck_not_logged": "Cookies do YouTube encontrados, mas você não parece estar logado.",
        "ck_none": "Nenhum cookie do YouTube encontrado. Entre no youtube.com por esse navegador.",
        "ck_locked": "Não foi possível ler os cookies: feche o navegador por completo e tente de novo.",
        "ck_decrypt": ("O navegador criptografou os cookies e o yt-dlp não conseguiu lê-los. "
                       "Use Firefox ou exporte um arquivo cookies.txt."),
        "ck_error": "Erro ao ler cookies: {msg}",
        "sec_options": "Opções de download",
        "opt_metadata": "Gravar título, canal e capítulos no arquivo (metadados)",
        "opt_thumbnail": "Inserir miniatura (capa) no arquivo",
        "opt_clipboard": "Colar automaticamente links do YouTube copiados ao abrir o app",
        "sub_langs_label": "Idiomas das legendas:",
        "sec_components": "Componentes",
        "sec_components_desc": ("ffmpeg junta vídeo e áudio em alta qualidade e converte para MP3. "
                                "Deno (ou Node.js) resolve os desafios do YouTube — sem ele aparece "
                                "'formato não disponível'."),
        "btn_install": "Instalar",
        "btn_recheck": "Verificar de novo",
        "dep_missing": "✗  não encontrado",
        "dep_node_optional": "não encontrado (opcional se o Deno estiver instalado)",
        "no_winget": ("O winget não foi encontrado.\nInstale o 'Instalador de Aplicativo' (App Installer) "
                      "pela Microsoft Store e tente de novo."),
        "installing": "Instalando: {names} (pode levar alguns minutos)...",
        "installed_ok": "{name}: instalado ✓",
        "installed_fail": "{name}: não foi possível confirmar a instalação",
        "all_ready": "Tudo pronto! ✓",
        "sec_appearance": "Aparência e atualizações",
        "theme_system": "Sistema",
        "theme_light": "Claro",
        "theme_dark": "Escuro",
        "version": "Versão {v}",
        "btn_check_updates": "Verificar atualizações",
        "btn_project_page": "Página do projeto",
        "checking_updates": "Verificando atualizações...",
        "update_error": "Não foi possível verificar atualizações.\n{err}",
        "update_available": "Nova versão disponível: {tag}\n(você tem {v})\n\nAbrir a página de download?",
        "up_to_date": "Você já está na versão mais recente ({v}).",
        "save_error": "Não foi possível salvar as configurações: {err}",
        "close_busy": "Ainda há downloads em andamento. Fechar mesmo assim?",
    },
    "en": {
        "app_name": "YouTube Downloader",
        "tab_download": "Download",
        "tab_history": "Downloaded videos",
        "tab_settings": "Settings",
        "url_placeholder": "Paste the video or playlist link here (you can paste several at once)",
        "btn_paste": "Paste",
        "btn_download": "Download",
        "chk_playlist": "Whole playlist",
        "chk_subtitles": "Subtitles",
        "login_browser": "Login: {name}  ⚙",
        "login_file": "Login: cookies.txt  ⚙",
        "login_none": "Login: none  ⚙",
        "btn_install_now": "Install now",
        "queue_title": "Download queue",
        "queue_empty": "No downloads yet.\nPaste a link above and click Download.",
        "save_to": "Save to:",
        "btn_open": "Open",
        "btn_change_folder": "Change folder...",
        "btn_clear_finished": "Clear finished",
        "invalid_url": "Paste a valid link (starting with http).",
        "browser_open_download": ("{name} is open. To read your YouTube login it must be closed.\n\n"
                                  "Yes: close {name} now and download\n"
                                  "No: download anyway (may cause a cookie error)\n"
                                  "Cancel: don't download now"),
        "missing_banner": "Missing components: {names}. Without them some videos fail or download in low quality.",
        "q_best": "Video — best quality",
        "q_1080": "Video — up to 1080p",
        "q_720": "Video — up to 720p",
        "q_480": "Video — up to 480p",
        "q_mp3": "Audio — MP3",
        "q_m4a": "Audio — M4A (no conversion)",
        "btn_cancel": "Cancel",
        "btn_open_folder": "Open folder",
        "btn_retry": "Retry",
        "btn_remove": "Remove",
        "st_queued": "Queued",
        "st_starting": "Starting...",
        "st_downloading": "Downloading",
        "st_downloading_audio": "Downloading (audio)",
        "st_processing": "Processing...",
        "st_merging": "Merging video and audio...",
        "st_converting": "Converting to MP3...",
        "st_thumbnail": "Embedding thumbnail...",
        "st_metadata": "Writing metadata...",
        "st_subtitles": "Embedding subtitles...",
        "st_done": "Done ✓",
        "st_cancelled": "Cancelled",
        "st_error": "Error: {msg}",
        "item_n": "item {n}",
        "eta": "{eta} left",
        "done_status": "Done: {title}",
        "failed_status": "A download failed — see the reason in the queue.",
        "err_login": ("YouTube asked for a login. In Settings, choose the browser where you are "
                      "logged in to YouTube and click 'Test login'."),
        "err_cookie_copy": "Could not read the cookies: fully close {browser} and try again.",
        "err_decrypt": "The browser encrypted its cookies. Use Firefox or a cookies.txt file (Settings).",
        "err_no_format": "No formats available. Install Deno in Settings › Components, reopen the app and try again.",
        "err_private": "Private video: only works with the login of an account that has access.",
        "err_age": "Age-restricted video: set up the browser login in Settings.",
        "err_unavailable": "Video unavailable (removed, blocked or region-restricted).",
        "err_unsupported": "Unsupported link.",
        "err_network": "Connection failed. Check your internet and try again.",
        "err_partial": "Some items could not be downloaded.",
        "err_generic": "{msg}",
        "the_browser": "the browser",
        "hist_search": "Search downloaded videos...",
        "btn_clear_history": "Clear list",
        "hist_empty": "Nothing here yet.",
        "hist_missing_file": "file is no longer on this computer",
        "btn_folder": "Folder",
        "btn_redownload": "Download again",
        "btn_delete": "Delete",
        "clear_history_confirm": ("Clear the whole list of downloaded videos?\n\n"
                                  "Files are NOT deleted from your computer. To delete a file, "
                                  "use the video's Delete button."),
        "delete_error": "Could not delete the file:\n{path}\n\n{err}\n\nClose the video if it is open and try again.",
        "deleted_to_trash": "File moved to the Recycle Bin: {name}",
        "removed_from_list": "Removed from the list (the file is still on your computer).",
        "del_title": "Delete video",
        "del_question": "Delete this video?",
        "del_warning": ("⚠  \"Delete file\" REMOVES the video from your computer (it goes to the Recycle Bin) "
                        "and from the list.\n\"List only\" keeps the file on your computer."),
        "del_no_file": "The file is no longer on this computer, so it can only be removed from the list.",
        "btn_only_list": "List only",
        "btn_delete_file": "Delete file",
        "sec_language": "Language",
        "language_label": "Interface language:",
        "sec_folder": "Download folder",
        "sec_folder_desc": "Where videos and audio are saved. Playlists get a subfolder named after the playlist.",
        "btn_choose": "Choose...",
        "choose_folder_title": "Choose where to save the videos",
        "sec_login": "YouTube login (cookies)",
        "sec_login_desc": ("Use your browser's login to download videos that ask for confirmation "
                           "(\"I'm not a robot\"), age-restricted or members-only videos. Cookies are read "
                           "only on your computer."),
        "browser_label": "Browser:",
        "browser_none": "None (no login)",
        "browser_file": "cookies.txt file",
        "detected": "(detected)",
        "btn_test_login": "Test login",
        "file_label": "File:",
        "cookie_placeholder": "path to cookies.txt",
        "all_files": "All files",
        "login_tip": ("Tip: Chrome, Edge, Opera and Opera GX lock their cookies while open — the app offers "
                      "to close the browser before downloading. If reading fails, use Firefox or export a "
                      "cookies.txt with the 'Get cookies.txt LOCALLY' extension."),
        "choose_browser_first": "Choose a browser first.",
        "choose_cookie_file": "Choose the cookies.txt file.",
        "browser_open_test": "{name} is open and must be closed to read the cookies.\n\nClose {name} now?",
        "testing": "Testing...",
        "ck_ok": "YouTube login found ({n} cookies).",
        "ck_not_logged": "YouTube cookies found, but you don't seem to be logged in.",
        "ck_none": "No YouTube cookies found. Sign in to youtube.com with this browser.",
        "ck_locked": "Could not read the cookies: fully close the browser and try again.",
        "ck_decrypt": ("The browser encrypted its cookies and yt-dlp could not read them. "
                       "Use Firefox or export a cookies.txt file."),
        "ck_error": "Error reading cookies: {msg}",
        "sec_options": "Download options",
        "opt_metadata": "Write title, channel and chapters into the file (metadata)",
        "opt_thumbnail": "Embed thumbnail (cover) into the file",
        "opt_clipboard": "Automatically paste copied YouTube links when the app gets focus",
        "sub_langs_label": "Subtitle languages:",
        "sec_components": "Components",
        "sec_components_desc": ("ffmpeg merges high-quality video and audio and converts to MP3. "
                                "Deno (or Node.js) solves YouTube's challenges — without it you get "
                                "'format not available'."),
        "btn_install": "Install",
        "btn_recheck": "Check again",
        "dep_missing": "✗  not found",
        "dep_node_optional": "not found (optional if Deno is installed)",
        "no_winget": ("winget was not found.\nInstall 'App Installer' from the Microsoft Store and try again."),
        "installing": "Installing: {names} (this may take a few minutes)...",
        "installed_ok": "{name}: installed ✓",
        "installed_fail": "{name}: could not confirm the installation",
        "all_ready": "All set! ✓",
        "sec_appearance": "Appearance and updates",
        "theme_system": "System",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "version": "Version {v}",
        "btn_check_updates": "Check for updates",
        "btn_project_page": "Project page",
        "checking_updates": "Checking for updates...",
        "update_error": "Could not check for updates.\n{err}",
        "update_available": "New version available: {tag}\n(you have {v})\n\nOpen the download page?",
        "up_to_date": "You already have the latest version ({v}).",
        "save_error": "Could not save the settings: {err}",
        "close_busy": "Downloads are still running. Close anyway?",
    },
}


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in STRINGS else DEFAULT


def current() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    text = STRINGS.get(_current, {}).get(key) or STRINGS[DEFAULT].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def _installer_language() -> str:
    """Idioma escolhido no instalador (gravado no registro)."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BaixadorYouTube") as k:
            value, _ = winreg.QueryValueEx(k, "Language")
        return {"brazilianportuguese": "pt", "english": "en"}.get(value, value if value in STRINGS else "")
    except OSError:
        return ""


def _system_language() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "pt" if (langid & 0x3FF) == 0x16 else "en"
        except Exception:
            pass
    try:
        loc = (locale.getlocale()[0] or "").lower()
    except Exception:
        loc = ""
    return "pt" if loc.startswith("pt") else "en"


def detect_default() -> str:
    """Idioma inicial: o escolhido no instalador; senão o idioma do Windows."""
    return _installer_language() or _system_language()
