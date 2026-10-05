/* Synthetic Workday adapter. Page selectors remain UNVERIFIED against a real export. */
(() => {
  if (!globalThis.PortalAdapters || PortalAdapters.list().some(item => item.id === "workday")) return;
  const generic = PortalAdapters.forLocation("");
  if (!generic) return;
  PortalAdapters.register({...generic, id: "workday", hosts: [/(^|\.)myworkdayjobs\.com$/]});
})();
