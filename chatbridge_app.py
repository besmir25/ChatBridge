"""ChatBridge - the modern window. A native window (Edge WebView2 on Windows, WebKit on macOS, Qt or WebKitGTK on Linux)
showing ui/index.html, backed by chatbridge.py."""
import hmac
import json
import logging
import os
import re
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import webview

import chatbridge as cb
import desktop
import webview_patch
from release_tools import changelog_between

VERSION = "1.4.0"
REPO = "besmir25/ChatBridge"   # GitHub "owner/name" that hosts the releases (change here if the repo is named differently)
# When packaged by PyInstaller the screen files sit next to the code inside _MEIPASS; otherwise next to this file.
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(cb.APP_DIR, "chatbridge.log")
SCAN_CACHE = os.path.join(cb.APP_DIR, "scan_cache.json")
ICON_DIR = os.path.join(cb.APP_DIR, "icons")


# ---------------------------------------------------------------- system helpers (desktop.py has the Windows, macOS and Linux versions)
set_clipboard = desktop.set_clipboard
foreground_title = desktop.foreground_title
window_open = desktop.window_open


# ---------------------------------------------------------------- AI websites you can send a chat to
# (name, address, shown by default). The chat is copied and saved as a file, then the site opens in your normal browser.
WEB_TOOLS = [
    ("ChatGPT (website)", "https://chatgpt.com/", True),
    ("Claude.ai (website)", "https://claude.ai/new", True),
    ("Gemini (website)", "https://gemini.google.com/app", True),
    ("Copilot (website)", "https://copilot.microsoft.com/", False),
    ("Perplexity (website)", "https://www.perplexity.ai/", False),
    ("Grok (website)", "https://grok.com/", False),
    ("DeepSeek (website)", "https://chat.deepseek.com/", False),
    ("Mistral Le Chat (website)", "https://chat.mistral.ai/chat", False),
]


# ---------------------------------------------------------------- update check
def parse_version(s):
    """'v1.2.3' -> (1, 2, 3). Missing parts count as 0."""
    nums = [int(n) for n in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def fetch_latest_release(repo=REPO):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"User-Agent": f"ChatBridge/{VERSION}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def update_info(fetch=fetch_latest_release):
    """Ask GitHub for the newest release. It sends nothing about you or your chats. Never downloads or installs anything."""
    try:
        rel = fetch()
    except urllib.error.HTTPError as e:
        return {"status": "none" if e.code == 404 else "offline"}   # 404 = no release published yet
    except Exception:
        return {"status": "offline"}
    tag = str(rel.get("tag_name") or "")
    newer = parse_version(tag) > parse_version(VERSION)
    return {"status": "available" if newer else "current", "version": tag.lstrip("vV"), "url": rel.get("html_url") or "",
            "notes": str(rel.get("body") or "")[:600]}


# ---------------------------------------------------------------- receives chats from the browser extension
CAPTURE_PORTS = range(47821, 47826)
_EXT_ORIGINS = ("chrome-extension://", "moz-extension://", "edge-extension://")


class _ExclusiveServer(ThreadingHTTPServer):
    """On Windows a port can be shared by default, so a second program (or a second ChatBridge) could sit on the same
    port and receive our requests. Claim it exclusively instead; if it's taken, the caller moves on to the next port.
    On Linux, SO_REUSEADDR never lets two programs listen on one port. On macOS another program may hold 0.0.0.0 on the same
    port, but connections to 127.0.0.1 go to the more specific bind (ours); an exact duplicate would need SO_REUSEPORT. It
    lets ChatBridge reopen its port right after a restart (otherwise refused for about a minute while old connections finish)."""
    allow_reuse_address = not desktop.WINDOWS

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class _CaptureHandler(BaseHTTPRequestHandler):
    api = None      # set when the server starts
    timeout = 10    # a stalled client can't hold a thread forever

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/ping":
            out = {"app": "ChatBridge", "version": VERSION}
            nonce = urllib.parse.parse_qs(query).get("nonce", [""])[0][:128]
            if nonce:
                # Proves to the extension that this is the real ChatBridge (it knows the pairing code) BEFORE the extension
                # sends the code or any chat. Another program that merely answers on this port can't produce it.
                out["proof"] = hmac.new(self.api._capture_token().encode(), nonce.encode(), "sha256").hexdigest()
            return self._send(200, out)
        self._send(404, {"error": "not found"})

    def _refuse(self, code, message):
        """Read (and throw away) a little of the request first: replying and closing with unread data makes Windows reset the
        connection, so the sender would see a crash instead of a clear 'no'."""
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if 0 < n <= 1_000_000:
                self.rfile.read(n)
        except (ValueError, OSError):
            pass
        self._send(code, {"error": message})

    def do_POST(self):
        # Any web page can try to talk to localhost, so only the extension (which sends the pairing token) is let in.
        origin = self.headers.get("Origin", "")
        if origin and not origin.startswith(_EXT_ORIGINS):
            return self._refuse(403, "forbidden origin")
        if not hmac.compare_digest(self.headers.get("X-ChatBridge-Token", "").encode("utf-8", "replace"),
                                   self.api._capture_token().encode()):   # bytes, so odd characters can't raise
            return self._refuse(401, "bad token - copy the pairing code from ChatBridge Settings")
        if self.path != "/capture":
            return self._refuse(404, "not found")
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= 8_000_000:
                return self._send(413, {"error": "too large"})
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "bad json"})
        res = self.api._capture(payload)
        self._send(200 if res.get("ok") else 400, res)


# ---------------------------------------------------------------- the bridge the page talks to
class Api:
    def __init__(self):
        self._window = None
        loaded = cb.load_json(cb.LIB_PATH, [])
        # Check every saved item once at start-up, so one damaged entry can never leave the window blank
        self._lib = [c for c in (cb.clean_conv(x, trusted=True) for x in (loaded if isinstance(loaded, list) else [])) if c]
        cfg = cb.load_json(cb.CFG_PATH, {})
        self._cfg = {**cb.DEFAULT_CFG, **(cfg if isinstance(cfg, dict) else {})}
        cb.prune_handoffs()
        self._found, self._apps, self._icons = [], [], {}
        cache = cb.load_json(SCAN_CACHE, {})
        self._apps = cache.get("apps", [])
        self._icons = desktop.app_icons(self._apps, ICON_DIR, cached_only=True)   # icons saved by the last scan
        self._proj = None
        self._chat = None
        self._busy = threading.Lock()
        self._lock = threading.RLock()
        self._update_fetch = fetch_latest_release   # replaced in tests
        self._made_files = set()                    # files we created, the only ones show_file may reveal
        self._capture_srv, self._capture_port = None, None
        self._paste_delay = 2.5      # seconds to let an app that is already open settle
        self._cold_delay = 9.0       # an app that had to start from closed needs longer before its message box works

    # ---- updates
    def whats_new(self):
        """After an upgrade, return the changelog entries for the versions you skipped (once). A fresh install shows nothing."""
        seen = self._cfg.get("seen_version") or ("1.0.0" if self._cfg.get("welcomed") else None)  # 1.0.0 didn't record it
        self._cfg["seen_version"] = VERSION
        cb.save_json(cb.CFG_PATH, self._cfg)
        if not seen or parse_version(seen) >= parse_version(VERSION):
            return {"show": False}
        try:
            with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as f:
                secs = changelog_between(f.read(), seen, VERSION)
        except OSError:
            return {"show": False}
        return {"show": bool(secs), "version": VERSION, "sections": [{"version": v, "body": b} for v, b in secs]}

    def check_update(self, manual=False):
        """Automatic checks run at most once a day and only if enabled; 'Check now' always runs."""
        if not manual:
            if not self._cfg.get("update_check", True) or time.time() - self._cfg.get("last_update_check", 0) < 86400:
                return {"status": "skipped"}
        info = update_info(self._update_fetch)
        if info["status"] in ("current", "available", "none"):
            self._cfg["last_update_check"] = time.time()
            cb.save_json(cb.CFG_PATH, self._cfg)
        return {**info, "current": VERSION}

    def open_release(self, url):
        """Open a release page in the browser - only pages of this project on github.com."""
        import webbrowser
        if str(url).startswith(f"https://github.com/{REPO}/"):
            webbrowser.open(url)
            return {"ok": True}
        return {"error": "That link isn't a ChatBridge release page."}

    # ---- browser capture
    def _capture_token(self):
        if not self._cfg.get("capture_token"):
            self._cfg["capture_token"] = secrets.token_urlsafe(24)
            cb.save_json(cb.CFG_PATH, self._cfg)
        return self._cfg["capture_token"]

    def start_capture_server(self):
        """Listen on 127.0.0.1 only. Returns the port, or None if every port is taken."""
        _CaptureHandler.api = self
        for port in CAPTURE_PORTS:
            try:
                srv = _ExclusiveServer(("127.0.0.1", port), _CaptureHandler)
            except OSError:
                continue
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self._capture_srv, self._capture_port = srv, port
            return port
        return None

    def _capture(self, p):
        if not isinstance(p, dict) or not isinstance(p.get("messages"), list):
            return {"error": "no messages"}
        msgs = []
        for m in p["messages"][:3000]:
            if isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].strip():
                msgs.append({"role": cb._norm_role(m.get("role", "assistant")), "content": m["content"].strip()[:200_000]})
        if not msgs:
            return {"error": "no messages"}
        title = str(p.get("title") or "Web chat").strip()[:120] or "Web chat"
        source = str(p.get("source") or "Web chat").strip()[:40]
        conv = cb.new_conv(title, source, msgs)
        url = str(p.get("url") or "")[:500]
        if url:
            conv["origin"] = "web:" + url   # capturing the same conversation again updates it instead of duplicating it
        with self._lock:
            self._lib = [c for c in self._lib if not (url and c.get("origin") == conv.get("origin"))]
            self._lib.insert(0, conv)
            self._save()
        self._push("onCaptured", {"id": conv["id"], "title": title, "source": source, "count": len(msgs), "chats": self._chats()})
        return {"ok": True, "id": conv["id"], "count": len(msgs)}

    def _push(self, fn, payload):
        if self._window:
            try:
                js = f"window.{fn} && window.{fn}({json.dumps(payload)})"
                run = getattr(self._window, "run_js", None)       # no result needed: run_js skips pywebview's eval wrapper,
                (run or self._window.evaluate_js)(js)              # which the page's CSP blocks on macOS and Linux
            except Exception:
                pass

    def open_extension_folder(self):
        folder = os.path.join(HERE, "extension")
        if os.path.isdir(folder):
            desktop.open_path(folder)
            return {"ok": True}
        return {"error": "The extension folder wasn't found next to the app."}

    # ---- plumbing
    def _emit(self, state, msg="", **extra):
        self._push("onProgress", {"state": state, "msg": msg, **extra})

    def _save(self):
        with self._lock:
            cb.save_json(cb.LIB_PATH, self._lib)

    def _pool(self):
        have = {c.get("origin") for c in self._lib if c.get("origin")}
        return self._lib + [c for c in self._found if c["origin"] not in have]

    def _by_ids(self, ids):
        pool = {c["id"]: c for c in self._pool()}
        return [pool[i] for i in ids if i in pool]

    def _chats(self):
        out = []
        with self._lock:
            lib_ids = {c["id"] for c in self._lib}
            for c in self._pool():
                try:    # one odd item must not take the whole list down
                    chars = sum(len(m["content"]) for m in c["messages"])
                    out.append({"id": c["id"], "title": str(c["title"]), "source": str(c.get("source") or "Other"),
                                "created": str(c.get("created", "")), "count": len(c["messages"]),
                                "kind": "project" if c.get("kind") == "project" else "chat", "saved": c["id"] in lib_ids,
                                "chars": chars, "tokens": chars // 4,
                                "real_tokens": sum(v for v in (c.get("usage") or {}).values() if isinstance(v, int)) or None,
                                "mode": c.get("mode") if c.get("mode") in ("full", "outline", "tree") else None})
                except (KeyError, TypeError):
                    continue
        return out

    def _apps_out(self):
        out = []
        compat = self._cfg.get("compat", {})
        for i, a in enumerate(self._apps):
            icon = self._icons.get(a["name"])
            if not icon and a["kind"] == "Local server":  # e.g. the Ollama server uses the Ollama app's icon
                icon = next((v for k, v in self._icons.items() if v and k.lower().startswith(a["name"].split()[0].lower())), None)
            out.append({"key": i, "name": a["name"], "kind": a["kind"], "icon": icon, "models": a.get("models", []),
                        "info": a.get("info", ""), "tested": (compat.get(a["name"]) or {}).get("ok"),
                        "note": cb.profile_for(a["name"]).get("note", "")})
        chosen = self._cfg.get("enabled_tools")          # None = the person hasn't picked yet: show everything we found
        known = set(self._cfg.get("known_tools", []))    # tools that were on the list when they last chose
        for o in out:                                    # a tool installed since then is shown by default, not hidden
            o["enabled"] = chosen is None or o["name"] in chosen or o["name"] not in known
        order = {"Desktop app": 0, "Local server": 1, "CLI tool": 2, "Possible AI app": 3}
        return sorted(out, key=lambda x: (order.get(x["kind"], 9), x["name"].lower()))

    def _web_out(self):
        chosen = self._cfg.get("enabled_tools")
        return [{"key": f"web:{i}", "name": n, "url": u, "kind": "Website",
                 "enabled": (n in chosen) if chosen is not None else default}
                for i, (n, u, default) in enumerate(WEB_TOOLS)]

    def set_tools(self, names):
        """Which tools the person wants to see (installed apps and websites). Saved so the choice sticks."""
        names = [n for n in (names if isinstance(names, list) else []) if isinstance(n, str)][:200]
        self._cfg["enabled_tools"], self._cfg["tools_chosen"] = names, True
        self._cfg["known_tools"] = [a["name"] for a in self._apps] + [w[0] for w in WEB_TOOLS]
        cb.save_json(cb.CFG_PATH, self._cfg)
        return {"apps": self._apps_out(), "web": self._web_out()}

    def _settings(self):
        c = self._cfg
        return {"provider": c["provider"], "base_url": c["base_url"], "model": c["model"], "has_key": bool(c["api_key"]),
                "autopaste": c.get("autopaste", True), "size": c.get("ui_size", 17),
                "theme": {"dark": "midnight"}.get(c.get("theme"), c.get("theme", "light")), "font": c.get("font", "sans"),
                "providers": list(cb.PROVIDERS), "about_me": c.get("about_me", ""),
                "price_in": c.get("price_in", ""), "price_out": c.get("price_out", ""),
                "compact": c.get("compact", False), "scrub": c.get("scrub", True), "last_target": c.get("last_target"),
                "capture_port": self._capture_port, "capture_token": self._capture_token(),
                "update_check": c.get("update_check", True), "version": VERSION,
                "group_by": c.get("group_by") if c.get("group_by") in ("app", "date") else "date",
                "language": c.get("language") if c.get("language") in ("auto", "en", "es", "pt-BR", "fr", "de", "zh-CN", "ja") else "auto"}

    # ---- startup and scanning
    def bootstrap(self):
        if not self._cfg.get("ui_v2"):      # the friendlier look is the default once; after that the person's choice wins
            self._cfg.update({"ui_v2": True, "theme": "light", "font": "sans", "ui_size": 17})
            cb.save_json(cb.CFG_PATH, self._cfg)
        return {"chats": self._chats(), "apps": self._apps_out(), "web": self._web_out(), "settings": self._settings(),
                "welcomed": bool(self._cfg.get("welcomed")), "tools_chosen": bool(self._cfg.get("tools_chosen")),
                "os": desktop.NAME, "can_paste": desktop.can_press_keys()}

    def scan_all(self):
        apps = cb.scan_apps()
        self._icons = desktop.app_icons(apps, ICON_DIR)
        self._apps = apps
        cb.save_json(SCAN_CACHE, {"apps": [{k: v for k, v in a.items() if k != "launch_fn"} for a in apps]})
        self._found = cb.discover_chats()
        return {"chats": self._chats(), "apps": self._apps_out(), "web": self._web_out(),
                "tools_chosen": bool(self._cfg.get("tools_chosen"))}

    def search_chats(self, query):
        """Which chats mention the text? (Titles are matched in the page; this looks inside the messages too.)"""
        q = (query or "").strip().lower()[:100]
        if len(q) < 2:
            return {"hits": {}}
        hits = {}
        for c in self._pool():
            try:
                for m in c["messages"]:
                    at = m["content"].lower().find(q)
                    if at >= 0:
                        s = max(0, at - 40)
                        hits[c["id"]] = ("…" if s else "") + m["content"][s:at + len(q) + 60].replace("\n", " ").strip() + "…"
                        break
            except (KeyError, TypeError, AttributeError):
                continue
            if len(hits) >= 200:
                break
        return {"hits": hits}

    def mark_welcomed(self):
        self._cfg["welcomed"] = True
        cb.save_json(cb.CFG_PATH, self._cfg)

    # ---- library
    def add_text(self, title, source, text):
        if not (text or "").strip():
            return {"error": "Paste some text first."}
        c = cb.parse_text(text, (title or "Pasted chat").strip())
        c["source"] = (source or "").strip()[:40] or "Pasted text"
        with self._lock:
            self._lib.insert(0, c)
            self._save()
        return {"id": c["id"], "chats": self._chats()}

    def import_files(self):
        fd = getattr(webview, "FileDialog", None)
        mode = fd.OPEN if fd else webview.OPEN_DIALOG
        paths = self._window.create_file_dialog(mode, allow_multiple=True, file_types=(
            "Chat files (*.json;*.txt;*.md;*.markdown)", "All files (*.*)"))
        if not paths:
            return {"ids": [], "chats": self._chats()}
        ids, errors = [], []
        for p in paths:
            try:
                convs = cb.parse_file(p)
                with self._lock:
                    self._lib = convs + self._lib
                ids += [c["id"] for c in convs]
            except Exception as e:
                errors.append(f"{os.path.basename(p)}: {e}")
        self._save()
        return {"ids": ids, "errors": errors, "chats": self._chats()}

    def pick_project(self):
        fd = getattr(webview, "FileDialog", None)
        res = self._window.create_file_dialog(fd.FOLDER if fd else webview.FOLDER_DIALOG)
        if not res:
            return None
        root = res[0] if isinstance(res, (list, tuple)) else res
        files, skipped = cb.scan_project(root)
        if not files:
            return {"error": "No text or code files found in that folder."}
        self._proj = (root, files)
        on, running = set(), 0
        for i, f in enumerate(files):
            if running + f["size"] <= cb.BUDGET:
                on.add(i)
                running += f["size"]
        return {"root": root, "name": os.path.basename(root.rstrip("\\/")) or root, "budget": cb.BUDGET,
                "files": [{"i": i, "rel": f["rel"], "size": f["size"], "on": i in on, "type": f["type"]}
                          for i, f in enumerate(files)],
                "skipped": [{"rel": r, "why": w} for r, w in skipped]}

    def project_size(self, indices, mode):
        """Estimated tokens for the project as it would be sent, so the picker can show a live meter."""
        if not self._proj:
            return {"tokens": 0}
        root, files = self._proj
        chosen = [files[i] for i in self._valid_indices(indices, len(files))]
        text = cb.build_project_text(root, chosen, mode if mode in ("full", "outline", "tree") else "full")
        return {"tokens": cb.estimate_tokens(text), "chars": len(text)}

    @staticmethod
    def _valid_indices(indices, n):
        """The page sends file numbers; only accept whole numbers that exist, once each."""
        seen, out = set(), []
        for i in indices if isinstance(indices, list) else []:
            if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < n and i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def add_project(self, indices, mode="full"):
        if not self._proj:
            return {"error": "Tick at least one file."}
        root, files = self._proj
        chosen = [files[i] for i in self._valid_indices(indices, len(files))]
        if not chosen:
            return {"error": "Tick at least one file."}
        c = cb.project_conv(root, chosen, mode if mode in ("full", "outline", "tree") else "full")
        with self._lock:
            self._lib = [x for x in self._lib if not (x.get("kind") == "project" and x.get("path") == root)]  # re-adding refreshes it
            self._lib.insert(0, c)
            self._save()
        return {"id": c["id"], "chats": self._chats()}

    def rename_chat(self, cid, title):
        """Give a chat a name you'll recognise. A chat found on this PC is kept in the library once it has your name on it."""
        title = " ".join(str(title or "").split())[:120]
        if not title:
            return {"error": "Type a name first."}
        with self._lock:
            conv = next((c for c in self._lib if c["id"] == cid), None)
            if conv is None:
                found = next((c for c in self._found if c["id"] == cid), None)
                if found is None:
                    return {"error": "That chat isn't in the list any more."}
                conv = cb.clean_conv(found, trusted=True)
                conv["id"], conv["origin"] = found["id"], found.get("origin", "")   # same item, now saved (so it isn't listed twice)
                if not conv["origin"]:
                    conv.pop("origin")
                self._lib.insert(0, conv)
            conv["title"] = title
            self._save()
        return {"chats": self._chats()}

    # ---- sections: work with part of a long chat
    def sections(self, cid):
        """The chat as a notebook: numbered messages ("cells") grouped under section headings."""
        found = self._by_ids([cid])
        if not found or found[0].get("kind") == "project":
            return {"error": "Sections work for chats, not project folders."}
        conv = found[0]
        msgs = conv["messages"]
        return {"id": cid, "title": str(conv["title"]), "source": str(conv.get("source") or ""),
                "sections": cb.split_sections(msgs),
                "cells": [{"i": i, "role": m["role"], "text": m["content"][:1500], "more": len(m["content"]) > 1500}
                          for i, m in enumerate(msgs)]}

    MAX_PARTS = 12

    def make_part(self, cid, cells, titles=None, with_outline=True):
        """Turn the ticked messages into a new item (an excerpt) that can go anywhere, outline of the rest optional."""
        found = self._by_ids([cid])
        if not found or found[0].get("kind") == "project":
            return {"error": "That chat isn't in the list any more."}
        conv = found[0]
        msgs = conv["messages"]
        chosen = sorted(self._valid_indices(cells, len(msgs)))
        if not chosen:
            return {"error": "Tick at least one section or message first."}
        secs = cb.split_sections(msgs)
        if isinstance(titles, dict):                          # names the person gave the sections
            for k, v in titles.items():
                if str(k).isdigit() and int(k) < len(secs) and isinstance(v, str) and v.strip():
                    secs[int(k)]["title"] = " ".join(v.split())[:100]
        part = cb.clean_conv({"title": f"Part of: {conv['title']}"[:120], "source": str(conv.get("source") or "Chat")[:40],
                              "created": time.strftime("%Y-%m-%d %H:%M"), "excerpt": True,
                              "summary": cb.chat_outline(str(conv["title"]), msgs, secs, set(chosen)) if with_outline else "",
                              "messages": [msgs[i] for i in chosen]})
        with self._lock:
            self._lib.insert(0, part)
            kept = 0
            for c in list(self._lib):                       # keep the newest few parts so the list doesn't fill up with them
                if c.get("excerpt"):
                    kept += 1
                    if kept > self.MAX_PARTS:
                        self._lib.remove(c)
            self._save()
        return {"id": part["id"], "chats": self._chats()}

    def problem_report(self):
        """A short report the person can paste into a bug report. It holds no conversation text: counts, app names,
        settings switches, and the last log lines with keys, emails and the Windows user name hidden."""
        import platform
        lines = [f"ChatBridge {VERSION}", f"Windows: {platform.platform()}", f"Python: {platform.python_version()}",
                 f"Apps found: {', '.join(a['name'] for a in self._apps) or 'none'}",
                 f"Conversations: {len(self._chats())} (saved: {len(self._lib)})",
                 f"Settings: autopaste={self._cfg.get('autopaste', True)} theme={self._cfg.get('theme')} "
                 f"scrub={self._cfg.get('scrub', True)} compact={self._cfg.get('compact', False)}", "", "Recent log:"]
        try:
            with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
                tail = f.read().splitlines()[-30:]
        except OSError:
            tail = ["(no log yet)"]
        lines += [cb.scrub_text(x, secrets=True, personal=True)[0] for x in tail]
        text = "\n".join(lines)
        try:
            set_clipboard(text)
        except OSError:
            return {"error": "Couldn't copy to the clipboard."}
        return {"ok": True, "chars": len(text)}

    def delete_chats(self, ids):
        gone = {i for i in (ids if isinstance(ids, list) else []) if isinstance(i, str)}
        with self._lock:
            self._lib = [c for c in self._lib if c["id"] not in gone]
            self._save()
        return self._chats()

    def preview(self, cid):
        c = next((c for c in self._pool() if c["id"] == cid), None)
        if not c:
            return None
        return {"title": c["title"], "source": c.get("source"), "kind": c.get("kind", "chat"),
                "messages": [{"role": m["role"], "content": m["content"][:4000]} for m in c["messages"][:60]]}

    # ---- settings
    def save_settings(self, s):
        self._cfg.update({"autopaste": bool(s["autopaste"]), "theme": s["theme"], "font": s.get("font", "code"),
                          "ui_size": int(s["size"])})
        for k in ("about_me", "price_in", "price_out", "compact", "scrub", "last_target", "update_check", "group_by", "language"):
            if k in s:
                self._cfg[k] = s[k]
        cb.save_json(cb.CFG_PATH, self._cfg)
        return self._settings()

    def edit_profiles(self):
        if not os.path.exists(cb.PROFILES_PATH):
            cb.save_json(cb.PROFILES_PATH, cb.DEFAULT_PROFILES)
        desktop.open_path(cb.PROFILES_PATH)

    def add_app(self, name):
        name = (name or "").strip()
        if not name:
            return {"error": "Type the app's name."}
        import re
        cb.merge_catalog([{"label": name, "regex": re.escape(name)}])
        return {"ok": True}

    # ---- sending
    def _prepared(self, convs, opts):
        """Apply 'compact' and 'scrub' to copies of the chosen items. Returns (items, scrub counts, tokens saved)."""
        opts = opts or {}
        out, totals, saved = [], {"keys": 0, "emails": 0, "phones": 0, "paths": 0}, 0
        for c in convs:
            msgs = c["messages"]
            if opts.get("compact") and c.get("kind") != "project":  # never alter code in a project
                before = sum(cb.estimate_tokens(m["content"]) for m in msgs)
                msgs = cb.compact_messages(msgs, aggressive=opts.get("compact") == "max")
                saved += before - sum(cb.estimate_tokens(m["content"]) for m in msgs)
            if opts.get("scrub"):
                cleaned = []
                for m in msgs:
                    text, n = cb.scrub_text(m["content"], secrets=True, personal=c.get("kind") != "project")
                    for k, v in n.items():
                        totals[k] += v
                    cleaned.append({"role": m["role"], "content": text})
                msgs = cleaned
            out.append({**c, "messages": msgs})
        return out, totals, saved

    def _build(self, convs, opts=None):
        items, counts, saved = self._prepared(convs, opts)
        about = self._cfg.get("about_me", "")
        if len(items) > 1 or any(c.get("kind") == "project" for c in items):
            text = cb.build_handoff_many(items, 0, "", about)
        else:
            text = cb.build_handoff(items[0], 0, "full", "", about)
        return text, counts, saved

    def _handoff(self, convs):
        return self._build(convs, {})[0]

    def _target_info(self, target):
        """(app name, approximate context window in tokens) for a target key."""
        if isinstance(target, int) or (isinstance(target, str) and target.isdigit()):
            try:
                name = self._apps[int(target)]["name"]
                return name, cb.profile_for(name).get("window")
            except IndexError:
                pass
        if isinstance(target, str) and target.startswith("web:"):
            tool = self._web_tool(target)
            return (tool[0] if tool else None), None
        return ("the clipboard" if target == "copy" else None), None

    @staticmethod
    def _web_tool(key):
        if key == "web:none":     # "I'll open it myself": copy and save, but open nothing
            return ("a website", None, False)
        try:
            return WEB_TOOLS[int(str(key).split(":", 1)[1])]
        except (ValueError, IndexError):
            return None

    LONG_TOKENS = 120000      # with no known window, a conversation longer than this gets shortened

    def _resolve_opts(self, convs, target, opts):
        """{"auto": True} means: hide private details (unless turned off in Settings) and shorten long text only
        when it won't fit. Anything else is used as given. Returns (opts to use, whether shortening was needed)."""
        if not (opts or {}).get("auto"):
            return opts or {}, False
        scrub = self._cfg.get("scrub", True)
        shorten = bool(self._cfg.get("compact", False))
        needed = False
        if not shorten and any(c.get("kind") != "project" for c in convs):
            tokens = cb.estimate_tokens(self._build(convs, {"scrub": scrub})[0])
            window = self._target_info(target)[1]
            needed = tokens > (window * 0.85 if window else self.LONG_TOKENS)
        return {"scrub": scrub, "compact": shorten or needed}, needed

    def estimate(self, ids, target, opts):
        """Size of what would be sent: tokens, share of the target's window, savings, and cost if a price is set."""
        convs = self._by_ids(ids)
        if not convs:
            return {"tokens": 0}
        opts, auto_compact = self._resolve_opts(convs, target, opts)
        text, counts, saved = self._build(convs, opts)
        tokens = cb.estimate_tokens(text)
        name, window = self._target_info(target)
        price = self._cfg.get("price_in")
        try:
            cost = round(tokens / 1e6 * float(price), 4) if price not in (None, "") else None
        except ValueError:
            cost = None
        return {"tokens": tokens, "chars": len(text), "saved": saved, "scrubbed": counts, "window": window,
                "pct": round(tokens / window * 100, 1) if window else None, "cost": cost, "target": name,
                "auto_compact": auto_compact}

    def usage_summary(self, ids):
        """Real token usage recorded by Claude Code for the chosen chats, plus cost if the user entered prices."""
        tot = {"in": 0, "out": 0, "cache_read": 0, "cache_create": 0}
        for c in self._by_ids(ids):
            for k, v in (c.get("usage") or {}).items():
                tot[k] = tot.get(k, 0) + v
        try:
            pin, pout = float(self._cfg.get("price_in") or 0), float(self._cfg.get("price_out") or 0)
        except ValueError:
            pin = pout = 0
        cost = round((tot["in"] * pin + tot["out"] * pout) / 1e6, 4) if (pin or pout) else None
        return {**tot, "cost": cost}

    def send(self, ids, target, opts=None):
        convs = self._by_ids(ids)
        if not convs:
            return {"error": "Tick at least one chat first."}
        if target is None:
            return {"error": "Choose where to send it."}
        with self._lock:
            known = {c["id"] for c in self._lib}
            new = [c for c in convs if c["id"] not in known]
            if new:
                self._lib = new + self._lib
                self._save()
        auto = bool((opts or {}).get("auto"))
        into_open = bool((opts or {}).get("into_open"))       # paste into the chat that's already open, not a new one
        opts, _ = self._resolve_opts(convs, target, opts)
        text, counts, saved = self._build(convs, opts)
        title = convs[0]["title"] if len(convs) == 1 else f"{len(convs)} items"
        name, _ = self._target_info(target)
        self._cfg["last_target"] = name if target != "copy" else "copy"
        if opts and not auto:     # automatic choices are never saved as the person's own settings
            self._cfg["compact"], self._cfg["scrub"] = bool(opts.get("compact")), bool(opts.get("scrub"))
        cb.save_json(cb.CFG_PATH, self._cfg)
        cb.add_history({"id": uuid.uuid4().hex, "time": time.strftime("%Y-%m-%d %H:%M"), "target": name or "?",
                        "target_key": target, "titles": [c["title"] for c in convs], "ids": ids, "opts": opts or {},
                        "tokens": cb.estimate_tokens(text)})
        threading.Thread(target=self._deliver, args=(target, text, title, ids, into_open), daemon=True).start()
        return {"ok": True, "chats": self._chats(), "settings": self._settings()}

    def get_history(self):
        return cb.load_json(cb.HISTORY_PATH, [])

    def _deliver(self, target, text, title, ids, into_open=False):
        try:
            if target == "copy":
                set_clipboard(text)
                self._emit("done", "Copied. Paste it anywhere with Ctrl+V.")
            elif isinstance(target, str) and target.startswith("web:"):
                self._deliver_web(target, title, text)
            else:
                app = self._apps[int(target)]
                if app["kind"] == "Local server":
                    model = app["models"][0] if app["models"] else ""
                    # kept in memory only: choosing a local model must not overwrite the user's saved settings or key
                    self._chat = {"system": text, "label": app["name"], "models": app["models"],
                                  "cfg": {"provider": "OpenAI-compatible", "base_url": app["base_url"], "model": model, "api_key": ""}}
                    self._emit("chat", "", label=app["name"], models=app["models"], model=model)
                elif app["kind"] == "CLI tool":
                    set_clipboard(text)
                    desktop.open_terminal(app["name"])     # a name from cb.CLI_TOOLS, found with shutil.which
                    self._emit("done", f"{app['name']} opened in a terminal. Right-click there to paste." if desktop.WINDOWS
                               else f"{app['name']} opened in a terminal. Press Ctrl+Shift+V there to paste." if desktop.LINUX
                               else f"{app['name']} opened in a terminal. Press Ctrl+V there to paste.")
                else:
                    self._deliver_desktop(app, title, text, into_open=into_open)
        except Exception as e:
            self._emit("error", f"Something went wrong: {e}")

    def _deliver_web(self, target, title, text):
        """Websites: copy the chat, also keep it as a file (for sites that won't take a long paste), open the site."""
        tool = self._web_tool(target)
        if not tool:
            return self._emit("error", "That website isn't in the list.")
        name, url, _ = tool
        set_clipboard(text)
        path = cb.save_handoff_file(text, title)
        self._made_files.add(os.path.normcase(os.path.abspath(path)))
        if not url:
            return self._emit("done", "Copied, and saved as a file. Open any AI website and press Ctrl+V in its message box.", file=path)
        import webbrowser
        webbrowser.open(url)   # only ever an address from WEB_TOOLS above
        self._emit("done", f"Copied, and {name} is opening in your browser. Click its message box and press Ctrl+V. "
                           "If it says the text is too long, attach the saved file instead.", file=path)

    def show_file(self, path):
        """Show a file ChatBridge made, in Explorer. Only files we created ourselves."""
        p = os.path.normcase(os.path.abspath(str(path)))
        if p in self._made_files and os.path.isfile(p):
            desktop.reveal(p)
            return {"ok": True}
        return {"error": "That file isn't one ChatBridge made."}

    def export_selected(self, ids, opts=None):
        """Save the ticked chats/projects as a file you can attach to any AI website (.md or .txt), or as a ChatBridge .json."""
        convs = self._by_ids(ids if isinstance(ids, list) else [])
        if not convs:
            return {"error": "Pick a conversation first."}
        opts, _ = self._resolve_opts(convs, None, opts)
        fd = getattr(webview, "FileDialog", None)
        res = self._window.create_file_dialog(
            fd.SAVE if fd else webview.SAVE_DIALOG, save_filename="chat-handoff.md",
            file_types=("Markdown (*.md)", "Text (*.txt)", "ChatBridge chats (*.json)"))
        if not res:
            return {"cancelled": True}
        path = res if isinstance(res, str) else res[0]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.export_text(convs, path, opts))
        except OSError as e:
            return {"error": f"Couldn't save the file: {e}"}
        self._made_files.add(os.path.normcase(os.path.abspath(path)))
        return {"ok": True, "path": path, "name": os.path.basename(path)}

    def export_text(self, convs, path, opts=None):
        if path.lower().endswith(".json"):
            items, _, _ = self._prepared(convs, opts)
            keep = ("title", "source", "created", "summary", "messages", "kind", "mode", "excerpt")
            return json.dumps({"format": "chatbridge", "conversations": [{k: c[k] for k in keep if k in c} for c in items]},
                              ensure_ascii=False, indent=1)
        return self._build(convs, opts)[0]

    def _deliver_desktop(self, app, title, text, force_full=False, test_marker=None, into_open=False):
        prof = cb.profile_for(app["name"])
        keys = cb.parse_keys(prof["new_chat"]) if prof["new_chat"] and not into_open else None   # no "new chat" when adding to the open one
        force_full = force_full or into_open
        exe = folder = None
        if prof["paste"] == "file" and not force_full:
            path = cb.save_handoff_file(text, title)
            folder = os.path.dirname(path)
            set_clipboard(f'Read the file "{path}". It is earlier work I did with another AI assistant. Treat it as our '
                          f"prior context, tell me in a sentence where we left off, then continue from there.")
            exe = cb.find_exe(app["name"])
        else:
            set_clipboard(test_marker or text)
        warm = window_open(prof["title"])      # looked at before launching: was the app already open?
        if callable(app.get("launch_fn")):
            app["launch_fn"]()
        elif exe:
            desktop.open_app(exe, folder)
        elif app.get("launch"):
            desktop.open_app(app["launch"])
        else:
            raise OSError("No launch target found for this app.")
        if not self._cfg.get("autopaste", True) or not desktop.can_press_keys():   # (Linux Wayland: the person pastes)
            self._emit("done", f"{app['name']} is open. Click its message box and press Ctrl+V.")
            return False
        self._emit("working", f"Opening {app['name']}... don't click elsewhere.")
        front = lambda: prof["title"] in foreground_title()
        for _ in range(50):  # up to ~25 seconds for the window to come forward
            if front():
                break
            time.sleep(0.5)
        else:
            self._emit("warn", f"{app['name']} didn't come to the front. Click its message box and press Ctrl+V.")
            return False
        if not warm:
            self._emit("working", f"{app['name']} is starting up... this takes a few seconds the first time.")
        time.sleep(self._paste_delay if warm else self._cold_delay)  # let the app finish loading
        if not front():
            # a freshly started app often flashes a splash screen or loses focus once; give it a moment to come back
            for _ in range(4 if warm else 30):
                time.sleep(0.5)
                if front():
                    time.sleep(1.5 if not warm else 0.5)
                    break
            else:
                self._emit("warn", f"{app['name']} isn't in front any more. Click its message box and press Ctrl+V.")
                return False
        try:
            if keys:
                desktop.press_spec(prof["new_chat"])   # checked by cb.parse_keys above, which refuses Enter
                time.sleep(1.2)
                if not front():
                    self._emit("warn", f"{app['name']} isn't in front any more. Click its message box and press Ctrl+V.")
                    return False
            desktop.paste()  # Ctrl+V (Cmd+V on macOS). ChatBridge never presses Enter.
        except desktop.NeedsPermission:
            self._emit("warn", "To paste for you on a Mac, ChatBridge needs permission: System Settings → Privacy & Security "
                               "→ Accessibility → turn on ChatBridge. For now, click the message box and press Ctrl+V.")
            return False
        self._emit("done", f"Pasted into {app['name']}. Check it, then press Enter there to send.", pasted=True)
        return True

    def test_app(self, target):
        try:
            app = self._apps[int(target)]
        except (TypeError, ValueError, IndexError):
            return {"error": "Pick a desktop app first."}
        if app["kind"] not in ("Desktop app", "Possible AI app"):
            return {"error": "Testing works for desktop apps."}
        marker = f"ChatBridge test {int(time.time()) % 10000}"

        def run():
            try:
                ok = self._deliver_desktop(app, "test", marker, force_full=True, test_marker=marker)
                self._emit("test", "", name=app["name"], marker=marker, pasted=bool(ok))
            except Exception as e:
                self._emit("error", f"Something went wrong: {e}")
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True}

    def record_compat(self, name, ok):
        self._cfg.setdefault("compat", {})[name] = {"ok": bool(ok), "date": time.strftime("%Y-%m-%d")}
        cb.save_json(cb.CFG_PATH, self._cfg)
        return self._apps_out()

    # ---- chatting with a local or API model inside the app
    def chat(self, history, model=None):
        if not self._chat:
            return {"error": "Nothing to continue yet."}
        cfg = {**self._cfg, **self._chat.get("cfg", {})}
        if model:
            cfg["model"] = model
        try:
            return {"reply": cb.call_model(cfg, self._chat["system"], history)}
        except Exception as e:
            return {"error": str(e)}


def main():
    # A windowed (no console) build has no stdout/stderr; some libraries crash if they try to print.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))
    os.makedirs(cb.APP_DIR, exist_ok=True)
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("ChatBridge %s starting", VERSION)
    try:
        api = Api()
        logging.info("Browser capture listening on port %s", api.start_capture_server())
        index = os.path.join(HERE, "ui", "index.html")
        if not os.path.isfile(index):
            raise FileNotFoundError(f"Missing screen files: {index}")
        window = webview.create_window(f"ChatBridge", index, js_api=api, width=1240, height=820, min_size=(960, 640),
                                       background_color="#f6f7f9")
        api._window = window
        if not desktop.WINDOWS:
            webview_patch.apply()      # pywebview's bridge without eval, so the strict CSP stays (see webview_patch.py)
        webview.start()
    except Exception:
        logging.exception("ChatBridge crashed on startup")
        desktop.show_error("ChatBridge", f"ChatBridge couldn't start.\n\nDetails were saved to:\n{LOG_PATH}\n\n{desktop.START_HINT}".strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
