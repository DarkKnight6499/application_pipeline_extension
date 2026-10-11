/* Taleo preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "taleo")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const REVIEW = /\b(review|summary|confirm)\b/i;
  const shown = node => {
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    }
    return node.getClientRects().length > 0;
  };
  const passwords = doc => [...doc.querySelectorAll('input[type="password"]')].filter(shown);

  // Taleo opens on a sign-in or account page. A visible password field means the person handles it, so writes stop.
  function humanGate(doc) {
    const common = generic.humanGate(doc);
    if (common) return common;
    return passwords(doc).length ? {kind: "sign_in", evidence: "Visible password field"} : null;
  }

  // Strict page detection: anything that is not clearly a sign-in or review page is a form only when it has fields.
  function pageKind(doc = document) {
    if (passwords(doc).length) return "sign_in";
    const heading = doc.querySelector("h1,h2")?.textContent || "";
    if (REVIEW.test(heading)) return "review";
    const fields = [...doc.querySelectorAll("input,select,textarea")].filter(node => shown(node) && !["hidden", "button", "submit"].includes(node.type));
    return fields.length ? "form" : "unknown";
  }

  const adapter = {
    ...generic,
    id: "taleo",
    version: "synthetic-1",
    hosts: [],
    mode: "fill",
    fillStrategy: "native_setter",
    humanGate,
    pageKind,
    // Legacy Taleo buttons are native submit inputs, which the shared progression denylist never treats as Next.
    nextStep: () => pageKind() === "review" ? {kind: "final_review", label: "", ref: null}
      : globalThis.PortalProgress ? PortalProgress.nextStep(document) : {kind: "none", label: "", ref: null}
  };
  globalThis.PortalTaleoAdapter = adapter;
  PortalAdapters.register(adapter);
})();
