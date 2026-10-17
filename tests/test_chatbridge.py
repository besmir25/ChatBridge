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

    def test_bump_keeps_the_android_version_in_step(self):
        import json as _json
        root = tempfile.mkdtemp(prefix="bump-", dir=_TMP)
        os.makedirs(os.path.join(root, "mobile"))
        with open(os.path.join(root, "chatbridge_app.py"), "w", encoding="utf-8") as f:
            f.write('VERSION = "1.0.0"\n')
        with open(os.path.join(root, "CHANGELOG.md"), "w", encoding="utf-8") as f:
            f.write(LOG)
        _json.dump({"name": "m", "version": "0.1.0"}, open(os.path.join(root, "mobile", "package.json"), "w"))
        _json.dump({"name": "m", "version": "0.1.0", "packages": {"": {"name": "m", "version": "0.1.0"}}}, open(os.path.join(root, "mobile", "package-lock.json"), "w"))
        self.rt.bump("2.5.7", root)
        self.assertEqual(_json.load(open(os.path.join(root, "mobile", "package.json")))["version"], "2.5.7")
        lock = _json.load(open(os.path.join(root, "mobile", "package-lock.json")))
        self.assertEqual((lock["version"], lock["packages"][""]["version"]), ("2.5.7", "2.5.7"))

    def test_the_android_version_matches_the_app_and_the_play_version_code_formula_goes_up(self):
        """Google Play rejects an upload whose versionCode doesn't go up: major*10000 + minor*100 + patch must stay ordered."""
        import json as _json
        import chatbridge_app as app
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(_json.load(open(os.path.join(here, "mobile", "package.json"), encoding="utf-8"))["version"], app.VERSION)
        code = lambda v: (lambda a, b, c: a * 10000 + b * 100 + c)(*[int(x) for x in v.split(".")])
        self.assertLess(code("1.4.0"), code("1.4.1"))
        self.assertLess(code("1.9.9"), code("1.10.0"))
        self.assertLess(code("1.99.0"), code("2.0.0"))

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


class ReviewFixes(unittest.TestCase):
    """Regression tests for the problems an independent code review found."""

    # -- untrusted chat files
    def test_hostile_import_is_neutralised(self):
        evil = {"format": "chatbridge", "conversations": [
            {"title": "<b>x</b>" * 100, "source": 5, "kind": "project", "mode": "<img src=x onerror=alert(1)>", "origin": "web:fake",
             "id": "../../x", "path": "C:\\", "messages": [{"role": "user", "content": "hi"}, {"role": "x", "content": 7}, "junk"]},
            {}, {"messages": "nope"}, {"messages": []}, "string", None]}
        convs = cb.parse_json(evil)
        self.assertEqual(len(convs), 1)
        c = convs[0]
        self.assertEqual(c["mode"], "full")                       # not a script
        self.assertNotIn("origin", c)                              # can't hide real chats by spoofing the origin
        self.assertNotEqual(c["id"], "../../x")
        self.assertEqual((len(c["messages"]), c["source"]), (1, "Imported"))
        self.assertLessEqual(len(c["title"]), 120)

    def test_a_damaged_library_does_not_blank_the_app(self):
        import chatbridge_app
        cb.save_json(cb.LIB_PATH, [{"title": "no messages"}, "junk", 5, {"title": "ok", "messages": [{"role": "user", "content": "hi"}]}])
        api = chatbridge_app.Api()
        self.assertEqual([c["title"] for c in api._lib], ["ok"])
        api._lib.append({"id": "bad", "title": "broken"})          # even one that slips in later can't take the list down
        self.assertEqual([c["title"] for c in api._chats()], ["ok"])

    def test_corrupt_files_are_set_aside_not_overwritten(self):
        p = os.path.join(_TMP, "damaged.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write("{ this is not json at all")
        self.assertEqual(cb.load_json(p, []), [])
        self.assertTrue([n for n in os.listdir(_TMP) if n.startswith("damaged.json.corrupt-")])   # kept for recovery
        self.assertFalse(os.path.exists(p))

    def test_saving_from_many_threads_at_once(self):
        import threading
        p, errors = os.path.join(_TMP, "race.json"), []

        def work(i):
            try:
                for j in range(15):
                    cb.save_json(p, {"writer": i, "n": j})
            except Exception as e:
                errors.append(e)
        ts = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errors, [])
        self.assertIn("writer", cb.load_json(p, {}))               # always a complete, valid file
        self.assertTrue(os.path.exists(p + ".bak"))

    # -- secrets and privacy
    def test_scrub_catches_prefixed_names_and_more_token_shapes(self):
        for s in ("OPENAI_API_KEY=abcd1234efgh5678", "DB_PASSWORD=hunter2hunter2", "GITHUB_TOKEN=ghx12345678901",
                  "AWS_SECRET_ACCESS_KEY: wJalrXUtnFEMI/K7MDENG", 'password: "correct horse battery"'):
            out, n = cb.scrub_text(s)
            self.assertGreaterEqual(n["keys"], 1, s)
        for s in ("sk_live_" + "a" * 24, "github_pat_" + "A" * 30, "npm_" + "b" * 36, "postgres://bob:secretpw@db.example.com/x",
                  "eyJhbGciOiJIUzI1NiJ9." + "c" * 20 + "." + "d" * 20, "AccountKey=" + "Zm9vYmFy" * 4):
            self.assertTrue(cb.SECRET_TEXT.search(s), s)

    def test_scrub_user_name_in_every_path_style(self):
        for s in ("C:\\Users\\Jo Doe\\x", "C:\\\\Users\\\\jodoe\\\\x", "c:/users/jodoe/x"):
            out, n = cb.scrub_text(s)
            self.assertNotIn("jodoe", out.lower().replace("jo doe", "jodoe"), s)
            self.assertEqual(n["paths"], 1, s)

    def test_long_text_does_not_stall_the_scrubber(self):
        t0 = time.time()
        cb.scrub_text("a" * 60_000)
        cb.scrub_text("a@" * 20_000)
        self.assertLess(time.time() - t0, 2.0)

    def test_scanner_skips_more_secret_files_folders_and_links(self):
        root = tempfile.mkdtemp(prefix="sc-", dir=_TMP)
        for rel in ("app.py", ".npmrc", "prod.tfvars", "terraform.tfstate", "release.jks", "id_ecdsa", "secret_key.txt",
                    ".aws/config", "secrets/notes.txt", ".ssh/known_hosts"):
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        outside = os.path.join(_TMP, "outside-secret.txt")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("not for sharing")
        try:
            os.symlink(outside, os.path.join(root, "link.txt"))
            linked = True
        except (OSError, NotImplementedError):
            linked = False                                          # creating links needs a privilege on Windows
        files, skipped = cb.scan_project(root)
        self.assertEqual([f["rel"] for f in files], ["app.py"])
        if linked:
            self.assertIn("link.txt", [r for r, _ in skipped])

    def test_project_text_has_no_folder_path(self):
        root = tempfile.mkdtemp(prefix="np-", dir=_TMP)
        with open(os.path.join(root, "a.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        files, _ = cb.scan_project(root)
        text = cb.build_project_text(root, files)
        self.assertNotIn(root, text)
        self.assertNotIn("Users", text.split("File list")[0].split("Folder structure")[0])

    def test_git_is_run_with_program_launching_settings_off(self):
        from unittest import mock
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"")
            cb._git(_TMP, "status")
        cmd = run.call_args[0][0]
        for flag in ("core.fsmonitor=false", "--no-optional-locks", "protocol.allow=never"):
            self.assertIn(flag, cmd)
        self.assertTrue(any(c.startswith("core.hooksPath=") for c in cmd))

    def test_handoff_files_are_pruned_after_a_week(self):
        folder = tempfile.mkdtemp(prefix="ho-", dir=_TMP)
        old, new = os.path.join(folder, "old.md"), os.path.join(folder, "new.md")
        for p in (old, new):
            with open(p, "w", encoding="utf-8") as f:
                f.write("chat")
        os.utime(old, (time.time() - 9 * 86400,) * 2)
        cb.prune_handoffs(folder=folder)
        self.assertEqual(os.listdir(folder), ["new.md"])

    # -- key presses
    def test_enter_in_disguise_is_refused_and_short_titles_are_not_trusted(self):
        for spec in ("ctrl+m", "ctrl+j", "ctrl+shift+m"):
            with self.assertRaises(ValueError, msg=spec):
                cb.parse_keys(spec)
        self.assertEqual(cb.parse_keys("ctrl+k"), [0x11, 0x4B])
        self.assertEqual(cb.profile_for("AI Helper")["title"], "ai helper")   # "ai" alone would match far too many windows

    # -- the extension handshake
    def test_ping_proves_the_app_knows_the_pairing_code(self):
        import chatbridge_app
        import hmac as _hmac
        import urllib.request
        api = chatbridge_app.Api()
        port = api.start_capture_server()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping?nonce=abc123", timeout=5) as r:
                out = json.loads(r.read())
            self.assertEqual(out["proof"], _hmac.new(api._capture_token().encode(), b"abc123", "sha256").hexdigest())
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=5) as r:
                self.assertNotIn("proof", json.loads(r.read()))      # no nonce, no proof
            req = urllib.request.Request(f"http://127.0.0.1:{port}/capture", b"{}", {"X-ChatBridge-Token": "t\u00e9st"})
            try:
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                self.assertEqual(getattr(e, "code", None), 401)      # odd characters give a clean refusal, not a dead thread
        finally:
            api._capture_srv.shutdown()
            api._capture_srv.server_close()

    # -- the page bridge
    def test_file_numbers_from_the_page_are_validated(self):
        import chatbridge_app
        v = chatbridge_app.Api._valid_indices
        self.assertEqual(v([0, 2, 2, -1, 99, True, "1", 1.5, None], 3), [0, 2])
        self.assertEqual(v("not a list", 3), [])

    def test_the_page_has_a_content_security_policy(self):
        html = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html"), encoding="utf-8").read()
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("script-src 'self'", html)
        self.assertNotIn("'unsafe-inline'", html.split("script-src")[1].split(";")[0])   # no inline scripts, ever
        self.assertIn("connect-src 'self'", html)


class SearchWebExportTools(unittest.TestCase):
    def setUp(self):
        import chatbridge_app
        self.m = chatbridge_app
        self.api = chatbridge_app.Api()
        self.events = []
        self.api._emit = lambda state, msg="", **extra: self.events.append((state, msg, extra))

    def test_search_looks_inside_the_messages(self):
        r = self.api.add_text("Trip", "Test", "User: planning a Kyoto visit in April\nAssistant: Great, book temples early")
        self.api.add_text("Other", "Test", "User: tax questions")
        hits = self.api.search_chats("kyoto")["hits"]
        self.assertEqual(list(hits), [r["id"]])
        self.assertIn("Kyoto", hits[r["id"]])
        self.assertEqual(self.api.search_chats("k"), {"hits": {}})            # too short to be useful
        self.assertEqual(self.api.search_chats("zzzz-not-there")["hits"], {})

    def test_sending_to_a_website_copies_saves_a_file_and_opens_only_listed_sites(self):
        from unittest import mock
        copied, opened = [], []
        with mock.patch.object(self.m, "set_clipboard", copied.append), mock.patch("webbrowser.open", opened.append):
            self.api._deliver_web("web:1", "My chat", "THE HANDOFF TEXT")
            self.api._deliver_web("web:99", "x", "x")                          # not in the list
            self.api._deliver_web("web:abc", "x", "x")
        self.assertEqual(copied, ["THE HANDOFF TEXT"])
        self.assertEqual(opened, [self.m.WEB_TOOLS[1][1]])
        done = [e for e in self.events if e[0] == "done"][0]
        path = done[2]["file"]
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(open(path, encoding="utf-8").read().strip(), "THE HANDOFF TEXT")
        self.assertEqual([e[0] for e in self.events].count("error"), 2)
        for url in (u for _, u, _ in self.m.WEB_TOOLS):
            self.assertTrue(url.startswith("https://"), url)
        with mock.patch("subprocess.Popen") as popen:
            self.assertTrue(self.api.show_file(path).get("ok"))
            self.assertIn("error", self.api.show_file(r"C:\Windows\System32\cmd.exe"))   # only files we made
            self.assertEqual(popen.call_count, 1)
        os.remove(path)

    def test_a_website_you_open_yourself_copies_and_saves_but_opens_nothing(self):
        from unittest import mock
        copied, opened = [], []
        with mock.patch.object(self.m, "set_clipboard", copied.append), mock.patch("webbrowser.open", opened.append):
            self.api._deliver_web("web:none", "My chat", "TEXT")
        self.assertEqual((copied, opened), (["TEXT"], []))
        done = [e for e in self.events if e[0] == "done"][0]
        self.assertTrue(os.path.isfile(done[2]["file"]))
        os.remove(done[2]["file"])

    def test_automatic_options_hide_private_details_and_shorten_only_when_needed(self):
        short = self.api.add_text("Short", "Test", "User: hello\nAssistant: hi there")
        self.api._cfg.update({"scrub": True, "compact": False})
        convs = self.api._by_ids([short["id"]])
        opts, needed = self.api._resolve_opts(convs, 0, {"auto": True})
        self.assertEqual((opts, needed), ({"scrub": True, "compact": False}, False))
        big = "User: question\nAssistant: " + ("lots of words here " * 40000)
        long_ = self.api.add_text("Long", "Test", big)
        opts, needed = self.api._resolve_opts(self.api._by_ids([long_["id"]]), "copy", {"auto": True})
        self.assertTrue(opts["compact"] and needed)
        self.api._cfg["scrub"] = False
        self.assertFalse(self.api._resolve_opts(convs, "copy", {"auto": True})[0]["scrub"])
        self.api._cfg["scrub"] = True
        self.assertEqual(self.api._resolve_opts(convs, "copy", {"compact": True}), ({"compact": True}, False))   # explicit options pass through
        est = self.api.estimate([long_["id"]], "copy", {"auto": True})
        self.assertTrue(est["auto_compact"])

    def test_automatic_choices_are_not_saved_as_settings(self):
        from unittest import mock
        conv = self.api.add_text("Keep", "Test", "User: a\nAssistant: b")
        self.api._cfg.update({"scrub": False, "compact": False})
        with mock.patch.object(self.m.threading, "Thread"):
            self.api.send([conv["id"]], "copy", {"auto": True})
        self.assertEqual((self.api._cfg["scrub"], self.api._cfg["compact"]), (False, False))

    def test_first_start_of_the_friendly_look_switches_to_light_once(self):
        self.api._cfg.pop("ui_v2", None)
        self.api._cfg.update({"theme": "midnight", "font": "code"})
        s = self.api.bootstrap()["settings"]
        self.assertEqual((s["theme"], s["font"]), ("light", "sans"))
        self.api.save_settings({"autopaste": True, "theme": "nord", "font": "code", "size": 16})
        s = self.api.bootstrap()["settings"]                                   # the person's own choice sticks afterwards
        self.assertEqual((s["theme"], s["font"]), ("nord", "code"))

    # ---- sections and parts of a chat
    MIXED = [("user", "Fix my git setup on Windows, push is rejected"), ("assistant", "The error is about the private email. Use the noreply address."),
             ("user", "ok that worked, thanks"), ("assistant", "Great."),
             ("user", "Now let's write a resume for a nursing job posting at the hospital"), ("assistant", "Here is a draft ```text```"),
             ("user", "Make the summary shorter and mention ICU experience"), ("assistant", "Done: shortened."),
             ("user", "Also plan a trip to Kyoto in April with temples"), ("assistant", "Day 1 temples"),
             ("user", "Add food places near Gion"), ("assistant", "Sure: here are places.")]

    def _mixed(self):
        text = "\n".join(("User: " if r == "user" else "Assistant: ") + t for r, t in self.MIXED)
        cid = self.api.add_text("Mixed chat", "Test", text)["id"]
        self.addCleanup(lambda: self.api.delete_chats([c["id"] for c in list(self.api._lib)
                                                       if c["title"].startswith(("Mixed chat", "Part of: Mixed chat"))]))
        return cid

    def test_sections_split_a_chat_by_topic_and_cover_every_message_once(self):
        import chatbridge as cb
        msgs = [{"role": r, "content": t} for r, t in self.MIXED]
        secs = cb.split_sections(msgs)
        self.assertEqual([(s["start"], s["end"]) for s in secs], [(0, 4), (4, 8), (8, 12)])
        self.assertEqual(secs[1]["title"], "write a resume for a nursing job posting at the hospital".capitalize())
        self.assertIn("Code", secs[1]["tags"])
        self.assertEqual(cb.split_sections([]), [])
        one = cb.split_sections([{"role": "user", "content": "hi"}])
        self.assertEqual((one[0]["start"], one[0]["end"]), (0, 1))
        long_chat = [{"role": "user" if i % 2 == 0 else "assistant", "content": "same topic words repeated here " * 3} for i in range(80)]
        covered = sorted(i for s in cb.split_sections(long_chat) for i in range(s["start"], s["end"]))
        self.assertEqual(covered, list(range(80)))                                # long chats are still cut into manageable parts

    def test_make_part_keeps_only_the_ticked_messages_and_adds_an_outline(self):
        import chatbridge as cb
        cid = self._mixed()
        d = self.api.sections(cid)
        self.assertEqual(len(d["sections"]), 3)
        r = self.api.make_part(cid, [4, 5, 6, 7], {"1": "The resume"}, True)
        part = next(c for c in self.api._lib if c["id"] == r["id"])
        self.assertEqual(len(part["messages"]), 4)
        self.assertTrue(part["excerpt"])
        self.assertIn("2. ► The resume", part["summary"])
        self.assertIn("1.   Fix my git setup", part["summary"])
        text = cb.build_handoff(part, 0, "full", "")
        self.assertIn("<excerpt>", text)
        self.assertIn("adding it to the conversation we are already having", text)
        self.assertNotIn("Kyoto", text.split("</outline_of_the_full_conversation>")[1])     # unticked parts are not sent in full
        self.assertIn("error", self.api.make_part(cid, [], {}, True))
        self.assertIn("error", self.api.make_part(cid, ["x", -1, 999, True], {}, True))   # only real message numbers count
        self.assertNotIn("<outline", cb.build_handoff(self.api._by_ids([self.api.make_part(cid, [0], {}, False)["id"]])[0], 0, "full", ""))

    def test_a_part_survives_export_and_reimport_as_a_part(self):
        import chatbridge as cb
        cid = self._mixed()
        r = self.api.make_part(cid, [8, 9], {}, True)
        part = self.api._by_ids([r["id"]])[0]
        data = json.loads(self.api.export_text([part], "x.json", {}))
        back = cb.parse_json(data)[0]
        self.assertTrue(back.get("excerpt"))
        self.assertEqual(len(back["messages"]), 2)

    def test_old_parts_are_cleared_so_the_list_does_not_fill_up(self):
        cid = self._mixed()
        for _ in range(self.api.MAX_PARTS + 5):
            self.api.make_part(cid, [0, 1], {}, True)
        parts = [c for c in self.api._lib if c.get("excerpt")]
        self.assertEqual(len(parts), self.api.MAX_PARTS)
        self.assertTrue(any(c["id"] == cid for c in self.api._lib))           # the real conversation is never touched

    def test_problem_report_has_no_conversation_text_and_hides_private_details(self):
        from unittest import mock
        copied = []
        self.api.add_text("Secret plans", "Test", "User: my password is hunter2-ZZZ-unique\nAssistant: ok")
        with open(self.m.LOG_PATH, "a", encoding="utf-8") as f:
            f.write("2026-01-01 ERROR failed for sk-abcdefghijklmnopqrstuvwxyz0123456789 at C:\\Users\\%s\\x\n" % os.environ.get("USERNAME", "someone"))
        with mock.patch.object(self.m, "set_clipboard", copied.append):
            r = self.api.problem_report()
        self.assertTrue(r["ok"])
        text = copied[0]
        self.assertIn("ChatBridge " + self.m.VERSION, text)
        self.assertNotIn("hunter2-ZZZ-unique", text)
        self.assertNotIn("Secret plans", text)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz0123456789", text)

    def test_language_setting_is_remembered_and_bad_values_fall_back_to_automatic(self):
        base = {"autopaste": True, "theme": "light", "font": "sans", "size": 17}
        self.assertEqual(self.api.save_settings({**base, "language": "es"})["language"], "es")
        self.assertEqual(self.api.bootstrap()["settings"]["language"], "es")
        self.assertEqual(self.api.save_settings({**base, "language": "ja"})["language"], "ja")
        self.assertEqual(self.api.save_settings({**base, "language": "klingon"})["language"], "auto")     # only languages we have
        self.assertEqual(self.api.save_settings({**base, "language": "<script>"})["language"], "auto")
        self.api.save_settings({**base, "language": "auto"})

    def test_a_settings_file_saved_with_a_byte_order_mark_is_still_read(self):
        import chatbridge as cb
        path = os.path.join(os.environ["APPDATA"], "ChatBridge", "bom-test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig") as f:             # what Notepad and PowerShell's -Encoding UTF8 write
            f.write('{"language": "es", "welcomed": true}')
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertEqual(cb.load_json(path, {}), {"language": "es", "welcomed": True})
        self.assertEqual([n for n in os.listdir(os.path.dirname(path)) if n.startswith("bom-test.json.corrupt")], [])   # and not set aside

    def test_target_info_names_a_website(self):
        self.assertEqual(self.api._target_info("web:0")[0], "ChatGPT (website)")
        self.assertEqual(self.api._target_info("web:42"), (None, None))

    def test_choosing_tools_and_a_tool_installed_later(self):
        self.api._cfg.pop("enabled_tools", None)
        self.api._cfg.pop("known_tools", None)
        self.api._apps = [{"name": "Alpha", "kind": "Desktop app", "launch": None, "models": []},
                          {"name": "Beta", "kind": "Desktop app", "launch": None, "models": []}]
        self.assertTrue(all(a["enabled"] for a in self.api._apps_out()))           # nothing chosen yet: show all
        self.assertEqual([w["name"] for w in self.api._web_out() if w["enabled"]],
                         [n for n, _, on in self.m.WEB_TOOLS if on])                   # a few popular sites by default
        out = self.api.set_tools(["Alpha", "Claude.ai (website)", 5, None])
        self.assertEqual({a["name"]: a["enabled"] for a in out["apps"]}, {"Alpha": True, "Beta": False})
        self.assertEqual([w["name"] for w in out["web"] if w["enabled"]], ["Claude.ai (website)"])
        self.api._apps.append({"name": "Gamma", "kind": "Desktop app", "launch": None, "models": []})   # installed afterwards
        self.assertEqual({a["name"]: a["enabled"] for a in self.api._apps_out()}, {"Alpha": True, "Beta": False, "Gamma": True})
        self.assertTrue(self.api._cfg["tools_chosen"])

    def test_export_formats_and_roundtrip(self):
        key = "sk-" + "c" * 30
        r = self.api.add_text("Exported", "Test", f"User: my key is {key}\nAssistant: noted")
        convs = self.api._by_ids([r["id"]])
        md = self.api.export_text(convs, "x.md", {"scrub": True})
        self.assertIn("You are picking up", md)
        self.assertNotIn(key, md)
        js = self.api.export_text(convs, "x.json", {"scrub": True})
        self.assertNotIn(key, js)
        back = cb.parse_json(json.loads(js))                                   # a .json export can be imported again
        self.assertEqual((len(back), back[0]["title"], len(back[0]["messages"])), (1, "Exported", 2))


class FriendlyList(unittest.TestCase):
    def test_titles_read_like_names_not_paths(self):
        f = cb.friendly_title
        t = f('@"C:\\Users\\Jo\\Downloads\\Resume.pdf" update this resume for the job at https://jobs.example.com/posting/123456789')
        self.assertNotIn("C:\\", t)
        self.assertNotIn("https", t)
        self.assertTrue(t.startswith("Update this resume"))
        self.assertLessEqual(len(t), 66)
        self.assertEqual(f("Can you help me plan a trip? I like temples."), "Can you help me plan a trip?")
        self.assertEqual(f(""), "Untitled chat")
        self.assertEqual(f("hi"), "Hi")
        self.assertTrue(f("word " * 60).endswith("\u2026"))

    def test_hidden_markup_from_the_chatgpt_desktop_app_is_skipped(self):
        self.assertEqual(cb.friendly_title('<external_codex_apps_open_page>{"page_id":null}</external_codex_apps_open_page>'), "Untitled chat")
        self.assertEqual(cb.friendly_title("<environment_context><cwd>C:\\x</cwd></environment_context> how do I use agents?"),
                         "How do I use agents?")
        p = os.path.join(_TMP, "cx.jsonl")
        rows = [("developer", "<app-context>stuff</app-context>"), ("user", "<environment_context>\n<cwd>C:\\x</cwd>\n</environment_context>"),
                ("user", '<external_codex_apps_open_page>{"page_id":null}</external_codex_apps_open_page>'),
                ("user", "how do i get multi agents to work on a project?"), ("assistant", "Here is how.")]
        with open(p, "w", encoding="utf-8") as f:
            for role, text in rows:
                f.write(json.dumps({"type": "response_item", "payload": {"type": "message", "role": role,
                                                                       "content": [{"type": "input_text", "text": text}]}}) + "\n")
        c = cb.parse_codex(p)
        self.assertEqual([m["role"] for m in c["messages"]], ["user", "assistant"])      # only the real conversation
        self.assertEqual(c["title"], "How do i get multi agents to work on a project?")

    def test_claude_code_chats_get_friendly_titles(self):
        p = os.path.join(_TMP, "ft.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": '@"C:\\x\\a.pdf" please summarise this contract. It is long.'}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}) + "\n")
        self.assertEqual(cb.parse_claude_code(p)["title"], "Please summarise this contract")

    def test_rename_keeps_a_found_chat_without_listing_it_twice(self):
        import chatbridge_app
        api = chatbridge_app.Api()
        found = cb.new_conv("Original", "Claude Code", [{"role": "user", "content": "hello there"}])
        found["origin"] = r"C:\fake\session.jsonl"
        api._found = [found]
        before = len(api._chats())
        out = api.rename_chat(found["id"], "  My   better   name ")
        titles = [c["title"] for c in out["chats"]]
        self.assertIn("My better name", titles)
        self.assertEqual(len(out["chats"]), before)                    # same number of chats: no duplicate
        self.assertTrue(next(c for c in out["chats"] if c["id"] == found["id"])["saved"])
        self.assertIn("error", api.rename_chat(found["id"], "   "))
        self.assertIn("error", api.rename_chat("nope", "x"))


class InstallerSafety(unittest.TestCase):
    def setUp(self):
        import installer
        self.i = installer

    def test_install_folder_is_always_named_chatbridge(self):
        n = self.i.normalize_install_dir
        self.assertEqual(os.path.basename(n(r"D:\Games")), "ChatBridge")
        self.assertEqual(n(r"D:\Games\ChatBridge"), r"D:\Games\ChatBridge")
        self.assertEqual(n(r'"D:\Games\chatbridge\"').lower(), r"d:\games\chatbridge")
        self.assertEqual(n("C:\\"), "C:\\ChatBridge")

    def test_uninstall_only_touches_our_own_folder(self):
        safe = self.i.is_safe_install_dir
        parent = tempfile.mkdtemp(prefix="inst-", dir=_TMP)
        self.assertFalse(safe(parent))                                # not named ChatBridge
        self.assertFalse(safe("C:\\"))                                # a drive
        self.assertFalse(safe(os.path.expanduser("~")))               # the user's folder
        self.assertFalse(safe(os.path.join(os.path.expanduser("~"), "Downloads")))
        mine = os.path.join(parent, "ChatBridge")
        os.makedirs(mine)
        self.assertFalse(safe(mine))                                  # right name but not made by the installer
        with open(os.path.join(mine, ".chatbridge-install"), "w") as f:
            f.write("x")
        self.assertTrue(safe(mine))

    def test_refused_uninstall_deletes_nothing(self):
        stray = os.path.join(tempfile.mkdtemp(prefix="stray-", dir=_TMP), "ChatBridge")
        os.makedirs(stray)
        with open(os.path.join(stray, "my-important-file.txt"), "w") as f:
            f.write("keep me")
        self.assertFalse(self.i.do_uninstall(stray, remove_data=True))
        self.assertTrue(os.path.exists(os.path.join(stray, "my-important-file.txt")))

    def test_install_refuses_a_folder_that_already_holds_other_files(self):
        bundle = tempfile.mkdtemp(prefix="bundle-", dir=_TMP)
        import zipfile
        zipfile.ZipFile(os.path.join(bundle, "payload.zip"), "w").close()
        old_bundle, self.i.BUNDLE = self.i.BUNDLE, bundle
        try:
            target = os.path.join(tempfile.mkdtemp(prefix="foreign-", dir=_TMP), "ChatBridge")
            os.makedirs(target)
            with open(os.path.join(target, "photos.zip"), "w") as f:
                f.write("someone's files")
            with self.assertRaises(ValueError):
                self.i.do_install(target, desktop=False)
            self.assertTrue(os.path.exists(os.path.join(target, "photos.zip")))
        finally:
            self.i.BUNDLE = old_bundle


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
