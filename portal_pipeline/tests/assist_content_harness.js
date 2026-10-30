/* Author: Yazad Madan. Synthetic DOM contracts without a browser or live CLI. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const APPLICATION_URL = 'https://example.myworkdayjobs.com/apply';
const SYNTHETIC_TOKEN = 'synthetic-assist-token';

class Input {
  constructor(type = 'text') {
    this.tagName = 'INPUT'; this.type = type; this.isConnected = true;
    this.disabled = false; this.readOnly = false; this.maxLength = -1;
    this._value = ''; this._checked = false; this.events = []; this.attributes = {};
    this.labels = []; this.name = ''; this.form = null;
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  get checked() { return this._checked; }
  set checked(value) { this._checked = value; }
  getAttribute(key) { return this.attributes[key] || null; }
  getClientRects() { return [{}]; }
  closest(selector) { return selector.startsWith('fieldset') ? this.group || null : null; }
  dispatchEvent(event) { this.events.push(event.type); }
  insertAdjacentElement(position, element) { element.isConnected = true; }
}
class Textarea extends Input {}
class Select extends Input {
  constructor(options) { super('select-one'); this.tagName = 'SELECT'; this.options = options; }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  get selectedOptions() { return this.options.filter(option => option.value === this.value); }
}

class AssistElement {
  constructor(tag, shadows) {
    this.tagName = tag.toUpperCase(); this.listeners = {}; this.hidden = false;
    this.attributes = {}; this.isConnected = true; this.shadows = shadows;
  }
  attachShadow(options) {
    assert.equal(options.mode, 'closed');
    const root = {children: [], append(...children) { this.children.push(...children); }};
    this.shadows.push(root);
    return root;
  }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  remove() { this.isConnected = false; }
}

async function contentChecks() {
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8');
  const marker = '  scan();\n})();';
  assert.equal(source.split(marker).length, 2);
  const instrumented = source.replace(marker,
    '  globalThis.testAssist = {match, nativeSet, nonempty, fill, labelFor, members, safeClick, scan};\n})();');
  const shadows = [];
  const requests = [];
  const document = {documentElement: {}, querySelectorAll: () => [], querySelector: () => null,
    getElementById: () => null, createElement: tag => new AssistElement(tag, shadows)};
  let storedResponse = {status: 'stored', answer: 'Example answer', candidates: ['Example answer']};
  let delayResponse = false;
  let pendingResponse;
  const runtime = {sendMessage(message, callback) {
    requests.push(message);
    if (delayResponse) pendingResponse = callback;
    else callback({ok: true, value: storedResponse});
  }};
  const context = vm.createContext({document, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    chrome: {runtime},
    Event, Node: {ELEMENT_NODE: 1}, HTMLInputElement: Input, HTMLTextAreaElement: Textarea,
    HTMLSelectElement: Select, getComputedStyle: () => ({visibility: 'visible'}),
    MutationObserver: class { observe() {} }});
  vm.runInContext(instrumented, context);
  const api = context.testAssist;
  const options = [{text: 'NO'}, {text: 'Yes, please'}, {text: 'Yesterday'}];
  assert.equal(api.match(options, ['No']).text, 'NO');
  assert.equal(api.match(options, ['Yes']).text, 'Yes, please');
  assert.equal(api.match([{text: 'None'}], ['No']), null);
  assert.equal(api.match([{text: 'Yes, A'}, {text: 'Yes, B'}], ['Yes']), null);
  assert.equal(api.match([{text: 'No'}, {text: 'Opt In'}], ['Yes', 'Opt In']).text, 'Opt In');

  const input = new Input();
  Object.defineProperty(input, 'value', {get() { return this._value; }, set() { throw Error('Framework setter'); }});
  const result = {answer: 'Example answer', candidates: ['Example answer']};
  await api.fill(input, result, () => true);
  assert.equal(input.value, 'Example answer');
  assert.deepEqual(input.events, ['input', 'change', 'blur']);
  assert.equal(api.nonempty(input), true);
  assert.equal(await api.fill(input, {...result, answer: 'Overwrite'}, () => false), null);
  assert.equal(input.value, 'Example answer');
  const limited = new Input(); limited.maxLength = 3;
  await assert.rejects(api.fill(limited, result, () => true), /Answer too long/);
  assert.equal(limited.value, '');

  const select = new Select([{text: 'Select one', value: '', parentElement: {}},
    {text: 'Example option', value: 'opaque-value', parentElement: {}}]);
  assert.equal(api.nonempty(select), false);
  assert.equal(await api.fill(select, {candidates: ['Missing']}, () => true), null);
  assert.equal(select.value, '');
  await api.fill(select, {candidates: ['example OPTION']}, () => true);
  assert.equal(select.value, 'opaque-value');
  assert.equal(api.nonempty(select), true);

  const checkbox = new Input('checkbox');
  await api.fill(checkbox, {candidates: ['Yes']}, () => true);
  assert.equal(checkbox.checked, true);
  await api.fill(checkbox, {candidates: ['No']}, () => true);
  assert.equal(checkbox.checked, false);

  const yes = new Input('radio'); const no = new Input('radio'); const other = new Input('radio');
  yes.labels = [{innerText: 'Yes'}]; no.labels = [{innerText: 'No'}]; other.labels = [{innerText: 'Yes'}];
  yes.name = no.name = other.name = 'example'; other.form = {};
  const group = {querySelector: () => ({innerText: 'Example group question'}),
    querySelectorAll: () => [yes, no, other], getAttribute: () => null};
  yes.group = no.group = group;
  assert.equal(api.labelFor(yes), 'Example group question');
  await api.fill(yes, {candidates: ['NO']}, () => true);
  assert.equal(no.checked, true); assert.equal(other.checked, false);
  assert.equal(api.nonempty(yes), true);

  const combo = new Input(); combo.attributes.role = 'combobox'; combo.attributes['aria-controls'] = 'example-list';
  const option = new Input(); option.innerText = 'Example choice'; option.click = () => { combo.value = option.innerText; };
  const list = new Input(); list.attributes.role = 'listbox'; list.querySelectorAll = () => [option];
  document.getElementById = id => id === 'example-list' ? list : null;
  await api.fill(combo, {candidates: ['Example choice']}, () => true);
  assert.equal(combo.value, 'Example choice');
  const submit = new Input(); submit.tagName = 'BUTTON'; submit.type = 'submit'; submit.form = {};
  submit.click = () => { throw Error('Submit must never run'); };
  assert.throws(() => api.safeClick(submit), /Manual field/);

  const field = new Input(); field.labels = [{innerText: 'Example question'}];
  document.querySelectorAll = () => [field];
  api.scan(); api.scan();
  assert.equal(shadows.length, 1);
  const [, button, badge, save] = shadows[0].children;
  assert.equal(button.type, 'button');
  const event = shiftKey => ({shiftKey, preventDefault() {}, stopPropagation() {}});
  field.value = 'Keep existing';
  await button.listeners.click(event(false));
  assert.equal(requests.length, 0); assert.equal(field.value, 'Keep existing');
  assert.equal(badge.textContent, 'has value');
  await button.listeners.click(event(true));
  assert.equal(field.value, 'Example answer'); assert.equal(badge.textContent, 'stored');
  assert.equal(save.hidden, true);

  field.value = ''; delayResponse = true;
  const inflight = button.listeners.click(event(false));
  field.value = 'Entered while lookup ran';
  pendingResponse({ok: true, value: storedResponse});
  await inflight;
  assert.equal(field.value, 'Entered while lookup ran');
  assert.equal(badge.textContent, 'field changed');
  delayResponse = false;
  storedResponse = {status: 'draft', answer: 'Example draft.', candidates: ['Example draft.']};
  await button.listeners.click(event(true));
  assert.equal(field.value, 'Example draft.'); assert.equal(save.hidden, false);
  assert.equal(badge.textContent, 'draft');
  await save.listeners.click(event(false));
  assert.equal(requests.at(-1).type, 'portal-assist-accept');
  assert.equal(requests.at(-1).body.answer, 'Example draft.');
  assert.equal(badge.textContent, 'stored');
  field.isConnected = false;
  const replacement = new Input(); replacement.labels = [{innerText: 'Example question'}];
  document.querySelectorAll = () => [replacement];
  api.scan(); api.scan();
  assert.equal(shadows.length, 2);
  context.PortalAutomationFilling = true;
  document.querySelectorAll = () => { throw Error('Must stay passive during automation'); };
  api.scan();
}

async function workerChecks() {
  const original = fs.readFileSync(path.join(EXTENSION, 'background.js'), 'utf8');
  const source = original;
  const calls = [];
  let listener;
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic-extension',
    onMessage: {addListener(value) { listener = value; }}}, storage: {local: {get: async () => ({assistToken: SYNTHETIC_TOKEN})}}}, fetch: async (url, options) => {
      calls.push({url, options}); return {ok: true, json: async () => ({status: 'stored', answer: 'Example answer'})};
    }});
  vm.runInContext(source, context);
  const send = (message, sender) => new Promise(resolve => listener(message, sender, resolve));
  const sender = {id: 'synthetic-extension', frameId: 0, tab: {}, url: APPLICATION_URL};
  const message = {type: 'portal-assist-answer', body: {label: 'Example question', host: 'forged.example', url: 'forged'}};
  const answer = await send(message, sender);
  assert.equal(answer.ok, true);
  assert.equal(calls[0].url, 'http://127.0.0.1:8766/assist/answer');
  assert.equal(calls[0].options.headers['X-Assist-Token'], SYNTHETIC_TOKEN);
  assert.equal(JSON.parse(calls[0].options.body).url, APPLICATION_URL);
  assert.equal(JSON.stringify(answer).includes(SYNTHETIC_TOKEN), false);
  for (const invalid of [{...sender, id: 'other-extension'}, {...sender, tab: null},
    {...sender, url: 'https://unrelated.example/apply'}, {...sender, url: 'http://example.myworkdayjobs.com/apply'}]) {
    assert.equal((await send(message, invalid)).ok, false);
  }
  assert.equal(calls.length, 1);
  assert.equal((await send({type: 'portal-assist-accept', body: {label: 'Example question', answer: 'Example answer'}}, sender)).ok, true);
  assert.equal(calls[1].url, 'http://127.0.0.1:8766/assist/accept');
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist content and worker checks passed\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
