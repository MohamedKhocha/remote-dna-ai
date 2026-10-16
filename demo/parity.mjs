// Prints, for every remote, the questions each strategy needs, as JSON.
// tests/test_parity.py compares it with the Python simulation.
import { readFileSync } from 'node:fs';
import { ESSENTIALS, foldOf, loadCatalogue, poolFor, runSession } from './dna.js';

const raw = JSON.parse(readFileSync(new URL('../data/catalogue.json', import.meta.url), 'utf8'));
const remotes = loadCatalogue(raw);
const out = [];
for (const t of remotes) {
  if (!ESSENTIALS.some((b) => b in t.commands)) continue;
  const pool = poolFor(t, remotes);
  out.push([foldOf(t), runSession(t, pool, false), runSession(t, pool, true)]);
}
process.stdout.write(JSON.stringify({ remotes: remotes.length, sessions: out }));
