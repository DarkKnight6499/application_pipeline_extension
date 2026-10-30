/* Author: Yazad Madan. Browser-free correction events, review priority, and worker boundaries. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const URL_TEXT = 'https://example.myworkdayjobs.com/apply';
const WRONG = 'Synthetic old project';
const USER = 'Synthetic revised project';
const TOKEN = 'synthetic-assist-token';
const PAUSE_MS = 220;

class Input {
  constructor(label) {
    this.tagName = 'INPUT'; this.type = 'text'; this.isConnected = true;
    this.labels = [{innerText: label}]; this.disabled = this.readOnly = false;
    this._value = ''; this.maxLength = -1;
  }
  get value() { return this._value; }
  set value(value) { this._value = value; }
  getAttribute() { return null; }
  getClientRects() { return [{}]; }
  closest() { return null; }
  dispatchEvent() {}
}
class Element {
  constructor(tag, shadows) {
    this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {};
    this.isConnected = true; this.style = {}; this.shadows = shadows;
  }
  attachShadow() {
    const root = {children: [], append(...children) { this.children.push(...children); }};
    this.shadows.push(root);
    return root;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
  addEventListener(type, listener) { this.listeners[type] = listener; }
  remove() { this.isConnected = false; }
}

async function contentChecks() {
  const shadows = [], requests = [], listeners = {};
  const fields = [];
  const original = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  const source = original.replace('  scan();\n})();',
    '  globalThis.testAssist = {scan, controls, learnRows};\n})();');
  assert.notEqual(source, original);
  const document = {documentElement: {}, body: {append() {}}, querySelectorAll: () => fields,
    querySelector: () => null, getElementById: () => null,
    createElement: tag => new Element(tag, shadows), createTextNode: textContent => ({textContent}),
    addEventListener(type, listener) { listeners[type] = listener; }};
  let failure = false;
  const context = vm.createContext({document, location: new URL(URL_TEXT), setTimeout, clearTimeout,
    Event, Node: {ELEMENT_NODE: 1}, HTMLInputElement: Input, HTMLSelectElement: Input, HTMLTextAreaElement: Input,
    getComputedStyle: () => ({visibility: 'visible'}), MutationObserver: class { observe() {} },
    chrome: {runtime: {sendMessage(message, callback) {
      requests.push(message);
      if (message.type === 'portal-assist-correction') {
        if (failure) callback({ok: false, error: 'Synthetic offline helper'});
        else callback({ok: true, value: {status: 'recorded'}});
      } else if (message.type === 'portal-assist-learn') {
        callback({ok: true, value: {scope: 'Example Corp', results: message.body.pairs.map(pair =>
          ({...pair, status: 'new', previous_answer: null}))}});
      } else callback({ok: true, value: {status: 'stored', answer: WRONG, candidates: [WRONG]}});
    }}}});
  vm.runInContext(source, context);
  const api = context.testAssist;
  const pause = () => new Promise(resolve => setTimeout(resolve, PAUSE_MS));
  const send = (type, field, isTrusted = true) => listeners[type]({target: field, isTrusted});
  const corrections = () => requests.filter(message => message.type === 'portal-assist-correction');
  const add = label => { const field = new Input(label); fields.push(field); api.scan(); return field; };
  const fill = async field => assert.equal(await api.controls.get(field).run(false), 'stored');
  const edit = (field, value = USER, trusted = true) => { field.value = value; send('input', field, trusted); };

  const manual = add('Manual project?');
  edit(manual); send('blur', manual); await pause();
  assert.equal(corrections().length, 0);
  const field = add('Preferred project?');
  await fill(field);
  edit(field, 'Intermediate synthetic value'); send('change', field);
  edit(field); send('change', field);
  await pause();
  assert.equal(corrections().length, 0);
  send('blur', field, false); await pause();
  assert.equal(corrections().length, 0);
  send('blur', field); send('blur', field);
  await pause();
  assert.equal(corrections().length, 1);
  assert.equal(corrections()[0].body.wrong_value, WRONG);
  assert.equal(corrections()[0].body.user_value, USER);
  assert.equal(JSON.stringify(corrections()).includes('Intermediate'), false);
  send('change', field); send('blur', field); await pause();
  assert.equal(corrections().length, 1);

  const rows = api.learnRows();
  assert.equal(rows[0].label, 'Preferred project?');
  assert.equal(rows[0].corrected, true);
  const learn = shadows[0].children[3], review = shadows[0].children[4];
  await learn.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.equal(review.children[0].children[0].children[0].checked, true);
  assert.match(review.children[0].children[0].children[1].textContent, /\ncorrected/);

  const scripted = add('Site project?'); await fill(scripted);
  edit(scripted, USER, false); send('change', scripted, false); send('blur', scripted); await pause();
  assert.equal(corrections().length, 1);
  const reverted = add('Reverted project?'); await fill(reverted);
  edit(reverted); edit(reverted, WRONG); send('blur', reverted); await pause();
  assert.equal(corrections().length, 1);
  const overwritten = add('Site rewrite after edit?'); await fill(overwritten);
  edit(overwritten); send('blur', overwritten); overwritten.value = 'Site rewrite'; await pause();
  assert.equal(corrections().length, 1);

  const refocused = add('Refocused project?'); await fill(refocused);
  edit(refocused); send('blur', refocused); send('focusin', refocused); await pause();
  assert.equal(corrections().length, 1);
  edit(refocused, 'Final synthetic choice'); send('blur', refocused); await pause();
  assert.equal(corrections().length, 2);
  assert.equal(corrections().at(-1).body.user_value, 'Final synthetic choice');

  const relabeled = add('Original project?'); await fill(relabeled);
  edit(relabeled); relabeled.labels = [{innerText: 'Changed project?'}]; send('blur', relabeled); await pause();
  assert.equal(corrections().length, 2);
  const blocked = add('Future sponsorship?'); await fill(blocked);
  edit(blocked); send('blur', blocked); await pause();
  assert.equal(corrections().length, 2);
  const automation = add('Automation project?'); await fill(automation);
  context.PortalAutomationFilling = true;
  edit(automation); send('blur', automation); await pause();
  context.PortalAutomationFilling = false;
  assert.equal(corrections().length, 2);
  const navigated = add('Navigated project?'); await fill(navigated);
  edit(navigated); send('blur', navigated); context.location.href += '/other'; await pause();
  assert.equal(corrections().length, 2);
  context.location.href = URL_TEXT;
  const offline = add('Offline project?'); await fill(offline);
  failure = true; edit(offline); send('blur', offline); await pause();
  assert.equal(corrections().length, 3);
  assert.equal(api.learnRows().find(row => row.element === offline).corrected, true);
  failure = false;
  edit(field, 'Later synthetic choice'); send('blur', field); await pause();
  assert.equal(corrections().length, 4);
  assert.equal(corrections().at(-1).body.wrong_value, WRONG);
  assert.equal(corrections().at(-1).body.user_value, 'Later synthetic choice');
  send('change', field); send('blur', field); await pause();
  assert.equal(corrections().length, 4);
  edit(field, WRONG); send('blur', field); await pause();
  assert.equal(corrections().length, 4);
  edit(field, 'Later synthetic choice'); send('blur', field); await pause();
  assert.equal(corrections().length, 5);
}

async function workerChecks() {
  let listener;
  const calls = [];
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic-extension',
    onMessage: {addListener(value) { listener = value; }}},
    storage: {local: {get: async () => ({assistToken: TOKEN})}}},
    fetch: async (url, options) => { calls.push({url, options}); return {ok: true, json: async () => ({status: 'recorded'})}; }});
  vm.runInContext(fs.readFileSync(path.join(EXTENSION, 'background.js'), 'utf8'), context);
  const send = (message, sender) => new Promise(resolve => listener(message, sender, resolve));
  const sender = {id: 'synthetic-extension', tab: {}, url: URL_TEXT};
  const message = {type: 'portal-assist-correction', body: {label: 'Preferred project?', type: 'text',
    host: 'forged.invalid', company_hint: 'Example Corp', wrong_value: WRONG, user_value: USER,
    url: 'DO_NOT_FORWARD', answer: 'DO_NOT_FORWARD', token: 'DO_NOT_FORWARD'}};
  assert.equal((await send(message, sender)).ok, true);
  assert.equal(calls[0].url, 'http://127.0.0.1:8766/assist/correction');
  assert.equal(calls[0].options.headers['X-Assist-Token'], TOKEN);
  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.host, new URL(URL_TEXT).hostname);
  assert.equal(body.user_value, USER);
  assert.equal(body.wrong_value, WRONG);
  assert.equal(JSON.stringify(body).includes('DO_NOT_FORWARD'), false);
  for (const invalid of [{...sender, id: 'other'}, {...sender, tab: null},
    {...sender, url: 'https://unrelated.invalid'}, {...sender, url: URL_TEXT.replace('https:', 'http:')}]) {
    assert.equal((await send(message, invalid)).ok, false);
  }
  assert.equal(calls.length, 1);
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist correction checks passed (2 suites)\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
