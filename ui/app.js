const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const S = {chats: [], apps: [], settings: {theme: "dark", size: 16}, sel: new Set(), target: null, busy: false, scanning: true};
const api = () => window.pywebview.api;
const PALETTE = ["#f0997b", "#93c5fd", "#5dcaa5", "#ed93b1", "#afa9ec", "#fac775", "#85b7eb"];
const colorFor = n => PALETTE[[...String(n)].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];

/* ---------- helpers ---------- */
let toastTimer;
function toast(msg, kind = "", ms = 5000) {
  const t = $("#toast");
  t.className = "toast show " + kind;
  t.innerHTML = (kind === "work" ? '<span class="spinner"></span>' : "") + `<span>${esc(msg)}</span>`;
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
  const parts = [`<b>~${e.tokens.toLocaleString()} tokens</b>`];
  if (e.pct != null) parts.push(`<span class="${e.pct > 100 ? "warn" : e.pct > 70 ? "warn" : "good"}">${e.pct}% of ${esc(e.target)}’s window${e.pct > 100 ? " — too big, try Compact" : ""}</span>`);
  else if (e.target && S.target !== "copy") parts.push(`${esc(e.target)}’s window size isn’t set`);
  if (e.saved > 0) parts.push(`saved ${e.saved.toLocaleString()} by compacting`);
  const s = e.scrubbed || {}, removed = (s.keys || 0) + (s.emails || 0) + (s.phones || 0) + (s.paths || 0);
  if (removed) parts.push(`scrubbed ${removed} private item${removed === 1 ? "" : "s"}`);
  if (e.cost != null) parts.push(`≈ $${e.cost} as API input`);
  box.innerHTML = parts.join(" · ");
}

function renderChats() {
  const L = $("#chatList");
  const n = S.chats.length;
  $("#chipChats").textContent = S.scanning && !n ? "Looking for chats…" : `${n} chat${n === 1 ? "" : "s"} & projects`;
  if (!n) {
    L.innerHTML = '<div class="empty"><b>No chats yet</b>Add a chat file, paste some text, or bring a project folder with the buttons above.</div>';
    return;
  }
  const groups = {};
  S.chats.forEach(c => (groups[c.source] = groups[c.source] || []).push(c));
  L.innerHTML = Object.entries(groups).map(([src, items]) => `
    <button class="grp-head" data-grp="${esc(src)}"><span class="gicon">${iconFor(src)}</span>From ${esc(src)} <span class="count">${items.length}</span></button>
    ${items.map(c => `
      <div class="card ${S.sel.has(c.id) ? "on" : ""}" data-id="${esc(c.id)}" draggable="true">
        <span class="chk">✓</span>
        <div class="t"><b>${esc(c.title)}</b><small title="${c.real_tokens ? "Claude Code recorded " + c.real_tokens.toLocaleString() + " tokens processed for this chat (including cached reads)" : "Estimated size"}">${c.kind === "project" ? "Project" + (c.mode ? " · " + c.mode : "") : c.count + " messages"} · ~${kfmt(c.tokens)} tokens · ${esc((c.created || "").slice(0, 10))}</small></div>
        <button class="eye" data-view="${esc(c.id)}" title="Preview">◉</button>
        ${c.saved ? `<button class="x" data-del="${esc(c.id)}" title="Remove from ChatBridge">×</button>` : ""}
      </div>`).join("")}`).join("");
}

function appTile(key, name, sub, iconHtml, bg) {
  const on = S.target === key ? "on" : "";
  const ic = iconHtml ? `<span class="ic" style="background:${bg || "transparent"}">${iconHtml}</span>`
                      : `<span class="ic" style="background:${colorFor(name)}">${esc(name[0].toUpperCase())}</span>`;
  return `<button class="app-tile ${on}" data-key="${esc(key)}">${ic}<b>${esc(name)}</b><small>${sub}</small></button>`;
}
function renderApps() {
  const kindSub = {"Desktop app": "Installed", "Possible AI app": "Might be an AI app", "CLI tool": "Terminal tool", "Local server": "Runs on this PC"};
  const tiles = S.apps.map(a => {
    let sub = esc(kindSub[a.kind] || a.kind);
    if (a.kind === "Local server") sub += ` · ${a.models.length} model${a.models.length === 1 ? "" : "s"}`;
    if (a.tested === true) sub = '<span class="ok">tested ✓</span> · ' + sub;
    if (a.tested === false) sub = '<span class="bad">didn’t work yet</span>';
    if (a.icon) return appTile(a.key, a.name, sub, `<img src="${a.icon}" alt="">`);
    return appTile(a.key, a.name, sub, a.kind === "CLI tool" ? "&gt;_" : "", a.kind === "CLI tool" ? "#b4b2a9" : "");
  });
  tiles.push(appTile("copy", "Copy only", "Paste it anywhere", "⧉", "#b4b2a9"));
  $("#appGrid").innerHTML = tiles.join("");
  const real = S.apps.filter(a => a.kind === "Desktop app" || a.kind === "Local server").length;
  $("#dotApps").classList.toggle("spin", S.scanning);
  $("#chipApps").textContent = S.scanning && !S.apps.length ? "Looking for your AI apps…" : `${S.apps.length} app${S.apps.length === 1 ? "" : "s"} found`;
}

function renderSummary() {
  const ids = [...S.sel].filter(id => S.chats.some(c => c.id === id));
  const n = ids.length, items = `${n} item${n === 1 ? "" : "s"}`;
  const app = typeof S.target === "number" ? S.apps.find(a => a.key === S.target) : null;
  const name = S.target === "copy" ? "the clipboard" : app ? app.name : null;
  let msg, label = "Send", ready = n > 0 && S.target !== null;
  if (!n) msg = "Tick a chat on the left and choose where it should go.";
  else if (!name) msg = `<b>${items}</b> ticked. Now choose where to send ${n === 1 ? "it" : "them"}.`;
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

$("#btnAll").onclick = () => { S.chats.forEach(c => S.sel.add(c.id)); renderAll(); };
$("#btnNone").onclick = () => { S.sel.clear(); renderAll(); };
$("#btnTheme").onclick = () => {
  const keys = Object.keys(THEMES);
  S.settings.theme = keys[(keys.indexOf(S.settings.theme) + 1) % keys.length];
  applySettings(); persistLook(); toast("Theme: " + THEMES[S.settings.theme], "", 1800);
};
$("#btnBigger").onclick = () => { S.settings.size = Math.min(26, (S.settings.size || 16) + 1); applySettings(); persistLook(); };
$("#btnSmaller").onclick = () => { S.settings.size = Math.max(11, (S.settings.size || 16) - 1); applySettings(); persistLook(); };
$("#btnEditApps").onclick = () => open("#mApps");
$("#aEdit").onclick = () => api().edit_profiles();
$("#aAdd").onclick = async () => {
  const r = await api().add_app($("#aName").value);
  if (r.error) return toast(r.error, "err");
  close("#mApps"); $("#aName").value = ""; rescan();
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
  const app = S.apps.find(a => a.name === h.target);
  S.sel = new Set(live); S.target = h.target_key === "copy" ? "copy" : app ? app.key : null;
  if (S.target === null) return toast(`${h.target} isn’t available right now.`, "warn");
  $("#oCompact").checked = !!(h.opts || {}).compact; $("#oScrub").checked = !!(h.opts || {}).scrub;
  close("#mHistory"); renderAll(); doSend();
};
$("#btnTest").onclick = async () => {
  if (typeof S.target !== "number") return toast("Pick a desktop app on the right first, then click Test.", "warn");
  S.busy = true; renderSummary();
  const r = await api().test_app(S.target);
  if (r.error) { S.busy = false; renderSummary(); return toast(r.error, "warn"); }
  toast("Testing… don’t click elsewhere.", "work", 0);
};
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
  toast(p.msg, {done: "good", warn: "warn", error: "err"}[p.state] || "", p.state === "done" ? 9000 : 12000);
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
async function rescan() {
  S.scanning = true; renderApps();
  const keep = typeof S.target === "number" ? (S.apps.find(a => a.key === S.target) || {}).name : null;  // app numbers can change on a rescan
  try { const r = await api().scan_all(); S.chats = r.chats; S.apps = r.apps; } catch (e) { toast("Scan problem: " + e, "err"); }
  if (keep) { const a = S.apps.find(a => a.name === keep); S.target = a ? a.key : null; }
  S.scanning = false; rememberTarget(); renderAll();
}
async function start() {
  const b = await api().bootstrap();
  S.chats = b.chats; S.apps = b.apps; S.settings = b.settings;
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
  const a = S.apps.find(a => a.name === last);
  if (last === "copy") S.target = "copy"; else if (a) S.target = a.key;
}
$("#wGo").onclick = () => { close("#mWelcome"); api().mark_welcomed(); };
if (window.pywebview && window.pywebview.api) start(); else window.addEventListener("pywebviewready", start);
