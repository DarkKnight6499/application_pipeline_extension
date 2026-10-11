/* SuccessFactors preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "successfactors")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const PREVIEW_HEADING = /\b(profile|preview|parsed|extracted|review your information)\b/i;
  const clean = text => text.replace(/\s+/g, " ").replace(/[*✱]/g, "").trim();
  const shown = node => !node.closest('[hidden],[aria-hidden="true"]') && getComputedStyle(node).display !== "none" && node.getClientRects().length > 0;

  // A resume parse can silently diverge from the stored profile, so the parsed values are listed for the person to compare.
  // Read only: nothing here writes, focuses, or clicks.
  function profilePreview(doc = document) {
    const regions = [...doc.querySelectorAll("section,fieldset,[role=region],[role=group]")]
      .filter(node => shown(node) && PREVIEW_HEADING.test(node.querySelector("h1,h2,h3,h4,legend,[role=heading]")?.textContent || ""));
    const rows = [];
    for (const region of regions) {
      for (const node of region.querySelectorAll("input,select,textarea")) {
        if (!shown(node) || ["password", "hidden", "file", "checkbox", "radio", "button", "submit"].includes(node.type)) continue;
        const label = clean([...(node.labels || [])].map(item => item.textContent).join(" ") || node.getAttribute("aria-label") || node.name || "");
        const value = node.tagName === "SELECT" ? node.selectedOptions[0]?.textContent.trim() || "" : node.value;
        rows.push({label, value, dom_id: node.id});
      }
    }
    return rows;
  }

  const adapter = {
    ...generic,
    id: "successfactors",
    version: "synthetic-1",
    hosts: [],
    mode: "fill",
    fillStrategy: "native_setter",
    profilePreview
  };
  globalThis.PortalSuccessFactorsAdapter = adapter;
  PortalAdapters.register(adapter);
})();
