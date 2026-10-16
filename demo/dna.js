// Remote DNA: the model and the teach-session replay, in plain JavaScript.
//
// A line-for-line port of dna/catalogue.py, dna/predict.py and
// dna/simulate.py. The browser demo runs it, and tests/test_parity.py checks
// that it asks exactly the same questions as the Python on every held-out
// remote. It is also the base of the TypeScript the phone app will run.

export const ESSENTIALS = ['volUp', 'volDown', 'mute', 'ok', 'back'];
export const MISMATCH = 0.05;
export const ELSEWHERE = 0.05;
export const UNKNOWN = 0.5;
export const GIVE_UP = 300;
const COMMAND_MAX = { rc5: 63, sirc: 127, sirc15: 127, sirc20: 127 };

/* ------------------------------------------------------------ catalogue */

/** Unique remotes in catalogue order; one remote sold as several brands is one entry. */
export function loadCatalogue(raw) {
  const byKey = new Map();
  for (const brand of raw.brands) {
    for (const s of brand.s) {
      const key = s.p + '|' + s.a + '|' + JSON.stringify(Object.entries(s.c).sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0)));
      const seen = byKey.get(key);
      if (seen) seen.brands.add(brand.b);
      else byKey.set(key, { brands: new Set([brand.b]), protocol: s.p, address: s.a, commands: { ...s.c } });
    }
  }
  return [...byKey.values()];
}

const sameWhere = (r, where) => r.protocol === where[0] && r.address === where[1];
export const whereOf = (r) => [r.protocol, r.address];
const sharesBrand = (a, b) => [...a.brands].some((x) => b.brands.has(x));

/** Every remote speaking the target's protocol, minus every remote of its brands. */
export function poolFor(target, remotes) {
  return remotes.filter((r) => r.protocol === target.protocol && !sharesBrand(r, target));
}

/* ----------------------------------------------------------------- fold */

let crcTable = null;
function crc32(bytes) {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      crcTable[n] = c >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const b of bytes) crc = crcTable[(crc ^ b) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

/** The half of the brands a remote belongs to; fold 1 is the one nothing was tuned on. */
export function foldOf(remote) {
  const first = [...remote.brands].sort((x, y) => (x < y ? -1 : x > y ? 1 : 0))[0];
  return crc32(new TextEncoder().encode(first)) % 2;
}

/* -------------------------------------------------------------- session */

const sweep = (protocol) => Array.from({ length: (COMMAND_MAX[protocol] ?? 255) + 1 }, (_, i) => i);

/** The app's current queue, fixed before the first question. */
export function catalogueOrder(where, pool, targets) {
  const votes = new Map(); // command -> Map(button -> count), in first-seen order
  for (const r of pool) {
    if (!sameWhere(r, where)) continue;
    for (const [button, command] of Object.entries(r.commands)) {
      if (!votes.has(command)) votes.set(command, new Map());
      const v = votes.get(command);
      v.set(button, (v.get(button) ?? 0) + 1);
    }
  }
  const meaning = new Map();
  for (const [command, v] of votes) {
    let best = null;
    for (const [button, count] of v) if (!best || count > best[1]) best = [button, count];
    meaning.set(command, best);
  }
  const needed = new Set(targets);
  const rank = (c) => {
    const [label, count] = meaning.get(c);
    return [label === 'power' ? 2 : needed.has(label) ? 0 : 1, -count, c];
  };
  const ordered = [...meaning.keys()].sort((a, b) => {
    const x = rank(a), y = rank(b);
    return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
  });
  return ordered.concat(sweep(where[0]).filter((c) => !meaning.has(c)));
}

/** What the model believes part-way through a session. */
export class Session {
  constructor(where, pool) {
    this.where = where;
    this.pool = pool;
    this.weight = pool.map((r) => (sameWhere(r, where) ? 1 : ELSEWHERE));
    this.hits = pool.map(() => 0);
    this.byCommand = pool.map((r) => {
      const m = new Map();
      for (const [b, c] of Object.entries(r.commands)) m.set(c, b); // later buttons win, as in Python
      return m;
    });
  }

  learn(command, button) {
    this.pool.forEach((r, i) => {
      const meant = this.byCommand[i].get(command);
      if (button === null) {
        if (meant !== undefined) this.weight[i] *= MISMATCH;
      } else if (!(button in r.commands)) {
        this.weight[i] *= UNKNOWN;
      } else if (r.commands[button] === command) {
        this.weight[i] *= 1 - MISMATCH;
        this.hits[i] += 1;
      } else {
        this.weight[i] *= MISMATCH;
      }
    });
  }

  /** How likely each command is to be one of the missing buttons. */
  score(missing) {
    const out = new Map();
    this.pool.forEach((r, i) => {
      if (!sameWhere(r, this.where) && !this.hits[i]) return;
      const w = this.weight[i];
      for (const b of missing) {
        const c = r.commands[b];
        if (c !== undefined) out.set(c, (out.get(c) ?? 0) + w);
      }
    });
    return out;
  }

  /** The remotes giving `command` its score, heaviest first: the reason for a choice. */
  voters(command, missing, limit = 3) {
    const list = [];
    this.pool.forEach((r, i) => {
      if (!sameWhere(r, this.where) && !this.hits[i]) return;
      const b = missing.find((m) => r.commands[m] === command);
      if (b) list.push({ remote: r, button: b, weight: this.weight[i] });
    });
    return list.sort((x, y) => y.weight - x.weight).slice(0, limit);
  }
}

/**
 * One teach session as a sequence of questions. Each call to next() asks one
 * question and returns what happened; `done` turns true when the essential
 * buttons are all found or the session gives up.
 */
export function startSession(target, pool, useModel) {
  const where = whereOf(target);
  const targets = ESSENTIALS.filter((b) => b in target.commands);
  const meaning = new Map();
  for (const [b, c] of Object.entries(target.commands)) meaning.set(c, b);
  const fixed = catalogueOrder(where, pool, targets);
  // The model only steers where the catalogue has remotes on this address;
  // see has_neighbours() in dna/simulate.py for why.
  const session = useModel && pool.some((r) => sameWhere(r, where)) ? new Session(where, pool) : null;
  const found = new Set();
  const tried = new Set();
  const state = { targets, found, questions: 0, done: targets.length === 0, gaveUp: false, last: null };

  state.next = () => {
    if (state.done) return state;
    if (state.questions >= GIVE_UP) {
      state.done = state.gaveUp = true;
      return state;
    }
    let command;
    let why = null;
    const missing = targets.filter((b) => !found.has(b));
    if (!session) {
      command = fixed.find((c) => !tried.has(c));
    } else {
      const scores = session.score(missing);
      let best = null;
      for (const [c, s] of scores) {
        if (tried.has(c) || !(s > 0)) continue;
        if (!best || s > best[1] || (s === best[1] && c < best[0])) best = [c, s];
      }
      if (best) {
        command = best[0];
        why = session.voters(command, missing);
      } else {
        command = fixed.find((c) => !tried.has(c));
      }
    }
    if (command === undefined) {
      state.done = state.gaveUp = true;
      state.questions = GIVE_UP;
      return state;
    }
    tried.add(command);
    state.questions += 1;
    const button = meaning.get(command) ?? null;
    if (button !== null && targets.includes(button)) found.add(button);
    if (session) session.learn(command, button);
    state.last = { command, button, why };
    if (found.size === targets.length) state.done = true;
    return state;
  };
  return state;
}

/** Questions until done, the number the simulation reports. */
export function runSession(target, pool, useModel) {
  const s = startSession(target, pool, useModel);
  while (!s.done) s.next();
  return s.gaveUp ? GIVE_UP : s.questions;
}
