"""The window for the ChatBridge installer and uninstaller: dark, crisp, with rounded buttons and switches instead of the
default-looking Windows widgets. All the actual work (copying files, the registry, safety checks) lives in installer.py;
this file only draws things and calls into it through `core`."""
import ctypes
import os
import queue
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

BG, PANEL, PANEL2, LINE = "#0f1115", "#171a20", "#1f242c", "#2a303a"
FG, MUTED, ACCENT, ACCENT_HOVER, INK = "#eef0f3", "#9aa3af", "#2dd4bf", "#5eead4", "#06201d"
OK, DANGER, DANGER_HOVER = "#34d399", "#f87171", "#fca5a5"


def enable_sharp_text():
    """Without this Windows stretches the window on high-resolution screens, which makes the text blurry."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def dark_title_bar(root):
    """Dark title bar (Windows 10 2004+/11) in the window's own colour on Windows 11. Quietly does nothing on older versions."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        for attr, value in ((20, 1), (19, 1),              # use dark mode for the frame
                            (35, 0x0015110F),               # caption colour = BG (COLORREF is 0x00BBGGRR)
                            (36, 0x00F3F0EE)):              # caption text colour = FG
            dwm(hwnd, attr, ctypes.byref(ctypes.c_int(value)), 4)
    except Exception:
        pass


def rrect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Button(tk.Canvas):
    """A rounded button. kind: primary (teal), secondary (grey), danger (red)."""
    COLORS = {"primary": (ACCENT, ACCENT_HOVER, INK), "secondary": (PANEL2, LINE, FG), "danger": (DANGER, DANGER_HOVER, "#2a0a0a")}

    def __init__(self, parent, text, command, font, sc, kind="primary", width=150, height=44, bg=BG):
        w, h = int(width * sc), int(height * sc)
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2", takefocus=0)
        self.command, self.kind, self.w, self.h, self.sc, self.font = command, kind, w, h, sc, font
        self.enabled = True
        self.shape = rrect(self, 1, 1, w - 1, h - 1, int(10 * sc), fill=self.COLORS[kind][0], outline="")
        self.label = self.create_text(w // 2, h // 2, text=text, font=font, fill=self.COLORS[kind][2])
        self.bind("<Enter>", lambda e: self._paint(1))
        self.bind("<Leave>", lambda e: self._paint(0))
        self.bind("<ButtonRelease-1>", lambda e: self.enabled and 0 <= e.x <= w and 0 <= e.y <= h and self.command())

    def _paint(self, hover):
        if self.enabled:
            self.itemconfigure(self.shape, fill=self.COLORS[self.kind][1 if hover else 0])

    def set_text(self, text):
        self.itemconfigure(self.label, text=text)

    def disable(self, text=None):
        self.enabled = False
        self.configure(cursor="arrow")
        self.itemconfigure(self.shape, fill=PANEL2)
        self.itemconfigure(self.label, fill=MUTED, **({"text": text} if text else {}))


class Switch(tk.Canvas):
    """A labelled on/off switch with an optional line of small print under it."""

    def __init__(self, parent, text, variable, font, small, sc, hint="", bg=PANEL, width=480):
        w, h = int(width * sc), int((62 if hint else 36) * sc)
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2", takefocus=0)
        self.var, self.sc = variable, sc
        tw, th = int(42 * sc), int(24 * sc)
        self.track = rrect(self, 1, int(6 * sc), tw, int(6 * sc) + th, th // 2, fill=LINE, outline="")
        self.knob = self.create_oval(0, 0, 1, 1, fill="#ffffff", outline="")
        self.create_text(tw + int(14 * sc), int(6 * sc) + th // 2, text=text, font=font, fill=FG, anchor="w")
        if hint:
            self.create_text(tw + int(14 * sc), int(42 * sc), text=hint, font=small, fill=MUTED, anchor="w", width=w - tw - int(20 * sc))
        self.tw, self.th = tw, th
        self.bind("<Button-1>", lambda e: self.var.set(not self.var.get()))
        self.var.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _draw(self):
        on, sc, tw, th = self.var.get(), self.sc, self.tw, self.th
        self.itemconfigure(self.track, fill=ACCENT if on else LINE)
        pad, top = int(3 * sc), int(6 * sc)
        x = tw - th + pad if on else pad
        self.coords(self.knob, x + 1, top + pad, x + th - 2 * pad + 1, top + th - pad)


class Bar(tk.Canvas):
    """A smooth progress bar: the fill glides towards each new value instead of jumping."""

    def __init__(self, parent, sc, width=520, height=10, bg=BG):
        self.w, self.h = int(width * sc), int(height * sc)
        super().__init__(parent, width=self.w, height=self.h, bg=bg, highlightthickness=0, bd=0)
        rrect(self, 0, 0, self.w, self.h, self.h // 2, fill=PANEL2, outline="")
        self.fill = None
        self.target = self.shown = 0.0
        self._tick()

    def set(self, pct):
        self.target = max(0.0, min(100.0, float(pct)))

    def _tick(self):
        self.shown += (self.target - self.shown) * 0.2 if abs(self.target - self.shown) > 0.3 else self.target - self.shown
        x = max(self.h, int(self.w * self.shown / 100))
        if self.fill:
            self.delete(self.fill)
        if self.shown > 0:
            self.fill = rrect(self, 0, 0, x, self.h, self.h // 2, fill=ACCENT, outline="")
        self.after(16, self._tick)


class Window:
    def __init__(self, mode, args, core):
        enable_sharp_text()
        self.mode, self.args, self.core = mode, args, core
        self.q = queue.Queue()
        self.root = r = tk.Tk()
        self.sc = max(1.0, r.winfo_fpixels("1i") / 96)
        sc = self.sc
        fam = "Segoe UI Variable Display" if "Segoe UI Variable Display" in tkfont.families() else "Segoe UI"
        self.f_xl = tkfont.Font(family=fam, size=24, weight="bold")
        self.f_title = tkfont.Font(family=fam, size=17, weight="bold")
        self.f_body = tkfont.Font(family=fam, size=11)
        self.f_small = tkfont.Font(family=fam, size=9)
        self.f_btn = tkfont.Font(family=fam, size=11, weight="bold")
        r.title(f"{core.APP} Setup" if mode == "install" else f"Remove {core.APP}")
        r.configure(bg=BG)
        r.resizable(False, False)
        w, h = int(640 * sc), int(520 * sc)
        r.geometry(f"{w}x{h}+{(r.winfo_screenwidth() - w) // 2}+{max(0, (r.winfo_screenheight() - h) // 2 - int(30 * sc))}")
        self.logo = self._load_logo(88)
        try:
            r.iconphoto(True, self._load_logo(48))
        except tk.TclError:
            pass
        self.body = tk.Frame(r, bg=BG)
        self.body.pack(fill="both", expand=True, padx=int(40 * sc), pady=int(32 * sc))
        dark_title_bar(r)
        self.show_install() if mode == "install" else self.show_uninstall()

    # ---- small helpers
    def _load_logo(self, size):
        want, best = size * self.sc, None
        for n in (48, 96, 144, 192):
            p = os.path.join(self.core.BUNDLE, "assets", f"installer-logo-{n}.png")
            if os.path.isfile(p):
                best = p
                if n >= want:
                    break
        try:
            return tk.PhotoImage(file=best) if best else None
        except tk.TclError:
            return None

    def px(self, n):
        return int(n * self.sc)

    def text(self, parent, s, font, color=FG, **kw):
        return tk.Label(parent, text=s, font=font, fg=color, bg=kw.pop("bg", BG), justify="left", anchor="w", **kw)

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def header(self, subtitle):
        head = tk.Frame(self.body, bg=BG)
        head.pack(fill="x")
        if self.logo:
            tk.Label(head, image=self.logo, bg=BG).pack(side="left", padx=(0, self.px(18)))
        col = tk.Frame(head, bg=BG)
        col.pack(side="left")
        self.text(col, self.core.APP, self.f_xl).pack(anchor="w")
        self.text(col, subtitle, self.f_body, MUTED).pack(anchor="w", pady=(self.px(2), 0))

    def footer(self):
        f = tk.Frame(self.body, bg=BG)
        f.pack(side="bottom", fill="x")
        return f

    def shorten(self, path, n=46):
        return path if len(path) <= n else path[:14] + "…" + path[-(n - 15):]

    # ---- install
    def show_install(self):
        c, sc = self.core, self.sc
        self.clear()
        self.header(f"Version {c.version()}  ·  Move a chat from one AI app to another")
        self.dir = tk.StringVar(value=c.normalize_install_dir(self.args.dir or c.installed_dir() or c.default_dir()))
        self.desk = tk.BooleanVar(value=self.args.desktop)

        card = tk.Frame(self.body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="x", pady=(self.px(30), 0))
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(fill="x", padx=self.px(20), pady=self.px(18))
        self.text(inner, "INSTALL LOCATION", self.f_small, MUTED, bg=PANEL).pack(anchor="w")
        row = tk.Frame(inner, bg=PANEL)
        row.pack(fill="x", pady=(self.px(6), self.px(14)))
        self.path_lbl = self.text(row, self.dir.get(), self.f_small, FG, bg=PANEL, wraplength=self.px(380))   # the full path, wrapped
        self.path_lbl.pack(side="left")
        Button(row, "Change…", self.change_dir, self.f_body, sc, "secondary", 96, 34, PANEL).pack(side="right")
        Switch(inner, "Add a shortcut to my desktop", self.desk, self.f_body, self.f_small, sc, bg=PANEL).pack(anchor="w")

        self.text(self.body, "✓  For your Windows account only     ✓  No administrator needed     ✓  Your chats stay on this PC",
                  self.f_small, MUTED, wraplength=self.px(540)).pack(anchor="w", pady=(self.px(18), 0))
        f = self.footer()
        Button(f, "Install", self.start_install, self.f_btn, sc, "primary", 150, 46).pack(side="right")
        Button(f, "Cancel", self.root.destroy, self.f_btn, sc, "secondary", 110, 46).pack(side="right", padx=(0, self.px(12)))

    def change_dir(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.dir.get()) or None, title="Choose where to install ChatBridge")
        if d:
            self.dir.set(self.core.normalize_install_dir(d))   # always ends in a folder named ChatBridge
            self.path_lbl.configure(text=self.dir.get())

    def start_install(self):
        c = self.core
        target, desk = self.dir.get(), self.desk.get()
        self.clear()
        self.header(f"Version {c.version()}")
        self.text(self.body, "Installing…", self.f_title).pack(anchor="w", pady=(self.px(46), self.px(4)))
        self.status = self.text(self.body, "Getting ready", self.f_body, MUTED)
        self.status.pack(anchor="w", pady=(0, self.px(18)))
        self.bar = Bar(self.body, self.sc)
        self.bar.pack(anchor="w")
        self.pct = self.text(self.body, "0%", self.f_small, MUTED)
        self.pct.pack(anchor="w", pady=(self.px(8), 0))

        def work():
            try:
                self.q.put(("done", c.do_install(target, desk, lambda p, m: self.q.put(("p", p, m)))))
            except Exception as e:
                self.q.put(("err", str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.poll()

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "p":
                    self.bar.set(m[1])
                    self.status.configure(text=m[2])
                    self.pct.configure(text=f"{int(m[1])}%")
                elif m[0] == "err":
                    return self.failed(m[1])
                else:
                    self.bar.set(100)
                    return self.root.after(450, lambda: self.finished(m[1]))   # let the bar visibly reach the end
        except queue.Empty:
            self.root.after(60, self.poll)

    def finished(self, exe):
        sc = self.sc
        self.clear()
        cv = tk.Canvas(self.body, width=self.px(84), height=self.px(84), bg=BG, highlightthickness=0)
        cv.pack(anchor="w", pady=(self.px(20), 0))
        cv.create_oval(2, 2, self.px(84) - 2, self.px(84) - 2, fill=ACCENT, outline="")
        s = self.px(84)
        cv.create_line(s * .28, s * .52, s * .44, s * .67, s * .73, s * .35, fill=INK, width=self.px(7), capstyle="round", joinstyle="round")
        self.text(self.body, "ChatBridge is ready", self.f_xl).pack(anchor="w", pady=(self.px(18), self.px(4)))
        self.text(self.body, "Find it any time in your Start menu. The first time it opens, it looks for your AI apps and chats by itself.",
                  self.f_body, MUTED, wraplength=self.px(540)).pack(anchor="w")
        self.text(self.body, f"Installed in {self.shorten(os.path.dirname(exe), 60)}", self.f_small, MUTED).pack(anchor="w", pady=(self.px(14), 0))
        f = self.footer()

        def open_app():
            subprocess.Popen([exe], cwd=os.path.dirname(exe))
            self.root.destroy()
        Button(f, "Open ChatBridge", open_app, self.f_btn, sc, "primary", 190, 46).pack(side="right")
        Button(f, "Close", self.root.destroy, self.f_btn, sc, "secondary", 110, 46).pack(side="right", padx=(0, self.px(12)))

    def failed(self, message):
        self.clear()
        self.text(self.body, "Setup couldn't finish", self.f_xl, DANGER).pack(anchor="w", pady=(self.px(30), self.px(10)))
        self.text(self.body, message, self.f_body, FG, wraplength=self.px(540)).pack(anchor="w")
        self.text(self.body, "You can try again, or choose a different folder with “Change…”.", self.f_small, MUTED).pack(anchor="w", pady=(self.px(14), 0))
        f = self.footer()
        Button(f, "Try again", self.show_install, self.f_btn, self.sc, "primary", 150, 46).pack(side="right")
        Button(f, "Close", self.root.destroy, self.f_btn, self.sc, "secondary", 110, 46).pack(side="right", padx=(0, self.px(12)))

    # ---- uninstall
    def show_uninstall(self):
        c, sc = self.core, self.sc
        self.clear()
        self.header(f"Version {c.version()}")
        self.text(self.body, "Remove ChatBridge from this PC?", self.f_title).pack(anchor="w", pady=(self.px(34), self.px(6)))
        self.text(self.body, f"This deletes the app from {self.shorten(self.args.dir, 56)}.", self.f_body, MUTED,
                  wraplength=self.px(540)).pack(anchor="w")
        card = tk.Frame(self.body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="x", pady=(self.px(24), 0))
        self.keep = tk.BooleanVar(value=True)
        Switch(card, "Keep my saved chats and settings", self.keep, self.f_body, self.f_small, sc, bg=PANEL,
               hint="They stay in your AppData folder, so installing again picks up where you left off.").pack(
            anchor="w", padx=self.px(20), pady=self.px(16))
        f = self.footer()

        def go():
            c.relaunch_from_temp(["--uninstall", "--dir", self.args.dir, "--silent", "--keep-data" if self.keep.get() else "--remove-data"])
            self.removing()
        Button(f, "Remove", go, self.f_btn, sc, "danger", 150, 46).pack(side="right")
        Button(f, "Cancel", self.root.destroy, self.f_btn, sc, "secondary", 110, 46).pack(side="right", padx=(0, self.px(12)))

    def removing(self):
        self.clear()
        self.text(self.body, "Removing ChatBridge…", self.f_xl).pack(anchor="w", pady=(self.px(60), self.px(8)))
        self.text(self.body, "This takes a few seconds. You can close this window.", self.f_body, MUTED).pack(anchor="w")
        self.root.after(3500, self.root.destroy)

    def run(self):
        self.root.mainloop()
