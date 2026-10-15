(() => {
  "use strict";
  const C = window.ChatCore;
  const $ = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const plugins = () => (window.Capacitor && window.Capacitor.Plugins) || {};
  const onPhone = () => !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  const store = {get(k, d) { try { const v = JSON.parse(localStorage.getItem(k)); return v === null ? d : v; } catch (e) { return d; } },
                 set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }};

  /* ---------- where a conversation can go (Android app packages, and websites) ---------- */
  const APPS = [
    {name: "ChatGPT", pkg: "com.openai.chatgpt", color: "#10a37f"}, {name: "Claude", pkg: "com.anthropic.claude", color: "#d97757"},
    {name: "Gemini", pkg: "com.google.android.apps.bard", color: "#4285f4"}, {name: "Copilot", pkg: "com.microsoft.copilot", color: "#7c5cf0"},
    {name: "Perplexity", pkg: "ai.perplexity.app.android", color: "#20808d"}, {name: "Grok", pkg: "ai.x.grok", color: "#555"},
    {name: "DeepSeek", pkg: "com.deepseek.chat", color: "#4d6bfe"}, {name: "Le Chat", pkg: "ai.mistral.chat", color: "#fa520f"}];
  const SITES = [["ChatGPT", "https://chatgpt.com/"], ["Claude.ai", "https://claude.ai/new"], ["Gemini", "https://gemini.google.com/app"],
                 ["Copilot", "https://copilot.microsoft.com/"], ["Perplexity", "https://www.perplexity.ai/"], ["Grok", "https://grok.com/"],
                 ["DeepSeek", "https://chat.deepseek.com/"], ["Mistral Le Chat", "https://chat.mistral.ai/chat"]];
  const installed = {};
  async function detectApps() {
    const AL = plugins().AppLauncher;
    for (const a of APPS) {
      if (!AL) { installed[a.pkg] = ["ChatGPT", "Claude", "Gemini", "Copilot"].includes(a.name); continue; }       // in a browser preview: show a few
      try { installed[a.pkg] = !!(await AL.canOpenUrl({url: a.pkg})).value; } catch (e) { installed[a.pkg] = false; }
    }
    if (!$("#detail").hidden) renderTiles();
  }

  /* ---------- the saved conversations (kept on this phone only) ---------- */
  const KEY = "chatbridge.library.v1", MAX_ITEMS = 50;
  const clean = c => {            // anything read back from storage is checked, never trusted
    if (!c || typeof c !== "object" || !Array.isArray(c.messages)) return null;
    const messages = c.messages.slice(0, 5000).filter(m => m && typeof m.content === "string" && m.content.trim())
      .map(m => ({role: C.normRole(m.role), content: m.content.slice(0, 200000)}));
    if (!messages.length) return null;
    return {id: String(c.id || Math.random().toString(36).slice(2)).slice(0, 40), title: String(c.title || "Untitled").slice(0, 120),
            source: String(c.source || "Shared").slice(0, 40), created: String(c.created || "").slice(0, 32), summary: "", messages};
  };
  let lib = (store.get(KEY, []) || []).map(clean).filter(Boolean);
  const save = () => {
    for (;;) { if (store.set(KEY, lib)) return true; if (lib.length <= 1) return false; lib.pop(); }       // storage full: drop the oldest
  };

  /* ---------- helpers ---------- */
  let toastTimer;
  function toast(msg, ms = 4000) {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), ms);
  }
  const open = id => { $(id).hidden = false; };
  document.addEventListener("click", e => { if (e.target.matches("[data-close]")) e.target.closest(".modal").hidden = true; if (e.target.classList.contains("modal")) e.target.hidden = true; });
  const nMsg = n => n === 1 ? "1 message" : `${n} messages`;
  const pages = t => { const p = Math.round((t || 0) / 650); return t < 250 ? "a short note" : p <= 1 ? "about 1 page" : "about " + p + " pages"; };
  const DATE_GROUPS = ["Today", "Yesterday", "Last 7 days", "Last 30 days", "Older"];
  function ageDays(s) {
    const m = String(s || "").match(/(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return null;
    const d = new Date(+m[1], +m[2] - 1, +m[3]), now = new Date();
    return Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - d) / 86400000);
  }
  const dateGroup = s => { const a = ageDays(s); return a === null ? "Older" : a <= 0 ? "Today" : a === 1 ? "Yesterday" : a <= 7 ? "Last 7 days" : a <= 30 ? "Last 30 days" : "Older"; };
  function relDate(s) {
    const a = ageDays(s);
    if (a === null) return "";
    if (a <= 0) return "today";
    if (a === 1) return "yesterday";
    if (a < 7) return a + " days ago";
    const d = new Date(s);
    return isNaN(d) ? "" : d.toLocaleDateString(I18N.lang === "en" ? undefined : I18N.lang, {month: "short", day: "numeric", year: a > 300 ? "numeric" : undefined});
  }

  /* ---------- settings: language, privacy, appearance ---------- */
  const SKEY = "chatbridge.settings.v1";
  const DEFAULTS = {mode: "auto", from: "19:00", to: "07:00", language: "auto", scrub: true, compact: false};
  const validTime = s => /^([01]\d|2[0-3]):[0-5]\d$/.test(String(s));
  let prefs = (() => {
    const s = store.get(SKEY, {}) || {};
    return {mode: ["auto", "system", "light", "dark"].includes(s.mode) ? s.mode : DEFAULTS.mode,
            from: validTime(s.from) ? s.from : DEFAULTS.from, to: validTime(s.to) ? s.to : DEFAULTS.to,
            language: typeof s.language === "string" && (s.language === "auto" || I18N.NAMES[s.language]) ? s.language : "auto",
            scrub: s.scrub !== false, compact: s.compact === true};
  })();
  const savePrefs = () => store.set(SKEY, prefs);
  const minutes = s => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
  function isNight(now, from, to) {          // works for ranges that cross midnight (19:00 to 07:00) and same-day ranges
    const n = now.getHours() * 60 + now.getMinutes(), a = minutes(from), b = minutes(to);
    if (a === b) return false;
    return a < b ? n >= a && n < b : n >= a || n < b;
  }
  function currentTheme(now = new Date()) {
    if (prefs.mode === "dark") return "dark";
    if (prefs.mode === "light") return "light";
    if (prefs.mode === "system") return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    return isNight(now, prefs.from, prefs.to) ? "dark" : "light";
  }
  const applyTheme = () => {
    const theme = currentTheme();
    document.documentElement.dataset.theme = theme;
    const SB = plugins().StatusBar;                                    // dark clock and icons on the light look, light ones on the night look
    if (SB) { try { SB.setStyle({style: theme === "dark" ? "DARK" : "LIGHT"}); } catch (e) { /* older phones */ } }
  };
  $("#btnSettings").onclick = () => {
    $("#sLang").innerHTML = [["auto", "Automatic"], ...Object.entries(I18N.NAMES)].map(([k, v]) => `<option value="${k}" ${k === prefs.language ? "selected" : ""}${k === "auto" ? "" : ' translate="no"'}>${esc(v)}</option>`).join("");
    $("#sScrub").checked = prefs.scrub; $("#sCompact").checked = prefs.compact;
    qa("input[name=mode]").forEach(r => r.checked = r.value === prefs.mode);
    $("#tFrom").value = prefs.from; $("#tTo").value = prefs.to; $("#times").hidden = prefs.mode !== "auto";
    open("#mSettings");
  };
  qa("input[name=mode]").forEach(r => r.onchange = () => { prefs.mode = r.value; $("#times").hidden = prefs.mode !== "auto"; savePrefs(); applyTheme(); });
  [$("#tFrom"), $("#tTo")].forEach(i => i.onchange = () => { if (validTime(i.value)) { prefs[i.id === "tFrom" ? "from" : "to"] = i.value; savePrefs(); applyTheme(); } });
  $("#sScrub").onchange = () => { prefs.scrub = $("#sScrub").checked; savePrefs(); refreshNote(); };
  $("#sCompact").onchange = () => { prefs.compact = $("#sCompact").checked; savePrefs(); refreshNote(); };
  $("#sLang").onchange = () => { prefs.language = $("#sLang").value; savePrefs(); location.reload(); };     // the new language starts fresh
  window.ChatBridgeTheme = {isNight, currentTheme: () => currentTheme(), get prefs() { return {...prefs}; }};   // for tests

  /* ---------- adding conversations ---------- */
  function addParsed(convs, source) {
    const added = [];
    for (const raw of convs) {
      const c = clean({...raw, id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), source: raw.source || source, created: raw.created || new Date().toISOString()});
      if (c) { lib.unshift(c); added.push(c); }
    }
    lib = lib.slice(0, MAX_ITEMS);
    if (added.length && !save()) toast("This phone is low on space, so it couldn't be saved. You can still send it.", 6000);
    return added;
  }
  function addConversation(text, source) {
    text = String(text || "").trim();
    if (!text) return toast("There was no text to add.");
    const conv = C.parseText(text, "");
    const firstAsk = (conv.messages.find(m => m.role === "user") || conv.messages[0] || {}).content || "";
    conv.title = C.friendlyTitle(firstAsk, 64, I18N.tr("Shared conversation"));
    const added = addParsed([conv], source || "Pasted text");
    if (!added.length) return toast("Couldn't read that text as a conversation.");
    renderHome(); openDetail(added[0].id);
  }
  function takeShared() {          // text another app shared to us (the Android side holds it until we ask)
    try { const t = window.ChatBridgeNative && window.ChatBridgeNative.takeShared(); if (t) addConversation(t, "Shared to ChatBridge"); } catch (e) { /* not on a phone */ }
  }
  async function pasteClipboard() {
    let t = "";
    try { const P = plugins().Clipboard; t = P ? ((await P.read()).value || "") : await navigator.clipboard.readText(); } catch (e) { /* denied */ }
    if (!t.trim()) { open("#mPaste"); return toast("Couldn't read the clipboard. Paste it here instead."); }
    addConversation(t, "Pasted text");
  }
  $("#filePick").onchange = async e => {
    let n = 0, bad = 0;
    for (const f of [...e.target.files]) {
      try {
        const text = await f.text();
        let convs;
        if (/\.json$/i.test(f.name)) convs = C.parseJson(JSON.parse(text));
        else { const c = C.parseText(text, f.name.replace(/\.[^.]+$/, "")); convs = [{...c, title: C.friendlyTitle(c.title, 64, f.name)}]; }
        n += addParsed(convs, "Imported").length; if (!convs.length) bad++;
      } catch (err) { bad++; }
    }
    e.target.value = "";
    renderHome();
    if (n) toast(n === 1 ? "Added 1 chat." : `Added ${n} chats.`);
    else if (bad) toast("That file doesn't look like a conversation.");
  };
  $("#btnFile").onclick = () => $("#filePick").click();
  $("#btnClip").onclick = pasteClipboard;
  $("#btnType").onclick = () => { open("#mPaste"); $("#pText").focus(); };
  $("#pAdd").onclick = () => { const t = $("#pText").value; if (!t.trim()) return toast("Paste some text first."); $("#pText").value = ""; $("#mPaste").hidden = true; addConversation(t, "Pasted text"); };
  $("#btnHelp").onclick = () => open("#mHelp");

  /* ---------- the list ---------- */
  let query = "";
  function renderHome() {
    const q = query.trim().toLowerCase();
    const shown = !q ? lib : lib.filter(c => `${c.title} ${c.source}`.toLowerCase().includes(q) || c.messages.some(m => m.content.toLowerCase().includes(q)));
    $("#searchRow").hidden = !lib.length;
    $("#hero").hidden = lib.length > 0;
    if (lib.length && !shown.length) { $("#list").innerHTML = `<div class="empty"><b>Nothing matches “${esc(query.trim())}”</b><br>Try a different word, or clear the search box.</div>`; return; }
    const groups = {};
    DATE_GROUPS.forEach(g => groups[g] = []);
    [...shown].sort((a, b) => String(b.created).localeCompare(String(a.created))).forEach(c => groups[dateGroup(c.created)].push(c));
    $("#list").innerHTML = Object.entries(groups).filter(([, items]) => items.length).map(([name, items]) => `
      <div class="grp-head">${esc(name)}</div>
      ${items.map(c => `<button class="card" data-id="${esc(c.id)}"><b translate="no">${esc(c.title)}</b><small>${["Today", "Yesterday"].includes(name) ? "" : esc(relDate(c.created)) + " · "}${esc(c.source)} · ${nMsg(c.messages.length)}</small></button>`).join("")}`).join("");
  }
  $("#list").addEventListener("click", e => { const b = e.target.closest(".card"); if (b) openDetail(b.dataset.id); });
  $("#chatSearch").addEventListener("input", e => { query = e.target.value; renderHome(); });

  /* ---------- one conversation, as a notebook of sections ---------- */
  const SEC = {id: null, secs: [], sel: new Set(), titles: {}, open: new Set()};
  const T = {kind: null, site: 0};                                 // where it goes: an app ("app:<package>"), "web", "file", "copy" or "share"
  const current = () => lib.find(c => c.id === SEC.id);
  const partial = () => SEC.sel.size > 0;
  function openDetail(id, keepTarget) {
    const c = lib.find(x => x.id === id);
    if (!c) return;
    Object.assign(SEC, {id, secs: C.splitSections(c.messages), sel: new Set(), titles: {}, open: new Set()});
    if (SEC.secs.length === 1) SEC.open.add(0);
    if (!keepTarget) T.kind = store.get("chatbridge.lastTarget", null);
    $("#home").hidden = true; $("#detail").hidden = false; $("#bar").hidden = false; $("#btnBack").hidden = false;
    $("#dTitle").textContent = c.title;
    $("#dMeta").textContent = `${nMsg(c.messages.length)} · ${pages(C.estimateTokens(c.messages.map(m => m.content).join("\n")))} · ${c.source}`;
    renderSections(); renderTiles(); renderSummary(); window.scrollTo(0, 0);
    if (history.state !== "detail") history.pushState("detail", "");
  }
  function showHome() { $("#home").hidden = false; $("#detail").hidden = true; $("#bar").hidden = true; $("#btnBack").hidden = true; SEC.id = null; renderHome(); }
  window.addEventListener("popstate", () => { if (!$("#detail").hidden) showHome(); });
  $("#btnBack").onclick = () => { if (history.state === "detail") history.back(); else showHome(); };

  function renderSections() {
    const c = current(); if (!c) return;
    $("#partNote").textContent = partial() ? `Sending ${SEC.sel.size} of ${c.messages.length} messages` : "Sending the whole conversation — or tick parts of it";
    $("#secClear").hidden = !partial(); $("#outlineRow").hidden = !partial();
    $("#secBody").innerHTML = SEC.secs.map((s, k) => {
      const idx = Array.from({length: s.end - s.start}, (_, j) => s.start + j), n = idx.filter(i => SEC.sel.has(i)).length;
      const state = n === 0 ? "" : n === idx.length ? "on" : "some", isOpen = SEC.open.has(k);
      return `<div class="sec ${state}" data-k="${k}"><div class="sec-head"><button class="arrow" data-toggle="${k}" aria-label="Open or close">${isOpen ? "▾" : "▸"}</button>
        <span class="chk" data-pick="${k}" role="checkbox" aria-label="Tick this whole section">${n === idx.length ? "✓" : n ? "–" : "✓"}</span>
        <input class="sectitle" data-title="${k}" value="${esc(SEC.titles[k] ?? s.title)}" maxlength="100" aria-label="Section name">
        <span class="sec-meta">${idx.length}</span></div>
        ${isOpen ? `<div class="cells">${idx.map(i => { const m = c.messages[i]; return `<div class="cell ${SEC.sel.has(i) ? "on" : ""}" data-cell="${i}"><span class="chk">✓</span><span class="who">${m.role === "user" ? "You" : "AI"}</span><span class="txt" translate="no">${esc(m.content.slice(0, 1500))}</span></div>`; }).join("")}</div>` : ""}</div>`;
    }).join("");
    refreshNote(); renderSummary();
  }
  function refreshNote() {
    const b = buildText(true);
    $("#estimate").textContent = !b ? "" : b.compact && !prefs.compact ? "It’s a long conversation, so ChatBridge will trim big blocks of code or output first."
      : b.text.length > 400000 ? "This is very long. Some apps refuse to share this much text; use Copy instead." : "";
  }
  $("#secBody").addEventListener("click", e => {
    if (e.target.matches("input.sectitle")) return;
    const tog = e.target.closest("[data-toggle]"), pick = e.target.closest("[data-pick]"), cell = e.target.closest("[data-cell]");
    if (tog) { const k = Number(tog.dataset.toggle); SEC.open.has(k) ? SEC.open.delete(k) : SEC.open.add(k); }
    else if (pick) {
      const s = SEC.secs[Number(pick.dataset.pick)], idx = Array.from({length: s.end - s.start}, (_, j) => s.start + j), all = idx.every(i => SEC.sel.has(i));
      idx.forEach(i => all ? SEC.sel.delete(i) : SEC.sel.add(i));
    } else if (cell) { const i = Number(cell.dataset.cell); SEC.sel.has(i) ? SEC.sel.delete(i) : SEC.sel.add(i); }
    else return;
    renderSections();
  });
  $("#secBody").addEventListener("change", e => { if (e.target.matches("input.sectitle")) SEC.titles[e.target.dataset.title] = e.target.value; });
  $("#secClear").onclick = () => { SEC.sel.clear(); renderSections(); };
  $("#secOpenAll").onclick = () => { SEC.secs.forEach((s, k) => SEC.open.add(k)); renderSections(); };
  $("#secCloseAll").onclick = () => { SEC.open.clear(); renderSections(); };
  $("#optOutline").onchange = refreshNote;

  $("#dRemove").onclick = () => {
    if (!confirm(I18N.tr("Remove this conversation from ChatBridge? The original stays in the app it came from."))) return;
    lib = lib.filter(c => c.id !== SEC.id); save(); showHome();
  };
  $("#dRename").onclick = () => { $("#rnInput").value = (current() || {}).title || ""; open("#mRename"); $("#rnInput").select(); };
  const doRename = () => {
    const name = $("#rnInput").value.split(/\s+/).filter(Boolean).join(" ").slice(0, 120);
    if (!name) return toast("Type a name first.");
    current().title = name; save(); $("#dTitle").textContent = name; $("#mRename").hidden = true;
  };
  $("#rnSave").onclick = doRename;
  $("#rnInput").addEventListener("keydown", e => { if (e.key === "Enter") doRename(); });

  /* ---------- where it goes: tiles, website list, summary and the big button ---------- */
  const siteLabel = () => T.site === "none" ? null : SITES[T.site][0];
  const appFor = kind => APPS.find(a => "app:" + a.pkg === kind);
  function tile(kind, name, glyph, color, fixed) {
    return `<button class="app-tile ${T.kind === kind ? "on" : ""}" data-kind="${esc(kind)}"><span class="ic" style="background:${color}">${glyph}</span><b${fixed ? "" : ' translate="no"'}>${esc(name)}</b></button>`;
  }
  function renderTiles() {
    const tiles = APPS.filter(a => installed[a.pkg]).map(a => tile("app:" + a.pkg, a.name, esc(a.name[0]), a.color, false));
    tiles.push(tile("web", "A website", "🌐", "var(--chip)", true), tile("file", "A file", "💾", "var(--chip)", true),
               tile("copy", "Just copy it", "⧉", "var(--chip)", true), tile("share", "Another app", "↗", "var(--chip)", true));
    $("#appGrid").innerHTML = tiles.join("");
    $("#webPick").hidden = T.kind !== "web";
    if (T.kind === "web") {
      $("#webSite").innerHTML = SITES.map(([n], i) => `<option value="${i}" ${T.site === i ? "selected" : ""} translate="no">${esc(n)}</option>`).join("") + `<option value="none" ${T.site === "none" ? "selected" : ""}>I’ll open it myself</option>`;
    }
  }
  $("#appGrid").addEventListener("click", e => {
    const b = e.target.closest(".app-tile"); if (!b) return;
    T.kind = b.dataset.kind; store.set("chatbridge.lastTarget", T.kind);
    renderTiles(); renderSummary();
  });
  $("#webSite").onchange = e => { T.site = e.target.value === "none" ? "none" : Number(e.target.value); renderSummary(); };

  function renderSummary() {
    const items = partial() ? "the parts you ticked" : "this conversation";
    let msg = "Now choose where you want to continue it.", label = "Continue";
    const app = appFor(T.kind);
    if (app) { msg = `ChatBridge copies ${items} and opens ${app.name}. Paste it into the message box.`; label = "Continue in " + app.name; }
    else if (T.kind === "web") {
      if (siteLabel()) { msg = `ChatBridge copies ${items} and opens ${siteLabel()}. Paste it into the message box.`; label = "Copy and open " + siteLabel(); }
      else { msg = `ChatBridge copies ${items}. Paste it into any AI website.`; label = "Copy it"; }
    }
    else if (T.kind === "file") { msg = `ChatBridge saves ${items} as a file you can attach anywhere.`; label = "Save as a file…"; }
    else if (T.kind === "copy") { msg = `ChatBridge copies ${items}. Paste it anywhere.`; label = "Copy it"; }
    else if (T.kind === "share") { msg = `ChatBridge shares ${items} with the app you pick.`; label = "Share…"; }
    $("#summary").textContent = msg;
    $("#sendLabel").textContent = label;
    $("#btnSend").classList.toggle("off", !T.kind);
  }

  /* ---------- what gets sent ---------- */
  function buildText(quiet) {
    const conv = current(); if (!conv) return null;
    let c = conv;
    if (partial()) {
      const r = C.makePart(conv, [...SEC.sel], SEC.titles, $("#optOutline").checked);
      if (r.error) { if (!quiet) toast(r.error); return null; }
      c = r.part;
    }
    const compact = prefs.compact || C.estimateTokens(c.messages.map(m => m.content).join("\n")) > 120000;     // otherwise only when it really is too long
    const p = C.prepare(c, {scrub: prefs.scrub, compact});
    return {text: C.buildHandoff(p.conv), compact, counts: p.counts, title: c.title};
  }
  async function copyText(text) {
    const P = plugins().Clipboard;
    if (P) return P.write({string: text});
    if (navigator.clipboard) return navigator.clipboard.writeText(text);
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  async function openTarget(url) {            // an Android package name (opens the app) or a web address (opens the browser)
    const P = plugins().AppLauncher;
    if (P) { await P.openUrl({url}); return true; }
    if (/^https?:/.test(url)) { window.open(url, "_blank", "noopener"); return true; }
    return false;
  }
  async function saveFile(b) {
    const name = "chatbridge-" + (b.title || "conversation").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) + ".md";
    const FS = plugins().Filesystem, SH = plugins().Share;
    if (FS && SH) {
      const r = await FS.writeFile({path: name, data: b.text, directory: "CACHE", encoding: "utf8"});      // a failure here is a real error
      try { await SH.share({title: name, files: [r.uri], dialogTitle: name}); } catch (e) { /* closing the share sheet is not an error */ }
      return true;
    }
    const a = document.createElement("a");                               // in a browser: a normal download
    a.href = URL.createObjectURL(new Blob([b.text], {type: "text/markdown"})); a.download = name; document.body.appendChild(a); a.click(); a.remove();
    return true;
  }
  const HKEY = "chatbridge.history.v1";
  function remember(label, b) {
    const h = store.get(HKEY, []) || [];
    h.unshift({time: new Date().toISOString().slice(0, 16).replace("T", " "), target: label, kind: T.kind, site: T.site, id: SEC.id, title: b.title, parts: partial()});
    store.set(HKEY, h.slice(0, 50));
  }
  async function doSend() {
    if (!T.kind) return toast("Choose where you want to continue it.");
    const b = buildText(); if (!b) return;
    const app = appFor(T.kind);
    try {
      if (app) {
        await copyText(b.text);
        try { await openTarget(app.pkg); toast("Copied. Paste it into the message box of any AI app."); }
        catch (e) { toast(`Couldn't open ${app.name}. It’s copied, so paste it into the app yourself.`, 6000); }
        remember(app.name, b);
      } else if (T.kind === "web") {
        await copyText(b.text);
        if (siteLabel()) {
          try { await openTarget(SITES[T.site][1]); toast("Copied. Paste it into the message box of any AI app."); }
          catch (e) { toast("Couldn't open it. The text is copied, so paste it where you like.", 6000); }
          remember(SITES[T.site][0], b);
        } else { toast("Copied. Paste it into any app."); remember(I18N.tr("A website"), b); }
      } else if (T.kind === "file") {
        try { await saveFile(b); remember(I18N.tr("A file"), b); } catch (e) { toast("Couldn't create the file."); }
      } else if (T.kind === "copy") {
        await copyText(b.text); toast("Copied. Paste it into any app."); remember(I18N.tr("Just copy it"), b);
      } else if (T.kind === "share") {
        const P = plugins().Share;
        try { if (P) await P.share({title: "ChatBridge", text: b.text, dialogTitle: "Share…"}); else if (navigator.share) await navigator.share({text: b.text}); else { await copyText(b.text); toast("Copied. Paste it into any app."); } remember(I18N.tr("Another app"), b); }
        catch (e) { /* closed the sheet */ }
      }
    } catch (e) { toast("Couldn't copy. Try Share instead."); }
  }
  $("#btnSend").onclick = doSend;

  /* ---------- history ---------- */
  $("#btnHistory").onclick = () => {
    const h = store.get(HKEY, []) || [];
    $("#histBody").innerHTML = h.length ? h.map((e, i) => `<div class="hrow"><div><b translate="no">${esc(e.title)}</b><small>${esc(e.time)} → <span translate="no">${esc(e.target)}</span></small></div><button class="btn" data-again="${i}">Send again</button></div>`).join("")
      : '<div class="empty"><b>Nothing sent yet</b><br>Chats you send will be listed here.</div>';
    open("#mHistory");
  };
  $("#histBody").onclick = e => {
    const b = e.target.closest("[data-again]"); if (!b) return;
    const h = (store.get(HKEY, []) || [])[Number(b.dataset.again)];
    if (!h || !lib.some(c => c.id === h.id)) return toast("Those chats aren’t in the list any more.");
    $("#mHistory").hidden = true; T.kind = h.kind; T.site = h.site;
    openDetail(h.id, true); doSend();
  };

  /* ---------- start ---------- */
  I18N.init((location.search.match(/[?&]lang=([\w-]+)/) || [])[1] || prefs.language);          // ?lang=xx is for previews
  applyTheme();
  setInterval(applyTheme, 60000);                                       // crosses into the evening while the app is open
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { applyTheme(); takeShared(); } });
  window.addEventListener("sharedtext", takeShared);
  renderHome();
  detectApps();
  takeShared();
  if (/[?&]demo/.test(location.search) && !lib.length) {            // browser preview only
    addConversation("User: Fix my git setup on Windows, push is rejected\nAssistant: The error is about the private email. Use the noreply address.\nUser: ok that worked, thanks\nAssistant: Great.\n" +
      "User: Now let's write a resume for a nursing job posting at the hospital\nAssistant: Here is a first draft:\n```\nSummary: Registered nurse with 6 years\n```\n" +
      "User: Make the summary shorter and mention ICU experience\nAssistant: Done: three lines, leading with ICU.\n" +
      "User: Also plan a trip to Kyoto in April with temples\nAssistant: Day 1 Fushimi Inari. We'll use the regional rail pass.", "Claude Code");
  }
})();
