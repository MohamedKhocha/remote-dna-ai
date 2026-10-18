// Model-number search, in plain JavaScript: a line-for-line port of
// dna/models.py. tests/test_parity.py checks it returns the same remotes as
// the Python for every indexed model, clean, with a suffix, misread, and in
// another screen size.

const MODEL_WORDS = /\b(MODEL|MOD|TYPE|MODEL NO|MODELE|MODÈLE|MODELO)\b/i;
const SERIAL_WORDS = /\b(S\/?N|SERIAL|SERIE|SÉRIE)\b/i;

/** Electrical ratings look like model numbers: 100-240V~50/60Hz becomes 100240V5060HZ. */
export const isRating = (key) => key.includes('HZ') || /^(AC)?\d{2,6}(V|W|VA|MA|KW|VAC)(AC)?$/.test(key);

export function loadModels(raw) {
  return raw.models.map((e) => ({
    brand: e.b,
    label: e.m,
    keys: e.k,
    protocol: e.p ?? null,
    address: e.a ?? null,
    field: e.src === 'field',
    wifi: e.wifi ?? null,
  }));
}

/** Upper-case letters and digits only: 'bn59-01199f' and 'BN5901199F' meet. */
export const modelKey = (s) => s.toUpperCase().replace(/[^A-Z0-9]/g, '');

/** Strings that could be a model number, likeliest first (see dna/models.py). */
export function candidates(text) {
  const scored = [];
  for (const line of text.split(/\r\n|\r|\n/)) {
    const onModelLine = MODEL_WORDS.test(line);
    if (!onModelLine && SERIAL_WORDS.test(line)) continue;
    for (const piece of line.split(/[\s:;,()[\]]+/)) {
      const k = modelKey(piece);
      if (k.length < 4 || k.length > 20 || !/[A-Z]/.test(k) || !/[0-9]/.test(k)) continue;
      if (MODEL_WORDS.test(piece) || isRating(k)) continue;
      const shaped = k.length >= 5 && k.length <= 12 ? 5 : 0;
      scored.push([(onModelLine ? 10 : 0) + shaped + Math.min(k.length, 10) / 10, k]);
    }
  }
  const out = [];
  for (const [, k] of scored.sort((a, b) => b[0] - a[0])) if (!out.includes(k)) out.push(k);
  return out;
}

function distance(a, b, limit) {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    }
    if (Math.min(...cur) > limit) return limit + 1;
    prev = cur;
  }
  return prev[prev.length - 1];
}

/** The model without its screen size: 43G7200 and 55G7200 share a remote. */
export const modelFamily = (key) => key.replace(/^\d{2,3}(?=[A-Z])/, '');

/** 1 the same; 0.9 a suffix; 0.85 the same family; 0.8 one off; 0.7 two off on long keys. */
export function match(candidate, key) {
  if (candidate === key) return 1;
  const shorter = Math.min(candidate.length, key.length);
  if (shorter >= 5 && (candidate.startsWith(key) || key.startsWith(candidate))) return 0.9;
  const fc = modelFamily(candidate);
  const fk = modelFamily(key);
  if (fc.length >= 4 && fk.length >= 4 && fc === fk) return 0.85;
  if (shorter >= 5) {
    const d = distance(candidate, key, 2);
    if (d === 1) return 0.8;
    if (d === 2 && shorter >= 8) return 0.7;
  }
  return 0;
}

/** The best models for a label's text or a typed number: [{ model, score }]. */
export function search(text, models, brand = null, limit = 5) {
  const found = candidates(text);
  if (!found.length) return [];
  const brands = new Set([...(brand ? [brand] : []), ...text.split(/\s+/).filter(Boolean)].map(modelKey));
  const scored = [];
  for (const m of models) {
    let s = 0;
    for (const c of found) for (const k of m.keys) s = Math.max(s, match(c, k));
    if (!s) continue;
    s += brands.has(modelKey(m.brand)) ? 0.05 : 0;
    s += m.field ? 0.02 : 0;
    scored.push({ model: m, score: Math.min(1, s) });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit);
}
