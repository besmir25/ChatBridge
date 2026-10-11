/* Sends captured chats to the ChatBridge app listening on this PC (127.0.0.1 only), using the pairing code. */
const PORTS = [47821, 47822, 47823, 47824, 47825];

async function findApp() {
  for (const p of PORTS) {
    try {
      const r = await fetch(`http://127.0.0.1:${p}/ping`);
      const j = await r.json();
      if (j && j.app === "ChatBridge") return {port: p, version: j.version};
    } catch (e) { /* not this port */ }
  }
  return null;
}

async function send(payload) {
  const {token} = await chrome.storage.local.get("token");
  if (!token) return {error: "Open the extension's options and paste the pairing code from ChatBridge → Settings."};
  const app = await findApp();
  if (!app) return {error: "Couldn't reach ChatBridge. Is the app open on this PC?"};
  try {
    const r = await fetch(`http://127.0.0.1:${app.port}/capture`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-ChatBridge-Token": token}, body: JSON.stringify(payload)});
    const j = await r.json();
    return r.ok ? j : {error: j.error || "ChatBridge said no (HTTP " + r.status + ")"};
  } catch (e) { return {error: "Couldn't send the chat: " + e.message}; }
}

chrome.runtime.onMessage.addListener((m, sender, reply) => {
  if (m.type === "capture") { send(m.payload).then(reply); return true; }
  if (m.type === "ping") { findApp().then(a => reply(a || {error: "ChatBridge isn't running."})); return true; }
});

chrome.action.onClicked.addListener(tab => {
  chrome.tabs.sendMessage(tab.id, {type: "do-capture"}).catch(() => chrome.runtime.openOptionsPage());
});
