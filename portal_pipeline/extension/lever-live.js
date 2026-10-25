/* Author: Yazad Madan. Lever question labels follow the sanitized public apply DOM. */
(() => {
  if (!globalThis.PortalAdapters || !globalThis.PortalLeverAdapter || PortalAdapters.list().some(item => item.id === "lever-live")) return;
  const base = PortalLeverAdapter;
  const generic = PortalAdapters.forLocation("");
  const WRITABLE = new Set(["text", "textarea", "email", "tel", "url", "select-one", "radio"]);
  const MANUAL = "Complete this Lever control manually.";
  const questions = new WeakMap();
  const clean = text => text.replace(/\s+/g, " ").replace(/(?:\s*(?:[*\u2731\u2217]|\(?\brequired\b\)?|\(?\boptional\b\)?))+\s*$/gi, "").trim();

  function question(element) {
    const label = element?.closest(".application-question")?.querySelector(".application-label");
    if (!label) return "";
    const copy = (label.querySelector(".text") || label).cloneNode(true);
    copy.querySelectorAll(".required,.optional").forEach(node => node.remove());
    return clean(copy.textContent);
  }

  function elementFor(field) {
    const {dom_id: id, name} = field.structure;
    return (id && document.getElementById(id)) || [...document.getElementsByName(name)].find(node => node.type === field.type);
  }

  const refuse = (control, proposal, reason = MANUAL) =>
    ({id: proposal?.id || control?.field?.id || "", ok: false, status: "refused", actual: null, reason, message: reason});

  PortalAdapters.register({...base, id: "lever-live", version: "live-1", hosts: [/^jobs\.lever\.co$/], mode: "fill", requiresApplicationMode: false,
    scan(profile, options) {
      const groups = new Set();
      return PortalEngine.core.scan(profile, options).filter(field => {
        const element = elementFor(field);
        if (!element || /captcha/i.test(`${field.label} ${element.name} ${element.id}`) || element.closest('.h-captcha,#h-captcha,[data-hcaptcha-widget-id]')) return false;
        const label = question(element);
        if (label && field.type !== "file") {
          // Mutating the registered field keeps review and generic fill on the same question.
          field.label = label;
          field.key = field.blocked ? null : PortalClassifier.classify(label, `${element.name} ${element.id}`, "contact");
        }
        const members = [...document.getElementsByName(element.name)].filter(node => node.type === field.type && node.form === element.form);
        const ambiguousRadio = field.type === "radio" && new Set(members.map(node => node.value)).size !== members.length;
        const protectedQuestion = PortalClassifier.hasAttestationText(field.label) || /\b(captcha|password|ssn|social security|gender|race|ethnicity|veteran|disability|sexual orientation)\b/i.test(field.label);
        const manual = field.blocked || !WRITABLE.has(field.type) || ambiguousRadio || protectedQuestion;
        if (manual) {
          field.blocked = true;
          field.key = null;
          field.current = "";
          field.manual_reason = MANUAL;
        }
        const proposal = generic.propose(field, profile, {element});
        Object.assign(field, {proposal: proposal.value, source: proposal.source, status: proposal.status, truth: proposal.truth});
        questions.set(field, label);
        if (field.type === "checkbox" && /^cards\[/.test(element.name) && label) {
          // Lever checkbox choices share one name and lack unique values, so the group stays manual.
          field.options = members.map(node => ({value: node.value, label: clean(node.closest("label")?.querySelector(".application-answer-alternative")?.textContent || ""), disabled: node.matches(":disabled")}));
          const holder = element.closest(".application-question");
          if (groups.has(holder)) return false;
          groups.add(holder);
        }
        return true;
      });
    },
    fill(control, proposal, guard) {
      if (!control || control.field.blocked || !WRITABLE.has(control.field.type)) return refuse(control, proposal);
      if (question(control.element) !== questions.get(control.field)) return refuse(control, proposal, "Question changed. Rescan before filling.");
      return generic.fill.call(this, control, proposal, guard);
    }
  });
})();
