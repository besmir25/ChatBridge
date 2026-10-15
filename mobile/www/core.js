/* ChatBridge core for phones: the same logic as chatbridge.py, in plain JavaScript (no libraries, no network).
   Works in a browser/WebView (window.ChatCore) and in Node (require). tests/golden.json holds Python's answers for the
   same inputs, so the two versions are checked against each other. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ChatCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* ---------- small helpers ---------- */
  const stripChars = (s, chars) => {                 // Python's str.strip(chars)
    let a = 0, b = s.length;
    while (a < b && chars.includes(s[a])) a++;
    while (b > a && chars.includes(s[b - 1])) b--;
    return s.slice(a, b);
  };
  const label = role => ({user: "User", assistant: "Assistant", system: "System"}[role] || (role.charAt(0).toUpperCase() + role.slice(1).toLowerCase()));
  const normRole = r => {
    r = String(r).toLowerCase();
    if (["user", "human", "you", "me"].includes(r)) return "user";
    return r === "system" ? "system" : "assistant";
  };

  /* ---------- size ---------- */
  const TOKEN_PIECE = /[A-Za-z]+|\d+|[^\sA-Za-z\d]/g;
  function estimateTokens(text) {
    let n = 0;
    for (const m of String(text || "").matchAll(TOKEN_PIECE)) {
      const t = m[0];
      n += /[A-Za-z]/.test(t[0]) ? Math.floor((t.length + 5) / 6) : /\d/.test(t[0]) ? Math.floor((t.length + 2) / 3) : 1;
    }
    return n;
  }

  /* ---------- privacy ---------- */
  const SECRET_TEXT = new RegExp(
    "(sk-[A-Za-z0-9_-]{20,}|sk_(?:live|test)_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}" +
    "|npm_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|SG\\.[A-Za-z0-9_-]{16,}\\.[A-Za-z0-9_-]{16,}" +
    "|eyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}" +
    "|[a-z][a-z0-9+.-]{1,20}://[^\\s:/@'\"]{1,64}:[^\\s@/'\"]{3,128}@" +
    "|AccountKey=[A-Za-z0-9+/=]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)", "g");
  const EMAIL = /(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+/g;
  const PHONE = /(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)/g;
  const USER_PATH = /(C:(?:\\{1,4}|\/)Users(?:\\{1,4}|\/))[^\\/\s"'<>|]+/gi;
  const KEY_ASSIGN = /([\w.-]{0,40}(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth)[\w.-]{0,40})(\s*[:=]\s*)(?:"[^"\n]{4,200}"|'[^'\n]{4,200}'|[^\s"']{8,})/gi;

  function scrubText(text, secrets = true, personal = true) {
    const counts = {keys: 0, emails: 0, phones: 0, paths: 0};
    const sub = (rx, repl, key, s) => s.replace(rx, (...a) => { counts[key]++; return typeof repl === "function" ? repl(...a) : repl; });
    text = String(text || "");
    if (secrets) {
      text = sub(SECRET_TEXT, "[key removed]", "keys", text);
      text = sub(KEY_ASSIGN, (m, a, b) => a + b + "[removed]", "keys", text);
    }
    if (personal) {
      text = sub(EMAIL, "[email]", "emails", text);
      text = sub(PHONE, "[phone]", "phones", text);
      text = sub(USER_PATH, (m, a) => a + "<user>", "paths", text);
    }
    return {text, counts};
  }

  /* ---------- shortening long text ---------- */
  const ANSI = /\x1b\[[0-9;]*[A-Za-z]/g;
  function compactText(text, maxBlock = 60, maxMessage = 200) {
    text = String(text).replace(ANSI, "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
    const squeeze = (lines, cap) => {
      if (lines.length <= cap) return lines;
      const head = Math.floor(cap * 0.65), tail = Math.floor(cap * 0.25);
      return lines.slice(0, head).concat([`[... ${lines.length - head - tail} lines omitted ...]`], lines.slice(lines.length - tail));
    };
    text = text.replace(/(```[^\n]*\n)([\s\S]*?)(\n```)/g, (m, a, body, c) => a + squeeze(body.split("\n"), maxBlock).join("\n") + c);
    return squeeze(text.split("\n"), maxMessage).join("\n");
  }
  function compactMessages(msgs, aggressive = false) {
    const out = [];
    let prev = null;
    for (const m of msgs) {
      let c = compactText(m.content, aggressive ? 30 : 60, aggressive ? 120 : 200);
      if (aggressive && c.length > 2500) c = c.slice(0, 1700) + `\n[... ${(c.length - 2200).toLocaleString("en-US")} characters omitted ...]\n` + c.slice(-500);
      if (prev && prev.role === m.role && prev.content === c) continue;   // exact repeat
      prev = {role: m.role, content: c};
      out.push(prev);
    }
    return out;
  }

  /* ---------- readable titles ---------- */
  const AT_MENTION = /@"[^"]*"|@\S+/g;
  const URL_IN_TEXT = /https?:\/\/([^\s/?#]+)\S*/g;
  function stripTags(text) {
    text = String(text || "").replace(/<([A-Za-z_][\w:.-]*)(?:\s[^>]*)?>[\s\S]*?<\/\1>/g, " ");
    return text.replace(/<\/?[A-Za-z_][\w:.-]*(?:\s[^>]*)?\/?>/g, " ");
  }
  function friendlyTitle(text, limit = 64, fallback = "Untitled chat") {
    let t = stripTags(String(text || "").replace(AT_MENTION, " "));
    t = t.replace(URL_IN_TEXT, (m, host) => host);
    t = stripChars(t.replace(/\s+/g, " "), " .,:;-—");
    const first = stripChars(t.split(/(?<=[.!?])\s/)[0], " .");
    if (first.length >= 12) t = first;
    if (t.length > limit) {
      const head = t.slice(0, limit), i = head.lastIndexOf(" ");
      t = stripChars(i > 0 ? head.slice(0, i) : head, " .,;:-").replace(/[ .,;:-]+$/, "") + "…";
    }
    return t ? t.charAt(0).toUpperCase() + t.slice(1) : fallback;
  }

  /* ---------- turning pasted or shared text into a conversation ---------- */
  const LABEL = "you said|chatgpt said|claude said|gemini said|copilot said|user|you|human|me|assistant|claude|chatgpt|gpt-?\\d*|ai|gemini|copilot|model|system|bot";
  const RE_COLON = new RegExp("^\\s*(?:#{1,6}\\s*)?\\**(" + LABEL + ")\\**\\s*:\\s*\\**\\s*(.*)$", "i");
  const RE_SAID = new RegExp("^\\s*(?:#{1,6}\\s*)?\\**((?:you|chatgpt|claude|gemini|copilot) said)\\**\\s*:?\\s*(.*)$", "i");
  const RE_ALONE = new RegExp("^\\s*(?:#{1,6}\\s*)?\\**(" + LABEL + ")\\**\\s*$", "i");
  function parseText(text, title = "Pasted chat") {
    const msgs = [];
    let role = null, buf = [];
    const flush = () => {
      const body = buf.join("\n").trim();
      if (role && body) msgs.push({role, content: body});
    };
    for (const line of String(text || "").split(/\r\n|\r|\n/)) {
      const m = RE_COLON.exec(line) || RE_SAID.exec(line) || RE_ALONE.exec(line);
      if (m) {
        flush();
        role = normRole(m[1].toLowerCase().replace(" said", "")); buf = [];
        if (m[2] !== undefined && m[2].trim()) buf.push(m[2]);
      } else buf.push(line);
    }
    flush();
    if (!msgs.length && String(text || "").trim()) msgs.push({role: "user", content: String(text).trim()});
    return {title: (title || "Untitled").trim().slice(0, 120) || "Untitled", source: "Pasted text", summary: "", messages: msgs};
  }

  /* ---------- import files (ChatGPT / Claude exports, generic message lists, ChatBridge's own file) ---------- */
  const flat = c => {
    if (typeof c === "string") return c;
    if (Array.isArray(c)) return c.map(flat).filter(Boolean).join("\n");
    if (c && typeof c === "object") {
      if (typeof c.text === "string") return c.text;
      for (const k of ["parts", "content"]) if (k in c) return flat(c[k]);
    }
    return "";
  };
  const pad = n => String(n).padStart(2, "0");
  const stamp = t => { const d = new Date(Number(t) * 1000); return isNaN(d) || !Number(t) ? "" : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const str = (v, n) => typeof v === "string" ? v.slice(0, n) : "";

  function parseChatgpt(item) {
    const mapping = item.mapping || {};
    let chain = [], node = item.current_node;
    if (node && mapping[node]) {
      const seen = new Set();
      while (node && mapping[node] && !seen.has(node)) { seen.add(node); chain.push(mapping[node]); node = mapping[node].parent; }
      chain.reverse();
    } else {
      chain = Object.values(mapping).filter(n => n && n.message).sort((a, b) => (a.message.create_time || 0) - (b.message.create_time || 0));
    }
    const messages = [];
    for (const n of chain) {
      const m = n && n.message;
      if (!m) continue;
      const role = (m.author || {}).role;
      if (role !== "user" && role !== "assistant") continue;
      const text = flat(m.content).trim();
      if (text) messages.push({role, content: text});
    }
    return {title: item.title, source: "ChatGPT", created: stamp(item.create_time), messages};
  }
  function parseClaude(item) {
    const messages = [];
    for (const m of item.chat_messages || []) {
      if (!m || typeof m !== "object") continue;
      const text = String(m.text || flat(m.content)).trim();
      if (text) messages.push({role: normRole(m.sender || "assistant"), content: text});
    }
    return {title: item.name, source: "Claude", created: str(item.created_at, 16).replace("T", " "), messages};
  }
  function parseGeneric(item) {
    const messages = [];
    for (const m of item.messages || []) {
      if (!m || typeof m !== "object") continue;
      const text = flat(m.content !== undefined ? m.content : (m.text !== undefined ? m.text : "")).trim();
      if (text) messages.push({role: normRole(m.role || "assistant"), content: text});
    }
    return {title: item.title || item.name, source: item.source || "Imported", messages};
  }
  /* keep only what we understand, with the right types and sizes: imported files are untrusted */
  function cleanConv(d) {
    if (!d || typeof d !== "object" || !Array.isArray(d.messages)) return null;
    const messages = [];
    for (const m of d.messages.slice(0, 5000)) {
      if (m && typeof m === "object" && typeof m.content === "string" && m.content.trim()) messages.push({role: normRole(m.role || "assistant"), content: m.content.slice(0, 200000)});
    }
    if (!messages.length) return null;
    const c = {title: str(d.title, 120).trim() || "Untitled", source: str(d.source, 40).trim() || "Imported", created: str(d.created, 32),
               summary: str(d.summary, 20000), messages};
    if (d.excerpt === true) c.excerpt = true;
    return c;
  }
  function parseJson(data) {
    if (data && typeof data === "object" && !Array.isArray(data) && data.format === "chatbridge") {
      return (Array.isArray(data.conversations) ? data.conversations : []).map(cleanConv).filter(Boolean);
    }
    let items = Array.isArray(data) ? data : [data];
    if (items.length && items[0] && typeof items[0] === "object" && "role" in items[0] && !("mapping" in items[0])) items = [{messages: items}];
    const out = [];
    for (const it of items) {
      if (!it || typeof it !== "object" || Array.isArray(it)) continue;
      if ("mapping" in it) out.push(parseChatgpt(it));
      else if ("chat_messages" in it) out.push(parseClaude(it));
      else if ("messages" in it) out.push(parseGeneric(it));
    }
    return out.map(cleanConv).filter(Boolean);
  }

  /* ---------- sections ---------- */
  const SHIFT = /^\W*(?:ok(?:ay)?\W+|alright\W+|great\W+|thanks?\W+)?(?:now|next|new topic|separate(?:ly)?|different|moving on|switching|let'?s (?:move|talk|work|try|do|start|build|look|switch)|also\b|one more thing|another (?:question|thing)|on another note|btw)\b/i;
  const STOPWORDS = new Set(("the and but for with that this from have has had was were are been being you your yours can could should would " +
    "will just then than not out into over also very more some what when where which who how why please okay " +
    "about like make made want need lets let get got use using one").split(/\s+/));
  const TAGS = [["Code", /```|\bdef \w+\(|\bfunction\b|\bclass \w+|=>|#include|\bimport \w+/],
                ["Decision", /\b(?:we(?:'ll| will) (?:use|go with)|let'?s (?:go with|use)|decided|decision|going with|settled on|i(?:'ll| will) go with)\b/i],
                ["Problem", /traceback|\berror\b|exception|\bfailed\b|doesn'?t work|not working|\bbug\b/i],
                ["Files", /\b[\w./\\-]+\.(?:py|js|ts|tsx|jsx|md|json|html|css|ya?ml|cs|java|go|rs|cpp|txt|toml|sql)\b/]];
  const keywords = text => {
    const out = new Set();
    for (const w of String(text || "").toLowerCase().match(/[a-z][a-z0-9_]{3,}/g) || []) if (!STOPWORDS.has(w)) out.add(w);
    return out;
  };
  const head = (m, n = 1500) => m.content.slice(0, n);

  function splitSections(messages, minTurns = 2, maxTurns = 14) {
    const n = messages.length;
    if (!n) return [];
    let starts = [];
    messages.forEach((m, i) => { if (m.role === "user") starts.push(i); });
    if (!starts.length || starts[0] !== 0) starts = [0].concat(starts);
    const joined = (a, b) => messages.slice(a, b).map(m => head(m)).join(" ");
    const cuts = [0];
    let run = 1, recent = keywords(joined(starts[0], starts.length > 1 ? starts[1] : n));
    for (let k = 1; k < starts.length; k++) {
      const i = starts[k], end = k + 1 < starts.length ? starts[k + 1] : n;
      const mine = keywords(head(messages[i]));
      const shift = SHIFT.test(messages[i].content.slice(0, 120));
      let shared = 0;
      for (const w of mine) if (recent.has(w)) shared++;
      const low = mine.size >= 5 && shared / mine.size < 0.08;
      if (run >= maxTurns || (run >= minTurns && (shift || low))) { cuts.push(i); run = 0; recent = new Set(); }
      run += 1;
      const here = keywords(joined(i, end));
      recent = run > 1 ? new Set([...recent, ...here]) : here;
    }
    return cuts.map((a, j) => {
      const b = j + 1 < cuts.length ? cuts[j + 1] : n;
      const part = messages.slice(a, b);
      const first = part.find(m => m.role === "user") || part[0];
      const text = part.map(m => m.content).join("\n");
      let ask = first.content;
      const m = SHIFT.exec(ask.slice(0, 120));
      if (m && stripChars(ask.slice(m[0].length), " ,.:;-").length >= 12) {
        ask = stripChars(ask.slice(m[0].length), " ,.:;-").replace(/^(?:let'?s|lets|let us)\s+/i, "");
      }
      return {title: friendlyTitle(ask, 70, `Part ${j + 1}`), start: a, end: b,
              tags: TAGS.filter(([, rx]) => rx.test(text)).map(([name]) => name).slice(0, 4), tokens: estimateTokens(text)};
    });
  }

  function chatOutline(convTitle, messages, sections, included) {
    const lines = [`Outline of the full conversation "${convTitle}" (${messages.length} messages, ${sections.length} sections). ` +
                   "Sections marked ► are included in full below; the others are only listed here for context."];
    sections.forEach((s, k) => {
      let mark = " ";
      for (let i = s.start; i < s.end; i++) if (included.has(i)) { mark = "►"; break; }
      let outcome = "";
      for (let i = s.end - 1; i >= s.start; i--) if (messages[i].role !== "user") { outcome = friendlyTitle(messages[i].content, 110, ""); break; }
      const tags = s.tags.length ? ` [${s.tags.join(", ")}]` : "";
      lines.push(`${k + 1}. ${mark} ${s.title}${tags}` + (outcome ? ` — ended with: ${outcome}` : ""));
    });
    return lines.join("\n");
  }

  /* ---------- building what gets sent ---------- */
  const fmt = msgs => msgs.map(m => `[${label(m.role)}]\n${m.content}`).join("\n\n");
  const aboutBlock = about => (about || "").trim() ? `\n\n<about_me>\nBackground the user wants you to know:\n${about.trim()}\n</about_me>` : "";

  function buildHandoff(conv, extra = "", about = "") {
    const msgs = conv.messages;
    if (conv.excerpt) {
      let h = `Below is an excerpt from an earlier conversation with another AI assistant (${conv.source || "unknown"}). ` +
              "I am adding it to the conversation we are already having. Use it as background for what I ask next. " +
              "Do not summarise it back to me; just reply briefly that you have read it, then wait for my next instruction.";
      if ((extra || "").trim()) h += "\n\nAdditional instructions: " + extra.trim();
      const outline = (conv.summary || "").trim()
        ? "<outline_of_the_full_conversation>\n" + conv.summary.trim() + "\n</outline_of_the_full_conversation>\n\n" : "";
      return h + aboutBlock(about) + "\n\n" + outline + "<excerpt>\n" + fmt(msgs) + "\n</excerpt>\n";
    }
    let h = `You are picking up a conversation that took place earlier with another AI assistant (${conv.source || "unknown"}). ` +
            "Read it fully and treat it as your own prior context: keep the same goals, decisions, style and any constraints " +
            "already established. Do not re-introduce yourself or recap at length. Reply with one or two sentences confirming where " +
            "we left off, then continue with the user's latest request or the clear next step.";
    if ((extra || "").trim()) h += "\n\nAdditional instructions: " + extra.trim();
    return h + aboutBlock(about) + "\n\n<transcript>\n" + fmt(msgs) + "\n</transcript>\n";
  }

  /* what to send: apply privacy / shortening to copies, then (optionally) cut out ticked messages with an outline */
  function prepare(conv, opts = {}) {
    let msgs = conv.messages;
    const counts = {keys: 0, emails: 0, phones: 0, paths: 0};
    if (opts.compact) msgs = compactMessages(msgs, opts.compact === "max");
    if (opts.scrub !== false) {
      msgs = msgs.map(m => {
        const r = scrubText(m.content, true, true);
        for (const k in r.counts) counts[k] += r.counts[k];
        return {role: m.role, content: r.text};
      });
    }
    const summary = opts.scrub !== false && conv.summary ? scrubText(conv.summary, true, true).text : conv.summary;   // the outline quotes the chat too
    return {conv: {...conv, messages: msgs, summary}, counts};
  }

  function makePart(conv, cells, titles = {}, withOutline = true) {
    const msgs = conv.messages;
    const chosen = [...new Set((cells || []).filter(i => Number.isInteger(i) && i >= 0 && i < msgs.length))].sort((a, b) => a - b);
    if (!chosen.length) return {error: "Tick at least one section or message first."};
    const secs = splitSections(msgs);
    for (const [k, v] of Object.entries(titles || {})) {
      if (/^\d+$/.test(k) && Number(k) < secs.length && typeof v === "string" && v.trim()) secs[Number(k)].title = v.split(/\s+/).filter(Boolean).join(" ").slice(0, 100);
    }
    return {part: {title: `Part of: ${conv.title}`.slice(0, 120), source: String(conv.source || "Chat").slice(0, 40), excerpt: true,
                   summary: withOutline ? chatOutline(String(conv.title), msgs, secs, new Set(chosen)) : "",
                   messages: chosen.map(i => msgs[i])}};
  }

  return {estimateTokens, scrubText, compactText, compactMessages, friendlyTitle, parseText, splitSections, chatOutline,
          buildHandoff, prepare, makePart, normRole, label, parseJson};
});
