/* Ashby preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "ashby")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const honeypot = /(honey.?pot|bee.?catcher|robots? only|do not enter if you are human|do not enter if you.?re human|leave (this )?(field )?(blank|empty))/i;

  const refuse = (control, proposal) => {
    const reason = "Ashby fill is disabled until a real export establishes the host and form contract.";
    return {id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason};
  };

  const adapter = {
    ...generic,
    id: "ashby",
    version: "synthetic-1",
    hosts: [],
    mode: "answer_sheet_only",
    requiresApplicationMode: true,
    fillStrategy: "native_setter",
    scan(profile, options) {
      return PortalEngine.core.scan(profile, options).filter(field =>
        !honeypot.test(`${field.label} ${field.structure?.dom_id || ""} ${field.structure?.name || ""}`));
    },
    fill: refuse,
    upload: refuse
  };
  globalThis.PortalAshbyAdapter = adapter;
  PortalAdapters.register(adapter);
})();
