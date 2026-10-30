// The app's screens as a slideshow, and a guided tour that plays every part of
// this page one after another (it presses the same buttons a visitor would).

const $ = (id) => document.getElementById(id);
const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------ slideshow */

const slides = [...document.querySelectorAll('#app-phone img')];
const caps = [...document.querySelectorAll('#app-caps li')];
const dots = $('app-dots');
let at = 0;
let timer = 0;
let paused = false;

function show(i) {
  at = (i + slides.length) % slides.length;
  slides.forEach((s, k) => s.classList.toggle('on', k === at));
  caps.forEach((c, k) => (c.hidden = k !== at));
  [...dots.children].forEach((d, k) => d.setAttribute('aria-current', k === at ? 'true' : 'false'));
  const next = slides[(at + 1) % slides.length];
  if (next && next.loading === 'lazy') next.loading = 'eager';
}

function autoplay(ms = 3600) {
  clearInterval(timer);
  if (reduced) return;
  timer = setInterval(() => { if (!paused) show(at + 1); }, ms);
}

slides.forEach((_, k) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.setAttribute('aria-label', `Screen ${k + 1} of ${slides.length}`);
  b.onclick = () => { show(k); autoplay(); };
  dots.append(b);
});
$('app-prev').onclick = () => { show(at - 1); autoplay(); };
$('app-next').onclick = () => { show(at + 1); autoplay(); };
const box = $('app');
if (box) {
  box.addEventListener('mouseenter', () => (paused = true));
  box.addEventListener('mouseleave', () => (paused = false));
  box.addEventListener('focusin', () => (paused = true));
  box.addEventListener('focusout', () => (paused = false));
}
show(0);
autoplay();

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
    // 1. The app itself
    status(1, 'The app: real screens, from adding a TV to the agent that rebuilds a remote');
    go('app');
    clearInterval(timer);
    for (let k = 0; k < slides.length; k++) {
      show(k);
      await wait(2600);
    }
    autoplay();

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
  autoplay();
};
