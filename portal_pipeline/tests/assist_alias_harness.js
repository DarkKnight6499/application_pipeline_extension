/* Author: Yazad Madan. Browser-free alias review, selection, and worker forwarding checks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const APPLICATION_URL = 'https://example.myworkdayjobs.com/apply';
const QUESTION = 'Describe your preferred project';
const ALIAS = 'Please describe your preferred project';
const ANSWER = 'Example project answer';
const TOKEN = 'synthetic-token';

class Element {
  constructor(tag = 'input') {
    this.tagName = tag.toUpperCase(); this.type = 'text'; this.isConnected = true;
    this.children = []; this.listeners = {}; this.style = {}; this.value = '';
    this.labels = [{innerText: ALIAS}];
  }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; this.textContent = ''; }
  attachShadow() { this.shadow = new Element('div'); return this.shadow; }
  addEventListener(type, callback) { this.listeners[type] = callback; }
  setAttribute() {}
  getAttribute() { return null; }
  getClientRects() { return [{}]; }
  closest() { return null; }
}

async function contentChecks() {
  const input = new Element();
  const hosts = [];
  const requests = [];
  const listeners = {};
  const document = {documentElement: {}, body: {append(host) { hosts.push(host); }},
    querySelectorAll: () => [input], querySelector: () => null, getElementById: () => null,
    createElement: tag => new Element(tag), createTextNode: textContent => ({textContent}),
    addEventListener(type, callback) { listeners[type] = callback; }};
  let suggest = true;
  const chrome = {runtime: {sendMessage(message, callback) {
    requests.push(message);
    callback({ok: true, value: {scope: 'Example Corp', results: message.body.pairs.map(pair => ({
      ...pair, previous_answer: null, status: 'new', stored: !message.body.dry_run,
      ...(suggest ? {similar_to: QUESTION, similar_scope: 'company'} : {})}))}});
  }}};
  const context = vm.createContext({document, chrome, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    getComputedStyle: () => ({visibility: 'visible'}), MutationObserver: class {observe() {}}, Node: {ELEMENT_NODE: 1}});
  vm.runInContext(fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8'), context);
  input.value = ANSWER;
  listeners.input({target: input, isTrusted: true});
  const dock = hosts.find(host => host.shadow?.children.some(child => child.textContent === 'Learn page'));
  const [, , , learn, review] = dock.shadow.children;
  const event = {preventDefault() {}, stopPropagation() {}};
  const open = () => learn.listeners.click(event);
  const confirm = () => review.children.at(-1).listeners.click(event);
  await open();
  const [row] = review.children;
  assert.equal(row.children[1].textContent, `similar to: ${QUESTION}`);
  const aliasCheckbox = row.children[2].children[0];
  assert.equal(aliasCheckbox.type, 'checkbox');
  assert.equal(aliasCheckbox.checked, false);
  assert.equal(row.children[2].children[1].textContent, 'also use this answer for the similar question wording');
  await confirm();
  assert.equal(requests.at(-1).body.pairs[0].use_alias, false);
  await open();
  review.children[0].children[2].children[0].checked = true;
  await confirm();
  const pair = requests.at(-1).body.pairs[0];
  assert.equal(pair.use_alias, true);
  assert.equal(pair.similar_to, QUESTION);
  assert.equal(pair.similar_scope, 'company');
  assert.equal(pair.answer, ANSWER);
  await open();
  review.children[0].children[2].children[0].checked = true;
  review.children[0].children[0].children[0].checked = false;
  const before = requests.length;
  await confirm();
  assert.equal(requests.length, before);
  suggest = false;
  await open();
  assert.equal(review.children[0].children.length, 1);
  await confirm();
  assert.equal(requests.at(-1).body.pairs[0].use_alias, false);
}

async function workerChecks() {
  let listener;
  let forwarded;
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic',
    onMessage: {addListener(callback) { listener = callback; }}},
    storage: {local: {get: async () => ({assistToken: TOKEN})}}}, fetch: async (url, options) => {
      forwarded = {url, body: JSON.parse(options.body)};
      return {ok: true, json: async () => ({results: []})};
    }});
  vm.runInContext(fs.readFileSync(path.join(EXTENSION, 'background.js'), 'utf8'), context);
  const pair = {label: ALIAS, answer: ANSWER, previous_answer: null,
    similar_to: QUESTION, similar_scope: 'company', use_alias: true};
  const result = await new Promise(resolve => listener({type: 'portal-assist-learn', body: {pairs: [pair], dry_run: false}},
    {id: 'synthetic', tab: {}, frameId: 0, url: APPLICATION_URL}, resolve));
  assert.equal(result.ok, true);
  assert.equal(forwarded.url, 'http://127.0.0.1:8766/assist/learn');
  assert.deepEqual(forwarded.body.pairs[0], pair);
  assert.equal(forwarded.body.url, APPLICATION_URL);
  assert.equal(JSON.stringify(result).includes(TOKEN), false);
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist alias checks passed\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
