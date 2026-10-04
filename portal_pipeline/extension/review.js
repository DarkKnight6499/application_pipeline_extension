const tabId = Number(new URL(location.href).searchParams.get("tab"));
const inspectionOnly = new URL(location.href).searchParams.get("mode") === "inspect";
const api = async (path, body) => {
  const result = await chrome.runtime.sendMessage({type: "portal-api", path, body});
  if (!result.ok) throw new Error(result.error);
  return result.value;
};
const storage = {
  async load(key) { return (await chrome.storage.local.get("review:" + key))["review:" + key]; },
  async save(key, value) { await chrome.storage.local.set({["review:" + key]: value}); }
};
async function command(type, body) {
  const result = await chrome.tabs.sendMessage(tabId, {type, ...body});
  if (!result?.ok) throw new Error(result?.error || "Scan the current page again using the extension popup.");
  return result.value;
}
async function rescan() {
  const status = document.getElementById("review-status");
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!/^https?:/.test(tab.url || "")) throw new Error("The target page is not available.");
    const {server: pairedServer} = await chrome.storage.local.get("server");
    PortalHostPolicy.assertSupported(tab.url, pairedServer);
    await chrome.scripting.executeScript({target: {tabId}, files: ["adapters/registry.js", "adapters/generic.js", "adapters/aria-listbox.js", "adapters/greenhouse.js", "adapters/greenhouse-select.js", "classifier.js", "engine.js", "page-bridge.js"]});
    await PortalPanel.open(api, storage, {extensionPage: true, targetUrl: tab.url, inspectionOnly,
      onFillState: busy => {document.getElementById("rescan").disabled = busy;},
      transport: {scan: (profile, bindings) => command("portal-scan", {profile, bindings}), fill: (selections, options) => command("portal-fill", {selections, options}), inspect: () => command("portal-inspect")}});
    status.textContent = inspectionOnly
      ? "Inspection only. No helper, candidate profile, or application import required. Navigate pages yourself, then Rescan."
      : "Review stays inside the extension. Continue and submit on the application page yourself.";
  } catch (error) {status.textContent = error.message;}
}
document.getElementById("rescan").onclick = rescan;
rescan();
