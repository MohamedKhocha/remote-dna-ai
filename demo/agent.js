// The agent's tools in JavaScript, the same answers as agent/tools.py
// (checked by tests/test_parity.py through demo/parity-agent.mjs).
import { search } from './models.js';

export const MISMATCH = 0.05;
export const ELSEWHERE = 0.05;
export const UNKNOWN = 0.5;
export const WANTED = ['volUp', 'volDown', 'mute', 'ok', 'back', 'chUp', 'chDown', 'menu', 'power'];
export const LOCAL_MAKERS = { IRIS: 'Skyworth' };

const same = (r, protocol, address) => r.protocol === protocol && r.address === address;

/** dna.predict.mixture: every resembling remote votes with its weight. */
export function predictButtons(remotes, protocol, address, confirmed, wanted = WANTED) {
  const weighted = [];
  for (const r of remotes) {
    if (r.protocol !== protocol) continue;
    const here = same(r, protocol, address);
    let w = here ? 1 : ELSEWHERE;
    let hits = 0;
    for (const [b, c] of Object.entries(confirmed)) {
      if (!(b in r.commands)) w *= UNKNOWN;
      else if (r.commands[b] === c) { w *= 1 - MISMATCH; hits += 1; }
      else w *= MISMATCH;
    }
    if (here || hits) weighted.push([r, w]);
  }
  const out = {};
  for (const b of wanted) {
    if (b in confirmed) continue;
    const votes = new Map();
    for (const [r, w] of weighted) {
      if (b in r.commands) votes.set(r.commands[b], (votes.get(r.commands[b]) ?? 0) + w);
    }
    let best = null;
    for (const [c, v] of votes) if (!best || v > best[1] || (v === best[1] && c < best[0])) best = [c, v];
    if (best) out[b] = best[0];
  }
  return out;
}

export function findModel(models, labelText, brand = null, limit = 3) {
  return search(labelText, models, brand, limit).map(({ model, score }) => ({
    brand: model.brand, model: model.label, protocol: model.protocol, address: model.address,
    wifi: model.wifi ?? null, tested_on_a_real_tv: model.field, score: Math.round(score * 100) / 100,
  }));
}

export function brandAddresses(remotes, brand, limit = 5) {
  const wanted = brand.trim().toUpperCase();
  const maker = LOCAL_MAKERS[wanted] ?? null;
  const names = new Set([wanted, ...(maker ? [maker.toUpperCase()] : [])]);
  const mine = remotes.filter((r) => [...r.brands].some((b) => names.has(b.toUpperCase())));
  const counts = new Map();
  for (const r of mine) {
    const k = `${r.protocol}|${r.address}`;
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  const top = [...counts].sort((a, b) => b[1] - a[1]).slice(0, limit);
  const out = {
    brand, maker,
    addresses: top.map(([k, n]) => {
      const [protocol, address] = [k.split('|')[0], Number(k.split('|')[1])];
      const others = new Set();
      for (const r of remotes) if (same(r, protocol, address)) for (const b of r.brands) if (!names.has(b.toUpperCase())) others.add(b);
      return { protocol, address, remotes: n, other_brands_on_it: others.size };
    }),
  };
  if (!mine.length) out.note = 'No catalogue remote for this brand. Ask for the model number on the label (back of the TV), or use the deep search in the app.';
  return out;
}

/** A TV that reacts only to its own address and its own remote's commands. */
export function virtualTv(remotes, models, labelText) {
  const hit = findModel(models, labelText, null, 1)[0];
  if (!hit || hit.protocol == null) throw new Error(`no infrared TV matches ${labelText}`);
  const here = remotes.filter((r) => same(r, hit.protocol, hit.address));
  const own = here.reduce((a, r) => (Object.keys(r.commands).length > Object.keys(a.commands).length ? r : a));
  const buttonOf = new Map(Object.entries(own.commands).map(([b, c]) => [c, b]));
  return {
    protocol: hit.protocol, address: hit.address, label: `${hit.brand} ${hit.model}`,
    receive: (p, a, c) => (p === hit.protocol && a === hit.address ? buttonOf.get(c) ?? null : null),
  };
}
