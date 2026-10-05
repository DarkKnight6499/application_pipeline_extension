/* Generic adapter wraps the engine's legacy field logic. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "generic")) return;
  // Passwords are protected per control, never gated page-wide; mfa and email_code kinds are reserved for adapters.
  const GATES = [
    ['iframe[src*="hcaptcha"]', "captcha", "hCaptcha frame"],
    ['iframe[src*="recaptcha"]', "captcha", "reCAPTCHA frame"],
    ['[class*="cf-turnstile"]', "captcha", "Turnstile widget"]
  ];
  // Only a challenge a person can see blocks; hidden frames and the invisible reCAPTCHA badge do not.
  function visibleChallenge(node) {
    if (node.closest(".grecaptcha-badge")) return false;
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    }
    const box = node.getBoundingClientRect(), view = node.ownerDocument.defaultView;
    return box.width > 0 && box.height > 0 && box.right > 0 && box.bottom > 0 && box.left < view.innerWidth;
  }
  const core = () => PortalEngine.core;

  const generic = {
    id: "generic", version: "1", hosts: [], mode: "fill", fillStrategy: "native_setter",
    humanGate(doc) {
      for (const [selector, kind, evidence] of GATES) {
        for (const node of doc.querySelectorAll(selector)) if (visibleChallenge(node)) return {kind, evidence};
      }
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
    // Real classification needs progress.js; without it the safe constants stay.
    nextStep: () => globalThis.PortalProgress ? PortalProgress.nextStep(document) : {kind: "none", label: "", ref: null},
    detectFinalReview: doc => globalThis.PortalProgress ? PortalProgress.detectFinalReview(doc || document) : {final: false, reasons: []}
  };
  PortalAdapters.register(generic);
})();
