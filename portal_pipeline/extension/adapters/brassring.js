/* BrassRing preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "brassring")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const honeypot = /(honey.?pot|bee.?catcher|robots? only|do not enter if you are human|do not enter if you.?re human|leave (this )?(field )?(blank|empty))/i;

  const shown = node => {
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    }
    return node.getClientRects().length > 0;
  };
  // A visible password field means sign-in or account creation, which the person handles.
  function humanGate(doc) {
    const common = generic.humanGate(doc);
    if (common) return common;
    return [...doc.querySelectorAll('input[type="password"]')].some(shown) ? {kind: "sign_in", evidence: "Visible password field"} : null;
  }

  const refuse = (control, proposal) => {
    const reason = "BrassRing fill is disabled until a real export establishes the host and form contract.";
    return {id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason};
  };

  const adapter = {
    ...generic,
    id: "brassring",
    version: "synthetic-1",
    hosts: [],
    mode: "answer_sheet_only",
    requiresApplicationMode: true,
    fillStrategy: "native_setter",
    humanGate,
    scan(profile, options) {
      return PortalEngine.core.scan(profile, options).filter(field =>
        !honeypot.test(`${field.label} ${field.structure?.dom_id || ""} ${field.structure?.name || ""}`));
    },
    fill: refuse,
    upload: refuse
  };
  globalThis.PortalBrassRingAdapter = adapter;
  PortalAdapters.register(adapter);
})();
