/* Author: Yazad Madan. Browser-free Save page capture and worker boundary checks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const APPLICATION_URL = 'https://example.myworkdayjobs.com/apply';
const TOKEN = 'synthetic-token';
const ANSWER = 'Synthetic project answer';
const LABELS = ['First name', 'Email address', 'Phone number', 'Address', 'LinkedIn URL',
  'Need sponsorship now?', 'Need sponsorship in future?', 'Authorized to work?', 'Veteran status',
  'Disability', 'Gender', 'Race or ethnicity', 'Nationality', 'Pronouns', 'Signature', 'I attest this is true', 'SSN'];
const EVENT = {preventDefault() {}, stopPropagation() {}};

class Element {
  constructor(tag = 'input', label = 'Synthetic question', type = 'text') {
    this.tagName = tag.toUpperCase(); this.type = type; this.isConnected = true;
    this.labels = [{innerText: label}]; this.attributes = {}; this.listeners = {};
    this.children = []; this.style = {}; this.value = ''; this.maxLength = -1;
  }
  getAttribute(key) { return this.attributes[key] || null; }
  setAttribute(key, value) { this.attributes[key] = value; }
  getClientRects() { return this.hidden ? [] : [{}]; }
  closest() { return null; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  attachShadow() { this.shadow = new Element('div'); return this.shadow; }
  remove() { this.isConnected = false; }
  click() { return this.listeners.click?.({preventDefault() {}, stopPropagation() {}}); }
}

async function contentChecks() {
  const fields = LABELS.map(label => new Element('input', label));
  fields.forEach(field => { field.value = ANSWER; });
  const typed = new Element('input', 'Typed project');
  const filled = new Element('input', 'Filled project');
  const corrected = new Element('textarea', 'Corrected project');
  const number = new Element('input', 'Years of experience', 'number'); number.value = '3';
  const date = new Element('input', 'Available day', 'date'); date.value = '2026-12-15';
  const readonly = new Element('input', 'Read only project'); readonly.value = ANSWER; readonly.readOnly = true;
  const disabled = new Element('input', 'Disabled project'); disabled.value = ANSWER; disabled.disabled = true;
  const long = new Element('input', 'Long project'); long.value = 'x'.repeat(2001);
  const blank = new Element('input', 'Blank project');
  const hidden = new Element('input', 'Hidden project'); hidden.hidden = true; hidden.value = ANSWER;
  const password = new Element('input', 'Password', 'password');
  const file = new Element('input', 'Upload', 'file');
  for (const field of [password, file]) Object.defineProperty(field, 'value', {
    get() { throw Error('Password and file values must never be read'); }
  });
  fields.push(typed, filled, corrected, number, date, readonly, disabled, long, blank, hidden, password, file);
  const hosts = [], requests = [], listeners = {};
  const document = {documentElement: {}, body: {append(host) { hosts.push(host); }},
    querySelectorAll: selector => selector.startsWith('input:not([type="hidden"])') ? fields
      : fields.filter(field => !['number', 'date', 'password', 'file'].includes(field.type)),
    querySelector: () => null, getElementById: () => null,
    createElement: tag => new Element(tag), createTextNode: textContent => ({textContent}),
    addEventListener(type, callback) { listeners[type] = callback; }};
  let failure = false;
  const context = vm.createContext({document, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    getComputedStyle: () => ({visibility: 'visible'}), MutationObserver: class {observe() {}}, Node: {ELEMENT_NODE: 1},
    chrome: {runtime: {sendMessage(message, callback) {
      requests.push(message);
      if (failure) callback({ok: false, error: ANSWER});
      else if (message.type === 'portal-assist-learn') callback({ok: true, value: {scope: 'Example Corp',
        results: message.body.pairs.map(pair => ({...pair, status: 'new', previous_answer: null, stored: !message.body.dry_run}))}});
      else {
        const excluded = message.body.pairs.filter(row => ['password', 'file'].includes(row.type)).length;
        callback({ok: true, value: {saved: message.body.pairs.length - excluded, duplicate: 0,
          excluded_by_type: excluded, flagged_sensitive: 12}});
      }
    }}}});
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  const marker = '  scan();\n})();';
  assert.equal(source.split(marker).length, 2);
  vm.runInContext(source.replace(marker, '  globalThis.testAssist = {scan, fieldStates, learnRows};\n})();'), context);
  const api = context.testAssist;
  api.scan();
  typed.value = ANSWER; listeners.input({target: typed, isTrusted: true});
  filled.value = ANSWER; api.fieldStates.get(filled).filled = ANSWER;
  corrected.value = ANSWER; api.fieldStates.get(corrected).corrected = ANSWER;
  fields.find(field => field.labels[0].innerText === 'Need sponsorship now?').value = 'Typed synthetic choice';
  listeners.change({target: fields[5], isTrusted: true});
  const dock = hosts.find(host => host.shadow?.children.some(child => child.textContent === 'Save page'));
  const save = dock.shadow.children[5];
  const summary = dock.shadow.children[6];
  assert.equal(dock.shadow.children[3].textContent, 'Learn page');
  assert.match(dock.shadow.children[0].textContent, /left:0!important/);
  assert.equal(save.type, 'button');
  const before = fields.filter(field => !['password', 'file'].includes(field.type)).map(field => field.value);
  await save.listeners.click(EVENT);
  assert.equal(requests[0].type, 'portal-assist-dump');
  assert.equal(requests[1].type, 'portal-assist-learn');  // Save page chains the reviewed Learn list
  assert.equal(requests[1].body.dry_run, true);
  const rows = requests[0].body.pairs;
  assert.equal(rows.length, fields.length - 2);
  assert.equal(rows.find(row => row.label === 'Typed project').source, 'typed');
  assert.equal(rows.find(row => row.label === 'Filled project').source, 'filled');
  assert.equal(rows.find(row => row.label === 'Corrected project').source, 'corrected');
  assert.equal(rows.find(row => row.label === 'First name').source, 'prefilled');
  assert.equal(rows.find(row => row.label === 'Need sponsorship now?').source, 'typed');
  for (const label of LABELS) assert.ok(rows.some(row => row.label === label));
  assert.equal(rows.find(row => row.label === 'Long project').answer.length, 2001);
  for (const row of rows.filter(row => ['password', 'file'].includes(row.type))) assert.equal(row.answer, undefined);
  assert.match(summary.textContent, /saved 25, skipped 2 blocked by type/);
  assert.match(summary.textContent, /password\/file inputs are not answers/);
  assert.equal(summary.hidden, false);
  assert.equal(save.disabled, false);
  assert.deepEqual(fields.filter(field => !['password', 'file'].includes(field.type)).map(field => field.value), before);
  assert.ok(dock.shadow.children[4].children.length > 0);  // chained Learn review is open
  context.PortalAutomationFilling = true;
  await save.listeners.click(EVENT);
  assert.equal(requests.length, 2);
  document.querySelectorAll = () => { throw Error('No scan during automation'); };
  api.scan();
  context.PortalAutomationFilling = false;
  document.querySelectorAll = () => fields;
  failure = true;
  await save.listeners.click(EVENT);
  assert.match(summary.textContent, /Save failed/);
  assert.equal(summary.textContent.includes(ANSWER), false);
  fields.forEach(field => { field.isConnected = false; });
  fields.splice(0, fields.length, ...Array.from({length: 81}, (_, index) => {
    const field = new Element('input', `Synthetic project ${index}`); field.value = ANSWER; return field;
  }));
  const count = requests.length;
  await save.listeners.click(EVENT);
  assert.equal(requests.length, count);
  assert.match(summary.textContent, /more than 80/);
  const dates = ['Month', 'Day', 'Year'].map((label, index) => {
    const field = new Element('input', label, 'number');
    field.attributes['aria-label'] = label;
    field.value = ['12', '15', '2026'][index]; field.readOnly = true;
    return field;
  });
  const group = {getAttribute: () => null, querySelectorAll: () => dates,
    querySelector: () => ({innerText: 'Availability date'})};
  dates.forEach(field => { field.closest = selector => selector.startsWith('fieldset')
    || selector.startsWith('[data-automation-id=') ? group : null; });
  fields.forEach(field => { field.isConnected = false; });
  fields.splice(0, fields.length, ...dates);
  failure = false;
  await save.listeners.click(EVENT);
  assert.equal(requests.at(-1).body.pairs.length, 1);
  assert.equal(requests.at(-1).body.pairs[0].label, 'Availability date');
  assert.equal(requests.at(-1).body.pairs[0].answer, '12/15/2026');
  const learningFields = ['Prefilled project', 'Typed project', 'Filled project', 'Corrected project', 'Gender']
    .map(label => new Element('input', label));
  learningFields[0].value = ANSWER;
  learningFields[4].value = ANSWER;
  fields.forEach(field => { field.isConnected = false; });
  fields.splice(0, fields.length, ...learningFields);
  api.scan();
  learningFields[1].value = ANSWER;
  listeners.input({target: learningFields[1], isTrusted: true});
  learningFields[2].value = ANSWER; api.fieldStates.get(learningFields[2]).filled = ANSWER;
  learningFields[3].value = ANSWER; api.fieldStates.get(learningFields[3]).corrected = ANSWER;
  const learn = dock.shadow.children[3], review = dock.shadow.children[4];
  await learn.listeners.click(EVENT);
  assert.equal(requests.at(-1).body.dry_run, true);
  assert.equal(requests.at(-1).body.pairs.length, 4);
  const expected = {'Prefilled project': 'prefilled', 'Typed project': 'typed',
    'Filled project': 'filled', 'Corrected project': 'corrected'};
  for (const row of requests.at(-1).body.pairs) assert.equal(row.source, expected[row.label]);
  const unchecked = review.children.find(line => line.children?.[0]?.children?.[1]?.textContent?.startsWith('Typed project'));
  unchecked.children[0].children[0].checked = false;
  await review.children.at(-1).listeners.click(EVENT);
  assert.equal(requests.at(-1).type, 'portal-assist-learn');
  assert.equal(requests.at(-1).body.dry_run, false);
  assert.equal(requests.at(-1).body.pairs.length, 3);
  for (const row of requests.at(-1).body.pairs) {
    assert.notEqual(row.label, 'Typed project');
    assert.equal(row.source, expected[row.label]);
  }
}

async function workerChecks() {
  let listener;
  const forwarded = [];
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic',
    onMessage: {addListener(callback) { listener = callback; }}}, storage: {local: {get: async () => ({assistToken: TOKEN})}}},
    fetch: async (url, options) => {
      forwarded.push({url, options, body: JSON.parse(options.body)});
      return {ok: true, json: async () => ({saved: 1, duplicate: 0, excluded_by_type: 0, flagged_sensitive: 0})};
    }});
  vm.runInContext(fs.readFileSync(path.join(EXTENSION, 'background.js'), 'utf8'), context);
  const sender = {id: 'synthetic', tab: {}, url: APPLICATION_URL};
  const message = {type: 'portal-assist-dump', body: {pairs: [{label: 'Signature', answer: ANSWER, source: 'prefilled', type: 'text'}],
    company_hint: 'Example Corp', host: 'forged.example', url: 'https://forged.example', secret: ANSWER}};
  const send = (payload = message, origin = sender) => new Promise(resolve => listener(payload, origin, resolve));
  assert.equal((await send()).ok, true);
  assert.equal(forwarded[0].url, 'http://127.0.0.1:8766/assist/dump');
  assert.equal(forwarded[0].body.host, 'example.myworkdayjobs.com');
  assert.equal(forwarded[0].body.url, APPLICATION_URL);
  assert.equal(forwarded[0].body.secret, undefined);
  assert.deepEqual(forwarded[0].body.pairs, message.body.pairs);
  for (const origin of [{...sender, id: 'forged'}, {...sender, tab: null}, {...sender, url: 'https://unrelated.example/apply'},
    {...sender, url: 'http://example.myworkdayjobs.com/apply'}]) assert.equal((await send(message, origin)).ok, false);
  assert.equal((await send({...message, body: []})).ok, false);
  assert.equal((await send({...message, body: {pairs: [{label: 'Synthetic', answer: 'x'.repeat(65536)}]}})).ok, false);
  assert.equal(forwarded.length, 1);
  const learn = {type: 'portal-assist-learn', body: {dry_run: false,
    pairs: [{label: 'Preferred project', answer: ANSWER, source: 'corrected'}]}};
  assert.equal((await send(learn)).ok, true);
  assert.equal(forwarded.at(-1).url, 'http://127.0.0.1:8766/assist/learn');
  assert.equal(forwarded.at(-1).body.host, 'example.myworkdayjobs.com');
  assert.equal(forwarded.at(-1).body.pairs[0].source, 'corrected');
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist Save page checks passed (2 suites)\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
