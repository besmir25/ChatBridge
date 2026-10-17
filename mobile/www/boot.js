/* Safety net, loaded before everything else. If the app can't start (most often because the phone's "Android System WebView" is very old
   and can't read modern JavaScript), show a plain message instead of a blank page. app.js sets window.__cbReady when it has started. */
(function () {
  "use strict";
  var shown = false;
  var TEXT = {
    en: ["ChatBridge couldn't start", "Your phone's “Android System WebView” may be out of date. Open Google Play, search for “Android System WebView”, update it, then open ChatBridge again."],
    es: ["ChatBridge no pudo iniciarse", "Es posible que el “Android System WebView” de tu teléfono esté desactualizado. Abre Google Play, busca “Android System WebView”, actualízalo y vuelve a abrir ChatBridge."],
    pt: ["O ChatBridge não conseguiu iniciar", "O “Android System WebView” do seu celular pode estar desatualizado. Abra a Google Play, procure “Android System WebView”, atualize e abra o ChatBridge de novo."],
    fr: ["ChatBridge n’a pas pu démarrer", "Le « Android System WebView » de votre téléphone est peut-être obsolète. Ouvrez Google Play, cherchez « Android System WebView », mettez-le à jour, puis rouvrez ChatBridge."],
    de: ["ChatBridge konnte nicht starten", "Das „Android System WebView“ Ihres Telefons ist möglicherweise veraltet. Öffnen Sie Google Play, suchen Sie „Android System WebView“, aktualisieren Sie es und öffnen Sie ChatBridge erneut."],
    zh: ["ChatBridge 无法启动", "你手机上的“Android System WebView”可能已过期。请打开 Google Play，搜索“Android System WebView”并更新，然后重新打开 ChatBridge。"],
    ja: ["ChatBridge を起動できませんでした", "お使いのスマートフォンの「Android System WebView」が古い可能性があります。Google Play で「Android System WebView」を検索して更新してから、ChatBridge をもう一度開いてください。"]
  };
  function show() {
    if (shown || window.__cbReady || !document.body) return;
    shown = true;
    var lang = String((navigator.language || "en")).slice(0, 2).toLowerCase();
    var t = TEXT[lang] || TEXT.en;
    var box = document.createElement("div");
    box.setAttribute("style", "font:16px/1.5 system-ui,sans-serif;padding:32px 24px;max-width:480px;margin:0 auto;color:#2b2622");
    var h = document.createElement("h1"); h.textContent = t[0]; h.setAttribute("style", "font-size:1.4em;margin:0 0 12px");
    var p = document.createElement("p"); p.textContent = t[1];
    box.appendChild(h); box.appendChild(p);
    document.body.innerHTML = ""; document.body.appendChild(box);
  }
  window.addEventListener("error", function (e) { if (!window.__cbReady) setTimeout(show, 50); }, true);     // a script that fails to load or parse
  window.addEventListener("load", function () { setTimeout(show, 4000); });                                     // started late or not at all
})();
