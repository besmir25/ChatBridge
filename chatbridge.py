"""ChatBridge - save AI chats and hand them to another model or app.

Import a chat (ChatGPT / Claude exports, pasted text, markdown, JSON), keep it in a
local library, then either copy a "pick up where we left off" handoff prompt or
continue the conversation live with another model through its API.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    import winreg
except ImportError:  # not on Windows
    winreg = None

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChatBridge")
LIB_PATH = os.path.join(APP_DIR, "library.json")
CFG_PATH = os.path.join(APP_DIR, "config.json")

PROVIDERS = {
    "Anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-5-5"},
    "OpenAI-compatible": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
}
DEFAULT_CFG = {"provider": "Anthropic", "base_url": PROVIDERS["Anthropic"]["base_url"],
               "model": PROVIDERS["Anthropic"]["model"], "api_key": "", "ui_size": 16}

# Midnight theme
BG, PANEL, PANEL2, LINE = "#14161a", "#1d2026", "#262a31", "#3a404a"
FG, MUTED = "#f1f3f5", "#aab2bd"
ACCENT, ACC_FG, SEL = "#2dd4bf", "#06201d", "#0f5c57"
USER_CLR = "#93c5fd"

# ---------------------------------------------------------------- AI app scanner
KNOWN_APPS = [
    ("Claude", r"^claude"), ("ChatGPT", r"chatgpt"), ("Codex", r"^codex"), ("Gemini", r"^gemini"),
    ("Microsoft Copilot", r"copilot"), ("Perplexity", r"perplexity"), ("Grok", r"^grok"),
    ("Ollama", r"^ollama"), ("LM Studio", r"lm ?studio"), ("Jan", r"^jan$"), ("GPT4All", r"gpt4all"),
    ("Msty", r"^msty"), ("AnythingLLM", r"anythingllm"), ("Open WebUI", r"open ?webui"),
    ("Cursor", r"^cursor"), ("Windsurf", r"^windsurf"), ("Poe", r"^poe$"), ("Pieces", r"^pieces"),
    ("Raycast", r"^raycast"), ("Cherry Studio", r"cherry ?studio"), ("Chatbox", r"^chatbox"),
    ("Antigravity", r"antigravity"), ("Kiro", r"^kiro"), ("Trae", r"^trae"), ("Zed", r"^zed$"),
    ("DeepSeek", r"deepseek"), ("Mistral Le Chat", r"le chat|mistral"), ("Kimi", r"^kimi"),
    ("Text Generation WebUI", r"text.?generation.?webui|oobabooga"), ("Enchanted", r"^enchanted"),
]
CLI_TOOLS = ("ollama", "claude", "codex", "gemini", "aider", "llm", "opencode", "goose", "antigravity", "agy")
GENERIC_AI = re.compile(r"\b(ai|a\.i\.|gpt|llm|llama|copilot|chatbot|assistant|agent)\b", re.I)
CATALOG_PATH = os.path.join(APP_DIR, "catalog.json")


def load_catalog():
    """Built-in list plus the user's own additions/updates from catalog.json."""
    extra = load_json(CATALOG_PATH, [])
    seen = {l for l, _ in KNOWN_APPS}
    out = list(KNOWN_APPS)
    for e in extra:
        if isinstance(e, dict) and e.get("label") and e.get("regex") and e["label"] not in seen:
            try:
                re.compile(e["regex"])
            except re.error:
                continue
            out.append((e["label"], e["regex"]))
            seen.add(e["label"])
    return out


def merge_catalog(entries):
    """Add new {label, regex} entries to catalog.json; returns how many were new."""
    have = {l for l, _ in load_catalog()}
    cur = load_json(CATALOG_PATH, [])
    n = 0
    for e in entries:
        if isinstance(e, dict) and e.get("label") and e.get("regex") and e["label"] not in have:
            try:
                re.compile(e["regex"])
            except re.error:
                continue
            cur.append({"label": str(e["label"]), "regex": str(e["regex"])})
            have.add(e["label"])
            n += 1
    if n:
        save_json(CATALOG_PATH, cur)
    return n


def fetch_catalog(url):
    """Download a JSON list of {label, regex} (or {'apps': [...]}) and merge it."""
    if not url.lower().startswith("https://"):
        raise ValueError("Catalog URL must start with https://")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ChatBridge"}), timeout=20) as r:
        data = json.loads(r.read(2_000_000).decode("utf-8"))
    return merge_catalog(data.get("apps", []) if isinstance(data, dict) else data)
LOCAL_SERVERS = [("Ollama", 11434, "/api/tags", "ollama"), ("LM Studio", 1234, "/v1/models", "openai"),
                 ("Jan", 1337, "/v1/models", "openai"), ("GPT4All", 4891, "/v1/models", "openai"),
                 ("llama.cpp / other", 8080, "/v1/models", "openai")]


CLIP_ONLY = "Clipboard only (paste anywhere)"

# ---------------------------------------------------------------- app profiles
# One entry per app, no code needed to add more. Edit %APPDATA%\ChatBridge\profiles.json (yours win over these).
#   match    regex on the app's name          title    text its window title contains (default: first word of name)
#   new_chat keys that start a new chat box   paste    "full" = paste the whole handoff, "file" = save a file + short note
PROFILES_PATH = os.path.join(APP_DIR, "profiles.json")
DEFAULT_PROFILES = [
    {"match": "antigravity", "title": "antigravity", "new_chat": "ctrl+shift+l", "paste": "full",
     "note": "Ctrl+Shift+L starts a new conversation (verified)."},
    {"match": "copilot", "title": "copilot", "new_chat": "", "paste": "full",
     "note": "Long pastes become a text attachment (verified)."},
    {"match": "^claude", "title": "claude", "new_chat": "", "paste": "full", "window": 200000,
     "note": "Window size is approximate and depends on your plan."},
    {"match": "chatgpt", "title": "chatgpt", "new_chat": "", "paste": "full", "window": 128000,
     "note": "Window size is approximate and depends on your plan."},
    {"match": "cursor|windsurf|kiro|trae|^zed", "title": "", "new_chat": "", "paste": "file",
     "note": "Code editors: hand over a file and ask the agent to read it."},
]
_KEYS = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "tab": 0x09, "esc": 0x1B, "space": 0x20}


def load_profiles():
    user = load_json(PROFILES_PATH, [])
    return [p for p in user if isinstance(p, dict) and p.get("match")] + DEFAULT_PROFILES


def _window_title_key(title, name):
    """The text a window title must contain before we press any key in it. Very short words (like "ai") match far too many
    windows, so fall back to the app's full name."""
    t = (title or name.split()[0]).lower()
    return t if len(t) >= 4 else name.lower()


def profile_for(name):
    for p in load_profiles():
        try:
            if re.search(p["match"], name, re.I):
                return {"new_chat": "", "paste": "full", "note": "", **p, "title": _window_title_key(p.get("title"), name)}
        except re.error:
            continue
    return {"match": "", "new_chat": "", "paste": "full", "note": "", "title": _window_title_key("", name)}


def parse_keys(spec):
    """'ctrl+shift+l' -> [0x11, 0x10, 0x4C]. Enter/Return are refused: ChatBridge never sends for you."""
    out = []
    parts = [s.strip().lower() for s in spec.split("+") if s.strip()]
    if "ctrl" in parts and any(p in ("m", "j") for p in parts):   # Ctrl+M / Ctrl+J are Enter in disguise (CR / LF)
        raise ValueError("Ctrl+M and Ctrl+J act like Enter. ChatBridge never presses Enter.")
    for part in parts:
        if part in ("enter", "return", "numpadenter"):
            raise ValueError("ChatBridge never presses Enter - you send the message yourself.")
        if part in _KEYS:
            out.append(_KEYS[part])
        elif len(part) == 1 and part.isalnum():
            out.append(ord(part.upper()))
        elif re.fullmatch(r"f([1-9]|1[0-2])", part):
            out.append(0x70 + int(part[1:]) - 1)
        else:
            raise ValueError(f"Unknown key '{part}'")
    return out


# ---------------------------------------------------------------- project folders
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", ".idea", ".vscode",
             "target", ".next", ".cache", "site-packages", ".pytest_cache", ".mypy_cache"}
SECRET_NAME = re.compile(
    r"(^\.env($|\.)|\.pem$|\.key$|\.pfx$|\.p12$|\.jks$|\.keystore$|\.ppk$|\.kdbx$|\.tfvars$|\.tfstate(\.backup)?$"
    r"|^\.(npmrc|pypirc|netrc|git-credentials|dockercfg|htpasswd|pgpass)$|^id_(rsa|dsa|ecdsa|ed25519)"
    r"|credentials|secrets?[._-]|[._-]secrets?\.|secret_key|private[._-]key|service[._-]account.*\.json$)", re.I)
SECRET_DIRS = {".ssh", ".aws", ".gnupg", ".kube", ".azure", ".gcloud", "secrets", ".secrets"}   # nothing inside these is ever included
SECRET_TEXT = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|sk_(?:live|test)_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|npm_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"                       # JWTs
    r"|[a-z][a-z0-9+.-]{1,20}://[^\s:/@'\"]{1,64}:[^\s@/'\"]{3,128}@"                        # user:password@host in URLs
    r"|AccountKey=[A-Za-z0-9+/=]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
MAX_FILE, BUDGET = 100_000, 120_000  # characters per file / suggested total (~30k tokens)


def _inside(root_real, path_real):
    try:
        return os.path.commonpath([os.path.normcase(root_real), os.path.normcase(path_real)]) == os.path.normcase(root_real)
    except ValueError:   # different drives
        return False


def _git(root, *args):
    """Run git in a folder the user picked. That folder may be a downloaded repo, and git reads its config, so switch off the
    settings that can run programs (fsmonitor, hooks) and ask git not to take locks or follow protocols."""
    safe = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + ("NUL" if os.name == "nt" else "/dev/null"),
            "-c", "protocol.allow=never", "--no-optional-locks"]
    try:
        r = subprocess.run(["git", *safe, "-C", root, *args], capture_output=True, timeout=20,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def scan_project(root, limit=3000):
    """Return (files, skipped). files: [{rel, size, text}] safe to share; skipped: [(rel, reason)]."""
    listed = _git(root, "ls-files", "-z", "-co", "--exclude-standard")   # -z: exact names, even with non-English letters
    if listed and listed.strip("\0"):
        rels = [r for r in listed.split("\0") if r]
    else:
        rels = []
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and x.lower() not in SECRET_DIRS]
            rels += [os.path.relpath(os.path.join(d, n), root) for n in names]
    files, skipped = [], []
    real_root = os.path.realpath(root)
    for rel in sorted(rels)[:limit]:
        rel = rel.replace("\\", "/")
        parts = rel.split("/")
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        path = os.path.join(root, rel)
        if any(part.lower() in SECRET_DIRS for part in parts[:-1]):
            skipped.append((rel, "inside a folder that holds secrets"))
            continue
        if SECRET_NAME.search(os.path.basename(rel)):
            skipped.append((rel, "looks like a secret file"))
            continue
        if not _inside(real_root, os.path.realpath(path)):   # a link could point at a file outside the folder you picked
            skipped.append((rel, "a link to a file outside this folder"))
            continue
        try:
            size = os.path.getsize(path)
            if size > MAX_FILE:
                skipped.append((rel, "too large"))
                continue
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            continue
        if b"\0" in data[:8000]:
            continue  # binary: silently ignored
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        if SECRET_TEXT.search(text):
            skipped.append((rel, "contains something that looks like a key or password"))
            continue
        files.append({"rel": rel, "size": len(text), "text": text, "type": file_type(rel)})

    def rank(f):
        base = f["rel"].lower()
        return (0 if base.startswith("readme") else 1 if "/" not in base and base.endswith(".md") else 2, base)
    files.sort(key=rank)
    return files, skipped


_CONFIG_EXT = {".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".xml", ".tf", ".gradle", ".properties", ".conf", ".lock"}
_CONFIG_NAMES = {"dockerfile", "makefile", "procfile", "requirements.txt", "package.json", ".gitignore", ".dockerignore"}
_DOC_EXT = {".md", ".rst", ".txt", ".adoc"}


def file_type(rel):
    """code / config / docs / tests - used for the quick filters in the project picker."""
    low = rel.lower()
    base, ext = os.path.basename(low), os.path.splitext(low)[1]
    if re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)test_|_test\.|\.test\.|\.spec\.", low):
        return "tests"
    if ext in _DOC_EXT:
        return "docs"
    if ext in _CONFIG_EXT or base in _CONFIG_NAMES or base.startswith(("dockerfile", ".env.")):
        return "config"
    return "code"


def outline_text(rel, text):
    """A short skeleton of a big file: definitions, headings, or top-level keys, instead of every line."""
    ext, lines = os.path.splitext(rel.lower())[1], text.splitlines()
    pats = {".py": r"^\s*(class|def|async def)\s+\w+",
            ".md": r"^#{1,4}\s+\S", ".rst": r"^\S.*\n?", ".adoc": r"^=+\s+\S",
            ".yml": r"^\S", ".yaml": r"^\S", ".toml": r"^\S", ".ini": r"^\S", ".cfg": r"^\S"}
    for e in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".java", ".cs", ".go", ".rs", ".kt", ".swift", ".php", ".rb"):
        pats[e] = r"^\s*(export\s+)?(default\s+)?(public\s+|private\s+|static\s+|pub\s+)?(async\s+)?(function|func|fn|def|class|interface|struct|enum|type|const|let|impl)\b"
    if ext == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return "\n".join(f"{k}: {type(v).__name__}" + (f" ({len(v)})" if hasattr(v, "__len__") and not isinstance(v, str) else "")
                                 for k in list(data)[:80] for v in [data[k]])
        except ValueError:
            pass
    pat = re.compile(pats[ext]) if ext in pats else None
    picked = [ln.rstrip()[:160] for ln in lines if pat and pat.match(ln)]
    return "\n".join((picked or [ln[:160] for ln in lines[:20]])[:150])


def _tree_lines(rels):
    root = {}
    for r in rels:
        d = root
        *folders, leaf = r.split("/")
        for p in folders:
            d = d.setdefault(p + "/", {})
        d[leaf] = None
    out = []

    def walk(d, depth):
        for k in sorted(d, key=lambda k: (d[k] is None, k.lower())):
            out.append("  " * depth + k)
            if d[k] is not None:
                walk(d[k], depth + 1)
    walk(root, 0)
    return out


OUTLINE_OVER = 6000  # characters: bigger files are shown as an outline in "outline" mode


def build_project_text(root, files, mode="full"):
    """mode: 'full' (every selected file), 'outline' (big files become skeletons), 'tree' (structure + README only)."""
    name = os.path.basename(root.rstrip("\\/")) or root
    out = [f"Project: {name}", f"Files included: {len(files)}   Mode: {mode}"]   # no full path: it usually contains the Windows user name
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        out += ["", "Git branch: " + branch.strip()]
        log = _git(root, "log", "-5", "--oneline")
        if log:
            out += ["Recent commits:", log.strip()]
        status = _git(root, "status", "--short")
        if status and status.strip():
            out += ["Uncommitted changes:", status.strip()[:2000]]
    out += ["", "Folder structure:"] + _tree_lines([f["rel"] for f in files]) + [""]
    lang = {".py": "python", ".js": "javascript", ".ts": "typescript", ".json": "json", ".md": "markdown",
            ".html": "html", ".css": "css", ".yml": "yaml", ".yaml": "yaml", ".sh": "bash", ".ps1": "powershell",
            ".toml": "toml", ".xml": "xml", ".sql": "sql", ".tf": "hcl"}
    for f in files:
        text, note = f["text"], ""
        if mode == "tree":
            if not f["rel"].lower().startswith("readme"):
                continue
            text, note = text[:4000], " (start of file)"
        elif mode == "outline" and f["size"] > OUTLINE_OVER:
            text, note = outline_text(f["rel"], text), f" (outline - the full file is {f['size']:,} characters)"
        fence = "````" if "```" in text else "```"
        out += [f"### {f['rel']}{note}", fence + lang.get(os.path.splitext(f["rel"])[1].lower(), ""),
                text.rstrip("\n"), fence, ""]
    return "\n".join(out)


def project_conv(root, files, mode="full"):
    name = os.path.basename(root.rstrip("\\/")) or root
    c = new_conv("Project: " + name, "Project folder",
                 [{"role": "user", "content": build_project_text(root, files, mode)}])
    c["kind"], c["path"], c["mode"] = "project", root, mode
    return c


# ---------------------------------------------------------------- size, compacting, privacy
_TOKEN_PIECE = re.compile(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+")   # the look-behind + caps keep this linear on long text
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_USER_PATH = re.compile(r"(?i)(C:(?:\\{1,4}|/)Users(?:\\{1,4}|/))[^\\/\s\"'<>|]+")   # C:\Users\x, C:\\Users\\x (JSON) and C:/Users/x
_KEY_ASSIGN = re.compile(r"(?i)([\w.-]{0,40}(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth)[\w.-]{0,40})(\s*[:=]\s*)"
                         r"(?:\"[^\"\n]{4,200}\"|'[^'\n]{4,200}'|[^\s\"']{8,})")   # quoted values may contain spaces


def estimate_tokens(text):
    """A rough token count (usually within ~15%). Exact counts need each vendor's own tokenizer."""
    n = 0
    for m in _TOKEN_PIECE.finditer(text or ""):
        t = m.group(0)
        n += (len(t) + 5) // 6 if t[0].isalpha() else (len(t) + 2) // 3 if t[0].isdigit() else 1
    return n


def compact_text(text, max_block=60, max_message=200):
    """Trim noise that costs tokens but rarely matters: ANSI codes, blank runs, and very long code/output blocks."""
    text = _ANSI.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    def squeeze(lines, cap):
        if len(lines) <= cap:
            return lines
        head, tail = int(cap * .65), int(cap * .25)
        return lines[:head] + [f"[... {len(lines) - head - tail} lines omitted ...]"] + lines[-tail:]

    def fenced(m):
        body = m.group(2).split("\n")
        return m.group(1) + "\n".join(squeeze(body, max_block)) + m.group(3)
    text = re.sub(r"(```[^\n]*\n)(.*?)(\n```)", fenced, text, flags=re.S)
    return "\n".join(squeeze(text.split("\n"), max_message))


def compact_messages(msgs, aggressive=False):
    out, prev = [], None
    for m in msgs:
        c = compact_text(m["content"], 30 if aggressive else 60, 120 if aggressive else 200)
        if aggressive and len(c) > 2500:
            c = c[:1700] + f"\n[... {len(c) - 2200:,} characters omitted ...]\n" + c[-500:]
        if prev and prev["role"] == m["role"] and prev["content"] == c:
            continue  # exact repeat
        prev = {"role": m["role"], "content": c}
        out.append(prev)
    return out


def scrub_text(text, secrets=True, personal=True):
    """Remove API keys/passwords and (optionally) emails, phone numbers and the Windows user name in file paths."""
    counts = {"keys": 0, "emails": 0, "phones": 0, "paths": 0}

    def sub(rx, repl, key, s):
        s, n = rx.subn(repl, s)
        counts[key] += n
        return s
    if secrets:
        text = sub(SECRET_TEXT, "[key removed]", "keys", text)
        text = sub(_KEY_ASSIGN, lambda m: f"{m.group(1)}{m.group(2)}[removed]", "keys", text)
    if personal:
        text = sub(_EMAIL, "[email]", "emails", text)
        text = sub(_PHONE, "[phone]", "phones", text)
        text = sub(_USER_PATH, lambda m: m.group(1) + "<user>", "paths", text)
    return text, counts


HISTORY_PATH = os.path.join(APP_DIR, "history.json")


def add_history(entry, keep=100):
    h = load_json(HISTORY_PATH, [])
    h.insert(0, entry)
    save_json(HISTORY_PATH, h[:keep])


def find_exe(name):
    """Locate an installed app's main .exe, e.g. %LOCALAPPDATA%\\Programs\\Antigravity\\Antigravity.exe."""
    from glob import glob
    first = name.split()[0].lower()
    for root in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
                 os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        for d in glob(os.path.join(root, first + "*")):
            exe = os.path.join(d, first + ".exe")
            if os.path.isfile(exe):
                return exe
    return shutil.which(first)


HANDOFF_DIR = os.path.join(os.path.expanduser("~"), "ChatBridge", "handoffs")


def prune_handoffs(days=7, folder=None):
    """These files hold full chat text, so don't let them pile up: delete the ones older than a week."""
    folder = folder or HANDOFF_DIR
    cutoff = time.time() - days * 86400
    try:
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            if name.endswith(".md") and os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except OSError:
        pass


def save_handoff_file(text, title):
    folder = HANDOFF_DIR
    os.makedirs(folder, exist_ok=True)
    prune_handoffs(folder=folder)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "-", title)[:50].strip("-") or "chat"
    path = os.path.join(folder, f"{time.strftime('%Y%m%d-%H%M%S')}-{safe}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return path


def app_label(a):
    return f"{a['name']}  -  {a['kind']}"


def scan_apps():
    """Return a list of dicts: name, kind, info, launch, base_url, models."""
    found = {}
    catalog = load_catalog()

    def add(name, kind, info="", launch=None):
        for label, rx in catalog:
            if re.search(rx, name, re.I):
                found.setdefault((label, kind), {"name": name, "kind": kind, "info": info,
                                                 "launch": launch, "base_url": None, "models": []})
                return
        if kind == "Desktop app" and GENERIC_AI.search(name):
            found.setdefault((name, "Possible AI app"), {"name": name, "kind": "Possible AI app", "info": info,
                                                         "launch": launch, "base_url": None, "models": []})

    try:  # Start menu entries cover classic and Microsoft Store apps
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=45, creationflags=0x08000000).stdout
        apps = json.loads(out) if out.strip() else []
        for a in [apps] if isinstance(apps, dict) else apps:
            add(a["Name"], "Desktop app", "Start menu", "shell:AppsFolder\\" + a["AppID"])
    except Exception:
        pass
    if winreg:  # installed-programs list (catches apps with no Start menu entry)
        for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                           (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
            try:
                with winreg.OpenKey(hive, sub) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        try:
                            with winreg.OpenKey(k, winreg.EnumKey(k, i)) as s:
                                name = winreg.QueryValueEx(s, "DisplayName")[0]
                                try:
                                    loc = winreg.QueryValueEx(s, "InstallLocation")[0]
                                except OSError:
                                    loc = ""
                            add(name, "Desktop app", loc or "Installed program", loc if loc and os.path.isdir(loc) else None)
                        except OSError:
                            continue
            except OSError:
                continue
    for exe in CLI_TOOLS:
        p = shutil.which(exe)
        if p:
            found[(exe, "CLI tool")] = {"name": exe, "kind": "CLI tool", "info": p, "launch": None,
                                        "base_url": None, "models": []}
    for name, port, path, style in LOCAL_SERVERS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1.2) as r:
                data = json.loads(r.read().decode("utf-8"))
            models = [m.get("name") or m.get("id") for m in (data.get("models") if style == "ollama" else data.get("data")) or []]
            found[(name, "Local server")] = {
                "name": name, "kind": "Local server", "launch": None, "models": [m for m in models if m],
                "info": f"Running on port {port} - {len(models)} model(s)", "base_url": f"http://127.0.0.1:{port}/v1"}
        except Exception:
            continue
    return sorted(found.values(), key=lambda a: (a["kind"], a["name"].lower()))


# ---------------------------------------------------------------- storage
_SAVE_LOCK = threading.RLock()


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return default
    except ValueError:
        # A damaged file must not be silently replaced by an empty one on the next save: set it aside so it can be recovered.
        try:
            if os.path.getsize(path) > 2:
                os.replace(path, f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        except OSError:
            pass
        return default


def save_json(path, data):
    """Write atomically, from any thread: a unique temp file per call, one lock, and a .bak of the previous version."""
    with _SAVE_LOCK:
        os.makedirs(os.path.dirname(path) or APP_DIR, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            try:
                shutil.copyfile(path, path + ".bak")
            except OSError:
                pass
        os.replace(tmp, path)


# ---------------------------------------------------------------- parsing
def new_conv(title, source, messages, created=None):
    return {"id": uuid.uuid4().hex, "title": (title or "Untitled").strip()[:120] or "Untitled",
            "source": source, "created": created or time.strftime("%Y-%m-%d %H:%M"),
            "summary": "", "messages": messages}


def _flat(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(t for t in (_flat(x) for x in c) if t)
    if isinstance(c, dict):
        if isinstance(c.get("text"), str):
            return c["text"]
        for k in ("parts", "content"):
            if k in c:
                return _flat(c[k])
    return ""


def _ts(t):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(t)))
    except (TypeError, ValueError, OSError):
        return None


def _norm_role(r):
    r = str(r).lower()
    if r in ("user", "human", "you", "me"):
        return "user"
    if r == "system":
        return "system"
    return "assistant"


def parse_chatgpt(item):
    mapping = item.get("mapping", {})
    chain, node = [], item.get("current_node")
    if node and node in mapping:
        while node:
            chain.append(mapping[node])
            node = mapping[node].get("parent")
        chain.reverse()
    else:
        chain = sorted((n for n in mapping.values() if n.get("message")),
                       key=lambda n: n["message"].get("create_time") or 0)
    msgs = []
    for n in chain:
        m = n.get("message")
        if not m:
            continue
        role = (m.get("author") or {}).get("role")
        if role not in ("user", "assistant"):
            continue
        text = _flat(m.get("content")).strip()
        if text:
            msgs.append({"role": role, "content": text})
    return new_conv(item.get("title"), "ChatGPT", msgs, _ts(item.get("create_time")))


def parse_claude(item):
    msgs = []
    for m in item.get("chat_messages", []):
        text = (m.get("text") or _flat(m.get("content"))).strip()
        if text:
            msgs.append({"role": _norm_role(m.get("sender", "assistant")), "content": text})
    return new_conv(item.get("name"), "Claude", msgs, (item.get("created_at") or "")[:16].replace("T", " ") or None)


def parse_generic(item, source="Imported"):
    msgs = []
    for m in item.get("messages", []):
        text = _flat(m.get("content", m.get("text", ""))).strip()
        if text:
            msgs.append({"role": _norm_role(m.get("role", "assistant")), "content": text})
    return new_conv(item.get("title") or item.get("name"), item.get("source") or source, msgs)


def _s(v, limit):
    return v[:limit] if isinstance(v, str) else ""


def clean_conv(d, trusted=False):
    """Keep only the fields we understand, with the right types and sizes. Returns None if there's nothing usable.

    Imported files are untrusted: they could carry markup meant for the page, wrong types that crash the app, or an
    'origin' that hides real chats. trusted=True (our own library file) additionally keeps id/origin/path.
    """
    if not isinstance(d, dict) or not isinstance(d.get("messages"), list):
        return None
    msgs = []
    for m in d["messages"][:5000]:
        if isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].strip():
            msgs.append({"role": _norm_role(m.get("role", "assistant")), "content": m["content"][:200_000]})
    if not msgs:
        return None
    c = {"id": uuid.uuid4().hex, "title": _s(d.get("title"), 120).strip() or "Untitled",
         "source": _s(d.get("source"), 40).strip() or "Imported", "created": _s(d.get("created"), 32),
         "summary": _s(d.get("summary"), 20_000), "messages": msgs}
    if d.get("kind") == "project":
        c["kind"] = "project"
        c["mode"] = d.get("mode") if d.get("mode") in ("full", "outline", "tree") else "full"
    if isinstance(d.get("usage"), dict):
        c["usage"] = {k: int(v) for k, v in d["usage"].items() if k in ("in", "out", "cache_read", "cache_create") and isinstance(v, int)}
    if trusted:
        for k in ("id", "origin", "path"):
            if isinstance(d.get(k), str) and d[k]:
                c[k] = d[k][:500]
    return c


def parse_json(data):
    if isinstance(data, dict) and data.get("format") == "chatbridge":
        convs = data.get("conversations")
        return [c for c in (clean_conv(x) for x in (convs if isinstance(convs, list) else [])) if c]
    items = data if isinstance(data, list) else [data]
    if items and isinstance(items[0], dict) and "role" in items[0] and "mapping" not in items[0]:
        items = [{"messages": items}]  # bare OpenAI-style messages array
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if "mapping" in it:
            out.append(parse_chatgpt(it))
        elif "chat_messages" in it:
            out.append(parse_claude(it))
        elif "messages" in it:
            out.append(parse_generic(it))
    return [c for c in (clean_conv(x) for x in out) if c]   # every import path ends here, so nothing unchecked gets saved


_LABEL = (r"you said|chatgpt said|claude said|gemini said|copilot said|user|you|human|me|assistant|"
          r"claude|chatgpt|gpt-?\d*|ai|gemini|copilot|model|system|bot")
_RE_COLON = re.compile(rf"^\s*(?:#{{1,6}}\s*)?\**({_LABEL})\**\s*:\s*\**\s*(.*)$", re.I)
_RE_SAID = re.compile(rf"^\s*(?:#{{1,6}}\s*)?\**((?:you|chatgpt|claude|gemini|copilot) said)\**\s*:?\s*(.*)$", re.I)
_RE_ALONE = re.compile(rf"^\s*(?:#{{1,6}}\s*)?\**({_LABEL})\**\s*$", re.I)


def parse_text(text, title="Pasted chat"):
    msgs, role, buf = [], None, []

    def flush():
        body = "\n".join(buf).strip()
        if role and body:
            msgs.append({"role": role, "content": body})

    for line in text.splitlines():
        m = _RE_COLON.match(line) or _RE_SAID.match(line) or _RE_ALONE.match(line)
        if m:
            flush()
            role, buf = _norm_role(m.group(1).lower().replace(" said", "")), []
            if m.lastindex and m.lastindex >= 2 and m.group(2).strip():
                buf.append(m.group(2))
        else:
            buf.append(line)
    flush()
    if not msgs and text.strip():
        msgs = [{"role": "user", "content": text.strip()}]
    return new_conv(title, "Pasted text", msgs)


def parse_file(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    title = os.path.splitext(os.path.basename(path))[0]
    if path.lower().endswith(".json"):
        convs = parse_json(json.loads(raw))
        if not convs:
            raise ValueError("No conversations recognised in that JSON file.")
        return convs
    return [parse_text(raw, title)]


# ---------------------------------------------------------------- finding chats on this PC
_NOISE = re.compile(r"<(system-reminder|command-\w+|local-command-\w+|ide_\w+)>.*?</\1>", re.S)


def _text_blocks(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict)
                         and b.get("type") in (None, "text", "input_text", "output_text") and isinstance(b.get("text"), str))
    return ""


def _mtime(path):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))


_AT_MENTION = re.compile(r'@"[^"]*"|@\S+')
_URL_IN_TEXT = re.compile(r"https?://([^\s/?#]+)\S*")


def _strip_tags(text):
    """Remove hidden control markup like <environment_context>…</environment_context> that some apps put in their chats."""
    text = re.sub(r"<([A-Za-z_][\w:.-]*)(?:\s[^>]*)?>.*?</\1>", " ", text or "", flags=re.S)
    return re.sub(r"</?[A-Za-z_][\w:.-]*(?:\s[^>]*)?/?>", " ", text)


def friendly_title(text, limit=64, fallback="Untitled chat"):
    """A readable name for a chat made from its first message: no file paths or @mentions, links shortened to the site
    name, the first sentence only, and not too long."""
    t = _strip_tags(_AT_MENTION.sub(" ", text or ""))
    t = _URL_IN_TEXT.sub(lambda m: m.group(1), t)
    t = re.sub(r"\s+", " ", t).strip(" .,:;-—")
    first = re.split(r"(?<=[.!?])\s", t, maxsplit=1)[0].strip(" .")
    if len(first) >= 12:
        t = first
    if len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0] or t[:limit]
        t = cut.rstrip(" .,;:-") + "…"
    return (t[:1].upper() + t[1:]) if t else fallback


def _title_from(msgs, fallback):
    for m in msgs:
        if m["role"] == "user":
            t = friendly_title(m["content"], fallback="")
            if len(t) >= 3:                 # skip messages that were only hidden markup
                return t
    return fallback


def parse_claude_code(path):
    msgs, ts, usage = [], None, {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            u = (o.get("message") or {}).get("usage") if o.get("type") == "assistant" else None
            if isinstance(u, dict):  # the same message can be logged several times; keep the latest figures per id
                usage[(o.get("message") or {}).get("id") or o.get("uuid") or len(usage)] = u
            if o.get("type") not in ("user", "assistant") or o.get("isSidechain") or o.get("isMeta"):
                continue
            text = _NOISE.sub("", _text_blocks((o.get("message") or {}).get("content"))).strip()
            if text:
                msgs.append({"role": o["type"], "content": text})
                ts = ts or o.get("timestamp")
    created = (ts or "")[:16].replace("T", " ") or _mtime(path)
    conv = new_conv(_title_from(msgs, os.path.basename(path)), "Claude Code", msgs, created)
    if usage:
        conv["usage"] = {"in": sum(int(u.get("input_tokens") or 0) for u in usage.values()),
                         "out": sum(int(u.get("output_tokens") or 0) for u in usage.values()),
                         "cache_read": sum(int(u.get("cache_read_input_tokens") or 0) for u in usage.values()),
                         "cache_create": sum(int(u.get("cache_creation_input_tokens") or 0) for u in usage.values())}
    return conv


def parse_codex(path):
    msgs = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                p = json.loads(line).get("payload") or {}
            except ValueError:
                continue
            if p.get("type") == "message" and p.get("role") in ("user", "assistant"):
                text = _text_blocks(p.get("content")).strip()
                if text and _strip_tags(text).strip():       # skip messages that are only hidden markup (no real words)
                    msgs.append({"role": p["role"], "content": text})
    return new_conv(_title_from(msgs, os.path.basename(path)), "Codex", msgs, _mtime(path))


def parse_gemini_cli(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    msgs = []
    for m in data.get("messages", []) if isinstance(data, dict) else []:
        text = _flat(m.get("content")).strip()
        if text:
            msgs.append({"role": "user" if m.get("type") == "user" else "assistant", "content": text})
    return new_conv(_title_from(msgs, os.path.basename(path)), "Gemini CLI", msgs, _mtime(path))


def parse_lmstudio(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    msgs = []
    for m in data.get("messages", []):
        vs = m.get("versions") or [m]
        v = vs[min(m.get("currentlySelected", 0), len(vs) - 1)]
        role = _norm_role(v.get("role") or (v.get("senderInfo") or {}).get("role") or m.get("role") or "assistant")
        text = _flat(v.get("content")).strip()
        if text:
            msgs.append({"role": role, "content": text})
    return new_conv(data.get("name") or _title_from(msgs, os.path.basename(path)), "LM Studio", msgs, _mtime(path))


def parse_jan(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        meta = json.load(f)
    msgs = []
    mp = os.path.join(os.path.dirname(path), "messages.jsonl")
    if os.path.exists(mp):
        with open(mp, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                text = _flat(o.get("content")).strip()
                if text and o.get("role") in ("user", "assistant"):
                    msgs.append({"role": o["role"], "content": text})
    return new_conv(meta.get("title") or _title_from(msgs, "Jan chat"), "Jan", msgs, _mtime(path))


def discover_chats(limit=400):
    """Find chats that AI apps keep as readable files on this PC. Returns unsaved conversations."""
    from glob import glob
    home, appdata = os.path.expanduser("~"), os.environ.get("APPDATA", "")
    sources = [
        (os.path.join(home, ".claude", "projects", "*", "*.jsonl"), parse_claude_code),
        (os.path.join(home, ".codex", "sessions", "**", "*.jsonl"), parse_codex),
        (os.path.join(home, ".gemini", "tmp", "*", "chats", "*.json"), parse_gemini_cli),
        (os.path.join(home, ".lmstudio", "conversations", "*.json"), parse_lmstudio),
        (os.path.join(appdata, "Jan", "data", "threads", "*", "thread.json"), parse_jan),
    ]
    out = []
    for pattern, parser in sources:
        files = sorted(glob(pattern, recursive=True), key=os.path.getmtime, reverse=True)[:limit]
        for p in files:
            try:
                c = parser(p)
            except Exception:
                continue
            if c["messages"]:
                c["origin"] = p
                out.append(c)
    return out


# ---------------------------------------------------------------- export / handoff
def label(role):
    return {"user": "User", "assistant": "Assistant", "system": "System"}.get(role, role.title())


def to_markdown(conv):
    out = [f"# {conv['title']}", f"*Source: {conv.get('source', '?')} - {conv.get('created', '')}*", ""]
    for m in conv["messages"]:
        out += [f"## {label(m['role'])}", "", m["content"], ""]
    return "\n".join(out)


def _about_block(about):
    return f"\n\n<about_me>\nBackground the user wants you to know:\n{about.strip()}\n</about_me>" if (about or "").strip() else ""


def build_handoff(conv, last_n, mode, extra, about=""):
    msgs = conv["messages"]
    if mode == "summary" and conv.get("summary", "").strip():
        msgs = msgs[-(last_n or 6):]
        body = ("<summary_of_earlier_conversation>\n" + conv["summary"].strip() +
                "\n</summary_of_earlier_conversation>\n\n<most_recent_messages>\n" + _fmt(msgs) +
                "\n</most_recent_messages>")
    else:
        if last_n:
            msgs = msgs[-last_n:]
        body = "<transcript>\n" + _fmt(msgs) + "\n</transcript>"
    head = (f"You are picking up a conversation that took place earlier with another AI assistant "
            f"({conv.get('source') or 'unknown'}). Read it fully and treat it as your own prior context: "
            f"keep the same goals, decisions, style and any constraints already established. Do not "
            f"re-introduce yourself or recap at length. Reply with one or two sentences confirming where "
            f"we left off, then continue with the user's latest request or the clear next step.")
    if extra.strip():
        head += "\n\nAdditional instructions: " + extra.strip()
    return head + _about_block(about) + "\n\n" + body + "\n"


def build_handoff_many(convs, last_n, extra, about=""):
    parts, has_project = [], False
    for c in convs:
        if c.get("kind") == "project":
            has_project = True
            parts.append(f'<project name="{c["title"]}">\n{c["messages"][0]["content"]}\n</project>')
            continue
        msgs = c["messages"][-last_n:] if last_n else c["messages"]
        parts.append(f'<conversation title="{c["title"]}" source="{c.get("source", "unknown")}">\n{_fmt(msgs)}\n</conversation>')
    if has_project:
        head = (f"You are picking up earlier work from other AI assistants. Below are {len(convs)} item(s): project files "
                f"(code and documents) and/or earlier conversations. Read everything and treat it as your own prior "
                f"context: keep the goals, decisions, conventions and constraints already established. Do not recap "
                f"at length. Reply with a short summary of what the project is and where the work stands, then ask "
                f"what to do next (or continue the clear next step).")
    else:
        head = (f"You are picking up {len(convs)} earlier conversations that took place with other AI assistants. Read "
                f"them all and treat them as your own prior context: keep the goals, decisions, style and constraints "
                f"established in each. Do not recap at length. Reply with one or two sentences listing what each "
                f"conversation was about, then ask which one to continue (or continue the clear next step).")
    if extra.strip():
        head += "\n\nAdditional instructions: " + extra.strip()
    return head + _about_block(about) + "\n\n" + "\n\n".join(parts) + "\n"


def _fmt(msgs):
    return "\n\n".join(f"[{label(m['role'])}]\n{m['content']}" for m in msgs)


# ---------------------------------------------------------------- model calls
def _clean(msgs):
    out = []
    for m in msgs:
        if m["role"] == "system":
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": m["role"], "content": m["content"]})
    if out and out[0]["role"] == "assistant":
        out.insert(0, {"role": "user", "content": "(conversation start)"})
    return out


def call_model(cfg, system, msgs):
    msgs = _clean(msgs)
    base = cfg["base_url"].rstrip("/")
    if cfg["provider"] == "Anthropic":
        url, headers = base + "/v1/messages", {
            "x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01"}
        body = {"model": cfg["model"], "max_tokens": 4096, "system": system, "messages": msgs}
    else:
        url, headers = base + "/chat/completions", {"Authorization": "Bearer " + cfg["api_key"]}
        body = {"model": cfg["model"], "messages": [{"role": "system", "content": system}] + msgs}
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, json.dumps(body).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}")
    if cfg["provider"] == "Anthropic":
        return "".join(b.get("text", "") for b in data.get("content", []))
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------- UI
class ScrollFrame(tk.Frame):
    """A vertically scrolling container; put widgets in .inner."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(self, command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=bg)
        self.win = self.cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self.win, width=e.width))
        self.bind("<Enter>", lambda e: self.cv.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", self._leave)

    def _wheel(self, e):
        self.cv.yview_scroll(-1 * (e.delta // 120), "units")

    def _leave(self, e):
        w = self.winfo_containing(*self.winfo_pointerxy())
        if w is None or not str(w).startswith(str(self)):
            self.cv.unbind_all("<MouseWheel>")


class App:
    def __init__(self, root):
        self.root = root
        root.title("ChatBridge")
        root.geometry("1320x820")
        root.minsize(980, 620)
        self.lib = load_json(LIB_PATH, [])
        self.cfg = {**DEFAULT_CFG, **load_json(CFG_PATH, {})}
        self.q = queue.Queue()
        self.cur = None
        self.shown = []
        self.apps = []
        self.found = []
        self.checked = set()
        self.send_convs = None
        self.paste_title, self.paste_done, self.paste_delay = None, None, 2500
        self.sel_target = None  # None = nothing chosen, "copy", or an index into self.apps
        self.setup_theme()
        self.status = tk.StringVar(value="Looking for your AI apps and chats...")
        self.autopaste = tk.BooleanVar(value=True)
        self.adv = tk.Toplevel(root)  # the old full-featured window, now behind the Advanced button
        self.adv.title("ChatBridge - Advanced")
        self.adv.geometry("1180x780")
        self.adv.configure(bg=BG)
        self.adv.withdraw()
        self.adv.protocol("WM_DELETE_WINDOW", self.adv.withdraw)
        self.build(self.adv)
        self.build_main()
        self.refresh()
        root.bind_all("<Control-MouseWheel>", lambda e: self.zoom(1 if e.delta > 0 else -1))
        root.bind_all("<Control-plus>", lambda e: self.zoom(1))
        root.bind_all("<Control-equal>", lambda e: self.zoom(1))
        root.bind_all("<Control-minus>", lambda e: self.zoom(-1))
        root.after(100, self.poll)
        root.after(600, self.scan)
        root.after(900, self.scan_chats)

    # ---- simple main screen: 1 pick chats, 2 pick destination, 3 send
    def build_main(self):
        r = self.root
        top = tk.Frame(r, bg=BG)
        top.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(top, text="ChatBridge", bg=BG, fg=FG, font=self.font_big).pack(side="left")
        tk.Label(top, text="Move a chat from one AI to another", bg=BG, fg=MUTED, font=self.font).pack(side="left", padx=14)
        ttk.Button(top, text="Advanced", command=lambda: self.open_advanced(0)).pack(side="right")
        ttk.Button(top, text="A+", width=3, command=lambda: self.zoom(1)).pack(side="right", padx=6)
        ttk.Button(top, text="A-", width=3, command=lambda: self.zoom(-1)).pack(side="right")
        body = tk.Frame(r, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=6)
        for i in range(3):
            body.columnconfigure(i, weight=1, uniform="c")
        body.rowconfigure(0, weight=1)

        def panel(col, n, title):
            p = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            p.grid(row=0, column=col, sticky="nsew", padx=6)
            h = tk.Frame(p, bg=PANEL)
            h.pack(fill="x", padx=12, pady=(12, 8))
            tk.Label(h, text=str(n), bg=ACCENT, fg=ACC_FG, font=self.font_b, width=2).pack(side="left")
            tk.Label(h, text=title, bg=PANEL, fg=FG, font=self.font_big).pack(side="left", padx=10)
            return p

        p1 = panel(0, 1, "Pick your chats")
        f = tk.Frame(p1, bg=PANEL)
        f.pack(fill="both", expand=True, padx=12)
        self.pool_tree = ttk.Treeview(f, columns=("info",), show="tree", selectmode="none")
        self.pool_tree.column("#0", width=250, stretch=True)
        self.pool_tree.column("info", width=100, stretch=False)
        sb = ttk.Scrollbar(f, command=self.pool_tree.yview)
        self.pool_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.pool_tree.pack(side="left", fill="both", expand=True)
        self.pool_tree.tag_configure("group", foreground=ACCENT, font=self.font_b)
        self.pool_tree.bind("<Button-1>", self.toggle_chat)
        self.groups = {}
        links = tk.Frame(p1, bg=PANEL)
        links.pack(fill="x", padx=12, pady=(10, 2))
        self.link(links, "Add from file", self.import_file)
        self.link(links, "Paste text", self.paste_dialog)
        links2 = tk.Frame(p1, bg=PANEL)
        links2.pack(fill="x", padx=12, pady=2)
        self.link(links2, "Add a project folder", self.project_dialog)
        links3 = tk.Frame(p1, bg=PANEL)
        links3.pack(fill="x", padx=12, pady=2)
        self.link(links3, "Tick all", lambda: self.tick_all(True))
        self.link(links3, "Tick none", lambda: self.tick_all(False))
        links4 = tk.Frame(p1, bg=PANEL)
        links4.pack(fill="x", padx=12, pady=(2, 12))
        self.link(links4, "Where are my ChatGPT chats?", self.cloud_help)

        p2 = panel(1, 2, "Where should it go?")
        self.tiles = ScrollFrame(p2, PANEL)
        self.tiles.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        links5 = tk.Frame(p2, bg=PANEL)
        links5.pack(fill="x", padx=12, pady=(0, 12))
        self.link(links5, "Test this app (sends nothing)", self.test_app)
        links6 = tk.Frame(p2, bg=PANEL)
        links6.pack(fill="x", padx=12, pady=(0, 12))
        self.link(links6, "Edit app list", self.edit_profiles)

        p3 = panel(2, 3, "Send it")
        self.sum_lbl = tk.Label(p3, text="", bg=PANEL, fg=FG, font=self.font, justify="left", anchor="nw", wraplength=300)
        self.sum_lbl.pack(fill="x", padx=14, pady=6)
        p3.bind("<Configure>", lambda e: self.sum_lbl.configure(wraplength=max(200, e.width - 40)))
        ttk.Checkbutton(p3, text="Paste into the app automatically", variable=self.autopaste).pack(anchor="w", padx=14, pady=6)
        self.send_main = ttk.Button(p3, text="Send", style="Big.TButton", command=self.send_simple)
        self.send_main.pack(fill="x", padx=14, pady=10)
        tk.Label(p3, text="ChatBridge never presses Enter for you - you stay in control of what gets sent.",
                 bg=PANEL, fg=MUTED, font=self.font_small, justify="left", wraplength=300,
                 anchor="w").pack(fill="x", padx=14)
        tk.Label(r, textvariable=self.status, bg=BG, fg=MUTED, font=self.font_small, anchor="w").pack(
            fill="x", padx=24, pady=(2, 10))
        self.render_tiles()

    def link(self, parent, text, cmd):
        lb = tk.Label(parent, text=text, bg=PANEL, fg=USER_CLR, font=self.font_link, cursor="hand2")
        lb.pack(side="left", padx=(0, 16))
        lb.bind("<Button-1>", lambda e: cmd())
        return lb

    def open_advanced(self, tab=0):
        self.adv.deiconify()
        self.adv.lift()
        self.tabs.select(tab)

    def pool(self):
        have = {c.get("origin") for c in self.lib if c.get("origin")}
        return self.lib + [c for c in self.found if c["origin"] not in have]

    def checked_convs(self):
        return [c for c in self.pool() if c["id"] in self.checked]

    def _row_text(self, c):
        return ("☑  " if c["id"] in self.checked else "☐  ") + c["title"]

    def _group_text(self, src, items):
        on = sum(c["id"] in self.checked for c in items)
        box = "☑" if on == len(items) else ("▣" if on else "☐")
        return f"{box}  From {src}  ({len(items)})"

    def refresh_pool(self):
        """List chats grouped under the app/place each one came from."""
        t = self.pool_tree
        t.delete(*t.get_children())
        self.groups = {}
        for c in self.pool():
            self.groups.setdefault(c.get("source") or "Other", []).append(c)
        for src, items in self.groups.items():
            gid = "grp:" + src
            t.insert("", "end", iid=gid, text=self._group_text(src, items), values=("",), open=True, tags=("group",))
            for c in items:
                t.insert(gid, "end", iid=c["id"], text=self._row_text(c), values=(c.get("created", "")[:10],))
        self.refresh_summary()

    def _update_rows(self):
        for src, items in self.groups.items():
            self.pool_tree.item("grp:" + src, text=self._group_text(src, items))
            for c in items:
                self.pool_tree.item(c["id"], text=self._row_text(c))
        self.refresh_summary()

    def toggle_chat(self, e):
        iid = self.pool_tree.identify_row(e.y)
        if iid.startswith("grp:"):
            ids = {c["id"] for c in self.groups.get(iid[4:], [])}
            if ids <= self.checked:
                self.checked -= ids
            else:
                self.checked |= ids
            self._update_rows()
        elif iid:
            self.checked.symmetric_difference_update({iid})
            self._update_rows()
        return "break"

    def tick_all(self, on):
        self.checked = {c["id"] for c in self.pool()} if on else set()
        self.refresh_pool()

    def render_tiles(self):
        inner = self.tiles.inner
        for w in inner.winfo_children():
            w.destroy()
        subs = {"Desktop app": "Installed on this PC", "Possible AI app": "Might be an AI app",
                "CLI tool": "Command-line tool"}
        order = {"Desktop app": 0, "Local server": 1, "CLI tool": 2, "Possible AI app": 3}
        for i in sorted(range(len(self.apps)), key=lambda i: (order.get(self.apps[i]["kind"], 9), self.apps[i]["name"].lower())):
            a = self.apps[i]
            sub = (f"Runs on this PC - {len(a['models'])} model(s)" if a["kind"] == "Local server"
                   else subs.get(a["kind"], a["kind"]))
            t = self.cfg.get("compat", {}).get(a["name"])
            if t:
                sub += "  -  tested: " + ("works" if t["ok"] else "didn't work")
            self.tile(i, a["name"], sub)
        self.tile("copy", "Copy only", "Paste it anywhere yourself")
        self.refresh_summary()

    def tile(self, key, name, sub):
        palette = ("#f0997b", "#93c5fd", "#5dcaa5", "#ed93b1", "#afa9ec", "#fac775", "#85b7eb")
        color = "#b4b2a9" if key == "copy" else palette[sum(map(ord, name)) % len(palette)]
        sel = self.sel_target == key
        t = tk.Frame(self.tiles.inner, bg=PANEL2, highlightthickness=2, cursor="hand2",
                     highlightbackground=ACCENT if sel else PANEL2)
        t.pack(fill="x", pady=4)
        ic = tk.Label(t, text="+" if key == "copy" else name[:1].upper(), bg=color, fg="#14161a", font=self.font_b, width=3)
        ic.pack(side="left", padx=10, pady=10)
        box = tk.Frame(t, bg=PANEL2)
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text=name, bg=PANEL2, fg=FG, font=self.font_b, anchor="w").pack(fill="x")
        tk.Label(box, text=sub, bg=PANEL2, fg=MUTED, font=self.font_small, anchor="w").pack(fill="x")
        for w in (t, ic, box, *box.winfo_children()):
            w.bind("<Button-1>", lambda e, k=key: self.pick_target(k))

    def pick_target(self, key):
        self.sel_target = key
        self.render_tiles()

    def target_app(self):
        return None if self.sel_target in (None, "copy") else self.apps[self.sel_target]

    def refresh_summary(self):
        if not hasattr(self, "sum_lbl"):
            return
        n = len(self.checked_convs())
        app = self.target_app()
        chats = f"{n} chat{'s' if n != 1 else ''}"
        if n == 0:
            msg, btn = "Tick at least one chat on the left.", "Send"
        elif self.sel_target is None:
            msg, btn = f"{chats} ticked. Now choose where to send {'them' if n != 1 else 'it'}.", "Send"
        elif app is None:
            msg, btn = f"{chats} will be copied. Paste {'them' if n != 1 else 'it'} anywhere with Ctrl+V.", "Copy"
        elif app["kind"] == "Local server":
            msg, btn = f"{chats} will load into {app['name']} and you'll keep chatting with it right here.", f"Send to {app['name']}"
        elif app["kind"] == "CLI tool":
            msg, btn = f"{chats} will be copied and {app['name']} opens in a terminal. Right-click there to paste.", f"Send to {app['name']}"
        else:
            msg, btn = (f"{chats} will be sent to {app['name']}. It opens and the chat is pasted in - then you press Enter.",
                        f"Send to {app['name']}")
        self.sum_lbl.configure(text=msg)
        self.send_main.configure(text=btn)

    def send_simple(self):
        convs = self.checked_convs()
        if not convs:
            messagebox.showinfo("ChatBridge", "Tick at least one chat on the left first.", parent=self.root)
            return
        if self.sel_target is None:
            messagebox.showinfo("ChatBridge", "Choose where to send it in the middle column.", parent=self.root)
            return
        ids = {c["id"] for c in self.lib}
        new = [c for c in convs if c["id"] not in ids]
        if new:
            self.lib = new + self.lib
            self.persist()
            self.refresh()
        self.cur, self.send_convs = convs[0], convs
        self.show()
        try:
            self.deliver(self.target_app())
        finally:
            self.send_convs = None

    def project_dialog(self):
        """Pick a folder, choose which files to bring along, and add it as an item you can send like a chat."""
        root_dir = filedialog.askdirectory(title="Choose the project folder", parent=self.root)
        if not root_dir:
            return
        self.status.set("Reading the project folder...")
        self.root.update_idletasks()
        files, skipped = scan_project(root_dir)
        if not files:
            messagebox.showinfo("ChatBridge", "No text or code files found in that folder.", parent=self.root)
            return
        d = tk.Toplevel(self.root)
        d.title("Add project - " + os.path.basename(root_dir))
        d.geometry("820x640")
        d.configure(bg=BG)
        d.transient(self.root)
        tk.Label(d, text="Choose the files to bring along", bg=BG, fg=FG, font=self.font_big).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(d, text=root_dir, bg=BG, fg=MUTED, font=self.font_small).pack(anchor="w", padx=16)
        f = tk.Frame(d, bg=BG)
        f.pack(fill="both", expand=True, padx=16, pady=10)
        tree = ttk.Treeview(f, columns=("size",), show="tree", selectmode="none")
        tree.column("#0", width=560)
        tree.column("size", width=110, stretch=False, anchor="e")
        sb = ttk.Scrollbar(f, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        total_lbl = tk.Label(d, bg=BG, fg=FG, font=self.font, anchor="w")
        total_lbl.pack(fill="x", padx=16)
        if skipped:
            left_out = ", ".join(r for r, _ in skipped[:4]) + (f" and {len(skipped) - 4} more" if len(skipped) > 4 else "")
            tk.Label(d, text=f"Left out for safety: {left_out}", bg=BG, fg=MUTED, font=self.font_small, anchor="w",
                     justify="left", wraplength=780).pack(fill="x", padx=16, pady=(2, 0))
        on, running = set(), 0
        for i, fl in enumerate(files):  # tick files in priority order until the suggested size is reached
            if running + fl["size"] <= BUDGET:
                on.add(i)
                running += fl["size"]

        def refresh():
            chars = sum(files[i]["size"] for i in on)
            over = chars > BUDGET
            total_lbl.configure(
                text=f"{len(on)} of {len(files)} files  -  about {chars:,} characters (~{chars // 4:,} tokens)"
                     + ("   Large: some apps may cut this off." if over else ""),
                fg="#fac775" if over else FG)
            for i, fl in enumerate(files):
                tree.item(str(i), text=("☑  " if i in on else "☐  ") + fl["rel"])

        for i, fl in enumerate(files):
            tree.insert("", "end", iid=str(i), text="", values=(f"{fl['size']:,} chars",))

        def toggle(e):
            iid = tree.identify_row(e.y)
            if iid:
                on.symmetric_difference_update({int(iid)})
                refresh()
            return "break"
        tree.bind("<Button-1>", toggle)
        refresh()
        btns = tk.Frame(d, bg=BG)
        btns.pack(fill="x", padx=16, pady=12)

        def go():
            chosen = [files[i] for i in sorted(on)]
            if not chosen:
                messagebox.showinfo("ChatBridge", "Tick at least one file.", parent=d)
                return
            d.destroy()
            self.add([project_conv(root_dir, chosen)])
            self.status.set(f"Added the project with {len(chosen)} files. It's ticked - pick where to send it.")
        ttk.Button(btns, text="Add project", style="Accent.TButton", command=go).pack(side="right")
        ttk.Button(btns, text="Cancel", command=d.destroy).pack(side="right", padx=8)
        ttk.Button(btns, text="All", command=lambda: (on.update(range(len(files))), refresh())).pack(side="left")
        ttk.Button(btns, text="None", command=lambda: (on.clear(), refresh())).pack(side="left", padx=8)

    def cloud_help(self):
        messagebox.showinfo("Chats that live online", (
            "ChatGPT, Claude.ai and Gemini keep your chats on their servers, so ChatBridge can't see them on this PC.\n\n"
            "To bring them in:\n"
            "- ChatGPT: Settings > Data controls > Export data. You'll get an email with a zip file.\n"
            "- Claude.ai: Settings > Privacy > Export data.\n"
            "- Gemini: export through Google Takeout.\n\n"
            "Unzip the file, then click 'Add from file' and choose conversations.json.\n"
            "(Menu names can change a little between versions.)"), parent=self.root)

    # ---- theme
    def setup_theme(self):
        self.fs = int(self.cfg.get("ui_size", 16))
        self.font = tkfont.Font(family="Segoe UI", size=self.fs)
        self.font_b = tkfont.Font(family="Segoe UI", size=self.fs, weight="bold")
        self.font_big = tkfont.Font(family="Segoe UI", size=self.fs + 3, weight="bold")
        self.font_link = tkfont.Font(family="Segoe UI", size=self.fs, underline=True)
        self.font_small = tkfont.Font(family="Segoe UI", size=max(9, self.fs - 3))
        for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(n).configure(family="Segoe UI", size=self.fs)
        r = self.root
        r.configure(bg=BG)
        r.option_add("*TCombobox*Listbox.background", PANEL)
        r.option_add("*TCombobox*Listbox.foreground", FG)
        r.option_add("*TCombobox*Listbox.selectBackground", SEL)
        s = self.style = ttk.Style(r)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor=LINE,
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, insertcolor=FG)
        s.configure("TButton", background=PANEL2, foreground=FG, padding=(12, 7), borderwidth=1, bordercolor=LINE)
        s.map("TButton", background=[("active", "#323842")])
        s.configure("Big.TButton", background=ACCENT, foreground=ACC_FG, bordercolor=ACCENT, padding=(20, 14),
                    font=self.font_big)
        s.map("Big.TButton", background=[("active", "#5eead4")])
        s.configure("Accent.TButton", background=ACCENT, foreground=ACC_FG, bordercolor=ACCENT)
        s.map("Accent.TButton", background=[("active", "#5eead4")])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(18, 9))
        s.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", ACCENT)])
        s.configure("TEntry", fieldbackground=PANEL, foreground=FG, padding=6)
        s.configure("TCombobox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG, padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG, padding=4)
        s.configure("TRadiobutton", background=BG, foreground=FG, indicatorcolor=PANEL)
        s.map("TRadiobutton", indicatorcolor=[("selected", ACCENT)], background=[("active", BG)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, borderwidth=0,
                    rowheight=int(self.fs * 2.4))
        s.map("Treeview", background=[("selected", SEL)], foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=PANEL2, foreground=FG, padding=6)
        s.configure("TScrollbar", background=PANEL2, arrowcolor=FG, bordercolor=PANEL, troughcolor=PANEL)
        s.configure("TPanedwindow", background=BG)
        s.configure("Muted.TLabel", foreground=MUTED)

    def zoom(self, d):
        self.fs = max(9, min(30, self.fs + d))
        for f in (self.font, self.font_b):
            f.configure(size=self.fs)
        self.font_big.configure(size=self.fs + 3)
        self.font_link.configure(size=self.fs)
        self.font_small.configure(size=max(9, self.fs - 3))
        for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(n).configure(size=self.fs)
        self.style.configure("Treeview", rowheight=int(self.fs * 2.4))
        self.cfg["ui_size"] = self.fs
        save_json(CFG_PATH, self.cfg)

    # ---- layout
    def build(self, parent):
        pw = ttk.PanedWindow(parent, orient="horizontal")
        pw.pack(fill="both", expand=True)
        left = ttk.Frame(pw, padding=8)
        right = ttk.Frame(pw, padding=(0, 8, 8, 8))
        pw.add(left, weight=1)
        pw.add(right, weight=4)

        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(left, textvariable=self.search).pack(fill="x")
        ttk.Label(left, text="Search library", foreground=MUTED).pack(anchor="w")
        self.listbox = tk.Listbox(left, exportselection=False, activestyle="none", font=self.font, bg=PANEL, fg=FG,
                                  selectmode="extended",
                                  selectbackground=SEL, selectforeground="#ffffff", relief="flat", borderwidth=0,
                                  highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
        self.listbox.pack(fill="both", expand=True, pady=6)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        for text, cmd in (("Import file...", self.import_file), ("Paste text...", self.paste_dialog),
                          ("Rename", self.rename), ("Delete", self.delete)):
            ttk.Button(left, text=text, command=cmd).pack(fill="x", pady=2)

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.build_conv_tab()
        self.build_handoff_tab()
        self.build_settings_tab()
        self.build_apps_tab()
        self.build_chats_tab()
        ttk.Label(right, textvariable=self.status, foreground=MUTED).pack(anchor="w", pady=(4, 0))

    def text_widget(self, parent, **kw):
        frame = ttk.Frame(parent)
        kw = {"bg": PANEL, "fg": FG, "insertbackground": FG, "selectbackground": SEL, "selectforeground": "#ffffff",
              "relief": "flat", "padx": 14, "pady": 10, "highlightthickness": 1, "highlightbackground": LINE,
              "highlightcolor": ACCENT, "spacing3": 3, **kw}
        t = tk.Text(frame, wrap="word", font=self.font, undo=True, **kw)
        sb = ttk.Scrollbar(frame, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        return frame, t

    def build_conv_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text="Conversation")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Export Markdown", command=lambda: self.export("md")).pack(side="left")
        ttk.Button(bar, text="Export JSON", command=lambda: self.export("json")).pack(side="left", padx=4)
        ttk.Button(bar, text="A+", width=3, command=lambda: self.zoom(1)).pack(side="right")
        ttk.Button(bar, text="A-", width=3, command=lambda: self.zoom(-1)).pack(side="right", padx=4)
        self.info = ttk.Label(bar, foreground=MUTED)
        self.info.pack(side="right", padx=8)
        send = ttk.Frame(tab)
        send.pack(fill="x", pady=(8, 0))
        ttk.Label(send, text="Send this chat to:").pack(side="left")
        self.target = tk.StringVar(value=CLIP_ONLY)
        self.target_box = ttk.Combobox(send, textvariable=self.target, values=[CLIP_ONLY], state="readonly", width=38)
        self.target_box.pack(side="left", padx=8)
        ttk.Checkbutton(send, text="Auto-paste", variable=self.autopaste).pack(side="left")
        ttk.Button(send, text="Send chat", style="Accent.TButton", command=self.send_to_target).pack(side="left", padx=8)
        ttk.Button(send, text="Rescan", command=self.scan).pack(side="left")
        f, self.view = self.text_widget(tab, state="disabled")
        f.pack(fill="both", expand=True, pady=6)
        self.view.tag_configure("user", foreground=USER_CLR, font=self.font_b, spacing1=8)
        self.view.tag_configure("assistant", foreground=ACCENT, font=self.font_b, spacing1=8)
        self.view.tag_configure("system", foreground=MUTED, font=self.font_b, spacing1=8)
        self.view.tag_configure("body", lmargin1=10, lmargin2=10, spacing3=2)
        ttk.Label(tab, text="Continue this conversation with the model in Settings  (Ctrl+Enter to send):").pack(anchor="w")
        f, self.entry = self.text_widget(tab, height=4)
        f.pack(fill="x")
        self.entry.bind("<Control-Return>", lambda e: (self.send(), "break")[1])
        self.send_btn = ttk.Button(tab, text="Send", command=self.send, style="Accent.TButton")
        self.send_btn.pack(anchor="e", pady=4)

    def build_handoff_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text="Handoff prompt")
        opts = ttk.Frame(tab)
        opts.pack(fill="x")
        self.mode = tk.StringVar(value="full")
        ttk.Radiobutton(opts, text="Full transcript", variable=self.mode, value="full").pack(side="left")
        ttk.Radiobutton(opts, text="Summary + recent messages", variable=self.mode, value="summary").pack(side="left", padx=8)
        ttk.Label(opts, text="Only last N messages (0 = all):").pack(side="left", padx=(12, 4))
        self.last_n = tk.IntVar(value=0)
        ttk.Spinbox(opts, from_=0, to=9999, width=6, textvariable=self.last_n).pack(side="left")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Extra instructions:").pack(side="left")
        self.extra = tk.StringVar()
        ttk.Entry(row, textvariable=self.extra).pack(side="left", fill="x", expand=True, padx=4)

        ttk.Label(tab, text="Summary (optional, used by 'Summary + recent'):").pack(anchor="w")
        f, self.summary = self.text_widget(tab, height=5)
        f.pack(fill="x")
        ttk.Button(tab, text="Generate summary with model", command=self.summarize).pack(anchor="w", pady=4)

        btns = ttk.Frame(tab)
        btns.pack(fill="x")
        ttk.Button(btns, text="Build handoff prompt", command=self.build_prompt, style="Accent.TButton").pack(side="left")
        ttk.Button(btns, text="Copy to clipboard", command=self.copy_prompt).pack(side="left", padx=4)
        ttk.Button(btns, text="Save as .txt", command=self.save_prompt).pack(side="left")
        self.size_lbl = ttk.Label(btns, foreground=MUTED)
        self.size_lbl.pack(side="right")
        f, self.prompt = self.text_widget(tab)
        f.pack(fill="both", expand=True, pady=6)

    def build_settings_tab(self):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text="Settings")
        self.v = {k: tk.StringVar(value=self.cfg[k]) for k in ("provider", "base_url", "model", "api_key")}
        ttk.Label(tab, text="Model used for 'Continue' and 'Generate summary'", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        rows = (("Provider", "provider"), ("Base URL", "base_url"), ("Model", "model"), ("API key", "api_key"))
        for i, (lbl, key) in enumerate(rows, 1):
            ttk.Label(tab, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
            if key == "provider":
                w = ttk.Combobox(tab, textvariable=self.v[key], values=list(PROVIDERS), state="readonly", width=60)
                w.bind("<<ComboboxSelected>>", self.on_provider)
            else:
                w = ttk.Entry(tab, textvariable=self.v[key], width=62, show="*" if key == "api_key" else "")
            w.grid(row=i, column=1, sticky="w", padx=8)
        ttk.Button(tab, text="Save settings", command=self.save_settings).grid(row=5, column=1, sticky="w", padx=8, pady=10)
        ttk.Label(tab, foreground=MUTED, justify="left", text=(
            "Works with Anthropic, OpenAI, and anything OpenAI-compatible (Ollama: http://localhost:11434/v1,\n"
            "LM Studio, OpenRouter, ...). Local models need no API key.\n"
            "The key is stored unencrypted in %APPDATA%\\ChatBridge\\config.json on this PC only.")
                  ).grid(row=6, column=0, columnspan=2, sticky="w", pady=8)

    # ---- AI apps
    def build_apps_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text="AI apps")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.scan_btn = ttk.Button(bar, text="Scan this PC", command=self.scan)
        self.scan_btn.pack(side="left")
        ttk.Button(bar, text="Copy handoff and open app", style="Accent.TButton",
                   command=self.handoff_to_app).pack(side="left", padx=6)
        ttk.Button(bar, text="Use as my model", command=self.use_as_model).pack(side="left")
        ttk.Button(bar, text="Add app...", command=self.add_app).pack(side="right")
        ttk.Button(bar, text="Update list online", command=self.update_catalog).pack(side="right", padx=6)
        cols = ("name", "kind", "info")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("name", "Name", 220), ("kind", "Type", 130), ("info", "Details", 420)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.handoff_to_app())
        ttk.Label(tab, foreground=MUTED, justify="left", text=(
            "Finds installed apps, command-line tools, and local model servers (Ollama, LM Studio, Jan, GPT4All).\n"
            "Select one, then 'Copy handoff and open app' copies the current chat's handoff prompt and launches it - paste to continue.\n"
            "Local servers can be set as the model in Settings with 'Use as my model'.")).pack(anchor="w", pady=6)

    def scan(self):
        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.status.set("Scanning for AI apps...")

        def done(res, err):
            self.scan_btn.configure(state="normal", text="Scan this PC")
            self.apps = res or []
            self.target_box.configure(values=[CLIP_ONLY] + [app_label(a) for a in self.apps])
            self.sel_target = None
            self.render_tiles()
            self.tree.delete(*self.tree.get_children())
            for i, a in enumerate(self.apps):
                self.tree.insert("", "end", iid=str(i), values=(a["name"], a["kind"], a["info"]))
            self.status.set(f"Found {len(self.apps)} AI app(s)/tool(s)." if not err else f"Scan failed: {err}")
        self.run_async(scan_apps, done)

    def add_app(self):
        name = simpledialog.askstring("Add app", "Name of the AI app (as shown in the Start menu):", parent=self.root)
        if name and name.strip():
            n = merge_catalog([{"label": name.strip(), "regex": re.escape(name.strip())}])
            self.status.set(f"Added '{name.strip()}' to your list." if n else "That app is already on the list.")
            self.scan()

    def update_catalog(self):
        url = simpledialog.askstring(
            "Update list online", "HTTPS link to a JSON list of apps, e.g. [{\"label\": \"Name\", \"regex\": \"name\"}]:",
            initialvalue=self.cfg.get("catalog_url", ""), parent=self.root)
        if not url or not url.strip():
            return
        self.cfg["catalog_url"] = url.strip()
        save_json(CFG_PATH, self.cfg)
        self.status.set("Downloading app list...")

        def done(res, err):
            if err:
                self.status.set("Update failed.")
                messagebox.showerror("Update failed", str(err))
                return
            self.status.set(f"List updated: {res} new app(s).")
            self.scan()
        self.run_async(lambda: fetch_catalog(self.cfg["catalog_url"]), done)

    def picked_app(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("ChatBridge", "Select an app in the list first.")
            return None
        return self.apps[int(sel[0])]

    def send_to_target(self):
        label = self.target.get()
        app = next((a for a in self.apps if app_label(a) == label), None)
        self.deliver(app)

    def handoff_to_app(self):
        app = self.picked_app()
        if app:
            self.deliver(app)

    def deliver(self, app):
        """Copy the handoff prompt, then open/switch to the chosen app (app=None: clipboard only)."""
        if not self.need_cur():
            return
        self.build_prompt()
        self.copy_prompt()
        if app is None:
            self.status.set("Handoff copied to the clipboard. Paste it anywhere with Ctrl+V.")
        elif app["kind"] == "Local server":
            self.use_server(app)
            self.open_advanced(0)
            self.entry.focus_set()
            self.status.set(f"Connected to {app['name']}. Type below to continue this chat with it.")
        elif app["kind"] == "CLI tool":
            subprocess.Popen(["cmd", "/k", app["name"]], creationflags=0x10)  # new console window
            self.status.set(f"Opened {app['name']} in a terminal. Handoff is on the clipboard - right-click to paste.")
        else:
            self.open_desktop(app, self.cur["title"], self.prompt.get("1.0", "end"))

    def open_desktop(self, app, title, text, done=None, force_full=False):
        """Open a desktop app and paste into it, following that app's profile. done(ok) is called afterwards."""
        prof = profile_for(app["name"])
        self.paste_title, self.paste_done = prof["title"], done
        try:
            keys = parse_keys(prof["new_chat"]) if prof["new_chat"] else None
        except ValueError as e:
            messagebox.showerror("Bad app profile", f"{app['name']}: {e}")
            return
        exe, folder = None, None
        if prof["paste"] == "file" and not force_full:
            # Code editors: save the chat as a file in a workspace folder and ask their agent to read it.
            # A short instruction pastes reliably; a 40,000-character paste into an editor does not.
            path = save_handoff_file(text, title)
            folder = os.path.dirname(path)
            self.root.clipboard_clear()
            self.root.clipboard_append(
                f'Read the file "{path}". It is earlier work I did with another AI assistant. Treat it as our '
                f"prior context, tell me in a sentence where we left off, then continue from there.")
            exe = find_exe(app["name"])
        try:
            if callable(app.get("launch_fn")):
                app["launch_fn"]()
            elif exe:
                subprocess.Popen([exe, folder])
            elif app["launch"] and app["launch"].startswith("shell:"):
                subprocess.Popen(["explorer", app["launch"]])
            elif app["launch"]:
                os.startfile(app["launch"])
            else:
                raise OSError("No launch target found for this app.")
        except OSError as e:
            messagebox.showerror("Couldn't open app", str(e))
            return
        how = "an instruction pointing to your chat file" if folder else "the chat"
        if self.autopaste.get():
            self.status.set(f"Opening {app['name']}... I'll paste {how} as soon as it's in front. Don't click elsewhere.")
            self.wait_then_paste(app["name"], keys)
        else:
            self.status.set(f"Opened {app['name']}. Click its message box and press Ctrl+V ({how} is on the clipboard).")

    def _front(self, name):
        return (getattr(self, "paste_title", None) or name.split()[0].lower()) in self._foreground_title()

    def _finish(self, ok):
        cb, self.paste_done = getattr(self, "paste_done", None), None
        if cb:
            cb(ok)

    def _foreground_title(self):
        import ctypes
        u = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(u.GetForegroundWindow(), buf, 256)
        return buf.value.lower()

    def _press(self, vks):
        import ctypes
        u = ctypes.windll.user32
        for vk in vks:
            u.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            u.keybd_event(vk, 0, 2, 0)

    def wait_then_paste(self, name, focus_keys=None, tries=0):
        """Wait (up to ~25s) for the app's window to be in front, then paste. Never presses Enter."""
        try:
            front = self._front(name)
        except Exception as e:
            self.status.set(f"Auto-paste unavailable ({e}). Press Ctrl+V in {name}.")
            self._finish(False)
            return
        if front:
            self.root.after(self.paste_delay, lambda: self._do_paste(name, focus_keys))  # let the app finish loading
        elif tries < 50:
            self.root.after(500, lambda: self.wait_then_paste(name, focus_keys, tries + 1))
        else:
            self.status.set(f"{name} didn't come to the front. Click its message box and press Ctrl+V.")
            self._finish(False)

    def _do_paste(self, name, focus_keys):
        try:
            if not self._front(name):
                self.status.set(f"{name} isn't in front any more. Click its message box and press Ctrl+V.")
                self._finish(False)
                return
            if focus_keys:
                self._press(list(focus_keys))  # move the cursor into the app's chat box
                self.root.after(1200, lambda: self._paste_now(name))
            else:
                self._paste_now(name)
        except Exception as e:
            self.status.set(f"Auto-paste failed ({e}). Press Ctrl+V in {name}.")
            self._finish(False)

    def _paste_now(self, name):
        try:
            if not self._front(name):
                self.status.set(f"{name} isn't in front any more. Click its message box and press Ctrl+V.")
                self._finish(False)
                return
            self._press([0x11, 0x56])
            self.status.set(f"Pasted into {name}. If it isn't in the chat box, click the box and press Ctrl+V. "
                            f"Check it, then press Enter there to send.")
            self._finish(True)
        except Exception as e:
            self.status.set(f"Auto-paste failed ({e}). Press Ctrl+V in {name}.")
            self._finish(False)

    def test_app(self):
        """Paste a harmless marker (never a real chat) and ask whether it showed up. Sends nothing."""
        app = self.target_app()
        if app is None or app["kind"] not in ("Desktop app", "Possible AI app"):
            messagebox.showinfo("ChatBridge", "Pick a desktop app in the middle column first.", parent=self.root)
            return
        marker = f"ChatBridge test {int(time.time()) % 10000}"
        self.root.clipboard_clear()
        self.root.clipboard_append(marker)

        def done(ok):
            if not ok:
                self.record_compat(app["name"], False)
                return
            yes = messagebox.askyesno("Did it work?", f"Did \"{marker}\" appear in {app['name']}'s message box?\n\n"
                                      "(Nothing was sent. You can delete the text there.)", parent=self.root)
            self.record_compat(app["name"], yes)
        self.open_desktop(app, "test", marker, done=done, force_full=True)

    def record_compat(self, name, ok):
        self.cfg.setdefault("compat", {})[name] = {"ok": bool(ok), "date": time.strftime("%Y-%m-%d")}
        save_json(CFG_PATH, self.cfg)
        self.render_tiles()
        self.status.set(f"{name}: marked as {'working' if ok else 'not working yet'}.")

    def edit_profiles(self):
        if not os.path.exists(PROFILES_PATH):
            save_json(PROFILES_PATH, DEFAULT_PROFILES)
        os.startfile(PROFILES_PATH)
        self.status.set("Edit the app list in Notepad, save, and the next Send uses it. "
                        "Keys look like ctrl+shift+l. Enter is never allowed.")

    def use_as_model(self):
        app = self.picked_app()
        if not app:
            return
        if app["kind"] != "Local server":
            messagebox.showinfo("ChatBridge", "Only running local model servers can be used directly.\n"
                                "For other apps, use 'Copy handoff and open app'.")
            return
        self.use_server(app)

    def use_server(self, app):
        model = app["models"][0] if app["models"] else ""
        if len(app["models"]) > 1:
            model = simpledialog.askstring("Choose model", "Available models:\n" + "\n".join(app["models"][:30]) +
                                           "\n\nModel to use:", initialvalue=model, parent=self.root) or model
        self.v["provider"].set("OpenAI-compatible")
        self.v["base_url"].set(app["base_url"])
        self.v["model"].set(model)
        self.v["api_key"].set("")
        self.save_settings()
        self.status.set(f"Now using {model} on {app['name']}. Continue chats from the Conversation tab.")

    # ---- library
    def refresh(self):
        q = self.search.get().lower()
        self.shown = [c for c in self.lib if q in c["title"].lower() or q in c.get("source", "").lower()]
        self.listbox.delete(0, "end")
        for c in self.shown:
            self.listbox.insert("end", f"{c['title']}  [{c.get('source', '?')}]")
        if self.cur in self.shown:
            i = self.shown.index(self.cur)
            self.listbox.selection_set(i)
        if hasattr(self, "pool_tree"):
            self.refresh_pool()

    def persist(self):
        save_json(LIB_PATH, self.lib)

    def on_select(self, _=None):
        sel = self.listbox.curselection()
        if sel:
            self.cur = self.shown[sel[0]]
            self.show()
            if len(sel) > 1:
                self.status.set(f"{len(sel)} chats selected - 'Send chat' will hand all of them over together.")

    def selected_convs(self):
        if self.send_convs:
            return self.send_convs
        sel = [self.shown[i] for i in self.listbox.curselection() if i < len(self.shown)]
        return sel or ([self.cur] if self.cur else [])

    # ---- find chats on this PC
    def build_chats_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text="Find chats")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.chat_scan_btn = ttk.Button(bar, text="Scan for chats", command=self.scan_chats)
        self.chat_scan_btn.pack(side="left")
        ttk.Button(bar, text="Select all", command=lambda: self.ctree.selection_set(self.ctree.get_children())).pack(side="left", padx=6)
        ttk.Button(bar, text="Add selected to library", style="Accent.TButton", command=self.import_found).pack(side="left")
        self.ctree = ttk.Treeview(tab, columns=("title", "source", "msgs", "date", "state"), show="headings",
                                  selectmode="extended")
        for c, t, w in (("title", "Chat", 430), ("source", "From", 120), ("msgs", "Msgs", 70),
                        ("date", "Date", 150), ("state", "", 110)):
            self.ctree.heading(c, text=t)
            self.ctree.column(c, width=w, anchor="w")
        self.ctree.pack(fill="both", expand=True)
        self.ctree.bind("<Control-a>", lambda e: (self.ctree.selection_set(self.ctree.get_children()), "break")[1])
        ttk.Label(tab, foreground=MUTED, justify="left", text=(
            "Lists chats that apps keep as files on this PC (Claude Code, Codex, Gemini CLI, LM Studio, Jan).\n"
            "Ctrl-click or Shift-click to pick several, add them to your library, then choose where to send them.\n"
            "Cloud chats (ChatGPT, Claude.ai, Gemini web) aren't stored on the PC - export them from the site and use 'Import file...'.")
                  ).pack(anchor="w", pady=6)
        self.found = []

    def scan_chats(self):
        self.chat_scan_btn.configure(state="disabled", text="Scanning...")
        self.status.set("Looking for chats on this PC...")

        def done(res, err):
            self.chat_scan_btn.configure(state="normal", text="Scan for chats")
            self.found = res or []
            have = {c.get("origin") for c in self.lib}
            self.ctree.delete(*self.ctree.get_children())
            for i, c in enumerate(self.found):
                self.ctree.insert("", "end", iid=str(i), values=(
                    c["title"], c["source"], len(c["messages"]), c.get("created", ""),
                    "In library" if c["origin"] in have else ""))
            self.status.set(f"Found {len(self.found)} chat(s) on this PC." if not err else f"Chat scan failed: {err}")
            self.refresh_pool()
            if not self.cfg.get("welcomed"):
                self.cfg["welcomed"] = True
                save_json(CFG_PATH, self.cfg)
                messagebox.showinfo("Welcome to ChatBridge", (
                    "ChatBridge moves a conversation from one AI to another so you can pick up where you left off.\n\n"
                    "1. Tick the chats you want.\n2. Choose where they should go.\n3. Press Send.\n\n"
                    "It already looked for AI apps and chats on this PC."), parent=self.root)
        self.run_async(discover_chats, done)

    def import_found(self):
        sel = [int(i) for i in self.ctree.selection()]
        have = {c.get("origin") for c in self.lib}
        new = [self.found[i] for i in sel if self.found[i]["origin"] not in have]
        if not sel:
            messagebox.showinfo("ChatBridge", "Select one or more chats in the list first.")
        elif not new:
            self.status.set("Those chats are already in your library.")
        else:
            self.add(new)
            self.status.set(f"Added {len(new)} chat(s) to your library. Select them on the left, then 'Send chat'.")
            self.scan_chats()

    def show(self):
        c = self.cur
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        for m in c["messages"]:
            self.view.insert("end", ("Project files" if c.get("kind") == "project" else label(m["role"])) + "\n", m["role"])
            self.view.insert("end", m["content"] + "\n\n", "body")
        self.view.configure(state="disabled")
        self.view.see("end")
        chars = sum(len(m["content"]) for m in c["messages"])
        self.info.configure(text=f"{len(c['messages'])} messages - ~{chars // 4:,} tokens - {c.get('created', '')}")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", c.get("summary", ""))
        self.prompt.delete("1.0", "end")

    def add(self, convs):
        self.lib = convs + self.lib
        self.checked.update(c["id"] for c in convs)
        self.persist()
        self.cur = convs[0]
        self.search.set("")
        self.refresh()
        self.show()
        self.status.set(f"Imported {len(convs)} conversation(s).")

    def need_cur(self):
        if not self.cur:
            messagebox.showinfo("ChatBridge", "Select or import a conversation first.")
        return self.cur

    def import_file(self):
        paths = filedialog.askopenfilenames(title="Import chat export", filetypes=[
            ("Chat files", "*.json *.txt *.md *.markdown"), ("All files", "*.*")])
        convs = []
        for p in paths:
            try:
                convs += parse_file(p)
            except Exception as e:
                messagebox.showerror("Import failed", f"{os.path.basename(p)}:\n{e}")
        if convs:
            self.add(convs)

    def paste_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("Paste a conversation")
        d.geometry("700x520")
        d.configure(bg=BG)
        d.transient(self.root)
        ttk.Label(d, text="Paste the chat. Lines like 'User:' / 'Assistant:' / 'You said:' / 'ChatGPT said:' split the turns.").pack(
            anchor="w", padx=8, pady=6)
        row = ttk.Frame(d)
        row.pack(fill="x", padx=8)
        ttk.Label(row, text="Title:").pack(side="left")
        title = tk.StringVar(value="Pasted chat")
        ttk.Entry(row, textvariable=title).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(row, text="Source:").pack(side="left")
        src = tk.StringVar(value="Pasted text")
        ttk.Entry(row, textvariable=src, width=16).pack(side="left", padx=4)
        f, t = self.text_widget(d)
        f.pack(fill="both", expand=True, padx=8, pady=6)
        t.focus_set()

        def go():
            raw = t.get("1.0", "end").strip()
            if not raw:
                return
            c = parse_text(raw, title.get())
            c["source"] = src.get().strip() or "Pasted text"
            d.destroy()
            self.add([c])
        ttk.Button(d, text="Import", command=go).pack(anchor="e", padx=8, pady=8)

    def rename(self):
        if self.need_cur():
            n = simpledialog.askstring("Rename", "New title:", initialvalue=self.cur["title"], parent=self.root)
            if n and n.strip():
                self.cur["title"] = n.strip()
                self.persist()
                self.refresh()

    def delete(self):
        gone = self.selected_convs()
        if self.need_cur() and messagebox.askyesno("Delete", f"Delete {len(gone)} chat(s) from the library?\n"
                                                   "(The original chats in the other apps are not touched.)"):
            self.lib = [c for c in self.lib if c not in gone]
            self.cur = None
            self.persist()
            self.refresh()
            self.view.configure(state="normal")
            self.view.delete("1.0", "end")
            self.view.configure(state="disabled")

    def export(self, kind):
        if not self.need_cur():
            return
        base = re.sub(r'[\\/:*?"<>|]+', "_", self.cur["title"])[:60]
        if kind == "md":
            path = filedialog.asksaveasfilename(defaultextension=".md", initialfile=base + ".md")
            data = to_markdown(self.cur)
        else:
            path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=base + ".json")
            data = json.dumps({"format": "chatbridge", "conversations": [self.cur]}, ensure_ascii=False, indent=1)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            self.status.set("Saved " + path)

    # ---- handoff
    def build_prompt(self):
        if not self.need_cur():
            return
        self.cur["summary"] = self.summary.get("1.0", "end").strip()
        self.persist()
        try:
            n = max(0, int(self.last_n.get()))
        except (tk.TclError, ValueError):
            n = 0
        convs = self.selected_convs()
        if len(convs) > 1 or any(c.get("kind") == "project" for c in convs):
            text = build_handoff_many(convs, n, self.extra.get())
        else:
            text = build_handoff(self.cur, n, self.mode.get(), self.extra.get())
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", text)
        self.size_lbl.configure(text=f"{len(text):,} chars - ~{len(text) // 4:,} tokens")

    def copy_prompt(self):
        text = self.prompt.get("1.0", "end").strip()
        if not text:
            self.build_prompt()
            text = self.prompt.get("1.0", "end").strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status.set("Handoff prompt copied - paste it into the new app/model.")

    def save_prompt(self):
        text = self.prompt.get("1.0", "end").strip()
        path = text and filedialog.asksaveasfilename(defaultextension=".txt", initialfile="handoff.txt")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    # ---- live model calls
    def save_settings(self):
        self.cfg.update({k: v.get().strip() for k, v in self.v.items()})
        save_json(CFG_PATH, self.cfg)
        self.status.set("Settings saved.")

    def on_provider(self, _=None):
        p = PROVIDERS[self.v["provider"].get()]
        self.v["base_url"].set(p["base_url"])
        self.v["model"].set(p["model"])

    def ready(self):
        self.save_settings()
        if not self.cfg["api_key"] and "localhost" not in self.cfg["base_url"] and "127.0.0.1" not in self.cfg["base_url"]:
            messagebox.showinfo("ChatBridge", "Add an API key in Settings first (not needed for local models).")
            self.open_advanced(2)
            return False
        return True

    def run_async(self, fn, done):
        def work():
            try:
                self.q.put((done, fn(), None))
            except Exception as e:
                self.q.put((done, None, e))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        while not self.q.empty():
            done, res, err = self.q.get()
            done(res, err)
        self.root.after(100, self.poll)

    def send(self):
        text = self.entry.get("1.0", "end").strip()
        if not (self.need_cur() and text and self.ready()):
            return
        conv = self.cur
        conv["messages"].append({"role": "user", "content": text})
        self.entry.delete("1.0", "end")
        self.show()
        self.send_btn.configure(state="disabled")
        self.status.set(f"Waiting for {self.cfg['model']}...")
        system = (f"You are continuing a conversation that began with another AI assistant "
                  f"({conv.get('source') or 'unknown'}). The earlier messages are your own prior context; "
                  f"continue naturally without re-introducing yourself.")
        msgs, cfg = list(conv["messages"]), dict(self.cfg)

        def done(res, err):
            self.send_btn.configure(state="normal")
            if err:
                self.status.set("Error.")
                messagebox.showerror("Model call failed", str(err))
                return
            conv["messages"].append({"role": "assistant", "content": res})
            self.persist()
            if self.cur is conv:
                self.show()
            self.status.set("Reply received.")
        self.run_async(lambda: call_model(cfg, system, msgs), done)

    def summarize(self):
        if not (self.need_cur() and self.ready()):
            return
        conv, cfg = self.cur, dict(self.cfg)
        self.status.set("Summarizing...")
        system = ("You compress conversations so another AI can continue them. Write a dense summary covering: "
                  "the user's goal, key facts and decisions, constraints and preferences, work completed, open "
                  "questions, and the immediate next step. Keep exact names, numbers, code identifiers and file "
                  "paths. No preamble.")
        msgs = [{"role": "user", "content": "Summarize this conversation:\n\n" + _fmt(conv["messages"])}]

        def done(res, err):
            if err:
                self.status.set("Error.")
                messagebox.showerror("Summary failed", str(err))
                return
            conv["summary"] = res.strip()
            self.persist()
            if self.cur is conv:
                self.summary.delete("1.0", "end")
                self.summary.insert("1.0", conv["summary"])
            self.mode.set("summary")
            self.status.set("Summary ready - set to 'Summary + recent messages' mode.")
        self.run_async(lambda: call_model(cfg, system, msgs), done)


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
