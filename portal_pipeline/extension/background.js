/* Author: Yazad Madan. Pairing credentials remain outside the page world. */
// Config: the token lives in extension storage (key assistToken), never in source.
const ASSIST_PORT = 8766;
const ASSIST_HOSTS = /^(?:[^.]+\.)*(?:myworkdayjobs\.com|myworkdaysite\.com|greenhouse\.io|ashbyhq\.com|icims\.com|successfactors\.(?:com|eu)|oraclecloud\.com|smartrecruiters\.com|taleo\.net|jobvite\.com|paylocity\.com|paycomonline\.net|dayforcehcm\.com|ultipro\.com|adp\.com)$|^jobs\.lever\.co$/i;
const ASSIST_TIMEOUT_MS = 100000;
const applicationRestrictions = new Set();
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (["portal-assist-answer", "portal-assist-accept", "portal-assist-learn", "portal-assist-miss", "portal-assist-correction", "portal-assist-dump"].includes(message.type)) {
      if (!sender.tab || sender.id !== chrome.runtime.id || typeof sender.url !== "string")
        throw new Error("Assist requires an extension content script.");
      const target = new URL(sender.url);
      if (target.protocol !== "https:" || !ASSIST_HOSTS.test(target.hostname))
        throw new Error("Assist is limited to application hosts.");
      const {assistToken: ASSIST_TOKEN} = await chrome.storage.local.get("assistToken");
      if (!ASSIST_TOKEN) throw new Error("Save the assist token first: see README, Assist setup.");
      const route = message.type.slice("portal-assist-".length);
      if (!message.body || typeof message.body !== "object" || Array.isArray(message.body))
        throw new Error("Assist requires a request object.");
      const miss = route === "miss";
      const body = miss ? {label: message.body?.label, type: message.body?.type, options: message.body?.options,
        company_hint: message.body?.company_hint, host: target.hostname}
        : route === "correction" ? {label: message.body?.label, type: message.body?.type,
          options: message.body?.options, company_hint: message.body?.company_hint, host: target.hostname,
          wrong_value: message.body?.wrong_value, user_value: message.body?.user_value}
        : route === "dump" ? {pairs: message.body.pairs, company_hint: message.body.company_hint,
          host: target.hostname, url: target.href}
        : {...message.body, host: target.hostname, url: target.href};
      const serialized = JSON.stringify(body);
      if (encodeURIComponent(serialized).replace(/%[0-9A-F]{2}|[^%]/g, 'x').length > 64 * 1024)
        throw new Error("Assist request exceeds 64 KB.");
      const response = await fetch(`http://127.0.0.1:${ASSIST_PORT}/assist/${route}`, {
        method: "POST", headers: {"X-Assist-Token": ASSIST_TOKEN, "Content-Type": "application/json"},
        body: serialized, signal: AbortSignal.timeout(ASSIST_TIMEOUT_MS)
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Assist request failed.");
      return value;
    }
    const paired = async () => {
      const {server, token} = await chrome.storage.local.get(["server", "token"]);
      if (!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(server || "") || !token) throw new Error("Pair the extension in its popup first.");
      return {server, token};
    };
    const request = async (server, token, path, body) => {
      const response = await fetch(server + path, body === undefined ? {headers: {"X-Portal-Token": token}}
        : {method: "POST", headers: {"X-Portal-Token": token, "Content-Type": "application/json"}, body: JSON.stringify(body)});
      const value = await response.json();
      if (!response.ok) throw new Error(value.error || "Local server rejected the request.");
      return value;
    };
    if (message.type === "portal-application-mode") {
      if (!sender.tab || sender.frameId !== 0 || sender.id !== chrome.runtime.id) throw new Error("Application mode requires a top-level extension content script.");
      if (!/^[a-f0-9]{32}$/.test(message.sessionId || "")) throw new Error("Invalid application session.");
      if (!Number.isSafeInteger(message.applicationId) || message.applicationId <= 0) throw new Error("An audited Application ID is required.");
      if (!["read", "restrict"].includes(message.action)) throw new Error("Invalid application mode action.");
      const key = `application-mode:application:${message.applicationId}`;
      if (message.action === "restrict") {
        if (message.reason !== "captcha") throw new Error("Invalid application restriction reason.");
        applicationRestrictions.add(key);
        await chrome.storage.local.set({[key]: true});
      }
      const {server, token} = await paired();
      const session = await request(server, token, "/api/current");
      if (session?.id !== message.sessionId || session?.mode !== "audited_import" || session?.application_id !== message.applicationId)
        throw new Error("The audited application changed. Rescan before writing.");
      const target = new URL(sender.url || sender.tab.url);
      if (!session.url || new URL(session.url).origin !== target.origin) throw new Error("The application page changed. Rescan before writing.");
      const path = `/api/sessions/${session.id}/fill-mode`;
      const stored = (await chrome.storage.local.get(key))[key];
      if (stored !== undefined && stored !== true) throw new Error("Invalid local application restriction.");
      if (message.action === "restrict") {
        await request(server, token, path, {mode: "answer_sheet_only", reason: "captcha"});
        return {schema_version: 1, application_id: message.applicationId, mode: "answer_sheet_only", reason: "captcha"};
      }
      const mode = await request(server, token, path);
      const latestSession = await request(server, token, "/api/current");
      if (latestSession?.id !== message.sessionId || latestSession?.mode !== "audited_import" ||
          latestSession?.application_id !== message.applicationId)
        throw new Error("The audited application changed during mode review.");
      const latest = (await chrome.storage.local.get(key))[key];
      if (latest !== undefined && latest !== true) throw new Error("Invalid local application restriction.");
      if (mode?.schema_version !== 1 || mode.application_id !== message.applicationId ||
          !((mode.mode === "fill" && mode.reason === "unrestricted") ||
            (mode.mode === "answer_sheet_only" && ["captcha", "storage_error"].includes(mode.reason))))
        throw new Error("Invalid application mode response.");
      return latest === true || applicationRestrictions.has(key) ? {...mode, mode: "answer_sheet_only", reason: "captcha"} : mode;
    }
    if (message.type === "portal-longform") {
      if (!sender.tab || sender.frameId !== 0 || sender.id !== chrome.runtime.id) throw new Error("Draft checks require a top-level extension content script.");
      if (!/^[a-f0-9]{32}$/.test(message.sessionId || "")) throw new Error("Invalid draft session.");
      const {server, token} = await paired();
      const session = await request(server, token, "/api/current");
      const target = new URL(sender.url || sender.tab.url);
      if (session?.id !== message.sessionId || !session.url || new URL(session.url).origin !== target.origin)
        throw new Error("The selected application changed. Rescan before checking a draft.");
      if (session.mode !== "audited_import" && !(target.hostname === "127.0.0.1" && target.pathname === "/fixture"))
        throw new Error("Draft filling requires an audited application.");
      const result = await request(server, token, `/api/sessions/${message.sessionId}/longform`, message.body);
      const latest = await request(server, token, "/api/current");
      if (latest?.id !== session.id || latest?.application_id !== session.application_id || latest?.mode !== session.mode
          || latest?.url !== session.url) throw new Error("The selected application changed during draft checks.");
      return result;
    }
    if (message.type !== "portal-api") throw new Error("Unknown extension request.");
    // Content scripts run in employer pages and frames, so helper routes are served to the extension's own pages only.
    if (sender.id !== chrome.runtime.id || typeof sender.url !== "string" || !sender.url.startsWith(chrome.runtime.getURL(""))) throw new Error("Helper requests are limited to the extension's own pages.");
    if (!/^\/api\/(profile|current|config|corpus|sessions\/[a-f0-9]{32}\/(attachment|profile|preflight|answer-sheet|override|record|reported-submitted|sponsorship-mode|fill-mode|longform))$/.test(message.path)) throw new Error("API path is not allowed.");
    const {server, token} = await paired();
    const post = /^\/api\/(corpus|sessions\/[a-f0-9]{32}\/(preflight|answer-sheet|override|record|reported-submitted|sponsorship-mode|longform))$/.test(message.path);
    if (message.path.endsWith("/fill-mode") && message.body !== undefined) throw new Error("Use application mode restriction for mode changes.");
    const preflight = message.path.endsWith("/preflight");
    const response = await fetch(server + message.path, post ? {method: "POST", headers: {"X-Portal-Token": token, "Content-Type": "application/json"}, body: JSON.stringify(preflight ? {fields: message.body?.fields ?? null} : message.body ?? {})}
      : {headers: {"X-Portal-Token": token}});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Local server rejected the request.");
    return value;
  })().then(value => sendResponse({ok: true, value})).catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
