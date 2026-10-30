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
    this.attributes = {}; this.isConnected = true; this.shadows = shadows; this.style = {};
    this.children = [];
  }
  attachShadow(options) {
    assert.equal(options.mode, 'closed');
    const root = {children: [], append(...children) { this.children.push(...children); }};
    this.shadows.push(root);
    return root;
  }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.textContent = ''; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  remove() { this.isConnected = false; }
}

async function contentChecks() {
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8');
  const marker = '  scan();\n})();';
  assert.equal(source.split(marker).length, 2);
  const instrumented = source.replace(marker,
    '  globalThis.testAssist = {match, nativeSet, nonempty, fill, labelFor, members, safeClick, scan, groupOf, learnRows, currentAnswer};\n})();');
  const shadows = [];
  const requests = [];
  const listeners = {};
  const document = {documentElement: {}, body: {append(host) { host.isConnected = true; }}, querySelectorAll: () => [], querySelector: () => null,
    addEventListener(type, listener) { listeners[type] = listener; }, createTextNode: value => ({textContent: value}),
    getElementById: () => null, createElement: tag => new AssistElement(tag, shadows)};
  let storedResponse = {status: 'stored', answer: 'Example answer', candidates: ['Example answer']};
  let delayResponse = false;
  let pendingResponse;
  let learnStatus = 'new';
  const runtime = {sendMessage(message, callback) {
    requests.push(message);
    if (delayResponse) pendingResponse = callback;
    else if (message.type === 'portal-assist-learn') callback({ok: true, value: {scope: 'Example Corp',
      results: message.body.pairs.map(pair => ({...pair, status: learnStatus,
        previous_answer: learnStatus === 'changed' ? 'Older answer' : null, stored: !message.body.dry_run}))}});
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
  assert.equal(api.currentAnswer(select), 'Example option');

  const checkbox = new Input('checkbox');
  await api.fill(checkbox, {candidates: ['Yes']}, () => true);
  assert.equal(checkbox.checked, true);
  await api.fill(checkbox, {candidates: ['No']}, () => true);
  assert.equal(checkbox.checked, false);
  assert.equal(api.currentAnswer(checkbox), 'No');

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
  assert.equal(api.currentAnswer(yes), 'No');

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
  assert.equal(shadows.length, 2);
  const [, button, badge, save] = shadows[1].children;
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
  assert.equal(shadows.length, 3);

  // Page button: fills empty fields only and reports what it left alone.
  replacement.isConnected = false;
  const keep = new Input(); keep.labels = [{innerText: 'Kept question'}]; keep.value = 'Typed by hand';
  const empty = new Input(); empty.labels = [{innerText: 'Open question'}];
  storedResponse = {status: 'stored', answer: 'Example answer', candidates: ['Example answer']};
  document.querySelectorAll = () => [keep, empty];
  api.scan();
  const [, dockButton, dockSummary] = shadows[0].children;
  const requestsBefore = requests.length;
  await dockButton.listeners.click(event(false));
  assert.equal(keep.value, 'Typed by hand'); assert.equal(empty.value, 'Example answer');
  assert.equal(requests.length, requestsBefore + 1);
  assert.match(dockSummary.textContent, /filled 1, left alone 1/);
  assert.equal(dockSummary.hidden, false);

  // Month, day and year inputs form one field and are filled together.
  const month = new Input(); const day = new Input(); const year = new Input();
  month.attributes['aria-label'] = 'Month'; day.attributes['aria-label'] = 'Day'; year.attributes['aria-label'] = 'Year';
  const dateGroup = {querySelector: () => ({innerText: 'When would you be available to start?'}),
    querySelectorAll: () => [month, day, year], getAttribute: () => null};
  month.group = day.group = year.group = dateGroup;
  assert.equal(api.groupOf(day).length, 3);
  assert.equal(api.labelFor(day), 'When would you be available to start?');
  await api.fill(month, {answer: '12/01/2026', candidates: []}, () => true);
  assert.deepEqual([month.value, day.value, year.value], ['12', '01', '2026']);
  assert.equal(api.nonempty(year), true);
  day.value = ''; year.value = '';
  assert.equal(await api.fill(month, {answer: 'Immediately', candidates: []}, () => true), null);
  assert.deepEqual([day.value, year.value], ['', '']);
  const city = new Input(); const zip = new Input(); city.attributes['aria-label'] = 'City'; zip.attributes['aria-label'] = 'Zip';
  const pair = {querySelector: () => null, querySelectorAll: () => [city, zip], getAttribute: () => null};
  city.group = zip.group = pair;
  assert.equal(api.groupOf(city).length, 1);

  // Learning requires a trusted edit or retained Fill, never a site-only write.
  keep.isConnected = empty.isConnected = false;
  const untouched = new Input(); untouched.labels = [{innerText: 'Prefilled project'}]; untouched.value = 'Site prefill';
  const scripted = new Input(); scripted.labels = [{innerText: 'Site project'}];
  const edited = new Input(); edited.labels = [{innerText: 'Preferred project'}];
  const filled = new Input(); filled.labels = [{innerText: 'Project experience'}];
  const hidden = new Input(); hidden.labels = [{innerText: 'Hidden project'}];
  const blank = new Input(); blank.labels = [{innerText: 'Empty project'}];
  const long = new Input(); long.labels = [{innerText: 'Length project'}];
  const blocked = ['Password', 'SSN', 'Signature', 'I attest this is true', 'Need sponsorship?', 'Authorized to work?',
    'Eligible for employment?', 'Veteran status', 'Disability', 'Gender', 'Race or ethnicity', 'Nationality', 'Pronouns'];
  const protectedFields = blocked.map(label => { const node = new Input(); node.labels = [{innerText: label}]; return node; });
  const password = new Input('password'); password.labels = [{innerText: 'Secret project'}];
  const file = new Input('file'); file.labels = [{innerText: 'Project file'}];
  const generic = new Select([{text: 'Select one', value: '', parentElement: {}},
    {text: 'Female', value: 'choice', parentElement: {}}]);
  generic.labels = [{innerText: 'Please select one'}];
  const learnFields = [untouched, scripted, edited, filled, hidden, blank, long, password, file, generic, ...protectedFields];
  let navigationClicks = 0;
  const navigation = ['Next', 'Continue', 'Submit'].map(innerText => ({innerText, click() { navigationClicks += 1; }}));
  document.querySelector = selector => selector.includes('companyName') ? null : navigation[0];
  document.querySelectorAll = selector => selector.includes('input[type="text"]') ? learnFields : navigation;
  api.scan();
  const trust = node => listeners.input({target: node, isTrusted: true});
  scripted.value = 'Site update'; listeners.input({target: scripted, isTrusted: false});
  edited.value = 'Human project'; trust(edited);
  hidden.value = 'Hidden answer'; trust(hidden); hidden.getClientRects = () => [];
  long.value = 'x'.repeat(2001); trust(long);
  password.value = file.value = 'Never store'; trust(password); trust(file);
  generic.value = 'choice'; trust(generic);
  for (const node of protectedFields) { node.value = 'Never learn'; trust(node); }
  assert.deepEqual(Array.from(api.learnRows(), row => row.label), ['Preferred project']);

  const [, , , learn, review] = shadows[0].children;
  assert.equal(learn.textContent, 'Learn page');
  assert.equal(learn.type, 'button');
  learnStatus = 'changed';
  await learn.listeners.click(event(false));
  assert.equal(requests.at(-1).body.dry_run, true);
  assert.equal(requests.at(-1).body.pairs[0].answer, 'Human project');
  const [reviewLine, confirm] = review.children;
  assert.equal(confirm.type, 'button');
  const reviewLabel = reviewLine.children[0];
  assert.equal(reviewLabel.children[0].checked, true);
  assert.match(reviewLabel.children[1].textContent, /Company: Example Corp\nchanged/);
  reviewLabel.children[0].checked = false;
  const beforeUntick = requests.length;
  await confirm.listeners.click(event(false));
  assert.equal(requests.length, beforeUntick);
  await learn.listeners.click(event(false));
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.at(-1).body.dry_run, false);
  assert.equal(requests.at(-1).body.pairs[0].previous_answer, 'Older answer');
  assert.match(review.textContent, /Stored 1 answers/);

  untouched.value = 'Edited prefill'; trust(untouched);
  await learn.listeners.click(event(false));
  assert.equal(review.children.length, 3);
  review.children[0].children[0].children[0].checked = false;
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.at(-1).body.pairs.length, 1);
  assert.equal(requests.at(-1).body.pairs[0].label, 'Preferred project');
  assert.equal(untouched.value, 'Edited prefill');
  untouched.isConnected = false;

  await learn.listeners.click(event(false));
  const beforeChanged = requests.length;
  edited.value = 'Edited after review'; trust(edited);
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.length, beforeChanged);
  assert.match(review.textContent, /Page answers changed/);
  edited.value = 'Human project'; trust(edited);
  await learn.listeners.click(event(false));
  const beforeAutomation = requests.length;
  context.PortalAutomationFilling = true;
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.length, beforeAutomation);
  context.PortalAutomationFilling = false;
  delayResponse = true;
  const learning = learn.listeners.click(event(false));
  context.PortalAutomationFilling = true;
  pendingResponse({ok: true, value: {scope: 'Example Corp', results: []}});
  await learning;
  assert.equal(review.children.length, 0);
  context.PortalAutomationFilling = false;
  delayResponse = false;
  edited.value = 'Site rewrite';
  assert.equal(api.learnRows().length, 0);

  // A Fill answer remains eligible even when it equals the first-scan value.
  const fillSame = new Input(); fillSame.labels = [{innerText: 'Retained project'}]; fillSame.value = 'Example answer';
  learnFields.forEach(node => { node.isConnected = false; });
  document.querySelectorAll = () => [fillSame];
  api.scan();
  const sameButton = shadows.at(-1).children[1];
  await sameButton.listeners.click(event(true));
  assert.deepEqual(Array.from(api.learnRows(), row => row.answer), ['Example answer']);
  fillSame.value = 'User revision'; listeners.change({target: fillSame, isTrusted: true});
  assert.deepEqual(Array.from(api.learnRows(), row => row.answer), ['User revision']);
  fillSame.value = 'Example answer'; trust(fillSame);
  assert.equal(api.learnRows().length, 0);

  const many = Array.from({length: 81}, (_, index) => {
    const node = new Input(); node.labels = [{innerText: `Project ${index}`}]; return node;
  });
  fillSame.isConnected = false;
  document.querySelectorAll = () => many;
  api.scan();
  many.forEach(node => { node.value = 'Example project'; trust(node); });
  const beforeLimit = requests.length;
  await learn.listeners.click(event(false));
  assert.equal(requests.length, beforeLimit);
  assert.match(review.textContent, /More than 80/);
  assert.equal(navigationClicks, 0);

  context.PortalAutomationFilling = true;
  await learn.listeners.click(event(false));
  assert.equal(requests.length, beforeLimit);
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
  const learn = {type: 'portal-assist-learn', body: {pairs: [{label: 'Example project', answer: 'Example answer'}],
    dry_run: true, host: 'forged.example', url: 'https://forged.example'}};
  assert.equal((await send(learn, sender)).ok, true);
  assert.equal(calls[2].url, 'http://127.0.0.1:8766/assist/learn');
  const learned = JSON.parse(calls[2].options.body);
  assert.equal(learned.host, 'example.myworkdayjobs.com'); assert.equal(learned.url, APPLICATION_URL);
  assert.equal(learned.dry_run, true);
  for (const invalid of [{...sender, id: 'other-extension'}, {...sender, tab: null},
    {...sender, url: 'https://unrelated.example/apply'}, {...sender, url: 'http://example.myworkdayjobs.com/apply'}]) {
    assert.equal((await send(learn, invalid)).ok, false);
  }
  assert.equal(calls.length, 3);
}

(async () => {
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist content and worker checks passed (2 suites)\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
