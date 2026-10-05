/* Oracle preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "oracle")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const honeypot = /(honey.?pot|bee.?catcher|robots? only|do not enter if you are human|do not enter if you.?re human|leave (this )?(field )?(blank|empty))/i;
  const emailHeading = /\b(verify|confirm|verification)\b.*\b(email|e-mail)\b|\b(email|e-mail)\b.*\b(verify|confirm|verification)\b/i;
  const codeLabel = /\b(verification|email|e-mail|one.time)\s+(code|passcode)\b/i;
  const shown = node => {
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    }
    return node.getClientRects().length > 0;
  };

  function humanGate(doc) {
    const captcha = generic.humanGate(doc);
    if (captcha) return captcha;
    const heading = [...doc.querySelectorAll("h1,h2,h3,[role=heading]")].some(node => shown(node) && emailHeading.test(node.textContent));
    const code = [...doc.querySelectorAll("input")].some(node => shown(node) &&
      (node.autocomplete === "one-time-code" || [...(node.labels || [])].some(label => codeLabel.test(label.textContent))));
    return heading && code ? {kind: "email_code", evidence: "Visible email verification heading and code input"} : null;
  }

  // This pure transition needs an application-scoped stored mode before production use.
  function nextMode(previousMode, gate) {
    return previousMode === "fill" && gate?.kind !== "captcha" ? "fill" : "answer_sheet_only";
  }

  const refuse = (control, proposal) => {
    const reason = "Oracle fill is disabled until a real export establishes the host and form contract.";
    return {id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason};
  };

  const adapter = {
    ...generic,
    id: "oracle",
    version: "synthetic-1",
    hosts: [],
    mode: "answer_sheet_only",
    requiresApplicationMode: true,
    fillStrategy: "native_setter",
    humanGate,
    scan(profile, options) {
      return PortalEngine.core.scan(profile, options).filter(field => {
        const identity = `${field.label} ${field.structure?.dom_id || ""} ${field.structure?.name || ""}`;
        return !honeypot.test(identity) && !codeLabel.test(identity);
      });
    },
    fill: refuse,
    upload: refuse,
    nextMode
  };
  globalThis.PortalOracleAdapter = adapter;
  PortalAdapters.register(adapter);
})();
