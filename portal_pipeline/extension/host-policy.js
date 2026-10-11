/* Keep popup and repeated scans on the same supported page boundary. */
(() => {
  function supported(targetUrl, pairedServer) {
    try {
      const url = new URL(targetUrl);
      if (!["http:", "https:"].includes(url.protocol)) return false;
      const localFixture = !!pairedServer && url.origin === pairedServer && url.pathname === "/fixture";
      // Registered non-generic adapters define the supported hosts; the literal pattern covers pages without the registry.
      const adapter = globalThis.PortalAdapters?.forLocation(targetUrl);
      const hosted = adapter ? adapter.id !== "generic" : /(^|\.)(myworkdayjobs\.com|greenhouse\.io)$/.test(url.hostname);
      return localFixture || hosted;
    } catch { return false; }
  }

  function assertSupported(targetUrl, pairedServer) {
    if (!supported(targetUrl, pairedServer)) throw new Error("Development is limited to Workday, Greenhouse, or the paired local fixture.");
  }

  // Unrouted public https hosts get the read-only answer-sheet fallback; loopback, private, and non-https targets stay rejected.
  function fallbackEligible(targetUrl) {
    try {
      const url = new URL(targetUrl), host = url.hostname.toLowerCase();
      if (url.protocol !== "https:" || url.username || url.password) return false;
      if (host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local") || host.endsWith(".internal")) return false;
      if (!host.includes(".") || host.includes(":")) return false;
      if (/^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return false;
      return true;
    } catch { return false; }
  }

  // "native" keeps the existing routing; "fallback" injects the answer-sheet-only adapter; null is rejected.
  function mode(targetUrl, pairedServer) {
    if (supported(targetUrl, pairedServer)) return "native";
    return fallbackEligible(targetUrl) ? "fallback" : null;
  }

  function assertAllowed(targetUrl, pairedServer) {
    const result = mode(targetUrl, pairedServer);
    if (!result) assertSupported(targetUrl, pairedServer);
    return result;
  }

  globalThis.PortalHostPolicy = {supported, assertSupported, fallbackEligible, mode, assertAllowed};
})();
