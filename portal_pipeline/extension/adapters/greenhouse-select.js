/* Greenhouse job-boards react-select adapter. DOM contract observed on a live public posting, see docs/GREENHOUSE_CONTRACT.md. */
(() => {
  if (globalThis.PortalGreenhouseSelect) return;
  const OPEN_TIMEOUT_MS = 1500, OPEN_RETRY_MS = 400, SETTLE_TIMEOUT_MS = 1200, POLL_MS = 50;
  const normalize = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = node => node?.isConnected && !node.closest('[aria-hidden="true"],[hidden]')
    && getComputedStyle(node).visibility !== "hidden" && node.getClientRects().length > 0;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  function shellOf(element) {
    const shell = element.closest(".select-shell"), control = element.closest(".select__control");
    return shell && control && shell.contains(control) ? {shell, control} : null;
  }

  function matches(element) {
    const gh = globalThis.PortalGreenhouse;
    return !!gh?.active() && !!gh.formFor(element) && element.tagName === "INPUT" && element.getAttribute("role") === "combobox"
      && element.classList.contains("select__input") && !!shellOf(element);
  }

  function contract(element) {
    const parts = shellOf(element);
    if (!matches(element) || !parts) throw new Error("This custom dropdown needs a portal-specific adapter.");
    const {shell, control} = parts;
    if (element.disabled || element.readOnly || element.getAttribute("aria-disabled") === "true" || shell.querySelector('[aria-disabled="true"]:not([role="option"])')) throw new Error("This custom dropdown cannot be edited.");
    if (shell.querySelectorAll('input[role="combobox"]').length !== 1 || shell.querySelector(".select__multi-value")) throw new Error("Only a single-value Greenhouse dropdown is supported.");
    if (!element.id || document.querySelectorAll(`[id="${CSS.escape(element.id)}"]`).length !== 1) throw new Error("The dropdown ID is missing or duplicated.");
    if (element.getAttribute("aria-expanded") !== "false") throw new Error("Close the dropdown before filling it.");
    return {shell, control};
  }

  function describe(element) {
    try {
      contract(element);
      return {supported: true, reason: "", options: [], dropdown_state: {popup_present: false, expanded: false, options_observed: false}};
    } catch (error) { return {supported: false, reason: error.message, options: [], dropdown_state: null}; }
  }

  function read(element) {
    const container = element.closest(".select__value-container");
    return container?.querySelector(".select__single-value")?.textContent.trim() ?? "";
  }

  // aria-controls is absent while the menu is closed, so it must not be part of the identity.
  function identity(element) {
    return ["greenhouse-select", element.id, element.getAttribute("role"), element.getAttribute("aria-labelledby"), element.tagName, element.type].join("|");
  }

  function popupOf(element) {
    const id = element.getAttribute("aria-controls");
    const popups = id ? [...document.querySelectorAll(`[id="${CSS.escape(id)}"]`)] : [];
    const popup = popups.length === 1 ? popups[0] : null;
    if (!popup || popup.getAttribute("role") !== "listbox" || popup.getAttribute("aria-multiselectable") === "true" || !visible(popup)) return null;
    const nodes = [...popup.querySelectorAll('[role="option"]')].filter(node => node.closest('[role="listbox"]') === popup);
    return {popup, nodes, labels: nodes.map(node => node.textContent.trim())};
  }

  // react-select ignores a bare ArrowDown here; it opens when which is set and keyup follows, as in a real keypress.
  function key(element, type, name, code) {
    element.dispatchEvent(new KeyboardEvent(type, {key: name, code: name, keyCode: code, which: code, bubbles: true, cancelable: true, composed: true}));
  }

  function close(element) {
    if (element.getAttribute("aria-expanded") === "true") key(element, "keydown", "Escape", 27);
  }

  function open(element, control, attempt) {
    element.focus();
    if (attempt === 0) { key(element, "keydown", "ArrowDown", 40); key(element, "keyup", "ArrowDown", 40); }
    else control.dispatchEvent(new MouseEvent("mousedown", {bubbles: true, cancelable: true, composed: true, button: 0}));
  }

  async function choose(element, answer, guard) {
    const wanted = normalize(answer);
    if (!wanted) throw new Error("Provide an answer before selecting this dropdown.");
    const {control} = contract(element);
    const startIdentity = identity(element), startValue = read(element);
    const assertCurrent = () => {
      guard();
      if (!visible(element) || identity(element) !== startIdentity) throw new Error("The dropdown identity changed while opening. Rescan before filling.");
      if (read(element) !== startValue) throw new Error("The dropdown value changed while opening. Rescan before filling.");
    };
    assertCurrent();
    try {
      let state = null, attempt = 0, opened = performance.now();
      open(element, control, attempt);
      const deadline = performance.now() + OPEN_TIMEOUT_MS;
      while (performance.now() < deadline) {
        assertCurrent();
        if (element.getAttribute("aria-expanded") === "true" && (state = popupOf(element)) && state.nodes.length) break;
        state = null;
        if (attempt === 0 && performance.now() - opened > OPEN_RETRY_MS) { attempt = 1; open(element, control, attempt); }
        await sleep(POLL_MS);
      }
      if (!state) throw new Error("The dropdown menu did not open. Choose this answer manually.");
      const hits = state.nodes.filter((node, index) => normalize(state.labels[index]) === wanted && node.getAttribute("aria-disabled") !== "true" && visible(node));
      if (hits.length !== 1) throw new Error("No unique exact dropdown option matches the answer. Choose this answer manually.");
      assertCurrent();
      const target = hits[0], label = target.textContent.trim();
      if (!target.isConnected || target.closest('[role="listbox"]') !== state.popup || target.closest("a,button,input,select,textarea")) throw new Error("The dropdown option was replaced. Rescan before filling.");
      target.click();
      const settle = performance.now() + SETTLE_TIMEOUT_MS;
      while (performance.now() < settle && read(element) !== label) await sleep(POLL_MS);
      if (read(element) !== label) throw new Error("The dropdown did not retain the choice. Choose this answer manually.");
      return label;
    } finally { close(element); }
  }

  globalThis.PortalGreenhouseSelect = {matches, describe, read, identity, choose};
})();
