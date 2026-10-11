/* ChatBridge Capture - reads the conversation on the page you're looking at and hands it to the ChatBridge app.
 * The page's own selectors change from time to time; each site has a function below, plus a fallback that uses
 * whatever text you've selected. Nothing is read or sent until you click the button. */
(() => {
  if (window.__chatbridgeLoaded) return;
  window.__chatbridgeLoaded = true;

  const host = window.__chatbridgeHost || location.hostname;   // the override is only for testing
  const clean = s => (s || "").replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim();
  const text = el => clean(el.innerText || el.textContent);
  const outermost = els => els.filter(a => !els.some(b => b !== a && b.contains(a)));
  const titleOf = () => clean(document.title.replace(/\s*[-|–·]\s*(ChatGPT|Claude|Gemini|Google Gemini).*$/i, "")) || "Web chat";

  const sites = {
    chatgpt() {
      const nodes = [...document.querySelectorAll("[data-message-author-role]")];
      return {source: "ChatGPT (web)", messages: nodes.map(n => ({
        role: n.getAttribute("data-message-author-role"), content: text(n.querySelector(".markdown") || n)}))};
    },
    claude() {
      const user = '[data-testid="user-message"]';
      const bot = '.font-claude-response, .font-claude-message, [data-is-streaming]';
      const nodes = outermost([...document.querySelectorAll(user + ", " + bot)]);
      return {source: "Claude.ai", messages: nodes.map(n => ({role: n.matches(user) ? "user" : "assistant", content: text(n)}))};
    },
    gemini() {
      const nodes = [...document.querySelectorAll("user-query, model-response")];
      return {source: "Gemini (web)", messages: nodes.map(n => {
        const isUser = n.tagName.toLowerCase() === "user-query";
        const body = isUser ? (n.querySelector(".query-text") || n) : (n.querySelector("message-content") || n);
        return {role: isUser ? "user" : "assistant", content: text(body).replace(/^(You said|Gemini said)\s*/i, "")};
      })};
    },
  };

  function extract() {
    const kind = /chatgpt|openai/.test(host) ? "chatgpt" : /claude/.test(host) ? "claude" : "gemini";
    let r = sites[kind]();
    r.messages = r.messages.filter(m => m.content);
    if (!r.messages.length) {                       // fallback: whatever is selected on the page
      const sel = clean(String(window.getSelection()));
      if (sel) r.messages = [{role: "user", content: sel}];
    }
    return {title: titleOf(), source: r.source, url: location.href.split("#")[0], messages: r.messages};
  }

  /* ---- the button (in a shadow root so the site's styles can't touch it) ---- */
  const root = document.createElement("div");
  root.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483647;all:initial;";
  const shadow = root.attachShadow({mode: "closed"});
  shadow.innerHTML = `<style>
    .b{position:fixed;right:18px;bottom:18px;font:600 13px/1 "Segoe UI",system-ui,sans-serif;background:#2dd4bf;color:#06201d;border:0;
       border-radius:99px;padding:11px 16px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.35);opacity:.92}
    .b:hover{opacity:1}
    .t{position:fixed;right:18px;bottom:66px;max-width:320px;font:13px/1.4 "Segoe UI",system-ui,sans-serif;background:#171a20;color:#eef0f3;
       border:1px solid #2dd4bf;border-radius:12px;padding:10px 14px;display:none;box-shadow:0 6px 20px rgba(0,0,0,.35)}
    .t.err{border-color:#f87171}
  </style><button class="b" title="Save this conversation to the ChatBridge app">⇄ Save to ChatBridge</button><div class="t"></div>`;
  document.documentElement.appendChild(root);
  const btn = shadow.querySelector(".b"), tip = shadow.querySelector(".t");
  let hideTimer;
  const say = (msg, err) => { tip.textContent = msg; tip.className = "t" + (err ? " err" : ""); tip.style.display = "block";
    clearTimeout(hideTimer); hideTimer = setTimeout(() => (tip.style.display = "none"), 6000); };

  function capture() {
    const payload = extract();
    if (!payload.messages.length) return say("I couldn't find the conversation on this page. Select the chat text and click again.", true);
    btn.disabled = true;
    chrome.runtime.sendMessage({type: "capture", payload}, res => {
      btn.disabled = false;
      if (chrome.runtime.lastError || !res) return say("Couldn't reach the extension. Reload this page and try again.", true);
      if (res.error) return say(res.error, true);
      say(`Saved ${res.count} messages to ChatBridge.`);
    });
  }
  btn.addEventListener("click", capture);
  chrome.runtime.onMessage.addListener(m => { if (m && m.type === "do-capture") capture(); });
})();
