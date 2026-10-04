/* Phenom wizard adapter built from synthetic pages only; every selector is UNVERIFIED against a real export. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "phenom")) return;
  // Hosts come from the job-scrap career-site list; the apply host is UNVERIFIED.
  const HOSTS = [/(^|\.)careers\.marsh\.com$/, /(^|\.)careers\.franklintempleton\.com$/];
  const CAPTCHA = [
    ['iframe[src*="recaptcha"]', "reCAPTCHA frame"],
    ['iframe[title*="recaptcha" i]', "reCAPTCHA frame"],
    [".g-recaptcha", "reCAPTCHA widget"],
    ["[data-sitekey]", "CAPTCHA site key"]
  ];
  const NEXT_LABELS = /^(next|continue|save and continue|save & continue)$/i;
  const SUBMIT_LABELS = /^(?:review and )?submit(?: application)?$|^apply(?: now)?$|^finish$|^send application$/i;
  const STEP_COUNT = /(\d+)\s+of\s+(\d+)/i;
  const generic = PortalAdapters.forLocation("");
  const core = () => PortalEngine.core;

  const shown = node => !node.closest('[hidden],[aria-hidden="true"]') && getComputedStyle(node).display !== "none";
  const buttons = doc => [...doc.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"]')].filter(shown);
  const labelOf = node => (node.value && node.tagName === "INPUT" ? node.value : node.textContent).replace(/\s+/g, " ").trim();

  function stepInfo(doc) {
    const current = doc.querySelector('nav [aria-current="step"],ol [aria-current="step"]');
    const text = current ? current.textContent.replace(/\s+/g, " ").trim() : "";
    const counter = text.match(STEP_COUNT);
    const heading = counter ? text.replace(counter[0], "").trim() : (doc.querySelector("h1,h2")?.textContent.trim() || "");
    return {index: counter ? Number(counter[1]) : null, total: counter ? Number(counter[2]) : null, heading};
  }

  function detectFinalReview(doc = document) {
    const shared = globalThis.PortalProgress?.detectFinalReview(doc);
    const info = stepInfo(doc), submit = buttons(doc).filter(node => SUBMIT_LABELS.test(labelOf(node)));
    const last = info.index !== null && info.index === info.total;
    const reasons = [...(shared?.reasons || [])];
    if (submit.length) reasons.push("Submit control present");
    if (submit.length && last) reasons.push(`Step ${info.index} of ${info.total}`);
    if (submit.length && /review/i.test(info.heading)) reasons.push("Review heading");
    return {final: reasons.length > 0, reasons};
  }

  function nextStep() {
    if (detectFinalReview().final) {
      const submit = buttons(document).find(node => SUBMIT_LABELS.test(labelOf(node)));
      return {kind: "final_review", label: submit ? labelOf(submit) : "", ref: null};
    }
    if (globalThis.PortalProgress) return PortalProgress.nextStep(document);
    const next = buttons(document).filter(node => NEXT_LABELS.test(labelOf(node)));
    if (next.length > 1) return {kind: "ambiguous", label: "", ref: null};
    if (next.length === 1) return {kind: "next", label: labelOf(next[0]), ref: null};
    const submit = buttons(document).filter(node => SUBMIT_LABELS.test(labelOf(node)));
    return submit.length ? {kind: "submit", label: labelOf(submit[0]), ref: null} : {kind: "none", label: "", ref: null};
  }

  PortalAdapters.register({
    ...generic, id: "phenom", version: "1", hosts: HOSTS, mode: "fill", fillStrategy: "native_setter",
    humanGate(doc) {
      const commonGate = generic.humanGate(doc);
      if (commonGate) return commonGate;
      for (const [selector, evidence] of CAPTCHA) if (doc.querySelector(selector)) return {kind: "captcha", evidence};
      return null;
    },
    // The scanner reads only the top document, so the LinkedIn import iframe is never entered or written.
    scan: (profile, options) => core().scan(profile, options),
    nextStep, detectFinalReview, stepInfo
  });
})();
