/* Keep popup and repeated scans on the same supported page boundary. */
(() => {
  function supported(targetUrl, pairedServer) {
    try {
      const url = new URL(targetUrl);
      if (!["http:", "https:"].includes(url.protocol)) return false;
      const localFixture = !!pairedServer && url.origin === pairedServer && url.pathname === "/fixture";
      return localFixture || /(^|\.)(myworkdayjobs\.com|greenhouse\.io)$/.test(url.hostname);
    } catch { return false; }
  }

  function assertSupported(targetUrl, pairedServer) {
    if (!supported(targetUrl, pairedServer)) throw new Error("Development is limited to Workday, Greenhouse, or the paired local fixture.");
  }

  globalThis.PortalHostPolicy = {supported, assertSupported};
})();
