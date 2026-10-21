"""Everything that works differently on Windows, macOS and Linux, in one place: where settings live, the clipboard, which window
is in front, pressing keys, finding and opening installed apps, their icons, and showing files.

Safety rules hold on every system (see CLAUDE.md): keys are only pressed while the target app is in front, Enter is never
pressed (cb.parse_keys refuses it before anything here runs), and where the system can't tell us reliably which window is in
front (Linux Wayland), we don't press keys at all; the person pastes themselves."""
import base64
import glob
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
NAME = "windows" if WINDOWS else "mac" if MAC else "linux"
_NO_WINDOW = 0x08000000 if WINDOWS else 0          # CREATE_NO_WINDOW: no console flash for helper programs on Windows


def app_dir():
    """Where ChatBridge keeps its settings and library. CHATBRIDGE_HOME overrides it (the tests use that)."""
    if os.environ.get("CHATBRIDGE_HOME"):
        return os.path.join(os.environ["CHATBRIDGE_HOME"], "ChatBridge")
    if WINDOWS:
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChatBridge")
    if MAC:
        return os.path.expanduser("~/Library/Application Support/ChatBridge")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "ChatBridge")


def data_dir(app):
    """Another app's settings folder (e.g. Jan): %APPDATA%\\Jan, ~/Library/Application Support/Jan, ~/.config/Jan."""
    if WINDOWS:
        return os.path.join(os.environ.get("APPDATA", ""), app)
    if MAC:
        return os.path.expanduser(f"~/Library/Application Support/{app}")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), app)


def wayland():
    """Any Wayland session counts, even with XWayland (DISPLAY) present: xdotool only sees XWayland's focus there, which may not be
    the window really in front."""
    return LINUX and (os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY")))


PASTE_KEYS = "Cmd+V" if MAC else "Ctrl+V"          # what the person presses themselves, for messages


# ---------------------------------------------------------------- clipboard
def set_clipboard(text):
    if WINDOWS:
        return _win_set_clipboard(text)
    if MAC:
        return _feed(["pbcopy"], text, {"LANG": "en_US.UTF-8", "LC_CTYPE": "UTF-8"})
    for cmd in ((["wl-copy"] if os.environ.get("WAYLAND_DISPLAY") else []),
                (["xclip", "-selection", "clipboard"] if os.environ.get("DISPLAY") else []),
                (["xsel", "--clipboard", "--input"] if os.environ.get("DISPLAY") else [])):
        if cmd and shutil.which(cmd[0]):
            return _feed(cmd, text)
    raise OSError("ChatBridge needs wl-clipboard or xclip to copy on Linux. Install one with your package manager "
                  "(for example: sudo apt install wl-clipboard xclip).")


def _feed(cmd, text, env=None):
    """Hand text to a clipboard helper. wl-copy and xclip keep running to serve the clipboard, so don't wait for them."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env={**os.environ, **(env or {})}, start_new_session=True)
    p.stdin.write(text.encode("utf-8"))
    p.stdin.close()
    try:
        p.wait(timeout=2)            # pbcopy and xsel finish quickly; the others fork into the background
    except subprocess.TimeoutExpired:
        pass
    if p.returncode not in (None, 0):
        raise OSError(f"Couldn't copy ({cmd[0]} failed).")


def get_clipboard():
    """For the tests: read the clipboard back as text."""
    if WINDOWS:
        return subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-Clipboard"],
                              capture_output=True, text=True, encoding="utf-8", creationflags=_NO_WINDOW).stdout.strip()
    if MAC:
        cmd = ["pbpaste"]
    elif os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        cmd = ["wl-paste", "--no-newline"]
    else:
        cmd = ["xclip", "-selection", "clipboard", "-o"]
    return subprocess.run(cmd, capture_output=True, timeout=5).stdout.decode("utf-8").strip()


def _win_set_clipboard(text):
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.OpenClipboard.argtypes, u.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
    u.SetClipboardData.argtypes, u.SetClipboardData.restype = [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE
    k.GlobalAlloc.argtypes, k.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], wintypes.HANDLE
    k.GlobalLock.argtypes, k.GlobalLock.restype = [wintypes.HANDLE], ctypes.c_void_p
    k.GlobalUnlock.argtypes = [wintypes.HANDLE]
    data = text.encode("utf-16-le") + b"\0\0"
    h = k.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = k.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k.GlobalUnlock(h)
    for _ in range(20):
        if u.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise OSError("Couldn't open the clipboard")
    try:
        u.EmptyClipboard()
        u.SetClipboardData(13, h)  # CF_UNICODETEXT
    finally:
        u.CloseClipboard()


# ---------------------------------------------------------------- which app is in front, and pressing keys
def can_press_keys():
    """Can ChatBridge paste for the person here? Not on Wayland: there no app may see which window is in front, so
    ChatBridge couldn't make sure the keys go to the right app."""
    if WINDOWS:
        return True
    if MAC:
        return bool(shutil.which("osascript"))
    return not wayland() and bool(os.environ.get("DISPLAY")) and bool(shutil.which("xdotool"))


def foreground_title():
    """The title of the window in front, in lower case (on macOS: the front app's name and its window title)."""
    if WINDOWS:
        import ctypes
        u = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(u.GetForegroundWindow(), buf, 256)
        return buf.value.lower()
    if MAC:
        name = ""
        try:
            from AppKit import NSWorkspace          # comes with pywebview on macOS; needs no permission
            name = str(NSWorkspace.sharedWorkspace().frontmostApplication().localizedName() or "")
        except Exception:
            name = _osa('tell application "System Events" to get name of first application process whose frontmost is true')
        return name.lower()
    if not can_press_keys():
        return ""
    return _run(["xdotool", "getactivewindow", "getwindowname"]).lower()


def window_open(key):
    """Is the app already running with a window whose title (macOS: app name) contains `key`? Only used to wait a little
    longer for an app that is starting from scratch."""
    if not key:
        return True
    if WINDOWS:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        found = []
        enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _):
            if u.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                u.GetWindowTextW(hwnd, buf, 256)
                if key in buf.value.lower():
                    found.append(hwnd)
                    return False
            return True
        u.EnumWindows(enum_type(visit), 0)
        return bool(found)
    if MAC:
        try:
            from AppKit import NSWorkspace
            return any(key in str(a.localizedName() or "").lower() for a in NSWorkspace.sharedWorkspace().runningApplications())
        except Exception:
            return key in _osa('tell application "System Events" to get name of every application process').lower()
    if shutil.which("xdotool") and os.environ.get("DISPLAY"):
        return bool(_run(["xdotool", "search", "--onlyvisible", "--name", re.escape(key)]))
    return False


# key names (as in cb.parse_keys / profiles.json) -> each system's names
_MAC_CODES = {"tab": 48, "esc": 53, "space": 49, **{f"f{i}": c for i, c in
              zip(range(1, 13), (122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111))}}
_X_NAMES = {"ctrl": "ctrl", "shift": "shift", "alt": "alt", "tab": "Tab", "esc": "Escape", "space": "space"}


def press_spec(spec):
    """Press a shortcut like 'ctrl+shift+l' in the app in front. On macOS Ctrl means Cmd (the same shortcut there).
    cb.parse_keys refuses Enter, Return, Ctrl+M and Ctrl+J (Enter in disguise) on every system before anything is pressed."""
    import chatbridge as cb
    vks = cb.parse_keys(spec)
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if WINDOWS:
        return _win_press(vks)
    if MAC:
        mods = [{"ctrl": "command down", "shift": "shift down", "alt": "option down"}[p] for p in parts if p in ("ctrl", "shift", "alt")]
        keys = [p for p in parts if p not in ("ctrl", "shift", "alt")]
        if len(keys) != 1:
            raise ValueError(f"Unknown shortcut '{spec}'")
        k = keys[0]
        what = f"key code {_MAC_CODES[k]}" if k in _MAC_CODES else f'keystroke "{k}"' if len(k) == 1 and k.isalnum() else None
        if not what:
            raise ValueError(f"Unknown key '{k}'")
        using = f" using {{{', '.join(mods)}}}" if mods else ""
        out = _osa(f'tell application "System Events" to {what}{using}', check=True)
        return out
    if not can_press_keys():
        raise OSError("Can't press keys here.")
    names = [_X_NAMES.get(p, p if re.fullmatch(r"[a-z0-9]|f([1-9]|1[0-2])", p) else None) for p in parts]
    if None in names:
        raise ValueError(f"Unknown shortcut '{spec}'")
    subprocess.run(["xdotool", "key", "--clearmodifiers", "+".join(n.upper() if re.fullmatch(r"f\d+", n) else n for n in names)],
                   check=True, timeout=5)


def paste():
    """Ctrl+V (Cmd+V on macOS) in the app in front. Never Enter."""
    press_spec("ctrl+v")


def _win_press(vks):
    import ctypes
    u = ctypes.windll.user32
    for vk in vks:
        u.keybd_event(vk, 0, 0, 0)
    for vk in reversed(vks):
        u.keybd_event(vk, 0, 2, 0)


class NeedsPermission(OSError):
    """macOS: ChatBridge isn't allowed to press keys yet (System Settings -> Privacy & Security -> Accessibility)."""


def _osa(script, check=False):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        if check:
            raise
        return ""
    if check and r.returncode != 0:
        err = r.stderr.lower()
        if any(s in err for s in ("not allowed", "not authorized", "1002", "-1743", "-25211", "assistive")):
            raise NeedsPermission("To paste for you, ChatBridge needs permission: System Settings → Privacy & Security → "
                                  "Accessibility → turn on ChatBridge.")
        raise OSError(r.stderr.strip() or "osascript failed")
    return r.stdout.strip()


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------- installed apps
def installed_apps():
    """[(name, info, launch)] for the apps installed on this computer. `launch` is what open_app() takes."""
    if WINDOWS:
        return _win_apps()
    if MAC:
        return _mac_apps()
    return _linux_apps()


def _win_apps():
    import json
    out = []
    try:  # Start menu entries cover classic and Microsoft Store apps
        raw = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=45, creationflags=_NO_WINDOW).stdout
        apps = json.loads(raw) if raw.strip() else []
        for a in [apps] if isinstance(apps, dict) else apps:
            out.append((a["Name"], "Start menu", "shell:AppsFolder\\" + a["AppID"]))
    except Exception:
        pass
    try:
        import winreg
    except ImportError:
        return out
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                      (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:   # installed-programs list (catches apps with no Start menu entry)
            with winreg.OpenKey(hive, sub) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        with winreg.OpenKey(k, winreg.EnumKey(k, i)) as s:
                            name = winreg.QueryValueEx(s, "DisplayName")[0]
                            try:
                                loc = winreg.QueryValueEx(s, "InstallLocation")[0]
                            except OSError:
                                loc = ""
                        out.append((name, loc or "Installed program", loc if loc and os.path.isdir(loc) else None))
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def _mac_apps():
    out, seen = [], set()
    for root in ("/Applications", os.path.expanduser("~/Applications"), "/Applications/Utilities"):
        for path in sorted(glob.glob(os.path.join(root, "*.app"))):
            name = os.path.basename(path)[:-4]
            if name.lower() not in seen:
                seen.add(name.lower())
                out.append((name, "Applications folder", path))
    return out


def _desktop_dirs():
    dirs = [os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "applications")]
    dirs += [os.path.join(d, "applications") for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    dirs += ["/var/lib/flatpak/exports/share/applications", os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
             "/var/lib/snapd/desktop/applications"]
    out = []
    for d in dirs:
        if d not in out and os.path.isdir(d):
            out.append(d)
    return out


def read_desktop_file(path):
    """The [Desktop Entry] part of a .desktop file as a dict (untranslated keys only)."""
    entry, inside = {}, False
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    inside = line == "[Desktop Entry]"
                elif inside and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    entry.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return entry


def _linux_apps():
    out, seen = [], set()
    for d in _desktop_dirs():
        for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            e = read_desktop_file(path)
            name = e.get("Name", "")
            if (not name or e.get("Type", "Application") != "Application" or e.get("NoDisplay", "").lower() == "true"
                    or e.get("Hidden", "").lower() == "true" or name.lower() in seen):
                continue
            seen.add(name.lower())
            out.append((name, "App menu", "desktop:" + path))
    return out


def open_app(launch, arg=None):
    """Start an installed app. `launch` comes from installed_apps() (or is a program path), never from a chat or web page."""
    if WINDOWS:
        if arg:
            return subprocess.Popen([launch, arg])
        if launch.startswith("shell:"):
            return subprocess.Popen(["explorer", launch])
        return os.startfile(launch)
    if MAC:
        cmd = ["open", "-a", launch] + ([arg] if arg else [])     # a folder is opened as a document, even if the app is running
        if not launch.endswith(".app") and os.path.isfile(launch):
            cmd = [launch] + ([arg] if arg else [])
        return subprocess.Popen(cmd, start_new_session=True)
    if launch.startswith("desktop:"):
        path = launch[len("desktop:"):]
        if shutil.which("gio") and not arg:
            try:   # gio returns as soon as the app is started; older glib has no "gio launch", then start it ourselves
                if subprocess.run(["gio", "launch", path], start_new_session=True, timeout=15,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    return None
            except (OSError, subprocess.SubprocessError):
                pass
        cmd = desktop_exec(read_desktop_file(path).get("Exec", ""), arg)
        if not cmd:
            raise OSError("That app's menu entry has no command to start it.")
        return subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.Popen([launch] + ([arg] if arg else []), start_new_session=True)


def desktop_exec(line, arg=None):
    """A .desktop file's Exec= line -> argv. Field codes (%f %U ...) are dropped, or filled with `arg` for %f/%F/%u/%U."""
    try:
        parts = shlex.split(line)
    except ValueError:
        return []
    out, used = [], False
    for p in parts:
        if re.fullmatch(r"%[fFuU]", p):
            if arg and not used:
                out.append(arg)
                used = True
        elif re.fullmatch(r"%[a-zA-Z]", p):
            continue
        else:
            out.append(p.replace("%%", "%"))
    if arg and not used:
        out.append(arg)
    return out


def find_program(name):
    """An installed app's main program by its name (used to hand an editor a folder), e.g. Antigravity."""
    first = name.split()[0].lower()
    if WINDOWS:
        for root in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
                     os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            for d in glob.glob(os.path.join(root, first + "*")):
                exe = os.path.join(d, first + ".exe")
                if os.path.isfile(exe):
                    return exe
    elif MAC:
        for root in ("/Applications", os.path.expanduser("~/Applications")):
            for app in glob.glob(os.path.join(root, "*.app")):
                if os.path.basename(app).lower().startswith(first):
                    return app
    return shutil.which(first)


def open_terminal(command):
    """Open a terminal window running a command-line AI tool (like `claude`). `command` is a name from cb.CLI_TOOLS."""
    if WINDOWS:
        return subprocess.Popen(["cmd", "/k", command], creationflags=0x10)   # CREATE_NEW_CONSOLE
    if MAC:
        return subprocess.Popen(["osascript", "-e", 'tell application "Terminal" to activate',
                                 "-e", f'tell application "Terminal" to do script {_aq(command)}'])
    for term in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xfce4-terminal", "-x"],
                 ["kitty"], ["alacritty", "-e"], ["xterm", "-e"]):
        if shutil.which(term[0]):
            return subprocess.Popen(term + [command], start_new_session=True)
    raise OSError("No terminal program was found.")


TERMINAL_PASTE = "right-click there and choose Paste" if WINDOWS else "press Cmd+V there" if MAC else "press Ctrl+Shift+V there"


# ---------------------------------------------------------------- files and folders
def open_path(path):
    """Open a file or folder ChatBridge made or ships with (never a path from a chat)."""
    if WINDOWS:
        return os.startfile(path)
    return subprocess.Popen(["open" if MAC else "xdg-open", path], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reveal(path):
    """Show a file in Explorer / Finder / the file manager, selected where the system allows it."""
    if WINDOWS:
        return subprocess.Popen(["explorer", "/select,", path])
    if MAC:
        return subprocess.Popen(["open", "-R", path])
    if shutil.which("dbus-send"):   # ask the file manager to show the file selected; if none answers, open the folder
        from urllib.parse import quote
        script = ('dbus-send --session --print-reply --reply-timeout=3000 --dest=org.freedesktop.FileManager1 '
                  '/org/freedesktop/FileManager1 org.freedesktop.FileManager1.ShowItems "array:string:$1" "string:" '
                  '>/dev/null 2>&1 || xdg-open "$2"')
        return subprocess.Popen(["sh", "-c", script, "sh", "file://" + quote(path), os.path.dirname(path)],   # paths are arguments,
                                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # never part of the script
    return open_path(os.path.dirname(path))


def show_error(title, message):
    """A plain message box for when the window itself couldn't start."""
    try:
        if WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        elif MAC:
            subprocess.run(["osascript", "-e", f"display alert {_aq(title)} message {_aq(message)} as critical"], timeout=300)
        elif shutil.which("zenity"):
            subprocess.run(["zenity", "--error", "--no-markup", "--title", title, "--text", message], timeout=300)
        elif shutil.which("kdialog"):
            subprocess.run(["kdialog", "--title", title, "--error", message], timeout=300)
        else:
            print(f"{title}: {message}", file=sys.stderr)
    except Exception:
        pass


def _aq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


START_HINT = ("If the window area is blank, install the Microsoft Edge WebView2 Runtime and try again." if WINDOWS else
              "" if MAC else "If the window doesn't appear, check that your system has the Qt or WebKitGTK libraries "
              "(see the Linux notes in the README).")


# ---------------------------------------------------------------- app icons
def _safe(name):
    """A file name for an app's icon. The hash keeps apps like "Foo" and "Foo+" apart."""
    import hashlib
    return (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "app")[:40] + "-" + hashlib.sha1(name.encode()).hexdigest()[:8]


def app_icons(apps, cache_dir, cached_only=False):
    """{app name: data-URI or None} for apps found by installed_apps(). Icons are cached as PNG files; with cached_only
    nothing new is extracted (used at start-up, so the window opens fast)."""
    if WINDOWS:
        from icons import fetch_icons
        items = [{"key": a["name"], "parse": None if cached_only else a.get("launch")} for a in apps
                 if cached_only or (a.get("launch") or "").startswith("shell:")]
        return fetch_icons(items, cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    out = {}
    for a in apps:
        launch = a.get("launch") or ""
        target = os.path.join(cache_dir, _safe(a["name"]) + ".png")
        if not os.path.isfile(target) and not cached_only:
            try:
                if MAC and launch.endswith(".app"):
                    _mac_icon(launch, target)
                elif launch.startswith("desktop:"):
                    _linux_icon(read_desktop_file(launch[len("desktop:"):]).get("Icon", ""), target)
            except Exception:
                pass
        out[a["name"]] = _data_uri(target)
    return out


def _data_uri(path):
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return None


def _mac_icon(app, target):
    with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
        info = plistlib.load(f)
    name = info.get("CFBundleIconFile") or info.get("CFBundleIconName")
    if not name:
        return
    icns = os.path.join(app, "Contents", "Resources", name if name.endswith(".icns") else name + ".icns")
    if os.path.isfile(icns):
        subprocess.run(["sips", "-s", "format", "png", "-Z", "96", icns, "--out", target], capture_output=True, timeout=20)


def _linux_icon(icon, target):
    """Find a PNG for a .desktop Icon= value in the usual icon folders (SVG-only icons are skipped)."""
    if not icon:
        return
    if os.path.isabs(icon):
        src = icon if icon.endswith(".png") and os.path.isfile(icon) else None
    else:
        src = None
        bases = [os.path.expanduser("~/.local/share/icons"), "/usr/share/icons", "/usr/local/share/icons",
                 "/var/lib/flatpak/exports/share/icons", os.path.expanduser("~/.local/share/flatpak/exports/share/icons"),
                 "/var/lib/snapd/desktop/icons", "/usr/share/pixmaps"]
        for size in ("128x128", "96x96", "256x256", "64x64", "512x512", "48x48"):
            for b in bases:
                for theme in ("hicolor", "*"):
                    hits = glob.glob(os.path.join(b, theme, size, "apps", icon + ".png"))
                    if hits:
                        src = hits[0]
                        break
                if src:
                    break
            if src:
                break
        if not src:
            for b in bases:
                p = os.path.join(b, icon + ".png")
                if os.path.isfile(p):
                    src = p
                    break
    if src:
        try:
            from PIL import Image
            Image.open(src).convert("RGBA").resize((96, 96)).save(target)
        except Exception:
            shutil.copyfile(src, target)

