# CLAUDE.md: base de conhecimento do VidNeon

> Leia este arquivo antes de mexer no projeto e **atualize-o** sempre que mudar a arquitetura, uma regra ou uma
> decisão registrada aqui (o autor pediu isso explicitamente).

## O que é

**VidNeon** (antes "Baixador de YouTube") é um app desktop **gratuito para Windows** que baixa vídeos e áudios do
YouTube (e de outros sites suportados) usando o **yt-dlp**, com interface em **CustomTkinter**, Biblioteca,
player com fila (estilo Spotify) e instalador.

- Repositório: `GuiSysLima/desktube-downloader` (GitHub). Pasta local do autor: `C:\PROJETOS\baixador-youtube`.
- Autor: **Guilherme Felix (GuiSysLima)**. Licença **GPL-3.0-only** + termos adicionais (seção 7 b/c/e) no `NOTICE`:
  o crédito "VidNeon by Guilherme Felix (GuiSysLima)" + URL do projeto é obrigatório em versões derivadas.
- Idiomas: português (padrão) e inglês.

## Preferências do autor (como trabalhar)

- Conversar em **português**.
- Seguir as melhorias **em ordem**, terminando uma antes da próxima.
- Mudanças grandes de UI/UX: apresentar o plano e **esperar aprovação** antes de alterar o código.
- Paleta (opção A, depois deixada mais "viva" a pedido): **rosa neon `#F0145A`** (ação principal, com contorno
  `primary_glow` no tema escuro) + **violeta neon** `accent` (`#8B3DFF` claro / `#A23BFF` escuro) para seleção,
  progresso e foco. Texto em violeta usa **`accent_text`** (`#7A2EF0` / `#C38BFF`) para manter contraste ≥ 4.5:1.
- Design "autêntico", sem cara de template de IA: listas sem bordas, divisórias finas, grupos de configuração
  no estilo Windows 11, sem ícones decorativos em todo título, sem gradientes nem emojis na interface.
- Assuntos jurídicos (licença etc.): lembrar que **não sou advogado**.
- **Nunca** commitar `cookies.txt` (está no `.gitignore`).
- Commits: padrão **Conventional Commits** com descrição em português no infinitivo, como já está no histórico
  (ex.: `feat: adicionar fila de reprodução`, `fix: detectar ffmpeg instalado pelo winget`, `chore: ...`,
  `docs: ...`, `build: ...`), com corpo em tópicos quando a mudança é grande.
- Versões (SemVer): funcionalidade nova compatível → sobe o MINOR (`v2.0.0` → `v2.1.0`); só correções → PATCH
  (`v2.1.1`); mudança incompatível (ex.: dados antigos deixam de abrir) → MAJOR.

## Estrutura

```
app/
  __init__.py    APP_NAME, AUTHOR, PROJECT_URL, GITHUB_REPO, __version__ (sobrescritos por _build_info.py no build)
  main.py        ponto de entrada (AppUserModelID "VidNeon.App"; stdout/stderr nulos no .exe)
  gui.py         App (janela), Sidebar, NavItem; integra páginas, player, componentes, atualizações e eventos
  ui/common.py   regex de URL, qualidades, open_path/reveal, split_msg, ellipsize
  ui/download.py DownloadPage + JobRow (fila de downloads)
  ui/library.py  LibraryPage (abas Tudo/Playlists, página da playlist), LibraryRow, PlaylistRow, group_playlists
  ui/playing.py  PlayingPage (vídeo/capa + fila) e PlayerBar (barra fixa no rodapé, em todas as telas)
  ui/settings.py SettingsPage (abas Geral/Login/Componentes/Sobre com SettingsGroup)
  downloader.py  fila de downloads (thread) + yt-dlp; grava 1 registro por item no histórico
  player.py      motor de reprodução: Playback (fila, shuffle, repeat, VLC); load_vlc seguro
  covers.py      capa personalizada: miniatura no app, folder.jpg na pasta, embutir no arquivo (ffmpeg)
  motion.py      animações: tokens de duração/easing, animate(), fade_color(), fade_in_window()
  updater.py     checagem de atualização (GitHub Releases), download e execução do instalador
  deps.py        ffmpeg / Deno / Node / VLC: detecção robusta, winget install/uninstall, diagnose()
  browsers.py    navegadores, cookies (cookiesfrombrowser), Opera GX, teste de login
  config.py      Settings (config.json), histórico (historico.json), migração de %APPDATA%\BaixadorYouTube
  thumbs.py      miniaturas 320x180 em cache (%APPDATA%\VidNeon\thumbs)
  i18n.py        STRINGS["pt"/"en"], t(key, **kw), idioma do instalador (registro)
  theme.py       design tokens (C, RADIUS, SP, TYPE, THUMB...), fonte, glifos Segoe Fluent Icons
  widgets.py     componentes: button, IconButton, ThumbBox, HoverRow, TabBar, SettingsGroup, Toast,
                 ChoiceDialog, TextDialog, Tooltip, divider, apply_icon, flash_window
assets/          icon.ico / icon.png
build.ps1        build local (PyInstaller + Inno Setup)
installer.iss    instalador Inno Setup (pt/en), AppId fixo {8F2C5B1E-6A4D-4C3B-9E7A-2D1F0B5C9A11}
LICENSE, NOTICE  GPL-3.0 e termos adicionais/terceiros (vão dentro do .exe e no instalador)
```

Dados do usuário: `%APPDATA%\VidNeon\` → `config.json`, `historico.json`, `thumbs\`, `app.log`.

## Regras de arquitetura

- **Threads nunca tocam em widgets.** Trabalho em segundo plano manda eventos para `app.events`
  (`("job", ...)`, `("install_log", ...)`, `("toast", ...)`, `("update_progress", ...)`...), processados em
  `App._poll()` a cada 100 ms. Para "roda isto e depois chama aquilo": `app._bg(func, callback)`.
- O **player** (`player.Playback`) é usado **só na thread principal**; `App._tick()` (250 ms) chama
  `playback.tick()` (avança ao terminar) e `bar.tick()`. Mudanças da fila chamam `on_change` →
  `App._on_playback_change()` (agrupa redesenhos com `after(30)`).
- As páginas só chamam métodos públicos do `App` (ex.: `play_entries`, `queue_entry`, `change_cover`,
  `start_download`, `dep_action`, `locate_dep`, `check_updates`). Não acessar outra página diretamente
  sem passar pelo App, exceto refresh simples (`app.pages["download"].refresh_login()`).
- Trocar o idioma recria toda a interface (`_build_ui`); o player continua (o handle do vídeo é reatribuído).
- O vídeo é desenhado num `tk.Frame` da página Reproduzindo (`video_handle()` → `set_hwnd`). Ao tocar um vídeo, o
  app abre essa página. Tela cheia (botão da barra, F11 ou duplo clique): some a barra lateral e a fila; a barra do
  player passa a **flutuar sobre o vídeo** (`place`), aparece ao mexer o mouse e some após 2,5 s (o cursor também).
  O botão vira "Sair da tela cheia"; Esc também sai. Ao sair, o ícone da janela é reaplicado (`apply_icon`).
- Botão "Fila" da barra alterna: abre Reproduzindo e, clicando de novo, volta para a tela anterior (`_prev_page`).

## Desempenho (regras que evitam a lentidão da v2.1.0)

- Widgets do CustomTkinter custam ~10 ms cada (desenham num Canvas). **Listas grandes usam Tk puro**:
  `widgets.LightRow` / `LightThumb` (fila de reprodução e Biblioteca), com fontes `tk_font()`/`tk_icon_font()`
  já na escala de DPI, cores resolvidas com `motion.resolve()` e recoloração automática ao trocar claro/escuro.
- A fila **reaproveita** as linhas (`QueueRow.set_item`) e só redesenha se a assinatura da fila mudou; desenha
  `VISIBLE` (40) itens por vez com "Mostrar mais".
- Telas escondidas não são redesenhadas: marcam "sujo" e atualizam ao abrir (`_playing_dirty`, `_lib_dirty`).
  Na Biblioteca, trocar a música só muda o destaque (`set_playing`), sem recriar a lista.
- `PlayerBar._set()` só reconfigura um widget quando o valor muda (o tick roda a cada 250 ms).
- `deps.find()` tem cache (`deps.invalidate()` ao reler o PATH, instalar/desinstalar ou Localizar…).
- VLC com `--avcodec-hw=any --no-osd` (cai para as opções básicas se a versão não aceitar).
- Arrastar para reordenar a fila: limiar de 6 px, indicador de inserção, rolagem automática perto das bordas e
  "flash" no item ao soltar. Durante o arraste a fila não é redesenhada.

## Histórico e Biblioteca

- Cada item baixado vira uma entrada: `id, when, title, url, quality, filepath, thumb, folder, channel,
  playlist, playlist_id` (+ `custom_thumb`, `playlist_cover` quando o usuário troca a capa).
- Playlists: **um registro por item** (`add_history_many`, na ordem da playlist). Itens antigos sem `playlist`
  são agrupados pela subpasta dentro da pasta de destino (`playlist_of`).
- "Artista" exibido no player = canal (`channel`/`uploader`).
- Baixar de novo o mesmo arquivo substitui o registro e **mantém a capa personalizada**.
- Limite do histórico: `HISTORY_LIMIT` (2000).

## Componentes (ffmpeg, Deno, Node, VLC)

- O winget instala ffmpeg e Deno como pacotes **portáteis**: só cria um link em
  `%LOCALAPPDATA%\Microsoft\WinGet\Links`; o .exe real fica em `...\WinGet\Packages\<Id>_*`. Alguns Pythons
  (ex.: o da Microsoft Store) não enxergam esses links. Por isso `deps.locate()` procura nesta ordem:
  caminho escolhido pelo usuário (`CUSTOM_PATHS` ← `settings.component_paths`) → `shutil.which` →
  WinGet Links (seguindo o link) → globs em `SEARCH` (WinGet Packages, Program Files, Scoop, Chocolatey).
  Quando acha, coloca a pasta no PATH do processo (o yt-dlp e o ffmpeg do thumbs passam a achar).
- Se algo não for encontrado, `deps.diagnose(name)` lista onde procurou (vai para o registro da instalação e
  para o `app.log`); o botão **Localizar…** permite apontar o executável manualmente.
- O downloader passa o caminho do Deno/Node ao yt-dlp via `js_runtimes` (desafios JS do YouTube).
- VLC: `player.load_vlc()` testa a DLL antes e captura `BaseException` (o python-vlc pode chamar `sys.exit`).
  `player.reset()` depois de instalar/localizar o VLC.

## Atualizações

- `updater.fetch_latest()` consulta `https://api.github.com/repos/<repo>/releases/latest` (404 → `NoReleases`).
- Versões: tags SemVer `vX.Y.Z`. Build fora de tag (`git describe` devolve hash) = **versão de desenvolvimento**:
  `compare()` devolve `"dev"` e o app não oferece "atualizar" (o antigo bug comparava o hash como número).
- Instalado (`sys.frozen`, Windows) + Release com o asset `VidNeon-Setup.exe`: baixa para `%TEMP%` e roda o
  instalador (mesmo AppId → atualiza no lugar). Senão, abre a página da Release.
- Checagem automática 1x/dia (`auto_update_check`, `last_update_check`); ao achar, mostra "vX disponível" no
  rodapé da barra lateral (clicável). Não checa em versão de desenvolvimento.

## Design system (theme.py / widgets.py)

- Use sempre os tokens: `C[...]` (cores claro/escuro), `RADIUS` (button 6, input 6, card 8, thumb 4),
  `SP` (4/8/12/16/24/32), `font(kind)` com `TYPE` (title 24, section 15, row/body/label 13, meta 12, small 11).
- Fonte: Segoe UI (Semibold para "forte"); variável de ambiente `BAIXADOR_FONT` troca a família (testes).
- Ícones: glifos da **Segoe Fluent Icons** em `GLYPHS`, escritos como escapes `\uXXXX`. **Nunca** gravar o caractere
  PUA literal no código (a ferramenta de escrita converte; confira com uma busca por caracteres U+E000–U+F8FF = 0).
- Listas: `HoverRow` (sem borda, destaca no hover, duplo clique/botão direito). Configurações: `SettingsGroup`.
  Abas: `TabBar` (texto + sublinhado). Botões: `button(style=primary|accent|secondary|ghost|danger|danger_ghost)`.
- `ChoiceDialog`: o Enter **não** aciona botão destrutivo (`danger`). Botões dizem a ação ("Apagar arquivo").
- O CustomTkinter troca o ícone da janela ~200 ms depois de criar; `apply_icon` reaplica após 300 ms.
- `corner_radius` em `button`/`IconButton` pode ser sobrescrito (ex.: botão redondo "Tocar tudo" = 22).

## Animações (motion.py)

- Tokens: `DUR` micro 110 ms (hover), short 180 ms (progresso, diálogo), medium 240 ms (aba, aviso); saída =
  `EXIT` (65%) da entrada. Curvas iguais às do anime.js (outCubic, inCubic, inOutCubic, outExpo, outBack).
- **anime.js não é usado**: é uma biblioteca JavaScript para páginas web e não roda em Tkinter; só as fórmulas
  de easing foram reproduzidas em `motion.py`.
- Onde há animação (com significado, 1–2 por tela): hover de linhas e da barra lateral (transição de cor),
  sublinhado das abas deslizando (`TabBar`), aviso (`Toast`) entrando/saindo de baixo, barra de progresso
  avançando suave, diálogos com fade-in (alpha da janela).
- `motion.animate(widget, chave, ms, step)` é interrompível (nova chamada na mesma chave cancela a anterior) e
  sempre aplica o estado final. Não animar largura/altura de layout (só `place` de elementos soltos e cores).
- Desligável em Configurações › Geral › Animações (`settings.animations`) e desligada automaticamente se o
  Windows estiver com "Mostrar animações" desligado (`SPI_GETCLIENTAREAANIMATION`).
- `Toast.show` com o mesmo tipo já visível só troca o texto (avisos de progresso não ficam "pulando").
- O CTkFrame não aceita `width`/`height` no `place()`: para elementos com largura animada, use `tk.Frame`.

## i18n

- Toda string visível passa por `t("chave")`; a chave **tem de existir em `pt` e `en`** com os mesmos
  placeholders `{x}`. Mensagens "Pergunta?\n\nExplicação" usam `split_msg`.
- Conferir cobertura: varrer `t("...")`/`split_msg("...")` em `app/**/*.py` e comparar com `STRINGS` (há chaves
  dinâmicas: `qs_*`, `q_*`, `theme_*`, `set_*`, `nav_*`, `dep_desc_*`, `kind_*`, `opt_*_desc`).

## Build e release

- `build.ps1`: `git fetch --tags`, versão via `git describe --tags --always`, repo pelo remote `origin`, gera
  `app/_build_info.py`; PyInstaller onefile `--name VidNeon --icon assets\icon.ico --add-data "assets;assets"
  --add-data "LICENSE;." --add-data "NOTICE;." --collect-all customtkinter --collect-all yt_dlp_ejs`;
  Inno Setup (se instalado) gera `dist\VidNeon-Setup.exe`.
- O GitHub Actions da conta está **bloqueado por cobrança** → o autor faz o build local e anexa
  `VidNeon.exe` / `VidNeon-Setup.exe` na Release manualmente. Para a versão sair certa, criar a tag
  (`git tag v2.1.0 && git push origin v2.1.0`) **antes** de rodar o build e conferir em Sobre que o app mostra
  "Versão v2.1.0" (e não um hash de commit).
- **Build só com a árvore limpa e no commit da tag.** Incidente da 2.2.0: o build foi feito com as alterações
  ainda sem commit, com o HEAD na tag v2.1.0 → `git describe` deu `v2.1.0` → o instalador anexado na Release
  v2.2.0 dizia ser 2.1.0, e o app atualizado continuava se achando 2.1.0. Agora o `build.ps1` **recusa** gerar com
  alterações pendentes (`-Force` só para teste, versão vira `...-dirty`) e avisa quando não está numa tag.
- O app confere o instalador baixado: `updater.installer_matches()` lê a "ProductVersion" do .exe (o Inno
  Setup grava a AppVersion ali; o número fixo fica 0.0.0.0) e cancela se não bater com a tag da Release.
- O asset do instalador na Release tem de se chamar exatamente **`VidNeon-Setup.exe`** (é o que o atualizador
  procura) e a Release não pode ser rascunho nem pré-lançamento (a API `releases/latest` ignora essas).
- As ~10 primeiras linhas das notas da Release aparecem no diálogo "Nova versão disponível": comece pelo resumo.
- Atenção: a Release v2.0.0 foi gerada antes da tag existir no clone local, então provavelmente se identifica como
  `b01330d`, e o botão antigo dela não avisa de versões novas. Quem tem a 2.0.0 precisa instalar a 2.1.0 uma vez
  manualmente (o instalador atualiza no lugar e mantém os dados); daí em diante a atualização é pelo app.

## Testes (ambiente da IA, Linux)

- Python 3.12 do uv; CustomTkinter, darkdetect, packaging e yt-dlp clonados do GitHub (o PyPI é bloqueado) e
  passados via `PYTHONPATH`.
- Interface: Xvfb com fontes X "core" (DejaVu em `/tmp/xfonts`, `-fp`) e `BAIXADOR_FONT="dejavu sans"`;
  screenshots com `import -window root`. Cantos arredondados aparecem serrilhados no Xvfb (só no teste).
- VLC falso (`vlc.py` com `State`, `Instance`, `MediaPlayer` mínimos) no `PYTHONPATH` para testar o player.
- Sempre: `python -m py_compile app/*.py app/ui/*.py`, checagem de chaves i18n, zero caracteres PUA,
  screenshots claro/escuro e pt/en das telas alteradas.

## Cabeçalho obrigatório dos .py

```python
# VidNeon — Copyright (C) 2026 Guilherme Felix (GuiSysLima)
# SPDX-License-Identifier: GPL-3.0-only
# Licença: veja LICENSE e NOTICE (termos adicionais de atribuição, seção 7 da GPL-3.0).
```

## Histórico de decisões

- v1.0.0: primeira versão ("Baixador de YouTube").
- v2.0.0: rebranding para VidNeon, nova UI, player VLC, GPL-3.0 + NOTICE, migração de dados da v1.
- Pós-2.0.0 (correções do arquivo "Correções - VidNeon"): detecção robusta de componentes + Localizar…,
  atualização funcional, player integrado com fila estilo Spotify e barra fixa em todas as telas, aba Playlists
  com troca de capa, redesign sem "cara de IA", versão com ícone centralizada no rodapé, este CLAUDE.md,
  animações (motion.py) e cores neon mais vivas (v2.1.0).
- v2.2.0: desempenho (linhas em Tk puro, fila reaproveitada, telas preguiçosas), arrastar para reordenar a fila,
  controles flutuantes na tela cheia, botão Fila que alterna, easings no estilo anime.js.
