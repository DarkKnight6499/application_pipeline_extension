const api = async (path, body) => {
  const headers = {"X-Portal-Token": document.querySelector("meta[name=portal-token]").content};
  const response = await fetch(path, body ? {method: "POST", headers: {...headers, "Content-Type": "application/json"}, body: JSON.stringify(body)} : {headers});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error);
  return value;
};
const memory = new Map();
document.getElementById("scan").onclick = () => PortalPanel.open(api, {load: async key => memory.get(key), save: async (key, value) => memory.set(key, value)});
const jobs = document.getElementById("jobs");
for (let index = 0; index < 5; index++) {
  const section = document.createElement("fieldset");
  section.dataset.portalSection = "employment";
  section.setAttribute("data-automation-id", "workExperience-" + index);
  const legend = document.createElement("legend"); legend.textContent = "Employment " + (index + 1); section.append(legend);
  for (const [name, label, type] of [["company", "Employer", "text"], ["title", "Job title", "text"], ["start", "Start date", "month"], ["end", "End date", "month"], ["description", "Job description", "textarea"]]) {
    const wrapper = document.createElement("label"); wrapper.textContent = label;
    const input = document.createElement(type === "textarea" ? "textarea" : "input");
    if (type !== "textarea") input.type = type;
    input.id = `${name}-${index}`; input.name = input.id;
    wrapper.append(input); section.append(wrapper);
  }
  jobs.append(section);
}
const educationRecords = document.getElementById("education-records");
for (let index = 0; index < 2; index++) {
  const section = document.createElement("fieldset"); section.dataset.portalSection = "education"; section.id = `education-row-${index}`;
  const legend = document.createElement("legend"); legend.textContent = `Education ${index + 1}`; section.append(legend);
  for (const [name, label, type] of [["school", "School", "text"], ["degree", "Degree", "text"], ["start-year", "Start year", "number"], ["end-month", "Graduation month", "select"], ["end-year", "Graduation year", "number"]]) {
    const wrapper = document.createElement("label"); wrapper.textContent = label;
    const input = document.createElement(type === "select" ? "select" : "input");
    if (type !== "select") input.type = type;
    input.id = `education-${name}-${index}`; input.name = input.id;
    if (type === "select") {
      const blank = document.createElement("option"); blank.value = ""; blank.textContent = "Choose month"; input.append(blank);
      ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].forEach((month, offset) => {
        const option = document.createElement("option"); option.value = String(offset); option.textContent = month; input.append(option);
      });
    }
    wrapper.append(input); section.append(wrapper);
  }
  educationRecords.append(section);
}
function step(number) {
  document.querySelectorAll("[data-step]").forEach(node => {node.hidden = node.dataset.step !== String(number);});
  document.getElementById("progress").textContent = `Step ${number} of 3`;
  document.getElementById("portal-panel-host")?.remove();
}
document.getElementById("next-one").onclick = () => step(2);
document.getElementById("next-two").onclick = () => step(3);
document.getElementById("resume").onchange = event => {document.getElementById("upload-state").textContent = event.target.files[0]?.name ? "Attached: " + event.target.files[0].name : "";};
let submits = 0;
document.getElementById("application").onsubmit = event => {event.preventDefault(); submits++; document.getElementById("submit-count").textContent = "Submit clicks: " + submits;};
const relocation = document.getElementById("custom-relocation"), choices = document.getElementById("relocation-options");
relocation.onclick = () => {choices.hidden = !choices.hidden; relocation.setAttribute("aria-expanded", String(!choices.hidden));};
choices.querySelectorAll('[role="option"]').forEach(option => {
  option.onclick = () => {
    choices.querySelectorAll('[role="option"]').forEach(item => item.setAttribute("aria-selected", String(item === option)));
    relocation.textContent = option.textContent;
    relocation.setAttribute("aria-valuetext", option.textContent);
    relocation.setAttribute("aria-expanded", "false"); choices.hidden = true;
  };
});
