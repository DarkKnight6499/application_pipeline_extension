/* Read-only inspection bridge for same-origin frames. It answers portal-inspect only and has no scan, fill, mode, or progress handler. */
(() => {
  if (window === window.top || globalThis.portalFrameBridgeInstalled) return;
  globalThis.portalFrameBridgeInstalled = true;
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type !== "portal-inspect" || sender.id !== chrome.runtime.id) return;
    let reviewUrl;
    try { reviewUrl = new URL(sender.url); } catch { return; }
    const trusted = new URL(chrome.runtime.getURL("review.html"));
    if (reviewUrl.protocol !== trusted.protocol || reviewUrl.host !== trusted.host || reviewUrl.pathname !== trusted.pathname) return;
    try { sendResponse({ok: true, value: PortalEngine.inspect()}); }
    catch (error) { sendResponse({ok: false, error: error.message}); }
  });
})();
