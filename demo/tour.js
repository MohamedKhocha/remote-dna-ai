// The app's screens as a small player (play, pause, full screen), and a guided tour that
// plays every part of this page one after another (it presses the same buttons a visitor would).

const $ = (id) => document.getElementById(id);
const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const svg = (d, extra = '') =>
  `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${extra}>${d}</svg>`;
const ICON = {
  play: svg('<path d="M8 5l11 7-11 7z" fill="currentColor"/>'),
  pause: svg('<path d="M8 5v14M16 5v14"/>', ' stroke-width="3"'),
  expand: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
  shrink: svg('<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>'),
};

/* ------------------------------------------------------------ the player */

const SLIDE_MS = 3200;
const player = $('app');
const slides = [...document.querySelectorAll('#app-phone img')];
const caps = [...document.querySelectorAll('#app-caps li')];
const dots = $('app-dots');
const toggle = $('app-toggle');
const fullBtn = $('app-full');
let at = 0;
let timer = 0;
let playing = !reduced; // with 'reduce motion' the screens wait for the play button

function show(i) {
  at = (i + slides.length) % slides.length;
  slides.forEach((s, k) => s.classList.toggle('on', k === at));
  caps.forEach((c, k) => (c.hidden = k !== at));
  [...dots.children].forEach((d, k) => d.setAttribute('aria-current', k === at ? 'true' : 'false'));
  const next = slides[(at + 1) % slides.length];
  if (next && next.loading === 'lazy') next.loading = 'eager';
}

function schedule() {
  clearTimeout(timer);
  if (playing) timer = setTimeout(() => { show(at + 1); schedule(); }, SLIDE_MS);
}

function setPlaying(on) {
  playing = on;
  if (toggle) {
    toggle.innerHTML = on ? ICON.pause : ICON.play;
    toggle.setAttribute('aria-label', on ? 'Pause' : 'Play');
    toggle.title = on ? 'Pause' : 'Play';
  }
  show(at);
  schedule();
}

slides.forEach((_, k) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.setAttribute('aria-label', `Screen ${k + 1} of ${slides.length}`);
  b.onclick = () => { show(k); schedule(); };
  dots.append(b);
});
$('app-prev').onclick = () => { show(at - 1); schedule(); };
$('app-next').onclick = () => { show(at + 1); schedule(); };
if (toggle) toggle.onclick = () => setPlaying(!playing);

// Full screen: the real one where the browser allows it, otherwise the player covers the page.
const fsElement = () => document.fullscreenElement || document.webkitFullscreenElement;
const isFull = () => fsElement() === player || player.classList.contains('cover');

function syncFull() {
  const on = isFull();
  player.classList.toggle('full', on);
  if (fullBtn) {
    fullBtn.innerHTML = on ? ICON.shrink : ICON.expand;
    fullBtn.setAttribute('aria-label', on ? 'Exit full screen' : 'Full screen');
    fullBtn.title = on ? 'Exit full screen (Esc)' : 'Full screen';
  }
}

function cover(on) {
  player.classList.toggle('cover', on);
  document.documentElement.style.overflow = on ? 'hidden' : '';
  syncFull();
}

async function enterFull() {
  const req = player.requestFullscreen || player.webkitRequestFullscreen;
  if (req) {
    try { await req.call(player); } catch { cover(true); }
  } else cover(true);
  if (!playing) setPlaying(true);
}

function exitFull() {
  if (fsElement()) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
  if (player.classList.contains('cover')) cover(false);
}

if (fullBtn) fullBtn.onclick = () => (isFull() ? exitFull() : enterFull());
document.addEventListener('fullscreenchange', syncFull);
document.addEventListener('webkitfullscreenchange', syncFull);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && player.classList.contains('cover')) cover(false); });

syncFull();
setPlaying(playing);

/* ------------------------------------------------------------ guided tour */

let stopped = true;
const bar = $('tour-bar');

function status(n, text) {
  $('tour-step').textContent = n ? `Step ${n} of 5` : 'Tour';
  $('tour-text').textContent = text;
}

async function wait(ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (stopped) throw new Error('stopped');
    await sleep(100);
  }
}

async function until(test, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (stopped) throw new Error('stopped');
    if (test()) return true;
    await sleep(150);
  }
  return false;
}

function go(id) {
  $(id).scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
}

async function tour() {
  stopped = false;
  bar.hidden = false;
  try {
    // 1. The app itself. The visitor asked for the tour, so the screens turn even with 'reduce motion'.
    status(1, 'The app: real screens, from adding a TV to the agent that rebuilds a remote');
    go('app');
    clearTimeout(timer);
    for (let k = 0; k < slides.length; k++) {
      show(k);
      await wait(2600);
    }
    if (isFull()) exitFull();
    show(at);
    schedule();

    // 2. Learning the buttons
    status(2, 'Learning the buttons: a TV whose address another brand shares, the case the model is for');
    go('teach-h');
    await until(() => !$('run').disabled, 15000);
    await wait(800);
    // Draw unseen TVs until one shares its address with another brand (the page
    // says which): the case the model is for. Alone on its address, both sides tie.
    for (let k = 0; k < 12 && !/address shared/.test($('target').textContent); k++) {
      $('random').click();
      await wait(250);
    }
    await wait(900);
    $('run').click();
    await wait(5500);

    // 3. Deep search: the tour taps "I saw it!" when the channel number shows
    status(3, 'Deep search: the phone sweeps every address; one tap when the TV reacts');
    go('deep');
    await until(() => !$('d-start').disabled, 15000);
    $('d-speed').value = '3';
    if (!$('d-new').disabled) $('d-new').click();
    await wait(800);
    $('d-result').textContent = '';
    $('d-start').click();
    let tapped = false;
    const osd = $('tv-osd');
    const watch = new MutationObserver(() => {
      if (!tapped && osd.classList.contains('on') && !$('d-saw').disabled) {
        tapped = true;
        setTimeout(() => { if (!stopped && !$('d-saw').disabled) $('d-saw').click(); }, 650);
      }
    });
    watch.observe(osd, { attributes: true, attributeFilter: ['class'] });
    status(3, 'Deep search: watching the TV… the tour taps "I saw it!" when the channel number shows');
    await until(() => $('d-result').textContent.trim() !== '', 150000);
    watch.disconnect();
    await wait(3500);

    // 4. Find by model
    status(4, 'Find by model: the label\'s number gives the remote at once');
    go('model');
    await wait(1200);
    const box = $('m-text');
    box.value = '';
    for (const ch of '43G7200') {
      box.value += ch;
      box.dispatchEvent(new Event('input'));
      await wait(260);
    }
    await wait(3500);

    // 5. The agent
    status(5, 'The agent: a real recorded session; it asks before every send');
    go('agent');
    await wait(1200);
    $('a-replay').click();
    let last = -1;
    let still = 0;
    await until(() => {
      const n = document.querySelectorAll('#a-log li').length;
      still = n === last ? still + 1 : 0;
      last = n;
      return n > 3 && still > 20;
    }, 60000);

    status(0, 'That was everything. Try any part yourself, or play the tour again.');
    $('tour-stop').textContent = 'Close';
  } catch (e) {
    if (e.message !== 'stopped') throw e;
  }
}

$('tour-play').onclick = () => {
  if (!stopped) return;
  $('tour-stop').textContent = 'Stop';
  tour();
};
$('tour-stop').onclick = () => {
  stopped = true;
  bar.hidden = true;
  schedule();
};
