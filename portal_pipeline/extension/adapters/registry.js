/* One registry maps a page location to the adapter that owns it; generic is the fallback. */
(() => {
  if (globalThis.PortalAdapters) return;
  const METHODS = ["humanGate", "scan", "propose", "fill", "upload", "verify", "nextStep", "detectFinalReview"];
  const MODES = ["fill", "answer_sheet_only"], STRATEGIES = ["native_setter", "trusted_keystrokes"];
  const adapters = [];

  function register(adapter) {
    if (!adapter || typeof adapter.id !== "string" || !adapter.id) throw new Error("Adapter needs a string id.");
    if (adapters.some(item => item.id === adapter.id)) throw new Error(`Adapter id already registered: ${adapter.id}`);
    for (const method of METHODS) if (typeof adapter[method] !== "function") throw new Error(`Adapter ${adapter.id} is missing method ${method}.`);
    if (!Array.isArray(adapter.hosts) || !adapter.hosts.every(host => host instanceof RegExp)) throw new Error(`Adapter ${adapter.id} needs hosts as a RegExp array.`);
    if (!MODES.includes(adapter.mode)) throw new Error(`Adapter ${adapter.id} has an invalid mode.`);
    if (!STRATEGIES.includes(adapter.fillStrategy)) throw new Error(`Adapter ${adapter.id} has an invalid fillStrategy.`);
    adapters.push(adapter);
    return adapter;
  }

  function forLocation(url) {
    let host = "";
    try { host = new URL(url).hostname; } catch { host = ""; }
    const match = host && adapters.find(adapter => adapter.id !== "generic" && adapter.hosts.some(pattern => pattern.test(host)));
    return match || adapters.find(adapter => adapter.id === "generic") || null;
  }

  const list = () => adapters.map(({id, version, mode, hosts}) => ({id, version, mode, hosts: hosts.map(host => host.source)}));

  globalThis.PortalAdapters = {register, forLocation, list};
})();
