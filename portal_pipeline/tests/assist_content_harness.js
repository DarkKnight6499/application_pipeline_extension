/* Author: Yazad Madan. Synthetic DOM contracts without a browser or live CLI. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Config
const EXTENSION = path.join(__dirname, '..', 'extension');
const APPLICATION_URL = 'https://example.myworkdayjobs.com/apply';
const SYNTHETIC_TOKEN = 'synthetic-assist-token';
const SIGNATURE_LABEL = 'I verify that all of the information I have provided is true and accurate. (By typing your legal name in the box below you are affirming that you agree to this statement.)*';
const PROFILE_NAME = 'Synthetic Applicant';
const NUMBERED_LABEL = '1. Example employer asks the following questions about whether you were referred by an employee in the past year?*';

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
  focus() { this.events.push('focus'); }
  click() {
    this.events.push('click');
    if (this.type === 'checkbox') { this._checked = !this._checked; this.indeterminate = false; }
  }
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
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  const marker = '  scan();\n})();';
  assert.equal(source.split(marker).length, 2);
  const instrumented = source.replace(marker,
    '  globalThis.testAssist = {match, nativeSet, nonempty, fill, labelFor, members, safeClick, scan, groupOf, learnRows, currentAnswer, essayContext};\n})();');
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
  assert.deepEqual(JSON.parse(JSON.stringify(api.essayContext())), {});
  const heading = {closest: () => null, cloneNode: () => ({textContent: 'Quantitative Research Analyst', querySelectorAll: () => []})};
  document.querySelector = selector => selector.includes('h1') ? heading : null;
  assert.equal(api.essayContext().job_title, 'Quantitative Research Analyst');
  heading.cloneNode = () => ({textContent: 'x'.repeat(2000), querySelectorAll: () => []});
  assert.equal(api.essayContext().job_title.length, 300);
  assert.equal(api.essayContext().page_snippet.length, 1500);
  heading.cloneNode = () => {
    const copy = {textContent: 'ALM Analyst PRIVATE_FORM_VALUE'};
    copy.querySelectorAll = selector => {
      assert.match(selector, /input,textarea,select/);
      return [{remove() { copy.textContent = 'ALM Analyst'; }}];
    };
    return copy;
  };
  assert.equal(api.essayContext().page_snippet, 'ALM Analyst');
  heading.closest = () => ({});
  assert.deepEqual(JSON.parse(JSON.stringify(api.essayContext())), {});
  heading.closest = () => null;
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

  for (const value of ['', 'placeholder']) {
    const placeholder = new Select([{text: '-- Make a Selection --*', value, parentElement: {}},
      {text: 'Yes', value: 'yes', parentElement: {}}]);
    placeholder.value = value;
    assert.equal(api.nonempty(placeholder), false);
    assert.equal(api.currentAnswer(placeholder), '');
    assert.equal(await api.fill(placeholder, {candidates: ['-- Make a Selection --*']}, () => true), null);
    await api.fill(placeholder, {candidates: ['Yes']}, () => true);
    assert.equal(placeholder.value, 'yes');
  }
  const annual = new Input(); annual.labels = [{innerText: 'Did you apply in the past year?*'}];
  assert.equal(api.labelFor(annual), 'Did you apply in the past year?*');

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
  assert.equal(requests.at(-1).body.job_title, 'ALM Analyst');
  assert.equal(requests.at(-1).body.page_snippet, 'ALM Analyst');
  assert.equal(JSON.stringify(requests.at(-1)).includes('PRIVATE_FORM_VALUE'), false);
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
  assert.doesNotMatch(dockSummary.textContent, /already filled/);
  assert.match(dockSummary.textContent, /2 visible controls, 0 without labels/);
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

  // Learning covers every visible answer, typed, filled or already on the page (Simplify, last application); the review step gates saving.
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
  document.querySelector = selector => selector.includes('companyName') || selector.includes('h1') ? null : navigation[0];
  document.querySelectorAll = selector => selector.includes('input[type="text"]') ? learnFields : navigation;
  api.scan();
  const trust = node => listeners.input({target: node, isTrusted: true});
  scripted.value = 'Site update'; listeners.input({target: scripted, isTrusted: false});
  edited.value = 'Human project'; trust(edited);
  hidden.value = 'Hidden answer'; trust(hidden); hidden.getClientRects = () => [];
  long.value = 'x'.repeat(2001); trust(long);
  password.value = file.value = 'Never store'; trust(password); trust(file);
  generic.value = 'choice'; trust(generic);
  for (const node of protectedFields) { node.value = 'Synthetic reviewed answer'; trust(node); }
  assert.deepEqual(Array.from(api.learnRows(), row => [row.label, row.source]), [['Prefilled project', 'prefilled'], ['Site project', 'prefilled'], ['Preferred project', 'typed'],
    ['Please select one', 'typed'], ...blocked.filter(label => !['Password', 'SSN'].includes(label)).map(label => [label, 'typed'])]);

  for (const node of [...protectedFields, generic]) node.getClientRects = () => [];
  untouched.getClientRects = () => []; scripted.getClientRects = () => [];  // The review below follows the typed field only.
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
  assert.match(reviewLabel.children[1].textContent, /Company: Example Corp\nSource: typed\nchanged/);
  reviewLabel.children[0].checked = false;
  const beforeUntick = requests.length;
  await confirm.listeners.click(event(false));
  assert.equal(requests.length, beforeUntick);
  await learn.listeners.click(event(false));
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.at(-1).body.dry_run, false);
  assert.equal(requests.at(-1).body.pairs[0].previous_answer, 'Older answer');
  assert.match(review.textContent, /Stored 1 answers/);

  untouched.getClientRects = () => [{}];  // a page value is listed as prefilled and can be unticked
  await learn.listeners.click(event(false));
  assert.equal(review.children.length, 3);
  assert.match(review.children[0].children[0].children[1].textContent, /Source: prefilled/);
  review.children[0].children[0].children[0].checked = false;
  await review.children.at(-1).listeners.click(event(false));
  assert.equal(requests.at(-1).body.pairs.length, 1);
  assert.equal(requests.at(-1).body.pairs[0].label, 'Preferred project');
  assert.equal(untouched.value, 'Site prefill');
  untouched.getClientRects = () => []; untouched.isConnected = false;

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
  assert.deepEqual(Array.from(api.learnRows(), row => [row.answer, row.source]), [['Site rewrite', 'prefilled']]);

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
  assert.deepEqual(Array.from(api.learnRows(), row => row.source), ['prefilled']);

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
  let profileName = PROFILE_NAME;
  let listener;
  const context = vm.createContext({URL, AbortSignal, chrome: {runtime: {id: 'synthetic-extension',
    onMessage: {addListener(value) { listener = value; }}}, storage: {local: {get: async () => ({assistToken: SYNTHETIC_TOKEN,
      server: 'http://127.0.0.1:8765', token: SYNTHETIC_TOKEN})}}}, fetch: async (url, options) => {
      calls.push({url, options}); return {ok: true, json: async () => url.endsWith('/api/profile')
        ? {values: {full_name: {value: profileName}, email: {value: 'private@example.test'}}}
        : {status: 'stored', answer: 'Example answer'}};
    }});
  vm.runInContext(source, context);
  const send = (message, sender) => new Promise(resolve => listener(message, sender, resolve));
  const sender = {id: 'synthetic-extension', frameId: 0, tab: {}, url: APPLICATION_URL};
  const message = {type: 'portal-assist-answer', body: {label: 'Example question', host: 'forged.example', url: 'forged',
    job_title: 'ALM Analyst', page_snippet: 'ALM Analyst'}};
  const answer = await send(message, sender);
  assert.equal(answer.ok, true);
  assert.equal(calls[0].url, 'http://127.0.0.1:8766/assist/answer');
  assert.equal(calls[0].options.headers['X-Assist-Token'], SYNTHETIC_TOKEN);
  assert.equal(JSON.parse(calls[0].options.body).url, APPLICATION_URL);
  assert.equal(JSON.parse(calls[0].options.body).job_title, 'ALM Analyst');
  assert.equal(JSON.parse(calls[0].options.body).page_snippet, 'ALM Analyst');
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
  const signature = {type: 'portal-assist-full-name', body: {label: SIGNATURE_LABEL}};
  const name = await send(signature, sender);
  assert.equal(name.ok, true);
  assert.equal(name.value.answer, PROFILE_NAME);
  assert.equal(calls.at(-1).url, 'http://127.0.0.1:8765/api/profile');
  assert.equal(calls.at(-1).options.headers['X-Portal-Token'], SYNTHETIC_TOKEN);
  assert.equal(JSON.stringify(name).includes('private@example.test'), false);
  profileName = null;
  assert.equal((await send(signature, sender)).value.status, 'none');
  profileName = {value: PROFILE_NAME};
  assert.equal((await send(signature, sender)).value.status, 'none');
  const beforeInvalid = calls.length;
  for (const invalid of [{...sender, id: 'other-extension'}, {...sender, tab: null},
    {...sender, url: 'https://unrelated.example/apply'}, {...sender, url: 'http://example.myworkdayjobs.com/apply'}]) {
    assert.equal((await send(signature, invalid)).ok, false);
  }
  assert.equal(calls.length, beforeInvalid);
}

async function plainFormChecks() {
  const shadows = [], requests = [];
  let fields = [], fullName = PROFILE_NAME;
  const document = {documentElement: {}, body: {append() {}}, querySelectorAll: () => fields,
    querySelector: () => null, getElementById: () => null, addEventListener() {},
    createElement: tag => new AssistElement(tag, shadows)};
  const context = vm.createContext({document, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    Event, Node: {ELEMENT_NODE: 1, TEXT_NODE: 3}, HTMLInputElement: Input, HTMLTextAreaElement: Textarea,
    HTMLSelectElement: Select, getComputedStyle: () => ({visibility: 'visible'}),
    MutationObserver: class {observe() {}}, chrome: {runtime: {sendMessage(message, callback) {
      requests.push(message);
      const answer = message.type === 'portal-assist-full-name' ? fullName : '';
      callback({ok: true, value: {status: answer ? 'stored' : 'none', answer, candidates: answer ? [answer] : []}});
    }}}});
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  vm.runInContext(source.replace('  scan();\n})();',
    '  globalThis.testAssist = {scan, labelFor, learnRows, currentAnswer, nonempty, choices, fill};\n})();'), context);
  const api = context.testAssist;
  const leaf = (tag, value, help = false) => ({tagName: tag.toUpperCase(), innerText: value,
    textContent: value, nodeType: 1, isConnected: true, getClientRects: () => [{}], closest: () => null,
    matches: selector => help && selector.includes('.help'), querySelector: () => null,
    cloneNode: () => ({textContent: value, querySelectorAll: () => []})});
  const plain = (tag, label, dedicated = false) => {
    const input = new Input(), question = leaf(tag, label), help = leaf('span', 'Help text', true);
    const container = {closest: () => null, matches: selector => selector.includes('div'),
      querySelectorAll: selector => selector.startsWith('input:') ? [input] : dedicated ? [question] : []};
    input.parentElement = container; input.previousSibling = help; help.previousSibling = question;
    return input;
  };
  const cell = plain('td', NUMBERED_LABEL), sibling = plain('span', 'Sibling question*');
  const previousCell = cell.previousSibling.previousSibling;
  const row = cell.parentElement;
  row.matches = selector => selector.includes('tr');
  const answerCell = {parentElement: row, previousSibling: previousCell, closest: () => null,
    matches: () => false, querySelectorAll: () => [cell]};
  cell.parentElement = answerCell; cell.previousSibling = null;
  const dedicated = plain('div', 'Dedicated question*', true);
  const precedingLabel = plain('label', 'Preceding question*');
  for (const [field, label] of [[cell, NUMBERED_LABEL], [sibling, 'Sibling question*'],
    [dedicated, 'Dedicated question*'], [precedingLabel, 'Preceding question*']]) {
    assert.equal(api.labelFor(field), label);
    field.value = 'Captured answer';
  }
  const ambiguous = plain('span', 'Wrong question');
  ambiguous.parentElement.querySelectorAll = () => [ambiguous, new Input()];
  assert.equal(api.labelFor(ambiguous), '');
  const raw = new Input();
  raw.parentElement = {closest: () => null, matches: selector => selector.includes('div'),
    querySelectorAll: selector => selector.startsWith('input:') ? [raw] : []};
  raw.previousSibling = {nodeType: 3, textContent: 'Preceding text question*'};
  assert.equal(api.labelFor(raw), 'Preceding text question*');
  const annual = new Input(); annual.labels = [{innerText: 'Did you apply in the past year?*'}];
  assert.equal(api.labelFor(annual), 'Did you apply in the past year?*');
  for (const value of ['', 'placeholder']) {
    const select = new Select([{text: '-- Make a Selection --*', value, parentElement: {}},
      {text: 'Yes', value: 'yes', parentElement: {}}]);
    select.labels = [{innerText: 'Placeholder question'}]; select.value = value;
    assert.equal(api.nonempty(select), false);
    assert.equal(api.currentAnswer(select), '');
    assert.deepEqual(Array.from(api.choices(select), option => option.text), ['Yes']);
    fields = [select];
    assert.equal(api.learnRows(true).length, 0);
    assert.equal(await api.fill(select, {candidates: ['-- Make a Selection --*']}, () => true), null);
    await api.fill(select, {candidates: ['Yes']}, () => true);
    assert.equal(select.value, 'yes');
  }
  const signature = new Input(); signature.labels = [{innerText: SIGNATURE_LABEL}];
  const unknown = new Input(); unknown.labels = [{innerText: 'Unknown question*'}];
  const bare = new Input();
  fields = [cell, sibling, dedicated, precedingLabel, signature, unknown, bare];
  api.scan();
  assert.deepEqual(Array.from(api.learnRows(true), row => row.label),
    [NUMBERED_LABEL, 'Sibling question*', 'Dedicated question*', 'Preceding question*']);
  const [, button, summary] = shadows[0].children;
  await button.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.equal(signature.value, PROFILE_NAME);
  assert.equal(unknown.value, '');
  assert.match(summary.textContent, /filled 1, left alone 4/);
  assert.match(summary.textContent, /7 visible controls, 1 without labels/);
  assert.match(summary.textContent, /Unknown question\*: no answer/);
  assert.doesNotMatch(summary.textContent, /already filled/);
  assert.equal(requests.find(message => message.type === 'portal-assist-full-name').body.label, SIGNATURE_LABEL);
  signature.value = ''; fullName = '';
  await button.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.equal(signature.value, '');
  assert.match(summary.textContent, /I verify.*: no answer/);
  for (const field of fields) field.isConnected = false;
  const checked = new Input('checkbox'); checked.labels = [{innerText: SIGNATURE_LABEL}];
  fields = [checked]; api.scan();
  const beforeCheckbox = requests.length;
  await button.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.equal(requests.slice(beforeCheckbox).some(message => message.type === 'portal-assist-full-name'), false);
  checked.isConnected = false;
  bare.isConnected = true;
  fields = [bare];
  for (const field of [cell, sibling, dedicated, precedingLabel, signature, unknown]) field.isConnected = false;
  await button.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.match(summary.textContent, /filled 0, left alone 0\n1 visible controls, 1 without labels/);
  process.stdout.write('Plain form regression checks passed\n');
}

async function checkboxChecks() {
  const shadows = [], requests = [];
  let fields = [];
  const document = {documentElement: {}, body: {append() {}},
    querySelectorAll: selector => fields.filter(node => node.type === 'checkbox' || selector.includes('[role="checkbox"]')),
    querySelector: () => null, getElementById: () => null, addEventListener() {},
    createElement: tag => new AssistElement(tag, shadows)};
  const context = vm.createContext({document, location: new URL(APPLICATION_URL), setTimeout, clearTimeout,
    Event, MouseEvent: Event, PointerEvent: Event, Node: {ELEMENT_NODE: 1}, HTMLInputElement: Input,
    HTMLTextAreaElement: Textarea, HTMLSelectElement: Select, getComputedStyle: () => ({visibility: 'visible'}),
    MutationObserver: class {observe() {}}, chrome: {runtime: {sendMessage(message, callback) {
      requests.push(message);
      callback({ok: true, value: {status: 'stored', answer: 'Yes', candidates: ['Yes']}});
    }}}});
  const source = fs.readFileSync(path.join(EXTENSION, 'assist-content.js'), 'utf8').replace(/\r\n/g, '\n');
  vm.runInContext(source.replace('  scan();\n})();', '  globalThis.testAssist = {scan, fill};\n})();'), context);
  const api = context.testAssist;
  const box = label => {
    const node = new Input('checkbox');
    node.labels = [{innerText: label}]; node.indeterminate = false; node.clicks = 0;
    node.focus = () => node.events.push('focus');
    node.click = () => {
      node.clicks += 1; node.events.push('click');
      node.checked = !node.checked; node.indeterminate = false;
      node.frameworkChecked = node.checked;
    };
    return node;
  };
  const native = box('Yes, I have read and consent to the terms and conditions *');
  await api.fill(native, {candidates: ['Yes']}, () => true);
  assert.equal(native.frameworkChecked, true);
  assert.deepEqual(native.events, ['focus', 'click']);
  assert.equal(native.clicks, 1);
  await api.fill(native, {candidates: ['Yes']}, () => true);
  assert.equal(native.clicks, 1);
  const mixed = box('I attest this is true'); mixed.indeterminate = true;
  await api.fill(mixed, {candidates: ['Yes']}, () => true);
  assert.equal(mixed.checked, true); assert.equal(mixed.indeterminate, false);
  const checkedMixed = box('Consent'); checkedMixed.checked = true; checkedMixed.indeterminate = true;
  await api.fill(checkedMixed, {candidates: ['Yes']}, () => true);
  assert.equal(checkedMixed.checked, true); assert.equal(checkedMixed.indeterminate, false);
  assert.equal(checkedMixed.clicks, 0);
  const custom = box('SMS opt-in'); custom.tagName = 'DIV'; custom.type = undefined;
  custom.attributes.role = 'checkbox'; custom.attributes['aria-checked'] = 'mixed';
  custom.click = () => { custom.clicks += 1; custom.events.push('click'); custom.attributes['aria-checked'] = 'true'; };
  await api.fill(custom, {candidates: ['Yes']}, () => true);
  assert.equal(custom.attributes['aria-checked'], 'true'); assert.equal(custom.clicks, 1);
  assert.deepEqual(custom.events, ['focus', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']);
  await api.fill(custom, {candidates: ['Yes']}, () => true);
  assert.equal(custom.clicks, 1);
  const hidden = box('Terms'); hidden.getClientRects = () => [];
  const wrapper = box('Terms'); wrapper.tagName = 'LABEL'; wrapper.type = undefined;
  wrapper.click = () => { wrapper.clicks += 1; hidden.click(); };
  hidden.attributes['aria-label'] = 'Terms'; hidden.labels = []; hidden.parentElement = wrapper;
  wrapper.querySelectorAll = () => [hidden]; wrapper.innerText = 'Terms';
  await api.fill(hidden, {candidates: ['Yes']}, () => true);
  assert.equal(hidden.frameworkChecked, true); assert.equal(wrapper.clicks, 1);
  const labelled = box('Label consent'); labelled.getClientRects = () => [];
  const label = box('Label consent'); label.tagName = 'LABEL'; label.innerText = 'Label consent';
  label.click = () => { label.clicks += 1; labelled.click(); }; labelled.labels = [label];
  await api.fill(labelled, {candidates: ['Yes']}, () => true);
  assert.equal(labelled.frameworkChecked, true); assert.equal(label.clicks, 1);
  const retry = box('Retry consent'); retry.click = () => { if (++retry.clicks === 2) retry.checked = true; };
  await api.fill(retry, {candidates: ['Yes']}, () => true);
  assert.equal(retry.checked, true); assert.equal(retry.clicks, 2);
  const failed = box('Failed consent'); failed.click = () => { failed.clicks += 1; };
  const ariaFailed = box('Invalid consent'); ariaFailed.attributes['aria-checked'] = 'mixed';
  const kept = box('Already accepted'); kept.checked = true;
  const protectedFields = ['Password', 'CAPTCHA', 'OTP', 'SSN', 'Credit card', 'Bank account'].map(box);
  fields = [native, mixed, custom, hidden, failed, ariaFailed, kept, ...protectedFields];
  native.checked = false; mixed.checked = false; mixed.indeterminate = true;
  custom.attributes['aria-checked'] = 'false'; hidden.checked = false;
  api.scan();
  const [, button, summary] = shadows[0].children;
  await button.listeners.click({preventDefault() {}, stopPropagation() {}});
  assert.equal(native.checked, true); assert.equal(mixed.checked, true);
  assert.equal(custom.attributes['aria-checked'], 'true'); assert.equal(hidden.checked, true);
  assert.equal(failed.clicks, 2); assert.equal(ariaFailed.clicks, 1);
  assert.equal(kept.checked, true); assert.equal(kept.clicks, 0);
  for (const node of protectedFields) { assert.equal(node.checked, false); assert.equal(node.clicks, 0); }
  assert.match(summary.textContent, /Failed consent: checkbox not retained/);
  assert.match(summary.textContent, /Invalid consent: checkbox not retained/);
  assert.equal(summary.hidden, false);
  assert.equal(requests.filter(message => message.type === 'portal-assist-miss').length, 2);
  process.stdout.write('Checkbox regression checks passed\n');
}

(async () => {
  if (process.argv.includes('--checkboxes')) { await checkboxChecks(); return; }
  await plainFormChecks();
  if (process.argv.includes('--plain-forms')) {
    await workerChecks();
    process.stdout.write('Worker regression checks passed\n');
    return;
  }
  await contentChecks();
  await workerChecks();
  process.stdout.write('Assist content and worker checks passed (2 suites)\n');
})().catch(error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
