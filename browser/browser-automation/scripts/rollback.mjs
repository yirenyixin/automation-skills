import { copyFileSync, existsSync, readFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { assertNoLinks, assertRunWorkFile } from './workspace_security.mjs';

const raw = process.argv.slice(2); const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
const fail = (message) => { console.error(message); process.exit(1); };
let scope;
try { scope = assertRunWorkFile(options['run-root'] || fail('--run-root is required'), options.file || fail('--file is required')); } catch (error) { fail(error.message); }
const { runRoot, file, relativePath } = scope; const versionDir = join(runRoot, 'versions', ...relativePath.split(/[\\/]/));
try { assertNoLinks(runRoot, versionDir); } catch (error) { fail(error.message); }
const manifest = JSON.parse(readFileSync(join(versionDir, 'manifest.json'))); const entry = manifest.versions.find((item) => item.version === options.version);
if (!entry || entry.snapshot !== `${entry.version}-${basename(file)}` || /[\\/]/.test(entry.snapshot)) fail(`无效或未知版本：${options.version}`);
const snapshot = join(versionDir, entry.snapshot); const digest = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');
try { assertNoLinks(versionDir, snapshot); } catch (error) { fail(error.message); }
if (digest(snapshot) !== entry.sha256) fail('快照校验和不匹配，已拒绝回滚。');
if (existsSync(file)) {
  const script = fileURLToPath(new URL('./version_manager.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [script, 'snapshot', '--run-root', runRoot, '--file', `work/${relativePath}`, '--reason', `回滚至 ${entry.version} 前的快照`], { stdio: 'inherit' });
  if (result.status !== 0) process.exit(result.status || 1);
}
copyFileSync(snapshot, file); console.log(JSON.stringify({ restored: file, sourceVersion: entry.version }, null, 2));
