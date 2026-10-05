/* Only the scanner and writer run in the page. Profile review stays extension-owned. */
(() => {
  if (globalThis.portalBridgeInstalled) return;
  globalThis.portalBridgeInstalled = true;
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    let reviewUrl;
    try { reviewUrl = new URL(sender.url); } catch { return; }
    const trustedReviewUrl = new URL(chrome.runtime.getURL("review.html"));
    if (sender.id !== chrome.runtime.id || reviewUrl.protocol !== trustedReviewUrl.protocol ||
        reviewUrl.host !== trustedReviewUrl.host || reviewUrl.pathname !== trustedReviewUrl.pathname) return;
    if (new URL(sender.url).searchParams.get("mode") === "inspect" && message.type !== "portal-inspect") {
      sendResponse({ok: false, error: "Inspection mode cannot scan candidate answers or fill fields."});
      return;
    }
    if (message.type !== "portal-inspect" && reviewUrl.searchParams.get("tab") !== String(message.tabId)) return;
    if (message.type === "portal-inspect") {
      try { sendResponse({ok: true, value: PortalEngine.inspect()}); }
      catch (error) { sendResponse({ok: false, error: error.message}); }
    } else if (message.type === "portal-scan") {
      try { sendResponse({ok: true, value: PortalEngine.scan(message.profile, {bindings: message.bindings || {}})}); }
      catch (error) { sendResponse({ok: false, error: error.message}); }
    } else if (message.type === "portal-mode") {
      const adapter = PortalAdapters.forLocation(location.href);
      const action = async () => {
        if (adapter?.requiresApplicationMode !== true) return null;
        if (!globalThis.PortalApplicationMode) throw new Error("Application mode guard is unavailable.");
        PortalApplicationMode.bind(message.applicationContext);
        return PortalApplicationMode.observe(adapter);
      };
      action().then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    } else if (message.type === "portal-progress") {
      const adapter = PortalAdapters.forLocation(location.href);
      const action = async () => {
        if (message.action === "next" && adapter?.requiresApplicationMode === true) {
          if (!globalThis.PortalApplicationMode) throw new Error("Application mode guard is unavailable.");
          PortalApplicationMode.bind(message.applicationContext);
          await PortalApplicationMode.check(adapter);
        }
        return message.action === "next" ? PortalProgress.guardedNext(adapter) : PortalProgress.pageCheck(adapter);
      };
      action().then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    } else if (message.type === "portal-fill") {
      const action = async () => {
        const adapter = PortalAdapters.forLocation(location.href);
        if (adapter?.requiresApplicationMode === true) {
          if (!globalThis.PortalApplicationMode) throw new Error("Application mode guard is unavailable.");
          PortalApplicationMode.bind(message.applicationContext);
          await PortalApplicationMode.check(adapter);
        }
        return PortalEngine.fill(message.selections, message.options);
      };
      action().then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    }
  });
})();
