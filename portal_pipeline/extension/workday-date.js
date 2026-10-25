(() => {
  if (globalThis.PortalWorkdayDate) return;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const DATE_ID = /--(startDate|endDate)-dateSection(Month|Year)-input$/;
  const EDUCATION_ID = /--(firstYearAttended|lastYearAttended)-dateSectionYear-input$/;

  const matches = element => element?.tagName === "INPUT" && element.getAttribute("role") === "spinbutton"
    && (DATE_ID.test(element.id) || EDUCATION_ID.test(element.id));

  function part(element) {
    if (!matches(element)) throw new Error("Not a Workday date field.");
    return element.id.endsWith("-dateSectionMonth-input") ? "month" : "year";
  }

  function read(element) {
    return String(element.value);
  }

  function identity(element) {
    return [element.id, element.getAttribute("name"), element.getAttribute("role"), element.tagName].join("|");
  }

  async function write(element, value, guard = () => {}) {
    guard();
    const datePart = part(element);
    let wanted = String(value ?? "");
    if (datePart === "month" && wanted.length === 1 && /^[1-9]$/.test(wanted)) wanted = "0" + wanted;
    if (datePart === "month" && (wanted.length !== 2 || !/^(0[1-9]|1[0-2])$/.test(wanted))) {
      throw new Error("Provide a month from 01 to 12.");
    }
    if (datePart === "year" && (wanted.length !== 4 || !/^\d{4}$/.test(wanted))) {
      throw new Error("Provide a year with exactly four digits.");
    }
    guard();
    const step = action => {
      guard();
      const result = action();
      guard();
      return result;
    };
    step(() => element.focus());
    // React observes the native setter rather than an overridden instance setter.
    step(() => Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(element, wanted));
    step(() => element.dispatchEvent(new Event("input", {bubbles: true})));
    step(() => element.dispatchEvent(new Event("change", {bubbles: true})));
    step(() => element.dispatchEvent(new Event("blur", {bubbles: true})));
    guard();
    await sleep(150);
    guard();
    const actual = step(() => read(element));
    if (datePart === "month" ? Number(actual) !== Number(wanted) : actual !== wanted) {
      throw new Error("The date field did not keep the value. Enter it manually.");
    }
    return wanted;
  }

  globalThis.PortalWorkdayDate = {matches, part, read, identity, write};
})();
