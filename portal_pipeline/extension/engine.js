/* Form scanning and selected filling. Only a bounded dropdown adapter clicks controls. */
(() => {
  if (globalThis.PortalEngine) return;
  const protectedTerms = /\b(password|passcode|captcha|one.?time|otp|ssn|social security|credit card|bank account|routing number|signature|attest|certify|certification of|consent|agree|accept terms|privacy policy|declaration)\b/i;
  const demographicTerms = /\b(gender|race|ethnicity|veteran|disability|sexual orientation)\b/i;
  const normalize = value => String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const answerKey = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  let controls = new Map();
  let filling = false;
  const recordIds = new WeakMap();
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function historyGroup(node) {
    if (!node.matches("fieldset,section,div")) return null;
    const explicit = node.getAttribute("data-portal-section");
    if (["employment", "education"].includes(explicit)) return explicit;
    const automation = node.getAttribute("data-automation-id") || "";
    return /^workExperience(?:-|$)/i.test(automation) ? "employment" : /^education(?:-|$)/i.test(automation) ? "education" : null;
  }

  function historyContexts() {
    const candidates = [...document.querySelectorAll("[data-portal-section],[data-automation-id]")].filter(node => historyGroup(node));
    return candidates.filter(node => !candidates.some(child => child !== node && node.contains(child) && historyGroup(child) === historyGroup(node)));
  }

  function contextFor(element, contexts = historyContexts()) {
    for (let parent = element.parentElement; parent; parent = parent.parentElement) if (contexts.includes(parent)) return parent;
    return null;
  }

  function contextIdentity(node) {
    return node ? [historyGroup(node), node.id, node.getAttribute("data-automation-id"), node.querySelector("legend")?.textContent || ""].join("|") : "";
  }

  function profileRecords(profile, group) {
    const indices = [...new Set(Object.keys(profile.values).map(key => key.match(new RegExp(`^${group}\\.(\\d+)\\.`))?.[1]).filter(value => value !== undefined))].map(Number).sort((a, b) => a - b);
    return indices.map(index => {
      const value = name => profile.values[`${group}.${index}.${name}`]?.value || "";
      const label = group === "employment" ? [value("company"), value("title"), [value("start_date"), value("end_date")].filter(Boolean).join(" to ")]
        : [value("school"), value("degree"), value("end_date")];
      return {index, label: label.filter(Boolean).join(", ")};
    });
  }

  function datePartFact(profile, key, element, options) {
    const match = key?.match(/^(employment|education)\.(\d+)\.(start|end)_(month|year)$/);
    if (!match) return profile.values[key];
    const baseKey = `${match[1]}.${match[2]}.${match[3]}_date`, base = profile.values[baseKey];
    const date = String(base?.value || "").match(/^(\d{4})-(0[1-9]|1[0-2])$/);
    if (!date) return null;
    let value = match[4] === "year" ? date[1] : element.type === "number" ? String(Number(date[2])) : date[2];
    if (match[4] === "month" && options.length) {
      const number = Number(date[2]), full = months[number - 1].toLowerCase();
      const matches = options.filter(option => !option.disabled && [full, full.slice(0, 3), String(number), date[2]].includes(answerKey(option.label)));
      if (matches.length !== 1) return null;
      value = matches[0].label;
    }
    return {value, source: `${base.source}: ${base.value}, ${match[4]} component`};
  }

  function labelText(label) {
    const copy = label.cloneNode(true);
    copy.querySelectorAll("input,select,textarea,[role=combobox]").forEach(node => node.remove());
    return copy.textContent.trim();
  }

  function labelFor(element) {
    const portalLabel = globalThis.PortalGreenhouse?.label(element);
    if (portalLabel) return portalLabel;
    const explicit = [...(element.labels || [])].map(labelText).join(" ");
    const ids = (element.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
    const ariaText = ids.map(id => document.getElementById(id)?.textContent || "").join(" ").trim();
    return explicit || element.getAttribute("aria-label") || ariaText || (element.closest("label") ? labelText(element.closest("label")) : "")
      || element.getAttribute("placeholder") || element.name || element.getAttribute("data-automation-id") || "Unlabelled field";
  }

  function visible(element) {
    if (element.closest('[aria-hidden="true"],[hidden]')) return false;
    const style = getComputedStyle(element);
    return !element.hidden && style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }

  function controlVisible(element) {
    const upload = globalThis.PortalGreenhouse?.uploadGroup(element);
    return upload ? visible(upload) && !element.closest('[aria-hidden="true"],[hidden]') : visible(element);
  }

  function classify(label, identity, section) {
    const aliases = {
      first_name: ["first name", "legal first name", "given name"],
      last_name: ["last name", "legal last name", "family name", "surname"],
      full_name: ["full name", "legal name"], email: ["email", "email address", "e mail"],
      phone: ["phone", "phone number", "mobile phone", "telephone"],
      linkedin: ["linkedin", "linkedin profile", "linkedin url"], github: ["github", "github url", "github profile"],
      city: ["city", "city of residence"], location: ["current location", "location of residence"],
      authorized_us: ["are you authorized to work in the us", "are you legally authorized to work in the united states", "are you authorized to work in the united states"],
      sponsorship_now: ["do you require sponsorship now", "do you currently require sponsorship", "do you require visa sponsorship now"],
      sponsorship_future: ["will you require sponsorship in the future", "will you require visa sponsorship in the future", "do you require sponsorship in the future"],
      citizenship: ["country of citizenship", "citizenship country", "nationality"],
      visa_type: ["visa type"], relocation: ["are you willing to relocate", "open to relocation"],
      salary: ["salary expectation", "salary expectations", "compensation expectation"],
      available_from: ["available from", "earliest start date", "when are you available to start"],
      job_source: ["how did you hear about this job", "how did you hear about us", "job source"]
    };
    const text = normalize(label);
    const history = section === "employment" ? {
      "employment.company": ["employer", "employer name", "company", "company name"],
      "employment.title": ["job title", "role title", "position title"],
      "employment.start_date": ["start date", "from date"], "employment.end_date": ["end date", "to date"],
      "employment.start_month": ["start month", "from month"], "employment.start_year": ["start year", "from year"],
      "employment.end_month": ["end month", "to month"], "employment.end_year": ["end year", "to year"],
      "employment.description": ["job description", "responsibilities", "role description"],
      "employment.location": ["location", "employment location"]
    } : section === "education" ? {
      "education.school": ["school", "school name", "university", "institution"],
      "education.degree": ["degree", "degree earned"], "education.end_date": ["end date", "graduation date"],
      "education.start_date": ["start date", "from date"], "education.location": ["location", "education location"],
      "education.start_month": ["start month", "from month"], "education.start_year": ["start year", "from year"],
      "education.end_month": ["end month", "graduation month", "to month"], "education.end_year": ["end year", "graduation year", "to year"]
    } : {};
    const scoped = ["employment", "education"].includes(section) ? history : aliases;
    for (const [key, labels] of Object.entries(scoped)) {
      if (labels.includes(text)) return key;
    }
    return null;
  }

  function controlIdentity(element) {
    return [labelFor(element), element.type || element.getAttribute("role"), element.name, element.id,
      element.getAttribute("data-automation-id"), element.closest("fieldset")?.querySelector("legend")?.textContent || ""].join("|");
  }

  function fingerprint(element) {
    const custom = element.getAttribute("role") === "combobox" && element.tagName !== "SELECT";
    const choices = custom ? globalThis.PortalListbox?.describe(element).options || []
      : element.tagName === "SELECT" ? [...element.options].map(option => [option.value, option.textContent.trim(), option.disabled])
      : element.type === "radio" ? [...document.querySelectorAll("input[type=radio]")].filter(item => item.name === element.name && item.form === element.form).map(item => [item.value, labelFor(item), item.disabled]) : [];
    return [controlIdentity(element), JSON.stringify(choices),
      custom ? globalThis.PortalListbox?.identity(element) : ""].join("|");
  }

  function read(control) {
    const {element, members, field} = control;
    if (!element.isConnected) return "[detached]";
    return field.type === "combobox" ? globalThis.PortalListbox?.read(element) ?? element.value ?? ""
      : field.type === "radio" ? members.find(item => item.checked)?.value || ""
      : field.type === "checkbox" ? element.checked : field.type === "file" ? [...element.files].map(file => file.name).join(",") : element.value || "";
  }

  function scan(profile, {register = true, bindings = {}} = {}) {
    if (register && filling) throw new Error("A fill is running. Wait for its results before rescanning.");
    if (register) controls = new Map();
    const fields = [], counts = new Map(), seenRadio = new Set();
    const contexts = historyContexts(), records = new Map(), usage = new Map();
    contexts.filter(visible).forEach((context, ordinal) => {
      const group = historyGroup(context);
      if (!recordIds.has(context)) recordIds.set(context, `${group}:${crypto.randomUUID()}`);
      const id = recordIds.get(context), chosen = bindings[id];
      const valid = chosen === "manual" || (Number.isInteger(chosen) && profileRecords(profile, group).some(record => record.index === chosen));
      const index = valid ? chosen : null;
      const record = {id, group, index, label: context.querySelector("legend")?.textContent.trim() || `${group === "employment" ? "Employment" : "Education"} row ${ordinal + 1}`, error: ""};
      records.set(context, record);
      if (Number.isInteger(index)) usage.set(`${group}.${index}`, (usage.get(`${group}.${index}`) || 0) + 1);
    });
    records.forEach(record => {
      if (Number.isInteger(record.index) && usage.get(`${record.group}.${record.index}`) > 1) {
        record.index = null; record.error = "The same profile record is assigned to multiple visible rows. Choose different records or manual answers.";
      }
    });
    for (const element of document.querySelectorAll("input, select, textarea, [role='combobox']")) {
      if (element.closest("#portal-panel-host") || !controlVisible(element)) continue;
      if (globalThis.PortalGreenhouse?.active() && !PortalGreenhouse.formFor(element)) continue;
      const custom = element.getAttribute("role") === "combobox" && element.tagName !== "SELECT";
      const type = custom ? "combobox" : element.type || element.getAttribute("role") || element.tagName.toLowerCase();
      if (["hidden", "submit", "button", "reset", "image"].includes(type)) continue;
      if (type === "radio" && element.name) {
        if (seenRadio.has(element.name)) continue;
        seenRadio.add(element.name);
      }
      let label = labelFor(element);
      let members = [element];
      if (type === "radio") {
        members = [...document.querySelectorAll("input[type=radio]")].filter(item => item.name === element.name && visible(item));
        label = element.closest("fieldset")?.querySelector("legend")?.textContent.trim() || element.getAttribute("aria-label") || element.name;
      }
      const identity = `${element.name || ""} ${element.id || ""} ${element.getAttribute("data-automation-id") || ""}`;
      const context = contextFor(element, contexts), record = records.get(context) || null;
      const section = record?.group || "contact";
      const protectionText = `${label} ${identity} ${element.closest("fieldset")?.querySelector("legend")?.textContent || ""}`;
      const blocked = element.type === "password" || protectedTerms.test(protectionText) || demographicTerms.test(protectionText) || !!globalThis.PortalGreenhouse?.protectedField(element);
      let key = blocked ? null : classify(label, identity, section);
      if (key?.includes(".")) {
        const [group, name] = key.split(".");
        key = Number.isInteger(record?.index) ? `${group}.${record.index}.${name}` : null;
      }
      const ordinalKey = `${record ? record.id + "|" : ""}${normalize(label)}|${type}`;
      const ordinal = counts.get(ordinalKey) || 0;
      counts.set(ordinalKey, ordinal + 1);
      const id = `${ordinalKey}|${ordinal}`;
      const customInfo = custom ? globalThis.PortalListbox?.describe(element) || {supported: false, reason: "No custom dropdown adapter is installed.", options: []} : null;
      const current = blocked ? "" : custom ? globalThis.PortalListbox?.read(element) ?? element.value ?? "" : type === "radio" ? members.find(item => item.checked)?.value || ""
        : type === "checkbox" ? element.checked : type === "file" ? [...element.files].map(file => file.name).join(", ") : element.value || "";
      const options = custom ? customInfo.options : element.tagName === "SELECT" ? [...element.options].map(option => ({value: option.value, label: option.textContent.trim(), disabled: option.disabled}))
        : type === "radio" ? members.map(item => ({value: item.value, label: labelFor(item), disabled: item.disabled})) : [];
      const fact = key ? datePartFact(profile, key, element, options) : null;
      const field = {id, label, key, section: key?.split(".")[0] || section, type, current, options, record,
                     required: element.required || element.getAttribute("aria-required") === "true" || globalThis.PortalGreenhouse?.uploadGroup(element)?.getAttribute("aria-required") === "true",
                     blocked, disabled: !!(element.disabled || element.readOnly || element.getAttribute("aria-disabled") === "true" || element.getAttribute("aria-readonly") === "true"),
                     adapter: customInfo?.supported ? "aria-listbox" : null, manual_reason: customInfo?.reason || "",
                     structure: {tag: element.tagName.toLowerCase(), name: element.name || "", automation_id: element.getAttribute("data-automation-id") || "",
                       dom_id: element.id, role: element.getAttribute("role") || "", controls: element.getAttribute("aria-controls") || "", popup: element.getAttribute("aria-haspopup") || ""},
                     proposal: fact?.value ?? "", source: record?.error || (record?.index === null ? "Choose a profile record for this row first." : fact?.source || "Manual answer required"),
                     status: blocked ? "manual_only" : !fact && type !== "file" ? "pending" : "prepared"};
      fields.push(field);
      if (register) controls.set(id, {element, members, field, context, portalForm: globalThis.PortalGreenhouse?.formFor(element), contextIdentity: contextIdentity(context), fingerprint: fingerprint(element), identity: controlIdentity(element)});
    }
    return fields;
  }

  function inspect() {
    const fields = scan({values: {}}, {register: false});
    return {schema_version: 1, host: location.hostname, inspected_at: new Date().toISOString(),
      portal: globalThis.PortalGreenhouse?.active() ? "greenhouse" : "generic",
      portal_manual_reason: globalThis.PortalGreenhouse?.active() && !PortalGreenhouse.form() ? "No unique supported Greenhouse application form found. Inspect the employer page manually." : "",
      protected_fields_omitted: fields.filter(field => field.blocked).length,
      fields: fields.filter(field => !field.blocked).map(field => ({label: field.label, type: field.type,
        required: field.required, disabled: field.disabled, section: field.section, adapter: field.adapter,
        record: field.record ? {id: field.record.id, group: field.record.group, label: field.record.label} : null,
        manual_reason: field.manual_reason, option_count: field.options.length, structure: field.structure}))};
  }

  function optionMatch(options, answer) {
    const wanted = answerKey(answer);
    if (!wanted) return null;
    const exact = options.filter(option => !option.disabled && (answerKey(option.label) === wanted || answerKey(option.value) === wanted));
    if (exact.length === 1) return exact[0];
    // Never use substring matching: "not authorized" must not match "authorized".
    return null;
  }

  function setNative(element, value) {
    const prototype = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype
      : element.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (!setter) throw new Error("Unsupported control. Fill this field manually.");
    setter.call(element, value);
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    element.dispatchEvent(new Event("blur", {bubbles: true}));
  }

  async function fillSelected(selections, {overwrite = false, attachment = null} = {}) {
    const results = [];
    const selectedIds = new Set(selections.map(selection => selection.id));
    const baseline = new Map([...controls].filter(([, control]) => !control.field.blocked).map(([id, control]) => [id, read(control)]));
    let aborted = false;
    const checkCollateral = () => {
      const collateral = [...baseline].filter(([id, value]) => !selectedIds.has(id) && read(controls.get(id)) !== value);
      if (collateral.length) {
        aborted = true;
        throw new Error("An unselected field changed: " + collateral.map(([id]) => controls.get(id).field.label).join(", ") + ". Review the form manually.");
      }
    };
    const checkHistory = control => {
      if (control.context && (contextFor(control.element) !== control.context || contextIdentity(control.context) !== control.contextIdentity)) throw new Error("The history row identity changed. Rescan and choose its profile record again.");
    };
    const checkPortal = control => {
      if (globalThis.PortalGreenhouse?.active() && (!control.portalForm || PortalGreenhouse.formFor(control.element) !== control.portalForm)) throw new Error("The Greenhouse application form changed. Rescan before filling.");
      if (globalThis.PortalGreenhouse?.protectedField(control.element)) throw new Error("This field is manual only.");
    };
    for (const selection of selections) {
      const control = controls.get(selection.id);
      let outcome;
      try {
        if (!control) throw new Error("Field changed. Scan the page again.");
        if (aborted) throw new Error("Filling stopped after an unexpected form change. Rescan and review.");
        const {element, members, field} = control;
        if (!element.isConnected || !controlVisible(element)) throw new Error("Field is no longer visible. Scan again.");
        checkPortal(control);
        if (fingerprint(element) !== control.fingerprint) throw new Error("Question or control identity changed. Rescan before filling.");
        if (field.record?.index === null) throw new Error(field.record.error || "Choose a profile record or manual answers for this row before filling.");
        checkHistory(control);
        if (field.blocked || protectedTerms.test(`${labelFor(element)} ${element.name || ""}`) || globalThis.PortalGreenhouse?.protectedField(element)) throw new Error("This field is manual only.");
        if (element.disabled || element.readOnly) throw new Error("This field cannot be edited.");
        const current = field.type === "combobox" ? read(control) : field.type === "radio" ? members.find(item => item.checked)?.value || ""
          : field.type === "checkbox" ? element.checked : field.type === "file" ? element.files.length : element.value;
        if (!(selection.overwrite === true || overwrite) && current !== "" && current !== false && current !== 0) {
          results.push({id: field.id, status: "preserved", message: "Existing portal value preserved."});
          continue;
        }
        let expected = selection.value;
        if (field.type === "file") {
          if (!attachment) throw new Error("Choose a reviewed resume session first.");
          if (element.multiple) throw new Error("Multiple-file upload requires manual selection in this prototype.");
          if (!["resume", "cv", "resume cv", "upload resume", "upload cv", "attach resume", "attach cv"].includes(normalize(field.label))) throw new Error("This upload is not an explicitly identified resume field. Choose the file manually.");
          const bytes = Uint8Array.from(atob(attachment.base64), char => char.charCodeAt(0));
          const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2, "0")).join("");
          if (hash !== attachment.sha256) throw new Error("Resume checksum does not match.");
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], attachment.name, {type: attachment.mime}));
          element.files = transfer.files;
          element.dispatchEvent(new Event("change", {bubbles: true}));
          expected = attachment.name;
        } else if (field.type === "radio" || element.tagName === "SELECT") {
          const option = optionMatch(field.options, expected);
          if (!option) throw new Error("No unique exact option matches the answer. Choose an available option.");
          expected = option.value;
          if (field.type === "radio") {
            const target = members.find(item => item.value === option.value);
            if (!target?.isConnected || !visible(target) || target.disabled) throw new Error("The selected radio option is unavailable. Rescan before filling.");
            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked").set.call(target, true);
            target.dispatchEvent(new Event("input", {bubbles: true}));
            target.dispatchEvent(new Event("change", {bubbles: true}));
          } else setNative(element, option.value);
        } else if (field.type === "combobox") {
          if (!field.adapter || !globalThis.PortalListbox) throw new Error(field.manual_reason || "This custom dropdown requires manual review.");
          expected = await PortalListbox.choose(element, expected, () => {
            checkCollateral();
            checkHistory(control);
            if (controlIdentity(element) !== control.identity) throw new Error("The dropdown question changed while opening. Rescan before filling.");
          });
        } else if (field.type === "checkbox") {
          throw new Error("Checkboxes require manual review in this prototype.");
        } else {
          expected = String(expected ?? "");
          if (!expected.trim()) throw new Error("Provide an answer before selecting this field.");
          if (element.maxLength > 0 && expected.length > element.maxLength) throw new Error("Answer exceeds the portal's length limit.");
          setNative(element, expected);
        }
        await new Promise(resolve => setTimeout(resolve, 500));
        checkCollateral();
        checkHistory(control);
        checkPortal(control);
        const actual = field.type === "combobox" ? read(control) : field.type === "file" ? element.files[0]?.name : field.type === "radio" ? members.find(item => item.checked)?.value : element.value;
        if (actual !== expected) throw new Error("Portal did not retain the value. Review this field manually.");
        if (!element.isConnected) throw new Error("Portal replaced the field after filling. Scan again to verify.");
        if (element.validity && !element.validity.valid) throw new Error("Portal validation rejected the value.");
        outcome = {id: field.id, status: "filled", message: field.type === "file" ? "File input verified. Check the portal's upload completion indicator." : "Value verified."};
      } catch (error) {
        outcome = {id: selection.id, status: "failed", message: error.message};
        try { checkCollateral(); } catch (change) {outcome.message = change.message;}
      }
      results.push(outcome);
    }
    return results;
  }

  async function fill(selections, options = {}) {
    if (filling) throw new Error("A fill is already running on this page. Wait for its results.");
    filling = true;
    try { return await fillSelected(selections, options); }
    finally { filling = false; }
  }

  globalThis.PortalEngine = {scan, fill, optionMatch, inspect, profileRecords};
})();
