// The page's fourth demo: the Remote DNA agent, live.
// The chat talks to the same agent the app's beta uses (agent/remote_agent.py, on our
// server, which holds the Gemini key: nothing secret is in this page). The agent may
// ask to send a code; only the visitor's click sends it, and here the "infrared" goes
// to a virtual TV that runs in this tab.
import { loadCatalogue } from './dna.js';
import { loadModels } from './models.js';
import { WANTED, virtualTv } from './agent.js';

const $ = (id) => document.getElementById(id);
const SERVER = 'https://remote-control-skyworth.onrender.com';
const NAMES = { volUp: 'volume up', volDown: 'volume down', chUp: 'channel up', chDown: 'channel down',
  ok: 'OK', back: 'back', mute: 'mute', menu: 'menu', power: 'power' };
const LANGS = ['ar', 'fr', 'en', 'es', 'pt', 'zh'];

let tv;
let thread = null;
let busy = false;

function say(who, text, cls = '') {
  const li = document.createElement('li');
  li.className = `a-${who} ${cls}`;
  const b = document.createElement('b');
  b.textContent = { you: 'You', agent: 'Agent', tv: 'TV', sys: '' }[who];
  li.append(b, document.createTextNode(who === 'agent' ? text.replace(/\*\*/g, '') : text));
  $('a-log').append(li);
  $('a-log').scrollTop = $('a-log').scrollHeight;
  return li;
}

function showTv(text, lit) {
  $('a-screen').textContent = text;
  $('a-tv').classList.toggle('lit', !!lit);
  if (lit) setTimeout(() => $('a-tv').classList.remove('lit'), 900);
}

/** The visitor approves, refuses, or edits one send (sends another button);
 *  nothing reaches the TV without it. Resolves to the decision for the server. */
function approve(button) {
  return new Promise((resolve) => {
    const li = say('sys', `The agent asks to send ${NAMES[button] ?? button}. `, 'ask');
    const yes = document.createElement('button');
    yes.className = 'primary';
    yes.textContent = 'Send';
    const no = document.createElement('button');
    no.textContent = "Don't send";
    const other = document.createElement('select');
    other.innerHTML = '<option value="">Send another button…</option>' +
      WANTED.filter((b) => b !== button).map((b) => `<option value="${b}">${NAMES[b] ?? b}</option>`).join('');
    const done = (decision, note) => {
      yes.remove(); no.remove(); other.remove();
      li.append(note);
      resolve(decision);
    };
    yes.onclick = () => done({ type: 'approve' }, 'Sent.');
    no.onclick = () => done({ type: 'reject' }, 'Refused.');
    other.onchange = () => other.value && done({ type: 'edit', button: other.value }, `Sent ${NAMES[other.value] ?? other.value} instead.`);
    li.append(yes, ' ', no, ' ', other);
  });
}

async function post(body) {
  const lang = (navigator.language || 'en').slice(0, 2);
  const res = await fetch(`${SERVER}/agent/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: thread, ...body,
      context: { language: LANGS.includes(lang) ? lang : 'en', phone_has_ir: true, country: 'DZ' } }),
  });
  const out = await res.json().catch(() => ({}));
  if (res.status === 429) throw new Error('Too many messages in a short time. Wait a minute, then send again.');
  if (!res.ok) throw new Error('The agent is busy right now. Send your message again in a few seconds.');
  return out;
}

/** One visitor message, then every send the agent asks for, until it waits for the visitor again. */
async function turn(text) {
  busy = true;
  $('a-send').disabled = true;
  say('you', text);
  const waking = setTimeout(() => say('sys', 'Waking the server: the first answer can take up to a minute.', 'note'), 5000);
  try {
    let out = await post({ message: text });
    clearTimeout(waking);
    for (let step = 0; step < 12; step++) {
      for (const s of out.send ?? []) {
        const seen = tv.receive(s.protocol, Number(s.address), Number(s.command));
        showTv(seen ? `▶ ${NAMES[seen] ?? seen}` : '…', !!seen);
        say('tv', seen ? `reacts: ${NAMES[seen] ?? seen}` : 'nothing happens', seen ? 'hit' : '');
      }
      if (out.reply) say('agent', out.reply);
      const confirmed = Object.keys(out.state?.confirmed ?? {});
      if (confirmed.length) $('a-state').textContent = confirmed.map((b) => NAMES[b] ?? b).join(' · ');
      if (!out.interrupt) break;
      const decision = await approve(out.interrupt.button);
      out = await post({ decision });
    }
  } catch (e) {
    clearTimeout(waking);
    say('sys', e.message, 'err');
  } finally {
    busy = false;
    $('a-send').disabled = false;
    $('a-text').focus();
  }
}

async function replay() {
  $('a-log').innerHTML = '';
  const steps = await (await fetch('./agent-session.json')).json();
  say('sys', `A real session, recorded on ${steps.recorded} with ${steps.model} and the same virtual TV.`, 'note');
  for (const s of steps.events) {
    await new Promise((r) => setTimeout(r, 700));
    if (s.tv !== undefined) {
      showTv(s.tv ? `▶ ${NAMES[s.tv] ?? s.tv}` : '…', !!s.tv);
      say('tv', s.tv ? `reacts: ${NAMES[s.tv] ?? s.tv}` : 'nothing happens', s.tv ? 'hit' : '');
    } else if (s.approve) say('sys', `The agent asks to send ${NAMES[s.approve] ?? s.approve}. Sent.`, 'ask');
    else say(s.who, s.text);
  }
  $('a-state').textContent = Object.keys(steps.confirmed ?? {}).map((b) => NAMES[b] ?? b).join(' · ');
}

function newThread() {
  const abc = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const r = crypto.getRandomValues(new Uint8Array(20));
  return 'web-' + [...r].map((x) => abc[x % abc.length]).join('');
}

try {
  const [cat, idx] = await Promise.all([
    fetch('../data/catalogue.json').then((r) => r.json()),
    fetch('../data/models.json').then((r) => r.json()),
  ]);
  tv = virtualTv(loadCatalogue(cat), loadModels(idx), '43G7200');
  showTv(`${tv.label} (virtual)`);

  $('a-replay').onclick = replay;
  $('a-start').onclick = () => {
    fetch(`${SERVER}/health`).catch(() => {}); // wake the server while the visitor types
    thread = newThread();
    $('a-state').textContent = '';
    $('a-log').innerHTML = '';
    $('a-live').hidden = false;
    say('sys', 'Live. Describe the TV, for example: "My Iris TV lost its remote. The label says MODEL: 43G7200".', 'note');
    $('a-text').focus();
  };
  $('a-form').onsubmit = (e) => {
    e.preventDefault();
    const t = $('a-text').value.trim();
    if (!t || busy || !thread) return;
    $('a-text').value = '';
    turn(t);
  };
} catch (e) {
  $('a-log').innerHTML = '<li class="err">The data could not be loaded. Open this page through a web server, not as a file.</li>';
}
