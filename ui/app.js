const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const S = {chats: [], apps: [], web: [], settings: {theme: "dark", size: 16}, sel: new Set(), target: null, busy: false, scanning: true,
           query: "", hits: {}, toolsChosen: false};
const api = () => window.pywebview.api;
const PALETTE = ["#f0997b", "#93c5fd", "#5dcaa5", "#ed93b1", "#afa9ec", "#fac775", "#85b7eb"];
const colorFor = n => PALETTE[[...String(n)].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];

/* ---------- helpers ---------- */
let toastTimer;
function toast(msg, kind = "", ms = 5000, action = null) {   // action = {label, fn}: a button inside the message
  const t = $("#toast");
  t.className = "toast show " + kind;
  t.innerHTML = (kind === "work" ? '<span class="spinner"></span>' : "") + `<span>${esc(msg)}</span>` + (action ? `<button>${esc(action.label)}</button>` : "");
  if (action) t.querySelector("button").onclick = () => { action.fn(); t.classList.remove("show"); };
  clearTimeout(toastTimer);
  if (ms) toastTimer = setTimeout(() => t.classList.remove("show"), ms);
}
const open = id => { $(id).hidden = false; };
const close = el => { (el.closest ? el.closest(".modal") : $(el)).hidden = true; };
document.addEventListener("click", e => { if (e.target.matches("[data-close]")) close(e.target); if (e.target.classList.contains("modal")) e.target.hidden = true; });
document.addEventListener("keydown", e => { if (e.key === "Escape") document.querySelectorAll(".modal").forEach(m => m.hidden = true); });
const iconFor = source => {
  const first = String(source).toLowerCase().split(" ")[0];
  const a = S.apps.find(a => a.icon && a.name.toLowerCase().split(" ")[0] === first);
  return a ? `<img src="${a.icon}" alt="">` : ({"project": "▤", "pasted": "⎘"}[first] || esc(String(source)[0] || "?").toUpperCase());
};
const THEMES = {midnight: "Midnight (teal)", tokyo: "Tokyo Night (blue)", gruvbox: "Gruvbox (amber)", nord: "Nord (ice)", light: "Paper (light)"};
const FONTS = {code: "Cascadia Code (code style)", consolas: "Consolas (code style)", sans: "Segoe UI (plain)"};
function applySettings() {
  const s = S.settings;
  document.documentElement.dataset.theme = THEMES[s.theme] ? s.theme : "midnight";
  document.documentElement.dataset.font = FONTS[s.font] ? s.font : "code";
  document.documentElement.style.setProperty("--fs", (s.size || 16) + "px");
}
async function persistLook() {
  const s = S.settings;
  S.settings = await api().save_settings({autopaste: s.autopaste, theme: s.theme, font: s.font, size: s.size});
}

/* ---------- rendering ---------- */
const kfmt = n => n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n || 0);
const opts = () => ({compact: $("#oCompact").checked, scrub: $("#oScrub").checked});
const selectedIds = () => [...S.sel].filter(id => S.chats.some(c => c.id === id));

let estTimer, estSeq = 0;
function scheduleEstimate() { clearTimeout(estTimer); estTimer = setTimeout(refreshEstimate, 250); }
async function refreshEstimate() {
  const ids = selectedIds(), box = $("#estimate"), seq = ++estSeq;
  if (!ids.length) { box.innerHTML = ""; return; }
  const e = await api().estimate(ids, S.target, opts());
  if (seq !== estSeq || !e) return;
  const parts = [`<b title="Tokens are how AI measures length: roughly 650 per page">${pagesOf(e.tokens)} (~${e.tokens.toLocaleString()} tokens)</b>`];
  if (e.pct != null) parts.push(`<span class="${e.pct > 70 ? "warn" : "good"}">${e.pct > 100 ? "too long for " + esc(e.target) + " — turn on “Shorten long text”" : e.pct > 70 ? "close to " + esc(e.target) + "’s limit" : "fits comfortably in " + esc(e.target)}</span>`);
  if (e.saved > 0) parts.push(`shortened by ${e.saved.toLocaleString()} tokens`);
  const s = e.scrubbed || {}, removed = (s.keys || 0) + (s.emails || 0) + (s.phones || 0) + (s.paths || 0);
  if (removed) parts.push(`hid ${removed} private detail${removed === 1 ? "" : "s"}`);
  if (e.cost != null) parts.push(`≈ $${e.cost} as API input`);
  box.innerHTML = parts.join(" · ");
}

/* the chats that match the search box (or all of them when it's empty) */
function visibleChats() {
  const q = S.query.trim().toLowerCase();
  if (!q) return S.chats;
  return S.chats.filter(c => `${c.title} ${c.source} ${c.created}`.toLowerCase().includes(q) || S.hits[c.id]);
}
function renderChats() {
  const L = $("#chatList");
  const n = S.chats.length;
  $("#chipChats").textContent = S.scanning && !n ? "Looking for chats…" : `${n} chat${n === 1 ? "" : "s"} & projects`;
  if (!n) {
    L.innerHTML = '<div class="empty"><b>No chats yet</b>Add a chat file, paste some text, or bring a project folder with the buttons above.</div>';
    return;
  }
  const shown = visibleChats();
  $("#searchNote").textContent = S.query.trim() ? `${shown.length} of ${n}` : "";
  if (!shown.length) {
    L.innerHTML = `<div class="empty"><b>No chats match “${esc(S.query.trim())}”</b>Try a different word, or clear the search box.</div>`;
    return;
  }
  const byDate = (S.settings.group_by || "date") === "date";
  const sorted = [...shown].sort((a, b) => String(b.created).localeCompare(String(a.created)));   // newest first
  const groups = {};
  if (byDate) {
    for (const g of DATE_GROUPS) groups[g] = [];
    sorted.forEach(c => groups[dateGroup(c.created)].push(c));
  } else {
    sorted.forEach(c => (groups[c.source] = groups[c.source] || []).push(c));
  }
  $("#groupSeg").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.g === (byDate ? "date" : "app")));
  L.innerHTML = Object.entries(groups).filter(([, items]) => items.length).map(([name, items]) => `
    <button class="grp-head" data-grp="${esc(name)}" title="Click to tick or untick this whole group">${byDate ? "" : `<span class="gicon">${iconFor(name)}</span>`}${byDate ? esc(name) : "From " + esc(name)} <span class="count">${items.length}</span></button>
    ${items.map(c => `
      <div class="card ${S.sel.has(c.id) ? "on" : ""}" data-id="${esc(c.id)}" draggable="true">
        <span class="chk">✓</span>
        <div class="t"><b title="${esc(c.title)}">${esc(c.title)}</b><small title="${tipFor(c)}">${c.kind === "project" ? "Code project" + (c.mode && c.mode !== "full" ? " (" + esc(c.mode) + ")" : "") : Number(c.count) + " messages"} · ${esc(pagesOf(c.tokens))} · <span class="when">${esc(relDate(c.created))}</span>${byDate ? "" : ""}</small>${S.hits[c.id] && S.query.trim() ? `<span class="snip">${esc(S.hits[c.id])}</span>` : ""}</div>
        <button class="eye" data-view="${esc(c.id)}" title="Read this chat">◉</button>
        <button class="ren" data-rename="${esc(c.id)}" title="Rename">✎</button>
        ${c.saved ? `<button class="x" data-del="${esc(c.id)}" title="Remove from ChatBridge (the original stays where it is)">×</button>` : ""}
      </div>`).join("")}`).join("");
}

/* plain-language helpers for the list */
const DATE_GROUPS = ["Today", "Yesterday", "Last 7 days", "Last 30 days", "Older"];
function ageDays(s) {
  const m = String(s || "").match(/(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3]), now = new Date();
  return Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - d) / 86400000);
}
function dateGroup(s) {
  const a = ageDays(s);
  return a === null ? "Older" : a <= 0 ? "Today" : a === 1 ? "Yesterday" : a <= 7 ? "Last 7 days" : a <= 30 ? "Last 30 days" : "Older";
}
function relDate(s) {
  const a = ageDays(s);
  if (a === null) return "";
  if (a <= 0) return "today";
  if (a === 1) return "yesterday";
  if (a < 7) return a + " days ago";
  const m = String(s).match(/(\d{4})-(\d{2})-(\d{2})/), d = new Date(+m[1], +m[2] - 1, +m[3]);
  return d.toLocaleDateString(undefined, {month: "short", day: "numeric", year: a > 300 ? "numeric" : undefined});
}
const pagesOf = t => {            // "about 6 pages" reads better than a token count (a page is roughly 650 tokens)
  const p = Math.round((t || 0) / 650);
  return t < 250 ? "a short note" : p <= 1 ? "about 1 page" : "about " + p + " pages";
};
const tipFor = c => c.real_tokens ? `About ${(c.tokens || 0).toLocaleString()} tokens (how AI measures length). Claude Code recorded ${c.real_tokens.toLocaleString()} tokens processed while this chat was running.`
                                  : `About ${(c.tokens || 0).toLocaleString()} tokens. Tokens are how AI measures length: roughly 650 per page.`;

function appTile(key, name, sub, iconHtml, bg) {
  const on = S.target === key ? "on" : "";
  const ic = iconHtml ? `<span class="ic" style="background:${bg || "transparent"}">${iconHtml}</span>`
                      : `<span class="ic" style="background:${colorFor(name)}">${esc(name[0].toUpperCase())}</span>`;
  return `<button class="app-tile ${on}" data-key="${esc(key)}">${ic}<b>${esc(name)}</b><small>${sub}</small></button>`;
}
function renderApps() {
  const kindSub = {"Desktop app": "Installed", "Possible AI app": "Might be an AI app", "CLI tool": "Terminal tool", "Local server": "Runs on this PC"};
  const tiles = S.apps.filter(a => a.enabled !== false).map(a => {
    let sub = esc(kindSub[a.kind] || a.kind);
    if (a.kind === "Local server") sub += ` · ${a.models.length} model${a.models.length === 1 ? "" : "s"}`;
    if (a.tested === true) sub = '<span class="ok">tested ✓</span> · ' + sub;
    if (a.tested === false) sub = '<span class="bad">didn’t work yet</span>';
    if (a.icon) return appTile(a.key, a.name, sub, `<img src="${a.icon}" alt="">`);
    return appTile(a.key, a.name, sub, a.kind === "CLI tool" ? "&gt;_" : "", a.kind === "CLI tool" ? "#b4b2a9" : "");
  });
  S.web.filter(w => w.enabled).forEach(w => tiles.push(appTile(w.key, w.name.replace(" (website)", ""), "Website · opens in your browser", "")));
  tiles.push(appTile("copy", "Copy only", "Paste it anywhere", "⧉", "#b4b2a9"));
  $("#appGrid").innerHTML = tiles.join("");
  const real = S.apps.filter(a => a.kind === "Desktop app" || a.kind === "Local server").length;
  $("#dotApps").classList.toggle("spin", S.scanning);
  $("#chipApps").textContent = S.scanning && !S.apps.length ? "Looking for your AI apps…" : `${S.apps.length} app${S.apps.length === 1 ? "" : "s"} found`;
}

function renderSummary() {
  const ids = [...S.sel].filter(id => S.chats.some(c => c.id === id));
  const n = ids.length, items = `${n} chat${n === 1 ? "" : "s"}`;
  const app = typeof S.target === "number" ? S.apps.find(a => a.key === S.target) : null;
  const web = typeof S.target === "string" && S.target.startsWith("web:") ? S.web.find(w => w.key === S.target) : null;
  const name = S.target === "copy" ? "the clipboard" : app ? app.name : web ? web.name.replace(" (website)", "") : null;
  let msg, label = "Send", ready = n > 0 && S.target !== null;
  if (!n) msg = "Tick a chat on the left and choose where it should go.";
  else if (!name) msg = `<b>${items}</b> ticked. Now choose where to send ${n === 1 ? "it" : "them"}.`;
  else if (web) { msg = `<b>${items}</b> will be copied and <b>${esc(name)}</b> opens in your browser. Click its message box and press Ctrl+V — or attach the saved file.`; label = "Open " + name; }
  else if (S.target === "copy") { msg = `<b>${items}</b> will be copied. Paste ${n === 1 ? "it" : "them"} anywhere with Ctrl+V.`; label = "Copy"; }
  else if (app && app.kind === "Local server") { msg = `<b>${items}</b> will load into <b>${esc(name)}</b> and you’ll keep chatting right here.`; label = "Continue here"; }
  else if (app && app.kind === "CLI tool") { msg = `<b>${items}</b> will be copied and <b>${esc(name)}</b> opens in a terminal. Right-click there to paste.`; label = "Send to " + name; }
  else { msg = `<b>${items}</b> → <b>${esc(name)}</b>. It opens and the chat is pasted in. You press Enter.`; label = "Send to " + name; }
  $("#summary").innerHTML = msg;
  $("#sendLabel").textContent = S.busy ? "Working…" : label;
  $("#btnSend").classList.toggle("off", !ready || S.busy);
  $("#btnSend").dataset.ready = ready ? "1" : "";
  scheduleEstimate();
}
const renderAll = () => { renderChats(); renderApps(); renderSummary(); };

/* ---------- events ---------- */
$("#chatList").addEventListener("click", async e => {
  const del = e.target.closest("[data-del]"), view = e.target.closest("[data-view]"), grp = e.target.closest("[data-grp]"), card = e.target.closest(".card");
  if (del) {
    e.stopPropagation();
    S.sel.delete(del.dataset.del);
    S.chats = await api().delete_chats([del.dataset.del]);
    return renderAll();
  }
  if (view) {
    e.stopPropagation();
    const p = await api().preview(view.dataset.view);
    if (!p) return;
    $("#vTitle").textContent = p.title;
    $("#vSub").textContent = (p.source || "") + (p.kind === "project" ? " · project files" : "");
    $("#vBody").innerHTML = p.messages.map(m => `<div class="bubble ${m.role === "user" ? "u" : "a"}">${esc(m.content)}</div>`).join("");
    return open("#mPreview");
  }
  if (grp) {
    const ids = S.chats.filter(c => c.source === grp.dataset.grp).map(c => c.id);
    const allOn = ids.every(i => S.sel.has(i));
    ids.forEach(i => allOn ? S.sel.delete(i) : S.sel.add(i));
    return renderAll();
  }
  if (card) { const id = card.dataset.id; S.sel.has(id) ? S.sel.delete(id) : S.sel.add(id); renderAll(); }
});
$("#appGrid").addEventListener("click", e => {
  const t = e.target.closest(".app-tile");
  if (!t) return;
  const k = t.dataset.key;
  S.target = /^\d+$/.test(k) ? Number(k) : k;
  renderApps(); renderSummary();
});
/* drag a chat onto an app to send it straight away */
let dragId = null;
$("#chatList").addEventListener("dragstart", e => {
  const card = e.target.closest(".card");
  if (!card) return;
  dragId = card.dataset.id; card.classList.add("dragging");
  e.dataTransfer.setData("text/plain", dragId); e.dataTransfer.effectAllowed = "copy";
});
$("#chatList").addEventListener("dragend", e => { dragId = null; document.querySelectorAll(".dragging,.drop").forEach(x => x.classList.remove("dragging", "drop")); });
$("#appGrid").addEventListener("dragover", e => { const t = e.target.closest(".app-tile"); if (!t || !dragId) return; e.preventDefault(); document.querySelectorAll(".drop").forEach(x => x.classList.remove("drop")); t.classList.add("drop"); });
$("#appGrid").addEventListener("dragleave", e => { const t = e.target.closest(".app-tile"); if (t) t.classList.remove("drop"); });
$("#appGrid").addEventListener("drop", e => {
  const t = e.target.closest(".app-tile");
  if (!t || !dragId) return;
  e.preventDefault(); t.classList.remove("drop");
  if (!S.sel.has(dragId)) { S.sel.clear(); S.sel.add(dragId); }       // dropping an unticked chat sends just that one
  const k = t.dataset.key;
  S.target = /^\d+$/.test(k) ? Number(k) : k;
  renderAll(); doSend();
});
$("#oCompact").onchange = $("#oScrub").onchange = () => { renderSummary(); api().save_settings({...S.settings, compact: $("#oCompact").checked, scrub: $("#oScrub").checked}); };

$("#btnAll").onclick = () => { visibleChats().forEach(c => S.sel.add(c.id)); renderAll(); };   // while searching, only the matches

/* how the list is arranged, remembered between visits */
$("#groupSeg").addEventListener("click", async e => {
  const b = e.target.closest("[data-g]");
  if (!b) return;
  S.settings.group_by = b.dataset.g; renderChats();
  api().save_settings({...S.settings, group_by: b.dataset.g});
});
$("#btnHelp").onclick = () => open("#mHelp");

/* rename a chat to something you'll recognise */
let renameId = null;
$("#chatList").addEventListener("click", e => {
  const b = e.target.closest("[data-rename]");
  if (!b) return;
  e.stopPropagation(); renameId = b.dataset.rename;
  $("#rnInput").value = (S.chats.find(c => c.id === renameId) || {}).title || ""; open("#mRename"); $("#rnInput").select();
}, true);
const doRename = async () => {
  const r = await api().rename_chat(renameId, $("#rnInput").value);
  if (r.error) return toast(r.error, "warn");
  S.chats = r.chats; close("#mRename"); renderAll();
};
$("#rnSave").onclick = doRename;
$("#rnInput").addEventListener("keydown", e => { if (e.key === "Enter") doRename(); });

/* search: titles right away, what was said after a short pause */
let searchTimer;
$("#chatSearch").addEventListener("input", e => {
  S.query = e.target.value;
  renderChats();
  clearTimeout(searchTimer);
  const q = S.query.trim();
  if (q.length < 2) { S.hits = {}; return renderChats(); }
  searchTimer = setTimeout(async () => {
    const r = await api().search_chats(q);
    if (S.query.trim() === q) { S.hits = r.hits || {}; renderChats(); }
  }, 250);
});

/* Refresh: look again for newly installed AI apps and new chats */
$("#btnRefresh").onclick = () => rescan(true);

/* choose which tools appear on the right */
function toolRow(t, icon) {
  return `<label class="tool"><input type="checkbox" data-name="${esc(t.name)}" ${t.enabled ? "checked" : ""} style="accent-color:var(--accent);width:18px;height:18px">
    <span class="ic" style="background:${icon ? "transparent" : colorFor(t.name)}">${icon ? `<img src="${icon}" alt="">` : esc(t.name[0].toUpperCase())}</span>
    <span class="n">${esc(t.name)}<br><small>${esc(t.kind)}</small></span>
    ${t.kind === "Desktop app" || t.kind === "Possible AI app" ? `<button class="link" data-test="${esc(t.key)}" title="Pastes a harmless test line into the app. Nothing is sent.">Test</button>` : ""}</label>`;
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-test]");
  if (!b) return;
  e.preventDefault(); e.stopPropagation();
  close("#mTools"); S.target = Number(b.dataset.test); renderAll(); runTest(S.target);
}, true);
function openTools(first) {
  $("#tlTitle").textContent = first ? "Which AI tools do you use?" : "Choose your AI tools";
  $("#tlSub").textContent = first ? "ChatBridge looked on this PC and found these. Tick the ones you want to send chats to — you can change this any time."
                                  : "Tick the ones you want to send chats to. Missing one? Add it at the bottom.";
  $("#tlApps").innerHTML = S.apps.length ? S.apps.map(a => toolRow(a, a.icon)).join("") : '<div class="empty" style="padding:14px">Nothing found yet. Install an AI app and press ↻ Refresh.</div>';
  $("#tlWeb").innerHTML = S.web.map(w => toolRow(w, null)).join("");
  $("#tlCancel").hidden = !!first;
  open("#mTools");
}
$("#btnTools").onclick = () => openTools(false);
$("#tlAll").onclick = () => document.querySelectorAll("#mTools input[type=checkbox]").forEach(c => c.checked = true);
$("#tlNone").onclick = () => document.querySelectorAll("#mTools input[type=checkbox]").forEach(c => c.checked = false);
$("#tlSave").onclick = async () => {
  const names = [...document.querySelectorAll("#mTools input[type=checkbox]:checked")].map(c => c.dataset.name);
  const r = await api().set_tools(names);
  S.apps = r.apps; S.web = r.web; S.toolsChosen = true;
  if (typeof S.target === "number" && !(S.apps.find(a => a.key === S.target) || {}).enabled) S.target = null;
  if (typeof S.target === "string" && S.target.startsWith("web:") && !(S.web.find(w => w.key === S.target) || {}).enabled) S.target = null;
  close("#mTools"); renderAll();
  toast(names.length ? `Showing ${names.length} tool${names.length === 1 ? "" : "s"}.` : "No tools ticked — only “Copy only” will show.", "good", 3000);
};
const maybeAskTools = () => {   // once per session, and never on top of the welcome or what's-new windows
  if (!S.toolsChosen && (S.apps.length || S.web.length) && !S.askedTools && $("#mWelcome").hidden && $("#mNew").hidden) { S.askedTools = true; openTools(true); }
};

/* save the ticked chats as a file you can attach on any AI website */
$("#btnExport").onclick = async () => {
  const ids = selectedIds();
  if (!ids.length) return toast("Tick at least one chat on the left first.", "warn");
  const r = await api().export_selected(ids, opts());
  if (r.cancelled) return;
  if (r.error) return toast(r.error, "err");
  toast(`Saved ${r.name}. Attach it on any AI website, or import the .json back into ChatBridge later.`, "good", 10000,
        {label: "Show file", fn: () => api().show_file(r.path)});
};
$("#btnNone").onclick = () => { S.sel.clear(); renderAll(); };
$("#btnTheme").onclick = () => {
  const keys = Object.keys(THEMES);
  S.settings.theme = keys[(keys.indexOf(S.settings.theme) + 1) % keys.length];
  applySettings(); persistLook(); toast("Theme: " + THEMES[S.settings.theme], "", 1800);
};
$("#btnBigger").onclick = () => { S.settings.size = Math.min(26, (S.settings.size || 16) + 1); applySettings(); persistLook(); };
$("#btnSmaller").onclick = () => { S.settings.size = Math.max(11, (S.settings.size || 16) - 1); applySettings(); persistLook(); };
$("#aEdit").onclick = () => api().edit_profiles();
$("#aAdd").onclick = async () => {
  const r = await api().add_app($("#aName").value);
  if (r.error) return toast(r.error, "err");
  close("#mTools"); $("#aName").value = ""; await rescan(true); openTools(false);
};

$("#btnFile").onclick = async () => {
  const r = await api().import_files();
  S.chats = r.chats;
  (r.ids || []).forEach(i => S.sel.add(i));
  renderAll();
  if (r.errors && r.errors.length) toast(r.errors.join("\n"), "err", 8000);
  else if (r.ids && r.ids.length) toast(`Added ${r.ids.length} chat${r.ids.length === 1 ? "" : "s"}.`, "good");
};
$("#btnPaste").onclick = () => { open("#mPaste"); $("#pText").focus(); };
$("#pAdd").onclick = async () => {
  const r = await api().add_text($("#pTitle").value, $("#pSource").value, $("#pText").value);
  if (r.error) return toast(r.error, "err");
  S.chats = r.chats; S.sel.add(r.id); $("#pText").value = ""; close("#mPaste"); renderAll(); toast("Chat added.", "good");
};

let prj = null;
$("#btnProject").onclick = async () => {
  toast("Reading the folder…", "work", 0);
  const r = await api().pick_project();
  $("#toast").classList.remove("show");
  if (!r) return;
  if (r.error) return toast(r.error, "err");
  prj = {...r, on: new Set(r.files.filter(f => f.on).map(f => f.i))};
  $("#prjTitle").textContent = "Bring “" + r.name + "” along";
  $("#prjRoot").textContent = r.root;
  $("#prjSkipped").textContent = r.skipped.length
    ? "Left out for safety: " + r.skipped.slice(0, 4).map(s => s.rel).join(", ") + (r.skipped.length > 4 ? ` and ${r.skipped.length - 4} more` : "") : "";
  document.querySelector('input[name=pmode][value=full]').checked = true;
  const counts = {};
  r.files.forEach(f => counts[f.type] = (counts[f.type] || 0) + 1);
  const labels = {code: "Code", config: "Config (yaml, json…)", docs: "Docs", tests: "Tests"};
  $("#prjTypes").innerHTML = Object.keys(labels).filter(t => counts[t]).map(t => `<button class="chipbtn" data-type="${t}">${labels[t]} · ${counts[t]}</button>`).join("");
  renderPrj(); open("#mProject");
};
const prjMode = () => document.querySelector("input[name=pmode]:checked").value;
let prjTimer;
function renderPrj() {
  $("#prjFiles").innerHTML = prj.files.map(f => `<div class="file" data-i="${f.i}"><span class="chk" style="${prj.on.has(f.i) ? "background:var(--accent);border-color:var(--accent);color:var(--accent-ink)" : ""}">✓</span><span class="n">${esc(f.rel)}</span><small>${f.type} · ${f.size.toLocaleString()} chars</small></div>`).join("");
  document.querySelectorAll("#prjTypes .chipbtn").forEach(b => {
    const ofType = prj.files.filter(f => f.type === b.dataset.type);
    b.classList.toggle("on", ofType.length > 0 && ofType.every(f => prj.on.has(f.i)));
  });
  $("#prjTotal").textContent = `${prj.on.size} of ${prj.files.length} files · working out the size…`;
  clearTimeout(prjTimer);
  prjTimer = setTimeout(async () => {
    const s = await api().project_size([...prj.on], prjMode());
    const budget = prj.budget / 4, over = s.tokens > budget;
    $("#prjMeter").classList.toggle("over", over);
    $("#prjMeter i").style.width = Math.min(100, s.tokens / budget * 100) + "%";
    $("#prjTotal").textContent = `${prj.on.size} of ${prj.files.length} files · about ${s.tokens.toLocaleString()} tokens as sent` + (over ? " — large; some apps may cut it off. Try “Outline big files”." : "");
  }, 200);
}
$("#prjFiles").onclick = e => { const f = e.target.closest(".file"); if (!f) return; const i = Number(f.dataset.i); prj.on.has(i) ? prj.on.delete(i) : prj.on.add(i); renderPrj(); };
$("#prjTypes").onclick = e => {
  const b = e.target.closest(".chipbtn");
  if (!b) return;
  const ofType = prj.files.filter(f => f.type === b.dataset.type);
  const allOn = ofType.every(f => prj.on.has(f.i));
  ofType.forEach(f => allOn ? prj.on.delete(f.i) : prj.on.add(f.i));
  renderPrj();
};
$("#prjModes").onchange = renderPrj;
$("#prjAll").onclick = () => { prj.files.forEach(f => prj.on.add(f.i)); renderPrj(); };
$("#prjNone").onclick = () => { prj.on.clear(); renderPrj(); };
$("#prjAdd").onclick = async () => {
  const r = await api().add_project([...prj.on], prjMode());
  if (r.error) return toast(r.error, "err");
  S.chats = r.chats; S.sel.add(r.id); close("#mProject"); renderAll(); toast("Project added and ticked.", "good");
};

$("#btnSettings").onclick = () => {
  const s = S.settings;
  $("#sTheme").innerHTML = Object.entries(THEMES).map(([k, v]) => `<option value="${k}" ${k === s.theme ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#sFont").innerHTML = Object.entries(FONTS).map(([k, v]) => `<option value="${k}" ${k === s.font ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#sAuto").checked = s.autopaste !== false;
  $("#sUpdate").checked = s.update_check !== false; $("#sVersion").textContent = "You have version " + (s.version || "");
  $("#sToken").value = s.capture_token || ""; $("#sPort").textContent = s.capture_port || "not running";
  $("#sAbout").value = s.about_me || ""; $("#sPriceIn").value = s.price_in || ""; $("#sPriceOut").value = s.price_out || "";
  open("#mSettings");
};
/* updates: ChatBridge only tells you; you choose whether to download */
function showUpdate(info, manual) {
  if (info && info.status === "available") {
    const c = $("#chipUpdate");
    c.hidden = false; c.textContent = "Update available: " + info.version; c.dataset.url = info.url;
    c.dataset.version = info.version; c.dataset.notes = info.notes || "";
    if (manual) toast(`Version ${info.version} is available. Click the chip at the top to download it.`, "good", 7000);
  } else if (manual) {
    toast(!info || info.status === "offline" ? "Couldn't reach GitHub. Check your internet connection."
          : info.status === "none" ? "No releases have been published yet." : `You're up to date (version ${info.current}).`,
          !info || info.status === "offline" ? "warn" : "good", 5000);
  }
}
/* very small markdown: "### heading", "- bullet", "**bold**", `code` */
function mdLite(text) {
  let html = "", list = false;
  for (const raw of String(text || "").split("\n")) {
    const line = esc(raw).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
    const li = line.match(/^\s*[-*]\s+(.*)$/);
    if (li) { if (!list) { html += '<ul style="margin:4px 0 8px 18px;padding:0">'; list = true; } html += `<li>${li[1]}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    if (/^#{1,4}\s+/.test(line)) html += `<div style="font-weight:600;margin:10px 0 2px">${line.replace(/^#+\s+/, "")}</div>`;
    else if (line.trim()) html += `<div>${line}</div>`;
  }
  return html + (list ? "</ul>" : "");
}
$("#chipUpdate").onclick = e => {                    // show the release notes first; the download is one more click
  e.preventDefault();
  const c = $("#chipUpdate");
  $("#nTitle").textContent = "ChatBridge " + (c.dataset.version || "") + " is available";
  $("#nBody").innerHTML = mdLite(c.dataset.notes) || "<div>See the download page for what changed.</div>";
  $("#nGo").hidden = false; open("#mNew");
};
$("#nGo").onclick = () => { api().open_release($("#chipUpdate").dataset.url); close("#mNew"); };
async function showWhatsNew() {
  let w; try { w = await api().whats_new(); } catch (e) { return; }
  if (!w || !w.show) return;
  $("#nTitle").textContent = "What's new in ChatBridge " + w.version;
  $("#nBody").innerHTML = w.sections.map(s => `<div style="font-weight:600;margin-top:6px">Version ${esc(s.version)}</div>${mdLite(s.body)}`).join("");
  $("#nGo").hidden = true; open("#mNew");
}
$("#sCheckNow").onclick = async () => { toast("Checking…", "work", 0); showUpdate(await api().check_update(true), true); };
$("#sCopyToken").onclick = async () => {
  const t = $("#sToken"); t.select();
  try { await navigator.clipboard.writeText(t.value); } catch (e) { document.execCommand("copy"); }
  toast("Pairing code copied. Paste it into the extension.", "good", 3000);
};
$("#sExt").onclick = async () => { const r = await api().open_extension_folder(); if (r.error) toast(r.error, "warn"); };
window.onCaptured = info => {          // a chat arrived from the browser extension
  S.chats = info.chats; S.sel.add(info.id); renderAll();
  toast(`Saved “${info.title}” from ${info.source} (${info.count} messages).`, "good", 6000);
};
$("#sTheme").onchange = () => { S.settings.theme = $("#sTheme").value; applySettings(); };
$("#sFont").onchange = () => { S.settings.font = $("#sFont").value; applySettings(); };
$("#sSave").onclick = async () => {
  S.settings = await api().save_settings({autopaste: $("#sAuto").checked, theme: $("#sTheme").value, font: $("#sFont").value, size: S.settings.size,
    update_check: $("#sUpdate").checked, about_me: $("#sAbout").value, price_in: $("#sPriceIn").value.trim(), price_out: $("#sPriceOut").value.trim()});
  close("#mSettings"); toast("Settings saved.", "good"); scheduleEstimate();
};

/* ---------- sending ---------- */
async function doSend() {
  if (S.busy) return;
  const ids = selectedIds();
  if (!ids.length) return toast("Tick at least one chat on the left first.", "warn");
  if (S.target === null) return toast("Choose where to send it on the right.", "warn");
  S.busy = true; renderSummary();
  const r = await api().send(ids, S.target, opts());
  if (r.error) { S.busy = false; renderSummary(); return toast(r.error, "warn"); }
  S.chats = r.chats; S.settings = r.settings || S.settings; renderChats();
  toast("Working…", "work", 0);
}
$("#btnSend").onclick = doSend;

/* history: what was sent where, with send-again */
$("#btnHistory").onclick = async () => {
  const h = await api().get_history();
  $("#histBody").innerHTML = h.length ? h.map((e, i) => `
    <div class="hrow"><div class="t"><b>${esc(e.titles.join(", "))}</b><small>${esc(e.time)} → ${esc(e.target)} · ~${(e.tokens || 0).toLocaleString()} tokens${e.opts && e.opts.compact ? " · compact" : ""}${e.opts && e.opts.scrub ? " · scrubbed" : ""}</small></div>
      <button class="btn" data-again="${i}">Send again</button></div>`).join("")
    : '<div class="empty"><b>Nothing sent yet</b>Chats you send will be listed here.</div>';
  $("#histBody").dataset.items = JSON.stringify(h);
  open("#mHistory");
};
$("#histBody").onclick = e => {
  const b = e.target.closest("[data-again]");
  if (!b) return;
  const h = JSON.parse($("#histBody").dataset.items)[Number(b.dataset.again)];
  const live = h.ids.filter(id => S.chats.some(c => c.id === id));
  if (!live.length) return toast("Those chats aren’t in the list any more.", "warn");
  const app = S.apps.find(a => a.name === h.target), site = S.web.find(w => w.name === h.target);
  S.sel = new Set(live); S.target = h.target_key === "copy" ? "copy" : app ? app.key : site ? site.key : null;
  if (S.target === null) return toast(`${h.target} isn’t available right now.`, "warn");
  $("#oCompact").checked = !!(h.opts || {}).compact; $("#oScrub").checked = !!(h.opts || {}).scrub;
  close("#mHistory"); renderAll(); doSend();
};
async function runTest(key) {   // started from the "Test" link next to an installed app in Choose tools
  if (S.busy) return;
  S.busy = true; renderSummary();
  const r = await api().test_app(key);
  if (r.error) { S.busy = false; renderSummary(); return toast(r.error, "warn"); }
  toast("Testing… don’t click elsewhere. A harmless test line is pasted; nothing is sent.", "work", 0);
}
let testName = "";
$("#tYes").onclick = async () => { close("#mTest"); S.apps = await api().record_compat(testName, true); renderAll(); toast(testName + " marked as working.", "good"); };
$("#tNo").onclick = async () => { close("#mTest"); S.apps = await api().record_compat(testName, false); renderAll(); toast(testName + " marked as not working yet.", "warn"); };

window.onProgress = p => {
  if (p.state === "working") return toast(p.msg, "work", 0);
  if (p.state === "chat") { S.busy = false; renderSummary(); $("#toast").classList.remove("show"); return startChat(p); }
  if (p.state === "test") {
    S.busy = false; renderSummary(); $("#toast").classList.remove("show");
    testName = p.name;
    if (!p.pasted) return api().record_compat(p.name, false).then(a => { S.apps = a; renderAll(); toast(p.name + ": the test didn’t reach the app. Marked as not working yet.", "warn", 8000); });
    $("#tTitle").textContent = "Did it work?";
    $("#tBody").innerHTML = `Did “<b>${esc(p.marker)}</b>” appear in ${esc(p.name)}’s message box?`;
    return open("#mTest");
  }
  S.busy = false; renderSummary();
  toast(p.msg, {done: "good", warn: "warn", error: "err"}[p.state] || "", p.state === "done" ? 14000 : 12000,
        p.file ? {label: "Show file", fn: () => api().show_file(p.file)} : null);
};

/* ---------- chatting with a local or API model ---------- */
let hist = [], chatModel = null;
function bubble(role, text) { const d = document.createElement("div"); d.className = "bubble " + (role === "user" ? "u" : "a"); d.textContent = text; $("#msgs").appendChild(d); $("#msgs").scrollTop = 1e9; return d; }
async function askModel(visible) {
  const wait = bubble("assistant", "…");
  const r = await api().chat(hist, chatModel);
  if (r.error) { wait.textContent = r.error; wait.style.borderColor = "var(--danger)"; hist.pop(); return; }
  wait.textContent = r.reply; hist.push({role: "assistant", content: r.reply});
}
function startChat(p) {
  $("#dTitle").textContent = "Chatting with " + p.label;
  $("#msgs").innerHTML = ""; hist = []; chatModel = p.model || null;
  const sel = $("#dModel");
  sel.hidden = !(p.models && p.models.length > 1);
  sel.innerHTML = (p.models || []).map(m => `<option ${m === p.model ? "selected" : ""}>${esc(m)}</option>`).join("");
  $("#drawer").hidden = false;
  hist.push({role: "user", content: "In one or two sentences, tell me where we left off, then wait for my next message."});
  askModel();
}
/* the side chat is only used for local models (Ollama, LM Studio...) that run on this PC */
$("#dModel").onchange = e => { chatModel = e.target.value; };
$("#dClose").onclick = () => { $("#drawer").hidden = true; };
async function sendChat() {
  const t = $("#dInput").value.trim();
  if (!t) return;
  $("#dInput").value = ""; bubble("user", t); hist.push({role: "user", content: t}); askModel();
}
$("#dSend").onclick = sendChat;
$("#dInput").addEventListener("keydown", e => { if (e.key === "Enter" && e.ctrlKey) sendChat(); });

/* ---------- startup ---------- */
async function rescan(manual = false) {
  S.scanning = true; renderApps();
  const btn = $("#btnRefresh"); btn.classList.add("busy"); btn.textContent = "↻ Looking…";
  const keep = typeof S.target === "number" ? (S.apps.find(a => a.key === S.target) || {}).name : null;  // app numbers can change on a rescan
  const had = new Set(S.apps.map(a => a.name)), hadChats = new Set(S.chats.map(c => c.id));
  try {
    const r = await api().scan_all();
    S.chats = r.chats; S.apps = r.apps; S.web = r.web || S.web; S.toolsChosen = !!r.tools_chosen;
  } catch (e) { toast("Scan problem: " + e, "err"); }
  if (keep) { const a = S.apps.find(a => a.name === keep); S.target = a ? a.key : null; }
  S.scanning = false; rememberTarget(); renderAll();
  btn.classList.remove("busy"); btn.textContent = "↻ Refresh";
  if (manual) {
    const newApps = S.apps.filter(a => !had.has(a.name)).map(a => a.name), newChats = S.chats.filter(c => !hadChats.has(c.id)).length;
    toast(newApps.length || newChats
      ? `Found ${newApps.length ? "new tool" + (newApps.length > 1 ? "s" : "") + ": " + newApps.join(", ") : ""}${newApps.length && newChats ? " and " : ""}${newChats ? newChats + " new chat" + (newChats > 1 ? "s" : "") : ""}.`
      : `Nothing new — ${S.apps.length} tool${S.apps.length === 1 ? "" : "s"} and ${S.chats.length} chat${S.chats.length === 1 ? "" : "s"} found.`, "good", 5000);
  } else maybeAskTools();
}
async function start() {
  const b = await api().bootstrap();
  S.chats = b.chats; S.apps = b.apps; S.web = b.web || []; S.settings = b.settings; S.toolsChosen = !!b.tools_chosen;
  $("#oCompact").checked = !!b.settings.compact; $("#oScrub").checked = b.settings.scrub !== false;
  applySettings(); rememberTarget(); renderAll();
  if (!b.welcomed) { open("#mWelcome"); } else { showWhatsNew(); }   // new users get the welcome; people who updated get what's new
  if (!b.welcomed) api().whats_new();                                  // just records the version so it isn't "new" next time
  rescan();
  api().check_update(false).then(i => showUpdate(i, false)).catch(() => {});
}
/* remember the last place something was sent, so it's already chosen next time */
function rememberTarget() {
  const last = S.settings.last_target;
  if (S.target !== null || !last) return;
  const a = S.apps.find(a => a.name === last && a.enabled !== false), w = S.web.find(w => w.name === last && w.enabled);
  if (last === "copy") S.target = "copy"; else if (a) S.target = a.key; else if (w) S.target = w.key;
}
$("#wGo").onclick = () => { close("#mWelcome"); api().mark_welcomed(); maybeAskTools(); };
if (window.pywebview && window.pywebview.api) start(); else window.addEventListener("pywebviewready", start);
