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
