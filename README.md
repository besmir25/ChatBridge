# ChatBridge

Move a conversation from one AI to another, without starting over.

ChatBridge finds the AI apps on your Windows PC and the chats and projects you've had, lets you tick what you want, and
sends it to the app you choose — opened, with the chat pasted in, ready for you to read and press Enter.

![ChatBridge](assets/chatbridge.png)

## What it does

- **Finds your AI apps** (Claude, ChatGPT, Copilot, Antigravity, local models like Ollama, and more) and shows their real icons.
- **Finds your chats** stored on this PC (Claude Code, Codex, Gemini CLI, LM Studio, Jan), and imports ChatGPT / Claude exports,
  pasted text, or markdown.
- **Saves web chats with one click** using the included browser extension (ChatGPT, Claude.ai, Gemini).
- **Brings whole projects** — code, markdown, YAML and other config files, with a folder tree, a live size meter, and a
  choice of full files, outlines of big files, or structure only. Secrets and key files are left out automatically.
- **Shows the size before you send** (estimated tokens, share of the app's context window), can **compact** long output,
  and can **scrub** keys, emails, phone numbers and your Windows user name.
- **Never presses Enter for you.** You always read it first.

## Install

Download `ChatBridge-Setup.exe` from the [Releases](../../releases) page and run it. It installs for your Windows account
only and needs no administrator rights.

Windows may warn about an unknown publisher while the app is new. Each release lists a SHA-256 checksum so you can
verify the download.

## Browser extension

1. Open `edge://extensions` (or `chrome://extensions`) and turn on **Developer mode**.
2. **Load unpacked** and choose the `extension` folder (ChatBridge → Settings → *Open extension folder* opens it).
3. In ChatBridge → Settings → **Browser capture**, click **Copy code**, then paste it into the extension's options page.

## Privacy

Everything stays on your PC. See [PRIVACY.md](PRIVACY.md).

## Build from source

Requires Python 3.9+ on Windows with the Edge WebView2 runtime (included in Windows 11).

```bash
pip install pywebview pyinstaller pillow
python chatbridge_app.py            # run it
python -m unittest discover -s tests -v
python make_release.py              # tests + build the app and the installer into release/
```

`CHATBRIDGE_GUI_TESTS=1` adds tests that open a fake chat window and briefly use the clipboard and keyboard.

## Adding or fixing an app

Each app's behaviour (its window title, its "new chat" shortcut, whether to paste the chat or hand over a file) is one entry
in `profiles.json` — see ChatBridge → *Edit app list*. Keys like `ctrl+shift+l` are allowed; **Enter is refused**.
