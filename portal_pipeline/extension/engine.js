/* Form scanning and selected filling. Only a bounded dropdown adapter clicks controls. */
(() => {
  if (globalThis.PortalEngine) return;
  const protectedTerms = /\b(password|passcode|captcha|one.?time|otp|ssn|social security|credit card|bank account|routing number|signature|attest|certify|certification of|consent|agree|accept terms|privacy policy|declaration)\b/i;
  const demographicTerms = /\b(gender|race|ethnicity|veteran|disability|sexual orientation)\b/i;
  const normalize = value => String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const answerKey = value => String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  let controls = new Map();
  let registeredSurface = [];
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

  function visibleControls() {
    return [...document.querySelectorAll("input,select,textarea,[role=combobox]")].filter(element => {
      if (element.closest("#portal-panel-host") || !controlVisible(element)) return false;
      if (globalThis.PortalGreenhouse?.active() && !PortalGreenhouse.formFor(element)) return false;
      const type = element.getAttribute("role") === "combobox" && element.tagName !== "SELECT" ? "combobox" : element.type;
      return !["hidden", "submit", "button", "reset", "image"].includes(type);
    });
  }

  // Classification and option matching live in classifier.js, loaded before this file.
  const classify = (label, identity, section) => globalThis.PortalClassifier.classify(label, identity, section);

  function controlIdentity(element) {
    return [labelFor(element), element.type || element.getAttribute("role"), element.name, element.id,
      element.getAttribute("data-automation-id"), element.closest("fieldset")?.querySelector("legend")?.textContent || ""].join("|");
  }

  // Bot traps that real forms hide from people; never fill or export them.
  // Survey sections whose option labels (for example "White", "Asian") carry no demographic word of their own.
  const demographicContainers = '[id^="countrySurvey_"],[data-qa*="demographic"],[data-qa*="survey"],[id*="demographic" i],[class*="demographic" i]';
  const honeypotTerms = /(honey.?pot|bee.?catcher|robots? only|do not enter if you are human|do not enter if you.?re human|leave (this )?(field )?(blank|empty))/i;

  function protectedControl(element) {
    const text = `${labelFor(element)} ${element.name || ""} ${element.id || ""} ${element.getAttribute("data-automation-id") || ""} ${element.closest("fieldset")?.querySelector("legend")?.textContent || ""}`;
    return element.type === "password" || honeypotTerms.test(text) || !!element.closest(demographicContainers) || protectedTerms.test(text) || demographicTerms.test(text) || !!globalThis.PortalGreenhouse?.protectedField(element);
  }

  function radioMembers(element) {
    return element.name ? [...document.querySelectorAll("input[type=radio]")].filter(item => item.name === element.name && item.form === element.form) : [element];
  }

  function unavailable(element) {
    return element.matches(":disabled") || !!element.readOnly || !!element.closest('[aria-disabled="true"],[aria-readonly="true"]');
  }

  function optionDisabled(option) {
    return unavailable(option) || !!option.closest("optgroup:disabled");
  }

  const dropdown = element => globalThis.PortalGreenhouseSelect?.matches(element) ? PortalGreenhouseSelect : globalThis.PortalListbox;

  function fingerprint(element) {
    const custom = element.getAttribute("role") === "combobox" && element.tagName !== "SELECT";
    const choices = custom ? dropdown(element)?.describe(element).options || []
      : element.tagName === "SELECT" ? [...element.options].map(option => [option.value, option.textContent.trim(), optionDisabled(option)])
      : element.type === "radio" ? radioMembers(element).map(item => [item.value, controlIdentity(item), unavailable(item)]) : [];
    return [controlIdentity(element), JSON.stringify(choices),
      custom ? dropdown(element)?.identity(element) : ""].join("|");
  }

  function read(control) {
    const {element, members, field} = control;
    if (!element.isConnected) return "[detached]";
    return field.type === "combobox" ? dropdown(element)?.read(element) ?? element.value ?? ""
      : field.type === "radio" ? members.find(item => item.checked)?.value || ""
      : field.type === "checkbox" ? element.checked : field.type === "file" ? [...element.files].map(file => file.name).join(",") : element.value || "";
  }

  const route = () => globalThis.PortalAdapters?.forLocation(location.href) || null;

  function proposeCore(field, profile, {element, options = field.options || []} = {}) {
    const fact = field.key ? datePartFact(profile, field.key, element, options) : null;
    const derived = /^(employment|education)\.\d+\.(start|end)_(month|year)$/.test(field.key || "");
    return {key: field.key, value: fact?.value ?? "", source: fact?.source || "Manual answer required",
      status: field.blocked ? "manual_only" : !fact && field.type !== "file" ? "pending" : "prepared", basis: derived ? "derived" : "exact_alias"};
  }

  function scanCore(profile, {register = true, bindings = {}} = {}) {
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
    const surface = visibleControls();
    if (register) registeredSurface = surface;
    for (const element of surface) {
      const custom = element.getAttribute("role") === "combobox" && element.tagName !== "SELECT";
      const type = custom ? "combobox" : element.type || element.getAttribute("role") || element.tagName.toLowerCase();
      if (["hidden", "submit", "button", "reset", "image"].includes(type)) continue;
      if (type === "radio") {
        if (seenRadio.has(element)) continue;
        radioMembers(element).forEach(item => seenRadio.add(item));
      }
      let label = labelFor(element);
      let members = [element];
      if (type === "radio") {
        members = radioMembers(element);
        label = element.closest("fieldset")?.querySelector("legend")?.textContent.trim() || element.getAttribute("aria-label") || element.name;
      }
      const identity = `${element.name || ""} ${element.id || ""} ${element.getAttribute("data-automation-id") || ""}`;
      const context = contextFor(element, contexts), record = records.get(context) || null;
      const section = record?.group || "contact";
      let blocked = members.some(protectedControl);
      let key = blocked ? null : classify(label, identity, section);
      const required = element.required || element.getAttribute("aria-required") === "true";
      if (!blocked && type === "checkbox" && PortalClassifier.isAttestationCheckbox({type, label, key, required, checked: element.checked})) { blocked = true; key = null; }
      if (key?.includes(".")) {
        const [group, name] = key.split(".");
        key = Number.isInteger(record?.index) ? `${group}.${record.index}.${name}` : null;
      }
      const ordinalKey = `${record ? record.id + "|" : ""}${normalize(label)}|${type}`;
      const ordinal = counts.get(ordinalKey) || 0;
      counts.set(ordinalKey, ordinal + 1);
      const id = `${ordinalKey}|${ordinal}`;
      const customInfo = custom ? dropdown(element)?.describe(element) || {supported: false, reason: "No custom dropdown adapter is installed.", options: []} : null;
      const current = blocked ? "" : custom ? dropdown(element)?.read(element) ?? element.value ?? "" : type === "radio" ? members.find(item => item.checked)?.value || ""
        : type === "checkbox" ? element.checked : type === "file" ? [...element.files].map(file => file.name).join(", ") : element.value || "";
      const options = custom ? customInfo.options : element.tagName === "SELECT" ? [...element.options].map(option => ({value: option.value, label: option.textContent.trim(), disabled: optionDisabled(option)}))
        : type === "radio" ? members.map(item => ({value: item.value, label: labelFor(item), disabled: unavailable(item) || !visible(item)})) : [];
      const proposal = proposeCore({key, blocked, type, options}, profile, {element, options});
      const field = {id, label, key, section: key?.split(".")[0] || section, type, current, options, record,
                     required: element.required || element.getAttribute("aria-required") === "true" || globalThis.PortalGreenhouse?.uploadGroup(element)?.getAttribute("aria-required") === "true",
                     blocked, disabled: unavailable(element),
                     adapter: customInfo?.supported ? (dropdown(element) === globalThis.PortalGreenhouseSelect ? "greenhouse-select" : "aria-listbox") : null, manual_reason: customInfo?.reason || "",
                     dropdown_state: customInfo?.dropdown_state || null,
                     structure: {tag: element.tagName.toLowerCase(), name: element.name || "", automation_id: element.getAttribute("data-automation-id") || "",
                       dom_id: element.id, role: element.getAttribute("role") || "", controls: element.getAttribute("aria-controls") || "", popup: element.getAttribute("aria-haspopup") || "",
                       maxlength: element.maxLength > 0 ? element.maxLength : null},
                     proposal: proposal.value, source: record?.error || (record?.index === null ? "Choose a profile record for this row first." : proposal.source),
                     status: proposal.status};
      fields.push(field);
      if (register) controls.set(id, {element, members, field, context, nativeForm: element.form, portalForm: globalThis.PortalGreenhouse?.formFor(element), contextIdentity: contextIdentity(context), fingerprint: fingerprint(element), identity: controlIdentity(element)});
    }
    return fields;
  }

  function inspect() {
    const fields = (route() ? route().scan.bind(route()) : scanCore)({values: {}}, {register: false});
    const outsidePanel = node => !node.closest("#portal-panel-host") && visible(node);
    const frames = [...document.querySelectorAll("iframe")].filter(outsidePanel).length;
    const shadowHosts = [...document.querySelectorAll("*")].filter(node => node.shadowRoot && outsidePanel(node)).length;
    const spinbuttons = [...document.querySelectorAll('[role="spinbutton"]')].filter(node => !node.matches("input,select,textarea") && outsidePanel(node)).length;
    const reasonCodes = [frames && "iframe_uninspected", shadowHosts && "open_shadow_uninspected", spinbuttons && "spinbutton_unsupported"].filter(Boolean);
    return {schema_version: 1, host: location.hostname, inspected_at: new Date().toISOString(),
      portal: globalThis.PortalGreenhouse?.active() ? "greenhouse" : "generic",
      portal_manual_reason: globalThis.PortalGreenhouse?.active() && !PortalGreenhouse.form() ? "No unique supported Greenhouse application form found. Inspect the employer page manually." : "",
      protected_fields_omitted: fields.filter(field => field.blocked).length,
      coverage: {scope: "visible_light_dom_current_page", visible_iframes: frames, visible_open_shadow_hosts: shadowHosts,
        unsupported_spinbuttons: spinbuttons, reason_codes: reasonCodes},
      fields: fields.filter(field => !field.blocked).map(field => ({label: field.label, type: field.type,
        required: field.required, disabled: field.disabled, section: field.section, adapter: field.adapter,
        record: field.record ? {id: field.record.id, group: field.record.group, label: field.record.label} : null,
        manual_reason: field.manual_reason, option_count: field.options.length, dropdown_state: field.dropdown_state, structure: field.structure}))};
  }

  const optionMatch = (options, answer) => globalThis.PortalClassifier.matchOption(options, answer);

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

  // Error text the portal shows for this field, searched only inside its own field container.
  const errorScope = 'fieldset,[role=group],[role=radiogroup],.field,[class*="form-group"],[class*="form-field"]';
  function validationText(control) {
    const {element, members} = control, found = [];
    if (members.some(item => item.getAttribute("aria-invalid") === "true")) found.push("Field marked invalid by the portal.");
    let base = element.parentElement;
    if (base?.tagName === "LABEL") base = base.parentElement;
    const container = base?.closest(errorScope) || base;
    const grouped = container?.matches("fieldset,[role=group],[role=radiogroup]");
    if (container && !container.matches("body,form,html") && (grouped || container.querySelectorAll("input,select,textarea,[role=combobox]").length <= 1)) {
      container.querySelectorAll('[role=alert],[id$="-error"]').forEach(node => {
        const text = node.textContent.trim();
        if (text && visible(node)) found.push(text);
      });
    }
    return found.join(" ");
  }

  function verifyCore(control, expected) {
    const {element, members, field} = control;
    const actual = field.type === "combobox" ? read(control) : field.type === "file" ? element.files[0]?.name : field.type === "radio" ? members.find(item => item.checked)?.value : element.value;
    const flagged = element.isConnected ? validationText(control) : "";
    if (actual !== expected) return {ok: false, actual, reason: "reverted after blur", failure_kind: "reverted", validation_error: flagged,
      message: "Portal did not retain the value (reverted after blur). Review this field manually."};
    if (!element.isConnected) return {ok: false, actual, reason: "Portal replaced the field after filling. Scan again to verify.", failure_kind: "error", validation_error: ""};
    if (element.validity && !element.validity.valid) return {ok: false, actual, reason: "Portal validation rejected the value.", failure_kind: "validation_error", validation_error: element.validationMessage || "Portal validation rejected the value."};
    if (flagged) return {ok: false, actual, reason: "Portal flagged a validation error: " + flagged, failure_kind: "validation_error", validation_error: flagged};
    return {ok: true, actual, reason: "", failure_kind: "", validation_error: ""};
  }

  // One selected field, written only through the guard's live-structure checks; selection is the proposal.
  async function fillField(control, selection, guard) {
    const {checkCollateral, checkCurrent, attachment, overwrite} = guard;
    try {
      if (!control) throw new Error("Field changed. Scan the page again.");
      if (guard.state.aborted) throw new Error("Filling stopped after an unexpected form change. Rescan and review.");
      const {element, members, field} = control;
      checkCollateral();
      checkCurrent(control);
      if (fingerprint(element) !== control.fingerprint) throw new Error("Question or control identity changed. Rescan before filling.");
      if (field.record?.index === null) throw new Error(field.record.error || "Choose a profile record or manual answers for this row before filling.");
      const current = field.type === "combobox" ? read(control) : field.type === "radio" ? members.find(item => item.checked)?.value || ""
        : field.type === "checkbox" ? element.checked : field.type === "file" ? element.files.length : element.value;
      if (!(selection.overwrite === true || overwrite) && current !== "" && current !== false && current !== 0) {
        return {id: field.id, status: "preserved", message: "Existing portal value preserved."};
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
        checkCollateral();
        checkCurrent(control);
        element.files = transfer.files;
        element.dispatchEvent(new Event("change", {bubbles: true}));
        expected = attachment.name;
      } else if (field.type === "radio" || element.tagName === "SELECT") {
        const option = optionMatch(field.options, expected);
        if (!option) throw new Error("No unique exact option matches the answer. Choose an available option.");
        expected = option.value;
        if (field.type === "radio") {
          if (members.filter(item => item.value === option.value).length !== 1) throw new Error("The radio option value is ambiguous. Choose this answer manually.");
          const target = members.find(item => item.value === option.value);
          if (element.form !== control.nativeForm || !radioMembers(element).includes(target)) throw new Error("The radio group changed. Rescan before filling.");
          if (members.some(protectedControl)) throw new Error("This radio group is manual only.");
          if (!target?.isConnected || !visible(target) || unavailable(target)) throw new Error("The selected radio option is unavailable. Rescan before filling.");
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked").set.call(target, true);
          target.dispatchEvent(new Event("input", {bubbles: true}));
          target.dispatchEvent(new Event("change", {bubbles: true}));
        } else {
          if ([...element.options].filter(item => item.value === option.value).length !== 1) throw new Error("The native option value is ambiguous. Choose this answer manually.");
          const target = [...element.options].find(item => item.value === option.value && item.textContent.trim() === option.label);
          if (!target || optionDisabled(target)) throw new Error("The selected option is unavailable. Rescan before filling.");
          setNative(element, option.value);
        }
      } else if (field.type === "combobox") {
        if (!field.adapter || !dropdown(element)) throw new Error(field.manual_reason || "This custom dropdown requires manual review.");
        expected = await dropdown(element).choose(element, expected, () => {
          checkCollateral();
          checkCurrent(control);
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
      checkCurrent(control);
      const check = guard.verify(control, expected);
      if (!check.ok) {
        const failed = {id: field.id, status: "failed", message: check.message || check.reason, reason: check.reason,
          failure_kind: check.failure_kind || "error", validation_error: check.validation_error || ""};
        try { checkCollateral(); } catch (change) {failed.message = change.message;}
        return failed;
      }
      return {id: field.id, status: "filled", message: field.type === "file" ? "File input verified. Check the portal's upload completion indicator." : "Value verified.",
        reason: "", failure_kind: "", validation_error: ""};
    } catch (error) {
      const outcome = {id: selection.id, status: "failed", message: error.message, reason: error.message, failure_kind: "error", validation_error: ""};
      try { checkCollateral(); } catch (change) {outcome.message = change.message; outcome.reason = change.message;}
      return outcome;
    }
  }

  async function fillSelected(selections, {overwrite = false, attachment = null} = {}) {
    const adapter = route();
    if (adapter && adapter.fillStrategy !== "native_setter") throw new Error(`Fill strategy ${adapter.fillStrategy} is not enabled.`);
    const gate = adapter?.humanGate(document);
    if (gate) {
      const reason = `A ${gate.kind} step needs you. Nothing was written. Complete it yourself, then rescan.`;
      return selections.map(selection => ({id: selection.id, ok: false, status: "blocked_by_human_gate", actual: null, reason, message: reason}));
    }
    const results = [];
    const selectedIds = new Set(selections.map(selection => selection.id));
    const baseline = new Map([...controls].map(([id, control]) => [id, read(control)]));
    const state = {aborted: false};
    const liveProtected = control => control.field.blocked || control.members.some(protectedControl);
    const checkCollateral = () => {
      const surface = visibleControls();
      const changedMembership = [...controls.values()].some(control => control.field.type === "radio" &&
        (radioMembers(control.element).length !== control.members.length || radioMembers(control.element).some(item => !control.members.includes(item))));
      if (surface.length !== registeredSurface.length || surface.some(element => !registeredSurface.includes(element)) || changedMembership) {
        state.aborted = true;
        throw new Error("The visible form structure changed. Stop and rescan before filling more fields.");
      }
      const collateral = [...baseline].filter(([id, value]) => (!selectedIds.has(id) || liveProtected(controls.get(id))) && read(controls.get(id)) !== value);
      if (collateral.length) {
        state.aborted = true;
        const labels = collateral.map(([id]) => liveProtected(controls.get(id)) ? "a protected field" : controls.get(id).field.label);
        throw new Error("An unselected field changed: " + labels.join(", ") + ". Review the form manually.");
      }
    };
    const checkHistory = control => {
      if (control.context && (contextFor(control.element) !== control.context || contextIdentity(control.context) !== control.contextIdentity)) throw new Error("The history row identity changed. Rescan and choose its profile record again.");
    };
    const checkPortal = control => {
      if (globalThis.PortalGreenhouse?.active() && (!control.portalForm || PortalGreenhouse.formFor(control.element) !== control.portalForm)) throw new Error("The Greenhouse application form changed. Rescan before filling.");
      if (globalThis.PortalGreenhouse?.protectedField(control.element)) throw new Error("This field is manual only.");
    };
    const checkCurrent = control => {
      const {element, members, field} = control;
      if (!element.isConnected || !controlVisible(element)) throw new Error("Field is no longer visible. Scan again.");
      if (element.form !== control.nativeForm) throw new Error("The field's form changed. Rescan before filling.");
      checkHistory(control);
      checkPortal(control);
      if (field.blocked || members.some(protectedControl)) throw new Error("This field is manual only.");
      if (unavailable(element)) throw new Error("This field cannot be edited.");
      const changed = field.type === "combobox" ? controlIdentity(element) !== control.identity : fingerprint(element) !== control.fingerprint;
      if (changed) throw new Error("Question or control identity changed. Rescan before filling.");
    };
    const verify = (control, expected) => (adapter ? adapter.verify(control, expected) : verifyCore(control, expected));
    for (const selection of selections) {
      const control = controls.get(selection.id);
      const guard = {selection, overwrite, attachment, state, checkCollateral, checkCurrent, verify};
      results.push(!adapter ? await fillField(control, selection, guard)
        : control?.field.type === "file" ? await adapter.upload(control, attachment, guard) : await adapter.fill(control, selection, guard));
    }
    return results;
  }

  async function fill(selections, options = {}) {
    if (filling) throw new Error("A fill is already running on this page. Wait for its results.");
    filling = true;
    try { return await fillSelected(selections, options); }
    finally { filling = false; }
  }

  function scan(profile, options = {}) {
    const adapter = route();
    return adapter ? adapter.scan(profile, options) : scanCore(profile, options);
  }

  // Adapters delegate to these legacy bodies, which stay otherwise private to the engine closure.
  const core = {scan: scanCore, propose: proposeCore, fill: fillField, verify: verifyCore};
  globalThis.PortalEngine = {scan, fill, optionMatch, inspect, profileRecords, core};
})();
