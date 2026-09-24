import { cpSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { assertDirectoryNotLink, assertTreeHasNoLinks } from './workspace_security.mjs';

const [command, ...raw] = process.argv.slice(2);
const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
const fail = (message) => { console.error(message); process.exit(1); };
const digest = (file) => createHash('sha256').update(readFileSync(file)).digest('hex');
const slug = (value) => (value || 'browser-task').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'browser-task';

if (command === 'create') {
  const runsDir = resolve(options['runs-dir'] || 'runs');
  mkdirSync(runsDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  let runId = `${stamp}-${slug(options.task)}`; let runRoot = join(runsDir, runId); let index = 2;
  while (existsSync(runRoot)) { runId = `${stamp}-${slug(options.task)}-${index++}`; runRoot = join(runsDir, runId); }
  for (const name of ['input', 'work', 'versions', 'evidence', 'logs']) mkdirSync(join(runRoot, name), { recursive: true });
  const manifest = { runId, createdAt: new Date().toISOString(), runRoot, writeRoot: join(runRoot, 'work'), status: 'active', inputs: [] };
  writeFileSync(join(runRoot, 'run-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(JSON.stringify({ runId, runRoot, workRoot: manifest.writeRoot }, null, 2));
} else if (command === 'import') {
  let runRoot; const source = resolve(options.source || fail('--source is required'));
  try { runRoot = assertDirectoryNotLink(options['run-root'] || fail('--run-root is required'), '运行目录'); assertTreeHasNoLinks(source); } catch (error) { fail(error.message); }
  if (!existsSync(join(runRoot, 'run-manifest.json')) || !existsSync(source)) fail('运行目录或导入源不存在。');
  const name = basename(source); const inputTarget = join(runRoot, 'input', name); const workTarget = join(runRoot, 'work', name);
  if (existsSync(inputTarget) || existsSync(workTarget)) fail(`Input already exists in this run: ${name}`);
  const directory = statSync(source).isDirectory();
  cpSync(source, inputTarget, { recursive: directory, errorOnExist: true }); cpSync(source, workTarget, { recursive: directory, errorOnExist: true });
  const manifestPath = join(runRoot, 'run-manifest.json'); const manifest = JSON.parse(readFileSync(manifestPath));
  manifest.inputs.push({ source, input: `input/${name}`, work: `work/${name}`, importedAt: new Date().toISOString(), sha256: directory ? null : digest(source) });
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(JSON.stringify({ input: inputTarget, work: workTarget }, null, 2));
} else if (command === 'finalize') {
  const runRoot = resolve(options['run-root'] || fail('--run-root is required')); const manifestPath = join(runRoot, 'run-manifest.json');
  const manifest = JSON.parse(readFileSync(manifestPath)); manifest.status = 'complete'; manifest.completedAt = new Date().toISOString();
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  writeFileSync(join(runRoot, 'result.json'), `${JSON.stringify({ ok: true, runId: manifest.runId, completedAt: manifest.completedAt }, null, 2)}\n`);
  console.log(JSON.stringify({ runRoot, result: join(runRoot, 'result.json') }, null, 2));
} else fail('Use: create, import, or finalize.');

