/* Pairing credentials remain in extension storage, outside the page world. */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message.type !== "portal-api") throw new Error("Unknown extension request.");
    if (!/^\/api\/(profile|current|config|corpus|sessions\/[a-f0-9]{32}\/(attachment|profile|preflight|answer-sheet|override|record|reported-submitted|sponsorship-mode))$/.test(message.path)) throw new Error("API path is not allowed.");
    const {server, token} = await chrome.storage.local.get(["server", "token"]);
    if (!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(server || "") || !token) throw new Error("Pair the extension in its popup first.");
    const post = /^\/api\/(corpus|sessions\/[a-f0-9]{32}\/(preflight|answer-sheet|override|record|reported-submitted|sponsorship-mode))$/.test(message.path);
    const preflight = message.path.endsWith("/preflight");
    const response = await fetch(server + message.path, post ? {method: "POST", headers: {"X-Portal-Token": token, "Content-Type": "application/json"}, body: JSON.stringify(preflight ? {fields: message.body?.fields ?? null} : message.body ?? {})}
      : {headers: {"X-Portal-Token": token}});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Local server rejected the request.");
    return value;
  })().then(value => sendResponse({ok: true, value})).catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
