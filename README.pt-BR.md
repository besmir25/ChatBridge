<sub>[English](README.md) · [Español](README.es.md) · **Português** · [Français](README.fr.md) · [Deutsch](README.de.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)</sub>

# ChatBridge

**Leve uma conversa (ou um projeto de código inteiro) de um app de IA para outro, sem recomeçar do zero.**

![Licença: MIT](https://img.shields.io/badge/license-MIT-2dd4bf) ![Plataforma: Windows 10/11](https://img.shields.io/badge/platform-Windows%2010%2F11-60a5fa) ![Roda localmente](https://img.shields.io/badge/data-stays%20on%20your%20PC-34d399)

> Esta é uma tradução. A versão em inglês ([README.md](README.md)) é a de referência. O aplicativo também está disponível em português: ele escolhe sozinho pelo idioma do Windows, ou em **Settings → Language**. Aqui os nomes dos botões ficam em inglês; no app você os verá no seu idioma.

Você começou uma conversa em uma IA e quer continuar em outra, ou passar um projeto para um modelo novo. Hoje isso significa copiar e colar, perder contexto e explicar tudo de novo. O ChatBridge faz isso em três passos simples.

![Um passeio rápido: escolha uma conversa, marque as partes que quer, escolha o destino e ela é colada](docs/demo.gif)

*A animação usa conversas de exemplo, não reais.*

## Como funciona

1. **Escolha uma conversa**: o ChatBridge lista à esquerda as conversas que encontrou no seu PC (você pode adicionar mais a partir de um arquivo ou colando texto). Clique em uma para abri-la.
2. **Escolha onde continuar**: à direita, um dos seus apps de IA (com o ícone real), **a website** (ChatGPT, Claude.ai, Gemini e outros), **a file**, ou apenas copiar.
3. **Clique no botão grande**: o app abre e a conversa é colocada no lugar. **Você lê e aperta Enter.**

## Recursos

- **Encontra seus apps de IA**: Claude, ChatGPT, Copilot, Antigravity, modelos locais como o Ollama e mais. Instalou algo novo? Abra *More options* e clique em **Look again**.
- **Sites e arquivos**: escolha um site de uma lista curta e a conversa é copiada (e salva como arquivo, caso o site não aceite um texto longo); ou salve como Markdown, texto ou um arquivo que você pode importar de novo.
- **Fácil de navegar**: nomes legíveis, agrupados por data, com busca que olha dentro das conversas.
- **Encontra seus chats**: os guardados neste PC (Claude Code, Codex, Gemini CLI, LM Studio, Jan) e importa exportações do ChatGPT e do Claude, texto colado e markdown.
- **Salva chats da web com um clique** com a extensão de navegador incluída (ChatGPT, Claude.ai, Gemini).
- **Leva só uma parte de um chat**: uma conversa longa abre como um caderno de seções que você pode marcar, renomear e enviar separadamente, com um resumo curto do restante; dá para colar em um chat que você já tem aberto.
- **Leva projetos inteiros**: código, markdown, YAML e outros arquivos de configuração, com árvore de pastas, medidor de tamanho ao vivo e a escolha entre *arquivos completos*, *resumos de arquivos grandes* ou *só a estrutura*.
- **Cuida de você**: senhas, chaves, e-mails e seu nome de usuário do Windows são ocultados automaticamente, e conversas muito longas só são encurtadas quando necessário.
- **Histórico** e **arrastar e soltar**; o último destino usado é lembrado.
- **Claro por padrão**, com cores escuras e uma fonte estilo código em Settings.

![Levando uma pasta de projeto](docs/screenshots/project.png)

> As capturas de tela usam dados de exemplo e ícones provisórios. No seu PC, o ChatBridge mostra o ícone real de cada app, retirado do Windows.

## Instalação

Baixe o **`ChatBridge-Setup.exe`** na página de [Releases](../../releases) e execute. Ele instala só para a sua conta do Windows e não precisa de permissão de administrador. Também instala um desinstalador, acessível em *Settings → Apps*.

### Se o Windows disser «O Windows protegeu o computador»
O ChatBridge é novo e ainda não tem assinatura digital, por isso o Windows SmartScreen mostra um aviso azul ou vermelho para qualquer programa que ele não viu muitas vezes. Isso não significa que algo esteja errado. Para continuar, clique em **Mais informações** e depois em **Executar assim mesmo**. Cada versão traz uma soma SHA-256 (`SHA256SUMS.txt`) para você conferir o download antes. Já foi solicitada a assinatura de código gratuita (veja a [política de assinatura de código](CODE_SIGNING_POLICY.md)), que vai remover o aviso.

**Requisitos:** Windows 10 ou 11 com o runtime Microsoft Edge WebView2 (já incluído no Windows 11).

## Extensão de navegador (opcional)

1. Abra `edge://extensions` (ou `chrome://extensions`) e ative o **Modo do desenvolvedor**.
2. Clique em **Carregar sem compactação** e escolha a pasta `extension` (ChatBridge → Settings → *Open extension folder* abre essa pasta).
3. Em ChatBridge → Settings → **Browser capture**, clique em **Copy code** e cole na página de opções da extensão.

Um botão *Save to ChatBridge* aparece no ChatGPT, Claude.ai e Gemini. A extensão só conversa com o ChatBridge no seu próprio PC, e só depois que você clica no botão.

## Privacidade e segurança

- Tudo fica no seu PC: sem conta, sem análises, sem servidores. Veja [PRIVACY.md](PRIVACY.md).
- A única requisição de rede é uma verificação opcional, uma vez por dia, de uma versão mais nova (você pode desativar).
- O ChatBridge **nunca aperta Enter** nem envia mensagens por você.
- Pastas de projeto: arquivos `.env`, arquivos de chave e qualquer arquivo que pareça conter uma chave ou senha são deixados de fora automaticamente.

## Compilar a partir do código-fonte

Python 3.9+ no Windows:

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py                      # executar
python -m unittest discover -s tests -v       # testes
python make_release.py                        # testes, depois compila o app e o instalador em release/
```

## Licença

[MIT](LICENSE). O ChatBridge é um projeto independente e não é afiliado nem endossado por nenhuma empresa de IA. Os nomes de produtos são marcas registradas dos seus donos.
