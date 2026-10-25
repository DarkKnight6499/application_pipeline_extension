(() => {
  if (globalThis.PortalOracleGrid) return;
  const normalize = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = node => node?.isConnected && !node.closest('[aria-hidden="true"],[hidden]')
    && getComputedStyle(node).visibility !== "hidden" && node.getClientRects().length > 0;

  const matches = element => element?.tagName === "INPUT" && element.getAttribute("role") === "combobox"
    && element.getAttribute("aria-haspopup") === "grid"
    && !["submit", "image", "button", "reset"].includes((element.getAttribute("type") || "text").toLowerCase());

  function popupFor(element) {
    const ids = (element.getAttribute("aria-controls") || "").trim().split(/\s+/).filter(Boolean);
    if (ids.length !== 1) return null;
    const found = document.querySelectorAll(`#${CSS.escape(ids[0])}`);
    return found.length === 1 && ["grid", "listbox"].includes(found[0].getAttribute("role")) ? found[0] : null;
  }

  // Oracle puts one gridcell in each row; the cell is the click target, so it is the option when a row holds exactly one.
  function optionNodes(popup) {
    if (!popup) return [];
    const picked = [];
    for (const node of popup.querySelectorAll('[role="option"],[role="row"]')) {
      if (node.closest('[role="grid"],[role="listbox"]') !== popup || !visible(node)) continue;
      if (node.parentElement.closest('[role="option"],[role="row"]')) continue;
      if (node.getAttribute("role") === "option") { picked.push(node); continue; }
      if (popup.getAttribute("role") !== "grid") continue;
      const cells = [...node.querySelectorAll('[role="gridcell"]')];
      picked.push(cells.length === 1 ? cells[0] : node);
    }
    return picked;
  }

  const optionLabel = node => (node.getAttribute("role") === "option" ? node.getAttribute("aria-label") || node.textContent : node.textContent).replace(/\s+/g, " ").trim();
  const disabled = node => node.disabled || node.getAttribute("aria-disabled") === "true";
  const read = element => element.value.trim();

  function identity(element) {
    return [element.id, element.getAttribute("name"), element.getAttribute("role"), element.getAttribute("aria-haspopup"), element.tagName].join("|");
  }

  function describe(element) {
    if (!matches(element)) return {supported: false, reason: "Not an Oracle grid combobox.", options: [], dropdown_state: null};
    if (disabled(element) || element.readOnly) return {supported: false, reason: "This menu cannot be edited.", options: [], dropdown_state: null};
    const popup = element.getAttribute("aria-expanded") === "true" ? popupFor(element) : null;
    const options = optionNodes(popup).map(node => ({value: optionLabel(node), label: optionLabel(node), disabled: !!disabled(node)}));
    return {supported: true, reason: "", options, dropdown_state: {popup_present: !!popup, expanded: element.getAttribute("aria-expanded") === "true", options_observed: options.length > 0}};
  }

  async function close(element) {
    element.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", code: "Escape", bubbles: true}));
    await sleep(100);
  }

  async function choose(element, answer, guard = () => {}) {
    const wanted = normalize(answer);
    if (!wanted) throw new Error("Provide an answer before selecting this menu.");
    const info = describe(element);
    if (!info.supported) throw new Error(info.reason);
    const startIdentity = identity(element);
    let expectedValue = read(element);
    const assertSame = () => {
      guard();
      if (!visible(element) || !matches(element) || disabled(element) || element.readOnly || identity(element) !== startIdentity) throw new Error("The menu identity changed while opening. Rescan before filling.");
      if (read(element) !== expectedValue) throw new Error("The menu value changed while opening. Rescan before filling.");
    };
    const waitForOptions = async () => {
      let popup = null;
      const deadline = performance.now() + 1500;
      do {
        await sleep(50);
        assertSame();
        popup = element.getAttribute("aria-expanded") === "true" ? popupFor(element) : null;
      } while ((!popup || !optionNodes(popup).length) && performance.now() < deadline);
      return popup;
    };
    try {
      assertSame();
      element.focus();
      assertSame();
      if (element.getAttribute("aria-expanded") !== "true") element.click();
      let popup = await waitForOptions();
      if (!popup || !optionNodes(popup).length) {
        assertSame();
        expectedValue = String(answer).trim();
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(element, expectedValue);
        element.dispatchEvent(new Event("input", {bubbles: true}));
        popup = await waitForOptions();
      }
      if (!popup || !optionNodes(popup).length) throw new Error("The menu popup did not open. Choose this answer manually.");
      const found = optionNodes(popup).filter(node => normalize(optionLabel(node)) === wanted);
      if (found.length !== 1 || disabled(found[0])) throw new Error("No unique exact option matches the answer. Choose this answer manually.");
      assertSame();
      found[0].scrollIntoView({block: "nearest"});
      await sleep(100);
      assertSame();
      if (element.getAttribute("aria-expanded") !== "true" || popupFor(element) !== popup || !optionNodes(popup).includes(found[0]) || normalize(optionLabel(found[0])) !== wanted || disabled(found[0])) throw new Error("The menu option was replaced. Rescan before filling.");
      const label = optionLabel(found[0]);
      if (found[0].closest("button[type=submit],input[type=submit],a[href]")) throw new Error("This option is a submit control. Choose this answer manually.");
      found[0].click();
      await sleep(300);
      guard();
      if (!visible(element) || identity(element) !== startIdentity) throw new Error("The menu identity changed while opening. Rescan before filling.");
      if (read(element) !== label) throw new Error("The menu did not show the chosen option. Choose this answer manually.");
      return read(element);
    } catch (error) {
      await close(element);
      throw error;
    }
  }

  globalThis.PortalOracleGrid = {matches, describe, read, identity, choose};
})();
