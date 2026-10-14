# ChatBridge for phones (Android first)

The phone version is a different app from the Windows one, because phones don't let an app read other apps' chats or paste into
them. It works through the **Share** button instead:

1. In any AI app, open a conversation and tap **Share → ChatBridge** (or copy it and tap *Paste what I copied*).
2. The conversation opens as a notebook of sections. Leave everything unticked to send it all, or tick sections or single messages.
3. **Share to an app…** sends it to any app; **Copy and open** copies it and opens ChatGPT, Claude, Gemini or Copilot.

Private details are hidden by default, nothing is sent for you, there is no account and no server, and the app asks Android for no
permissions (not even the internet).

## How it's built
- `www/` is the whole screen (plain HTML/CSS/JS). `www/core.js` is the same logic as `chatbridge.py` (splitting into sections,
  hiding private details, shortening, building the text to send), written in JavaScript.
- `tests/golden.json` holds what the Python version answers for a set of inputs; `tests/core.test.js` checks the JavaScript gives
  the same answers. **After changing the logic in `chatbridge.py`, run** `python mobile/tests/make_golden.py` **and then**
  `npm test` **(inside `mobile/`)**, and port the change to `core.js` if a test fails.
- `android/` is a [Capacitor](https://capacitorjs.com) project that wraps `www/`. `MainActivity.java` receives text or a small file
  that another app shares and gives it to the page. Plugins used: Share, Clipboard, App Launcher.

## Build the .apk
- **On GitHub (no setup):** the *Android* workflow builds it on every change under `mobile/`. Open the run in the Actions tab and
  download **ChatBridge-android-debug**. Install it on a phone (allow "install unknown apps" for your browser or file manager).
- **On your PC:** install Node.js, a JDK (21) and Android Studio (for the SDK), then in `mobile/`:
  `npm install`, `npx cap sync android`, and `cd android && gradlew.bat assembleDebug`. The file appears in
  `android/app/build/outputs/apk/debug/`.

## Try the screen in a browser
Serve `www/` (for example `python -m http.server --directory www`) and open `index.html?demo`.

## Not done yet
Google Play release (needs a signed release build and a $25 developer account), an app icon, saving a conversation as a file,
and the iPhone version (needs a Mac and an Apple developer account).
