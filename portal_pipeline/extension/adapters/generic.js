/* Generic adapter wraps the engine's legacy field logic; workday reuses it unchanged. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "generic")) return;
  // Passwords are protected per control, never gated page-wide; mfa and email_code kinds are reserved for adapters.
  const GATES = [
    ['iframe[src*="hcaptcha"]', "captcha", "hCaptcha frame"],
    ['iframe[src*="recaptcha"]', "captcha", "reCAPTCHA frame"],
    ['[class*="cf-turnstile"]', "captcha", "Turnstile widget"]
  ];
  const core = () => PortalEngine.core;

  const generic = {
    id: "generic", version: "1", hosts: [], mode: "fill", fillStrategy: "native_setter",
    humanGate(doc) {
      for (const [selector, kind, evidence] of GATES) if (doc.querySelector(selector)) return {kind, evidence};
      return null;
    },
    scan: (profile, options) => core().scan(profile, options),
    propose: (field, profile, context) => core().propose(field, profile, context),
    fill(control, proposal, guard) {
      if (this.fillStrategy !== "native_setter") throw new Error(`Fill strategy ${this.fillStrategy} is not enabled.`);
      return core().fill(control, proposal, guard);
    },
    upload: (control, attachment, guard) => core().fill(control, guard.selection, {...guard, attachment}),
    verify: (control, expected) => core().verify(control, expected),
    nextStep: () => ({kind: "none", label: "", ref: null}),
    detectFinalReview: () => ({final: false, reasons: []})
  };
  PortalAdapters.register(generic);
  PortalAdapters.register({...generic, id: "workday", hosts: [/(^|\.)myworkdayjobs\.com$/]});
})();
