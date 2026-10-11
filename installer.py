"""ChatBridge setup. One file that installs (or removes) ChatBridge for the current Windows user. No admin rights needed.

  ChatBridge-Setup.exe                      normal installer window
  ChatBridge-Setup.exe --silent             no window; options: --dir PATH  --desktop  --no-launch
  "Uninstall ChatBridge.exe" --uninstall    remove it (add --silent and/or --keep-data / --remove-data)
"""
import argparse
import ctypes
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import zipfile
from tkinter import filedialog, messagebox, ttk

try:
    import winreg
except ImportError:
    winreg = None

APP = "ChatBridge"
BUNDLE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ChatBridge"
BG, PANEL, LINE, FG, MUTED, ACCENT, INK = "#0f1115", "#171a20", "#262b34", "#eef0f3", "#9aa3af", "#2dd4bf", "#06201d"
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


# ---------------------------------------------------------------- the window
class Window:
    def __init__(self, mode, args):
        self.mode, self.args = mode, args
        self.q = queue.Queue()
        self.root = tk.Tk()
        r = self.root
        r.title(f"{APP} Setup" if mode == "install" else f"Uninstall {APP}")
        r.configure(bg=BG)
        r.geometry("560x430")
        r.resizable(False, False)
        s = ttk.Style(r)
        s.theme_use("clam")
        s.configure("TProgressbar", troughcolor=PANEL, background=ACCENT, bordercolor=LINE, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        s.map("TCheckbutton", background=[("active", BG)])
        try:
            self.logo = tk.PhotoImage(file=os.path.join(BUNDLE, "assets", "chatbridge.png")).subsample(8, 8)
            r.iconphoto(True, self.logo)
        except tk.TclError:
            self.logo = None
        self.body = tk.Frame(r, bg=BG)
        self.body.pack(fill="both", expand=True, padx=28, pady=22)
        self.show_install() if mode == "install" else self.show_uninstall()

    def label(self, text, size=11, color=FG, bold=False, **kw):
        return tk.Label(self.body, text=text, bg=BG, fg=color, font=("Segoe UI", size, "bold" if bold else "normal"),
                        justify="left", anchor="w", wraplength=500, **kw)

    def button(self, parent, text, cmd, primary=False):
        return tk.Button(parent, text=text, command=cmd, bg=ACCENT if primary else PANEL, fg=INK if primary else FG, relief="flat",
                         font=("Segoe UI", 11, "bold" if primary else "normal"), padx=20, pady=8, cursor="hand2",
                         activebackground=ACCENT if primary else LINE, bd=0)

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def show_install(self):
        self.clear()
        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x")
        if self.logo:
            tk.Label(head, image=self.logo, bg=BG).pack(side="left", padx=(0, 14))
        t = tk.Frame(head, bg=BG)
        t.pack(side="left")
        tk.Label(t, text=APP, bg=BG, fg=FG, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(t, text=f"Version {version()}  ·  Move a chat from one AI to another", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        self.label("Install location", 10, MUTED).pack(fill="x", pady=(22, 4))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        self.dir = tk.StringVar(value=self.args.dir or installed_dir() or default_dir())
        tk.Entry(row, textvariable=self.dir, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 10)).pack(
            side="left", fill="x", expand=True, ipady=7)
        self.button(row, "Browse…", self.browse).pack(side="left", padx=(8, 0))
        self.desk = tk.BooleanVar(value=self.args.desktop)
        self.launch = tk.BooleanVar(value=not self.args.no_launch)
        ttk.Checkbutton(self.body, text="Add a shortcut to my desktop", variable=self.desk).pack(anchor="w", pady=(18, 2))
        ttk.Checkbutton(self.body, text="Start ChatBridge when setup finishes", variable=self.launch).pack(anchor="w")
        self.label("Installs for your Windows account only. No administrator rights needed. "
                   "Your saved chats and settings stay in your AppData folder.", 9, MUTED).pack(fill="x", pady=(16, 0))
        self.status = self.label("", 10, MUTED)
        self.bar = ttk.Progressbar(self.body, maximum=100)
        foot = tk.Frame(self.body, bg=BG)
        foot.pack(side="bottom", fill="x")
        self.go = self.button(foot, "Install", self.start_install, primary=True)
        self.go.pack(side="right")
        self.button(foot, "Cancel", self.root.destroy).pack(side="right", padx=8)

    def browse(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.dir.get()) or None)
        if d:
            self.dir.set(os.path.join(d, APP) if os.path.basename(d).lower() != APP.lower() else d)

    def start_install(self):
        self.go.config(state="disabled", text="Installing…")
        self.status.pack(fill="x", pady=(14, 4))
        self.bar.pack(fill="x")
        target = self.dir.get().strip()

        def work():
            try:
                self.q.put(("done", do_install(target, self.desk.get(), lambda p, m: self.q.put(("p", p, m)))))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.poll(target)

    def poll(self, target):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "p":
                    self.bar["value"], self.status["text"] = m[1], m[2]
                elif m[0] == "err":
                    messagebox.showerror("Setup couldn't finish", m[1])
                    return self.show_install()
                else:
                    return self.finished(m[1])
        except queue.Empty:
            self.root.after(80, lambda: self.poll(target))

    def finished(self, exe):
        self.clear()
        self.label("ChatBridge is installed", 18, FG, True).pack(fill="x", pady=(30, 6))
        self.label("Find it in your Start menu. On first start it looks for your AI apps and chats automatically.", 11, MUTED).pack(fill="x")
        self.label(f"Installed in {os.path.dirname(exe)}", 9, MUTED).pack(fill="x", pady=(12, 0))
        foot = tk.Frame(self.body, bg=BG)
        foot.pack(side="bottom", fill="x")

        def close():
            if self.launch.get():
                subprocess.Popen([exe], cwd=os.path.dirname(exe))
            self.root.destroy()
        self.button(foot, "Finish", close, primary=True).pack(side="right")

    def show_uninstall(self):
        self.clear()
        self.label(f"Uninstall {APP}?", 18, FG, True).pack(fill="x", pady=(10, 6))
        self.label(f"This removes the app from {self.args.dir}.", 11, MUTED).pack(fill="x")
        self.keep = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.body, text="Keep my saved chats and settings", variable=self.keep).pack(anchor="w", pady=(20, 0))
        foot = tk.Frame(self.body, bg=BG)
        foot.pack(side="bottom", fill="x")

        def go():
            relaunch_from_temp(["--uninstall", "--dir", self.args.dir, "--silent", "--remove-data" if not self.keep.get() else "--keep-data"])
            self.root.destroy()
        self.button(foot, "Uninstall", go, primary=True).pack(side="right")
        self.button(foot, "Cancel", self.root.destroy).pack(side="right", padx=8)

    def run(self):
        self.root.mainloop()


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
        return Window("uninstall", a).run()
    if a.silent:
        try:
            exe = do_install(a.dir or installed_dir() or default_dir(), a.desktop)
        except (ValueError, OSError) as e:
            print(e, file=sys.stderr)
            sys.exit(2)
        if not a.no_launch:
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
        return
    Window("install", a).run()


if __name__ == "__main__":
    main()
