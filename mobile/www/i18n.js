/* Translations for ChatBridge. The English in the page is the fallback; a language "pack" (lang/xx.js) maps English text to its translation:
     I18N.packs["es"] = { "Settings": "Ajustes", "Showing {n} apps.": "Mostrando {n} apps." };
   Keys with {name} are patterns: the matching parts are filled into the translation (and translated themselves if they have an entry).
   After init() everything that appears on the page is translated: the fixed text, and text the app adds later (a MutationObserver).
   Text inside translate="no" (chat titles, messages, file names) is never touched. Anything without an entry stays English.
   init(lang, {swaps: [["Ctrl+V", "Cmd+V"]]}) also swaps words after translating, in every language including English (macOS key names).
   Used by both the Windows screen (ui/) and the phone screen (mobile/www/); mobile/www/i18n.js must be an identical copy. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.I18N = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const NAMES = {en: "English", es: "Español", "pt-BR": "Português (Brasil)", fr: "Français", de: "Deutsch", "zh-CN": "简体中文", ja: "日本語"};
  const packs = {};
  let dict = {}, patterns = [], active = "en", observer = null, swaps = [];
  const cache = new Map();
  const NUMERIC = new Set(["n", "total", "on", "a", "c", "tokens"]);   // these placeholders only ever match numbers

  const norm = s => s.replace(/\s+/g, " ").trim();
  const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  /* "auto" (or nothing) means: follow the system language */
  function pick(pref, navLang) {
    if (pref && pref !== "auto" && NAMES[pref]) return pref;
    const l = String(navLang || (typeof navigator !== "undefined" && navigator.language) || "en").toLowerCase();
    if (l.startsWith("zh")) return "zh-CN";
    if (l.startsWith("pt")) return "pt-BR";
    for (const c of ["es", "fr", "de", "ja"]) if (l.startsWith(c)) return c;
    return "en";
  }

  function compile(pack) {
    dict = {}; patterns = []; cache.clear();
    for (const [k, v] of Object.entries(pack || {})) {
      const key = norm(k);
      if (/\{\w+\}/.test(key)) {
        let literal = 0;
        const source = reEsc(key).replace(/\\\{(\w+)\\\}/g, (m, name) => "(?<" + name + ">" + (name === "total" ? "\\d[\\d,.]*|\\?" : NUMERIC.has(name) ? "\\d[\\d,.]*" : name === "v" ? "[\\w.\\-]+" : ".+?") + ")");
        literal = key.replace(/\{\w+\}/g, "").length;
        patterns.push({re: new RegExp("^" + source + "$"), tpl: v, literal});
      } else dict[key] = v;
    }
    patterns.sort((a, b) => b.literal - a.literal);          // the most specific pattern wins
  }

  function trCore(core) {
    const key = norm(core);
    if (cache.has(key)) return cache.get(key);
    let out = null;
    if (dict[key] !== undefined) out = dict[key];
    if (out === null) {
      for (const p of patterns) {
        const m = p.re.exec(key);
        if (m) { out = p.tpl.replace(/\{(\w+)\}/g, (x, n) => (m.groups && m.groups[n] !== undefined ? trCore(m.groups[n]) : x)); break; }
      }
    }
    if (out === null && key.includes(" · ")) {                // "3 days ago · Claude Code": translate each piece
      const parts = key.split(" · "), t = parts.map(trCore);
      if (t.some((x, i) => x !== parts[i])) out = t.join(" · ");
    }
    if (out === null) out = core;
    cache.set(key, out);
    return out;
  }

  const swap = s => { for (const [a, b] of swaps) s = s.split(a).join(b); return s; };

  /* translate a string, keeping its leading and trailing spaces */
  function tr(text) {
    if ((active === "en" && !swaps.length) || typeof text !== "string") return text;
    const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(text);
    if (!m || !m[2]) return text;
    const out = swap(active === "en" ? m[2] : trCore(m[2]));
    return out === m[2] ? text : m[1] + out + m[3];
  }

  /* ---------- the page ---------- */
  const ATTRS = ["title", "placeholder", "aria-label"];
  const noTr = node => { const el = node.nodeType === 1 ? node : node.parentElement; return !!(el && el.closest && el.closest('[translate="no"],script,style,textarea')); };
  function fixText(n) {
    if (n.__t === n.nodeValue || noTr(n)) return;
    const v = tr(n.nodeValue);
    if (v !== n.nodeValue) n.nodeValue = v;
    n.__t = n.nodeValue;
  }
  function fixAttr(el, name) {
    if (!el.getAttribute || (el.closest && el.closest('[translate="no"]'))) return;    // (a text box's own placeholder is ours to translate)
    const cur = el.getAttribute(name);
    if (cur) { const v = tr(cur); if (v !== cur) el.setAttribute(name, v); }
  }
  function walk(node) {
    if (node.nodeType === 3) return fixText(node);
    if (node.nodeType !== 1) return;
    const w = document.createTreeWalker(node, 4);           // text nodes
    for (let n = w.nextNode(); n; n = w.nextNode()) fixText(n);
    const els = [node, ...node.querySelectorAll("[title],[placeholder],[aria-label]")];
    for (const el of els) for (const a of ATTRS) if (el.hasAttribute && el.hasAttribute(a)) fixAttr(el, a);
  }
  function setHtml() {                                     // paragraphs with bold parts are translated as a whole: <p data-i18n-html="help.step1">
    for (const el of document.querySelectorAll("[data-i18n-html]")) {
      const v = dict["html:" + el.dataset.i18nHtml];
      if (v !== undefined) el.innerHTML = swap(v);
    }
  }

  function init(pref, opts) {
    active = pick(pref);
    swaps = (opts && Array.isArray(opts.swaps) ? opts.swaps : []).filter(s => Array.isArray(s) && s.length === 2 && s[0]);
    document.documentElement.lang = active;
    if (active === "en" && !swaps.length) return active;
    compile(active === "en" ? {} : packs[active]);
    setHtml();
    walk(document.body);
    if (!observer && typeof MutationObserver !== "undefined") {
      observer = new MutationObserver(records => {
        for (const r of records) {
          if (r.type === "childList") r.addedNodes.forEach(walk);
          else if (r.type === "characterData") fixText(r.target);
          else if (r.type === "attributes") fixAttr(r.target, r.attributeName);
        }
      });
      observer.observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS});
    }
    return active;
  }

  /* for tests and for code that needs a translated string right now */
  function use(code, opts) { active = code; swaps = (opts && opts.swaps) || []; compile(packs[code]); return active; }
  return {NAMES, packs, init, pick, tr, use, get lang() { return active; }};
});
