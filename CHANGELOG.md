# Changelog

Newest first. Add new entries under **Unreleased**; `python bump_version.py X.Y.Z` turns that section into the release.

## 1.0.1 (2026-10-11)
- Safer imports: chat files are now checked when you import them, so a booby-trapped file can't run anything inside the app, and the app's page has a strict security policy that blocks scripts from running or sending data elsewhere
- Safer uninstall and install: the uninstaller only ever removes a folder named ChatBridge that setup itself created, and setup always installs into a ChatBridge folder (it won't clear out `D:\Games`)
- "Scrub private info" now also catches names like `OPENAI_API_KEY`, quoted passwords with spaces, and more kinds of tokens and web addresses with passwords; it also hides your Windows user name in more path styles
- Project folders skip more secret files (`.npmrc`, `.tfvars`, `.jks`, `secret_key.txt`, and more), anything inside `.ssh`, `.aws` or `secrets` folders, and links that point outside the folder; the project text no longer includes the folder's full path
- The browser extension now checks it's talking to the real ChatBridge before it sends the pairing code or any chat
- More reliable: a damaged or odd entry in your saved library can't leave the window blank, saving is safer when two things happen at once, a damaged settings file is set aside instead of overwritten, and old hand-over files are deleted after a week
- Faster on very long messages; ChatBridge no longer overwrites your saved settings when you pick a local model

## 1.0.0
First public release.

- Finds installed AI apps (with their real icons) and chats stored on the PC; imports ChatGPT/Claude exports, text and markdown
- Sends chats or whole projects to desktop apps, command-line tools and local model servers; never presses Enter
- Project folders: folder tree, full / outline / structure-only modes, quick filters, secret files left out
- Size preview, Compact, Scrub private info, send history, drag and drop
- Browser extension for ChatGPT, Claude.ai and Gemini
- Five color themes, installer and uninstaller
- Optional daily update check, with a "What's new" window after you update and release notes shown before you download
- The app and installer show their name, version and publisher in Windows file properties
