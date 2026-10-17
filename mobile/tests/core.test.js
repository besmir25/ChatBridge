// Checks core.js against what the Python engine answers (golden.json), plus a few phone-specific behaviours.
// Run:  node --test mobile/tests
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../www/core.js");
const G = JSON.parse(fs.readFileSync(path.join(__dirname, "golden.json"), "utf8"));

test("estimateTokens matches Python", () => { for (const c of G.estimate_tokens) assert.equal(C.estimateTokens(c.in), c.out, JSON.stringify(c.in)); });

test("scrubText matches Python (text and counts)", () => {
  for (const c of G.scrub_text) {
    const r = C.scrubText(c.in);
    assert.equal(r.text, c.out[0], JSON.stringify(c.in));
    assert.deepEqual(r.counts, c.out[1], JSON.stringify(c.in));
  }
});

test("compactText and compactMessages match Python", () => {
  for (const c of G.compact_text) assert.equal(C.compactText(c.in), c.out);
  for (const c of G.compact_messages) assert.deepEqual(C.compactMessages(c.in, c.aggressive), c.out);
});

test("friendlyTitle matches Python", () => { for (const c of G.friendly_title) assert.equal(C.friendlyTitle(c.in), c.out, JSON.stringify(c.in)); });

test("parseText matches Python", () => { for (const c of G.parse_text) assert.deepEqual(C.parseText(c.in).messages, c.out, JSON.stringify(c.in)); });

test("splitSections matches Python", () => { G.split_sections.forEach((c, i) => assert.deepEqual(C.splitSections(c.in), c.out, "case " + i)); });

test("chatOutline matches Python", () => {
  for (const c of G.chat_outline) {
    const secs = C.splitSections(c.messages);
    assert.equal(C.chatOutline(c.title, c.messages, secs, new Set(c.included)), c.out);
  }
});

test("buildHandoff matches Python (whole chat and excerpt)", () => { for (const c of G.build_handoff) assert.equal(C.buildHandoff(c.conv, c.extra, c.about), c.out); });

test("parseJson reads the same files as Python (ChatGPT, Claude, generic, ChatBridge)", () => {
  G.parse_json.forEach((c, i) => {
    const got = C.parseJson(c.in).map(x => { const o = {title: x.title, source: x.source, messages: x.messages}; if (x.excerpt) { o.excerpt = true; o.summary = x.summary; } return o; });
    assert.deepEqual(got, c.out, "case " + i);
  });
});

test("parseJson survives hostile input", () => {
  const loop = {mapping: {a: {parent: "b", message: {author: {role: "user"}, content: {parts: ["x"]}}}, b: {parent: "a", message: {author: {role: "assistant"}, content: {parts: ["y"]}}}}, current_node: "a"};
  assert.equal(C.parseJson(loop)[0].messages.length, 2);                         // a loop in the tree can't hang it
  assert.deepEqual(C.parseJson(null), []);
  assert.deepEqual(C.parseJson({messages: [null, 5, {content: 7}, {content: "ok"}]}).map(c => c.messages.length), [1]);
  const big = C.parseJson({title: "t".repeat(500), source: "s".repeat(500), messages: [{role: "user", content: "x".repeat(300000)}]})[0];
  assert.ok(big.title.length <= 120 && big.source.length <= 40 && big.messages[0].content.length <= 200000);
});

const MIXED = G.split_sections[0].in;

test("makePart keeps only ticked messages, ignores bad numbers, names sections", () => {
  const conv = {title: "Mixed chat", source: "Claude Code", messages: MIXED};
  const r = C.makePart(conv, [4, 5, 6, 7, 6, -1, 99, "x", 4.5], {1: "The resume"}, true);
  assert.equal(r.part.messages.length, 4);
  assert.ok(r.part.excerpt);
  assert.match(r.part.summary, /2\. ► The resume/);
  assert.match(r.part.summary, /1\.   Fix my git setup/);
  assert.ok(C.makePart(conv, [], {}, true).error);
  assert.ok(C.makePart(conv, ["x", -1, 999], {}, true).error);
  assert.equal(C.makePart(conv, [0], {}, false).part.summary, "");
  const text = C.buildHandoff(r.part);
  assert.ok(!text.split("</outline_of_the_full_conversation>")[1].includes("Kyoto"));      // unticked parts are not sent in full
});

test("prepare hides private details and can shorten, without touching the original", () => {
  const conv = {title: "t", source: "s", messages: [{role: "user", content: "mail me at a.b@example.com key sk-abcdefghijklmnopqrstuvwxyz0123456789"}]};
  const r = C.prepare(conv, {scrub: true});
  assert.match(r.conv.messages[0].content, /\[email\]/);
  assert.match(r.conv.messages[0].content, /\[key removed\]/);
  assert.equal(r.counts.emails, 1);
  assert.match(conv.messages[0].content, /example\.com/);                                     // original unchanged
  assert.match(C.prepare(conv, {scrub: false}).conv.messages[0].content, /example\.com/);
});

test("very long input stays fast", () => {
  const big = Array.from({length: 4000}, (_, i) => ({role: i % 2 ? "assistant" : "user", content: "word ".repeat(200) + i}));
  const t = Date.now();
  C.splitSections(big); C.prepare({title: "x", source: "y", messages: big}, {scrub: true, compact: true});
  assert.ok(Date.now() - t < 5000, "took " + (Date.now() - t) + " ms");
});

test("prepare also hides private details quoted in the outline", () => {
  const conv = {title: "t", source: "s", excerpt: true, summary: "1. mail jane@example.com", messages: [{role: "user", content: "hi"}]};
  assert.match(C.prepare(conv, {scrub: true}).conv.summary, /\[email\]/);
});

test("unzipText reads zips made by Python (deflated, stored, nested, unicode) and skips what it should", async () => {
  for (const z of G.zips) {
    const buf = Buffer.from(z.b64, "base64");
    const got = await C.unzipText(buf, name => /(^|\/)conversations\.json$/.test(name));
    assert.deepEqual(Object.fromEntries(got.map(f => [f.name, f.text])), z.files, z.name);
  }
  const all = await C.unzipText(Buffer.from(G.zips[0].b64, "base64"), () => true);
  assert.deepEqual(all.map(f => f.name).sort(), ["conversations.json", "img/a.png", "user.json"]);   // folders are not files
  assert.deepEqual(await C.unzipText(Buffer.from(G.zips[0].b64, "base64"), () => false), []);
});

test("a zip export goes all the way to conversations", async () => {
  const z = G.zips[0];
  const files = await C.unzipText(Buffer.from(z.b64, "base64"), n => /conversations\.json$/.test(n));
  const convs = C.parseJson(JSON.parse(files[0].text));
  assert.equal(convs.length, 1);
  assert.equal(convs[0].messages[0].content, "hello from a zip");
});

test("unzipText refuses broken, truncated and hostile files without hanging", async () => {
  const good = Buffer.from(G.zips[0].b64, "base64");
  await assert.rejects(() => C.unzipText(Buffer.from("this is not a zip file at all"), () => true), /zip-bad/);
  await assert.rejects(() => C.unzipText(good.subarray(0, good.length - 30), () => true), /zip-bad/);          // cut off
  await assert.rejects(() => C.unzipText(Buffer.alloc(0), () => true), /zip-bad/);
  const lie = Buffer.from(good);                                                                              // claims a huge unpacked size
  const cd = lie.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02]));
  lie.writeUInt32LE(0x7fffffff, cd + 24);
  await assert.rejects(() => C.unzipText(lie, () => true), /zip-too-big/);
  const bomb = Buffer.from(good);                                                                             // directory points outside the file
  bomb.writeUInt32LE(0x00ffffff, bomb.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02])) + 42);
  await assert.rejects(() => C.unzipText(bomb, () => true), /zip-bad/);
});

test("isOnlyALink tells a shared link from shared text", () => {
  assert.ok(C.isOnlyALink("https://chatgpt.com/share/abc-123"));
  assert.ok(C.isOnlyALink("  https://claude.ai/chat/xyz \n"));
  assert.ok(!C.isOnlyALink("User: see https://example.com for details\nAssistant: ok"));
  assert.ok(!C.isOnlyALink("hello"));
  assert.ok(!C.isOnlyALink(""));
});
