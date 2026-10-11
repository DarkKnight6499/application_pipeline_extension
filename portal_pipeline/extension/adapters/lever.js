/* Lever preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "lever")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const WRITABLE = new Set(["text", "textarea", "email", "tel", "url"]);
  const MANUAL = "Lever fill is limited to text and textarea fields. Complete this one yourself.";
  const outside = ".application-label,.application-question label,.application-field label";
  const clean = text => text.replace(/\s+/g, " ").replace(/[*✱]/g, "").trim();

  // Lever holds some labels outside the field, so a blank or identifier-only label is read from the enclosing question block.
  function relabel(field) {
    const own = field.label && field.label !== field.structure?.name && field.label !== field.structure?.dom_id;
    if (own) return field.label;
    const node = (field.structure?.dom_id && document.getElementById(field.structure.dom_id))
      || (field.structure?.name && document.getElementsByName(field.structure.name)[0]);
    const holder = node?.closest("li,.application-question,.application-field");
    const label = holder?.querySelector(outside);
    return label ? clean(label.textContent) : field.label;
  }

  const refuse = (control, proposal, reason = MANUAL) =>
    ({id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason});

  const adapter = {
    ...generic,
    id: "lever",
    version: "synthetic-1",
    hosts: [],
    mode: "fill",
    fillStrategy: "native_setter",
    scan(profile, options) {
      return PortalEngine.core.scan(profile, options).map(field => {
        const label = relabel(field);
        const manual = !WRITABLE.has(field.type);
        return {...field, label, ...(manual ? {status: "manual_only", proposal: "", manual_reason: MANUAL} : {})};
      });
    },
    fill(control, proposal, guard) {
      return WRITABLE.has(control?.field?.type) ? generic.fill.call(this, control, proposal, guard) : refuse(control, proposal);
    },
    upload: (control, attachment, guard) => refuse(control, guard?.selection, "Lever uploads are disabled until a real export establishes the contract.")
  };
  globalThis.PortalLeverAdapter = adapter;
  PortalAdapters.register(adapter);
})();
