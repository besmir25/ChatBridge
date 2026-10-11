/* Preview mode: open index.html?demo in any browser to see the screen with sample data (no Python needed). */
if (!window.pywebview && /[?&]demo/.test(location.search)) {
  const svg = (bg, glyph, fg = "#0f1115") => "data:image/svg+xml;utf8," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" rx="22" fill="${bg}"/><text x="48" y="64" font-size="50" font-family="Segoe UI,Arial" font-weight="600" text-anchor="middle" fill="${fg}">${glyph}</text></svg>`);
  let chats = [
    {id: "1", title: "Resume builds for the job list", source: "Claude Code", created: "2026-10-11 15:36", count: 40, kind: "chat", saved: false, tokens: 9800, real_tokens: 1420000},
    {id: "2", title: "ChatBridge: build an app to move chats", source: "Claude Code", created: "2026-10-11 15:36", count: 19, kind: "chat", saved: false, tokens: 4300},
    {id: "3", title: "Fix a git setup problem on Windows", source: "Claude Code", created: "2026-06-13 14:17", count: 27, kind: "chat", saved: true, tokens: 1600},
    {id: "4", title: "Project: chatbridge", source: "Project folder", created: "2026-10-11 16:40", count: 1, kind: "project", saved: true, tokens: 22800, mode: "outline"},
    {id: "5", title: "Trip planning", source: "ChatGPT", created: "2026-09-02 10:12", count: 22, kind: "chat", saved: true, tokens: 5200},
  ];
  let apps = [
    {key: 0, name: "Claude", kind: "Desktop app", icon: svg("#d97757", "✺", "#fff"), models: [], tested: null},
    {key: 1, name: "Antigravity", kind: "Desktop app", icon: svg("#e8eefc", "A", "#1a1a1a"), models: [], tested: true},
    {key: 2, name: "Copilot", kind: "Desktop app", icon: svg("#eef0ff", "✦", "#6d5ce7"), models: [], tested: true},
    {key: 3, name: "Ollama", kind: "Local server", icon: null, models: ["llama3.2", "qwen2.5"], tested: null},
    {key: 4, name: "claude", kind: "CLI tool", icon: null, models: [], tested: null},
  ];
  const settings = {provider: "Anthropic", base_url: "https://api.anthropic.com", model: "claude-sonnet-5-5", has_key: false, autopaste: true,
    theme: (location.search.match(/theme=(\w+)/) || [0, "midnight"])[1], font: (location.search.match(/font=(\w+)/) || [0, "code"])[1], size: 16, providers: ["Anthropic", "OpenAI-compatible"]};
  const wait = ms => new Promise(r => setTimeout(r, ms));
  window.pywebview = {api: {
    bootstrap: async () => ({chats, apps, settings, welcomed: !/welcome/.test(location.search)}),
    scan_all: async () => { await wait(900); return {chats, apps}; },
    save_settings: async s => Object.assign(settings, s),
    set_provider: async () => ({}), delete_chats: async ids => (chats = chats.filter(c => !ids.includes(c.id))),
    preview: async id => ({title: "Preview", source: "Demo", kind: "chat", messages: [{role: "user", content: "Hello, can we pick up the itinerary?"}, {role: "assistant", content: "Yes. Day 3 was Kyoto."}]}),
    estimate: async (ids, target, o) => ({tokens: 18240 - (o.compact ? 4100 : 0), chars: 70000, saved: o.compact ? 4100 : 0,
      scrubbed: o.scrub ? {keys: 1, emails: 2, phones: 0, paths: 3} : {}, window: target === 0 ? 200000 : null,
      pct: target === 0 ? Math.round((18240 - (o.compact ? 4100 : 0)) / 200) / 10 : null, cost: null, target: target === 0 ? "Claude" : "Antigravity"}),
    get_history: async () => [{time: "2026-10-11 17:30", target: "Claude", target_key: 0, titles: ["Resume builds for the job list", "ChatBridge: build an app"], ids: ["1", "2"], opts: {compact: true, scrub: true}, tokens: 14140},
                              {time: "2026-10-11 16:05", target: "the clipboard", target_key: "copy", titles: ["Project: chatbridge"], ids: ["4"], opts: {}, tokens: 22800}],
    project_size: async (idx, mode) => ({tokens: Math.round(idx.length * (mode === "tree" ? 120 : mode === "outline" ? 900 : 3200))}),
    send: async () => { setTimeout(() => window.onProgress({state: "working", msg: "Opening Claude… don’t click elsewhere."}), 200);
      setTimeout(() => window.onProgress({state: "done", msg: "Pasted into Claude. Check it, then press Enter there to send.", pasted: true}), 1800); return {ok: true, chats}; },
    test_app: async () => { setTimeout(() => window.onProgress({state: "test", name: "Claude", marker: "ChatBridge test 4821", pasted: true}), 800); return {ok: true}; },
    record_compat: async (n, ok) => (apps = apps.map(a => a.name === n ? {...a, tested: ok} : a)),
    chat: async () => ({reply: "We were moving your chats between AI apps; next step is packaging the exe."}),
    pick_project: async () => ({root: "C:\\Users\\you\\my-project", name: "my-project", budget: 120000, skipped: [{rel: ".env", why: "secret"}],
      files: [["README.md", 900, "docs"], ["src/app.py", 5200, "code"], ["src/utils.py", 3100, "code"], ["config/settings.yaml", 600, "config"], ["tests/test_app.py", 1800, "tests"]]
        .map(([rel, size, type], i) => ({i, rel, size, type, on: true}))}),
    add_project: async () => ({id: "9", chats}), add_text: async () => ({id: "8", chats}), import_files: async () => ({ids: [], chats}),
    add_app: async () => ({ok: true}), edit_profiles: async () => {}, mark_welcomed: async () => {},
    whats_new: async () => /modal=new/.test(location.search) ? {show: true, version: "1.1.0", sections: [
      {version: "1.1.0", body: "- New: send a chat to two apps at once\n- The project picker remembers your last choice"},
      {version: "1.0.1", body: "- Fixed: Copilot sometimes opened without the chat\n- **Faster** start-up"}]} : {show: false},
    check_update: async () => /modal=update/.test(location.search) ? {status: "available", current: "1.0.0", version: "1.1.0",
      url: "https://github.com/besmir25/ChatBridge/releases/tag/v1.1.0", notes: "## ChatBridge 1.1.0\n\n- New: send a chat to two apps at once\n- The project picker remembers your last choice\n\n### Install\nDownload **ChatBridge-Setup.exe** below and run it."} : {status: "current", current: "1.0.0"},
    open_release: async () => ({ok: true}),
  }};
  /* ?demo&pick preselects two chats and Claude; ?demo&modal=project|history|settings opens that dialog */
  setTimeout(() => {
    if (/[?&]pick/.test(location.search)) { S.sel = new Set(["1", "2"]); S.target = 0; renderAll(); }
    const m = (location.search.match(/modal=(\w+)/) || [])[1];
    const btn = {project: "#btnProject", history: "#btnHistory", settings: "#btnSettings"}[m];
    if (btn) document.querySelector(btn).click();
    if (m === "update") document.querySelector("#chipUpdate").click();
  }, 1500);
}
