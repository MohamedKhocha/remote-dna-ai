// The deep search, in plain JavaScript: a line-for-line port of dna/sweep.py.
// tests/test_parity.py checks it finds the same TVs, with the same answers
// and times, as the Python.

export const DEEP_SPACES = [['nec', 256], ['samsung32', 256], ['rc6', 256], ['rc5', 32], ['sirc', 32]];
const UNSAFE = ['power', 'source'];
export const PROBES = 2;
export const LOOKBACK_MS = 3000;
export const BATCH = 24;
export const FRAME_GAP_MS = 45;
export const SETTLE_MS = 700;
export const LOOK_MS = 2500;

/* -------------------------------------------------------------- probes */

/** Greedy set cover over `remotes`, safe commands only (see dna/sweep.py). */
export function deepProbes(remotes, count = PROBES) {
  const who = new Map();
  const unsafe = new Map();
  remotes.forEach((r, i) => {
    for (const [key, value] of Object.entries(r.commands)) {
      if (!who.has(value)) who.set(value, new Set());
      who.get(value).add(i);
      if (UNSAFE.includes(key)) unsafe.set(value, (unsafe.get(value) ?? 0) + 1);
    }
  });
  const safe = [...who.keys()].filter((v) => 5 * (unsafe.get(v) ?? 0) < who.get(v).size).sort((a, b) => a - b);
  const left = new Set(remotes.map((_, i) => i));
  const probes = [];
  while (probes.length < count) {
    let best = null;
    let score = -1;
    for (const v of safe) {
      if (probes.includes(v)) continue;
      let g = 0;
      for (const i of who.get(v)) if (left.has(i)) g++;
      const s = g * remotes.length + who.get(v).size;
      if (s > score) [best, score] = [v, s];
    }
    if (best === null) break;
    probes.push(best);
    for (const i of who.get(best)) left.delete(i);
  }
  return probes;
}

function spaces(remotes) {
  const known = new Set(remotes.map((r) => r.protocol + '|' + r.address));
  const out = [];
  for (const [protocol, size] of DEEP_SPACES) {
    const probes = deepProbes(remotes.filter((r) => r.protocol === protocol));
    const addresses = [];
    for (let a = 0; a < size; a++) if (!known.has(protocol + '|' + a)) addresses.push(a);
    if (probes.length && addresses.length) out.push({ protocol, addresses, probes });
  }
  return out;
}

/** The sweep's order: every address with the first probe, then with the second. */
export function sweepCandidates(remotes) {
  const sp = spaces(remotes);
  const out = [];
  for (let p = 0; p < PROBES; p++) {
    for (const { protocol, addresses, probes } of sp) {
      if (p >= probes.length) continue;
      for (const address of addresses) out.push({ protocol, address, probes: [probes[p]] });
    }
  }
  return out;
}

/** The batch search's order: every address once, with both probes. */
export function batchCandidates(remotes) {
  const out = [];
  for (const { protocol, addresses, probes } of spaces(remotes)) {
    for (const address of addresses) out.push({ protocol, address, probes: [...probes] });
  }
  return out;
}

/* -------------------------------------------------------------- timing */

const bits = (value, count) => Array.from({ length: count }, (_, i) => (value >> i) & 1);

/** Air time of one frame, in microseconds, as the app's encoders build it. */
export function frameUs(protocol, address, command) {
  if (protocol === 'nec') return 9000 + 4500 + 16 * (562 + 1687) + 16 * (562 + 562) + 562;
  if (protocol === 'samsung32') {
    const b = [...bits(address, 8), ...bits(address, 8), ...bits(command, 8), ...bits(command ^ 0xff, 8)];
    return 4500 + 4500 + b.reduce((t, x) => t + 560 + (x ? 1690 : 560), 0) + 560;
  }
  if (protocol === 'rc5') return 14 * 2 * 889 - 889;
  if (protocol === 'rc6') {
    const total = 2666 + 889 + 4 * 2 * 444 + 2 * 889 + 16 * 2 * 444;
    return total - (command & 1 ? 444 : 0);
  }
  if (protocol === 'sirc') {
    const b = [...bits(command & 0x7f, 7), ...bits(address & 0x1f, 5)];
    const frame = 2400 + 600 + b.reduce((t, x) => t + (x ? 1200 : 600) + 600, 0);
    const gap = Math.max(45000 - frame, 10000);
    return 2 * (frame + gap - 600) + frame - 600;
  }
  throw new Error(protocol);
}

/** How long one candidate takes to go out: every probe, each with its gap. */
export const sendMs = (c) => c.probes.reduce((t, p) => t + frameUs(c.protocol, c.address, p) / 1000 + FRAME_GAP_MS, 0);

/* ----------------------------------------------------------- searching */

/** The sends on air in the `lookback` before the tap, and the one overlapping its start. */
export function suspects(sentAt, tapAt, lookback = LOOKBACK_MS) {
  const sent = [...sentAt.entries()].filter(([, t]) => t <= tapAt).sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  if (!sent.length) return [];
  const inside = sent.filter(([, t]) => t >= tapAt - lookback).map(([i]) => i);
  const before = sent.filter(([, t]) => t < tapAt - lookback).map(([i]) => i);
  const out = [...(before.length ? [before[before.length - 1]] : []), ...inside];
  return out.length ? out : [sent[sent.length - 1][0]];
}

/**
 * Replay the group, halve it while it reacts, confirm the last one alone.
 * Returns { found, answers, seconds, steps }; each step is the group sent
 * and whether the TV reacted, for the page to show.
 */
export function settle(group, reacts, cost) {
  const steps = [];
  const ask = (g) => {
    const r = reacts(g);
    steps.push({ group: g, reacted: r });
    return r;
  };
  let answers = 1;
  let ms = cost(group);
  if (!ask(group)) return { found: null, answers, seconds: ms / 1000, steps };
  let current = group;
  while (current.length > 1) {
    const mid = Math.ceil(current.length / 2);
    const half = current.slice(0, mid);
    answers += 1;
    ms += cost(half);
    current = ask(half) ? half : current.slice(mid);
  }
  answers += 1;
  ms += cost(current);
  return { found: ask(current) ? current[0] : null, answers, seconds: ms / 1000, steps };
}

const hits = (c, tv, knows) => c.protocol === tv.protocol && c.address === tv.address && c.probes.includes(knows);

/** One deep search by sweep, with a simulated hand (see dna/sweep.py). */
export function runSweep(cands, tv, knows, handMs, strayAt = null) {
  const air = cands.map(sendMs);
  const reacts = (group) => group.some((i) => hits(cands[i], tv, knows));
  const cost = (group) => group.reduce((t, i) => t + air[i], 0) + LOOK_MS + SETTLE_MS;
  const sentAt = new Map();
  let clock = 0;
  let answers = 0;
  let cursor = 0;
  while (cursor < cands.length) {
    let tap = null;
    for (let i = cursor; i < cands.length; i++) {
      if (tap !== null && clock >= tap) break;
      sentAt.set(i, clock);
      clock += air[i];
      if (strayAt !== null && clock >= strayAt) {
        tap = strayAt;
        strayAt = null;
      } else if (tap === null && hits(cands[i], tv, knows)) {
        tap = clock + handMs;
      }
    }
    if (tap === null) return { found: null, answers, seconds: clock / 1000 };
    const group = suspects(sentAt, tap);
    answers += 1;
    const out = settle(group, reacts, cost);
    clock = tap + SETTLE_MS + out.seconds * 1000;
    answers += out.answers;
    if (out.found !== null) return { found: out.found, answers, seconds: clock / 1000 };
    cursor = Math.max(...group) + 1;
  }
  return { found: null, answers, seconds: clock / 1000 };
}

/** One deep search the old way: batches, one yes/no question each. */
export function runBatch(cands, tv, knows, batch = BATCH) {
  const air = cands.map(sendMs);
  const reacts = (group) => group.some((i) => hits(cands[i], tv, knows));
  const cost = (group) => group.reduce((t, i) => t + air[i], 0) + LOOK_MS + SETTLE_MS;
  let answers = 0;
  let seconds = 0;
  for (let start = 0; start < cands.length; start += batch) {
    const group = [];
    for (let i = start; i < Math.min(start + batch, cands.length); i++) group.push(i);
    answers += 1;
    seconds += cost(group) / 1000;
    if (reacts(group)) {
      const out = settle(group, reacts, cost);
      return { found: out.found, answers: answers + out.answers, seconds: seconds + out.seconds };
    }
  }
  return { found: null, answers, seconds };
}
