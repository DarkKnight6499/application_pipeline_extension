const token = document.querySelector("meta[name=portal-token]").content;
const $ = id => document.getElementById(id);
let current = null;
$("sample").disabled = true;
$("create-form").querySelector("button[type=submit]").disabled = true;
$("import-form").querySelector("button[type=submit]").disabled = true;
async function api(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {"X-Portal-Token": token, "Content-Type": "application/json"}, ...(body ? {body: JSON.stringify(body)} : {})});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Request failed.");
  return value;
}
function show(session) {
  current = session;
  $("review").hidden = !session;
  if (!session) return;
  const imported = session.mode === "audited_import";
  $("context").textContent = `${session.company}: ${session.role}. ${imported ? "Audited Application ID " + session.application_id : "Sandbox working copy"}.`;
  $("build-editor").hidden = imported;
  $("audit-details").hidden = !imported;
  $("audit-report").textContent = session.audit_report || "";
  $("content").value = JSON.stringify(session.content, null, 2);
  $("terms").value = (session.requirements?.resume_terms || []).join("\n");
  $("eligibility").value = (session.requirements?.eligibility_requirements || []).map(item => `${item.requirement}::${item.meets}::${item.note || ""}::${item.severity || "required"}`).join("\n");
  $("requirements-reviewed").checked = session.requirements?.requirements_reviewed === true;
  $("content-reviewed").checked = session.content_reviewed === true;
  $("visual-reviewed").checked = session.upload_reviewed;
  $("checks").textContent = session.checks ? `${imported ? "Existing application audit passed." : `${session.checks.words} words, ${session.checks.bullets} bullets`}\n${session.checks.blocking.length ? "Needs correction:\n" + session.checks.blocking.join("\n") : "Checks passed."}\n\nReview notes:\n${session.checks.advisory.join("\n")}` : "Build after reviewing the content and JD requirements.";
  $("download").disabled = !session.checks;
  $("approve").disabled = session.state !== "built";
}
$("import-form").onsubmit = event => {
  event.preventDefault();
  action(async () => {
    $("status").textContent = "Running the existing application audit...";
    show(await api("/api/import", Object.fromEntries(new FormData(event.target))));
    $("status").textContent = "Audited resume imported. Download and review it in Word before enabling attachment.";
  });
};
$("build-editor").addEventListener("input", () => {
  if (!current) return;
  $("approve").disabled = true;
  $("visual-reviewed").checked = false;
  $("status").textContent = "Unsaved edits. Build again to replace the current working document and reset its upload review.";
});
async function action(operation) {
  try { await operation(); }
  catch (error) { $("status").textContent = error.message; }
}
$("create-form").onsubmit = event => {
  event.preventDefault();
  action(async () => {
    const values = Object.fromEntries(new FormData(event.target));
    show(await api("/api/sessions", values));
    $("requirements-reviewed").checked = false;
    $("content-reviewed").checked = false;
    $("terms").value = "";
    $("eligibility").value = "";
    $("status").textContent = "Working application created. Review its resume content and requirements.";
  });
};
$("sample").onclick = () => {
  const form = $("create-form");
  form.closest("details").open = true;
  form.elements.company.value = "Synthetic Employer";
  form.elements.role.value = "Treasury Risk Analyst";
  form.elements.url.value = location.origin + "/fixture";
  form.elements.jd.value = "Synthetic demonstration posting. Treasury risk analyst working on ALM, LCR, NSFR, Python, SQL, and Basel III. Relevant finance education preferred. This is a local test form, not an employer application.";
  const template = [...$("templates").options].find(option => option.value.includes("ALM_Treasury"));
  if (template) $("templates").value = template.value;
  form.requestSubmit();
};
$("build").onclick = () => action(async () => {
  const eligibility = $("eligibility").value.split("\n").filter(line => line.trim()).map(line => {
    const [requirement, meets, note = "", severity = "required"] = line.split("::").map(value => value.trim());
    return {requirement, meets, note, severity};
  });
  $("status").textContent = "Building the working document...";
  show(await api(`/api/sessions/${current.id}/build`, {content: JSON.parse($("content").value),
    resume_terms: $("terms").value.split("\n").map(value => value.trim()).filter(Boolean), eligibility,
    requirements_reviewed: $("requirements-reviewed").checked, content_reviewed: $("content-reviewed").checked}));
  $("status").textContent = current.state === "built" ? "Working resume built. Download and review it in Word before enabling attachment." : "Working resume built with issues. Correct the listed issues before enabling attachment.";
});
$("download").onclick = () => action(async () => {
  const response = await fetch(`/api/sessions/${current.id}/download`, {headers: {"X-Portal-Token": token}});
  if (!response.ok) throw new Error((await response.json()).error);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = "Yazad_Madan.docx"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("approve").onclick = () => action(async () => {
  show(await api(`/api/sessions/${current.id}/approve-upload`, {visual_reviewed: $("visual-reviewed").checked}));
  $("status").textContent = "This document is enabled for attachment. Review and select fields on the application page.";
});
$("pairing").value = token;
$("copy").onclick = () => action(async () => {await navigator.clipboard.writeText(token); $("status").textContent = "Pairing token copied.";});
action(async () => {
  const config = await api("/api/config");
  config.templates.forEach(name => {
    const option = document.createElement("option"); option.value = name; option.textContent = name.replace("Resume_Draft_", "").replace(".json", "").replaceAll("_", " ");
    $("templates").append(option);
  });
  show(config.current);
  $("sample").disabled = false;
  $("create-form").querySelector("button[type=submit]").disabled = false;
  $("import-form").querySelector("button[type=submit]").disabled = false;
  $("status").textContent = "Ready. All generated files stay in this separate development workspace.";
});
