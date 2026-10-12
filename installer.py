"""ChatBridge setup. One file that installs (or removes) ChatBridge for the current Windows user. No admin rights needed.

  ChatBridge-Setup.exe                      normal installer window
  ChatBridge-Setup.exe --silent             no window; options: --dir PATH  --desktop  --no-launch
  "Uninstall ChatBridge.exe" --uninstall    remove it (add --silent and/or --keep-data / --remove-data)
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from tkinter import messagebox

from installer_ui import Window

try:
    import winreg
except ImportError:
    winreg = None

APP = "ChatBridge"
BUNDLE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ChatBridge"
NOWIN = 0x08000000


def version():
    try:
        with open(os.path.join(BUNDLE, "version.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "1.0.0"


def known_folder(csidl):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def default_dir():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP)


def start_menu_link():
    return os.path.join(known_folder(0x02), f"{APP}.lnk")        # CSIDL_PROGRAMS


def desktop_link():
    return os.path.join(known_folder(0x10), f"{APP}.lnk")        # CSIDL_DESKTOPDIRECTORY


def make_shortcut(lnk, target, workdir):
    # Paths go in through environment variables, never pasted into the script, so no folder or user name can break the quoting.
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CB_LNK);$s.TargetPath=$env:CB_TARGET;"
          "$s.WorkingDirectory=$env:CB_DIR;$s.IconLocation=$env:CB_TARGET;$s.Description='Move chats between AI apps';$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=NOWIN, capture_output=True, timeout=60,
                       env={**os.environ, "CB_LNK": lnk, "CB_TARGET": target, "CB_DIR": workdir})
    if r.returncode or not os.path.exists(lnk):
        raise OSError(f"Couldn't create the shortcut {lnk}")


MARKER = ".chatbridge-install"


def is_ours(d):
    """True only for a folder this installer made: it has our marker, or both ChatBridge.exe and its uninstaller."""
    return os.path.isfile(os.path.join(d, MARKER)) or (
        os.path.isfile(os.path.join(d, f"{APP}.exe")) and os.path.isfile(os.path.join(d, f"Uninstall {APP}.exe")))


def normalize_install_dir(d):
    """Whatever the user types, install into a folder named ChatBridge (so 'D:\\Games' becomes 'D:\\Games\\ChatBridge')."""
    d = os.path.abspath(os.path.expandvars((d or "").strip().strip('"')))
    return d if os.path.basename(d.rstrip("\\/")).lower() == APP.lower() else os.path.join(d, APP)


def is_safe_install_dir(d):
    """Deleting is only allowed for a folder named ChatBridge that this installer created - never a drive, Downloads, etc."""
    d = os.path.abspath(d or "")
    if os.path.dirname(d) == d or os.path.basename(d.rstrip("\\/")).lower() != APP.lower():
        return False
    return is_ours(d)


def app_running(install_dir):
    exe = os.path.join(install_dir, f"{APP}.exe")
    if not os.path.exists(exe):
        return False
    try:
        with open(exe, "ab"):
            return False
    except OSError:
        return True


def stop_app():
    subprocess.run(["taskkill", "/IM", f"{APP}.exe", "/F"], creationflags=NOWIN, capture_output=True)
    time.sleep(1)


def dir_size_kb(path):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs) // 1024


# ---------------------------------------------------------------- install / uninstall work
def do_install(install_dir, desktop, progress=lambda pct, msg: None):
    payload = os.path.join(BUNDLE, "payload.zip")
    if not os.path.isfile(payload):
        raise FileNotFoundError("This setup file is incomplete (payload.zip is missing).")
    install_dir = normalize_install_dir(install_dir)
    if os.path.isdir(install_dir) and os.listdir(install_dir) and not is_ours(install_dir):
        raise ValueError(f"The folder {install_dir} already has other files in it. Choose an empty or new folder.")
    if app_running(install_dir):
        stop_app()
    progress(2, "Preparing…")
    if os.path.isdir(os.path.join(install_dir, "_internal")):
        shutil.rmtree(os.path.join(install_dir, "_internal"), ignore_errors=True)   # an upgrade starts clean
    os.makedirs(install_dir, exist_ok=True)
    with zipfile.ZipFile(payload) as z:
        names = z.namelist()
        for i, n in enumerate(names, 1):
            z.extract(n, install_dir)
            if i % 25 == 0 or i == len(names):
                progress(5 + int(80 * i / len(names)), "Copying files…")
    uninstaller = os.path.join(install_dir, f"Uninstall {APP}.exe")
    shutil.copyfile(sys.executable, uninstaller)
    with open(os.path.join(install_dir, MARKER), "w", encoding="utf-8") as f:
        f.write(f"Installed by ChatBridge Setup {version()}. Uninstall only deletes folders that contain this file.\n")
    progress(88, "Creating shortcuts…")
    exe = os.path.join(install_dir, f"{APP}.exe")
    make_shortcut(start_menu_link(), exe, install_dir)
    if desktop:
        make_shortcut(desktop_link(), exe, install_dir)
    progress(95, "Registering with Windows…")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", APP), ("DisplayVersion", version()), ("Publisher", APP), ("InstallLocation", install_dir),
                          ("DisplayIcon", exe), ("UninstallString", f'"{uninstaller}" --uninstall')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name, val in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", dir_size_kb(install_dir))):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
    progress(100, "Done")
    return exe


def installed_dir():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            return winreg.QueryValueEx(k, "InstallLocation")[0]
    except OSError:
        return None


def do_uninstall(install_dir, remove_data):
    """Returns False (and deletes nothing) if install_dir isn't a ChatBridge folder made by this installer."""
    if not is_safe_install_dir(install_dir):
        return False
    stop_app()
    for lnk in (start_menu_link(), desktop_link()):
        try:
            os.remove(lnk)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    shutil.rmtree(install_dir, ignore_errors=True)
    if remove_data:
        shutil.rmtree(os.path.join(os.environ.get("APPDATA", ""), APP), ignore_errors=True)
        home_cb = os.path.join(os.path.expanduser("~"), APP)     # the saved hand-over files (full chat text)
        shutil.rmtree(os.path.join(home_cb, "handoffs"), ignore_errors=True)
        try:
            os.rmdir(home_cb)   # only if now empty
        except OSError:
            pass
    return True


def relaunch_from_temp(args):
    """The uninstaller can't delete the folder it's running from, so it copies itself to temp and continues there."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="cb-uninstall-"), "uninstall.exe")
    shutil.copyfile(sys.executable, tmp)
    subprocess.Popen([tmp, *args, "--from-temp"], creationflags=NOWIN | 0x00000008, close_fds=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--dir", default="")
    ap.add_argument("--desktop", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--keep-data", action="store_true")
    ap.add_argument("--remove-data", action="store_true")
    ap.add_argument("--from-temp", action="store_true")
    a = ap.parse_args()
    if a.uninstall:
        a.dir = a.dir or installed_dir() or os.path.dirname(sys.executable)
        norm = lambda p: os.path.normcase(os.path.abspath(p))
        if not is_safe_install_dir(a.dir):   # checked up front, so a wrong folder is never touched (and the user is told)
            if not a.silent:
                messagebox.showerror("Nothing was removed", f"{a.dir}\n\nisn't a ChatBridge folder created by this installer, "
                                     "so it was left alone.")
            sys.exit(2)
        if a.from_temp or (a.silent and norm(os.path.dirname(sys.executable)) != norm(a.dir)):
            time.sleep(1.5)  # let the first copy exit so its files can be deleted
            do_uninstall(a.dir, a.remove_data)
            if a.from_temp:  # remove this temporary copy once we've exited; retry because Windows keeps the exe locked briefly
                mine = os.path.dirname(sys.executable)
                bat = os.path.join(tempfile.gettempdir(), f"cb-cleanup-{os.getpid()}.bat")
                with open(bat, "w") as f:
                    f.write(f'@echo off\nfor /l %%i in (1,1,20) do (\n  rmdir /s /q "{mine}" 2>nul\n'
                            f'  if not exist "{mine}" goto done\n  ping -n 2 127.0.0.1 >nul\n)\n:done\ndel "%~f0"\n')
                subprocess.Popen(["cmd", "/c", bat], creationflags=NOWIN, close_fds=True)
            return
        if a.silent:
            relaunch_from_temp(["--uninstall", "--dir", a.dir, "--silent"] + (["--remove-data"] if a.remove_data else []))
            return
        return Window("uninstall", a, sys.modules[__name__]).run()
    if a.silent:
        try:
            exe = do_install(a.dir or installed_dir() or default_dir(), a.desktop)
        except (ValueError, OSError) as e:
            print(e, file=sys.stderr)
            sys.exit(2)
        if not a.no_launch:
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
        return
    Window("install", a, sys.modules[__name__]).run()


if __name__ == "__main__":
    main()
