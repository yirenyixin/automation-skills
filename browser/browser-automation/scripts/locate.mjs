import { readFileSync } from 'node:fs';

const [snapshotPath, ...raw] = process.argv.slice(2); const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
if (!snapshotPath) { console.error('Use: node locate.mjs <snapshot.json> [--role button] [--name Save]'); process.exit(1); }
const nodes = JSON.parse(readFileSync(snapshotPath)).nodes || [];
const norm = (v) => String(v || '').trim().toLowerCase(); const role = norm(options.role); const name = norm(options.name);
const matches = nodes.filter((node) => node.visible !== false && (!role || norm(node.role) === role) && (!name || norm(node.name) === name))
  .map((node) => ({ role: node.role, name: node.name, locator: node.testId ? { testId: node.testId } : node.id ? { id: node.id } : node.selector ? { selector: node.selector } : { role: node.role, name: node.name } }));
console.log(JSON.stringify({ unique: matches.length === 1, matches }, null, 2));
