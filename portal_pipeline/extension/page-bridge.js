/* Only the scanner and writer run in the page. Profile review stays extension-owned. */
(() => {
  if (globalThis.portalBridgeInstalled) return;
  globalThis.portalBridgeInstalled = true;
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL("review.html"))) return;
    if (new URL(sender.url).searchParams.get("mode") === "inspect" && message.type !== "portal-inspect") {
      sendResponse({ok: false, error: "Inspection mode cannot scan candidate answers or fill fields."});
      return;
    }
    if (message.type === "portal-inspect") {
      try { sendResponse({ok: true, value: PortalEngine.inspect()}); }
      catch (error) { sendResponse({ok: false, error: error.message}); }
    } else if (message.type === "portal-scan") {
      try { sendResponse({ok: true, value: PortalEngine.scan(message.profile, {bindings: message.bindings || {}})}); }
      catch (error) { sendResponse({ok: false, error: error.message}); }
    } else if (message.type === "portal-progress") {
      const adapter = PortalAdapters.forLocation(location.href);
      (message.action === "next" ? PortalProgress.guardedNext(adapter) : PortalProgress.pageCheck(adapter)).then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    } else if (message.type === "portal-fill") {
      PortalEngine.fill(message.selections, message.options).then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    }
  });
})();
