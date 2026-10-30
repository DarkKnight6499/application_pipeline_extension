/* Author: Yazad Madan. User-selected per-field assist in the extension's isolated world. */
(() => {
  // Config
  const FIELD_SELECTOR = 'input:not([type]),input[type="text"],input[type="email"],input[type="tel"],input[type="url"],input[type="search"],textarea,select,input[type="radio"],input[type="checkbox"],[role="combobox"]';
  const GROUP_SELECTOR = 'fieldset,[role="radiogroup"],[role="group"],[data-automation-id="formField"],.form-field,.field';
  const FORBIDDEN = /\b(password|passcode|captcha|verification code|ssn|social security|signature|sign|signed|initials|attest\w*|certify|declaration|I (confirm|affirm|declare)|truthful|accurate and complete|true and (correct|accurate))\b/i;
  const ACTION = /^(?:next|continue|submit|apply)(?:\b|$)/i;
  const DEBOUNCE_MS = 180;
  const SETTLE_MS = 180;
  const POPUP_TIMEOUT_MS = 1800;
  const PLACEHOLDER = /^(?:select(?:\s+(?:one|an? option))?|choose(?:\s+.*)?|please select(?:\s+.*)?|[-*\s]*)$/i;
  const TEXT_TYPES = ['text', 'tel', 'number'];
  const SEGMENT = /\b(?:month|day|year|mm|dd|yyyy)\b/i;
  const STYLE = ':host{all:initial!important;position:absolute!important;z-index:2147483647!important;font:12px Arial,sans-serif!important}button{font:inherit;border:1px solid #777;border-radius:4px;background:#fff;color:#222;padding:2px 6px;cursor:pointer}button:disabled{opacity:.6;cursor:wait}span{font:inherit;color:#333;margin-left:4px}a{font:inherit;color:#165bb4;cursor:pointer;margin-left:4px;text-decoration:underline}';
  const DOCK_STYLE = ':host{all:initial!important;position:fixed!important;right:0!important;top:40%!important;z-index:2147483647!important;font:12px Arial,sans-serif!important}button{font:inherit;border:1px solid #777;border-right:0;border-radius:6px 0 0 6px;background:#fff;color:#222;padding:8px 6px;cursor:pointer}button:disabled{opacity:.6;cursor:wait}div{background:#fff;border:1px solid #777;border-right:0;padding:4px 6px;max-width:240px;color:#333}';
  if (globalThis.PortalAssistLoaded) return;
  globalThis.PortalAssistLoaded = true;
  const controls = new Map();
  let pending = false;
  let timer;
  let focused = null;
  let dock = null;
  const text = element => element?.innerText?.replace(/\s+/g, ' ').trim() || '';
  const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim().toLocaleLowerCase();
  const visible = element => !!element?.isConnected && !element.closest('[hidden],[inert],[aria-hidden="true"]')
    && element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
  const automation = () => globalThis.PortalAutomationFilling === true;
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  function ariaLabel(element) {
    const ids = (element.getAttribute('aria-labelledby') || '').trim().split(/\s+/);
    return ids.map(id => text(document.getElementById(id))).filter(Boolean).join(' ')
      || element.getAttribute('aria-label')?.trim() || '';
  }

  function ownLabel(element) {
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
    const group = element.type === 'checkbox' ? groupLabel(element) : '';
    if (own && group && normalize(own) !== normalize(group)) return `${group}: ${own}`;
    if (own && !SEGMENT.test(own)) return own;
    const container = element.closest('[data-automation-id="formField"],.form-field,.field');
    return text(container?.querySelector('label,[data-automation-id="formLabel"]')) || groupLabel(element);
  }

  function members(element) {
    if (element.type !== 'radio') return [element];
    const scope = element.closest(GROUP_SELECTOR) || element.form || document;
    return [...scope.querySelectorAll('input[type="radio"]')].filter(candidate =>
      candidate.form === element.form && (element.name ? candidate.name === element.name : candidate === element));
  }

  const descriptor = node => [ariaLabel(node), node.placeholder, node.name, node.id].join(' ');

  // Split date or similar segments (month/day/year inputs) are one field, not three.
  function groupOf(element) {
    const textInput = node => node.tagName === 'INPUT' && TEXT_TYPES.includes(node.type) && node.getAttribute('role') !== 'combobox';
    if (!textInput(element)) return [element];
    const container = element.closest(GROUP_SELECTOR);
    if (!container) return [element];
    const parts = [...container.querySelectorAll(FIELD_SELECTOR)].filter(node => textInput(node) && visible(node) && !node.disabled && !node.readOnly);
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
    return lists.length === 1 ? lists[0] : null;
  }

  function choices(element) {
    if (element.tagName === 'SELECT') return [...element.options].filter(option => !option.disabled && !option.hidden
      && !option.parentElement.disabled && option.value !== '' && !PLACEHOLDER.test(option.text)).map(option => ({node: option, text: option.text}));
    if (element.type === 'radio') return members(element).filter(node => visible(node) && !node.disabled)
      .map(node => ({node, text: ownLabel(node)})).filter(option => option.text);
    if (element.type === 'checkbox') return [{node: element, text: 'Yes', checked: true}, {node: element, text: 'No', checked: false}];
    if (element.getAttribute('role') === 'combobox') return [...(popup(element)?.querySelectorAll('[role="option"]') || [])]
      .filter(node => visible(node) && node.getAttribute('aria-disabled') !== 'true').map(node => ({node, text: text(node)}));
    return [];
  }

  function match(options, candidates) {
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

  function nonempty(element) {
    if (element.type === 'radio') return members(element).some(node => node.checked);
    if (element.type === 'checkbox') return element.checked || element.indeterminate;
    if (element.tagName === 'SELECT') return [...element.selectedOptions].some(option => option.value !== '' && !PLACEHOLDER.test(option.text));
    if (element.getAttribute('role') === 'combobox') {
      const value = 'value' in element ? element.value : text(element);
      return !!value.trim() && !PLACEHOLDER.test(value.trim());
    }
    return !!element.value?.trim();
  }

  function nativeSet(element, property, value) {
    const prototype = element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : element.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, property)?.set;
    if (!setter) throw new Error('Unsupported field');
    setter.call(element, value);
    for (const type of ['input', 'change', 'blur']) element.dispatchEvent(new Event(type, {bubbles: true}));
  }

  function safeClick(element) {
    const button = element.closest('button');
    if (!visible(element) || element.closest('a[href],button[type="submit"],input[type="submit"],input[type="image"]')
      || (button?.form && button.type !== 'button')
      || (element.tagName === 'BUTTON' && element.form && element.type !== 'button')
      || ACTION.test(text(element))) throw new Error('Manual field');
    element.click();
  }

  function companyHint() {
    const employer = document.querySelector('[data-automation-id="companyName"],[itemprop="hiringOrganization"] [itemprop="name"]');
    if (text(employer)) return text(employer).slice(0, 150);
    const host = location.hostname;
    if (/\.(?:myworkdayjobs|myworkdaysite)\.com$/i.test(host)) return host.split('.')[0];
    if (host === 'jobs.lever.co' || /greenhouse\.io$/i.test(host)) return location.pathname.split('/').filter(Boolean)[0] || '';
    return '';
  }

  function request(type, body) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({type, body}, response => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else if (!response?.ok) reject(new Error(response?.error || 'Assist unavailable'));
        else resolve(response.value);
      });
    });
  }

  async function fill(element, result, mayWrite) {
    if (!mayWrite()) return null;
    if (element.getAttribute('role') === 'combobox' && element.tagName !== 'SELECT') {
      if (!popup(element)) safeClick(element);
      const deadline = Date.now() + POPUP_TIMEOUT_MS;
      while (!match(choices(element), result.candidates) && Date.now() < deadline) {
        await wait(60);
        if (!mayWrite()) return null;
      }
      const option = match(choices(element), result.candidates);
      if (!option || !mayWrite()) return null;
      safeClick(option.node);
      for (const type of ['input', 'change', 'blur']) element.dispatchEvent(new Event(type, {bubbles: true}));
      return {kind: 'combobox', value: option.text};
    }
    if (element.tagName === 'SELECT' || ['radio', 'checkbox'].includes(element.type)) {
      const option = match(choices(element), result.candidates);
      if (!option) return null;
      if (element.tagName === 'SELECT') nativeSet(element, 'value', option.node.value);
      else nativeSet(option.node, 'checked', element.type === 'radio' || option.checked);
      return {kind: element.type === 'radio' ? 'radio' : element.type === 'checkbox' ? 'checkbox' : 'select',
        node: option.node, value: element.tagName === 'SELECT' ? option.node.value : element.type === 'radio' || option.checked};
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
    if (written.kind === 'radio' || written.kind === 'checkbox') return written.node.checked === written.value;
    if (written.kind === 'combobox') return normalize('value' in element ? element.value : text(element)) === normalize(written.value);
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
        await request('portal-assist-accept', {label: draft.label, answer: draft.answer});
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
      const mayWrite = () => !automation() && element.isConnected && visible(element) && !element.disabled && !element.readOnly
        && labelFor(element) === label && location.href === url && (overwrite || !parts.some(nonempty));
      pending = true;
      button.disabled = true;
      badge.textContent = 'looking up';
      save.hidden = true;
      try {
        const result = await request('portal-assist-answer', {label, options: choices(element).map(option => option.text),
          type: element.getAttribute('role') === 'combobox' ? 'combobox' : element.type || element.tagName.toLowerCase(),
          host: location.hostname, url, company_hint: companyHint()});
        if (!mayWrite()) return 'field changed';
        if (!['stored', 'draft'].includes(result.status) || typeof result.answer !== 'string' || !Array.isArray(result.candidates)) return 'no answer';
        written = await fill(element, result, mayWrite);
        if (!written) return 'no match';
        await wait(SETTLE_MS);
        if (!unchanged(element, written)) return 'not retained';
        draft = result.status === 'draft' ? {label, answer: result.answer} : null;
        save.hidden = !draft;
        return result.status;
      } catch (error) { badge.title = error.message; return 'unavailable'; }
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
    (document.body || document.documentElement).append(host);
    button.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      if (pending || automation()) return;
      const order = ([a], [b]) => typeof a.compareDocumentPosition === 'function' ? (a.compareDocumentPosition(b) & 4 ? -1 : 1) : 0;
      const rows = [...controls].filter(([element]) => element.isConnected && visible(element)).sort(order);
      let filled = 0;
      let left = 0;
      const misses = [];
      button.disabled = true;
      for (const [element, entry] of rows) {
        const status = await entry.run(false);
        if (status === 'stored' || status === 'draft') filled += 1;
        else if (status === 'has value') left += 1;
        else misses.push(`${labelFor(element).slice(0, 60)}: ${status}`);
      }
      button.disabled = false;
      summary.textContent = `filled ${filled}, left alone ${left} (already filled)${misses.length ? '; not filled: ' + misses.join('; ') : ''}`;
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
    dock.host.hidden = controls.size === 0 || automation();
    place();
    if (automation()) return;
    const radioSeen = new Set();
    for (const element of document.querySelectorAll(FIELD_SELECTOR)) {
      if (!visible(element) || element.disabled || element.readOnly || element.closest('[data-portal-panel]')) continue;
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
    scan();
  });
  scan();
})();
