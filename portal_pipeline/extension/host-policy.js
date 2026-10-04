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

  globalThis.PortalHostPolicy = {supported, assertSupported};
})();
