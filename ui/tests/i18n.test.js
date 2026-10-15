// Checks the translation engine and the language files. Run:  node --test ui/tests/i18n.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const UI = path.join(__dirname, "..");
global.I18N = require(path.join(UI, "i18n.js"));
const CODES = ["es", "pt-BR", "fr", "de", "zh-CN", "ja"];
for (const c of CODES) require(path.join(UI, "lang", c + ".js"));
const P = I18N.packs;
const norm = s => s.replace(/\s+/g, " ").trim();
const holes = s => (s.match(/\{\w+\}/g) || []).sort().join(",");

test("every language has exactly the same entries", () => {
  const base = Object.keys(P.es).sort();
  assert.ok(base.length > 250, "expected a full set, got " + base.length);
  for (const c of CODES) assert.deepEqual(Object.keys(P[c]).sort(), base, c);
});

test("{placeholders} and html tags survive translation", () => {
  for (const c of CODES) for (const [k, v] of Object.entries(P[c])) {
    assert.equal(holes(v), holes(k), `${c}: ${k.slice(0, 50)}`);
    assert.ok(v.trim().length > 0, `${c}: empty ${k.slice(0, 50)}`);
    if (k.startsWith("html:")) assert.equal((v.match(/<\w+/g) || []).length, (P.es[k].match(/<\w+/g) || []).length, `${c}: ${k}`);
  }
});

test("language choice: settings first, then the system language", () => {
  assert.equal(I18N.pick("ja", "en-US"), "ja");
  assert.equal(I18N.pick("auto", "es-MX"), "es");
  assert.equal(I18N.pick(undefined, "pt-PT"), "pt-BR");
  assert.equal(I18N.pick("auto", "zh-TW"), "zh-CN");
  assert.equal(I18N.pick("auto", "fr-CA"), "fr");
  assert.equal(I18N.pick("auto", "de-AT"), "de");
  assert.equal(I18N.pick("auto", "it-IT"), "en");          // not translated yet: English
  assert.equal(I18N.pick("xx", "en-GB"), "en");
});

test("exact text, patterns, nesting, spacing and the dot separator", () => {
  I18N.use("es");
  assert.equal(I18N.tr("Settings"), "Ajustes");
  assert.equal(I18N.tr("  Settings \n"), "  Ajustes \n");                                       // spaces around are kept
  assert.equal(I18N.tr("Something nobody translated"), "Something nobody translated");           // unknown stays English
  assert.equal(I18N.tr("Showing 3 apps."), "Se muestran 3 apps.");
  assert.equal(I18N.tr("Pasted into Claude. Check it, then press Enter there to send."), "Pegado en Claude. Revísalo y pulsa Enter allí para enviarlo.");
  // a pattern that contains another translated phrase
  assert.equal(I18N.tr("ChatBridge copies this conversation and opens ChatGPT. Click its message box and press Ctrl+V."),
               "ChatBridge copia esta conversación y abre ChatGPT. Haz clic en su cuadro de mensaje y pulsa Ctrl+V.");
  assert.match(I18N.tr("ChatBridge copies these 3 conversations. Paste it anywhere with Ctrl+V."), /estas 3 conversaciones/);
  assert.equal(I18N.tr("3 days ago · Claude Code"), "hace 3 días · Claude Code");
  assert.equal(I18N.tr("Code project · 40 messages"), "Proyecto de código · 40 mensajes");
  assert.equal(I18N.tr("Sending 2 of 12 messages"), "Se enviarán 2 de 12 mensajes");
  assert.equal(I18N.tr("Sending 2 of ? messages"), "Se enviarán 2 de ? mensajes");
});

test("number-only placeholders can't mangle unrelated sentences", () => {
  I18N.use("de");
  for (const s of ["This is part of it", "Went through 3 of the files", "The state of things", "Version", "We saw 3 days ago and more"]) {
    assert.equal(I18N.tr(s), s, s);                                  // "X of Y" and "N days ago" only match real numbers in the right place
  }
  assert.equal(I18N.tr("Version 1.3.0"), "Version 1.3.0");
  assert.equal(I18N.tr("Update available: 1.3.0"), "Update verfügbar: 1.3.0");
});

test("English mode changes nothing", () => {
  I18N.use("en");
  assert.equal(I18N.tr("Settings"), "Settings");
});

/* every fixed piece of text in the page must have a translation, so a new button can't be forgotten */
function pageStrings() {
  let html = fs.readFileSync(path.join(UI, "index.html"), "utf8");
  html = html.replace(/<!--[\s\S]*?-->/g, "").replace(/<script[\s\S]*?<\/script>/g, "").replace(/<style[\s\S]*?<\/style>/g, "");
  const out = new Set();
  html = html.replace(/<([a-z0-9]+)([^>]*?)data-i18n-html="[^"]*"[^>]*>[\s\S]*?<\/\1>/g, "");        // translated whole under html:… keys
  for (const m of html.matchAll(/\b(?:title|placeholder|aria-label)="([^"]+)"/g)) out.add(norm(m[1]));
  for (const m of html.replace(/<[^>]+>/g, "\u0000").split("\u0000")) { const t = norm(m.replace(/&[a-z]+;/g, " ")); if (t) out.add(t); }
  return [...out];
}
const NOT_TEXT = new Set(["ChatBridge", "⇄", "×", "–", "Pasted chat", "Pasted text", "Chat"]);        // names and symbols

test("every fixed text in index.html has a translation", () => {
  const missing = pageStrings().filter(s => !NOT_TEXT.has(s) && P.es[s] === undefined && !/^[\W\d_]+$/.test(s));
  assert.deepEqual(missing, []);
});

test("every data-i18n-html paragraph has a translation in every language", () => {
  const html = fs.readFileSync(path.join(UI, "index.html"), "utf8");
  const ids = [...html.matchAll(/data-i18n-html="([^"]+)"/g)].map(m => m[1]);
  assert.ok(ids.length >= 6);
  for (const c of CODES) for (const id of ids) assert.ok(P[c]["html:" + id], `${c} html:${id}`);
});
