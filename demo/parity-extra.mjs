// Prints, as JSON, what demo/models.js and demo/sweep.js answer for the cases
// tests/test_parity.py sends on stdin, so the Python can compare.
//   { "models": ["MODEL: 43G7200", ...], "sweep": { "step": 9, "hands": [300, ...] } }
import { readFileSync } from 'node:fs';
import { loadCatalogue } from './dna.js';
import { loadModels, search } from './models.js';
import { batchCandidates, runBatch, runSweep, sweepCandidates } from './sweep.js';

const ask = JSON.parse(readFileSync(0, 'utf8'));
const data = (f) => JSON.parse(readFileSync(new URL('../data/' + f, import.meta.url), 'utf8'));

const models = loadModels(data('models.json'));
const found = ask.models.map((text) =>
  search(text, models, null, 3).map(({ model, score }) => [model.label, model.protocol, model.address, Math.round(score * 1000)])
);

const remotes = loadCatalogue(data('catalogue.json'));
const sweep = sweepCandidates(remotes);
const batch = batchCandidates(remotes);
const sessions = [];
for (let t = 0; t < batch.length; t += ask.sweep.step) {
  const tv = batch[t];
  tv.probes.forEach((knows) => {
    const old = runBatch(batch, tv, knows);
    const row = [t, knows, old.found, old.answers, Math.round(old.seconds * 1000)];
    for (const hand of ask.sweep.hands) {
      const out = runSweep(sweep, tv, knows, hand);
      row.push(out.found, out.answers, Math.round(out.seconds * 1000));
    }
    sessions.push(row);
  });
}
process.stdout.write(JSON.stringify({ models: found, sweep: { candidates: sweep.length, sessions } }));
