/* Sends captured chats to the ChatBridge app listening on this PC (127.0.0.1 only), using the pairing code.
 *
 * Before anything is sent, the extension asks "prove you're ChatBridge": it sends a random number and the app must answer with
 * HMAC(pairing code, number). Only the real app knows the code, so another program that happens to answer on the same port
 * never receives the code or your chat. */
const PORTS = [47821, 47822, 47823, 47824, 47825];
const hex = bytes => [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, "0")).join("");

async function hmacHex(key, message) {
  const enc = new TextEncoder();
  const k = await crypto.subtle.importKey("raw", enc.encode(key), {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(message)));
}

async function findApp(token) {
  for (const p of PORTS) {
    try {
      const nonce = hex(crypto.getRandomValues(new Uint8Array(16)));
      const r = await fetch(`http://127.0.0.1:${p}/ping?nonce=${nonce}`);
      const j = await r.json();
      if (j && j.app === "ChatBridge" && j.proof && j.proof === await hmacHex(token, nonce)) return {port: p, version: j.version};
    } catch (e) { /* nothing (or something else) on this port */ }
  }
  return null;
}

const NEED_CODE = "Open the extension's options and paste the pairing code from ChatBridge → Settings.";

async function send(payload) {
  const {token} = await chrome.storage.local.get("token");
  if (!token) return {error: NEED_CODE};
  const app = await findApp(token);
  if (!app) return {error: "Couldn't reach ChatBridge with this pairing code. Is the app open, and is the code the current one?"};
  try {
    const r = await fetch(`http://127.0.0.1:${app.port}/capture`, {
      method: "POST", headers: {"Content-Type": "application/json", "X-ChatBridge-Token": token}, body: JSON.stringify(payload)});
    const j = await r.json();
    return r.ok ? j : {error: j.error || "ChatBridge said no (HTTP " + r.status + ")"};
  } catch (e) { return {error: "Couldn't send the chat: " + e.message}; }
}

chrome.runtime.onMessage.addListener((m, sender, reply) => {
  if (m.type === "capture") { send(m.payload).then(reply); return true; }
  if (m.type === "ping") {
    chrome.storage.local.get("token").then(({token}) =>
      token ? findApp(token).then(a => reply(a || {error: "Couldn't reach ChatBridge with this code. Is the app open?"})) : reply({error: NEED_CODE}));
    return true;
  }
});

chrome.action.onClicked.addListener(tab => {
  chrome.tabs.sendMessage(tab.id, {type: "do-capture"}).catch(() => chrome.runtime.openOptionsPage());
});
