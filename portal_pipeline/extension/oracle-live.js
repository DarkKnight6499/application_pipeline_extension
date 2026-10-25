/* Oracle Fusion candidate-experience hosts: fill mode with the grid combobox adapter; honeypot and code fields stay out of scans. */
(() => {
  if (!globalThis.PortalAdapters || !globalThis.PortalOracleAdapter || PortalAdapters.list().some(item => item.id === "oracle-jpmc")) return;
  const base = PortalOracleAdapter;
  const generic = PortalAdapters.forLocation("");
  // Application-mode brokering needs a backend application id, which this local run never allocates.
  PortalAdapters.register({...base, id: "oracle-jpmc", version: "live-1", hosts: [/(^|\.)oraclecloud\.com$/], mode: "fill", requiresApplicationMode: false,
    fill: generic.fill, upload: generic.upload});
})();
