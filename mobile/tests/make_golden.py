"""Records what the Python engine answers for a set of inputs, so core.js can be checked against it.
Run from the project root:  python mobile/tests/make_golden.py   (rewrites mobile/tests/golden.json)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import chatbridge as cb


def M(role, text):
    return {"role": role, "content": text}


MIXED = [M("user", "Fix my git setup on Windows, push is rejected"), M("assistant", "The error is about the private email. Use the noreply address."),
         M("user", "ok that worked, thanks"), M("assistant", "Great."),
         M("user", "Now let's write a resume for a nursing job posting at the hospital"), M("assistant", "Here is a draft ```text```"),
         M("user", "Make the summary shorter and mention ICU experience"), M("assistant", "Done: shortened."),
         M("user", "Also plan a trip to Kyoto in April with temples"), M("assistant", "Day 1 temples, we'll use the train pass"),
         M("user", "Add food places near Gion"), M("assistant", "Sure: here are places.")]
LONG = [M("user" if i % 2 == 0 else "assistant", "same topic words repeated here " * 3) for i in range(80)]
REPLY_FIRST = [M("assistant", "Welcome back"), M("user", "Different question: how do mortgage rates work in the United States?"), M("assistant", "They depend on the lender, the term and your credit.")]
SHIFTS = [M("user", "Please review the database schema for the orders table carefully"), M("assistant", "The schema looks fine, but add an index on customer_id."),
          M("user", "Add the index and show the migration script"), M("assistant", "```sql\nCREATE INDEX idx ON orders(customer_id);\n```"),
          M("user", "Switching topics: draft an email to the landlord about the broken heater in apartment 4B"), M("assistant", "Subject: Heater repair needed. Hello, the heater is broken."),
          M("user", "Make it more polite and mention the lease clause"), M("assistant", "Sure, here is a politer version."),
          M("user", "btw what is a good name for the cat we adopted last week? she is orange"), M("assistant", "Marmalade, Ginger or Clementine.")]

TEXTS_TOKENS = ["", "hello world", "The quick brown fox jumps over 13 lazy dogs!", "def f(x): return x**2  # 1234567890", "caf\u00e9 na\u00efve \u4f60\u597d", "a" * 100]
TEXTS_SCRUB = [
    "my key is sk-abcdefghijklmnopqrstuvwxyz0123456789 ok",
    "email me at jane.doe@example.com or call (415) 555-0172 please",
    "OPENAI_API_KEY=abcdefghijk123456 and password: \"correct horse battery\" and token = 'short'",
    "path C:\\Users\\Besmir\\Documents\\x and C:/Users/Jane/file and C:\\\\Users\\\\Bob\\\\y",
    "postgres://admin:s3cretpass@db.example.com/prod",
    "-----BEGIN RSA PRIVATE KEY----- abc ghp_" + "a" * 36,
    "nothing private here, just words", ""]
CODE = "intro\n```python\n" + "\n".join(f"line {i}" for i in range(100)) + "\n```\nafter\n\n\n\n\x1b[31mred\x1b[0m   \nend"
BIG = "\n".join(f"row {i}" for i in range(500))
TITLES = ["Update my resume for a job posting. Then more.", "@file.py fix <environment_context>hidden</environment_context> the bug in https://github.com/x/y/issues/12 please",
          "ok", "", "A very long first message that keeps going and going without any sentence ending so that it must be cut at the limit somewhere",
          "<tag>only markup</tag>", "Hello! How are you today my friend? I am fine."]
PASTES = ["User: hi there\nAssistant: hello!\nUser: what is 2+2?\nAssistant: 4",
          "You said:\nWhat is the capital of France?\nChatGPT said:\nParis.",
          "## User\nhello\n## Assistant\nhi there\n\nmore",
          "just a block of text with no labels", "Human: first\r\nClaude: second\r\nHuman: third", "   ", "Me: one\nBot: two"]

golden = {
    "estimate_tokens": [{"in": t, "out": cb.estimate_tokens(t)} for t in TEXTS_TOKENS],
    "scrub_text": [{"in": t, "out": list(cb.scrub_text(t))} for t in TEXTS_SCRUB],
    "compact_text": [{"in": t, "out": cb.compact_text(t)} for t in (CODE, BIG)],
    "compact_messages": [{"in": [M("user", CODE), M("user", CODE), M("assistant", "x" * 3000)], "aggressive": a,
                          "out": cb.compact_messages([M("user", CODE), M("user", CODE), M("assistant", "x" * 3000)], a)} for a in (False, True)],
    "friendly_title": [{"in": t, "out": cb.friendly_title(t)} for t in TITLES],
    "parse_text": [{"in": t, "out": cb.parse_text(t)["messages"]} for t in PASTES],
    "split_sections": [{"in": c, "out": cb.split_sections(c)} for c in (MIXED, LONG, REPLY_FIRST, SHIFTS, [M("user", "hi")], [])],
}
secs = cb.split_sections(MIXED)
golden["chat_outline"] = [{"title": "Mixed chat", "messages": MIXED, "included": inc, "out": cb.chat_outline("Mixed chat", MIXED, secs, set(inc))}
                          for inc in ([4, 5, 6, 7], [0], [])]
conv = {"title": "Mixed chat", "source": "Claude Code", "summary": "", "messages": MIXED}
part = {"title": "Part of: Mixed chat", "source": "Claude Code", "excerpt": True,
        "summary": cb.chat_outline("Mixed chat", MIXED, secs, {4, 5, 6, 7}), "messages": MIXED[4:8]}
golden["build_handoff"] = [
    {"conv": conv, "extra": "", "about": "", "out": cb.build_handoff(conv, 0, "full", "", "")},
    {"conv": conv, "extra": "Keep answers short.", "about": "I am a nurse.", "out": cb.build_handoff(conv, 0, "full", "Keep answers short.", "I am a nurse.")},
    {"conv": part, "extra": "", "about": "", "out": cb.build_handoff(part, 0, "full", "", "")},
    {"conv": part, "extra": "Be brief.", "about": "Background", "out": cb.build_handoff(part, 0, "full", "Be brief.", "Background")},
]
with open(os.path.join(HERE, "golden.json"), "w", encoding="utf-8") as f:
    json.dump(golden, f, ensure_ascii=False, indent=1)
print("wrote golden.json:", {k: len(v) for k, v in golden.items()})
