import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { createHash } from 'node:crypto';
import { assertNoLinks, assertRunWorkFile } from './workspace_security.mjs';

const [command, ...raw] = process.argv.slice(2);
const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
const fail = (message) => { console.error(message); process.exit(1); };
let scope;
try { scope = assertRunWorkFile(options['run-root'] || fail('--run-root is required'), options.file || fail('--file is required')); } catch (error) { fail(error.message); }
const { runRoot, file, relativePath } = scope;
const digest = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');
const versionDir = join(runRoot, 'versions', ...relativePath.split(/[\\/]/)); const manifestPath = join(versionDir, 'manifest.json');
const getManifest = () => existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath)) : { file: `work/${relativePath.replaceAll('\\', '/')}`, versions: [] };
if (command === 'snapshot') {
  if (!existsSync(file) || !statSync(file).isFile()) fail('目标必须是已存在的普通文件。');
  try { assertNoLinks(runRoot, join(runRoot, 'versions')); mkdirSync(versionDir, { recursive: true }); assertNoLinks(runRoot, versionDir); } catch (error) { fail(error.message); }
  const manifest = getManifest(); const version = `v${String(manifest.versions.length + 1).padStart(4, '0')}`;
  const target = join(versionDir, `${version}-${basename(file)}`); copyFileSync(file, target);
  manifest.versions.push({ version, snapshot: basename(target), createdAt: new Date().toISOString(), reason: options.reason || '修改前快照', sha256: digest(file), bytes: statSync(file).size });
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`); console.log(JSON.stringify({ version, snapshot: target, manifest: manifestPath }, null, 2));
} else if (command === 'list') console.log(JSON.stringify(getManifest(), null, 2));
else fail('用法：snapshot 或 list。');
