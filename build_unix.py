"""Builds ChatBridge for macOS or Linux, on that system:   python build_unix.py

macOS:  release/ChatBridge-<version>-mac-<arm64|x86_64>.dmg
        Signed and notarized when these are set (GitHub Actions secrets; see RELEASING.md), unsigned otherwise:
          MACOS_SIGN_IDENTITY   e.g. "Developer ID Application: Your Name (TEAMID)"  (the certificate must be in the keychain)
          APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD   for notarization (an app-specific password from appleid.apple.com)
Linux:  release/ChatBridge-<version>-x86_64.AppImage
        Needs appimagetool on PATH (or APPIMAGETOOL=/path/to/appimagetool). Uses the Qt web view (pip install PyQt6 PyQt6-WebEngine).

Runs the tests first. Writes release/SHA256SUMS-<platform>.txt.
"""
import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
MAC, LINUX = sys.platform == "darwin", sys.platform.startswith("linux")
if not (MAC or LINUX):
    sys.exit("build_unix.py is for macOS and Linux. On Windows use make_release.py.")
VERSION = re.search(r'VERSION = "([^"]+)"', open("chatbridge_app.py", encoding="utf-8").read()).group(1)
OUT = os.path.join(HERE, "release")
BUNDLE_ID = "com.besmir25.chatbridge"


def run(cmd, **kw):
    shown = ["***" if i and cmd[i - 1] == "--password" else c for i, c in enumerate(cmd)]   # never print the notarization password
    print("\n>", " ".join(shown))
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f"Stopped: {cmd[0]} failed.")
    return r


def tests():
    run([sys.executable, "-W", "ignore", "-m", "unittest", "discover", "-s", "tests"])


def pyinstaller(extra):
    import PyInstaller.__main__ as pyi
    exclude = ["numpy", "scipy", "pandas", "matplotlib", "IPython", "notebook", "jupyter", "PyQt5", "PySide2", "PySide6",
               "sphinx", "pytest", "sklearn", "numba", "bokeh", "dask", "h5py", "lxml", "sqlalchemy", "cryptography", "tkinter"]
    if MAC:
        exclude.append("PyQt6")          # macOS uses its own WebKit (Cocoa), no Qt
    if LINUX:
        exclude += ["gi", "PIL"]         # the AppImage uses Qt, not GTK; app icons are copied as they are (desktop.py falls back)
    sep = os.pathsep
    args = ["--noconfirm", "--clean", "--windowed", "--name", "ChatBridge",
            "--add-data", f"{os.path.join(HERE, 'ui')}{sep}ui",
            "--add-data", f"{os.path.join(HERE, 'assets', 'chatbridge.png')}{sep}assets",
            "--add-data", f"{os.path.join(HERE, 'extension')}{sep}extension",
            "--add-data", f"{os.path.join(HERE, 'CHANGELOG.md')}{sep}.",
            "--distpath", os.path.join(HERE, "dist"), "--workpath", os.path.join(HERE, "build"),
            "--specpath", os.path.join(HERE, "build")] + extra
    for m in exclude:
        args += ["--exclude-module", m]
    args.append(os.path.join(HERE, "chatbridge_app.py"))
    pyi.run(args)


def checksums(files, tag):
    with open(os.path.join(OUT, f"SHA256SUMS-{tag}.txt"), "w") as f:
        for p in files:
            f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {os.path.basename(p)}\n")


# ---------------------------------------------------------------- macOS
def mac_icns():
    from PIL import Image
    path = os.path.join(HERE, "build", "chatbridge.icns")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.open(os.path.join(HERE, "assets", "chatbridge.png")).convert("RGBA").save(
        path, sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    return path


ENTITLEMENTS = {   # what the hardened runtime must allow for a Python app with a web view that asks System Events to paste
    "com.apple.security.cs.allow-jit": True,
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
    "com.apple.security.cs.disable-library-validation": True,
    "com.apple.security.automation.apple-events": True,
}


def build_mac():
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "").strip()
    ent = os.path.join(HERE, "build", "entitlements.plist")
    os.makedirs(os.path.dirname(ent), exist_ok=True)
    with open(ent, "wb") as f:
        plistlib.dump(ENTITLEMENTS, f)
    extra = ["--icon", mac_icns(), "--osx-bundle-identifier", BUNDLE_ID]
    if identity:
        extra += ["--codesign-identity", identity, "--osx-entitlements-file", ent]
    pyinstaller(extra)
    app = os.path.join(HERE, "dist", "ChatBridge.app")
    info_path = os.path.join(app, "Contents", "Info.plist")
    with open(info_path, "rb") as f:
        info = plistlib.load(f)
    info.update({
        "CFBundleDisplayName": "ChatBridge", "CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True, "LSApplicationCategoryType": "public.app-category.productivity",
        "NSAppleEventsUsageDescription": "ChatBridge pastes the conversation you chose into the AI app you picked. It never presses Enter.",
        "NSHumanReadableCopyright": "MIT License",
    })
    with open(info_path, "wb") as f:
        plistlib.dump(info, f)
    if identity:   # the plist changed, so the outer signature must be made again
        run(["codesign", "--force", "--options", "runtime", "--timestamp", "--entitlements", ent, "--sign", identity, app])
        run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app])
    arch = os.uname().machine            # arm64 or x86_64
    os.makedirs(OUT, exist_ok=True)
    dmg = os.path.join(OUT, f"ChatBridge-{VERSION}-mac-{arch}.dmg")
    stage = os.path.join(HERE, "build", "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    run(["ditto", app, os.path.join(stage, "ChatBridge.app")])
    os.symlink("/Applications", os.path.join(stage, "Applications"))     # drag the app onto this to install
    if os.path.exists(dmg):
        os.remove(dmg)
    run(["hdiutil", "create", "-volname", "ChatBridge", "-srcfolder", stage, "-ov", "-format", "UDZO", dmg])
    if identity:
        run(["codesign", "--force", "--timestamp", "--sign", identity, dmg])
        if all(os.environ.get(k) for k in ("APPLE_ID", "APPLE_TEAM_ID", "APPLE_APP_PASSWORD")):
            run(["xcrun", "notarytool", "submit", dmg, "--apple-id", os.environ["APPLE_ID"], "--team-id", os.environ["APPLE_TEAM_ID"],
                 "--password", os.environ["APPLE_APP_PASSWORD"], "--wait"])
            run(["xcrun", "stapler", "staple", dmg])
            run(["spctl", "--assess", "--type", "open", "--context", "context:primary-signature", "--verbose", dmg])
        else:
            print("\nSigned but NOT notarized (APPLE_ID / APPLE_TEAM_ID / APPLE_APP_PASSWORD not set).")
    else:
        print("\nUNSIGNED build (MACOS_SIGN_IDENTITY not set): macOS will warn on first open.")
    checksums([dmg], f"mac-{arch}")
    return dmg


# ---------------------------------------------------------------- Linux
APPRUN = """#!/bin/sh
# Starts ChatBridge from inside the AppImage.
HERE="$(dirname "$(readlink -f "$0")")"
export PYWEBVIEW_GUI=qt
# Keep Chromium's sandbox wherever it can work. An AppImage can't use its setuid helper, so on systems that block
# unprivileged user namespaces (e.g. Ubuntu 24.04's AppArmor rule) the web view would not start at all; only there is it
# switched off. The window only ever shows ChatBridge's own files under a strict Content-Security-Policy.
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null)" = "1" ] || ! unshare -Ur true 2>/dev/null; then
  export QTWEBENGINE_DISABLE_SANDBOX=1
fi
exec "$HERE/usr/lib/chatbridge/ChatBridge" "$@"
"""
DESKTOP = """[Desktop Entry]
Type=Application
Name=ChatBridge
GenericName=Move AI chats between apps
Comment=Continue an AI conversation in a different AI app
Exec=ChatBridge
Icon=chatbridge
Categories=Utility;Office;
Terminal=false
StartupWMClass=ChatBridge
"""


KEEP_LOCALES = ("en-US", "en-GB", "es", "es-419", "pt-BR", "pt-PT", "fr", "de", "zh-CN", "ja")   # the app's languages


def trim_qt(root):
    """Qt ships translations for ~100 languages and Chromium's developer tools; ChatBridge needs neither (about 60 MB)."""
    qt = next((os.path.join(d, "Qt6") for d, subs, _ in os.walk(root) if "Qt6" in subs and d.endswith("PyQt6")), None)
    if not qt:
        return
    locales = os.path.join(qt, "translations", "qtwebengine_locales")
    for name in os.listdir(locales) if os.path.isdir(locales) else []:
        if name.endswith(".pak") and name[:-4] not in KEEP_LOCALES:
            os.remove(os.path.join(locales, name))
    tr = os.path.join(qt, "translations")
    for name in os.listdir(tr) if os.path.isdir(tr) else []:
        if name.endswith(".qm"):
            os.remove(os.path.join(tr, name))          # Qt's own dialogs in other languages; the screen has its own translations
    devtools = os.path.join(qt, "resources", "qtwebengine_devtools_resources.pak")
    if os.path.isfile(devtools):
        os.remove(devtools)


def build_linux():
    tool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if not tool:
        sys.exit("appimagetool wasn't found. Download it from https://github.com/AppImage/appimagetool/releases "
                 "and set APPIMAGETOOL=/path/to/it.")
    pyinstaller(["--icon", os.path.join(HERE, "assets", "chatbridge.png"), "--hidden-import", "webview.platforms.qt"])
    appdir = os.path.join(HERE, "build", "ChatBridge.AppDir")
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(os.path.join(HERE, "dist", "ChatBridge"), os.path.join(appdir, "usr", "lib", "chatbridge"), symlinks=True)
    trim_qt(os.path.join(appdir, "usr", "lib", "chatbridge"))
    with open(os.path.join(appdir, "AppRun"), "w") as f:
        f.write(APPRUN)
    os.chmod(os.path.join(appdir, "AppRun"), 0o755)
    with open(os.path.join(appdir, "chatbridge.desktop"), "w") as f:
        f.write(DESKTOP)
    shutil.copyfile(os.path.join(HERE, "assets", "chatbridge.png"), os.path.join(appdir, "chatbridge.png"))
    icons = os.path.join(appdir, "usr", "share", "icons", "hicolor", "256x256", "apps")
    os.makedirs(icons, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "assets", "chatbridge.png"), os.path.join(icons, "chatbridge.png"))
    os.makedirs(OUT, exist_ok=True)
    image = os.path.join(OUT, f"ChatBridge-{VERSION}-x86_64.AppImage")
    run([tool, "--no-appstream", appdir, image], env={**os.environ, "ARCH": "x86_64"})
    checksums([image], "linux")
    return image


if __name__ == "__main__":
    if "--skip-tests" not in sys.argv:
        tests()
    path = build_mac() if MAC else build_linux()
    print(f"\nReady: {path}  ({os.path.getsize(path) / 1e6:.1f} MB)")
