/* Author: Yazad Madan. Browser-free miss notifications and worker privacy checks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const APPLICATION_URL = 'https://example.myworkdayjobs.com/apply';
const TOKEN = 'synthetic-assist-token';
const LABEL = 'Preferred project?';

class Input {
  constructor(label = LABEL) {
    this.tagName = 'INPUT'; this.type = 'text'; this.isConnected = true;
    this.labels = [{innerText: label}]; this.attributes = {};
    this.disabled = false; this.readOnly = false; this.maxLength = -1;
    this._value = ''; this.events = [];
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  getAttribute(key) { return this.attributes[key] || null; }
  getClientRects() { return [{}]; }
  closest() { return null; }
  dispatchEvent(event) { this.events.push(event.type); }
}

class Select extends Input {
  constructor() {
    super(); this.tagName = 'SELECT'; this.type = 'select-one';
    this.options = Array.from({length: 45}, (_, index) => ({
      text: `Example ${index} ` + 'o'.repeat(130), value: 'DO_NOT_SEND_OPTION_VALUE', parentElement: {}}));
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  get selectedOptions() { return []; }
}

class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.isConnected = true; this.style = {}; }
  attachShadow() { return {append() {}}; }
  setAttribute() {}
  addEventListener() {}
  remove() { this.isConnected = false; }
}

async function contentChecks() {
  const original = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  const source = original.replace('  scan();\n})();', '  globalThis.testAssist = {scan, controls, reportMiss};\n})();');
  assert.notEqual(source, original);
  const requests = [];
  let fields = [];
  let answer = {status: 'none', answer: '', candidates: []};
  let missMode = 'pending';
  const runtime = {sendMessage(message, callback) {
    requests.push(message);
    if (message.type !== 'portal-assist-miss') callback({ok: true, value: answer});
    else if (missMode === 'throw') throw Error('Synthetic worker failure');
    else if (missMode === 'reject') callback({ok: false, error: 'Synthetic server failure'});
    else if (missMode === 'lastError') {
      runtime.lastError = {message: 'Synthetic disconnected worker'};
      callback();
      delete runtime.lastError;
    }
  }};
  const document = {documentElement: {}, body: {append() {}}, querySelectorAll: () => fields,
    querySelector: () => null, getElementById: () => null, createElement: tag => new Element(tag)};
  const context = vm.createContext({document, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    chrome: {runtime}, Event, Node: {ELEMENT_NODE: 1}, HTMLInputElement: Input,
    HTMLSelectElement: Select, HTMLTextAreaElement: Input, getComputedStyle: () => ({visibility: 'visible'}),
    MutationObserver: class { observe() {} }});
  vm.runInContext(source, context);
  const api = context.testAssist;
  const misses = () => requests.filter(message => message.type === 'portal-assist-miss');
  const input = new Input();
  fields = [input]; api.scan();
  // An unresolved notification must not keep the fill pending.
  assert.equal(await api.controls.get(input).run(false), 'no answer');
  assert.equal(misses().length, 1);
  assert.deepEqual(Object.keys(misses()[0].body).sort(), ['company_hint', 'host', 'label', 'options', 'type']);
  assert.equal(misses()[0].body.label, LABEL);
  assert.equal(input.value, '');
  for (missMode of ['throw', 'reject', 'lastError']) {
    assert.equal(await api.controls.get(input).run(false), 'no answer');
  }
  input.isConnected = false;
  const select = new Select();
  select.labels = [{innerText: 'q'.repeat(400)}];
  fields = [select]; api.scan();
  answer = {status: 'stored', answer: 'Missing option', candidates: ['Missing option']};
  assert.equal(await api.controls.get(select).run(false), 'no match');
  const body = misses().at(-1).body;
  assert.equal(body.label.length, 300);
  assert.equal(body.options.length, 40);
  assert.equal(body.options[0].length, 120);
  assert.equal(JSON.stringify(body).includes('DO_NOT_SEND'), false);
  assert.equal(select.value, '');
  assert.equal(select.events.length, 0);
  select.isConnected = false;
  input.isConnected = true;
  fields = [input]; api.scan();
  const before = misses().length;
  for (const status of ['stored', 'draft']) {
    input.value = '';
    answer = {status, answer: 'Example answer', candidates: ['Example answer']};
    assert.equal(await api.controls.get(input).run(false), status);
    assert.equal(input.value, 'Example answer');
  }
  assert.equal(await api.controls.get(input).run(false), 'has value');
  assert.equal(misses().length, before);
}

async function workerChecks() {
  const calls = [];
  let listener;
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic-extension',
    onMessage: {addListener(value) { listener = value; }}},
    storage: {local: {get: async () => ({assistToken: TOKEN})}}},
    fetch: async (url, options) => {
      calls.push({url, options}); return {ok: true, json: async () => ({status: 'logged'})};
    }});
  vm.runInContext(fs.readFileSync(path.join(EXTENSION, 'background.js'), 'utf8'), context);
  const send = (message, sender) => new Promise(resolve => listener(message, sender, resolve));
  const sender = {id: 'synthetic-extension', frameId: 0, tab: {}, url: APPLICATION_URL};
  const message = {type: 'portal-assist-miss', body: {label: LABEL, type: 'select-one',
    company_hint: 'Example Corp', options: ['Example A'], host: 'forged.example',
    value: 'DO_NOT_SEND', answer: 'DO_NOT_SEND', url: 'DO_NOT_SEND'}};
  assert.equal((await send(message, sender)).ok, true);
  assert.equal(calls[0].url, 'http://127.0.0.1:8766/assist/miss');
  assert.equal(calls[0].options.headers['X-Assist-Token'], TOKEN);
  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.host, 'example.myworkdayjobs.com');
  assert.equal(JSON.stringify(body).includes('DO_NOT_SEND'), false);
  assert.deepEqual(Object.keys(body).sort(), ['company_hint', 'host', 'label', 'options', 'type']);
  for (const invalid of [{...sender, id: 'other-extension'}, {...sender, tab: null},
    {...sender, url: 'https://unrelated.example/apply'}, {...sender, url: 'http://example.myworkdayjobs.com/apply'}]) {
    assert.equal((await send(message, invalid)).ok, false);
  }
  assert.equal(calls.length, 1);
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist miss checks passed\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
