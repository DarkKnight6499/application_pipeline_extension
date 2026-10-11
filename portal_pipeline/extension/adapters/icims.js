/* iCIMS preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "icims")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  // The iCIMS form is reported to sit inside a same-origin frame. frameFill marks the only adapter kind the page bridge
  // will serve scan, fill, and mode commands for inside a frame. With hosts empty it never routes a real frame.
  const adapter = {
    ...generic,
    id: "icims",
    version: "synthetic-1",
    hosts: [],
    mode: "fill",
    fillStrategy: "native_setter",
    frameFill: true
  };
  globalThis.PortalIcimsAdapter = adapter;
  PortalAdapters.register(adapter);
})();
