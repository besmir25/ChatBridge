# ChatBridge for phones (Android first)

The phone version works through the **Share** button, because phones don't let an app read other apps' chats or paste into them.
It follows the same flow as the Windows app:

1. **Pick a conversation.** Share one in from any AI app (Share → ChatBridge), copy one and tap *Paste what I copied*, or add a
   file (ChatGPT and Claude exports, `.txt`, `.md`). They're listed by date, with search.
2. **Open it** to see its sections. Leave everything unticked to send it all, or tick sections or single messages (an outline of the
   rest is added so the AI sees the bigger picture).
3. **Choose where it goes** and press the big button: an AI app installed on the phone (ChatGPT, Claude, Gemini, Copilot, Perplexity,
   Grok, DeepSeek, Le Chat), a website, a file, just copy it, or any other app through the Share sheet.

Private details are hidden by default, nothing is sent for you, there is no account and no server, and the app asks Android for no
permissions (not even the internet). It speaks English, Spanish, Portuguese, French, German, Chinese and Japanese, and switches to a
night look by time.

## How it's built
- `www/` is the whole screen (plain HTML/CSS/JS). `www/core.js` is the same logic as `chatbridge.py` (sections, hiding private
  details, shortening, importing exports, building the text to send), in JavaScript. `www/i18n.js` and `www/lang/` are the
  translations (generated; see `ui/lang/`).
- `tests/golden.json` holds what the Python version answers for a set of inputs; `tests/core.test.js` checks the JavaScript gives
  the same answers. **After changing the logic in `chatbridge.py`, run** `python mobile/tests/make_golden.py` **and then**
  `npm test` **(inside `mobile/`)**, and port the change to `core.js` if a test fails.
- `android/` is a [Capacitor](https://capacitorjs.com) project that wraps `www/`. `MainActivity.java` receives text or a small file
  that another app shares. The manifest lists the AI apps it may look for (it cannot see any other app). Plugins: Share, Clipboard,
  App Launcher, Filesystem, Status Bar.
- Icons: `python mobile/make_icons.py build c` (the teal-to-blue icon, the same colours as the Windows app).

## Get the .apk
- **From GitHub (no setup):** the *Android* workflow builds it on every change under `mobile/`. Open the run in the Actions tab and
  download **ChatBridge-android-debug**. Install it on a phone (allow "install unknown apps" for your browser or file manager).
- **On your PC:** see below.

## Test on this PC (a phone emulator)
One-time setup, with no admin rights, in one folder you can delete (about 5 GB):
1. Java 21 (Microsoft Build of OpenJDK, unzip to `~\Android\jdk`).
2. Google's Android command-line tools (unzip to `~\Android\sdk\cmdline-tools\latest`), then with `sdkmanager`:
   `platform-tools`, `platforms;android-35`, `build-tools;35.0.0`, `emulator`, `system-images;android-35;google_apis;x86_64`.
3. `avdmanager create avd -n ChatBridgeTest -k "system-images;android-35;google_apis;x86_64" -d pixel_7`.
4. Windows needs *Windows Hypervisor Platform* switched on (`emulator -accel-check` should say WHPX is usable).

Then, any time, from the project folder:

```bash
powershell -ExecutionPolicy Bypass -File mobile\run-test-phone.ps1
```

It builds the app, starts the test phone, installs ChatBridge and opens it. Add `-NoBuild` to reuse the last build, or `-Root <folder>`
if you didn't use `~\Android`.

To try sharing in: open any app on the test phone, use its Share button and pick ChatBridge. From a terminal you can also run
`adb shell am start -a android.intent.action.SEND -t text/plain -n com.besmir25.chatbridge/.MainActivity --es android.intent.extra.TEXT "User: hi"`.

## Try the screen in a browser
Serve `www/` (for example `python -m http.server --directory www`) and open `index.html?demo` (add `&lang=ja` to preview a language).

## Not done yet
Google Play release (needs a signed release build and a $25 developer account), the iPhone version (needs a Mac and an Apple
developer account), and reading a conversation straight from another app (not possible on phones).
