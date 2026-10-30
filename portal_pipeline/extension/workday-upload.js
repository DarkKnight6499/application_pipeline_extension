(() => {
  if (globalThis.PortalWorkdayUpload) return;
  const INPUT_SELECTOR = 'input[type="file"][data-automation-id="file-upload-input-ref"]';
  const CONTAINER_SELECTOR = '[data-automation-id*="file-upload"],[data-automation-id*="attachments-FileUpload"]';
  // Config
  const CONFIRMATION_TIMEOUT = 15000;
  const POLL_INTERVAL = 100;
  const MAX_TIMEOUT = 60000;
  const REJECTION_SELECTOR = '[role="alert"],[data-automation-id*="error"],[id$="-error"]';
  const NAME_LIMIT = 240;
  const SLOT_PATTERNS = {resume: /\b(resume|cv)\b/i, cover: /cover\s*letter/i};
  const SLOT_CONTAINER_SELECTOR = CONTAINER_SELECTOR + ',fieldset,[data-automation-id="formField-resume"],[data-automation-id="formField-coverLetter"]';
  const DELETE_SELECTOR = 'button,[role="button"],input[type="button"]';
  const DELETE_LABEL = /^(?:delete|remove)(?:\s+(?:file|attachment|resume|cv|cover\s*letter))?(?:\s+.+\.(?:pdf|docx?|rtf|txt|odt))?$/i;
  const UNSAFE_DELETE_LABEL = /submit|finish|sign|attest|certif|login|captcha|verif/i;
  const FILENAME_PATTERN = /[^\s"'()<>:\\\/]+\.(?:pdf|docx?|rtf|txt|odt)\b/gi;
  const ITEM_SELECTOR = '[data-automation-id="file-upload-item"]';
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const SIZE_PATTERN = /(\d+(?:\.\d+)?)\s*(bytes?|kb|mb)(?![a-z])/i;

  function observation(container, name, byteLength) {
    const text = container.innerText || container.textContent || "";
    const exact = new RegExp("(^|[\\s\"'(])" + escapeRegExp(name) + "($|[\\s\"')])").test(text);
    const size = SIZE_PATTERN.exec(text);
    const unit = size?.[2].toLowerCase();
    const shown = size ? Number(size[1]) * (unit === "mb" ? 1048576 : unit.startsWith("b") ? 1 : 1024) : null;
    const precision = size?.[1].split(".")[1]?.length || 0;
    const slack = unit?.startsWith("b") ? 0 : (unit === "mb" ? 1048576 : 1024) * 0.5 * 10 ** -precision;
    const mismatch = exact && shown !== null && (slack === 0 ? shown !== byteLength : byteLength < shown - slack || byteLength >= shown + slack);
    const rejected = [...container.querySelectorAll(REJECTION_SELECTOR)].some(node =>
      node.getClientRects().length && !node.closest('[hidden],[aria-hidden=true]') && node.textContent.trim());
    const ambiguous = container.querySelectorAll(ITEM_SELECTOR).length > 1;
    return {confirmed: exact && shown !== null && !mismatch && !rejected && !ambiguous, size_mismatch: mismatch, rejected, ambiguous,
      observed_filename: exact ? name.slice(0, NAME_LIMIT) : (text.match(/[^\s"'()<>:\\\/]+\.(?:pdf|docx?|rtf|txt|odt)\b/i)?.[0] || "").slice(0, NAME_LIMIT), observed_size: shown};
  }

  function owner(node) {
    let fallback = null;
    for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      if (!parent.querySelectorAll) continue;
      if (parent.querySelectorAll('input[type="file"]').length > 1) break;
      const clone = parent.cloneNode?.(true);
      clone?.querySelectorAll(ITEM_SELECTOR + ',input,button,[role="button"],script,style').forEach(child => child.remove());
      const text = [parent.getAttribute("aria-label"), clone ? clone.textContent : parent.textContent].filter(Boolean).join(" ").trim();
      const identity = parent.getAttribute("data-automation-id") || "";
      if (/^formField-(coverLetter|attachments)$/i.test(identity) || /\bcover\s*letter\b/i.test(text) || /^attachments\b/i.test(text)) return {slot: "cover", container: parent};
      if (/^formField-resume$/i.test(identity) || SLOT_PATTERNS.resume.test(text)) return {slot: "resume", container: parent};
      if (!fallback && /\bupload a file\b/i.test(text)) fallback = {slot: "resume", container: parent};
    }
    return fallback;
  }

  function find(root = document, slot = "resume") {
    const inputs = root.querySelectorAll(INPUT_SELECTOR);
    const owned = [...inputs].filter(input => owner(input)?.slot === slot);
    if (owned.length) return owned.length === 1 ? owned[0] : null;
    return inputs.length === 1 ? inputs[0] : null;
  }

  function refindContainer(previous, slot = "resume") {
    const sameSlot = node => node && !(slot === "resume" ? /cover letter/i.test(node.textContent) && !/(resume|cv)/i.test(node.textContent) : !SLOT_PATTERNS.cover.test(node.textContent)) &&
      (previous.id ? node.id === previous.id : node.getAttribute("data-automation-id") === previous.getAttribute("data-automation-id"));
    const input = find(document, slot);
    const live = owner(input || {})?.container || input?.parentElement?.closest(CONTAINER_SELECTOR);
    if (sameSlot(live)) return live;
    if (previous.isConnected) return previous;
    const candidates = [...document.querySelectorAll(CONTAINER_SELECTOR)].filter(sameSlot);
    return candidates.length === 1 ? candidates[0] : null;
  }

  async function upload(input, attachment, guard = () => {}, {timeout = CONFIRMATION_TIMEOUT, detailed = false, slot = "resume"} = {}) {
    const started = performance.now();
    const finish = (state, status = "unconfirmed") => {
      const result = {...state, status, elapsed_seconds: (performance.now() - started) / 1000, subtype: slot};
      if (detailed) return result;
      if (!state.confirmed) throw Object.assign(new Error("Upload was not confirmed on the page. Check it manually."), {upload_state: result});
      return status === "already attached" ? status : attachment.name;
    };
    guard();
    if (!input?.isConnected || !input.matches(INPUT_SELECTOR) || input.matches(":disabled") || input.getAttribute("aria-disabled") === "true") throw new Error("The upload input is unavailable. Rescan before attaching.");
    if (!attachment || ["name", "mime", "base64", "sha256"].some(key => typeof attachment[key] !== "string" || !attachment[key])) {
      throw new Error("Provide all resume attachment fields.");
    }
    const {name, mime, base64, sha256} = attachment;
    const ownership = owner(input);
    let container = ownership?.container || input.parentElement?.closest(CONTAINER_SELECTOR);
    if (!container) throw new Error("The upload container is unavailable. Rescan before attaching.");
    if (ownership && ownership.slot !== slot) throw new Error("The attachment slot changed to " + ownership.slot + ". Attach it manually.");
    if (!ownership && slot === "resume" && /cover letter/i.test(container.textContent) && !/(resume|cv)/i.test(container.textContent)) throw new Error("This looks like a cover letter upload, not the resume. Attach it manually.");
    if (!ownership && slot === "cover" && (!SLOT_PATTERNS.cover.test(container.textContent) || SLOT_PATTERNS.resume.test(container.textContent))) throw new Error("The cover letter slot is ambiguous. Attach it manually.");
    const bytes = Uint8Array.from(atob(base64), character => character.charCodeAt(0));
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const checksum = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
    if (checksum !== sha256) throw new Error("Resume checksum does not match.");
    guard();
    if (!input.isConnected || !container.contains(input)) throw new Error("The upload input is unavailable. Rescan before attaching.");
    const files = [...input.files];
    if (files.length > 1 || container.querySelectorAll(ITEM_SELECTOR).length > 1) throw new Error("Multiple attachments require manual review.");
    if (files.some(file => file.name !== name)) throw new Error("A different file is already attached. Replace it manually.");
    for (const file of files) {
      const existing = [...new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()))].map(value => value.toString(16).padStart(2, "0")).join("");
      if (existing !== sha256) throw new Error("A different file with this name is already attached. Replace it manually.");
    }
    guard();
    if (!input.isConnected || container.querySelectorAll(ITEM_SELECTOR).length > 1 || !container.contains(input) || input.files.length !== files.length ||
        [...input.files].some((file, index) => file !== files[index])) throw new Error("The upload input changed. Rescan before attaching.");
    const initial = observation(container, name, bytes.length);
    if (files.length && initial.confirmed) return finish(initial, "already attached");
    const stale = !files.length && initial.observed_filename === name;
    if (!files.length) {
      const transfer = new DataTransfer();
      transfer.items.add(new File([bytes], name, {type: mime}));
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", {bubbles: true}));
    }
    guard();
    const deadline = performance.now() + Math.min(MAX_TIMEOUT, Math.max(0, Number.isFinite(timeout) ? timeout : CONFIRMATION_TIMEOUT));
    let replaced = false;
    let latest = initial;
    while (true) {
      guard();
      const liveContainer = refindContainer(container, slot);
      if (liveContainer && liveContainer !== container) {
        replaced = true;
        container = liveContainer;
      }
      if (!container.isConnected) replaced = true;
      latest = container.isConnected ? observation(container, name, bytes.length) : {confirmed: false};
      latest.container_replaced = replaced;
      latest.stale_filename = stale;
      if (latest.rejected || latest.ambiguous || stale) return finish({...latest, confirmed: false});
      if (latest.confirmed) return finish(latest, files.length ? "already attached" : "confirmed");
      const remaining = deadline - performance.now();
      if (remaining <= 0) return finish(latest);
      await sleep(Math.min(POLL_INTERVAL, remaining));
    }
  }

  function slotContainers(slot) {
    const owned = [...new Set([...document.querySelectorAll(INPUT_SELECTOR)].map(owner)
      .filter(state => state?.slot === slot).map(state => state.container))];
    if (owned.length) return owned;
    const other = slot === "resume" ? "cover" : "resume";
    const candidates = [...document.querySelectorAll(SLOT_CONTAINER_SELECTOR)].filter(node => {
      const label = [node.getAttribute("aria-label"), node.textContent,
        ...[...node.querySelectorAll(INPUT_SELECTOR)].flatMap(input => [input.getAttribute("aria-label"),
          ...[...(input.labels || [])].map(item => item.textContent)])].filter(Boolean).join(" ");
      return SLOT_PATTERNS[slot].test(label) && !SLOT_PATTERNS[other].test(label);
    });
    return candidates.filter(node => !candidates.some(otherNode => otherNode !== node && node.contains(otherNode)));
  }

  function slotState(slot) {
    const containers = slotContainers(slot);
    if (!containers.length) {
      const known = Object.keys(SLOT_PATTERNS).flatMap(slotContainers);
      const unknown = [...document.querySelectorAll(INPUT_SELECTOR)].some(input => !known.some(node => node.contains(input)));
      return {status: unknown ? "ambiguous" : "absent"};
    }
    if (containers.length !== 1) return {status: "ambiguous"};
    const container = containers[0];
    const inputs = [...container.querySelectorAll(INPUT_SELECTOR)];
    const names = [...new Set((container.textContent || "").match(FILENAME_PATTERN) || [])];
    const files = inputs.flatMap(input => [...input.files]);
    const attached = names.length > 0 || files.length > 0;
    const deletions = [...container.querySelectorAll(DELETE_SELECTOR)].filter(node => {
      const label = node.getAttribute("aria-label") || node.textContent || node.value || "";
      return node.getClientRects().length && !node.disabled && node.getAttribute("aria-disabled") !== "true" &&
        !node.closest('[hidden],[aria-hidden="true"]') && DELETE_LABEL.test(label.trim()) && !UNSAFE_DELETE_LABEL.test(label) &&
        node.type !== "submit" && node.type !== "image";
    });
    const input = inputs[0];
    const ambiguous = inputs.length !== 1 || !input?.isConnected || input.matches(":disabled") ||
      input.getAttribute("aria-disabled") === "true" || names.length > 1 || files.length > 1 ||
      container.querySelectorAll(ITEM_SELECTOR).length > 1 ||
      (names.length && files.length && names[0] !== files[0].name) || (attached && deletions.length !== 1) || (!attached && deletions.length);
    return {status: ambiguous ? "ambiguous" : "ready", container, input, attached, deletion: deletions[0], names, files};
  }

  function inspectSlot(slot) {
    const state = slotState(slot);
    return {status: state.status, subtype: slot, attached: Boolean(state.attached)};
  }

  async function replace(attachment, slot, guard = () => {}, {timeout = CONFIRMATION_TIMEOUT} = {}) {
    guard();
    if (!Object.hasOwn(SLOT_PATTERNS, slot)) throw new Error("Unknown attachment slot.");
    if (!attachment || ["name", "mime", "base64", "sha256"].some(key => typeof attachment[key] !== "string" || !attachment[key])) {
      throw new Error("Provide all attachment fields before replacement.");
    }
    let state = slotState(slot);
    if (state.status !== "ready") return {confirmed: false, status: state.status, removal: state.status, subtype: slot};
    // Invalid replacements must leave the previous attachment intact.
    const bytes = Uint8Array.from(atob(attachment.base64), character => character.charCodeAt(0));
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(value => value.toString(16).padStart(2, "0")).join("");
    if (digest !== attachment.sha256) throw new Error("Attachment checksum does not match.");
    guard();
    const current = slotState(slot);
    if (current.status !== "ready" || current.container !== state.container || current.input !== state.input ||
        current.deletion !== state.deletion || current.attached !== state.attached || current.names.join("\n") !== state.names.join("\n") ||
        current.files.length !== state.files.length || current.files.some((file, index) => file !== state.files[index])) {
      return {confirmed: false, status: "ambiguous", removal: "identity_changed", subtype: slot};
    }
    let removal = "not_needed";
    if (state.attached) {
      guard();
      state.deletion.click();
      const deadline = performance.now() + Math.min(MAX_TIMEOUT, Math.max(0, timeout));
      while (true) {
        guard();
        state = slotState(slot);
        if (state.status === "ready" && !state.attached) break;
        if (state.status === "ambiguous" || performance.now() >= deadline) {
          return {confirmed: false, status: "unconfirmed", removal: state.status === "ambiguous" ? "ambiguous" : "timeout", subtype: slot};
        }
        await sleep(POLL_INTERVAL);
      }
      removal = "removed";
    }
    guard();
    const result = await upload(state.input, attachment, guard, {timeout, detailed: true, slot});
    return {...result, removal};
  }

  globalThis.PortalWorkdayUpload = {find, upload, inspectSlot, replace};
})();
