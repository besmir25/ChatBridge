"""ChatBridge simulation tests.

Run (no GUI parts):      python -m unittest discover -s tests -v
Run with the fake-app window too:   set CHATBRIDGE_GUI_TESTS=1  then the same command.

Nothing here touches your real apps, chats, or settings: APPDATA is redirected to a temp folder,
the "AI app" is a fake window, and the "model" is a tiny local HTTP server. The GUI tests inject
keystrokes, but ChatBridge only sends them while the fake window is in front.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

_TMP = tempfile.mkdtemp(prefix="chatbridge-test-")
os.environ["APPDATA"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chatbridge as cb  # noqa: E402


def conv(*pairs, title="t", source="Test"):
    return cb.new_conv(title, source, [{"role": r, "content": c} for r, c in pairs])


class Parsing(unittest.TestCase):
    def test_pasted_text_roles(self):
        c = cb.parse_text("You said:\nHi\nChatGPT said:\nHello! You can ask me anything.\nUser: next\nAssistant: ok")
        self.assertEqual([m["role"] for m in c["messages"]], ["user", "assistant", "user", "assistant"])
        self.assertIn("You can ask me anything", c["messages"][1]["content"])  # "You" mid-line is not a speaker

    def test_chatgpt_export_follows_current_branch(self):
        gpt = [{"title": "t", "current_node": "b", "mapping": {
            "a": {"parent": None, "message": {"author": {"role": "user"}, "content": {"parts": ["q"]}}},
            "b": {"parent": "a", "message": {"author": {"role": "assistant"}, "content": {"parts": ["a"]}}},
            "x": {"parent": "a", "message": {"author": {"role": "assistant"}, "content": {"parts": ["old branch"]}}}}}]
        self.assertEqual([m["content"] for m in cb.parse_json(gpt)[0]["messages"]], ["q", "a"])

    def test_claude_export(self):
        data = [{"name": "n", "chat_messages": [{"sender": "human", "text": "hi"}, {"sender": "assistant", "text": "yo"}]}]
        self.assertEqual([m["role"] for m in cb.parse_json(data)[0]["messages"]], ["user", "assistant"])

    def test_claude_code_jsonl_strips_tool_noise(self):
        p = os.path.join(_TMP, "s.jsonl")
        lines = [
            {"type": "user", "message": {"role": "user", "content": "<system-reminder>x</system-reminder>real question"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Bash"}, {"type": "text", "text": "answer"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "big output"}]}},
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "meta"}},
        ]
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
        msgs = cb.parse_claude_code(p)["messages"]
        self.assertEqual([m["content"] for m in msgs], ["real question", "answer"])


class Handoff(unittest.TestCase):
    def test_single_and_many(self):
        a, b = conv(("user", "hello")), conv(("user", "second"), title="b")
        self.assertIn("[User]\nhello", cb.build_handoff(a, 0, "full", ""))
        many = cb.build_handoff_many([a, b], 0, "extra please")
        self.assertIn("2 earlier conversations", many)
        self.assertIn("extra please", many)

    def test_last_n(self):
        c = conv(*[("user", f"m{i}") for i in range(10)])
        out = cb.build_handoff(c, 2, "full", "")
        self.assertIn("m9", out)
        self.assertNotIn("m0", out)


class Profiles(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(cb.parse_keys("ctrl+shift+l"), [0x11, 0x10, 0x4C])
        self.assertEqual(cb.parse_keys("alt+f4"), [0x12, 0x73])
        for bad in ("enter", "ctrl+Enter", "return", "ctrl+nonsense"):
            with self.assertRaises(ValueError, msg=bad):
                cb.parse_keys(bad)

    def test_builtin_profiles(self):
        self.assertEqual(cb.profile_for("Antigravity")["new_chat"], "ctrl+shift+l")
        self.assertEqual(cb.profile_for("Cursor")["paste"], "file")
        unknown = cb.profile_for("Some New AI")
        self.assertEqual((unknown["paste"], unknown["title"]), ("full", "some"))

    def test_user_profile_overrides_default(self):
        cb.save_json(cb.PROFILES_PATH, [{"match": "antigravity", "new_chat": "ctrl+n", "paste": "full"}])
        try:
            self.assertEqual(cb.profile_for("Antigravity")["new_chat"], "ctrl+n")
        finally:
            os.remove(cb.PROFILES_PATH)


class Projects(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="proj-", dir=_TMP)
        def w(rel, data, mode="w"):
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
                f.write(data)
        w("README.md", "# Demo\n")
        w("app.py", "print('hi')\n")
        w("notes.md", "uses ``` fences\n")
        w(".env", "TOKEN=abc\n")
        w("config.py", "KEY = 'sk-" + "a" * 30 + "'\n")
        w("node_modules/x/index.js", "junk")
        w("logo.png", b"\x89PNG\0\0\0", "wb")

    def test_scan_keeps_safe_files_only(self):
        files, skipped = cb.scan_project(self.root)
        names = [f["rel"] for f in files]
        self.assertEqual(names[0], "README.md")  # readme first
        self.assertIn("app.py", names)
        for banned in (".env", "config.py", "logo.png", "node_modules/x/index.js"):
            self.assertNotIn(banned, names)
        self.assertEqual({r for r, _ in skipped}, {".env", "config.py"})  # secrets are reported, not included

    def test_bundle_and_handoff(self):
        files, _ = cb.scan_project(self.root)
        text = cb.build_project_text(self.root, files)
        self.assertIn("### app.py", text)
        self.assertNotIn("sk-aaaa", text)
        self.assertIn("````", text)  # a file containing ``` gets a longer fence
        c = cb.project_conv(self.root, files)
        self.assertEqual(c["kind"], "project")
        out = cb.build_handoff_many([c, conv(("user", "chat"))], 0, "")
        self.assertIn("<project name=", out)
        self.assertIn("project files", out)


class SizeCompactPrivacy(unittest.TestCase):
    def test_token_estimate_is_sane(self):
        self.assertEqual(cb.estimate_tokens(""), 0)
        prose = "The quick brown fox jumps over the lazy dog. " * 20
        est = cb.estimate_tokens(prose)
        self.assertTrue(len(prose) / 6 < est < len(prose) / 2.5, est)  # prose is roughly 4-5 characters per token
        self.assertGreater(cb.estimate_tokens(prose * 2), est * 1.9)

    def test_compact_shrinks_noise_but_keeps_ends(self):
        big = "```\n" + "\n".join(f"line {i}" for i in range(500)) + "\n```"
        out = cb.compact_text("\x1b[31mred\x1b[0m\n\n\n\n" + big)
        self.assertNotIn("\x1b", out)
        self.assertIn("line 0", out)
        self.assertIn("line 499", out)
        self.assertIn("lines omitted", out)
        self.assertLess(len(out), len(big) / 3)
        msgs = [{"role": "user", "content": "same"}, {"role": "user", "content": "same"}]
        self.assertEqual(len(cb.compact_messages(msgs)), 1)

    def test_scrub_removes_secrets_and_personal_info(self):
        key = "sk-" + "a" * 30
        text = f"mail me at jo.doe@example.com or 407-555-0123. api_key = {key}. File C:\\Users\\Jo Doe\\x.txt"
        out, n = cb.scrub_text(text)
        for leaked in ("jo.doe@example.com", "407-555-0123", key):
            self.assertNotIn(leaked, out)
        self.assertIn("<user>", out)
        self.assertGreaterEqual(n["keys"], 1)
        kept, _ = cb.scrub_text("mail jo@example.com", secrets=True, personal=False)
        self.assertIn("jo@example.com", kept)  # projects keep emails that are part of the code

    def test_claude_code_usage_is_read(self):
        p = os.path.join(_TMP, "u.jsonl")
        lines = [{"type": "user", "message": {"role": "user", "content": "hi"}},
                 {"type": "assistant", "message": {"id": "m1", "role": "assistant", "content": [{"type": "text", "text": "yo"}],
                                                   "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100}}},
                 {"type": "assistant", "message": {"id": "m1", "role": "assistant", "content": [{"type": "text", "text": "yo"}],
                                                   "usage": {"input_tokens": 10, "output_tokens": 7, "cache_read_input_tokens": 100}}}]
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x) for x in lines))
        u = cb.parse_claude_code(p)["usage"]
        self.assertEqual((u["in"], u["out"], u["cache_read"]), (10, 7, 100))  # duplicates of one message count once


class ProjectModes(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pm-", dir=_TMP)
        for rel, data in {"README.md": "# Demo\n", "src/app.py": "import os\n\nclass A:\n    pass\n\ndef run():\n    pass\n" + "x = 1\n" * 2000,
                          "config/settings.yaml": "name: demo\nports:\n  - 80\n", "tests/test_app.py": "def test(): pass\n",
                          "package.json": '{"name": "demo", "version": "1", "scripts": {}}'}.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)

    def test_file_types(self):
        self.assertEqual([cb.file_type(p) for p in ("src/app.py", "config/settings.yaml", "README.md", "tests/test_app.py", "Dockerfile")],
                         ["code", "config", "docs", "tests", "config"])

    def test_modes(self):
        files, _ = cb.scan_project(self.root)
        full = cb.build_project_text(self.root, files, "full")
        outline = cb.build_project_text(self.root, files, "outline")
        tree = cb.build_project_text(self.root, files, "tree")
        self.assertIn("src/\n  app.py", full)           # folder tree is shown with indentation
        self.assertNotIn("\r", full)                    # Windows line endings are normalised
        self.assertGreater(len(full), len(outline))
        self.assertGreater(len(outline), len(tree))
        self.assertIn("class A:", outline)              # outline keeps definitions of the big file
        self.assertNotIn("x = 1\nx = 1\nx = 1", outline)
        self.assertNotIn("class A:", tree)              # tree mode has structure and the README only
        self.assertIn("# Demo", tree)
        self.assertIn("yaml", full)

    def test_outline_of_json_and_yaml(self):
        self.assertIn("scripts: dict", cb.outline_text("package.json", '{"name": "d", "scripts": {}}'))
        self.assertIn("ports:", cb.outline_text("c.yaml", "name: a\nports:\n  - 1\n"))


class WebApi(unittest.TestCase):
    """The backend behind the new window (chatbridge_app.Api), without opening the window."""

    @classmethod
    def setUpClass(cls):
        import chatbridge_app
        cls.app = chatbridge_app
        cls.api = chatbridge_app.Api()

    def test_add_text_then_list(self):
        r = self.api.add_text("Trip", "ChatGPT", "User: hi\nAssistant: hello")
        row = next(c for c in r["chats"] if c["id"] == r["id"])
        self.assertEqual((row["source"], row["count"], row["saved"]), ("ChatGPT", 2, True))
        self.assertIn("error", self.api.add_text("x", "y", "   "))

    def test_send_requires_selection_and_target(self):
        self.assertIn("error", self.api.send([], "copy"))
        r = self.api.add_text("t", "s", "User: a")
        self.assertIn("error", self.api.send([r["id"]], None))

    def test_project_flow_and_handoff(self):
        root = tempfile.mkdtemp(prefix="wp-", dir=_TMP)
        with open(os.path.join(root, "a.py"), "w") as f:
            f.write("x = 1\n")
        with open(os.path.join(root, ".env"), "w") as f:
            f.write("SECRET=1\n")
        self.api._proj = (root, cb.scan_project(root)[0])
        r = self.api.add_project([0])
        conv = next(c for c in self.api._lib if c["id"] == r["id"])
        self.assertEqual(conv["kind"], "project")
        text = self.api._handoff([conv])
        self.assertIn("<project name=", text)
        self.assertNotIn("SECRET", text)

    def test_estimate_scrub_compact_and_about_me(self):
        key = "sk-" + "b" * 30
        r = self.api.add_text("sec", "Test", f"User: my key is {key} and mail a@b.com\nAssistant: ok")
        self.api._cfg["about_me"] = "I am a nurse."
        est = self.api.estimate([r["id"]], "copy", {"scrub": True, "compact": False})
        self.assertGreater(est["tokens"], 0)
        self.assertGreaterEqual(est["scrubbed"]["keys"], 1)
        text, _, _ = self.api._build(self.api._by_ids([r["id"]]), {"scrub": True})
        self.assertNotIn(key, text)
        self.assertIn("I am a nurse.", text)
        unscrubbed, _, _ = self.api._build(self.api._by_ids([r["id"]]), {})
        self.assertIn(key, unscrubbed)
        self.api._cfg["about_me"] = ""

    def test_window_percentage_and_cost(self):
        self.api._apps = [{"name": "Claude", "kind": "Desktop app", "launch": None, "models": []}]
        r = self.api.add_text("w", "Test", "User: " + "word " * 4000)
        self.api._cfg["price_in"] = "3"
        est = self.api.estimate([r["id"]], 0, {})
        self.assertEqual(est["target"], "Claude")
        self.assertEqual(est["window"], 200000)
        self.assertAlmostEqual(est["pct"], est["tokens"] / 2000, delta=0.2)
        self.assertAlmostEqual(est["cost"], est["tokens"] * 3 / 1e6, places=3)
        self.api._cfg["price_in"] = ""
        self.assertIsNone(self.api.estimate([r["id"]], 0, {})["cost"])

    def test_history_and_remembered_target(self):
        self.api._apps = [{"name": "Claude", "kind": "Desktop app", "launch": None, "models": []}]
        self.api._deliver = lambda *a, **k: None  # don't open anything
        r = self.api.add_text("hist", "Test", "User: hello")
        out = self.api.send([r["id"]], "copy", {"scrub": True})
        self.assertTrue(out["ok"])
        self.assertEqual(out["settings"]["last_target"], "copy")
        entry = self.api.get_history()[0]
        self.assertEqual((entry["target"], entry["titles"]), ("the clipboard", ["hist"]))

    def test_re_adding_a_project_refreshes_it(self):
        root = tempfile.mkdtemp(prefix="rp-", dir=_TMP)
        with open(os.path.join(root, "a.py"), "w") as f:
            f.write("x = 1\n")
        for _ in range(2):
            self.api._proj = (root, cb.scan_project(root)[0])
            self.api.add_project([0], "outline")
        self.assertEqual(sum(1 for c in self.api._lib if c.get("path") == root), 1)

    def test_private_state_is_not_exposed_to_the_page(self):
        public = [n for n in vars(self.api) if not n.startswith("_")]
        self.assertEqual(public, [])

    @unittest.skipIf(os.environ.get("CI"), "build servers have no interactive clipboard")
    def test_clipboard_round_trip(self):
        self.app.set_clipboard("héllo ✓ ChatBridge")
        out = __import__("subprocess").run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True,
                                           text=True, encoding="utf-8").stdout.strip()
        self.assertEqual(out, "héllo ✓ ChatBridge")


class BrowserCapture(unittest.TestCase):
    """The local receiver the browser extension talks to."""

    @classmethod
    def setUpClass(cls):
        import chatbridge_app
        cls.api = chatbridge_app.Api()
        cls.port = cls.api.start_capture_server()
        cls.token = cls.api._capture_token()

    @classmethod
    def tearDownClass(cls):
        cls.api._capture_srv.shutdown()
        cls.api._capture_srv.server_close()

    def post(self, body, token=None, origin="chrome-extension://abcdef", path="/capture", raw=None):
        import urllib.error
        import urllib.request
        h = {"Content-Type": "application/json"}
        if token is not None:
            h["X-ChatBridge-Token"] = token
        if origin:
            h["Origin"] = origin
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", raw if raw is not None else json.dumps(body).encode(), h)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    GOOD = {"title": "Trip", "source": "ChatGPT (web)", "url": "https://chatgpt.com/c/abc",
            "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}

    def test_the_port_cannot_be_shared_with_another_listener(self):
        """Regression: a second server must not be able to sit on the same port (Windows allows that by default)."""
        import chatbridge_app
        import socket
        with self.assertRaises(OSError):
            chatbridge_app._ExclusiveServer(("127.0.0.1", self.port), chatbridge_app._CaptureHandler)
        s = socket.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # even a listener that asks to share is refused
            with self.assertRaises(OSError):
                s.bind(("127.0.0.1", self.port))
        finally:
            s.close()

    def test_ping(self):
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/ping", timeout=5) as r:
            self.assertEqual(json.loads(r.read())["app"], "ChatBridge")

    def test_needs_the_pairing_code(self):
        self.assertEqual(self.post(self.GOOD, token=None)[0], 401)
        self.assertEqual(self.post(self.GOOD, token="wrong")[0], 401)

    def test_a_website_cannot_post_even_with_the_code(self):
        self.assertEqual(self.post(self.GOOD, token=self.token, origin="https://evil.example")[0], 403)

    def test_capture_saves_and_recapture_updates(self):
        before = sum(1 for c in self.api._lib if c.get("origin") == "web:https://chatgpt.com/c/abc")
        self.assertEqual(before, 0)
        for _ in range(2):
            code, res = self.post(self.GOOD, token=self.token)
            self.assertEqual((code, res["ok"], res["count"]), (200, True, 2))
        saved = [c for c in self.api._lib if c.get("origin") == "web:https://chatgpt.com/c/abc"]
        self.assertEqual(len(saved), 1)                                   # same URL twice = one chat
        self.assertEqual((saved[0]["source"], saved[0]["messages"][1]["role"]), ("ChatGPT (web)", "assistant"))

    def test_bad_input(self):
        self.assertEqual(self.post({"messages": []}, token=self.token)[0], 400)
        self.assertEqual(self.post(None, token=self.token, raw=b"not json")[0], 400)
        self.assertEqual(self.post(self.GOOD, token=self.token, path="/elsewhere")[0], 404)


class Updates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import chatbridge_app
        cls.m = chatbridge_app

    def test_version_parsing_and_order(self):
        p = self.m.parse_version
        self.assertEqual(p("v1.2.3"), (1, 2, 3))
        self.assertEqual(p("2.0"), (2, 0, 0))
        self.assertGreater(p("v1.10.0"), p("1.9.9"))   # compares numbers, not text
        self.assertEqual(p("garbage"), (0, 0, 0))

    def test_status_for_each_situation(self):
        import urllib.error
        newer = lambda: {"tag_name": "v9.0.0", "html_url": "https://github.com/x/y/releases/tag/v9.0.0", "body": "notes"}
        same = lambda: {"tag_name": "v" + self.m.VERSION, "html_url": "u"}

        def http404():
            raise urllib.error.HTTPError("u", 404, "nf", {}, None)

        def down():
            raise OSError("no network")
        self.assertEqual(self.m.update_info(newer)["status"], "available")
        self.assertEqual(self.m.update_info(same)["status"], "current")
        self.assertEqual(self.m.update_info(http404)["status"], "none")
        self.assertEqual(self.m.update_info(down)["status"], "offline")

    def test_daily_throttle_switch_and_link_whitelist(self):
        api = self.m.Api()
        calls = []
        api._update_fetch = lambda: calls.append(1) or {"tag_name": "v9.9.9", "html_url": "u"}
        api._cfg["update_check"], api._cfg["last_update_check"] = True, 0
        self.assertEqual(api.check_update(False)["status"], "available")
        self.assertEqual(api.check_update(False)["status"], "skipped")     # already checked today
        self.assertEqual(api.check_update(True)["status"], "available")    # 'Check now' always asks
        api._cfg["last_update_check"], api._cfg["update_check"] = 0, False
        self.assertEqual(api.check_update(False)["status"], "skipped")     # switched off
        self.assertEqual(len(calls), 2)
        self.assertIn("error", api.open_release("https://evil.example/x"))
        self.assertIn("error", api.open_release("https://github.com/someone-else/repo/releases"))


LOG = """# Changelog

## Unreleased
- not out yet

## 1.2.0 (2026-11-01)
- third feature

## 1.1.0
- second feature
- **bold** thing

## 1.0.0
- first
"""


class ReleaseTools(unittest.TestCase):
    def setUp(self):
        import release_tools
        self.rt = release_tools

    def test_changelog_parsing_and_ranges(self):
        self.assertEqual([v for v, _ in self.rt.parse_changelog(LOG)], ["1.2.0", "1.1.0", "1.0.0"])   # 'Unreleased' skipped
        self.assertEqual([v for v, _ in self.rt.changelog_between(LOG, "1.0.0", "1.2.0")], ["1.2.0", "1.1.0"])
        self.assertEqual(self.rt.changelog_between(LOG, "1.2.0", "1.2.0"), [])
        self.assertGreater(self.rt.vkey("1.10.0"), self.rt.vkey("1.9.0"))

    def test_release_notes(self):
        notes = self.rt.release_notes("1.1.0", LOG)
        self.assertIn("second feature", notes)
        self.assertIn("ChatBridge-Setup.exe", notes)
        self.assertNotIn("third feature", notes)
        with self.assertRaises(ValueError):
            self.rt.release_notes("9.9.9", LOG)

    def test_bump_turns_unreleased_into_a_version(self):
        root = tempfile.mkdtemp(prefix="bump-", dir=_TMP)
        with open(os.path.join(root, "chatbridge_app.py"), "w", encoding="utf-8") as f:
            f.write('import os\nVERSION = "1.0.0"\nREPO = "x/y"\n')
        with open(os.path.join(root, "CHANGELOG.md"), "w", encoding="utf-8") as f:
            f.write(LOG)
        self.rt.bump("1.3.0", root)
        self.assertIn('VERSION = "1.3.0"', open(os.path.join(root, "chatbridge_app.py"), encoding="utf-8").read())
        log = open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
        self.assertEqual(self.rt.parse_changelog(log)[0][0], "1.3.0")
        self.assertIn("not out yet", dict(self.rt.parse_changelog(log))["1.3.0"])
        self.rt.bump("1.3.0", root)                                    # running it twice changes nothing more
        self.assertEqual(log, open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read())
        for bad in ("1.3", "v1.3.0", "abc"):
            with self.assertRaises(ValueError):
                self.rt.bump(bad, root)

    def test_version_resource_file(self):
        import version_info
        p = os.path.join(_TMP, "vi.txt")
        version_info.write_version_file(p, "1.4.2", "ChatBridge Setup")
        text = open(p, encoding="utf-8").read()
        self.assertIn("filevers=(1, 4, 2, 0)", text)
        self.assertIn("ProductVersion', '1.4.2'", text)


class WhatsNew(unittest.TestCase):
    def setUp(self):
        import chatbridge_app
        self.m = chatbridge_app
        self.api = chatbridge_app.Api()
        self.old_here, self.old_ver = chatbridge_app.HERE, chatbridge_app.VERSION
        folder = tempfile.mkdtemp(prefix="wn-", dir=_TMP)
        with open(os.path.join(folder, "CHANGELOG.md"), "w", encoding="utf-8") as f:
            f.write(LOG)
        chatbridge_app.HERE, chatbridge_app.VERSION = folder, "1.2.0"

    def tearDown(self):
        self.m.HERE, self.m.VERSION = self.old_here, self.old_ver

    def test_fresh_install_shows_nothing_but_records_the_version(self):
        self.api._cfg.pop("seen_version", None), self.api._cfg.pop("welcomed", None)
        self.assertFalse(self.api.whats_new()["show"])
        self.assertEqual(self.api._cfg["seen_version"], "1.2.0")

    def test_upgrade_shows_every_skipped_version_once(self):
        self.api._cfg["seen_version"] = "1.0.0"
        w = self.api.whats_new()
        self.assertTrue(w["show"])
        self.assertEqual([s["version"] for s in w["sections"]], ["1.2.0", "1.1.0"])
        self.assertFalse(self.api.whats_new()["show"])                 # second launch: already seen

    def test_existing_1_0_0_user_who_never_recorded_a_version(self):
        self.api._cfg.pop("seen_version", None)
        self.api._cfg["welcomed"] = True
        self.assertEqual(len(self.api.whats_new()["sections"]), 2)


class _Model(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Model.seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.path.endswith("/v1/messages"):
            out = {"content": [{"type": "text", "text": "anthropic-ok"}]}
        else:
            out = {"choices": [{"message": {"content": "openai-ok"}}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class ModelCalls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Model)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_anthropic_style(self):
        cfg = {"provider": "Anthropic", "base_url": self.base, "model": "m", "api_key": "k"}
        msgs = [{"role": "assistant", "content": "a0"}, {"role": "user", "content": "u1"}, {"role": "user", "content": "u2"}]
        self.assertEqual(cb.call_model(cfg, "sys", msgs), "anthropic-ok")
        path, headers, body = _Model.seen[-1]
        self.assertEqual(headers.get("x-api-key"), "k")
        self.assertEqual(body["system"], "sys")
        self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])  # fixed up for the API
        self.assertIn("u1\n\nu2", body["messages"][2]["content"])

    def test_openai_style(self):
        cfg = {"provider": "OpenAI-compatible", "base_url": self.base, "model": "m", "api_key": ""}
        self.assertEqual(cb.call_model(cfg, "sys", [{"role": "user", "content": "hi"}]), "openai-ok")
        self.assertEqual(_Model.seen[-1][2]["messages"][0], {"role": "system", "content": "sys"})


@unittest.skipUnless(os.environ.get("CHATBRIDGE_GUI_TESTS") == "1", "set CHATBRIDGE_GUI_TESTS=1 to run the fake-app window tests")
class FakeAppWindow(unittest.TestCase):
    """A fake 'AI app' window stands in for Claude/Copilot/Antigravity."""

    def setUp(self):
        import tkinter as tk
        from tkinter import messagebox
        messagebox.showinfo = messagebox.showerror = lambda *a, **k: None
        self.tk = tk
        self.root = tk.Tk()
        self.app = cb.App(self.root)
        self.root.geometry("300x200+0+0")
        self.fake = tk.Toplevel(self.root)
        self.fake.title("FakeAI - chat")
        self.fake.geometry("500x300+400+200")
        self.box = tk.Text(self.fake)
        self.box.pack(fill="both", expand=True)
        self.log = {"new_chat": False, "enter": False}

        def on_key(e):
            ctrl, shift = bool(e.state & 0x4), bool(e.state & 0x1)
            if ctrl and shift and e.keysym.lower() == "l":
                self.log["new_chat"] = True
                self.box.focus_set()
            if e.keysym in ("Return", "KP_Enter"):
                self.log["enter"] = True
        self.fake.bind_all("<KeyPress>", on_key, add="+")
        cb.save_json(cb.PROFILES_PATH, [{"match": "FakeAI", "title": "fakeai", "new_chat": "ctrl+shift+l", "paste": "full"}])
        self.app.paste_delay = 300
        self.target = {"name": "FakeAI", "kind": "Desktop app", "info": "", "launch": None, "models": [],
                       "launch_fn": self.show}

    def tearDown(self):
        if os.path.exists(cb.PROFILES_PATH):
            os.remove(cb.PROFILES_PATH)
        self.root.destroy()

    def show(self):
        self.fake.deiconify()
        self.fake.lift()
        self.fake.focus_force()

    def pump(self, seconds, until=lambda: False):
        end = time.time() + seconds
        while time.time() < end and not until():
            self.root.update()
            time.sleep(0.05)

    def test_chat_is_pasted_and_never_sent(self):
        c = conv(("user", "remember the code word PINEAPPLE"), ("assistant", "noted"), title="sim")
        self.app.lib.append(c)
        self.app.cur, self.app.send_convs = c, [c]
        self.app.deliver(self.target)
        self.pump(30, until=lambda: "PINEAPPLE" in self.box.get("1.0", "end"))
        text = self.box.get("1.0", "end")
        self.assertIn("PINEAPPLE", text, self.app.status.get())
        self.assertIn("You are picking up a conversation", text)
        self.assertTrue(self.log["new_chat"], "profile's new-chat shortcut should have been pressed")
        self.assertFalse(self.log["enter"], "ChatBridge must never press Enter")

    def test_nothing_is_pasted_if_the_app_never_comes_forward(self):
        cb.save_json(cb.PROFILES_PATH, [{"match": "FakeAI", "title": "no-such-window-xyz", "paste": "full"}])
        self.root.clipboard_clear()
        self.root.clipboard_append("SHOULD-NOT-APPEAR")
        self.app.paste_title = "no-such-window-xyz"
        self.app.wait_then_paste("FakeAI", None, tries=50)  # 50 = the wait has already run out
        self.assertIn("didn't come to the front", self.app.status.get())  # before background scans overwrite it
        self.pump(2)
        self.assertNotIn("SHOULD-NOT-APPEAR", self.box.get("1.0", "end"))
        self.assertFalse(self.log["enter"])

    def test_project_is_sent_like_a_chat(self):
        proj = tempfile.mkdtemp(prefix="p-", dir=_TMP)
        with open(os.path.join(proj, "main.py"), "w") as f:
            f.write("MARKER_FILE_CONTENT = 1\n")
        files, _ = cb.scan_project(proj)
        c = cb.project_conv(proj, files)
        self.app.lib.append(c)
        self.app.cur, self.app.send_convs = c, [c]
        self.app.deliver(self.target)
        self.pump(30, until=lambda: "MARKER_FILE_CONTENT" in self.box.get("1.0", "end"))
        self.assertIn("MARKER_FILE_CONTENT", self.box.get("1.0", "end"), self.app.status.get())
        self.assertFalse(self.log["enter"])


if __name__ == "__main__":
    unittest.main()
