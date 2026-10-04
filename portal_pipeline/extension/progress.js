/* Page progression guards: required sweep, stall check, Next classification and a default-off guarded Next. */
(() => {
  if (globalThis.PortalProgress) return;
  const MAX_NEXT_ACTIONS = 15, MAX_ROUNDS = 3, ROUND_PAUSE_MS = 120;
  // Decision D3: guarded Next stays off until Yazad turns it on.
  const settings = {allowGuardedNext: false};
  const ALLOW = ["next", "continue", "save and continue", "proceed"];
  const DENY = ["submit", "apply", "finish", "send", "sign", "certify", "attest", "agree", "review and submit", "complete"];
  const PLACEHOLDER = /^(select|choose|please select|please choose|pick)\b/i;
  const FIELD_TYPES = /^(text|checkbox|radio|file|hidden|password|email|tel|number|date|search|url|range|color|time|month|week|datetime-local)$/;
  const normalize = value => String(value ?? "").toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const stalls = new Map();
  let nextActions = 0;

  function shown(node) {
    if (node.closest('#portal-panel-host,[aria-hidden="true"],[hidden]')) return false;
    const style = getComputedStyle(node);
    return style.display !== "none" && style.visibility !== "hidden" && node.getClientRects().length > 0;
  }

  const heading = () => [...document.querySelectorAll("h1,h2,[role=heading]")].find(shown)?.textContent.trim() || "";
  const pageKey = () => `${location.host}${location.pathname}#${normalize(heading())}`;
  const labelOf = node => (node.textContent.trim() || node.value || node.getAttribute("aria-label") || "").trim();

  function candidates(doc = document) {
    const list = [...doc.querySelectorAll("button,input,[role=button]")].filter(node => node.tagName !== "INPUT" || !FIELD_TYPES.test(node.type)).filter(shown).map(node => ({node, label: labelOf(node), key: normalize(labelOf(node))}));
    const denied = list.filter(item => DENY.some(term => item.key.includes(term)));
    const nativeSubmit = item => item.node.matches("button,input") && ["submit", "image"].includes(item.node.type);
    const allowed = list.filter(item => !nativeSubmit(item) && !denied.includes(item) && ALLOW.includes(item.key));
    return {list, denied, allowed};
  }

  const refFor = (item, ordinal) => `next:${ordinal}:${item.key}`;

  function nextStep(doc = document) {
    const {denied, allowed} = candidates(doc);
    if (!allowed.length) return {kind: "none", label: "", ref: null};
    const sameScope = item => denied.some(other => other.node.closest("form") === item.node.closest("form"));
    if (allowed.length > 1 || sameScope(allowed[0])) return {kind: "ambiguous", label: allowed.map(item => item.label).join(" | "), ref: null};
    return {kind: "next", label: allowed[0].label, ref: refFor(allowed[0], 0)};
  }

  function resolveRef(ref) {
    const {allowed} = candidates();
    const index = allowed.findIndex((item, ordinal) => refFor(item, ordinal) === ref);
    return index >= 0 && allowed.length === 1 ? allowed[0].node : null;
  }

  function scanFields(adapter) {
    const scan = adapter ? adapter.scan.bind(adapter) : PortalEngine.scan;
    return scan({values: {}}, {register: false});
  }

  function detectFinalReview(doc = document, adapter = null) {
    const reasons = candidates(doc).denied.map(item => `control: ${item.label}`);
    if (/review/i.test(heading()) && !scanFields(adapter).some(field => !field.blocked && !field.disabled)) reasons.push("review heading without editable fields");
    return {final: reasons.length > 0, reasons};
  }

  function missingReason(field) {
    const current = field.current;
    if (field.type === "checkbox") return current ? null : "unchecked_required";
    if (field.type.startsWith("select")) {
      const chosen = field.options.find(option => option.value === current);
      return current === "" || (chosen && PLACEHOLDER.test(chosen.label.trim())) ? "placeholder_selected" : null;
    }
    if (field.type === "combobox") return current === "" || PLACEHOLDER.test(String(current).trim()) ? "placeholder_selected" : null;
    return current === "" || current === null || current === undefined ? "empty" : null;
  }

  async function requiredSweep(adapter = null) {
    let ids = new Set(), fields = [];
    for (let round = 0; round < MAX_ROUNDS; round++) {
      fields = scanFields(adapter).filter(field => field.required || /\*\s*$/.test(field.label));
      const found = new Set(fields.map(field => field.id));
      const settled = round > 0 && [...found].every(id => ids.has(id));
      ids = found;
      if (settled || round === MAX_ROUNDS - 1) break;
      await pause(ROUND_PAUSE_MS);
    }
    const missing = fields.map(field => ({id: field.id, label: field.label, reason: missingReason(field), manual: !!field.blocked})).filter(item => item.reason);
    return {page_key: pageKey(), missing, checked: fields.length};
  }

  function stallCheck(key, missingIds) {
    const signature = [...missingIds].sort().join("\n");
    const before = stalls.get(key);
    const repeats = signature && before?.signature === signature ? before.repeats + 1 : 1;
    stalls.set(key, {signature, repeats});
    return {stalled: !!signature && repeats >= 2, repeats};
  }

  async function pageCheck(adapter = null) {
    const sweep = await requiredSweep(adapter);
    return {...sweep, stall: stallCheck(sweep.page_key, sweep.missing.map(item => item.id)), next: nextStep(document),
      final_review: detectFinalReview(document, adapter), allow_guarded_next: settings.allowGuardedNext === true, next_actions: nextActions};
  }

  const refuse = reason => ({status: "refused", reason, message: `Next not clicked: ${reason}.`});

  async function guardedNext(adapter = null) {
    if (settings.allowGuardedNext !== true) return refuse("guarded_next_off");
    if (adapter?.humanGate(document)) return refuse("human_gate");
    if (detectFinalReview(document, adapter).final) return refuse("final_review");
    const sweep = await requiredSweep(adapter);
    if (stallCheck(sweep.page_key, sweep.missing.map(item => item.id)).stalled) return refuse("stalled");
    if (sweep.missing.length) return refuse("missing_required");
    if (nextActions >= MAX_NEXT_ACTIONS) return refuse("max_next_actions");
    const next = nextStep(document);
    if (next.kind !== "next") return refuse(`next_${next.kind}`);
    const node = resolveRef(next.ref);
    if (adapter?.humanGate(document)) return refuse("human_gate");
    if (detectFinalReview(document, adapter).final) return refuse("final_review");
    if (!node || node.matches("button[type=submit],input[type=submit],input[type=image]")
        || DENY.some(term => normalize(labelOf(node)).includes(term))) return refuse("next_unresolved");
    nextActions++;
    node.click();
    return {status: "clicked", ref: next.ref, label: next.label, message: "Next clicked once."};
  }

  globalThis.PortalProgress = {requiredSweep, stallCheck, guardedNext, pageCheck, nextStep, detectFinalReview, settings, MAX_NEXT_ACTIONS};
})();
