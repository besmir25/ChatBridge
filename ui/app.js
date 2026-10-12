const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const S = {chats: [], apps: [], web: [], settings: {theme: "light", font: "sans", size: 17}, sel: new Set(), target: null, site: 0, busy: false, scanning: true,
           query: "", hits: {}, toolsChosen: false};
/* "web" is the single "A website" tile; the site inside it is chosen in a small list ("none" = I'll open it myself) */
const targetKey = () => S.target === "web" ? (S.site === "none" ? "web:none" : "web:" + S.site) : S.target;
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
const THEMES = {light: "Light", midnight: "Dark (teal)", tokyo: "Dark (blue)", gruvbox: "Dark (amber)", nord: "Dark (ice)"};
const FONTS = {sans: "Easy to read (Segoe UI)", code: "Programmer style (Cascadia Code)", consolas: "Programmer style (Consolas)"};
const SIZES = {14: "Smaller", 16: "Normal", 17: "Comfortable", 19: "Large", 22: "Extra large"};
function applySettings() {
  const s = S.settings;
  document.documentElement.dataset.theme = THEMES[s.theme] ? s.theme : "light";
  document.documentElement.dataset.font = FONTS[s.font] ? s.font : "sans";
  document.documentElement.style.setProperty("--fs", (s.size || 17) + "px");
}
/* ---------- rendering ---------- */
const kfmt = n => n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n || 0);
const opts = () => ({auto: true, into_open: !$("#intoRow").hidden && $("#intoOpen").checked});   // the app decides: private details hidden, long text shortened only when it needs to be
const selectedIds = () => [...S.sel].filter(id => S.chats.some(c => c.id === id));

let estTimer, estSeq = 0;
function scheduleEstimate() { clearTimeout(estTimer); estTimer = setTimeout(refreshEstimate, 250); }
async function refreshEstimate() {
  const ids = selectedIds(), box = $("#estimate"), seq = ++estSeq;
  if (!ids.length) { box.innerHTML = ""; return; }
  const e = await api().estimate(ids, targetKey(), opts());
  if (seq !== estSeq || !e) return;
  /* say something only when there's something to say, in plain words */
  const who = e.target ? esc(e.target.replace(" (website)", "")) : "the app";
  if (e.pct != null && e.pct > 100) box.innerHTML = `<span class="warn">This is a lot of text, even after shortening — ${who} may cut part of it off. Try fewer conversations.</span>`;
  else if (e.auto_compact) box.innerHTML = "It’s a long conversation, so ChatBridge will trim big blocks of code or output first.";
  else box.innerHTML = "";
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
  if (!n) {
    L.innerHTML = S.scanning ? '<div class="empty"><b>Looking for your conversations…</b></div>'
      : '<div class="empty"><b>No conversations yet</b>Add one from a file, or paste some text, with the links below.</div>';
    return;
  }
  const shown = visibleChats();
  $("#searchNote").textContent = S.query.trim() ? `${shown.length} of ${n}` : "";
  if (!shown.length) {
    L.innerHTML = `<div class="empty"><b>Nothing matches “${esc(S.query.trim())}”</b>Try a different word, or clear the search box.</div>`;
    return;
  }
  const sorted = [...shown].sort((a, b) => String(b.created).localeCompare(String(a.created)));   // newest first
  const groups = {};
  for (const g of DATE_GROUPS) groups[g] = [];
  sorted.forEach(c => groups[dateGroup(c.created)].push(c));
  L.innerHTML = Object.entries(groups).filter(([, items]) => items.length).map(([name, items]) => `
    <div class="grp-head">${esc(name)}</div>
    ${items.map(c => `
      <div class="card ${S.sel.has(c.id) ? "on" : ""}" data-id="${esc(c.id)}" draggable="true">
        <span class="chk">✓</span>
        <div class="t"><b title="${esc(c.title)}">${esc(c.title)}</b><small class="when">${c.kind === "project" ? "Code project · " : ""}${["Today", "Yesterday"].includes(name) ? "" : esc(relDate(c.created)) + (c.source && c.kind !== "project" ? " · " : "")}${c.source && c.kind !== "project" ? esc(c.source) : ""}</small>${S.hits[c.id] && S.query.trim() ? `<span class="snip">${esc(S.hits[c.id])}</span>` : ""}</div>
        <button class="eye" data-view="${esc(c.id)}" title="Read it">◉</button>
        ${c.kind === "project" ? "" : `<button class="sbtn" data-sections="${esc(c.id)}" title="Pick just some parts of this conversation">☰</button>`}
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

function appTile(key, name, iconHtml, bg) {
  const on = S.target === key ? "on" : "";
  const ic = iconHtml ? `<span class="ic" style="background:${bg || "transparent"}">${iconHtml}</span>`
                      : `<span class="ic" style="background:${colorFor(name)}">${esc(name[0].toUpperCase())}</span>`;
  return `<button class="app-tile ${on}" data-key="${esc(key)}">${ic}<b>${esc(name)}</b></button>`;
}
const siteName = w => w.name.replace(" (website)", "");
function renderApps() {
  const tiles = S.apps.filter(a => a.enabled !== false).map(a => {
    if (a.icon) return appTile(a.key, a.name, `<img src="${a.icon}" alt="">`);
    return appTile(a.key, a.name, a.kind === "CLI tool" ? "&gt;_" : "", a.kind === "CLI tool" ? "#b4b2a9" : "");
  });
  tiles.push(appTile("web", "A website", "🌐", "var(--chip)"));
  tiles.push(appTile("file", "A file", "💾", "var(--chip)"));
  tiles.push(appTile("copy", "Just copy it", "⧉", "var(--chip)"));
  $("#appGrid").innerHTML = tiles.join("");
  const ta = typeof S.target === "number" ? S.apps.find(a => a.key === S.target) : null;
  $("#intoRow").hidden = !(ta && ta.kind === "Desktop app");      // only desktop apps have a chat that can already be open
  /* the small list under the tiles, only while "A website" is chosen */
  const pick = $("#webPick");
  pick.hidden = S.target !== "web";
  if (!pick.hidden) {
    $("#webSite").innerHTML = S.web.map((w, i) => `<option value="${i}" ${S.site === i ? "selected" : ""}>${esc(siteName(w))}</option>`).join("")
      + `<option value="none" ${S.site === "none" ? "selected" : ""}>I’ll open it myself</option>`;
  }
  const real = S.apps.filter(a => a.enabled !== false && (a.kind === "Desktop app" || a.kind === "Local server")).map(a => a.name);
  const list = real.length > 1 ? real.slice(0, -1).join(", ") + " and " + real[real.length - 1] : real[0];
  $("#foundLine").innerHTML = S.scanning && !S.apps.length ? "Looking for AI apps on your computer…"
    : real.length ? `We found ${esc(list)} on your computer. <button class="link" id="btnNotRight">Not right?</button>`
    : `We didn’t find an AI app on your computer. <button class="link" id="btnNotRight">Add one</button>`;
}

function renderSummary() {
  const n = selectedIds().length, items = n === 1 ? "this conversation" : `these ${n} conversations`;
  const t = S.target;
  const app = typeof t === "number" ? S.apps.find(a => a.key === t) : null;
  const site = t === "web" && S.site !== "none" ? S.web[S.site] : null;
  let msg, label = "Continue", ready = n > 0 && t !== null;
  if (!n) msg = "Pick a conversation to get started.";
  else if (t === null) msg = "Now choose where you want to continue it.";
  else if (t === "web") {
    if (site) { msg = `ChatBridge copies ${items} and opens ${esc(siteName(site))}. Click its message box and press Ctrl+V.`; label = "Copy and open " + siteName(site); }
    else { msg = `ChatBridge copies ${items} and saves it as a file. Paste it into any AI website with Ctrl+V.`; label = "Copy it"; }
  }
  else if (t === "file") { msg = `ChatBridge saves ${items} as a file you can attach anywhere.`; label = "Save as a file…"; }
  else if (t === "copy") { msg = `ChatBridge copies ${items}. Paste it anywhere with Ctrl+V.`; label = "Copy it"; }
  else if (app && app.kind === "Local server") { msg = `${items[0].toUpperCase() + items.slice(1)} loads into ${esc(app.name)} and you keep chatting right here.`; label = "Continue with " + app.name; }
  else if (app && app.kind === "CLI tool") { msg = `ChatBridge copies ${items} and opens ${esc(app.name)} in a terminal. Right-click there to paste.`; label = "Continue in " + app.name; }
  else if (app) { msg = `${app.name} opens with ${items} ready to go. You press Enter when you’re ready.`; label = "Continue in " + app.name; }
  else msg = "Now choose where you want to continue it.";
  $("#summary").innerHTML = msg;
  $("#sendLabel").textContent = S.busy ? "Working…" : label;
  $("#btnSend").classList.toggle("off", !ready || S.busy);
  $("#btnSend").dataset.ready = ready ? "1" : "";
  scheduleEstimate();
}const renderAll = () => { renderChats(); renderApps(); renderSummary(); };

/* ---------- events ---------- */
$("#chatList").addEventListener("click", async e => {
  const del = e.target.closest("[data-del]"), view = e.target.closest("[data-view]"), grp = e.target.closest("[data-grp]"), card = e.target.closest(".card");
  const secBtn = e.target.closest("[data-sections]");
  if (secBtn) { e.stopPropagation(); return openSections(secBtn.dataset.sections); }
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
  const next = /^\d+$/.test(k) ? Number(k) : k;
  if (next !== S.target) $("#intoOpen").checked = false;       // "add to the open chat" is chosen per send, never carried over
  S.target = next;
  api().save_settings({...S.settings, last_target: lastName()});
  renderApps(); renderSummary();
});
$("#webSite").onchange = e => {
  S.site = e.target.value === "none" ? "none" : Number(e.target.value);
  api().save_settings({...S.settings, last_target: lastName()});
  renderSummary();
};
/* what we remember as "the last place you sent something" */
function lastName() { return S.target === "web" ? (S.site === "none" ? "a website" : (S.web[S.site] || {}).name) : S.target === "file" ? null : typeof S.target === "number" ? (S.apps.find(a => a.key === S.target) || {}).name : S.target; }
document.addEventListener("click", e => { if (e.target.id === "btnNotRight") openTools(false); });
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
$("#btnHelp").onclick = () => open("#mHelp");
$("#intoOpen").onchange = renderSummary;

/* ---------- sections: a long chat as a notebook ---------- */
const SEC = {id: null, data: null, sel: new Set(), titles: {}, open: new Set()};
async function openSections(id) {
  const d = await api().sections(id);
  if (d.error) return toast(d.error, "warn");
  Object.assign(SEC, {id, data: d, sel: new Set(), titles: {}, open: new Set()});
  $("#secTitle").textContent = "Choose parts of “" + d.title + "”";
  renderSections(); open("#mSections");
}
const secCells = s => SEC.data.cells.slice(s.start, s.end);
function renderSections() {
  const d = SEC.data;
  $("#secBody").innerHTML = d.sections.map((s, k) => {
    const cells = secCells(s), n = cells.filter(c => SEC.sel.has(c.i)).length;
    const state = n === 0 ? "" : n === cells.length ? "on" : "some";
    const isOpen = SEC.open.has(k);
    return `<div class="sec ${state}" data-k="${k}" style="margin-bottom:10px">
      <div class="sec-head"><button class="arrow" data-toggle="${k}" title="Open or close">${isOpen ? "▾" : "▸"}</button>
        <span class="chk" data-pick="${k}" title="Tick this whole section">${n === cells.length ? "✓" : n ? "–" : "✓"}</span>
        <input class="sectitle" data-title="${k}" value="${esc(SEC.titles[k] ?? s.title)}" maxlength="100" aria-label="Section name">
        ${s.tags.map(t => `<span class="tagchip">${esc(t)}</span>`).join("")}
        <span class="sec-meta">${cells.length} messages · ${esc(pagesOf(s.tokens))}</span></div>
      ${isOpen ? `<div class="cells">${cells.map(c => `<div class="cell ${SEC.sel.has(c.i) ? "on" : ""}" data-cell="${c.i}">
        <span class="chk">✓</span><span class="who">${c.role === "user" ? "You" : "AI"}</span><span class="txt">${esc(c.text)}${c.more ? "…" : ""}</span></div>`).join("")}</div>` : ""}
    </div>`;
  }).join("");
  const total = d.cells.length;
  $("#secCount").textContent = `${SEC.sel.size} of ${total} messages ticked`;
  $("#secGo").classList.toggle("off", !SEC.sel.size);
}
$("#secBody").addEventListener("click", e => {
  if (e.target.matches("input.sectitle")) return;
  const tog = e.target.closest("[data-toggle]"), pick = e.target.closest("[data-pick]"), cell = e.target.closest("[data-cell]");
  if (tog) { const k = Number(tog.dataset.toggle); SEC.open.has(k) ? SEC.open.delete(k) : SEC.open.add(k); }
  else if (pick) {
    const cells = secCells(SEC.data.sections[Number(pick.dataset.pick)]), all = cells.every(c => SEC.sel.has(c.i));
    cells.forEach(c => all ? SEC.sel.delete(c.i) : SEC.sel.add(c.i));
  } else if (cell) { const i = Number(cell.dataset.cell); SEC.sel.has(i) ? SEC.sel.delete(i) : SEC.sel.add(i); }
  else return;
  renderSections();
});
$("#secBody").addEventListener("change", e => { if (e.target.matches("input.sectitle")) SEC.titles[e.target.dataset.title] = e.target.value; });
$("#secAll").onclick = () => { SEC.data.cells.forEach(c => SEC.sel.add(c.i)); renderSections(); };
$("#secNone").onclick = () => { SEC.sel.clear(); renderSections(); };
$("#secOpenAll").onclick = () => { SEC.data.sections.forEach((s, k) => SEC.open.add(k)); renderSections(); };
$("#secCloseAll").onclick = () => { SEC.open.clear(); renderSections(); };
$("#secGo").onclick = async () => {
  if (!SEC.sel.size) return toast("Tick at least one section or message first.", "warn");
  const r = await api().make_part(SEC.id, [...SEC.sel], SEC.titles, $("#secOutline").checked);
  if (r.error) return toast(r.error, "warn");
  S.chats = r.chats; S.sel = new Set([r.id]); close("#mSections"); renderAll();
  toast("Made a new item with just those parts. Now choose where it should go.", "good", 6000);
};

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
  $("#tlTitle").textContent = "Which AI apps do you use?";
  $("#tlSub").textContent = "Tick the ones you want to see. Missing one? Add it at the bottom.";
  $("#tlApps").innerHTML = S.apps.length ? S.apps.map(a => toolRow(a, a.icon)).join("") : '<div class="empty" style="padding:14px">Nothing found yet. Install an AI app, then open More options and press Look again.</div>';
  $("#tlCancel").hidden = !!first;
  open("#mTools");
}
$("#btnTools").onclick = () => openTools(false);
$("#tlAll").onclick = () => document.querySelectorAll("#mTools input[type=checkbox]").forEach(c => c.checked = true);
$("#tlNone").onclick = () => document.querySelectorAll("#mTools input[type=checkbox]").forEach(c => c.checked = false);
$("#tlSave").onclick = async () => {
  const names = [...document.querySelectorAll("#mTools input[type=checkbox]:checked")].map(c => c.dataset.name);
  const r = await api().set_tools([...names, ...S.web.map(w => w.name)]);
  S.apps = r.apps; S.web = r.web; S.toolsChosen = true;
  if (typeof S.target === "number" && !(S.apps.find(a => a.key === S.target) || {}).enabled) S.target = null;
  close("#mTools"); renderAll();
  toast(names.length ? `Showing ${names.length} app${names.length === 1 ? "" : "s"}.` : "No apps ticked — you can still use a website, a file, or copy.", "good", 3000);
};
/* "A file": save the ticked conversations as a file you can attach on any AI website */
async function saveAsFile() {
  const r = await api().export_selected(selectedIds(), opts());
  S.busy = false; renderSummary();
  if (r.cancelled) return;
  if (r.error) return toast(r.error, "err");
  toast(`Saved ${r.name}. Attach it on any AI website, or add it back to ChatBridge later.`, "good", 10000,
        {label: "Show file", fn: () => api().show_file(r.path)});
}
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
  $("#sSize").innerHTML = Object.entries(SIZES).map(([k, v]) => `<option value="${k}" ${Number(k) === s.size ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#sScrub").checked = s.scrub !== false; $("#sCompact").checked = !!s.compact;
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
    if (manual) toast(`Version ${info.version} is available. Click “Update available” at the top to download it.`, "good", 7000);
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
  toast(`Saved “${info.title}” from ${info.source}.`, "good", 6000);
};
$("#sTheme").onchange = () => { S.settings.theme = $("#sTheme").value; applySettings(); };
$("#sFont").onchange = () => { S.settings.font = $("#sFont").value; applySettings(); };
$("#sSize").onchange = () => { S.settings.size = Number($("#sSize").value); applySettings(); };
$("#sSave").onclick = async () => {
  S.settings = await api().save_settings({autopaste: $("#sAuto").checked, theme: $("#sTheme").value, font: $("#sFont").value, size: Number($("#sSize").value), scrub: $("#sScrub").checked, compact: $("#sCompact").checked,
    update_check: $("#sUpdate").checked, about_me: $("#sAbout").value, price_in: $("#sPriceIn").value.trim(), price_out: $("#sPriceOut").value.trim()});
  close("#mSettings"); toast("Settings saved.", "good"); scheduleEstimate();
};

/* ---------- sending ---------- */
async function doSend() {
  if (S.busy) return;
  const ids = selectedIds();
  if (!ids.length) return toast("Pick a conversation first.", "warn");
  if (S.target === null) return toast("Choose where you want to continue it.", "warn");
  S.busy = true; renderSummary();
  if (S.target === "file") return saveAsFile();
  const r = await api().send(ids, targetKey(), opts());
  if (r.error) { S.busy = false; renderSummary(); return toast(r.error, "warn"); }
  S.chats = r.chats; S.settings = r.settings || S.settings; renderChats();
  toast("Working…", "work", 0);
}
$("#btnSend").onclick = doSend;

/* history: what was sent where, with send-again */
$("#btnHistory").onclick = async () => {
  const h = await api().get_history();
  $("#histBody").innerHTML = h.length ? h.map((e, i) => `
    <div class="hrow"><div class="t"><b>${esc(e.titles.join(", "))}</b><small>${esc(e.time)} → ${esc(e.target)}</small></div>
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
  const app = S.apps.find(a => a.name === h.target), siteIx = S.web.findIndex(w => w.name === h.target);
  S.sel = new Set(live); S.target = h.target_key === "copy" ? "copy" : app ? app.key : (siteIx >= 0 || h.target_key === "web:none") ? "web" : null;
  if (S.target === "web") S.site = siteIx >= 0 ? siteIx : "none";
  if (S.target === null) return toast(`${h.target} isn’t available right now.`, "warn");
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
  const btn = $("#btnRefresh"); btn.classList.add("busy"); btn.textContent = "Looking…";
  const keep = typeof S.target === "number" ? (S.apps.find(a => a.key === S.target) || {}).name : null;  // app numbers can change on a rescan
  const had = new Set(S.apps.map(a => a.name)), hadChats = new Set(S.chats.map(c => c.id));
  try {
    const r = await api().scan_all();
    S.chats = r.chats; S.apps = r.apps; S.web = r.web || S.web; S.toolsChosen = !!r.tools_chosen;
  } catch (e) { toast("Scan problem: " + e, "err"); }
  if (keep) { const a = S.apps.find(a => a.name === keep); S.target = a ? a.key : null; }
  S.scanning = false; rememberTarget(); renderAll();
  btn.classList.remove("busy"); btn.textContent = "Look again";
  if (manual) {
    const newApps = S.apps.filter(a => !had.has(a.name)).map(a => a.name), newChats = S.chats.filter(c => !hadChats.has(c.id)).length;
    toast(newApps.length || newChats
      ? `Found ${newApps.length ? "new tool" + (newApps.length > 1 ? "s" : "") + ": " + newApps.join(", ") : ""}${newApps.length && newChats ? " and " : ""}${newChats ? newChats + " new chat" + (newChats > 1 ? "s" : "") : ""}.`
      : `Nothing new — ${S.apps.length} tool${S.apps.length === 1 ? "" : "s"} and ${S.chats.length} chat${S.chats.length === 1 ? "" : "s"} found.`, "good", 5000);
  }
}
async function start() {
  const b = await api().bootstrap();
  S.chats = b.chats; S.apps = b.apps; S.web = b.web || []; S.settings = b.settings; S.toolsChosen = !!b.tools_chosen;
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
  const a = S.apps.find(a => a.name === last && a.enabled !== false), wi = S.web.findIndex(w => w.name === last);
  if (last === "copy") S.target = "copy";
  else if (a) S.target = a.key;
  else if (wi >= 0 || last === "a website") { S.target = "web"; S.site = wi >= 0 ? wi : "none"; }
}
$("#wGo").onclick = () => { close("#mWelcome"); api().mark_welcomed(); };
if (window.pywebview && window.pywebview.api) start(); else window.addEventListener("pywebviewready", start);
