"""Small helpers shared by the release scripts and the app: reading CHANGELOG.md, building release notes, bumping the version."""
import datetime
import json
import os
import re


def vkey(v):
    """'1.10.2' -> (1, 10, 2) so versions compare as numbers, not text."""
    nums = [int(n) for n in re.findall(r"\d+", str(v))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def parse_changelog(text):
    """Return [(version, body)] in file order. Sections like '## Unreleased' are skipped."""
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\b", line)
        if m:
            cur = [m.group(1), []]
            out.append(cur)
        elif line.startswith("## "):
            cur = None
        elif cur is not None:
            cur[1].append(line)
    return [(v, "\n".join(body).strip()) for v, body in out]


def changelog_between(text, old, new):
    """Sections newer than `old` up to and including `new`, newest first."""
    secs = [(v, b) for v, b in parse_changelog(text) if vkey(old) < vkey(v) <= vkey(new)]
    return sorted(secs, key=lambda s: vkey(s[0]), reverse=True)


INSTALL_NOTES = """### Install
Download **ChatBridge-Setup.exe** below and run it. It installs for your Windows account only; no administrator rights needed.
Windows may show an "unknown publisher" warning while the app is new - it isn't code-signed yet (see CODE_SIGNING_POLICY.md).
To verify the download, compare its SHA-256 with **SHA256SUMS.txt**.

The browser extension is the separate zip: unzip it, open `edge://extensions`, turn on Developer mode, **Load unpacked**.

**Android:** download **ChatBridge-Android.apk** (attached a few minutes after the other files), open it on your phone and allow "install unknown apps" when asked. It is an early test build.

Everything stays on your PC (or your phone). See PRIVACY.md.
"""


def release_notes(version, changelog_text):
    """The text for a GitHub release: this version's changelog section plus the standard install notes."""
    body = dict(parse_changelog(changelog_text)).get(version)
    if body is None:
        raise ValueError(f"CHANGELOG.md has no '## {version}' section - add one before releasing.")
    return f"## ChatBridge {version}\n\n{body}\n\n{INSTALL_NOTES}"


def bump(version, root):
    """Set VERSION in chatbridge_app.py and make sure CHANGELOG.md has a section for it. Returns what changed."""
    if not re.fullmatch(r"\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?", version):
        raise ValueError("Use a version like 1.2.3 (or 1.2.3-beta1).")
    done = []
    app_py = os.path.join(root, "chatbridge_app.py")
    src = open(app_py, encoding="utf-8").read()
    new_src, n = re.subn(r'^VERSION = "[^"]+"', f'VERSION = "{version}"', src, count=1, flags=re.M)
    if not n:
        raise ValueError("Couldn't find VERSION = \"...\" in chatbridge_app.py")
    if new_src != src:
        open(app_py, "w", encoding="utf-8", newline="").write(new_src)
        done.append(f"chatbridge_app.py: VERSION = {version}")
    for rel in ("mobile/package.json", "mobile/package-lock.json"):       # the Android app's version follows the Windows app's
        path = os.path.join(root, *rel.split("/"))
        if os.path.isfile(path):
            data = json.load(open(path, encoding="utf-8"))
            if data.get("version") != version:
                data["version"] = version
                if isinstance(data.get("packages"), dict) and "" in data["packages"]:
                    data["packages"][""]["version"] = version
                open(path, "w", encoding="utf-8", newline="").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                done.append(f"{rel}: version = {version}")
    log_path = os.path.join(root, "CHANGELOG.md")
    log = open(log_path, encoding="utf-8").read()
    today = datetime.date.today().isoformat()
    if re.search(rf"^##\s+v?{re.escape(version)}\b", log, flags=re.M):
        done.append(f"CHANGELOG.md: already has a section for {version}")
    elif re.search(r"^##\s+Unreleased\s*$", log, flags=re.M):
        log = re.sub(r"^##\s+Unreleased\s*$", f"## {version} ({today})", log, count=1, flags=re.M)
        open(log_path, "w", encoding="utf-8", newline="").write(log)
        done.append(f"CHANGELOG.md: renamed 'Unreleased' to {version}")
    else:
        log = re.sub(r"(# Changelog\s*\n)", rf"\1\n## {version} ({today})\n- (describe what's new)\n", log, count=1)
        open(log_path, "w", encoding="utf-8", newline="").write(log)
        done.append(f"CHANGELOG.md: added a {version} section - edit it")
    return done
