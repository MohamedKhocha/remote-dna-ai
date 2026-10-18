// The page's second and third demos: the deep search with a real tap, and
// the model-number search. The algorithms live in sweep.js and models.js.
import { loadCatalogue } from './dna.js';
import { loadModels, candidates, search } from './models.js';
import { LOOKBACK_MS, batchCandidates, runBatch, sendMs, settle, suspects, sweepCandidates } from './sweep.js';

const $ = (id) => document.getElementById(id);
const hex = (c) => '0x' + c.toString(16).toUpperCase().padStart(2, '0');
const PROTOCOL = { nec: 'NEC', samsung32: 'Samsung32', rc6: 'RC6', rc5: 'RC5', sirc: 'Sony', necext: 'NECext' };
const where = (c) => `${PROTOCOL[c.protocol] ?? c.protocol} ${hex(c.address)}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------ deep search */

let sweep = [];
let batch = [];
let air = [];
let tv = null; // { cand, knows, channel }
let run = null; // the sweep in progress

function hideTv() {
  // A TV on an address of the first pass: it knows the first number key.
  const firstPass = batch.length;
  const i = Math.floor(Math.random() * firstPass);
  const cand = sweep[i];
  tv = { cand, knows: cand.probes[0], channel: 1 + Math.floor(Math.random() * 40) };
  $('tv-ch').textContent = 'CH ' + tv.channel;
  $('tv-note').textContent = 'The hidden TV listens on one of 720 addresses. Its address appears at the end.';
  $('d-log').innerHTML = '';
  $('d-result').textContent = '';
  $('d-bar').style.width = '0';
  $('d-now').textContent = `${sweep.length.toLocaleString('en')} sends to try. Press start and watch the TV.`;
  $('d-start').disabled = false;
  $('d-saw').disabled = true;
}

function flashTv() {
  // What a real TV does with a number key: it shows the new channel number.
  tv.channel = tv.knows % 10 || 10;
  $('tv-ch').textContent = 'CH ' + tv.channel;
  $('tv-osd').textContent = String(tv.channel);
  $('tv-osd').classList.add('on');
  setTimeout(() => $('tv-osd').classList.remove('on'), 1500);
}

const hits = (i) => {
  const c = sweep[i];
  return c.protocol === tv.cand.protocol && c.address === tv.cand.address && c.probes.includes(tv.knows);
};

function log(text, cls = '') {
  const li = document.createElement('li');
  if (cls) li.className = cls;
  li.textContent = text;
  $('d-log').prepend(li);
}

/** Send from `cursor` in real time until the tap or the end of the list. */
function startSweep(cursor = 0, answers = 0) {
  const speed = Number($('d-speed').value);
  run = { cursor, answers, speed, sentAt: new Map(), t0: performance.now(), clock: 0, tap: null, raf: 0 };
  $('d-start').disabled = $('d-new').disabled = true;
  $('d-saw').disabled = false;
  const tick = () => {
    const now = (performance.now() - run.t0) * run.speed;
    while (run.cursor < sweep.length && run.clock <= now) {
      const i = run.cursor;
      run.sentAt.set(i, run.clock);
      run.clock += air[i];
      run.cursor++;
      if (hits(i)) setTimeout(flashTv, air[i] / run.speed);
      const c = sweep[i];
      $('d-now').textContent = `Sending ${where(c)}, key ${hex(c.probes[0])} · ${i + 1} of ${sweep.length.toLocaleString('en')}`;
    }
    $('d-bar').style.width = `${(100 * run.cursor) / sweep.length}%`;
    if (run.cursor >= sweep.length) return finish(null);
    run.raf = requestAnimationFrame(tick);
  };
  run.raf = requestAnimationFrame(tick);
}

async function sawIt() {
  if (!run || run.tap !== null) return;
  run.tap = (performance.now() - run.t0) * run.speed;
  cancelAnimationFrame(run.raf);
  $('d-saw').disabled = true;
  const group = suspects(run.sentAt, run.tap, LOOKBACK_MS * run.speed);
  run.answers += 1;
  log(`Your tap: the ${group.length} sends of the ${((LOOKBACK_MS * run.speed) / 1000).toFixed(0)} s before it are suspects.`);
  const reacts = (g) => g.some(hits);
  const out = settle(group, reacts, () => 0);
  for (const [n, step] of out.steps.entries()) {
    await sleep(900);
    const what = step.group.length === 1 ? `${where(sweep[step.group[0]])} alone` : `${step.group.length} of them`;
    const kind = n === 0 ? 'Replay' : step.group.length === 1 && n === out.steps.length - 1 ? 'Confirm' : 'Halve: send';
    if (step.reacted) flashTv();
    log(`${kind} ${what}: ${step.reacted ? 'the TV reacted' : 'nothing'}`, step.reacted ? 'hit' : '');
  }
  run.answers += out.answers;
  await sleep(600);
  if (out.found === null) {
    log('Nothing on the replay: a stray or very late tap. The sweep carries on after the window.');
    return startSweep(Math.max(...group) + 1, run.answers);
  }
  finish(out.found);
}

function finish(found) {
  const answers = run.answers;
  run = null;
  $('d-saw').disabled = true;
  $('d-new').disabled = $('d-start').disabled = false;
  const at = where(tv.cand);
  if (found === null) {
    $('d-result').textContent = `The sweep ended without finding the TV (it was on ${at}). A tap more than 3 s late misses it.`;
  } else {
    const same = batch.find((c) => c.protocol === tv.cand.protocol && c.address === tv.cand.address);
    const b = runBatch(batch, same, tv.knows);
    $('d-result').textContent =
      `Found: ${where(sweep[found])} in ${answers} answers, the tap included. ` +
      `The old batch search would have asked ${b.answers} questions for this TV.`;
  }
  $('tv-note').textContent = `The hidden TV was on ${at}.`;
}

/* ---------------------------------------------------------- model search */

let models = [];
const EXAMPLES = [
  ['43G7200', '43G7200'],
  ['G7200 (no size)', 'G7200'],
  ['55U6K', '55U6K'],
  ['5SU6K (misread)', '5SU6K'],
  ['A real label', 'ATTENTION:\nPOUR EVITER UN CHOC ELECTRIQUE, NE PAS ENLEVER LE COUVERT.\n43G7200\nIRIS\nALIMENTATION : 100-240V~50/60Hz 95W'],
  ['Model No.: 43E6A', 'IRIS\nLED TV\nModel No.: 43E6A'],
];

function showModels() {
  const text = $('m-text').value;
  const read = candidates(text);
  $('m-read').textContent = text.trim()
    ? read.length
      ? `Read as a model number: ${read.slice(0, 3).join(', ')}`
      : 'No model number found: four or more letters and digits, not a voltage or a serial number.'
    : '';
  const list = $('m-hits');
  list.innerHTML = '';
  const found = search(text, models, null, 5);
  if (text.trim() && read.length && !found.length) {
    const li = document.createElement('li');
    li.textContent = 'No remote known for this model yet. In the app, "Teach my TV" finds it, and sharing it afterwards adds the model.';
    list.append(li);
  }
  for (const { model, score } of found) {
    const li = document.createElement('li');
    const left = document.createElement('div');
    const name = document.createElement('b');
    name.textContent = `${model.brand} ${model.label}`;
    const what = document.createElement('div');
    what.className = 'what';
    what.textContent =
      (model.wifi ? 'Android TV: controlled over Wi-Fi in the app' : `Infrared remote: ${where(model)}`) +
      (model.field ? ' · tested on a real TV' : ' · from Flipper-IRDB');
    left.append(name, what);
    const s = document.createElement('span');
    s.className = 'score';
    s.textContent = `${Math.round(score * 100)}%`;
    li.append(left, s);
    list.append(li);
  }
}

/* ----------------------------------------------------------------- start */

try {
  const [cat, idx] = await Promise.all([
    fetch('../data/catalogue.json').then((r) => r.json()),
    fetch('../data/models.json').then((r) => r.json()),
  ]);
  const remotes = loadCatalogue(cat);
  sweep = sweepCandidates(remotes);
  batch = batchCandidates(remotes);
  air = sweep.map(sendMs);
  models = loadModels(idx);

  hideTv();
  $('d-start').onclick = () => {
    $('d-log').innerHTML = '';
    $('d-result').textContent = '';
    startSweep();
  };
  $('d-saw').onclick = sawIt;
  $('d-new').onclick = hideTv;
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && run && run.tap === null) {
      e.preventDefault();
      sawIt();
    }
  });

  const ex = $('m-examples');
  for (const [label, text] of EXAMPLES) {
    const b = document.createElement('button');
    b.textContent = label;
    b.onclick = () => {
      $('m-text').value = text;
      showModels();
    };
    ex.append(b);
  }
  $('m-text').oninput = showModels;
  $('m-text').value = '43G7200';
  showModels();
} catch (e) {
  $('d-now').innerHTML = '<span class="err">The data could not be loaded. Open this page through a web server, not as a file.</span>';
}
