(() => {
  "use strict";
  const C = window.ChatCore;
  const $ = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const plugins = () => (window.Capacitor && window.Capacitor.Plugins) || {};

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
  const load = () => { try { return (JSON.parse(localStorage.getItem(KEY)) || []).map(clean).filter(Boolean); } catch (e) { return []; } };
  let lib = load();
  const save = () => {
    for (;;) {
      try { localStorage.setItem(KEY, JSON.stringify(lib)); return true; }
      catch (e) { if (lib.length <= 1) return false; lib.pop(); }       // storage full: drop the oldest
    }
  };

  /* ---------- helpers ---------- */
  let toastTimer;
  function toast(msg, ms = 3500) {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), ms);
  }
  const open = id => { $(id).hidden = false; };
  document.addEventListener("click", e => { if (e.target.matches("[data-close]")) e.target.closest(".modal").hidden = true; if (e.target.classList.contains("modal")) e.target.hidden = true; });
  const pages = t => { const p = Math.round((t || 0) / 650); return t < 250 ? "a short note" : p <= 1 ? "about 1 page" : "about " + p + " pages"; };
  const niceDate = s => { const d = new Date(s); return isNaN(d) ? "" : d.toLocaleDateString(undefined, {month: "short", day: "numeric"}); };

  /* ---------- adding conversations ---------- */
  function addConversation(text, source) {
    text = String(text || "").trim();
    if (!text) return toast("There was no text to add.");
    const conv = C.parseText(text, "");
    const firstAsk = (conv.messages.find(m => m.role === "user") || conv.messages[0] || {}).content || "";
    const c = clean({...conv, id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: C.friendlyTitle(firstAsk, 64, "Shared conversation"),
                     source: source || "Pasted text", created: new Date().toISOString()});
    if (!c) return toast("Couldn't read that text as a conversation.");
    lib.unshift(c); lib = lib.slice(0, MAX_ITEMS);
    if (!save()) toast("This phone is low on space, so it couldn't be saved. You can still send it.", 6000);
    renderHome(); openDetail(c.id);
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

  /* ---------- the list ---------- */
  function renderHome() {
    $("#listLbl").hidden = !lib.length;
    $("#list").innerHTML = lib.map(c => `<button class="card" data-id="${esc(c.id)}"><b>${esc(c.title)}</b><small>${esc(niceDate(c.created))}${c.created ? " · " : ""}${esc(c.source)} · ${c.messages.length} messages</small></button>`).join("");
  }
  $("#list").addEventListener("click", e => { const b = e.target.closest(".card"); if (b) openDetail(b.dataset.id); });

  /* ---------- one conversation, as a notebook of sections ---------- */
  const SEC = {id: null, secs: [], sel: new Set(), titles: {}, open: new Set()};
  const current = () => lib.find(c => c.id === SEC.id);
  function openDetail(id) {
    const c = lib.find(x => x.id === id);
    if (!c) return;
    Object.assign(SEC, {id, secs: C.splitSections(c.messages), sel: new Set(), titles: {}, open: new Set()});
    if (SEC.secs.length === 1) SEC.open.add(0);
    $("#home").hidden = true; $("#detail").hidden = false; $("#bar").hidden = false; $("#btnBack").hidden = false;
    $("#dTitle").textContent = c.title;
    $("#dMeta").textContent = `${c.messages.length} messages · ${pages(C.estimateTokens(c.messages.map(m => m.content).join("\n")))} · ${c.source}`;
    renderSections(); window.scrollTo(0, 0);
    if (history.state !== "detail") history.pushState("detail", "");
  }
  function showHome() { $("#home").hidden = false; $("#detail").hidden = true; $("#bar").hidden = true; $("#btnBack").hidden = true; SEC.id = null; renderHome(); }
  window.addEventListener("popstate", () => { if (!$("#detail").hidden) showHome(); });
  $("#btnBack").onclick = () => { if (history.state === "detail") history.back(); else showHome(); };

  function renderSections() {
    const c = current(); if (!c) return;
    const partial = SEC.sel.size > 0;
    $("#partNote").textContent = partial ? `Sending ${SEC.sel.size} of ${c.messages.length} messages` : "Sending the whole conversation";
    $("#secClear").hidden = !partial; $("#outlineRow").hidden = !partial;
    $("#secBody").innerHTML = SEC.secs.map((s, k) => {
      const idx = Array.from({length: s.end - s.start}, (_, j) => s.start + j), n = idx.filter(i => SEC.sel.has(i)).length;
      const state = n === 0 ? "" : n === idx.length ? "on" : "some", isOpen = SEC.open.has(k);
      return `<div class="sec ${state}" data-k="${k}"><div class="sec-head"><button class="arrow" data-toggle="${k}" aria-label="Open or close">${isOpen ? "▾" : "▸"}</button>
        <span class="chk" data-pick="${k}" role="checkbox" aria-label="Tick this section">${n === idx.length ? "✓" : n ? "–" : "✓"}</span>
        <input class="sectitle" data-title="${k}" value="${esc(SEC.titles[k] ?? s.title)}" maxlength="100" aria-label="Section name">
        <span class="sec-meta">${idx.length}</span></div>
        ${isOpen ? `<div class="cells">${idx.map(i => { const m = c.messages[i]; return `<div class="cell ${SEC.sel.has(i) ? "on" : ""}" data-cell="${i}"><span class="chk">✓</span><span class="who">${m.role === "user" ? "You" : "AI"}</span><span class="txt">${esc(m.content.slice(0, 1500))}</span></div>`; }).join("")}</div>` : ""}</div>`;
    }).join("");
    refreshNote();
  }
  function refreshNote() {
    const b = buildText(true);
    $("#estimate").textContent = !b ? "" : b.compact ? "It’s a long conversation, so ChatBridge will trim big blocks of code or output first."
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
  $("#optScrub").onchange = $("#optOutline").onchange = refreshNote;
  $("#btnDelete").onclick = () => {
    if (!confirm("Remove this conversation from ChatBridge? The original stays in the app it came from.")) return;
    lib = lib.filter(c => c.id !== SEC.id); save(); showHome();
  };

  /* ---------- what gets sent ---------- */
  function buildText(quiet) {
    const conv = current(); if (!conv) return null;
    let c = conv;
    if (SEC.sel.size) {
      const r = C.makePart(conv, [...SEC.sel], SEC.titles, $("#optOutline").checked);
      if (r.error) { if (!quiet) toast(r.error); return null; }
      c = r.part;
    }
    const compact = C.estimateTokens(c.messages.map(m => m.content).join("\n")) > 120000;     // only when it really is too long
    const p = C.prepare(c, {scrub: $("#optScrub").checked, compact});
    return {text: C.buildHandoff(p.conv), compact, counts: p.counts};
  }
  async function copyText(text) {
    const P = plugins().Clipboard;
    if (P) return P.write({string: text});
    if (navigator.clipboard) return navigator.clipboard.writeText(text);
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
  }
  async function copyOnly() { const b = buildText(); if (!b) return false; try { await copyText(b.text); toast("Copied. Paste it into the message box of any AI app."); return true; } catch (e) { toast("Couldn't copy. Try Share instead."); return false; } }
  $("#btnCopy").onclick = copyOnly;
  $("#btnShare").onclick = async () => {
    const b = buildText(); if (!b) return;
    try {
      const P = plugins().Share;
      if (P) await P.share({title: "ChatBridge", text: b.text, dialogTitle: "Send to…"});
      else if (navigator.share) await navigator.share({text: b.text});
      else { await copyText(b.text); toast("Copied. Paste it into any app."); }
    } catch (e) { /* closed the sheet */ }
  };
  $("#bar").addEventListener("click", async e => {
    const q = e.target.closest("[data-open]");
    if (!q) return;
    if (!(await copyOnly())) return;
    setTimeout(() => { const P = plugins().AppLauncher; if (P) P.openUrl({url: q.dataset.open}); else window.open(q.dataset.open, "_blank", "noopener"); }, 700);
  });

  /* ---------- buttons on the home screen, help ---------- */
  $("#btnClip").onclick = pasteClipboard;
  $("#btnType").onclick = () => { open("#mPaste"); $("#pText").focus(); };
  $("#pAdd").onclick = () => { const t = $("#pText").value; if (!t.trim()) return toast("Paste some text first."); $("#pText").value = ""; $("#mPaste").hidden = true; addConversation(t, "Pasted text"); };
  $("#btnHelp").onclick = () => open("#mHelp");

  /* ---------- appearance: light by day, dark at night (or follow the phone, or fixed) ---------- */
  const SKEY = "chatbridge.settings.v1";
  const DEFAULTS = {mode: "auto", from: "19:00", to: "07:00"};
  const validTime = s => /^([01]\d|2[0-3]):[0-5]\d$/.test(String(s));
  let prefs = (() => {
    try { const s = JSON.parse(localStorage.getItem(SKEY)) || {};
      return {mode: ["auto", "system", "light", "dark"].includes(s.mode) ? s.mode : DEFAULTS.mode,
              from: validTime(s.from) ? s.from : DEFAULTS.from, to: validTime(s.to) ? s.to : DEFAULTS.to}; }
    catch (e) { return {...DEFAULTS}; }
  })();
  const minutes = s => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
  /* is it "night" at this moment? Works for ranges that cross midnight (19:00 to 07:00) and same-day ranges */
  function isNight(now, from, to) {
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
  function applyTheme() { document.documentElement.dataset.theme = currentTheme(); }
  function savePrefs() { try { localStorage.setItem(SKEY, JSON.stringify(prefs)); } catch (e) { /* not saved */ } }
  $("#btnSettings").onclick = () => {
    qa("input[name=mode]").forEach(r => r.checked = r.value === prefs.mode);
    $("#tFrom").value = prefs.from; $("#tTo").value = prefs.to; $("#times").hidden = prefs.mode !== "auto";
    open("#mSettings");
  };
  qa("input[name=mode]").forEach(r => r.onchange = () => { prefs.mode = r.value; $("#times").hidden = prefs.mode !== "auto"; savePrefs(); applyTheme(); });
  [$("#tFrom"), $("#tTo")].forEach(i => i.onchange = () => {
    if (validTime(i.value)) { prefs[i.id === "tFrom" ? "from" : "to"] = i.value; savePrefs(); applyTheme(); }
  });
  applyTheme();
  setInterval(applyTheme, 60000);                                       // crosses into the evening while the app is open
  document.addEventListener("visibilitychange", () => { if (!document.hidden) applyTheme(); });
  window.ChatBridgeTheme = {isNight, currentTheme: () => currentTheme(), get prefs() { return {...prefs}; }};   // for tests

  /* ---------- start ---------- */
  renderHome();
  window.addEventListener("sharedtext", takeShared);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) takeShared(); });
  takeShared();
  if (/[?&]demo/.test(location.search) && !lib.length) {            // browser preview only
    addConversation("User: Fix my git setup on Windows, push is rejected\nAssistant: The error is about the private email. Use the noreply address.\nUser: ok that worked, thanks\nAssistant: Great.\n" +
      "User: Now let's write a resume for a nursing job posting at the hospital\nAssistant: Here is a first draft:\n```\nSummary: Registered nurse with 6 years\n```\n" +
      "User: Make the summary shorter and mention ICU experience\nAssistant: Done: three lines, leading with ICU.\n" +
      "User: Also plan a trip to Kyoto in April with temples\nAssistant: Day 1 Fushimi Inari. We'll use the regional rail pass.", "Claude Code");
  }
})();
