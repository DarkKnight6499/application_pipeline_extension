/* Workday search pickers verify selected pills because the search popup structure is unknown. */
(() => {
  if (globalThis.PortalWorkdayPicker) return;
  const CONTAINER = '[data-automation-id="multiselectInputContainer"]';
  const PILL = '[data-automation-id="selectedItem"]';
  const normalize = value => String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  const matches = input => input?.tagName === "INPUT" && input.getAttribute("data-uxi-widget-type") === "selectinput"
    && !!input.closest(CONTAINER);

  function pillNodes(input) {
    const container = input.closest(CONTAINER);
    if (!container) return [];
    const owned = root => root ? [...root.querySelectorAll(PILL)].filter(node => {
      const owner = node.closest(CONTAINER);
      return owner === container || (!owner && root === container.parentElement);
    }) : [];
    const local = owned(container);
    return local.length ? local : owned(container.parentElement);
  }

  const pillLabel = node => node.querySelector('[data-automation-id="promptOption"]')?.getAttribute("data-automation-label") ?? "";
  const selected = input => pillNodes(input).map(pillLabel);

  function identity(input) {
    return [input.id, input.getAttribute("name"), input.getAttribute("data-uxi-widget-type"), input.tagName].join("|");
  }

  async function choose(input, candidates, guard = () => {}) {
    const usable = Array.isArray(candidates) ? candidates.filter(value => typeof value === "string" && normalize(value)) : [];
    if (!usable.length) throw new Error("Provide an exact candidate before selecting this picker.");
    if (!matches(input)) throw new Error("Not a Workday search picker.");
    if (input.matches(":disabled") || input.getAttribute("aria-disabled") === "true") throw new Error("This picker cannot be edited.");
    guard();
    const existing = selected(input);
    if (existing.length) return {status: "already_selected", label: existing[0]};
    const view = input.ownerDocument.defaultView;
    const setter = Object.getOwnPropertyDescriptor(view.HTMLInputElement.prototype, "value").set;
    const write = value => {
      guard();
      setter.call(input, value);
      guard();
      input.dispatchEvent(new view.Event("input", {bubbles: true}));
    };
    const waitUntil = async (condition, timeout) => {
      const deadline = performance.now() + timeout;
      for (;;) {
        guard();
        if (condition()) return true;
        if (performance.now() >= deadline) return false;
        await sleep(100);
      }
    };
    const tried = [];
    for (const candidate of usable) {
      guard();
      const before = new Set(pillNodes(input));
      input.focus();
      write(candidate);
      tried.push(candidate);
      for (const type of ["keydown", "keyup"]) {
        guard();
        input.dispatchEvent(new view.KeyboardEvent(type, {key: "Enter", code: "Enter", keyCode: 13, bubbles: true}));
      }
      await waitUntil(() => pillNodes(input).some(node => !before.has(node)) || input.value === "", 3000);
      guard();
      const added = pillNodes(input).filter(node => !before.has(node));
      if (added.length === 1 && normalize(pillLabel(added[0])) === normalize(candidate)) {
        return {status: "selected", label: pillLabel(added[0]), tried};
      }
      for (const pill of added) {
        guard();
        const remove = pill.querySelector('[data-automation-id="DELETE_charm"]');
        if (!remove) throw new Error("The unmatched picker selection cannot be removed.");
        guard();
        remove.click();
        if (!await waitUntil(() => !pillNodes(input).includes(pill), 1500)) throw new Error("The unmatched picker selection was not removed.");
      }
      write("");
    }
    write("");
    guard();
    return {status: "not_found", tried};
  }

  globalThis.PortalWorkdayPicker = {matches, selected, identity, choose};
})();
