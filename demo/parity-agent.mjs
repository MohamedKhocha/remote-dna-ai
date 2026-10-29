// Prints, as JSON, what demo/agent.js answers for the cases tests/test_parity.py
// sends on stdin, so the Python agent tools can be compared with it.
//   { "predict": [["nec", 4, {"volUp": 2}], ...], "brands": ["Samsung", "Iris"] }
import { readFileSync } from 'node:fs';
import { loadCatalogue } from './dna.js';
import { brandAddresses, predictButtons } from './agent.js';

const ask = JSON.parse(readFileSync(0, 'utf8'));
const remotes = loadCatalogue(JSON.parse(readFileSync(new URL('../data/catalogue.json', import.meta.url), 'utf8')));
process.stdout.write(JSON.stringify({
  predict: ask.predict.map(([p, a, known]) => predictButtons(remotes, p, a, known)),
  brands: ask.brands.map((b) => brandAddresses(remotes, b)),
}));
