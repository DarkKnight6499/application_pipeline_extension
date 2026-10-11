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
// Every command targets the top frame explicitly so a frame bridge can never answer it.
async function command(type, body, applicationContext = null) {
  const result = await chrome.tabs.sendMessage(tabId, {type, tabId, ...body,
    ...(["portal-fill", "portal-progress", "portal-mode"].includes(type) ? {applicationContext} : {})}, {frameId: 0});
  if (!result?.ok) throw new Error(result?.error || "Scan the current page again using the extension popup.");
  return result.value;
}
const FRAME_FILES = ["adapters/registry.js", "adapters/generic.js", "adapters/aria-listbox.js", "classifier.js", "engine.js", "frame-bridge.js"];
let inspectedFrames = [];
// Inspection only: inject the read-only bridge into frames the extension may access (activeTab covers same-origin frames).
async function injectFrames() {
  inspectedFrames = [];
  try {
    const results = await chrome.scripting.executeScript({target: {tabId, allFrames: true}, files: FRAME_FILES});
    inspectedFrames = results.map(item => item.frameId).filter(id => Number.isInteger(id) && id > 0);
  } catch { /* Frames the extension cannot access stay uninspected and are reported by the top-level coverage. */ }
}
async function inspectAll() {
  const report = await command("portal-inspect");
  const frameReports = [];
  for (const frameId of inspectedFrames) {
    try {
      const result = await chrome.tabs.sendMessage(tabId, {type: "portal-inspect", tabId}, {frameId});
      if (result?.ok) frameReports.push({frame_id: frameId, ...result.value});
    } catch { /* A frame that navigated or closed is skipped. */ }
  }
  return {...report, frame_reports: frameReports};
}
async function rescan() {
  const status = document.getElementById("review-status");
  try {
    let boundContext = null;
    const tab = await chrome.tabs.get(tabId);
    if (!/^https?:/.test(tab.url || "")) throw new Error("The target page is not available.");
    const {server: pairedServer} = await chrome.storage.local.get("server");
    const routing = PortalHostPolicy.assertAllowed(tab.url, pairedServer);
    await chrome.scripting.executeScript({target: {tabId}, files: ["adapters/registry.js", "adapters/generic.js", "adapters/workday.js", "adapters/aria-listbox.js", "adapters/greenhouse.js", "adapters/greenhouse-select.js", "adapters/phenom.js", "classifier.js", "application-mode.js", "engine.js", "progress.js", "handoff.js", "page-bridge.js"].concat(routing === "fallback" ? ["adapters/fallback.js"] : [])});
    if (inspectionOnly) await injectFrames();
    await PortalPanel.open(api, storage, {extensionPage: true, targetUrl: tab.url, inspectionOnly,
      onFillState: busy => {document.getElementById("rescan").disabled = busy;},
      transport: {bindSession: session => {boundContext = {sessionId: session.id, applicationId: session.application_id, targetUrl: tab.url};},
        scan: (profile, bindings) => command("portal-scan", {profile, bindings}),
        mode: () => command("portal-mode", {}, boundContext),
        fill: (selections, options) => command("portal-fill", {selections, options}, boundContext),
        inspect: () => inspectionOnly ? inspectAll() : command("portal-inspect"), progress: action => command("portal-progress", {action}, boundContext)}});
    status.textContent = inspectionOnly
      ? "Inspection only. No helper, candidate profile, or application import required. Navigate pages yourself, then Rescan."
      : "Review stays inside the extension. Continue and submit on the application page yourself.";
  } catch (error) {status.textContent = error.message;}
}
document.getElementById("rescan").onclick = rescan;
rescan();
