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
// Every command targets one frame explicitly: the top frame unless chooseFrame picked a frameFill frame at rescan.
let activeFrame = {id: 0, url: null};
const send = (frameId, message) => chrome.tabs.sendMessage(tabId, message, {frameId});
async function command(type, body, applicationContext = null) {
  const result = await send(activeFrame.id, {type, tabId, ...body,
    ...(activeFrame.id ? {frameUrl: activeFrame.url} : {}),
    ...(["portal-fill", "portal-progress", "portal-mode"].includes(type) ? {applicationContext} : {})});
  if (!result?.ok) throw new Error(result?.error || "Scan the current page again using the extension popup.");
  return result.value;
}
const FRAME_FILES = ["adapters/registry.js", "adapters/generic.js", "adapters/aria-listbox.js", "adapters/icims.js", "classifier.js", "engine.js", "page-bridge.js"];
let inspectedFrames = [];
// Inject the page bridge into frames the extension may access (activeTab covers same-origin frames). A frame serves
// inspection only, unless its own adapter is marked frameFill.
async function injectFrames() {
  inspectedFrames = [];
  try {
    const results = await chrome.scripting.executeScript({target: {tabId, allFrames: true}, files: FRAME_FILES});
    inspectedFrames = results.map(item => item.frameId).filter(id => Number.isInteger(id) && id > 0);
  } catch { /* Frames the extension cannot access stay uninspected and are reported by the top-level coverage. */ }
}
// Work moves into a frame only when the top page has no visible fields and exactly one frame reports a frameFill adapter with fields.
async function chooseFrame() {
  activeFrame = {id: 0, url: null};
  if (inspectionOnly || !inspectedFrames.length) return;
  const top = await send(0, {type: "portal-inspect", tabId});
  if (!top?.ok || top.value.fields.length) return;
  const candidates = [];
  for (const id of inspectedFrames) {
    try {
      const result = await send(id, {type: "portal-inspect", tabId});
      if (result?.ok && result.value.frame?.fill === true && result.value.fields.length) candidates.push({id, url: result.value.frame.url});
    } catch { /* A frame that navigated or closed is skipped. */ }
  }
  if (candidates.length === 1) activeFrame = candidates[0];
}
async function inspectAll() {
  const report = await command("portal-inspect");
  const frameReports = [];
  for (const frameId of inspectedFrames) {
    try {
      const result = await send(frameId, {type: "portal-inspect", tabId});
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
    await injectFrames();
    await chooseFrame();
    await PortalPanel.open(api, storage, {extensionPage: true, targetUrl: tab.url, inspectionOnly,
      onFillState: busy => {document.getElementById("rescan").disabled = busy;},
      transport: {bindSession: session => {boundContext = {sessionId: session.id, applicationId: session.application_id, targetUrl: tab.url};},
        scan: (profile, bindings) => command("portal-scan", {profile, bindings}),
        mode: () => command("portal-mode", {}, boundContext),
        fill: (selections, options) => command("portal-fill", {selections, options}, boundContext),
        inspect: () => inspectionOnly ? inspectAll() : command("portal-inspect"), progress: action => command("portal-progress", {action}, boundContext)}});
    status.textContent = inspectionOnly
      ? "Inspection only. No helper, candidate profile, or application import required. Navigate pages yourself, then Rescan."
      : "Review stays inside the extension. Continue and submit on the application page yourself." +
        (activeFrame.id ? ` Working inside the application frame (id ${activeFrame.id}). Page progression is not available there.` : "");
  } catch (error) {status.textContent = error.message;}
}
document.getElementById("rescan").onclick = rescan;
rescan();
