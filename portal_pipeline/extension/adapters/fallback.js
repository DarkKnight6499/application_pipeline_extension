/* Answer-sheet-only fallback for hosts with no registered adapter. It scans read-only and never writes. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "fallback")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const reason = "This site has no verified adapter. Fill is disabled; use the answer sheet and complete the page yourself.";
  const refuse = (control, proposal) =>
    ({id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason});

  const adapter = {
    ...generic,
    id: "fallback",
    version: "1",
    hosts: [],
    mode: "answer_sheet_only",
    requiresApplicationMode: true,
    fillStrategy: "native_setter",
    fill: refuse,
    upload: refuse
  };
  globalThis.PortalFallbackAdapter = adapter;
  PortalAdapters.register(adapter);
  globalThis.PortalFallbackActive = true;
})();
