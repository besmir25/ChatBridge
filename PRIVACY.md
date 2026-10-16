# Privacy

ChatBridge runs entirely on your PC. It has no account, no analytics, no ads and no servers of its own.

## What it reads
- **Chats and projects you choose.** It looks for chat files that other apps keep on this PC (for example Claude Code's
  session logs) and for project folders you pick. It reads them only to list them and to build what you send.
- **Which AI apps are installed**, from your Start menu and installed-programs list, so it can show them as tiles.
- **Your clipboard**, only to place the text you're sending on it.

## What it stores
Everything is under `%APPDATA%\ChatBridge`: your library, settings, send history, an icon cache, a pairing code for the
browser extension, and a log file. Nothing is encrypted. Delete the folder to remove it all. Uninstalling keeps it unless
you choose to remove it.

## What it sends over the network
- **Update check (optional, once a day, can be turned off in Settings).** It asks GitHub for the newest version number.
  No chat, file name, or personal information is included. It never downloads or installs anything by itself.
- **Chats only go where you send them.** When you send a chat to an app, ChatBridge opens that app and pastes the text; what
  that app does with it is governed by that app's own terms and privacy policy.
- **Local models** (Ollama, LM Studio and similar) are contacted on your own PC (`127.0.0.1`) if you choose them.
- **Browser extension.** Talks only to ChatBridge on `127.0.0.1`, and only after you click *Save to ChatBridge*. A pairing
  code stops other programs and websites from sending data in.

## What it never does
- It never presses **Enter** or sends a message for you.
- It never uploads your chats or files to a server.
- Project folders: `.env` files, key files, and any file that looks like it contains an API key or password are left out
  before anything is built. The *Scrub private info* option additionally removes keys, emails, phone numbers and your
  Windows user name from chats before sending. This is a safeguard, not a guarantee — look at what you're sending.

## The Android app
- It has no account and no servers, and it asks Android for **no permissions**, not even the internet.
- Conversations you share to it, paste or add from a file are kept only inside the app on your phone, and the app is excluded
  from Android's cloud backup. Removing a conversation (or the app) deletes it.
- It can check whether certain AI apps (ChatGPT, Claude, Gemini, Copilot, Perplexity, Grok, DeepSeek, Le Chat) are installed, so it
  can show them as choices. It cannot see any other app.
- When you press the big button it puts text on the clipboard, or hands it to the app, website or share sheet **you chose**.
  What that app or website does with it is up to them.
- It never sends a message for you.

## Questions
Open an issue on the project's GitHub page.
