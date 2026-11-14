<p align="center"><img src="assets/icon.png" width="128" alt="ícone"></p>

# VidNeon

**Baixe vídeos e áudios** — grátis, sem anúncios e de código aberto.

![Licença: GPL-3.0](https://img.shields.io/badge/licen%C3%A7a-GPL--3.0-7C3AED)

**Português** · [English](README.en.md)

Aplicativo desktop para Windows, gratuito, sem anúncios e de código aberto, para baixar vídeos e áudios do YouTube (e de centenas de outros sites) com poucos cliques.

---

## O problema

Baixar um vídeo do YouTube deveria ser simples, mas na prática:

- **Os sites de download** cobram créditos ou assinatura, enchem a tela de anúncios e pop-ups, limitam a qualidade ou obrigam a instalar um app que ninguém sabe de onde vem.
- **As ferramentas gratuitas e confiáveis**, como o [yt-dlp](https://github.com/yt-dlp/yt-dlp), funcionam muito bem, mas só pelo terminal. Para quem não é técnico, configurar formatos, cookies e dependências é complicado.
- **O YouTube bloqueia downloads com frequência.** Os erros mais comuns são:
  - *"Sign in to confirm you're not a bot"*: o YouTube exige login.
  - *"Requested format is not available"*: o YouTube passou a exigir um interpretador de JavaScript para liberar os formatos.
  - Vídeos com restrição de idade ou só para membros, que também exigem login.
- **Para usar o login nessas ferramentas**, é preciso exportar cookies do navegador. Além disso, navegadores como Chrome, Edge e Opera GX bloqueiam o arquivo de cookies enquanto estão abertos, e o erro resultante não explica o que fazer.

## A solução

O VidNeon coloca o yt-dlp atrás de uma interface simples e resolve sozinho os problemas acima:

| Problema | Como o app resolve |
|---|---|
| Sites pagos ou cheios de anúncios | Roda localmente, é gratuito e não tem anúncios nem limites. |
| Linha de comando é difícil | Basta colar o link, escolher a qualidade e clicar em **Baixar**. |
| "Não sou um robô", restrição de idade | Usa o login que você já tem no navegador (Opera GX, Opera, Chrome, Edge, Brave, Vivaldi, Firefox) ou um `cookies.txt`. O botão **Testar login** confirma se está funcionando. |
| Navegador bloqueando os cookies | Detecta que o navegador está aberto e oferece fechá-lo antes de baixar. |
| "Formato não disponível" | Verifica se o Deno (ou o Node.js) está instalado e instala com um clique pelo `winget`. |
| Componentes difíceis de instalar e remover | A tela *Componentes* instala e desinstala o ffmpeg, o Deno, o Node.js e o VLC com um clique. |
| Qualidade baixa e falta de MP3 | Verifica se o ffmpeg está instalado e instala com um clique. Com ele, o app junta vídeo e áudio em alta qualidade e converte para MP3. |
| Mensagens de erro em inglês técnico | Traduz cada erro numa explicação do que fazer, em português ou inglês. |
| O YouTube mudou e o app parou de funcionar | Cada versão nova do app é compilada com o yt-dlp mais recente, e o app avisa quando há atualização. |

## Funcionalidades

- **Fila de downloads**: dá para colar vários links de uma vez. Cada item mostra a miniatura, o progresso, a velocidade e o tempo restante, e pode ser cancelado ou baixado novamente.
- **Qualidade**: melhor disponível, 1080p, 720p, 480p, MP3 ou M4A.
- **Playlists inteiras**, salvas numa subpasta com o nome da playlist.
- **Legendas** no idioma que você escolher, inseridas direto no vídeo.
- **Preview com miniatura** de cada vídeo ou áudio, na fila e na lista, mesmo com a opção de inserir capa desligada. Para arquivos antigos, a miniatura é gerada a partir do próprio arquivo.
- **Player e fila de reprodução** (no estilo do Spotify): vídeos e áudios tocam dentro do app. Uma barra fixa no rodapé, presente em todas as telas, mostra a capa, o título e o canal, com aleatório, repetir, barra de tempo e volume. A tela **Reproduzindo** mostra o vídeo (ou a capa do áudio) e a fila, que pode ser reordenada. Na Biblioteca: *Tocar*, *Tocar a seguir* e *Adicionar à fila*. Usa o VLC; sem ele, o arquivo abre no player do Windows.
- **Playlists**: cada item de uma playlist baixada entra na Biblioteca com o canal e o nome da playlist. A aba *Playlists* permite tocar a playlist inteira e **trocar a capa**, que é aplicada no app, como `folder.jpg` na pasta e, se você quiser, dentro dos arquivos (.mp3, .m4a, .mp4).
- **Metadados e capa** (título, canal, capítulos e miniatura) gravados no arquivo.
- **Pasta de destino** visível na tela principal, com botões para abrir e trocar.
- **Biblioteca**: lista dos vídeos baixados (título, canal, formato e data), com busca e botões para reproduzir, abrir a pasta, baixar novamente ou excluir. Se o arquivo ainda estiver na pasta, "Baixar novamente" pergunta se você quer reproduzir o arquivo atual ou substituí-lo. Ao excluir, você escolhe entre remover **só da lista** ou **apagar o arquivo**; o arquivo vai para a Lixeira e o app avisa antes de apagar.
- **Cola o link sozinho** quando você copia um link do YouTube e volta para o app.
- **Idiomas**: português e inglês, com troca na hora em *Configurações › Geral*.
- **Interface** no estilo Windows 11: barra lateral, listas sem bordas, configurações agrupadas, tema claro e escuro, cores da marca (rosa neon e violeta) e ícones nativos do Windows (Segoe Fluent Icons).
- **Animações** discretas (hover, troca de aba, avisos, progresso), que respeitam a opção do Windows de reduzir animações e podem ser desligadas em *Configurações › Geral*.
- **Atualizações**: *Configurações › Sobre › Verificar atualizações* compara a sua versão com a última Release do GitHub e, no app instalado, baixa e roda o instalador novo. A checagem automática (uma vez por dia) pode ser desligada.
- **Atalhos**: Ctrl+V cola o link e já começa a baixar · Ctrl+L vai para o campo de link · Ctrl+1/2/3/4 alternam entre Baixar, Biblioteca, Reproduzindo e Configurações · Espaço pausa/continua · F11 tela cheia (vídeo) · Esc sai da tela cheia.
- **Tema** claro, escuro ou igual ao do sistema.
- **Instalador** em português ou inglês, com escolha da pasta de instalação.

## Como funciona

```mermaid
flowchart LR
    U[Usuário cola o link] --> GUI[Interface<br/>CustomTkinter]
    GUI -->|fila| DL[Downloader<br/>thread em segundo plano]
    DL --> Y[yt-dlp]
    B[(Cookies do navegador<br/>ou cookies.txt)] -->|login| Y
    J[Deno / Node.js] -->|desafios JS do YouTube| Y
    Y -->|vídeo + áudio| F[ffmpeg<br/>junta, converte, insere capa/legendas]
    F --> P[(Pasta de destino)]
    DL -->|progresso e erros| GUI
    DL --> H[(Histórico<br/>%APPDATA%)]
```

1. **Interface** (`app/gui.py`): recebe os links e coloca cada um na fila. A interface nunca trava, porque os downloads rodam em outra thread e mandam o progresso por uma fila de eventos.
2. **Downloader** (`app/downloader.py`): monta as opções do yt-dlp de acordo com as configurações (formato, login, legendas, pós-processamento) e baixa um item por vez. Se o formato ideal não existir, tenta alternativas (MP4+M4A → qualquer vídeo+áudio → arquivo único).
3. **Login** (`app/browsers.py`): detecta os navegadores instalados e lê os cookies **localmente**, com o leitor do próprio yt-dlp. O Opera GX tem uma pasta de perfil própria, que o app informa ao yt-dlp. Os cookies nunca saem do seu computador.
4. **Componentes** (`app/deps.py`): procura o ffmpeg, o Deno e o Node.js no PATH, nos atalhos do WinGet e nas pastas onde o winget, o Scoop e o Chocolatey instalam; instala os que faltarem com o `winget` e relê o PATH do Windows sem reiniciar. Se ainda assim algo não for encontrado, *Localizar…* permite apontar o executável, e o `app.log` registra onde o app procurou.
5. **Erros** (`friendly_error`): converte a mensagem técnica do yt-dlp numa orientação clara.
6. **Dados** (`app/config.py`): as configurações e o histórico ficam em `%APPDATA%\VidNeon` (`config.json` e `historico.json`). Na primeira execução da v2, os dados da v1 (`%APPDATA%\BaixadorYouTube`) são copiados automaticamente.
7. **Idiomas** (`app/i18n.py`): todos os textos ficam num dicionário por idioma. O idioma inicial é o escolhido no instalador; se não houver, é o idioma do Windows.

---

## Instalação

Na aba **Releases** do repositório há duas opções:

- **`VidNeon-Setup.exe`** (recomendado): instalador em português ou inglês. Se você já tem a v1 ("Baixador de YouTube"), ele atualiza a instalação existente. Deixa escolher a pasta de instalação, cria atalhos no Menu Iniciar e, se quiser, na Área de Trabalho, e aparece em *Configurações › Aplicativos* para desinstalar. Não pede senha de administrador.
- **`VidNeon.exe`** (portátil): roda direto, sem instalar.

Se aparecer o aviso do Windows SmartScreen, clique em *Mais informações* e depois em *Executar assim mesmo*. O app não tem assinatura digital paga.

### Primeiro uso

1. Se aparecer a faixa amarela "Faltam componentes", clique em **Instalar agora** para instalar o ffmpeg e o Deno.
2. Em **Configurações › Login**, escolha o navegador em que você está logado e clique em **Testar login**.
3. Na tela **Baixar**, cole o link, escolha a qualidade e clique em **Baixar**.

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "O YouTube pediu login" | Configure o navegador em que você está logado e clique em **Testar login**. |
| "Nenhum formato disponível" | Instale o Deno em **Configurações › Componentes** e reabra o app. |
| "Não foi possível ler os cookies" | Feche o navegador por completo (inclusive o ícone perto do relógio) ou use um `cookies.txt`. |
| "O navegador criptografou os cookies" | Use o Firefox ou exporte um `cookies.txt` com a extensão *Get cookies.txt LOCALLY*. |
| Vídeo em qualidade baixa | Instale o ffmpeg. |
| ffmpeg/Deno instalados, mas "Não encontrado" | Em **Configurações › Componentes**, clique em **Localizar…** e aponte o `.exe` (por exemplo, `%LOCALAPPDATA%\Microsoft\WinGet\Packages\...\ffmpeg.exe`). O `app.log` mostra onde o app procurou. |

---

## Para desenvolvedores

### Rodar pelo código-fonte

```powershell
git clone https://github.com/GuiSysLima/desktube-downloader.git
cd desktube-downloader
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

### Gerar o .exe e o instalador localmente

```powershell
.\build.ps1
```
O script gera o `dist\VidNeon.exe`. Se o Inno Setup estiver instalado (`winget install JRSoftware.InnoSetup`), gera também o `dist\VidNeon-Setup.exe`.

### Publicar uma versão (GitHub Actions)

O workflow `.github/workflows/build.yml` compila tudo numa máquina Windows do GitHub:

```powershell
git tag v2.0.0
git push origin v2.0.0
```
Depois de uns 5 minutos, a Release `v2.0.0` aparece com o instalador e o `.exe` portátil. Para testar sem publicar, use *Actions › Build Windows › Run workflow*.

### Adicionar um idioma

1. Em `app/i18n.py`, copie o dicionário `"en"` para um código novo (por exemplo, `"es"`), traduza os textos e inclua o idioma em `LANGUAGES`.
2. Em `installer.iss`, adicione o idioma em `[Languages]` e uma linha `<idioma>.AppName=` em `[CustomMessages]`. Depois, inclua o nome que o Inno Setup usa para esse idioma (por exemplo, `"spanish": "es"`) no mapeamento da função `_installer_language`, em `app/i18n.py`.

### Estrutura

```
app/
  main.py        ponto de entrada
  gui.py         janela principal: barra lateral, páginas, barra do player, eventos
  ui/            páginas: download.py, library.py, playing.py, settings.py (+ common.py)
  downloader.py  fila e integração com o yt-dlp
  browsers.py    detecção de navegadores e leitura de cookies
  deps.py        ffmpeg / Deno / Node e instalação pelo winget
  config.py      configurações e histórico
  fsutil.py      envio de arquivos para a Lixeira
  i18n.py        traduções (pt / en)
  theme.py       design system: cores, fontes, raios, espaçamentos, ícones
  widgets.py     componentes visuais reutilizáveis (cards, botões, diálogos, avisos)
  thumbs.py      miniaturas (preview) em cache
  player.py      motor de reprodução: fila + VLC (Playback)
  covers.py      capas personalizadas (app, folder.jpg, dentro do arquivo)
  updater.py     verificação de atualizações pelas Releases do GitHub
assets/          ícone do app (.ico / .png)
cli/             versão de terminal (script simples)
run.py           atalho: python run.py
build.ps1        gera o .exe e o instalador localmente
installer.iss    script do instalador (Inno Setup, pt/en)
```

---

## Privacidade e uso responsável

- Tudo roda no seu computador. O app não envia dados para nenhum servidor. A única conexão além dos downloads é a verificação opcional de atualizações na API do GitHub.
- Os cookies são lidos só na hora do download e não são salvos pelo app. **Nunca envie seu `cookies.txt` para o repositório**: o `.gitignore` já bloqueia esse arquivo.
- Baixe apenas conteúdo que você tem direito de usar, como seus próprios vídeos, vídeos com licença livre ou cópias para uso pessoal permitidas pela lei do seu país, respeitando os Termos de Serviço do YouTube.

---

## Licença

O VidNeon é **software livre**, licenciado sob a **[GNU GPL versão 3](LICENSE)** (`GPL-3.0-only`), com os [termos adicionais](NOTICE) permitidos pela seção 7 da licença:

- **Crédito obrigatório:** toda cópia distribuída, original ou modificada, deve manter visível na tela **Sobre** o crédito *"Based on VidNeon by Guilherme Felix (GuiSysLima)"* com o link do projeto, além do arquivo `NOTICE` e dos avisos de copyright no código.
- **Versões modificadas** devem dizer que são modificadas e não podem se passar pela original.
- O **nome "VidNeon" e o logotipo** não podem ser usados para identificar versões modificadas.
- Versões modificadas que forem distribuídas também precisam ser **GPL-3.0, com o código-fonte aberto**.

Você pode usar, estudar, modificar e compartilhar o VidNeon livremente, desde que respeite essas regras. O programa é fornecido **sem nenhuma garantia**.

© 2026 Guilherme Felix (GuiSysLima). As bibliotecas e componentes de terceiros têm suas próprias licenças; veja a lista no arquivo [NOTICE](NOTICE).
