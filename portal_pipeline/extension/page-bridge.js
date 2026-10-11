/* Only the scanner and writer run in the page. Profile review stays extension-owned. */
(() => {
  if (globalThis.portalBridgeInstalled) return;
  globalThis.portalBridgeInstalled = true;
  const inFrame = window !== window.top;
  // Inside a frame only inspection is served, unless the frame's own adapter is explicitly marked frameFill.
  const sameOriginAsTop = () => { try { return window.top.location.origin === location.origin; } catch { return false; } };
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    let reviewUrl;
    try { reviewUrl = new URL(sender.url); } catch { return; }
    const trustedReviewUrl = new URL(chrome.runtime.getURL("review.html"));
    if (sender.id !== chrome.runtime.id || reviewUrl.protocol !== trustedReviewUrl.protocol ||
        reviewUrl.host !== trustedReviewUrl.host || reviewUrl.pathname !== trustedReviewUrl.pathname) return;
    if (inFrame && message.type !== "portal-inspect") {
      const frameAdapter = PortalAdapters.forLocation(location.href);
      if (frameAdapter?.frameFill !== true) return;
      if (message.type === "portal-progress") { sendResponse({ok: false, error: "Page progression is not available inside a frame."}); return; }
      if (!sameOriginAsTop() || message.frameUrl !== location.href) { sendResponse({ok: false, error: "The frame changed. Scan the current page again."}); return; }
    }
    if (new URL(sender.url).searchParams.get("mode") === "inspect" && message.type !== "portal-inspect") {
      sendResponse({ok: false, error: "Inspection mode cannot scan candidate answers or fill fields."});
      return;
    }
    if (message.type !== "portal-inspect" && reviewUrl.searchParams.get("tab") !== String(message.tabId)) return;
    if (message.type === "portal-inspect") {
      try { sendResponse({ok: true, value: {...PortalEngine.inspect(), handoff: globalThis.PortalHandoff ? PortalHandoff.scan(document) : [],
        ...(inFrame ? {frame: {url: location.href, adapter: PortalAdapters.forLocation(location.href)?.id || null, fill: PortalAdapters.forLocation(location.href)?.frameFill === true}} : {})}}); }
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
        const validateLongform = async body => {
          const targetUrl = location.href;
          const result = await chrome.runtime.sendMessage({type: "portal-longform", body,
            sessionId: message.applicationContext?.sessionId});
          if (location.href !== targetUrl) throw new Error("Application page changed during draft checks. Rescan.");
          if (!result?.ok) throw new Error(result?.error || "Draft checks could not be completed.");
          return result.value;
        };
        // Draft checks need the top-level broker, so a frame fills without long-form drafts.
        return PortalEngine.fill(message.selections, {...message.options, ...(inFrame ? {} : {validateLongform})});
      };
      action().then(value => sendResponse({ok: true, value}))
        .catch(error => sendResponse({ok: false, error: error.message}));
      return true;
    }
  });
})();
