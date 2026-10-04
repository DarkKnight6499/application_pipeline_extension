(async () => {
  const server = document.getElementById("server"), token = document.getElementById("token"), status = document.getElementById("status");
  document.getElementById("pair").onclick = async () => {
    if (!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(server.value)) { status.textContent = "Use the exact loopback URL shown at startup."; return; }
    await chrome.storage.local.set({server: server.value, token: token.value});
    const result = await chrome.runtime.sendMessage({type: "portal-api", path: "/api/config"});
    status.textContent = result.ok ? "Paired. Open an application page, then scan it." : result.error;
  };
  async function openPage(inspectionOnly) {
    try {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      if (!/^https?:/.test(tab?.url || "")) throw new Error("Open a normal application webpage first.");
      const {server: pairedServer} = await chrome.storage.local.get("server");
      PortalHostPolicy.assertSupported(tab.url, pairedServer);
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["adapters/registry.js", "adapters/generic.js", "adapters/aria-listbox.js", "adapters/greenhouse.js", "adapters/greenhouse-select.js", "classifier.js", "engine.js", "page-bridge.js"]});
      await chrome.sidePanel.setOptions({tabId: tab.id, path: `review.html?tab=${tab.id}${inspectionOnly ? "&mode=inspect" : ""}`, enabled: true});
      await chrome.sidePanel.open({tabId: tab.id});
      window.close();
    } catch (error) { status.textContent = error.message; }
  }
  document.getElementById("scan").onclick = () => openPage(false);
  document.getElementById("inspect").onclick = () => openPage(true);
  // Handlers attach first so an early click is never dropped; restore saved values only into untouched fields.
  server.oninput = token.oninput = event => { event.target.dataset.edited = "1"; };
  const saved = await chrome.storage.local.get(["server", "token"]);
  if (saved.server && !server.dataset.edited) server.value = saved.server;
  if (saved.token && !token.dataset.edited) token.value = saved.token;
})();
