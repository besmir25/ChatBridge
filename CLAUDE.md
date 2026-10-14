# ChatBridge — notes for AI assistants and new contributors

ChatBridge (Windows) moves AI chats and code projects from one AI app to another. Python + pywebview (Edge WebView2) window;
the screen is plain HTML/CSS/JS in `ui/`. Public repo: github.com/besmir25/ChatBridge. MIT licensed.

## Where things are
- `chatbridge_app.py` — the app: `Api` (everything the page can call), the local receiver for the browser extension, update check, auto-paste.
- `chatbridge.py` — the engine: chat parsers, app/chat discovery, project scanner, compact/scrub, app profiles. (Its old tkinter window is legacy.)
- `ui/` — `index.html`, `app.js`, `app.css`; `demo.js` is preview-only sample data (`index.html?demo`).
- `extension/` — Chrome/Edge extension (Manifest V3) that saves web chats. `installer.py` — our own per-user installer/uninstaller.
- `release_tools.py`, `bump_version.py`, `make_release.py`, `build_*.py` — releasing. `tests/` — the test suite.

- `mobile/` — the Android app (Capacitor wrapper around plain HTML/JS). `mobile/www/core.js` re-implements the chat logic of `chatbridge.py`
  (sections, privacy scrubbing, shortening, handoff text); `mobile/tests/golden.json` is generated from Python and `npm test` in `mobile/`
  checks the JS gives identical answers. Change the Python logic -> run `python mobile/tests/make_golden.py` -> fix `core.js` until the tests pass.

## Commands
```bash
python -W ignore -m unittest discover -s tests      # must stay green (CHATBRIDGE_GUI_TESTS=1 adds fake-window tests)
python chatbridge_app.py                            # run from source
python bump_version.py 1.2.0                        # then commit, tag v1.2.0, push -> GitHub Actions builds the release
```

## Rules that must not be broken
1. **Never press Enter or send a message for the user.** `parse_keys` refuses Enter (and Ctrl+M / Ctrl+J). Keys are only sent while the target window's title matches.
2. **Chats stay on the PC.** The only network call is the optional update check to GitHub. Don't add telemetry or uploads.
3. **Imported files are untrusted.** Everything goes through `clean_conv`. Never put imported text into the page with `innerHTML` unless it went through `esc()`. Keep the Content-Security-Policy in `ui/index.html` (no inline scripts, `connect-src 'self'`).
4. **The uninstaller may only delete a folder named `ChatBridge` that contains our marker** (`is_safe_install_dir`). Don't loosen this.
5. **The capture receiver** binds 127.0.0.1 exclusively, needs the pairing token, refuses web-page origins, and proves itself to the extension with an HMAC on `/ping?nonce=`.
6. **Project scans must exclude secrets** (`SECRET_NAME`, `SECRET_DIRS`, `SECRET_TEXT`, symlinks) and the bundle must not contain the folder's full path.
7. Tests must not touch the real `%APPDATA%\ChatBridge`, registry, Start menu, or clipboard history beyond a short test string (the test file redirects `APPDATA`).

## Gotchas
- Git commits for this repo use the GitHub *noreply* address, never a personal email (GitHub rejects pushes that expose a private one).
- `release/`, `dist/`, `build/`, `previews/` are git-ignored; screenshots in `docs/screenshots/` are made from `?demo` data only — never commit screenshots of real chats.
- On this machine's Anaconda Python, PyInstaller refuses to run next to an old `pathlib` backport; `build_exe.py` works around it. CI uses a clean Python.
- Only Antigravity and Copilot were tested end-to-end; the extension's page selectors for ChatGPT/Claude.ai/Gemini are untested on the real sites.
- App behaviour lives in `profiles.json` entries (window title, new-chat shortcut, paste vs file), not in code — adding an app is usually one entry.

## Asking for a review
Start a fresh session in this folder and ask for a read-only security + correctness review of the areas above; give it this file first.
