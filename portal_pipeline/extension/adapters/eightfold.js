/* Eightfold preparation uses synthetic markup only. No real host or form contract has been verified. */
(() => {
  if (!globalThis.PortalAdapters || globalThis.PortalAdapters.list().some(item => item.id === "eightfold")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;

  const BANNER = '[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i]';
  const CHOICE = /\b(accept|agree|allow|reject|decline|got it|manage|preferences|settings)\b/i;
  const shown = node => {
    for (let item = node; item; item = item.parentElement) {
      const style = getComputedStyle(item);
      if (item.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
    }
    return node.getClientRects().length > 0;
  };

  // A visible cookie banner holds the page until the person dismisses it; the adapter never clicks it.
  function cookieBanner(doc) {
    return [...doc.querySelectorAll(BANNER)].some(node => shown(node) && !node.querySelector("form,input:not([type=checkbox]),select,textarea")
      && [...node.querySelectorAll('button,[role="button"],a')].some(control => shown(control) && CHOICE.test(control.textContent)));
  }

  const adapter = {
    ...generic,
    id: "eightfold",
    version: "synthetic-1",
    hosts: [],
    mode: "fill",
    fillStrategy: "native_setter",
    humanGate(doc) {
      const common = generic.humanGate(doc);
      if (common) return common;
      return cookieBanner(doc) ? {kind: "cookie_banner", evidence: "Visible cookie banner with accept or reject controls"} : null;
    }
  };
  globalThis.PortalEightfoldAdapter = adapter;
  PortalAdapters.register(adapter);
})();
