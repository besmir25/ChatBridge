const $ = s => document.querySelector(s);
const say = (t, ok) => { $("#msg").textContent = t; $("#msg").className = ok ? "ok" : "bad"; };
chrome.storage.local.get("token").then(({token}) => { if (token) $("#token").value = token; });
$("#save").onclick = async () => {
  const token = $("#token").value.trim();
  if (!token) return say("Paste the pairing code from ChatBridge → Settings first.", false);
  await chrome.storage.local.set({token});
  say("Saved. You can now use the Save to ChatBridge button.", true);
};
$("#test").onclick = () => chrome.runtime.sendMessage({type: "ping"}, r =>
  r && !r.error ? say(`Connected to ChatBridge ${r.version} on port ${r.port}.`, true) : say((r && r.error) || "Couldn't reach ChatBridge. Is the app open?", false));
