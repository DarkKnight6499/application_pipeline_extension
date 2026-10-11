/* Read-only handoff resolution: names the ATS an apply link points to. It never clicks, follows, or fetches a link. */
(() => {
  if (globalThis.PortalHandoff) return;
  // ats ids match the adapter ids. support: routed (adapter on real hosts), prepared (synthetic unrouted adapter),
  // inspect_only (frame inspection, no adapter), fallback (answer sheet fallback only). Host lists are UNVERIFIED except where routed.
  const RULES = [
    [/(^|\.)(myworkdayjobs|myworkdaysite)\.com$/, "workday", "routed"],
    [/(^|\.)greenhouse\.io$/, "greenhouse", "routed"],
    [/^careers\.(marsh|franklintempleton)\.com$/, "phenom", "routed"],
    [/(^|\.)lever\.co$/, "lever", "prepared"],
    [/(^|\.)ashbyhq\.com$/, "ashby", "prepared"],
    [/(^|\.)oraclecloud\.com$/, "oracle", "prepared"],
    [/(^|\.)taleo\.net$/, "taleo", "prepared"],
    [/(^|\.)(successfactors\.(com|eu)|sapsf\.(com|eu)|jobs2web\.com)$/, "successfactors", "prepared"],
    [/(^|\.)smartrecruiters\.com$/, "smartrecruiters", "prepared"],
    [/(^|\.)(brassring|kenexa)\.com$/, "brassring", "prepared"],
    [/(^|\.)eightfold\.ai$/, "eightfold", "prepared"],
    [/(^|\.)icims\.com$/, "icims", "inspect_only"],
    [/(^|\.)(jibeapply\.com|avature\.net|hrmdirect\.com|workable\.com|dayforcehcm\.com)$/, "other", "fallback"]
  ];
  const APPLY = /\b(apply|start application|begin application|continue to application)\b/i;
  const clean = text => text.replace(/\s+/g, " ").trim().slice(0, 80);
  const shown = node => {
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || item.getAttribute("aria-hidden") === "true" || style.display === "none" || style.visibility === "hidden") return false;
    }
    return node.getClientRects().length > 0;
  };

  function resolve(href, base = location.href) {
    let url;
    try { url = new URL(href, base); } catch { return null; }
    if (url.protocol !== "https:" || url.username || url.password) return null;
    const host = url.hostname.toLowerCase();
    const rule = RULES.find(([pattern]) => pattern.test(host));
    return {host, ats: rule ? rule[1] : "unknown", support: rule ? rule[2] : "fallback"};
  }

  // Redirect links (trackers, shorteners) resolve to their own host and stay "unknown"; the person follows them manually.
  function scan(doc = document) {
    const seen = new Set(), links = [];
    for (const node of doc.querySelectorAll("a[href]")) {
      if (!shown(node) || node.closest("#portal-panel-host")) continue;
      const label = clean(node.textContent || node.getAttribute("aria-label") || "");
      if (!APPLY.test(label)) continue;
      const target = resolve(node.getAttribute("href"));
      if (!target) continue;
      const key = `${target.host}|${label}`;
      if (seen.has(key)) continue;
      seen.add(key);
      links.push({label, ...target});
    }
    return links.slice(0, 20);
  }

  globalThis.PortalHandoff = {resolve, scan};
})();
