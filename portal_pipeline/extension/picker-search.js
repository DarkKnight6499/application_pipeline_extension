/* Search-picker helper: tries each known name in order, selects only one exact option match, else reports a fallback. */
(() => {
  if (globalThis.PortalPickerSearch) return;
  const normalize = value => String(value ?? "").toLowerCase().replace(/[^a-z0-9\s]+/g, " ").replace(/\s+/g, " ").trim();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  function typeInto(input, text) {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), "value")?.set;
    setter ? setter.call(input, text) : (input.value = text);
    input.dispatchEvent(new Event("input", {bubbles: true}));
  }

  // options() returns the currently visible [{label, node}]; settles when the list stops changing or the wait ends.
  async function settledOptions(options, waitMs, stepMs) {
    const deadline = performance.now() + waitMs;
    let last = "", stable = 0, current = [];
    do {
      await sleep(stepMs);
      current = options();
      const signature = current.map(item => item.label).join("|");
      stable = signature && signature === last ? stable + 1 : 0;
      last = signature;
    } while (stable < 2 && performance.now() < deadline);
    return current;
  }

  async function searchAndChoose({input, candidates, options, click, fallback = "", guard = () => {}, waitMs = 1500, stepMs = 60}) {
    const wanted = candidates.map(normalize).filter(Boolean);
    if (!wanted.length) throw new Error("Provide at least one name to search for.");
    const tried = [];
    for (const candidate of candidates) {
      guard();
      typeInto(input, candidate);
      tried.push(candidate);
      const found = await settledOptions(options, waitMs, stepMs);
      guard();
      const matches = found.filter(item => wanted.includes(normalize(item.label)));
      if (matches.length > 1) { typeInto(input, ""); return {status: "ambiguous", tried}; }
      if (matches.length === 1) { click(matches[0].node); return {status: "selected", label: matches[0].label, tried}; }
    }
    typeInto(input, "");
    return {status: "fallback", text: fallback, tried};
  }

  globalThis.PortalPickerSearch = {normalize, searchAndChoose};
})();
