/* SmartRecruiters preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "smartrecruiters")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const honeypot = /(honey.?pot|bee.?catcher|robots? only|do not enter if you are human|do not enter if you.?re human|leave (this )?(field )?(blank|empty))/i;

  const refuse = (control, proposal) => {
    const reason = "SmartRecruiters fill is disabled until a real export establishes the host and form contract.";
    return {id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason};
  };

  const adapter = {
    ...generic,
    id: "smartrecruiters",
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
  globalThis.PortalSmartRecruitersAdapter = adapter;
  PortalAdapters.register(adapter);
})();
