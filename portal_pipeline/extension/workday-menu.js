/* Workday button menus: a button with aria-haspopup="listbox" whose popup is named by aria-controls once opened. */
(() => {
  if (globalThis.PortalWorkdayMenu) return;
  const normalize = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = node => node?.isConnected && !node.closest('[aria-hidden="true"],[hidden]')
    && getComputedStyle(node).visibility !== "hidden" && node.getClientRects().length > 0;
  const PLACEHOLDER = /^select one\b/i;

  const matches = element => element?.tagName === "BUTTON" && element.getAttribute("aria-haspopup") === "listbox"
    && element.getAttribute("data-automation-id") !== "utilityMenuButton";

  function popupFor(element) {
    const ids = (element.getAttribute("aria-controls") || "").trim().split(/\s+/).filter(Boolean);
    if (ids.length !== 1) return null;
    const found = document.querySelectorAll(`#${CSS.escape(ids[0])}`);
    return found.length === 1 && found[0].getAttribute("role") === "listbox" ? found[0] : null;
  }

  const optionNodes = popup => popup ? [...popup.querySelectorAll('[role="option"]')].filter(node => node.closest('[role="listbox"]') === popup) : [];
  const optionLabel = node => (node.getAttribute("aria-label") || node.textContent).replace(/\s+/g, " ").trim();

  // The question text: the fieldset legend, else the smallest ancestor holding this menu and no other control (its hidden mirror input excepted).
  function question(element) {
    const legend = element.closest("fieldset")?.querySelector("legend");
    const legendText = legend ? legend.textContent.replace(/\s+/g, " ").trim() : "";
    if (legendText) return legendText.slice(0, 300);
    const mirror = item => item.tagName === "INPUT" && item.type === "text" && item.getAttribute("value") === element.getAttribute("value");
    for (let parent = element.parentElement, depth = 0; parent && depth < 6; parent = parent.parentElement, depth += 1) {
      const others = [...parent.querySelectorAll('input:not([type="hidden"]),select,textarea,[role="listbox"],button')].some(item => item !== element && !mirror(item));
      if (others) return "";
      const clone = parent.cloneNode(true);
      clone.querySelectorAll("button,[role=button],[aria-haspopup],input,script,style").forEach(item => item.remove());
      const text = clone.textContent.replace(/\s+/g, " ").trim();
      if (text) return text.slice(0, 300);
    }
    return "";
  }

  function read(element) {
    const text = element.textContent.replace(/\s+/g, " ").trim();
    return PLACEHOLDER.test(text) ? "" : text;
  }

  function identity(element) {
    return [element.id, element.getAttribute("name"), element.getAttribute("aria-haspopup"), element.tagName].join("|");
  }

  function describe(element) {
    if (!matches(element)) return {supported: false, reason: "Not a Workday button menu.", options: [], dropdown_state: null};
    if (element.disabled || element.getAttribute("aria-disabled") === "true") return {supported: false, reason: "This menu cannot be edited.", options: [], dropdown_state: null};
    const popup = element.getAttribute("aria-expanded") === "true" ? popupFor(element) : null;
    const options = optionNodes(popup).map(node => ({value: optionLabel(node), label: optionLabel(node), disabled: node.getAttribute("aria-disabled") === "true"}));
    return {supported: true, reason: "", options, dropdown_state: {popup_present: !!popup, expanded: element.getAttribute("aria-expanded") === "true", options_observed: options.length > 0}};
  }

  async function close(element) {
    if (element.getAttribute("aria-expanded") === "true") element.click();
    await sleep(100);
  }

  async function choose(element, answer, guard = () => {}) {
    const wanted = normalize(answer);
    if (!wanted) throw new Error("Provide an answer before selecting this menu.");
    const startIdentity = identity(element), startValue = read(element);
    const assertSame = () => {
      guard();
      if (!visible(element) || identity(element) !== startIdentity) throw new Error("The menu identity changed while opening. Rescan before filling.");
      if (read(element) !== startValue) throw new Error("The menu value changed while opening. Rescan before filling.");
    };
    assertSame();
    if (element.getAttribute("aria-expanded") !== "true") element.click();
    let popup = null;
    const deadline = performance.now() + 1500;
    do {
      await sleep(50);
      assertSame();
      popup = element.getAttribute("aria-expanded") === "true" ? popupFor(element) : null;
    } while ((!popup || !optionNodes(popup).length) && performance.now() < deadline);
    if (!popup || !optionNodes(popup).length) { await close(element); throw new Error("The menu popup did not open. Choose this answer manually."); }
    const found = optionNodes(popup).filter(node => normalize(optionLabel(node)) === wanted && node.getAttribute("aria-disabled") !== "true");
    if (found.length !== 1) { await close(element); throw new Error("No unique exact menu option matches the answer. Choose this answer manually."); }
    found[0].scrollIntoView({block: "nearest"});
    await sleep(100);
    assertSame();
    if (popupFor(element) !== popup || !found[0].isConnected) { await close(element); throw new Error("The menu option was replaced. Rescan before filling."); }
    found[0].click();
    await sleep(300);
    if (normalize(read(element)) !== wanted) { await close(element); throw new Error("The menu did not show the chosen option. Choose this answer manually."); }
    return read(element);
  }

  globalThis.PortalWorkdayMenu = {matches, describe, read, identity, choose, question};
})();
