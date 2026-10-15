// Checks the phone's language files. Run:  node --test mobile/tests/i18n.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const WWW = path.join(__dirname, "..", "www");
const UI = path.join(__dirname, "..", "..", "ui");
global.I18N = require(path.join(WWW, "i18n.js"));
const CODES = ["es", "pt-BR", "fr", "de", "zh-CN", "ja"];
for (const c of CODES) require(path.join(WWW, "lang", c + ".js"));
const P = I18N.packs;
const norm = s => s.replace(/\s+/g, " ").trim();

test("the phone uses exactly the same translation engine as Windows", () => {
  assert.equal(fs.readFileSync(path.join(WWW, "i18n.js"), "utf8"), fs.readFileSync(path.join(UI, "i18n.js"), "utf8"));
});

test("every language has the same entries, and they are all filled in", () => {
  const base = Object.keys(P.es).sort();
  assert.ok(base.length > 300);
  for (const c of CODES) { assert.deepEqual(Object.keys(P[c]).sort(), base, c); for (const [k, v] of Object.entries(P[c])) assert.ok(v.trim(), c + ": " + k.slice(0, 40)); }
});

function pageStrings() {
  let html = fs.readFileSync(path.join(WWW, "index.html"), "utf8");
  html = html.replace(/<!--[\s\S]*?-->/g, "").replace(/<script[\s\S]*?<\/script>/g, "").replace(/<style[\s\S]*?<\/style>/g, "");
  html = html.replace(/<([a-z0-9]+)([^>]*?)data-i18n-html="[^"]*"[^>]*>[\s\S]*?<\/\1>/g, "");
  const out = new Set();
  for (const m of html.matchAll(/\b(?:title|placeholder|aria-label)="([^"]+)"/g)) out.add(norm(m[1]));
  for (const m of html.replace(/<[^>]+>/g, "\u0000").split("\u0000")) { const t = norm(m.replace(/&[a-z]+;/g, " ")); if (t) out.add(t); }
  return [...out];
}
const NOT_TEXT = new Set(["ChatBridge", "⇄", "‹", "?", "◐", "ChatGPT", "Claude", "Gemini", "Copilot"]);       // names and symbols

test("every fixed text on the phone screen has a translation", () => {
  const missing = pageStrings().filter(s => !NOT_TEXT.has(s) && P.es[s] === undefined && !/^[\W\d_]+$/.test(s));
  assert.deepEqual(missing, []);
});

test("every translated paragraph on the phone screen exists in every language", () => {
  const html = fs.readFileSync(path.join(WWW, "index.html"), "utf8");
  const ids = [...html.matchAll(/data-i18n-html="([^"]+)"/g)].map(m => m[1]);
  assert.ok(ids.length >= 4);
  for (const c of CODES) for (const id of ids) assert.ok(P[c]["html:" + id], `${c} html:${id}`);
});

test("messages the phone builds are translated", () => {
  I18N.use("fr");
  assert.equal(I18N.tr("Copied. Paste it into the message box of any AI app."), "Copié. Collez-le dans la zone de message de n’importe quelle application d’IA.");
  assert.equal(I18N.tr("Sending 2 of 10 messages"), "Envoi de 2 messages sur 10");
  assert.equal(I18N.tr("Oct 14 · Claude Code · 10 messages"), "Oct 14 · Claude Code · 10 messages".replace("10 messages", "10 messages"));
  I18N.use("ja");
  assert.equal(I18N.tr("Share to an app…"), "アプリに共有…");
});
