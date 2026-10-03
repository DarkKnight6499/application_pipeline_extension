/* Greenhouse hosted-form boundaries verified against a public Justworks form. */
(() => {
  if (globalThis.PortalGreenhouse) return;
  const active = () => /(^|\.)greenhouse\.io$/.test(location.hostname);
  function form() {
    const matches = document.querySelectorAll("form#application-form");
    return active() && matches.length === 1 ? matches[0] : null;
  }
  function formFor(node) {
    const application = form();
    return application && node.closest("form") === application ? application : null;
  }
  function uploadGroup(node) {
    if (!formFor(node) || node.tagName !== "INPUT" || node.type !== "file" || !["resume", "cover_letter"].includes(node.id)) return null;
    if (document.querySelectorAll(`[id="${node.id}"]`).length !== 1) return null;
    const group = node.closest('.file-upload[role="group"]');
    if (!group || group.querySelectorAll('input[type="file"]').length !== 1 || group.getAttribute("aria-labelledby") !== `upload-label-${node.id}`) return null;
    const labels = document.querySelectorAll(`[id="upload-label-${node.id}"]`);
    if (labels.length !== 1 || !group.contains(labels[0])) return null;
    const label = labels[0].textContent.replace(/\*/g, "").trim();
    const expected = node.id === "resume" ? "resume/cv" : "cover letter";
    return label.toLowerCase() === expected ? group : null;
  }
  function label(node) {
    const group = uploadGroup(node);
    return group ? document.getElementById(group.getAttribute("aria-labelledby")).textContent.replace(/\*/g, "").trim() : null;
  }
  const protectedField = node => !!formFor(node) && !!node.closest("#demographic-section,.demographic--container");
  globalThis.PortalGreenhouse = {active, form, formFor, uploadGroup, label, protectedField};
})();
