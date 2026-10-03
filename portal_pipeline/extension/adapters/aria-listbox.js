/* A bounded adapter for select-only comboboxes with an explicitly owned listbox. */
(() => {
  if (globalThis.PortalListbox) return;
  const normalize = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = node => node?.isConnected && !node.hidden && getComputedStyle(node).visibility !== "hidden" && node.getClientRects().length > 0;
  const disabled = node => node.disabled || node.getAttribute("aria-disabled") === "true" || !!node.closest('[aria-disabled="true"]');
  const optionLabel = node => (node.getAttribute("aria-label") || node.textContent).trim();
  const safeClick = node => {
    const action = node.closest('a,button,input,select,textarea,[role="button"]');
    if (action && action !== node) return false;
    return ["DIV", "SPAN", "LI"].includes(node.tagName) || (node.tagName === "BUTTON" && node.type === "button");
  };

  function contract(element) {
    if (element.getAttribute("role") !== "combobox" || !safeClick(element) || element.isContentEditable
        || element.querySelector("input,select,textarea,button,a,[contenteditable=true]")) throw new Error("This custom dropdown needs a portal-specific adapter.");
    if (disabled(element) || element.getAttribute("aria-readonly") === "true") throw new Error("This custom dropdown cannot be edited.");
    if (!['false', 'true'].includes(element.getAttribute("aria-expanded"))
        || ![null, "listbox"].includes(element.getAttribute("aria-haspopup"))) throw new Error("Only a select-only listbox dropdown is supported.");
    const ids = (element.getAttribute("aria-controls") || "").trim().split(/\s+/).filter(Boolean);
    if (ids.length !== 1) throw new Error("The dropdown must identify exactly one listbox using aria-controls.");
    const owners = [...document.querySelectorAll('[role="combobox"]')].filter(node => node.getAttribute("aria-controls")?.trim() === ids[0]);
    if (owners.length !== 1 || owners[0] !== element) throw new Error("The dropdown's listbox ownership is ambiguous.");
    const popups = [...document.querySelectorAll(`#${CSS.escape(ids[0])}`)];
    if (popups.length > 1) throw new Error("The dropdown's listbox ID is duplicated.");
    const popup = popups[0];
    if (popup && (popup.getAttribute("role") !== "listbox" || popup.getAttribute("aria-multiselectable") === "true")) throw new Error("The owned popup is not a single-select listbox.");
    const nodes = popup ? [...popup.querySelectorAll('[role="option"]')].filter(node => node.closest('[role="listbox"]') === popup) : [];
    const choices = nodes.map(node => ({value: optionLabel(node), label: optionLabel(node),
      disabled: !!disabled(node) || !safeClick(node) || !!node.querySelector("a,button,input,select,textarea,[role=button]")}));
    return {popup, nodes, choices};
  }

  function describe(element) {
    try { return {supported: true, reason: "", options: contract(element).choices}; }
    catch (error) { return {supported: false, reason: error.message, options: []}; }
  }

  function read(element) {
    if (element.hasAttribute("aria-valuetext")) return element.getAttribute("aria-valuetext");
    return element.value ?? element.textContent.trim();
  }

  function identity(element) {
    return [element.getAttribute("aria-controls"), element.getAttribute("aria-haspopup"), element.id,
      element.getAttribute("role"), element.getAttribute("aria-label"), element.getAttribute("aria-labelledby"), element.tagName, element.type].join("|");
  }

  async function choose(element, answer, guard) {
    const wanted = normalize(answer);
    if (!wanted) throw new Error("Provide an answer before selecting this dropdown.");
    let state = contract(element);
    const initialIdentity = identity(element), initialValue = read(element);
    const snapshot = JSON.stringify(state.choices);
    const hadChoices = state.choices.length > 0;
    const assertCurrent = () => {
      guard();
      if (!visible(element) || identity(element) !== initialIdentity) throw new Error("The dropdown identity changed while opening. Rescan before filling.");
      if (read(element) !== initialValue) throw new Error("The dropdown value changed while opening. Rescan before filling.");
      const current = contract(element);
      if (hadChoices && JSON.stringify(current.choices) !== snapshot) throw new Error("The dropdown options changed while opening. Rescan before filling.");
      return current;
    };
    assertCurrent();
    if (element.getAttribute("aria-expanded") === "false") element.click();
    const deadline = performance.now() + 1200;
    do {
      state = assertCurrent();
      if (element.getAttribute("aria-expanded") === "true" && visible(state.popup) && state.choices.length) break;
      await new Promise(resolve => setTimeout(resolve, 50));
    } while (performance.now() < deadline);
    if (element.getAttribute("aria-expanded") !== "true" || !visible(state.popup)) throw new Error("The owned listbox did not open. Choose this answer manually.");
    const matches = state.choices.map((choice, index) => ({choice, node: state.nodes[index]}))
      .filter(({choice, node}) => !choice.disabled && visible(node) && normalize(choice.label) === wanted);
    if (matches.length !== 1) throw new Error("No unique exact listbox option matches the answer. Choose this answer manually.");
    assertCurrent();
    const match = matches[0];
    if (!match.node.isConnected || match.node.closest('[role="listbox"]') !== state.popup) throw new Error("The dropdown option was replaced. Rescan before filling.");
    match.node.click();
    return match.choice.label;
  }

  globalThis.PortalListbox = {describe, read, identity, choose};
})();
