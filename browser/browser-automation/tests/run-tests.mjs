import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const root = new URL('..', import.meta.url).pathname.replace(/^\/(.:)/, '$1');
const script = (name) => join(root, 'scripts', name);
const run = (name, args, ok = true) => {
  try { return execFileSync(process.execPath, [script(name), ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); }
  catch (error) { if (ok) throw error; return `${error.stdout?.toString() || ''}${error.stderr?.toString() || ''}`; }
};
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const temp = mkdtempSync(join(tmpdir(), 'browser-automation-test-'));
try {
  const created = JSON.parse(run('workspace_manager.mjs', ['create', '--runs-dir', join(temp, 'runs'), '--task', 'test']));
  const source = join(temp, 'source.txt'); writeFileSync(source, 'first');
  run('workspace_manager.mjs', ['import', '--run-root', created.runRoot, '--source', source]);
  const target = 'work/source.txt'; run('version_manager.mjs', ['snapshot', '--run-root', created.runRoot, '--file', target, '--reason', 'test']);
  const versionFile = join(created.runRoot, 'versions', 'source.txt', 'v0001-source.txt'); writeFileSync(versionFile, 'tampered');
  assert(run('rollback.mjs', ['--run-root', created.runRoot, '--file', target, '--version', 'v0001'], false).includes('校验和不匹配'), '损坏快照必须拒绝回滚');
  const invalid = join(created.runRoot, 'invalid.json'); writeFileSync(invalid, JSON.stringify({ browser: 'edge', steps: [{ op: 'mutate_file', file: 'work/source.txt' }] }));
  assert(run('workflow_runner.mjs', ['validate', '--workflow', invalid, '--run-root', created.runRoot], false).includes('必须包含 reason'), '缺少修改原因必须拒绝');
  assert(run('browser_adapter.mjs', ['request', '--action', JSON.stringify({ browser: 'edge', operation: 'click', payload: {} })], false).includes('挑战状态'), '挑战未解除时必须拒绝交互');
  assert(run('browser_adapter.mjs', ['request', '--action', JSON.stringify({ browser: 'edge', operation: 'click', payload: { challengeState: 'clear', effect: 'high' } })], false).includes('确认'), '高影响操作缺少确认必须拒绝');
  const html = join(temp, 'slider.html'); writeFileSync(html, '<div class="slider-captcha">drag</div>'); assert(JSON.parse(run('challenge_detector.mjs', [html])).kinds.includes('slider'), '必须检测滑块挑战');
  const external = join(temp, 'external.txt'); writeFileSync(external, 'outside'); const linked = join(created.workRoot, 'linked.txt');
  try { symlinkSync(external, linked, 'file'); assert(run('version_manager.mjs', ['snapshot', '--run-root', created.runRoot, '--file', 'work/linked.txt'], false).includes('符号链接'), '符号链接必须拒绝'); } catch (error) { if (error.code !== 'EPERM') throw error; }
  assert(run('browser_adapter.mjs', ['request', '--action', JSON.stringify({ browser: 'edge', operation: 'click', payload: { challengeState: 'clear', effect: 'high', confirmation: { runId: 'test', summary: '测试', confirmedAt: new Date().toISOString() } } })]).includes('click'), '具备确认的高影响操作应通过请求关卡');
  console.log('所有回归测试通过。');
} finally { rmSync(temp, { recursive: true, force: true }); }



