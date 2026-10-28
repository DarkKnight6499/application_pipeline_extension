/* No live Oracle form contract has been verified. */
(() => {
  // Config
  const adapterId = "oracle-jpmc";
  const hosts = [/^jpmc\.fa\.oraclecloud\.com$/];
  const dialogSelector = '[role="dialog"],dialog[open],[aria-modal="true"]';

  if (!globalThis.PortalAdapters || !globalThis.PortalOracleAdapter || PortalAdapters.list().some(item => item.id === adapterId)) return;
  const base = PortalOracleAdapter;
  const generic = PortalAdapters.forLocation("");
  // Application-mode brokering needs a backend application id, which this local run never allocates.
  PortalAdapters.register({...base, id: adapterId, version: "live-1", hosts, mode: "fill", requiresApplicationMode: false,
    humanGate(doc) {
      const gate = base.humanGate(doc);
      if (gate) return gate;
      const open = [...doc.querySelectorAll(dialogSelector)].some(node => {
        for (let item = node; item; item = item.parentElement) {
          const style = getComputedStyle(item);
          if (item.hidden || item.getAttribute("aria-hidden") === "true" || style.display === "none"
              || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
        }
        return node.getClientRects().length > 0;
      });
      return open ? {kind: "dialog", evidence: "Visible dialog requires manual review"} : null;
    },
    fill: generic.fill, upload: generic.upload});
})();
