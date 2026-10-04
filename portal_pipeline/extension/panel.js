/* Review panel shared by the extension and the local synthetic fixture. */
(() => {
  if (globalThis.PortalPanel) return;
  function element(tag, text, attributes = {}) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  async function open(api, storage, options = {}) {
    document.getElementById("portal-panel-host")?.remove();
    const host = element("div", "", {id: "portal-panel-host"});
    const shadow = host.attachShadow({mode: "open"});
    shadow.append(element("style", `
      :host{all:initial;position:${options.extensionPage ? "static" : "fixed"};right:18px;top:18px;width:${options.extensionPage ? "100%" : "460px"};max-width:95vw;max-height:94vh;z-index:2147483647;color:#18273d;font:14px system-ui}
      *{box-sizing:border-box} .panel{background:#fff;border:1px solid #cad5e2;border-radius:14px;box-shadow:0 12px 60px #18273d40;padding:18px;max-height:94vh;overflow:auto}
      h2{margin:0;font-size:20px} p{line-height:1.5}button{cursor:pointer;border:1px solid #b7c5d8;border-radius:7px;background:#eef3fa;color:#18273d;padding:9px 12px;font:inherit}
      button.primary{background:#254c79;color:white}button:disabled{opacity:.55;cursor:default}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.top{justify-content:space-between}
      .field{border:1px solid #dce3ed;border-radius:9px;margin:10px 0;padding:12px}.field label{font-weight:600;display:block;margin-bottom:8px}.field input.answer,.field textarea,.field select{width:100%;padding:8px;border:1px solid #becada;border-radius:6px;font:inherit}
      .field textarea{min-height:70px}.source,.current{font-size:12px;color:#56677d;overflow-wrap:anywhere;margin-top:6px}.result{font-size:12px;margin-top:8px}.failed{color:#a12828}.filled{color:#196442}.pending{background:#fff9ee}.manual{background:#f5f6f8}
      .note{padding:10px;background:#eef3fa;border-radius:8px}.close{font-size:12px}select{padding:6px}.sticky{position:sticky;bottom:-18px;background:white;padding:12px 0;border-top:1px solid #ddd}
    `));
    const panel = element("section", "", {class: "panel", "aria-label": "Portal filling review"});
    const top = element("div", "", {class: "row top"});
    top.append(element("h2", options.inspectionOnly ? "Inspect application fields" : "Review selected fields"));
    const close = element("button", "Close", {class: "close", type: "button"});
    close.onclick = () => host.remove();
    top.append(close);
    panel.append(top);
    const exportReport = element("button", "Export field structure", {type: "button"});
    panel.append(exportReport);
    const status = element("p", "Loading approved profile...", {class: "note", role: "status"});
    panel.append(status);
    shadow.append(panel);
    document.body.append(host);
    exportReport.onclick = async () => {
      try {
        const report = await (options.transport ? options.transport.inspect() : PortalEngine.inspect());
        const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: "application/json"}));
        const link = document.createElement("a"); link.href = url; link.download = "portal-field-structure.json"; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        status.textContent = "Field structure exported. Entered answers, proposals, and protected fields are omitted. Review labels before sharing.";
      } catch (error) {status.textContent = error.message;}
    };
    if (options.inspectionOnly) {
      try {
        const report = await options.transport.inspect();
        status.textContent = `${report.host}: ${report.fields.length} visible, unprotected controls. Inspection only. No candidate profile loaded and no fields filled.`;
        panel.append(element("p", "This is a current-page snapshot of visible controls in the main document. Hidden sections, future pages, and closed shadow roots remain uninspected. Navigate manually and export each page. Reports omit entered answers and option text; review labels before sharing.", {class: "source"}));
        const coverage = report.coverage;
        if (coverage?.reason_codes.length) panel.append(element("p", `Incomplete inspection: ${coverage.visible_iframes} visible iframe(s), ${coverage.visible_open_shadow_hosts} visible open shadow host(s), and ${coverage.unsupported_spinbuttons} unsupported spinbutton(s). Inspect those surfaces manually.`, {class: "note"}));
        if (!report.fields.length) panel.append(element("p", "No application fields found. This may be a posting, login page, or unsupported form. Inspect the next application page after manual navigation.", {class: "note"}));
        if (report.portal_manual_reason) panel.append(element("p", report.portal_manual_reason, {class: "note"}));
        for (const field of report.fields) {
          const card = element("div", "", {class: "field"});
          card.append(element("h3", field.label || "Unlabelled control"));
          card.append(element("p", `${field.type}, ${field.section}${field.required ? ", required" : ""}${field.disabled ? ", disabled" : ""}. ${field.option_count} options.`, {class: "source"}));
          if (field.adapter) card.append(element("p", `Adapter: ${field.adapter}`, {class: "source"}));
          if (field.dropdown_state && !field.dropdown_state.options_observed) card.append(element("p", "Choices have not been inspected. Open this dropdown manually and rescan to inspect its structure.", {class: "source"}));
          if (field.manual_reason) card.append(element("p", field.manual_reason, {class: "source"}));
          panel.append(card);
        }
      } catch (error) {status.textContent = error.message;}
      return host;
    }
    try {
      const [baseProfile, session] = await Promise.all([api("/api/profile"), api("/api/current")]);
      let profile = baseProfile;
      if (!session) throw new Error("Import an audited application or create a sandbox application in the dashboard first.");
      // Session profile carries the per-application sponsorship toggle; fall back to the global profile.
      try { const scoped = await api(`/api/sessions/${session.id}/profile`); if (scoped?.values) profile = scoped; } catch (error) { /* global profile stays */ }
      const targetUrl = options.targetUrl || location.href;
      const target = new URL(targetUrl);
      if (session.mode !== "audited_import" && !(target.hostname === "127.0.0.1" && target.pathname === "/fixture")) throw new Error("Sandbox sessions are only for the local fixture. Import an audited application for an employer portal.");
      if (session.url && new URL(session.url).origin !== new URL(targetUrl).origin) throw new Error("This page has a different origin from the selected posting. Prepare or import the correct application first.");
      const cacheKey = `${session.id}|${new URL(targetUrl).origin}${new URL(targetUrl).pathname}`;
      const saved = options.reviewState || await storage.load(cacheKey) || {};
      const bindings = options.bindings || {};
      const fields = await (options.transport ? options.transport.scan(profile, bindings) : PortalEngine.scan(profile, {bindings}));
      // Fail closed: a preflight error leaves Fill disabled rather than skipping the gates.
      let preflight = null, preflightError = "";
      try {
        preflight = await api(`/api/sessions/${session.id}/preflight`, {fields: fields.map(item => ({id: item.id, label: item.label, type: item.type, section: item.section,
          intent: globalThis.PortalClassifier?.workAuthIntent(item.label) ?? null, options: item.options.map(option => option.label)}))});
      } catch (error) { preflightError = error.message; }
      const forcedManual = new Set(preflight?.manual_field_ids || []);
      fields.forEach(item => { if (forcedManual.has(item.id)) { item.blocked = true; item.forced_manual = true; item.manual_reason = "Preflight: answer this yourself."; } });
      // Pending questions feed the local corpus; the server drops protected ones too.
      const pendingQuestions = fields.filter(item => item.status === "pending" && !item.blocked).map(item => ({label: item.label, portal: target.hostname, type: item.type, options: item.options.map(option => option.label), classified_as: item.key}));
      if (pendingQuestions.length) api("/api/corpus", {questions: pendingQuestions}).catch(() => {});
      status.textContent = `${session.company}: ${session.role}. ${fields.length} fields found. Review each selected answer. Submission stays manual.`;
      const posting = element("p", "", {class: "source"});
      posting.textContent = `Selected posting: ${session.url || "No posting URL set"}. Current page: ${targetUrl}`;
      if (session.tracker_url && session.tracker_url !== session.url) posting.textContent += ` Tracker link: ${session.tracker_url}. Portal URL override was set during import.`;
      panel.append(posting);
      const sponsorBox = element("input", "", {type: "checkbox", "aria-label": "Answer No to sponsorship questions for this application"});
      sponsorBox.checked = profile.sponsorship_answer_mode === "screening_no";
      const sponsorLabel = element("label", "", {class: "source"});
      sponsorLabel.append(sponsorBox, document.createTextNode(" Answer No to sponsorship questions for this application. This is a statement on the application. Your boilerplate answer is shown beside each proposal."));
      sponsorBox.onchange = async () => {
        try { await api(`/api/sessions/${session.id}/sponsorship-mode`, {mode: sponsorBox.checked ? "screening_no" : "truthful"}); document.getElementById("rescan")?.click(); }
        catch (error) { sponsorBox.checked = !sponsorBox.checked; status.textContent = error.message; }
      };
      panel.append(sponsorLabel);
      const acknowledgements = [];
      const gates = element("div", "", {class: "preflight"});
      if (preflightError) gates.append(element("p", `Preflight failed: ${preflightError} Fill stays disabled.`, {class: "note failed"}));
      for (const entry of preflight?.items || []) {
        const row = element("div", "", {class: `field ${entry.severity === "block" ? "pending" : ""}`});
        row.append(element("strong", `${entry.severity === "block" ? "Blocking" : "Warning"}: ${entry.message}`));
        if (entry.evidence) row.append(element("div", entry.evidence, {class: "source"}));
        if (entry.ack_required) {
          const box = element("input", "", {type: "checkbox", "aria-label": `Acknowledge preflight item: ${entry.message}`});
          const boxLabel = element("label", "", {class: "source"});
          boxLabel.append(box, document.createTextNode(" I have read this and still want to fill"));
          row.append(boxLabel); acknowledgements.push(box);
        }
        gates.append(row);
      }
      panel.append(gates);
      const groups = element("div", "", {class: "row"});
      const groupSelect = element("select", "", {"aria-label": "Select section"});
      ["contact", "employment", "education", "all"].forEach(group => groupSelect.append(element("option", group, {value: group})));
      const select = element("button", "Select suggested", {type: "button"});
      const clear = element("button", "Clear selection", {type: "button"});
      groups.append(groupSelect, select, clear);
      panel.append(groups);
      const listable = fields.filter(item => !item.blocked);
      const summary = element("div", "", {class: "note"});
      summary.append(element("p", `Required fields: ${listable.filter(item => item.required).map(item => item.label).join("; ") || "none"}.`));
      summary.append(element("p", `Pending, no proposed value: ${listable.filter(item => item.status === "pending").map(item => item.label).join("; ") || "none"}.`));
      panel.append(summary);
      const exportSheet = element("button", "Export answer sheet", {type: "button"});
      panel.append(exportSheet);
      const rows = new Map();
      const recordBoxes = new Set();
      const mappingChoosers = [];
      const capture = () => Object.fromEntries([...rows].map(([id, row]) => [id, {selected: row.checkbox.checked, value: row.answer.value, overwrite: row.overwrite.checked}]));
      const save = async () => {
        await storage.save(cacheKey, capture());
      };
      for (const field of fields) {
        if (field.record && !recordBoxes.has(field.record.id)) {
          recordBoxes.add(field.record.id);
          const mapping = element("div", "", {class: "field note"});
          mapping.append(element("h3", field.record.label));
          mapping.append(element("p", "Choose the employer or school for this row. Changing the choice resets this row's answers and selection.", {class: "source"}));
          const chooser = element("select", "", {"aria-label": `Profile record for ${field.record.label}`});
          chooser.append(element("option", "Choose a profile record", {value: ""}));
          PortalEngine.profileRecords(profile, field.record.group).forEach(record => chooser.append(element("option", record.label, {value: String(record.index)})));
          chooser.append(element("option", "Enter answers manually for this row", {value: "manual"}));
          chooser.value = bindings[field.record.id] === undefined ? "" : String(bindings[field.record.id]);
          mapping.append(chooser); panel.append(mapping);
          mappingChoosers.push(chooser);
          chooser.onchange = async () => {
            const reviewState = capture();
            rows.forEach((row, id) => {if (row.field.record?.id === field.record.id) delete reviewState[id];});
            if (chooser.value === "") delete bindings[field.record.id];
            else bindings[field.record.id] = chooser.value === "manual" ? "manual" : Number(chooser.value);
            await storage.save(cacheKey, reviewState);
            await open(api, storage, {...options, bindings, reviewState});
          };
        }
        const card = element("div", "", {class: `field ${field.blocked ? "manual" : field.status === "pending" ? "pending" : ""}`});
        const title = element("label");
        const checkbox = element("input", "", {type: "checkbox", "aria-label": `Select ${field.label}`});
        const previous = field.record?.index === null ? null : saved[field.id];
        checkbox.disabled = field.blocked || field.disabled || field.record?.index === null;
        checkbox.checked = !checkbox.disabled && previous?.selected === true;
        title.append(checkbox, document.createTextNode(` ${field.label}${field.required ? " *" : ""}`));
        card.append(title);
        const answer = field.type === "file" ? element("input", "", {class: "answer", readonly: "", "aria-label": `Answer ${field.label}`})
          : field.options.length ? element("select", "", {"aria-label": `Answer ${field.label}`})
          : element(field.type === "textarea" ? "textarea" : "input", "", {class: "answer", "aria-label": `Answer ${field.label}`});
        if (field.options.length) {
          answer.append(element("option", "Choose an answer", {value: ""}));
          field.options.filter(option => option.value).forEach(option => {
            const item = element("option", option.label, {value: option.value}); item.disabled = !!option.disabled; answer.append(item);
          });
          const match = PortalEngine.optionMatch(field.options, field.proposal);
          answer.value = previous?.value ?? match?.value ?? "";
        } else answer.value = previous?.value ?? (field.type === "file" ? "Yazad_Madan.docx" : field.proposal);
        answer.disabled = checkbox.disabled;
        card.append(answer);
        const result = element("div", "", {class: "result", role: "status"});
        card.append(element("div", field.blocked ? "Manual only. This control is excluded." : field.manual_reason || field.source, {class: "source"}));
        if (field.truth && !field.blocked) card.append(element("div", `Proposing ${field.proposal} by your toggle; boilerplate says ${field.truth.value} (${field.truth.source}).`, {class: "source"}));
        card.append(element("div", `Current: ${field.current || "empty"}`, {class: "current"}));
        if (field.key && !field.blocked && !field.options.length && field.type !== "file") {
          const saveEdit = element("button", "Save edit to profile", {type: "button", "aria-label": `Save edit to profile for ${field.label}`});
          const sync = () => { saveEdit.disabled = !answer.value.trim() || answer.value === field.proposal; };
          sync(); answer.addEventListener("input", sync); answer.addEventListener("change", sync);
          saveEdit.onclick = async () => {
            try {
              await api(`/api/sessions/${session.id}/override`, {key: field.key, value: answer.value, reason: "Edited in review panel"});
              field.proposal = answer.value; sync(); result.textContent = "Saved to this application's profile overrides.";
            } catch (error) { result.textContent = error.message; }
          };
          card.append(saveEdit);
        }
        const overwrite = element("input", "", {type: "checkbox", "aria-label": `Replace existing ${field.label}`});
        overwrite.checked = !checkbox.disabled && previous?.overwrite === true;
        overwrite.disabled = checkbox.disabled;
        const replaceLabel = element("label", "", {class: "source"});
        replaceLabel.append(overwrite, document.createTextNode(" Replace this field's existing value"));
        card.append(replaceLabel);
        card.append(result);
        panel.append(card);
        rows.set(field.id, {checkbox, answer, overwrite, result, field});
        checkbox.onchange = save;
        answer.onchange = save;
        overwrite.onchange = save;
      }
      select.onclick = () => {
        rows.forEach(row => {
          if (!row.checkbox.disabled && row.field.proposal !== "" && row.field.type !== "file" && row.answer.value && (groupSelect.value === "all" || row.field.section === groupSelect.value)) row.checkbox.checked = true;
        });
        save();
      };
      exportSheet.onclick = async () => {
        try {
          const payload = fields.filter(item => !item.blocked || item.forced_manual).map(item => {
            const row = rows.get(item.id), chosen = row ? (row.answer.tagName === "SELECT" ? row.answer.selectedOptions[0]?.textContent || "" : row.answer.value) : item.proposal;
            const edited = !item.blocked && item.type !== "file" && chosen !== "" && chosen !== item.proposal;
            return {label: item.label, required: item.required, type: item.type, options: item.options.map(option => option.label), blocked: item.blocked, forced_manual: item.forced_manual === true,
              proposal: item.blocked ? "" : chosen, source: edited ? "Edited in review panel" : item.source, status: edited ? "draft_needs_review" : item.status, structure: {maxlength: item.structure?.maxlength ?? null}};
          });
          const sheet = await api(`/api/sessions/${session.id}/answer-sheet`, {fields: payload, url: targetUrl, heading: options.heading ?? (options.extensionPage ? "" : document.querySelector("h1,h2")?.textContent || "")});
          const link = document.createElement("a");
          link.href = URL.createObjectURL(new Blob([sheet.html], {type: "text/html"})); link.download = "answer-sheet.html"; link.click();
          setTimeout(() => URL.revokeObjectURL(link.href), 1000);
          status.textContent = `Answer sheet exported. Saved to ${sheet.html_path || "the session folder"}. Nothing was filled.`;
        } catch (error) { status.textContent = error.message; }
      };
      clear.onclick = () => { rows.forEach(row => {row.checkbox.checked = false;}); save(); };
      const footer = element("div", "", {class: "sticky"});
      const matchPage = element("input", "", {type: "checkbox", id: "match-page"});
      const matchLabel = element("label");
      matchLabel.append(matchPage, document.createTextNode(" This page belongs to the selected posting"));
      const fill = element("button", "Fill selected fields", {type: "button", class: "primary"});
      footer.append(matchLabel, element("p"), fill);
      panel.append(footer);
      const acknowledged = () => !preflightError && acknowledgements.every(box => box.checked);
      const refreshFill = () => { fill.disabled = !acknowledged(); };
      acknowledgements.forEach(box => { box.onchange = refreshFill; });
      refreshFill();
      fill.onclick = async () => {
        if (!acknowledged()) return;
        fill.disabled = true;
        const locked = [...rows.values()].flatMap(row => [row.checkbox, row.answer, row.overwrite]).concat(mappingChoosers, select, clear, groupSelect, close);
        const initialDisabled = locked.map(node => node.disabled);
        try {
          if (!matchPage.checked) throw new Error("Confirm the page belongs to this posting before filling.");
          const selected = [...rows.values()].filter(row => row.checkbox.checked && !row.checkbox.disabled);
          if (!selected.length) throw new Error("Select at least one field.");
          locked.forEach(node => {node.disabled = true;});
          options.onFillState?.(true);
          let attachment = null;
          if (selected.some(row => row.field.type === "file")) attachment = await api(`/api/sessions/${session.id}/attachment`);
          const selections = selected.map(row => ({id: row.field.id, value: row.answer.value, overwrite: row.overwrite.checked}));
          const results = await (options.transport ? options.transport.fill(selections, {attachment}) : PortalEngine.fill(selections, {attachment}));
          results.forEach(result => {
            const row = rows.get(result.id);
            row.result.className = `result ${result.status}`;
            row.result.textContent = `${result.status}: ${result.message}`;
          });
          status.textContent = `${results.filter(item => item.status === "filled").length} filled, ${results.filter(item => item.status === "preserved").length} preserved, ${results.filter(item => item.status === "failed").length} need attention. Continue and submit manually.`;
          await save();
        } catch (error) { status.textContent = error.message; }
        finally { locked.forEach((node, index) => {node.disabled = initialDisabled[index];}); refreshFill(); options.onFillState?.(false); }
      };
    } catch (error) { status.textContent = error.message; }
    return host;
  }
  globalThis.PortalPanel = {open};
})();
