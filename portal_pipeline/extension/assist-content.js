/* Author: Yazad Madan. User-selected per-field assist in the extension's isolated world. */
(() => {
  // Config
  const FIELD_SELECTOR = 'input:not([type]),input[type="text"],input[type="email"],input[type="tel"],input[type="url"],input[type="search"],textarea,select,input[type="radio"],input[type="checkbox"],[role="checkbox"],[role="combobox"],button[aria-haspopup="listbox"]';
  const CAPTURE_SELECTOR = 'input:not([type="hidden"]):not([type="button"]):not([type="submit"]):not([type="reset"]):not([type="image"]),textarea,select,[role="checkbox"],[role="combobox"],[role="radiogroup"],button[aria-haspopup="listbox"]';
  // Oracle-style pills: a radiogroup of buttons with role=radio and aria-checked, no native inputs.
  // Workday-style custom dropdown: a button that opens a listbox; its chosen option shows as the button text.
  const menuButton = element => element?.tagName === 'BUTTON' && element.getAttribute('aria-haspopup') === 'listbox';
  const PILL_OPTION = '[role="radio"]:not(input)';
  const pillGroup = element => element?.getAttribute?.('role') === 'radiogroup' && !!element.querySelector(PILL_OPTION);
  const GROUP_SELECTOR = 'fieldset,[role="radiogroup"],[role="group"],[data-automation-id="formField"],.form-field,.field';
  const FORBIDDEN = /\b(password|passcode|captcha|verification code|one.?time|otp|ssn|social security|credit card|bank account|routing number)\b/i;
  const MAX_LEARN_PAIRS = 80;
  const MAX_PAGE_FIELDS = 200;
  const MAX_LEARN_LABEL = 300;
  const MAX_LEARN_ANSWER = 2000;
  const ACTION = /^(?:next|continue|submit|apply)(?:\b|$)/i;
  const DEBOUNCE_MS = 180;
  const SETTLE_MS = 180;
  const CHECKBOX_FAILURE = 'checkbox not retained';
  const STATUS_HIDE_MS = 3000;
  const RELOADED = 'Extension was reloaded. Refresh this page.';
  const CORRECTION_DEBOUNCE_MS = 180;
  const POPUP_TIMEOUT_MS = 1800;
  const MISS_LABEL_LIMIT = 300;
  const MISS_OPTION_LIMIT = 40;
  const MISS_OPTION_TEXT_LIMIT = 120;
  const MAX_JOB_TITLE = 300;
  const MAX_PAGE_SNIPPET = 1500;
  const JOB_HEADING_SELECTOR = '[data-automation-id="jobPostingHeader"],h1,[role="heading"][aria-level="1"]';
  const HEADING_VALUES = 'input,textarea,select,output,[contenteditable],[role="textbox"],[role="combobox"],[role="spinbutton"],[role="listbox"]';
  const PLACEHOLDER = /^(?:select(?:\s+(?:one|an? option))?|choose(?:\s+.*)?|please select(?:\s+.*)?|[-*\s]*)$/i;
  const isPlaceholder = value => PLACEHOLDER.test(value) || /^makeaselection$/i.test(String(value).replace(/[\s*-]/g, ''));
  const DATE_SEGMENT_LABEL = /^[\s*]*(?:month|day|year|mm|dd|yyyy)[\s*:]*$/i;
  const PLAIN_CONTAINER = 'tr,.iCIMS_TableRow,.form-group,div';
  const QUESTION_NODE = 'label,.question-label,.iCIMS_LabelText,.iCIMS_QuestionText,[data-automation-id="formLabel"]';
  const LABEL_EXCLUSIONS = 'option,input,textarea,select,button,[role="combobox"],[role="listbox"],.help,.help-text,.help-block,.hint,[role="tooltip"],[aria-hidden="true"],[hidden]';
  const LABEL_DEPTH = 5;
  const LABEL_TEXT_LIMIT = 2000;
  const TYPED_SIGNATURE = /\b(?:by\s+)?typing\s+your\s+(?:full|legal)\s+name\b|^[*\s]*(?:typed |electronic |e-?)?signature\b/i;
  const TEXT_TYPES = ['text', 'tel', 'number'];
  const SEGMENT = /\b(?:month|day|year|mm|dd|yyyy)\b/i;
  const STYLE = ':host{all:initial!important;position:absolute!important;z-index:2147483647!important;font:12px Arial,sans-serif!important}button{font:inherit;border:1px solid #777;border-radius:4px;background:#fff;color:#222;padding:2px 6px;cursor:pointer}button:disabled{opacity:.6;cursor:wait}[hidden]{display:none!important}span{font:inherit;color:#333;margin-left:4px}a{font:inherit;color:#165bb4;cursor:pointer;margin-left:4px;text-decoration:underline}';
  const DOCK_STYLE = ':host{all:initial!important;position:fixed!important;left:0!important;top:40%!important;z-index:2147483647!important;font:12px Arial,sans-serif!important;max-height:58vh;overflow:auto}button{display:block;width:84px;font:inherit;border:1px solid #777;border-left:0;border-radius:0 6px 6px 0;background:#fff;color:#222;padding:8px 6px;cursor:pointer;margin-bottom:4px}button:disabled{opacity:.6;cursor:wait}[hidden]{display:none!important}div{background:#fff;border:1px solid #777;border-left:0;padding:4px 6px;max-width:320px;color:#333;white-space:pre-wrap;overflow-wrap:anywhere}';
  if (globalThis.PortalAssistLoaded) return;
  globalThis.PortalAssistLoaded = true;
  const controls = new Map();
  const fieldStates = new WeakMap();
  let pending = false;
  let timer;
  let focused = null;
  let dock = null;
  const text = element => element?.innerText?.replace(/\s+/g, ' ').trim() || '';
  const menuAnswer = element => {
    const shown = text(element);
    return isPlaceholder(shown) || /^select one required$/i.test(shown) ? '' : shown;
  };
  const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim().toLocaleLowerCase();
  const visible = element => !!element?.isConnected && !element.closest('[hidden],[inert],[aria-hidden="true"]')
    && element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
  const automation = () => globalThis.PortalAutomationFilling === true;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const checkbox = element => element.type === 'checkbox' || element.getAttribute?.('role') === 'checkbox';
  const checked = element => element.type === 'checkbox' ? element.checked : element.getAttribute('aria-checked') === 'true';

  function checkboxTarget(element) {
    if (visible(element)) return element;
    const role = element.closest('[role="checkbox"]');
    const parent = element.parentElement;
    const candidates = [...(element.labels || []), role,
      ...(parent?.querySelectorAll?.('input').length === 1 ? [parent] : [])];
    return candidates.find(node => node?.getClientRects && visible(node)) || element;
  }

  const fieldVisible = element => visible(element) || (checkbox(element) && visible(checkboxTarget(element)));
  const duplicateCheckbox = element => element.type !== 'checkbox' && checkbox(element)
    && !!element.querySelector?.('input[type="checkbox"]');
  const checkboxRetained = (element, wanted) => element.isConnected && checked(element) === wanted && !element.indeterminate
    && [element, checkboxTarget(element)].every(node => {
      const aria = node.getAttribute('aria-checked');
      return aria === null || aria === String(wanted);
    });

  async function fillCheckbox(element, wanted, mayWrite) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      if (element.type === 'checkbox' && element.indeterminate) element.indeterminate = false;
      if (checkboxRetained(element, wanted)) return;
      // Never toggle an accepted value to repair ARIA or framework state.
      if (checked(element) === wanted || !mayWrite()) break;
      const target = checkboxTarget(element);
      if (element.disabled || element.getAttribute('aria-disabled') === 'true' || target.getAttribute('aria-disabled') === 'true') break;
      target.focus?.();
      if (!mayWrite() || checked(element) === wanted) break;
      safeClick(target, element.type !== 'checkbox' || target !== element);
      await wait(SETTLE_MS);
    }
    if (element.type === 'checkbox' && element.indeterminate) element.indeterminate = false;
    if (!checkboxRetained(element, wanted)) throw new Error(CHECKBOX_FAILURE);
  }

  function ariaLabel(element) {
    const ids = (element.getAttribute('aria-labelledby') || '').trim().split(/\s+/);
    return ids.map(id => text(document.getElementById(id))).filter(Boolean).join(' ')
      || element.getAttribute('aria-label')?.trim() || '';
  }

  function ownLabel(element) {
    if (menuButton(element)) {  // Workday names the button 'Select One Required'; the question is its label or the field container's label
      const linked = [...(element.labels || [])].map(text).filter(Boolean).join(' ');
      if (linked) return linked;
      const named = ariaLabel(element);
      return /^select one( required)?$/i.test(named) ? '' : named;
    }
    return ariaLabel(element) || [...(element.labels || [])].map(text).filter(Boolean).join(' ');
  }

  function groupLabel(element) {
    const group = element.closest(GROUP_SELECTOR);
    if (!group) return '';
    const explicit = ariaLabel(group) || text(group.querySelector(':scope > legend'));
    if (explicit) return explicit;
    const label = group.querySelector(':scope > [data-automation-id="formLabel"],:scope > .question-label,:scope > label');
    if (label?.control || label?.querySelector('input,textarea,select')) return '';
    return text(label);
  }

  function labelFor(element) {
    if (element.type === 'radio') return groupLabel(element);
    const own = ownLabel(element);
    const group = checkbox(element) ? groupLabel(element) : '';
    if (own && group && normalize(own) !== normalize(group)) return `${group}: ${own}`;
    if (own && !DATE_SEGMENT_LABEL.test(own)) return own;
    const container = element.closest('[data-automation-id="formField"],[data-automation-id^="formField-"],.form-field,.field');
    return text(container?.querySelector('label,[data-automation-id="formLabel"]')) || groupLabel(element) || plainLabel(element);
  }

  function plainLabel(element) {
    const described = (element.getAttribute('aria-describedby') || '').split(/\s+/);
    const labelText = node => {
      if (!node) return '';
      if (node.nodeType === Node.TEXT_NODE) {
        const value = node.textContent.replace(/\s+/g, ' ').trim();
        return value.length <= LABEL_TEXT_LIMIT ? value : '';
      }
      if (!visible(node) || node.matches(LABEL_EXCLUSIONS) || described.includes(node.id)
        || node.querySelector(CAPTURE_SELECTOR) || (node.control && node.control !== element)) return '';
      const copy = node.cloneNode(true);
      for (const child of copy.querySelectorAll(LABEL_EXCLUSIONS)) child.remove();
      for (const child of copy.querySelectorAll('[id]')) if (described.includes(child.id)) child.remove();
      const value = (copy.textContent || '').replace(/\s+/g, ' ').trim();
      return value.length <= LABEL_TEXT_LIMIT ? value : '';
    };
    let branch = element;
    for (let depth = 0; branch.parentElement && depth < LABEL_DEPTH; depth += 1) {
      const container = branch.parentElement;
      if (container.matches('body,html,form,main')) break;
      // Hidden backing controls and inner inputs of a combobox are not separate questions.
      const fields = [...container.querySelectorAll(CAPTURE_SELECTOR)].filter(node => fieldVisible(node) && !duplicateCheckbox(node)
        && !node.parentElement?.closest('[role="combobox"]'));
      if (fields.length !== 1 || fields[0] !== element) return '';
      if (container.matches(PLAIN_CONTAINER)) {
        const questions = [...container.querySelectorAll(QUESTION_NODE)].map(labelText).filter(Boolean);
        if (questions.length > 1) return '';
        if (questions.length === 1) return questions[0];
        for (let sibling = branch.previousSibling, count = 0; sibling && count < LABEL_DEPTH; sibling = sibling.previousSibling, count += 1) {
          const value = labelText(sibling);
          if (value) return value;
        }
      }
      branch = container;
    }
    return '';
  }

  function members(element) {
    if (element.type !== 'radio') return [element];
    const scope = element.closest(GROUP_SELECTOR) || element.form || document;
    return [...scope.querySelectorAll('input[type="radio"]')].filter(candidate =>
      candidate.form === element.form && (element.name ? candidate.name === element.name : candidate === element));
  }

  const descriptor = node => [ariaLabel(node), node.placeholder, node.name, node.id].join(' ');

  // Split date or similar segments (month/day/year inputs) are one field, not three.
  function groupOf(element, capture = false) {
    const textInput = node => node.tagName === 'INPUT' && TEXT_TYPES.includes(node.type) && node.getAttribute('role') !== 'combobox';
    if (!textInput(element)) return [element];
    const container = element.closest(GROUP_SELECTOR);
    if (!container) return [element];
    const parts = [...container.querySelectorAll(capture ? CAPTURE_SELECTOR : FIELD_SELECTOR)].filter(node =>
      textInput(node) && visible(node) && (capture || (!node.disabled && !node.readOnly)));
    return parts.length > 1 && parts.includes(element) && parts.every(node => SEGMENT.test(descriptor(node))) ? parts : [element];
  }

  function fillGroup(parts, result) {
    const numbers = result.answer.match(/\d+/g) || [];
    if (numbers.length !== parts.length || parts.length > 3) return null;
    const key = node => /month|\bmm\b/i.test(descriptor(node)) ? 0 : /day|\bdd\b/i.test(descriptor(node)) ? 1 : /year|yyyy/i.test(descriptor(node)) ? 2 : -1;
    const keys = parts.map(key);
    const byKey = keys.every(index => index >= 0) && new Set(keys).size === parts.length;
    const values = parts.map((node, position) => numbers[byKey ? keys[position] : position]);
    parts.forEach((node, position) => nativeSet(node, 'value', values[position]));
    return {kind: 'group', parts, values};
  }

  function popup(element) {
    const ids = `${element.getAttribute('aria-controls') || ''} ${element.getAttribute('aria-owns') || ''}`.trim().split(/\s+/);
    const lists = ids.map(id => document.getElementById(id)).filter(node =>
      visible(node) && (node.getAttribute('role') === 'listbox' || node.querySelector('[role="option"]')));
    if (lists.length === 1) return lists[0];
    if (!menuButton(element)) return null;
    const open = [...document.querySelectorAll('[role="listbox"]')].filter(node => visible(node) && node.querySelector('[role="option"]'));
    return open.length === 1 ? open[0] : null;
  }

  function choices(element) {
    if (element.tagName === 'SELECT') return [...element.options].filter(option => !option.disabled && !option.hidden
      && !option.parentElement.disabled && option.value !== '' && !isPlaceholder(option.text)).map(option => ({node: option, text: option.text}));
    if (element.type === 'radio') return members(element).filter(node => visible(node) && !node.disabled)
      .map(node => ({node, text: ownLabel(node)})).filter(option => option.text);
    if (pillGroup(element)) return [...element.querySelectorAll(PILL_OPTION)].filter(node => visible(node))
      .map(node => ({node, text: text(node)})).filter(option => option.text);
    if (checkbox(element)) return [{node: element, text: 'Yes', checked: true}, {node: element, text: 'No', checked: false}];
    if (element.getAttribute('role') === 'combobox' || menuButton(element)) return [...(popup(element)?.querySelectorAll('[role="option"]') || [])]
      .filter(node => visible(node) && node.getAttribute('aria-disabled') !== 'true' && !isPlaceholder(text(node))).map(node => ({node, text: text(node)}));
    return [];
  }

  function match(options, candidates, mappedOptions = []) {
    for (const mapped of mappedOptions) {
      if (typeof mapped !== 'string' || !normalize(mapped)) continue;
      const exact = options.filter(option => normalize(option.text) === normalize(mapped));
      if (exact.length === 1) return exact[0];
      if (exact.length > 1) return null;
    }
    for (const candidate of candidates) {
      const wanted = normalize(candidate);
      if (!wanted) continue;
      const exact = options.filter(option => normalize(option.text) === wanted);
      if (exact.length === 1) return exact[0];
      if (exact.length > 1) return null;
      // Whole words prevent No matching None or Yes matching Yesterday.
      const escaped = wanted.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const pattern = new RegExp(`(?:^|\\W)${escaped}(?:$|\\W)`, 'i');
      const near = options.filter(option => pattern.test(normalize(option.text)));
      if (near.length === 1) return near[0];
    }
    return null;
  }

  // Workday multiselect pickers hold their value as pills; the search input itself stays empty.
  function pills(element) {
    const box = element.closest?.('[data-automation-id="multiselectInputContainer"]');
    const scope = box && box.querySelector('[data-automation-id="selectedItem"]') ? box : box?.parentElement;
    return scope ? [...scope.querySelectorAll('[data-automation-id="selectedItem"] [data-automation-id="promptOption"]')]
      .map(node => node.getAttribute('data-automation-label') || text(node)).filter(Boolean) : [];
  }

  function nonempty(element) {
    if (menuButton(element)) return !!menuAnswer(element);
    if (pills(element).length) return true;
    if (element.type === 'radio') return members(element).some(node => node.checked);
    if (checkbox(element)) return checked(element) && checkboxRetained(element, true);
    if (element.tagName === 'SELECT') return [...element.selectedOptions].some(option => option.value !== '' && !isPlaceholder(option.text));
    if (element.getAttribute('role') === 'combobox') {
      const value = 'value' in element ? element.value : text(element);
      return !!value.trim() && !isPlaceholder(value.trim());
    }
    return !!element.value?.trim();
  }

  function currentAnswer(element, capture = false) {
    if (pillGroup(element)) return text(element.querySelector(`${PILL_OPTION}[aria-checked="true"]`));
    if (['password', 'file'].includes(element.type)) return '';
    if (element.type === 'radio') {
      const checked = members(element).find(node => node.checked);
      return checked ? ownLabel(checked) : '';
    }
    if (checkbox(element)) return element.indeterminate || element.getAttribute('aria-checked') === 'mixed' ? '' : checked(element) ? 'Yes' : 'No';
    if (element.tagName === 'SELECT') return [...element.selectedOptions].filter(option =>
      option.value !== '' && !isPlaceholder(option.text)).map(option => option.text).join('; ');
    if (menuButton(element)) return menuAnswer(element);
    const chosen = pills(element);
    if (chosen.length) return chosen.join('; ');
    const parts = groupOf(element, capture);
    if (parts.length > 1) return parts.every(node => node.value.trim()) ? parts.map(node => node.value.trim()).join('/') : '';
    const value = String('value' in element ? element.value : text(element)).trim();
    return element.getAttribute('role') === 'combobox' && isPlaceholder(value) ? '' : value;
  }

  function captureElements() {
    const seen = new Set();
    return [...document.querySelectorAll(CAPTURE_SELECTOR)].filter(element => {
      if (!fieldVisible(element) || duplicateCheckbox(element) || element.closest('[data-portal-panel]') || element.parentElement?.closest('[role="combobox"]')) return false;
      if (element.getAttribute('role') === 'radiogroup' && !pillGroup(element)) return false;
      const parts = element.type === 'radio' ? members(element) : groupOf(element, true);
      if (parts.some(node => seen.has(node))) return false;
      parts.forEach(node => seen.add(node));
      return true;
    });
  }

  // When nothing saves, say why: how many controls exist, are visible, have a label, and whether this is an iframe.
  function saveDiagnosis(rows) {
    const all = [...document.querySelectorAll(CAPTURE_SELECTOR)];
    const shown = all.filter(visible);
    const named = shown.filter(element => labelFor(element) || ownLabel(element)).length;
    const answered = rows.length;
    const bare = shown.filter(element => !labelFor(element) && !ownLabel(element))[0];
    return `[${window === window.top ? 'top page' : 'iframe'}: ${all.length} controls, ${shown.length} visible, ${named} labelled, ${answered} answered${bare ? `, unlabelled e.g. ${bare.tagName.toLowerCase()}#${bare.id || bare.name || '?'}` : ''}]
`;
  }

  function learnRows(capture = false) {
    const rows = [];
    for (const element of capture ? captureElements() : controls.keys()) {
      const label = labelFor(element) || (capture ? ownLabel(element) : '');
      if (capture && ['password', 'file'].includes(element.type)) {
        rows.push({element, label, type: element.type});
        continue;
      }
      const answer = currentAnswer(element, capture);
      const state = fieldStates.get(element) || {initial: answer};
      const options = choices(element).map(option => option.text);
      if (!visible(element) || !label || !answer) continue;
      if (!capture && (element.disabled || element.readOnly || FORBIDDEN.test(label)
        || /\d+\s*:/.test(label)  // indexed rows of a repeating section (Work Experience 2: ...) are not reusable answers
        || label.length > MAX_LEARN_LABEL || answer.length > MAX_LEARN_ANSWER)) continue;
      // Values already on the page count too: Simplify and the last application are trusted, and the review step still gates saving.
      const corrected = state.corrected === answer;
      const typed = state.user === answer && answer !== state.initial;
      const source = corrected ? 'corrected' : state.filled === answer ? 'filled' : typed ? 'typed' : 'prefilled';
      rows.push({element, label, answer, options, corrected, source,
        manual: state.filled !== answer && (typed || corrected),
        type: element.getAttribute('role') === 'combobox' || menuButton(element) ? 'combobox' : pillGroup(element) ? 'radio' : element.type || element.tagName.toLowerCase()});
    }
    return rows.sort((a, b) => Number(b.corrected) - Number(a.corrected));
  }

  function correctionEdit(element, state, capture = false) {
    const answer = currentAnswer(element, capture);
    clearTimeout(state.correctionTimer);
    if (state.assistValue && answer !== state.assistValue) {
      state.corrected = answer;
      state.correctionPending = !!state.fillContext && answer !== state.reportedUser;
    } else {
      state.corrected = null;
      state.correctionPending = false;
    }
    state.user = answer;
    state.filled = null;
  }

  function correctionBlur(element, state) {
    clearTimeout(state.correctionTimer);
    if (state.user === state.assistValue && currentAnswer(element) === state.user) state.reportedUser = state.assistValue;
    if (!state.correctionPending || !state.fillContext) return;
    const context = state.fillContext;
    const answer = state.user;
    state.correctionTimer = setTimeout(() => {
      if (automation() || !element.isConnected || !visible(element) || element.disabled || element.readOnly
        || state.fillContext !== context || !state.correctionPending || state.user !== answer
        || currentAnswer(element) !== answer || labelFor(element) !== context.label
        || location.href !== context.url || companyHint() !== context.company_hint) return;
      const options = [...new Set([...context.options, ...choices(element).map(option => option.text)])];
      if (!answer || answer.length > MAX_LEARN_ANSWER || context.label.length > MAX_LEARN_LABEL
        || FORBIDDEN.test(context.label)) return;
      state.correctionPending = false;
      state.reportedUser = answer;
      void request('portal-assist-correction', {...context, options, user_value: answer}).catch(() => {});
    }, CORRECTION_DEBOUNCE_MS);
  }

  function nativeSet(element, property, value) {
    const prototype = element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : element.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, property)?.set;
    if (!setter) throw new Error('Unsupported field');
    setter.call(element, value);
    for (const type of ['input', 'change', 'blur']) element.dispatchEvent(new Event(type, {bubbles: true}));
  }

  function safeClick(element, pointer = false) {
    const button = element.closest('button');
    if (!visible(element) || element.closest('a[href],button[type="submit"],input[type="submit"],input[type="image"]')
      || (button?.form && button.type !== 'button')
      || (element.tagName === 'BUTTON' && element.form && element.type !== 'button')
      || ACTION.test(text(element))) throw new Error('Manual field');
    if (pointer) {
      for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
        const Constructor = type.startsWith('pointer') && typeof PointerEvent !== 'undefined' ? PointerEvent : MouseEvent;
        element.dispatchEvent(new Constructor(type, {bubbles: true, cancelable: true, composed: true, button: 0}));
      }
    }
    element.click();
  }

  // Workday tenant slugs that differ from the company name.
  const TENANT_NAMES = { ghr: 'Bank of America' };

  function companyHint() {
    const employer = document.querySelector('[data-automation-id="companyName"],[itemprop="hiringOrganization"] [itemprop="name"]');
    if (text(employer)) return text(employer).slice(0, 150);
    const host = location.hostname;
    if (/\.(?:myworkdayjobs|myworkdaysite)\.com$/i.test(host)) return TENANT_NAMES[host.split('.')[0].toLowerCase()] || host.split('.')[0];
    if (/\.fa\.[a-z0-9-]+\.oraclecloud\.com$/i.test(host)) return host.split('.')[0];
    // SuccessFactors hosts are shared (careerN.successfactors.com); the tenant is the company query parameter.
    if (/\.successfactors\.(?:com|eu)$/i.test(host)) return (new URLSearchParams(location.search).get('company') || '').slice(0, 150);
    if (host === 'jobs.lever.co' || /greenhouse\.io$/i.test(host)) return location.pathname.split('/').filter(Boolean)[0] || '';
    return '';
  }

  function request(type, body) {
    return new Promise((resolve, reject) => {
      // An extension reload orphans this script; sendMessage then throws instead of calling back.
      try {
        chrome.runtime.sendMessage({type, body}, response => {
          if (chrome.runtime.lastError) reject(new Error(/context invalidated/i.test(chrome.runtime.lastError.message) ? RELOADED : chrome.runtime.lastError.message));
          else if (!response?.ok) reject(new Error(response?.error || 'Assist unavailable'));
          else resolve(response.value);
        });
      } catch (_) { reject(new Error(RELOADED)); }
    });
  }

  function reportMiss(element, label) {
    try {
      const dropdown = element.tagName === 'SELECT' || element.getAttribute('role') === 'combobox' || menuButton(element);
      void request('portal-assist-miss', {label: label.replace(/\s+/g, ' ').trim().slice(0, MISS_LABEL_LIMIT),
        type: element.getAttribute('role') === 'combobox' || menuButton(element) ? 'combobox' : element.type || element.tagName.toLowerCase(),
        host: location.hostname, company_hint: companyHint(),
        options: dropdown ? choices(element).slice(0, MISS_OPTION_LIMIT).map(option => option.text.slice(0, MISS_OPTION_TEXT_LIMIT)) : []})
        .catch(() => {});
    } catch (_) { /* Logging must not change a fill outcome. */ }
  }

  function essayContext() {
    const heading = document.querySelector(JOB_HEADING_SELECTOR);
    if (!heading || heading.closest(HEADING_VALUES)) return {};
    const copy = heading.cloneNode(true);
    for (const node of copy.querySelectorAll(HEADING_VALUES)) node.remove();
    const snippet = (copy.textContent || '').replace(/\s+/g, ' ').trim().slice(0, MAX_PAGE_SNIPPET);
    return {job_title: snippet.slice(0, MAX_JOB_TITLE), page_snippet: snippet};
  }

  // Workday history rows share an id prefix like education-2--; the row index is the prefix's page order.
  const HISTORY_ROW = /^(education|certifications?)-\d+--/;
  const HISTORY_SECTIONS = {Education: 'education', Certifications: 'certification'};
  function rowContext(element) {
    const found = HISTORY_ROW.exec(element.id || '');
    if (!found) return {};
    const prefixes = [...new Set([...document.querySelectorAll(`[id^="${found[1]}-"]`)].map(node => HISTORY_ROW.exec(node.id)?.[0]).filter(Boolean))];
    return {row_group: found[1].replace(/s$/, ''), row_index: prefixes.indexOf(found[0])};
  }

  function rowCount(group) {
    return new Set([...document.querySelectorAll(`[id^="${group}-"],[id^="${group}s-"]`)].map(node => HISTORY_ROW.exec(node.id)?.[0]).filter(Boolean)).size;
  }

  // Click the section's Add button once per missing profile record; never touches Next or Submit.
  async function addHistoryRows() {
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')];
    if (!Object.keys(HISTORY_SECTIONS).some(text => headings.some(node => node.textContent.trim() === text))) return;
    const counts = await request('portal-assist-history', {label: 'history'});
    for (const [text, group] of Object.entries(HISTORY_SECTIONS)) {
      const heading = headings.find(node => node.textContent.trim() === text);
      if (!heading) continue;
      for (let guard = 0; guard < 6 && rowCount(group) < (counts[group] || 0); guard += 1) {
        let button = null;
        for (let node = heading.parentElement, depth = 0; node && depth < 8 && !button; node = node.parentElement, depth += 1) {
          const own = [...node.querySelectorAll('button[data-automation-id="add-button"]')];
          if (own.length === 1) button = own[0];
          else if (own.length > 1) break;
        }
        if (!button) break;
        const before = rowCount(group);
        safeClick(button);
        for (let waited = 0; waited < 3000 && rowCount(group) === before; waited += 100) await wait(100);
        if (rowCount(group) === before) break;
        await wait(SETTLE_MS);
      }
    }
  }

  async function fill(element, result, mayWrite) {
    if (!mayWrite()) return null;
    if (checkbox(element)) {
      const option = match(choices(element), result.candidates, result.mapped_options);
      if (!option) return null;
      await fillCheckbox(element, option.checked, mayWrite);
      return {kind: 'checkbox', node: element, value: option.checked};
    }
    if ((element.getAttribute('role') === 'combobox' || menuButton(element)) && element.tagName !== 'SELECT') {
      const matchChoices = () => {
        const options = choices(element);
        if (!menuButton(element) || globalThis.PortalClassifier?.classify(labelFor(element), '', 'contact') !== 'state') {
          return match(options, result.candidates, result.mapped_options);
        }
        for (const answer of [...(result.mapped_options || []), ...result.candidates]) {
          const found = PortalClassifier.matchOption(options.map(option => ({...option, label: option.text, value: option.text})), answer);
          if (found) return found;
        }
        return null;
      };
      if (!popup(element)) safeClick(element);
      const deadline = Date.now() + POPUP_TIMEOUT_MS;
      while (!matchChoices() && Date.now() < deadline) {
        await wait(60);
        if (!mayWrite()) return null;
      }
      const option = matchChoices();
      if (!option || !mayWrite()) return null;
      safeClick(option.node);
      for (const type of ['input', 'change', 'blur']) element.dispatchEvent(new Event(type, {bubbles: true}));
      return {kind: 'combobox', value: option.text};
    }
    if (element.tagName === 'SELECT' || element.type === 'radio') {
      const option = match(choices(element), result.candidates, result.mapped_options);
      if (!option) return null;
      if (element.tagName === 'SELECT') nativeSet(element, 'value', option.node.value);
      else nativeSet(option.node, 'checked', true);
      return {kind: element.type === 'radio' ? 'radio' : 'select',
        node: option.node, value: element.tagName === 'SELECT' ? option.node.value : true};
    }
    const parts = groupOf(element);
    if (parts.length > 1) return fillGroup(parts, result);
    if (element.maxLength >= 0 && result.answer.length > element.maxLength) throw new Error('Answer too long');
    nativeSet(element, 'value', result.answer);
    return {kind: 'text', value: result.answer};
  }

  function unchanged(element, written) {
    if (!element.isConnected || !written) return false;
    if (written.kind === 'group') return written.parts.every((node, index) => node.value === written.values[index]);
    if (written.kind === 'checkbox') return checkboxRetained(written.node, written.value);
    if (written.kind === 'radio') return written.node.checked === written.value;
    if (written.kind === 'combobox') return normalize('value' in element && !menuButton(element) ? element.value : text(element)) === normalize(written.value);
    return element.value === written.value;
  }

  function inject(element) {
    const host = document.createElement('span');
    const shadow = host.attachShadow({mode: 'closed'});
    const style = document.createElement('style');
    style.textContent = STYLE;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Fill';
    button.title = 'Fill this field. Shift-click to overwrite an existing value.';
    const badge = document.createElement('span');
    badge.setAttribute('role', 'status');
    const save = document.createElement('a');
    save.textContent = 'Save this answer';
    save.tabIndex = 0;
    save.setAttribute('role', 'button');
    save.hidden = true;
    shadow.append(style, button, badge, save);
    const anchor = element.type === 'radio' ? element.closest(GROUP_SELECTOR) || element : element;
    (document.body || document.documentElement).append(host);
    host.hidden = true;
    const entry = {host, button, badge, anchor, run: null};
    controls.set(element, entry);
    let draft = null;
    let written = null;
    const saveDraft = async event => {
      event.preventDefault();
      event.stopPropagation();
      if (!draft || pending || automation() || !unchanged(element, written) || labelFor(element) !== draft.label) return;
      save.hidden = true;
      try {
        await request('portal-assist-accept', {label: draft.label, answer: draft.answer,
          host: location.hostname, url: location.href, company_hint: companyHint()});
        badge.textContent = 'stored';
      } catch (error) { badge.textContent = 'save failed'; badge.title = error.message; save.hidden = false; }
    };
    save.addEventListener('click', saveDraft);
    save.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') saveDraft(event); });
    const attempt = async overwrite => {
      if (pending || automation()) return 'busy';
      const parts = groupOf(element);
      const label = labelFor(element);
      if (!overwrite && parts.some(nonempty)) return 'has value';
      if (!label || FORBIDDEN.test(label) || element.disabled || element.readOnly) return 'manual';
      const url = location.href;
      const mayWrite = () => !automation() && element.isConnected && fieldVisible(element) && !element.disabled && !element.readOnly
        && labelFor(element) === label && location.href === url && (overwrite || !parts.some(nonempty));
      pending = true;
      button.disabled = true;
      badge.textContent = 'looking up';
      save.hidden = true;
      try {
        const signature = element.tagName === 'INPUT' && element.type === 'text' && TYPED_SIGNATURE.test(label);
        const result = await request(signature ? 'portal-assist-full-name' : 'portal-assist-answer', {label, options: choices(element).map(option => option.text),
          type: element.getAttribute('role') === 'combobox' || menuButton(element) ? 'combobox' : element.type || element.tagName.toLowerCase(),
          host: location.hostname, url, company_hint: companyHint(), ...essayContext(), ...rowContext(element)});
        if (!mayWrite()) return 'field changed';
        if (result.status === 'blank') return 'left blank';  // optional field Yazad leaves empty on purpose
        if (!['stored', 'draft'].includes(result.status) || typeof result.answer !== 'string' || !Array.isArray(result.candidates)) {
          reportMiss(element, label);
          return 'no answer';
        }
        written = await fill(element, result, mayWrite);
        if (!written) {
          reportMiss(element, label);
          return 'no match';
        }
        await wait(SETTLE_MS);
        if (!unchanged(element, written)) {
          if (written.kind === 'checkbox') { reportMiss(element, label); return CHECKBOX_FAILURE; }
          return 'not retained';
        }
        const state = fieldStates.get(element);
        if (state) {
          clearTimeout(state.correctionTimer);
          state.filled = currentAnswer(element);
          state.assistValue = state.filled;
          state.reportedUser = state.filled;
          state.user = state.corrected = null;
          state.correctionPending = false;
          state.fillContext = {label, type: element.getAttribute('role') === 'combobox' || menuButton(element) ? 'combobox'
            : element.type || element.tagName.toLowerCase(), host: location.hostname, url,
            company_hint: companyHint(), options: choices(element).map(option => option.text), wrong_value: state.filled};
        }
        draft = result.status === 'draft' ? {label, answer: result.answer} : null;
        save.hidden = !draft;
        return result.status;
      } catch (error) {
        badge.title = error.message;
        if (error.message === CHECKBOX_FAILURE) { reportMiss(element, label); return CHECKBOX_FAILURE; }
        return 'unavailable';
      }
      finally { pending = false; button.disabled = false; }
    };
    entry.run = async overwrite => {
      const status = await attempt(overwrite);
      badge.textContent = status;
      return status;
    };
    button.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      await entry.run(event.shiftKey);
    });
  }

  // One page-level button fills only empty fields; it never overwrites and never clicks Next or Submit.
  function makeDock() {
    const host = document.createElement('div');
    const shadow = host.attachShadow({mode: 'closed'});
    const style = document.createElement('style');
    style.textContent = DOCK_STYLE;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Fill page';
    button.title = 'Fill every empty field on this page. Fields that already have a value are left alone.';
    const summary = document.createElement('div');
    summary.hidden = true;
    shadow.append(style, button, summary);
    const learn = document.createElement('button');
    learn.type = 'button';
    learn.textContent = 'Learn page';
    learn.title = 'Review current answers before saving them for this company.';
    const review = document.createElement('div');
    review.hidden = true;
    review.style.cssText = 'max-height:55vh;overflow-y:auto';  // long lists scroll inside the panel
    learn.hidden = true;  // Save page now opens this review itself
    shadow.append(learn, review);
    const savePage = document.createElement('button');
    savePage.type = 'button';
    savePage.textContent = 'Save page';
    savePage.title = 'Save every visible labelled answer locally, then review new or changed answers to learn for this company.';
    const savedSummary = document.createElement('div');
    savedSummary.hidden = true;
    shadow.append(savePage, savedSummary);
    (document.body || document.documentElement).append(host);
    // Status text hides itself after a few seconds; an open review with a Confirm button stays.
    const autoHide = (box, ms) => {
      let timer;
      new MutationObserver(() => {
        clearTimeout(timer);
        if (box.hidden || box.querySelector('button')) return;
        timer = setTimeout(() => { if (!box.querySelector('button')) box.hidden = true; }, ms);
      }).observe(box, {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden']});
    };
    // While a review is open the dock takes the full height so Confirm and the list fit on screen.
    new MutationObserver(() => {
      const open = !review.hidden && !!review.querySelector('button');
      host.style.setProperty('top', open ? '8px' : '40%', 'important');
      host.style.setProperty('max-height', open ? '75vh' : '58vh', 'important');
    }).observe(review, {childList: true, subtree: true, attributes: true, attributeFilter: ['hidden']});
    autoHide(savedSummary, STATUS_HIDE_MS);
    autoHide(review, STATUS_HIDE_MS);
    autoHide(summary, STATUS_HIDE_MS * 2);
    savePage.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      if (pending || automation()) return;
      scan();
      const rows = learnRows(true);
      savedSummary.hidden = false;
      if (rows.length > MAX_LEARN_PAIRS) {
        savedSummary.textContent = 'Save failed: more than 80 fields. Save a smaller page.';
        return;
      }
      pending = true;
      savePage.disabled = true;
      let captured = false;
      try {
        const pairs = rows.map(({label, answer, source, type, options}) => ({label, answer, source, type, options}));
        const result = await request('portal-assist-dump', {pairs, company_hint: companyHint()});
        if (!['saved', 'excluded_by_type', 'duplicate', 'flagged_sensitive'].every(key => Number.isSafeInteger(result?.[key]) && result[key] >= 0))
          throw new Error('Invalid save counts');
        savedSummary.textContent = `${result.saved ? '' : saveDiagnosis(rows)}saved ${result.saved}, skipped ${result.excluded_by_type} blocked by type (password/file inputs are not answers), duplicate ${result.duplicate}, sensitive ${result.flagged_sensitive}`;
        captured = true;
      } catch (error) { savedSummary.textContent = error.message === RELOADED ? RELOADED : 'Save failed. Check the local helper and request size (64 KB).'; }
      finally { pending = false; savePage.disabled = false; }
      // One button: capture everything above, then open the reviewed Learn list for new or changed answers.
      if (captured && !learn.disabled) learn.click();
    });
    learn.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      if (pending || automation()) return;
      scan();
      review.replaceChildren();
      review.hidden = false;
      const rows = learnRows();
      if (!rows.length || rows.length > MAX_LEARN_PAIRS) {
        review.textContent = rows.length ? 'More than 80 answers. Review a smaller page.' : 'No touched answers to learn.';
        return;
      }
      const url = location.href;
      const company = companyHint();
      const context = {host: location.hostname, url, company_hint: company};
      const pairs = rows.map(({label, answer, options, type, manual, source}) => ({label, answer, options, type, manual, source}));
      pending = true;
      learn.disabled = true;
      try {
        const result = await request('portal-assist-learn', {...context, pairs, dry_run: true});
        if (automation() || location.href !== url || companyHint() !== company) return;
        if (!Array.isArray(result.results) || result.results.length !== rows.length) throw new Error('Invalid learning review');
        const selected = [];
        let known = 0;
        result.results.forEach((item, index) => {
          const row = rows[index];
          if (item.label !== row.label) throw new Error('Learning question changed');
          if (item.status === 'same' && typeof item.similar_to !== 'string') { known += 1; return; }  // already stored, nothing to review
          if (item.status === 'skipped') return;
          if (!['new', 'same', 'changed', 'dropdown'].includes(item.status) || item.answer !== row.answer) throw new Error('Invalid learning answer');
          const mapping = item.status === 'dropdown';
          if (mapping && (typeof item.mapping_answer !== 'string' || !row.manual)) throw new Error('Invalid dropdown review');
          const line = document.createElement('div');
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.checked = true;
          const label = document.createElement('label');
          const description = mapping ? `dropdown: ${item.mapping_answer} = ${row.answer}\nVendor: ${item.vendor}${item.previous_option && item.previous_option !== row.answer ? `\nPrevious option: ${item.previous_option}` : ''}`
            : `${row.answer}\nCompany: ${result.scope}${row.corrected ? '\ncorrected' : ''}\nSource: ${row.source}`;
          label.append(checkbox, document.createTextNode(`${row.label}\n${description}${item.status === 'changed' ? '\nchanged' : ''}`));
          line.append(label);
          let aliasCheckbox;
          if (typeof item.similar_to === 'string' && ['company', 'global'].includes(item.similar_scope)) {
            const similar = document.createElement('div');
            similar.textContent = `similar to: ${item.similar_to}${item.similar_scope === 'global' ? ' (global)' : ''}`;
            aliasCheckbox = document.createElement('input');
            aliasCheckbox.type = 'checkbox';
            aliasCheckbox.checked = false;
            const aliasLabel = document.createElement('label');
            aliasLabel.append(aliasCheckbox, document.createTextNode('also use this answer for the similar question wording'));
            line.append(similar, aliasLabel);
          }
          review.append(line);
          selected.push({row, checkbox, aliasCheckbox, pair: {...pairs[index], ...(mapping
            ? {mapping_answer: item.mapping_answer, previous_option: item.previous_option}
            : {previous_answer: item.previous_answer}),
            ...(aliasCheckbox ? {similar_to: item.similar_to, similar_scope: item.similar_scope} : {})}});
        });
        if (!selected.length) { review.textContent = known ? `Nothing new to learn (${known} already stored).` : 'No eligible answers to learn.'; return; }
        const confirm = document.createElement('button');
        confirm.type = 'button';
        confirm.textContent = 'Confirm';
        confirm.style.cssText = 'position:sticky;bottom:0;width:100%;font-weight:bold';  // stays visible below a long list
        review.append(confirm);
        confirm.addEventListener('click', async event => {
          event.preventDefault();
          event.stopPropagation();
          if (pending || automation()) return;
          const ticked = selected.filter(item => item.checkbox.checked);
          const current = learnRows();
          if (location.href !== url || companyHint() !== company || ticked.some(({row}) =>
            !current.some(item => item.element === row.element && item.label === row.label && item.answer === row.answer
              && item.manual === row.manual && JSON.stringify(item.options) === JSON.stringify(row.options)))) {
            review.textContent = 'Page answers changed. Click Learn page again.';
            return;
          }
          if (!ticked.length) { review.textContent = 'No answers selected.'; return; }
          pending = true;
          confirm.disabled = true;
          try {
            const saved = await request('portal-assist-learn', {...context, dry_run: false,
              pairs: ticked.map(item => ({...item.pair, use_alias: item.aliasCheckbox?.checked === true}))});
            const count = saved.results.filter(item => item.stored).length;
            review.textContent = `Stored ${count} answers or mappings.${count < ticked.length ? ' KB or mapping changed. Click Learn page again.' : ''}`;
          } catch (error) { review.textContent = `Learn failed: ${error.message}`; }
          finally { pending = false; confirm.disabled = false; }
        });
      } catch (error) { review.textContent = `Learn failed: ${error.message}`; }
      finally { pending = false; learn.disabled = false; }
    });
    button.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      if (pending || automation()) return;
      const order = ([a], [b]) => typeof a.compareDocumentPosition === 'function' ? (a.compareDocumentPosition(b) & 4 ? -1 : 1) : 0;
      const name = element => labelFor(element) || ariaLabel(element) || element.placeholder || element.name || element.id || element.type || 'unnamed field';
      const keyOf = element => `${normalize(labelFor(element) || name(element))}|${element.name || element.id || ''}`;
      const attempted = new Set();
      let filled = 0;
      let left = 0;
      let blank = 0;
      const misses = [];
      button.disabled = true;
      if (/myworkday/.test(location.hostname)) { try { await addHistoryRows(); } catch (_) { /* rows stay as they are */ } }
      // Sites re-render fields after an earlier answer (country, device type), so the next field is looked up fresh each time.
      for (let guard = 0; guard < MAX_PAGE_FIELDS; guard += 1) {
        scan();
        const next = [...controls].filter(([element]) => element.isConnected && fieldVisible(element) && !attempted.has(keyOf(element))).sort(order)[0];
        if (!next) break;
        const key = keyOf(next[0]);
        attempted.add(key);
        let [element, entry] = next;
        let label = name(element);
        let status = await entry.run(false);
        if (status === 'not retained') {
          await wait(SETTLE_MS * 3);
          scan();
          const fresh = [...controls].find(([node]) => node.isConnected && visible(node) && keyOf(node) === key);
          if (fresh) { [element, entry] = fresh; label = name(element); status = await entry.run(false); }
        }
        if (status === 'stored' || status === 'draft') filled += 1;
        else if (status === 'has value') left += 1;
        else if (status === 'left blank') blank += 1;
        else misses.push(`${label.slice(0, 60)}: ${status}`);
      }
      button.disabled = false;
      const shown = captureElements();
      const unlabelled = shown.filter(element => !labelFor(element)).length;
      summary.textContent = [`filled ${filled}, left alone ${left}${blank ? `, left blank ${blank} (optional)` : ""}`,
        `${shown.length} visible controls, ${unlabelled} without labels`,
        ...(misses.length ? ['not filled:', ...misses.map(line => `- ${line}`)] : [])].join('\n');
      summary.hidden = false;
    });
    return {host, button, summary};
  }

  // The per-field Fill appears beside the focused field only, outside its right edge.
  function place() {
    for (const [element, entry] of controls) {
      if (entry.host.hidden || typeof entry.anchor.getBoundingClientRect !== 'function') continue;
      const rect = entry.anchor.getBoundingClientRect();
      const left = rect.right + (globalThis.scrollX || 0) + 8;
      const top = rect.top + (globalThis.scrollY || 0) + Math.max(0, (rect.height - 24) / 2);
      if (entry.host.style) { entry.host.style.left = `${left}px`; entry.host.style.top = `${top}px`; }
    }
  }

  function scan() {
    for (const [element, entry] of controls) {
      if (!element.isConnected || !entry.host.isConnected) { entry.host.remove(); controls.delete(element); }
      else entry.host.hidden = !(focused === element && visible(element));
    }
    if (!dock) dock = makeDock();
    dock.host.hidden = automation() || captureElements().length === 0;
    place();
    if (automation()) return;
    for (const element of captureElements()) {
      if (!fieldStates.has(element)) fieldStates.set(element, {initial: currentAnswer(element, true)});
    }
    const radioSeen = new Set();
    for (const element of document.querySelectorAll(FIELD_SELECTOR)) {
      if (!fieldStates.has(element)) fieldStates.set(element, {initial: currentAnswer(element)});
      if (!fieldVisible(element) || duplicateCheckbox(element) || element.disabled || element.readOnly || element.closest('[data-portal-panel]')) continue;
      if (element.parentElement?.closest('[role="combobox"]')) continue;
      const parts = groupOf(element);
      if (parts[0] !== element) continue;
      if (element.type === 'radio') {
        const group = members(element);
        if (group.some(node => radioSeen.has(node))) continue;
        group.forEach(node => radioSeen.add(node));
        if (group.some(node => controls.has(node))) continue;
      }
      const label = labelFor(element);
      if (!controls.has(element) && label && !FORBIDDEN.test(label)) inject(element);
    }
  }
  const observer = new MutationObserver(records => {
    if (!records.some(record => record.target.nodeType === Node.ELEMENT_NODE
      && record.target !== dock?.host && ![...controls.values()].some(entry => entry.host === record.target))) return;
    clearTimeout(timer);
    timer = setTimeout(scan, DEBOUNCE_MS);
  });
  observer.observe(document.documentElement, {childList: true, subtree: true, attributes: true,
    attributeFilter: ['hidden', 'style', 'class', 'disabled', 'readonly', 'aria-hidden', 'aria-labelledby', 'aria-label']});
  document.addEventListener?.('focusin', event => {
    if (event.target === dock?.host || [...controls.values()].some(entry => entry.host === event.target)) return;
    focused = [...controls.keys()].find(element => groupOf(element).includes(event.target) || element.contains?.(event.target)) || null;
    if (event.isTrusted && focused) clearTimeout(fieldStates.get(focused)?.correctionTimer);
    scan();
  });
  for (const type of ['input', 'change']) document.addEventListener?.(type, event => {
    if (!event.isTrusted || automation()) return;
    for (const element of new Set([...controls.keys(), ...captureElements()])) {
      const capture = !controls.has(element);
      if (groupOf(element, capture).includes(event.target) || members(element).includes(event.target)) {
        const state = fieldStates.get(element);
        if (state) correctionEdit(element, state, capture);
      }
    }
  }, true);
  document.addEventListener?.('blur', event => {
    if (!event.isTrusted || automation()) return;
    for (const [element] of controls) {
      if (groupOf(element).includes(event.target) || members(element).includes(event.target)) {
        const state = fieldStates.get(element);
        if (state) correctionBlur(element, state);
      }
    }
  }, true);
  scan();
})();
