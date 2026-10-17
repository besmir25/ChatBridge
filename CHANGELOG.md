# Changelog

Newest first. Add new entries under **Unreleased**; `python bump_version.py X.Y.Z` turns that section into the release.

## Unreleased
- **Android, Google Play preparation**: the app now targets Android 16 (API 36, Capacitor 8) and draws edge to edge with correct status and navigation bar colours in the light and night looks; a signed release bundle (.aab) can be built with `mobile\build-release.ps1`; the app can read the .zip your ChatGPT or Claude export gives you; sharing only a link opens Help with the right tip; phones whose web view is too old show a clear message instead of a blank screen
- Safer on Android: an uncompressed-size cap on zip files that is checked while unpacking, size limits on shared text, only content:// files accepted when sharing in, and exported files are kept in one folder that is cleared on the next export
- Store listing text says the privacy hiding is a safeguard, not a guarantee

## 1.4.0 (2026-10-16)
- **The Android app now follows the same flow as the Windows app**: a searchable list of conversations by date, then an open conversation with its sections and a "Continue it in" row: the AI apps installed on the phone (ChatGPT, Claude, Gemini, Copilot, Perplexity, Grok, DeepSeek, Le Chat), a website, a file, just copy it, or any app through the Share sheet. It also has rename, remove, "what I've sent" with send again, and settings for privacy and language
- Android can import ChatGPT and Claude export files, `.txt` and `.md`, and the app was tested end to end on an emulator (sharing in, copy, opening a website, saving a file, languages)
- Closing the share sheet on the phone no longer shows an error; "1 message" is written in the singular; the status bar is readable in both the light and night looks
- Importing a list of messages that contains a broken entry no longer fails (Windows and phone)
- **ChatBridge speaks more languages**: Spanish, Portuguese (Brazil), French, German, Simplified Chinese and Japanese, on Windows and on the Android app. It follows your system language by default; choose one in Settings → Language. Conversation titles and messages are never translated
- Settings on the phone now hold the language, the privacy options and the light/night look; the phone and Windows apps share one translation engine and one set of translation tables
- A settings file saved with a hidden byte-order mark (Notepad can add one) is now read instead of being set aside
- New "Copy a problem report" button in Help, a clearer message when no conversations are found, and saved "Part of…" items are tidied automatically

## 1.3.0 (2026-10-12)
- **A new two-pane layout**: your conversations in a list on the left; click one and it opens on the right with its sections, and the places you can continue it are right below, so the whole job happens on one screen. Tick the small box on a row to send several conversations together
- **Send just part of a conversation**: an opened conversation is shown as a notebook of sections (found automatically, with tags like Code, Decision, Problem and Files). Leave everything unticked to send the whole thing, or tick sections or single messages and rename sections; the AI also gets a short outline of the rest so it sees the bigger picture
- **Add to the chat that's already open**: choose a desktop app and tick the new box, and ChatBridge pastes into the open conversation instead of starting a new one (still never pressing Enter)
- **Apps that were closed now work the first time**: ChatBridge notices when an app has to start up and waits until it is ready, so you no longer have to press the button twice
- **No more scrolling** to find the big button: the screen fits the window, and the conversation list takes the free space
- **Help → Copy a problem report**: copies a short report (version, Windows, apps found, recent log with private details hidden) with no conversation text, ready to paste into an email or GitHub issue
- A clearer message when ChatBridge finds no conversations on a PC, explaining that web chats come in from a file or the browser extension
- Saved "Part of…" items are tidied automatically (the newest 12 are kept); the window no longer flashes dark while it loads

## 1.2.0 (2026-10-11)
- **A much simpler, friendlier screen**: one column with two questions — "Which conversation?" and "Where do you want to continue it?" — and one big button
- **One "A website" choice** instead of eight: pick ChatGPT, Claude.ai, Gemini and more from a small list (it remembers your pick), or choose "I'll open it myself". The conversation is copied and saved as a file either way
- New **"A file"** and **"Just copy it"** choices; the button now says what will happen ("Continue in Claude", "Copy and open ChatGPT")
- Light, easy-to-read look by default (other colors and the code-style font are still in Settings, along with text size)
- Private details are always hidden, and long conversations are shortened automatically only when they need it; ChatBridge says so in plain words. Both can be changed in Settings
- Less clutter: token counts, "tested" labels and the header chips are gone; Refresh, history, code projects and "Choose which apps" live under **More options**; ChatBridge says which AI apps it found, with a "Not right?" link
- Calmer conversation list: title and date, with read, rename and remove appearing when you point at one

## 1.1.0 (2026-10-11)
- **Refresh** button: look again for AI apps you've just installed and for new chats, without restarting
- **Search** your chats by title or by what was said inside them
- **Choose your tools** screen: tick which AI apps and websites you want on the right, and add one that's missing; a tool you install later appears by itself
- **Send to AI websites** (ChatGPT, Claude.ai, Gemini, Copilot, Perplexity, Grok, DeepSeek, Mistral): the chat is copied and saved as a file, and the site opens in your browser
- **Save as file…** exports the ticked chats as Markdown, text, or a ChatBridge file you can import again
- A friendlier chat list: readable titles instead of file paths, "Today / Yesterday / Last 7 days" groups (or group by app), "about 6 pages" and "3 days ago" instead of token counts and dates, and a rename button
- Chats from the ChatGPT desktop app stored on your PC are listed with proper names (hidden control text in them is ignored)
- **Help** window with plain answers; plainer wording throughout ("Shorten long text", "Hide private details")
- A redesigned installer: dark title bar, crisp text, a progress bar, a clear "ready" screen, and a clearer remove screen
- "Test this app" moved into Choose tools

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
