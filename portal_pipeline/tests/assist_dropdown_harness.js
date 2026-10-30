/* Author: Yazad Madan. Synthetic dropdown mapping fill and review checks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const HOST = 'example.myworkdayjobs.com';
const LABEL = 'Country?';
const ANSWER = 'USA';
const OPTION = 'United States of America';

class Element {
  constructor(tag = 'input') {
    this.tagName = tag.toUpperCase(); this.type = 'text'; this.isConnected = true;
    this.attributes = {}; this.listeners = {}; this.children = []; this.style = {};
    this.labels = [{innerText: LABEL}]; this._value = ''; this._checked = false;
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  get checked() { return this._checked; }
  set checked(value) { this._checked = value; }
  getAttribute(key) { return this.attributes[key] || null; }
  setAttribute(key, value) { this.attributes[key] = value; }
  closest(selector) { return selector.startsWith('fieldset') ? this.group || null : null; }
  getClientRects() { return [{}]; }
  dispatchEvent() {}
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.textContent = ''; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  remove() { this.isConnected = false; }
  attachShadow() { const shadow = new Element('div'); shadows.push(shadow); return shadow; }
}
class Select extends Element {
  constructor() {
    super('select'); this.type = 'select-one';
    this.options = [{text: 'Select one', value: '', parentElement: {}},
      {text: OPTION, value: 'opaque-option', parentElement: {}}, {text: ANSWER, value: 'literal', parentElement: {}}];
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  get selectedOptions() { return this.options.filter(option => option.value === this.value); }
}

const shadows = [];
const requests = [];
const listeners = {};
const fields = [];
const nodes = {};
const event = {preventDefault() {}, stopPropagation() {}};
const document = {documentElement: {}, body: {append() {}}, querySelectorAll: () => fields,
  querySelector: () => null, getElementById: id => nodes[id], createElement: tag => new Element(tag),
  createTextNode: textContent => ({textContent}), addEventListener: (type, listener) => { listeners[type] = listener; }};
const runtime = {sendMessage(message, callback) {
  requests.push(message);
  if (message.type === 'portal-assist-learn') callback({ok: true, value: {scope: 'Example Corp',
    results: message.body.pairs.map(pair => ({label: pair.label, answer: pair.answer, status: 'dropdown',
      mapping_answer: ANSWER, vendor: 'workday', previous_option: null, stored: !message.body.dry_run}))}});
  else callback({ok: true, value: {status: 'stored', answer: ANSWER, candidates: [ANSWER], mapped_options: [OPTION]}});
}};
const context = vm.createContext({document, location: new URL(`https://${HOST}/apply`),
  setTimeout, clearTimeout, chrome: {runtime}, Event, Node: {ELEMENT_NODE: 1},
  HTMLInputElement: Element, HTMLSelectElement: Select, HTMLTextAreaElement: Element,
  MutationObserver: class { observe() {} }, getComputedStyle: () => ({visibility: 'visible'})});
const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
const marker = '  scan();\n})();';
assert.equal(source.split(marker).length, 2);
vm.runInContext(source.replace(marker,
  '  globalThis.testAssist = {match, fill, scan, controls, learnRows};\n})();'), context);
const api = context.testAssist;

async function checks() {
  const options = [{text: ANSWER}, {text: OPTION}];
  assert.equal(api.match(options, [ANSWER], [OPTION]).text, OPTION);
  assert.equal(api.match(options, [ANSWER], ['Absent']).text, ANSWER);
  assert.equal(api.match([{text: OPTION + ' extra'}], [ANSWER], [OPTION]), null);
  assert.equal(api.match([{text: OPTION}, {text: OPTION}], [ANSWER], [OPTION]), null);
  assert.equal(api.match(options, ['Missing', ANSWER], [null, OPTION]).text, OPTION);
  const result = {status: 'stored', answer: ANSWER, candidates: [ANSWER], mapped_options: [OPTION]};
  const select = new Select();
  await api.fill(select, result, () => true);
  assert.equal(select.value, 'opaque-option');
  const radio = new Element(); radio.type = 'radio'; radio.name = 'country'; radio.labels = [{innerText: OPTION}];
  radio.group = {querySelectorAll: () => [radio], querySelector: () => ({innerText: LABEL}), getAttribute: () => null};
  await api.fill(radio, result, () => true);
  assert.equal(radio.checked, true);
  const combo = new Element(); combo.attributes = {role: 'combobox', 'aria-controls': 'options'};
  const option = new Element(); option.innerText = OPTION;
  option.click = () => { combo.value = OPTION; };
  const list = new Element(); list.attributes.role = 'listbox'; list.querySelectorAll = () => [option];
  nodes.options = list;
  await api.fill(combo, result, () => true);
  assert.equal(combo.value, OPTION);
  const text = new Element();
  await api.fill(text, result, () => true);
  assert.equal(text.value, ANSWER);
  assert.equal(requests.length, 0);

  for (const field of [new Select(), combo, radio]) {
    field.value = ''; field.checked = false;
    fields.splice(0, fields.length, field);
    api.scan();
    const dock = shadows[0];
    const learn = dock.children[3];
    const review = dock.children[4];
    if (field.tagName === 'SELECT') field.value = 'opaque-option';
    else if (field.type === 'radio') field.checked = true;
    else field.value = OPTION;
    listeners.change({target: field, isTrusted: true});
    assert.equal(api.learnRows()[0].manual, true);
    await learn.listeners.click(event);
    assert.equal(requests.at(-1).body.dry_run, true);
    assert.match(review.children[0].children[0].children[1].textContent, /dropdown: USA = United States of America/);
    assert.match(review.children[0].children[0].children[1].textContent, /Vendor: workday/);
    await review.children.at(-1).listeners.click(event);
    const pair = requests.at(-1).body.pairs[0];
    assert.equal(requests.at(-1).body.dry_run, false);
    assert.equal(pair.mapping_answer, ANSWER);
    assert.equal(pair.previous_option, null);
    assert.equal(pair.type, field.attributes.role || field.type);
    assert.equal('previous_answer' in pair, false);
    field.isConnected = false;
  }

  const filled = new Select(); fields.splice(0, fields.length, filled); api.scan();
  const before = requests.length;
  assert.equal(await api.controls.get(filled).run(false), 'stored');
  assert.equal(requests.length, before + 1);
  assert.equal(requests.at(-1).type, 'portal-assist-answer');
  assert.equal(api.learnRows()[0].manual, false);
  assert.equal(filled.value, 'opaque-option');
  assert.equal(await api.controls.get(filled).run(false), 'has value');
  assert.equal(requests.length, before + 1);
  process.stdout.write('Assist dropdown checks passed\n');
}

checks().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
