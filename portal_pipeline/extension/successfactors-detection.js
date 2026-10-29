/* Author: Yazad Madan. Read only RMK identity signals, never form values. */
(() => {
  if (globalThis.PortalSuccessFactorsDetection) return;
  const HOSTS = /(^|\.)(successfactors\.(com|eu)|sapsf\.(com|eu)|jobs2web\.com)$/i;
  const CUSTOM_HOSTS = new Set(["careers.provident.bank"]);
  const APPLY_PATH = /^\/talentcommunity\/apply\/\d+\/?$/;
  const JOB_PATH = /^\/job\/[^/]+\/\d+\/?$/;
  const GENERATOR = /\b(?:SAP\s+)?SuccessFactors\s+Recruiting\s+Marketing\b/i;

  function matches(href, doc = document) {
    let url;
    try { url = new URL(href); } catch { return false; }
    if (url.protocol !== "https:" || url.username || url.password) return false;
    if (CUSTOM_HOSTS.has(url.hostname) || HOSTS.test(url.hostname) || APPLY_PATH.test(url.pathname)) return true;
    const asset = [...doc.querySelectorAll('script[src],link[href]')].some(node => {
      try {
        const resource = new URL(node.getAttribute("src") || node.getAttribute("href"), doc.baseURI);
        return resource.protocol === "https:" && resource.hostname === "rmkcdn.successfactors.com" && !resource.username && !resource.password;
      } catch { return false; }
    });
    const marker = [...doc.querySelectorAll('meta[name="generator"]')]
      .some(node => GENERATOR.test(node.getAttribute("content") || ""));
    return JOB_PATH.test(url.pathname) ? asset || marker : asset && marker;
  }

  globalThis.PortalSuccessFactorsDetection = {matches};
})();
