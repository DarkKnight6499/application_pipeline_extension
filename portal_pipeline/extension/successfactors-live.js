/* Author: Yazad Madan. CLI registration is scoped to the detected page host; live form compatibility is unverified. */
(() => {
  if (!globalThis.PortalSuccessFactorsAdapter || !globalThis.PortalSuccessFactorsDetection
      || PortalAdapters.list().some(item => item.id === "successfactors-cli")
      || !PortalSuccessFactorsDetection.matches(location.href)) return;
  const base = PortalSuccessFactorsAdapter;
  const MANUAL = /\b(consent|agree\w*|accept\w*|privacy|terms|attest\w*|certif\w*|signature|sign\s+here|immigration|visa|sponsor\w*|citizen\w*|nationality|authori[sz]\w*|eligible|eligibility|(?:right|permit\w*|legal\w*)\s+(?:to\s+)?work|self[- ]?id\w*|demograph\w*|eeo|gender|sex\w*|race|ethnic\w*|veteran|disabil\w*|password)\b/i;
  const REASON = "Complete protected SuccessFactors answers and history manually.";
  const protectedField = field => field.blocked || field.record || ["file", "checkbox", "password"].includes(field.type)
    || globalThis.PortalClassifier?.hasAttestationText(field.label || "")
    || MANUAL.test(`${field.label} ${field.key || ""} ${field.structure?.name || ""} ${field.structure?.dom_id || ""}`.replace(/[_-]+/g, " "));
  const refuse = (control, proposal) => ({id: proposal?.id || control?.field?.id || "", ok: false,
    status: "refused", actual: null, reason: REASON, message: REASON});
  const host = new URL(location.href).hostname.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  PortalAdapters.register({...base, id: "successfactors-cli", version: "custom-domain-1", hosts: [new RegExp(`^${host}$`)],
    scan(profile, options) {
      return base.scan(profile, options).map(field => {
        if (protectedField(field)) Object.assign(field, {has_value: field.has_value ?? !["", false, null, undefined].includes(field.current),
          blocked: true, key: null, proposal: "", current: "",
          truth: null, status: "manual_only", manual_reason: REASON});
        return field;
      });
    },
    fill(control, proposal, guard) {
      return protectedField(control.field) ? refuse(control, proposal) : base.fill.call(this, control, proposal, guard);
    },
    upload: refuse
  });
})();
