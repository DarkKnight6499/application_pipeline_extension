/* Extension-owned, application-scoped write guard. The page never supplies mode authority. */
(() => {
  if (globalThis.PortalApplicationMode) return;
  let context = null;
  let generation = 0;
  const captchaLatches = new Set();

  function bind(next) {
    if (!next || !/^[a-f0-9]{32}$/.test(next.sessionId || "") ||
        !Number.isSafeInteger(next.applicationId) || next.applicationId <= 0 ||
        next.targetUrl !== location.href) throw new Error("Application identity is unavailable. Rescan before writing.");
    if (context?.sessionId !== next.sessionId || context?.applicationId !== next.applicationId || context?.targetUrl !== next.targetUrl) {
      generation++;
      context = {...next};
    }
  }

  async function broker(action, reason) {
    if (!context) throw new Error("Application mode has not loaded. Rescan before writing.");
    const current = context;
    const version = generation;
    const result = await chrome.runtime.sendMessage({type: "portal-application-mode", action,
      sessionId: current.sessionId, applicationId: current.applicationId, ...(reason ? {reason} : {})});
    if (version !== generation || context !== current) throw new Error("Application identity changed. Rescan before writing.");
    if (!result?.ok) throw new Error(result?.error || "Application mode could not be checked.");
    const mode = result.value;
    if (mode?.schema_version !== 1 || mode.application_id !== current.applicationId ||
        !((mode.mode === "fill" && mode.reason === "unrestricted") ||
          (mode.mode === "answer_sheet_only" && ["captcha", "storage_error"].includes(mode.reason))))
      throw new Error("Invalid application mode response.");
    return mode;
  }

  async function check(adapter) {
    if (adapter?.requiresApplicationMode !== true) return;
    if (!context || context.targetUrl !== location.href) throw new Error("Application page changed. Rescan before writing.");
    if (captchaLatches.has(context.applicationId)) throw new Error("Application is restricted to answer sheet only after CAPTCHA.");
    const restrict = async () => {
      captchaLatches.add(context.applicationId);
      try { await broker("restrict", "captcha"); } catch (error) {
        throw new Error(`CAPTCHA restriction could not be saved: ${error.message}`);
      }
      throw new Error("Application is restricted to answer sheet only after CAPTCHA.");
    };
    const gate = adapter.humanGate(document);
    if (gate?.kind === "captcha") await restrict();
    if (gate) throw new Error(`A ${gate.kind} step needs you. Complete it yourself, then rescan.`);
    if (adapter.mode !== "fill") throw new Error("Application adapter is answer sheet only.");
    const mode = await broker("read");
    if (context.targetUrl !== location.href || captchaLatches.has(context.applicationId) || adapter.mode !== "fill")
      throw new Error("Application mode or page changed. Rescan before writing.");
    const laterGate = adapter.humanGate(document);
    if (laterGate?.kind === "captcha") await restrict();
    if (laterGate) throw new Error("A human gate appeared. Complete it yourself, then rescan.");
    if (mode.mode !== "fill") throw new Error("Application is restricted to answer sheet only.");
  }

  async function observe(adapter) {
    if (adapter?.requiresApplicationMode !== true) return null;
    if (!context || context.targetUrl !== location.href) throw new Error("Application page changed. Rescan before reviewing mode.");
    if (captchaLatches.has(context.applicationId)) return {schema_version: 1, application_id: context.applicationId,
      mode: "answer_sheet_only", reason: "captcha"};
    if (adapter.humanGate(document)?.kind === "captcha") {
      captchaLatches.add(context.applicationId);
      await broker("restrict", "captcha");
      return {schema_version: 1, application_id: context.applicationId, mode: "answer_sheet_only", reason: "captcha"};
    }
    const mode = await broker("read");
    if (!context || context.targetUrl !== location.href) throw new Error("Application page changed during mode review.");
    if (adapter.humanGate(document)?.kind === "captcha") {
      captchaLatches.add(context.applicationId);
      await broker("restrict", "captcha");
      return {schema_version: 1, application_id: context.applicationId, mode: "answer_sheet_only", reason: "captcha"};
    }
    return adapter.mode === "fill" ? mode : {...mode, mode: "answer_sheet_only",
      reason: mode.mode === "answer_sheet_only" ? mode.reason : "adapter_answer_sheet_only"};
  }

  globalThis.PortalApplicationMode = {bind, check, observe};
})();
