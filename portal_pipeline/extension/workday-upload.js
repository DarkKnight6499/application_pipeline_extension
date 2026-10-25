(() => {
  if (globalThis.PortalWorkdayUpload) return;
  const INPUT_SELECTOR = 'input[type="file"][data-automation-id="file-upload-input-ref"]';
  const CONTAINER_SELECTOR = '[data-automation-id*="file-upload"],[data-automation-id*="attachments-FileUpload"]';
  const CONFIRMATION_TIMEOUT = 5000;
  const POLL_INTERVAL = 100;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  function find(root = document) {
    const inputs = root.querySelectorAll(INPUT_SELECTOR);
    return inputs.length === 1 ? inputs[0] : null;
  }

  async function upload(input, attachment, guard = () => {}) {
    guard();
    if (!input?.isConnected || !input.matches(INPUT_SELECTOR)) throw new Error("The upload input is unavailable. Rescan before attaching.");
    if (!attachment || ["name", "mime", "base64", "sha256"].some(key => typeof attachment[key] !== "string" || !attachment[key])) {
      throw new Error("Provide all resume attachment fields.");
    }
    const {name, mime, base64, sha256} = attachment;
    const container = input.parentElement?.closest(CONTAINER_SELECTOR);
    if (!container) throw new Error("The upload container is unavailable. Rescan before attaching.");
    const bytes = Uint8Array.from(atob(base64), character => character.charCodeAt(0));
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const checksum = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
    if (checksum !== sha256) throw new Error("Resume checksum does not match.");
    if (!input.isConnected || !container.contains(input)) throw new Error("The upload input is unavailable. Rescan before attaching.");
    const files = [...input.files];
    if (files.some(file => file.name !== name)) throw new Error("A different file is already attached. Replace it manually.");
    if (files.some(file => file.name === name) && container.textContent.includes(name)) return "already attached";
    const transfer = new DataTransfer();
    transfer.items.add(new File([bytes], name, {type: mime}));
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", {bubbles: true}));
    guard();
    const deadline = performance.now() + CONFIRMATION_TIMEOUT;
    while (!container.textContent.includes(name)) {
      const remaining = deadline - performance.now();
      if (remaining <= 0) throw new Error("Upload was not confirmed on the page. Check it manually.");
      await sleep(Math.min(POLL_INTERVAL, remaining));
    }
    return name;
  }

  globalThis.PortalWorkdayUpload = {find, upload};
})();
