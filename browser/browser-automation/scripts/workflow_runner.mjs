import { existsSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { assertDirectoryNotLink } from './workspace_security.mjs';

const [command, ...raw] = process.argv.slice(2); const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
if (command !== 'validate') { console.error('用法：validate --workflow <文件> --run-root <目录>'); process.exit(1); }
const workflowPath = resolve(options.workflow || ''); let runRoot;
try { runRoot = assertDirectoryNotLink(options['run-root'] || '', '运行目录'); } catch (error) { console.error(error.message); process.exit(1); }
if (!existsSync(workflowPath)) { console.error('工作流不存在。'); process.exit(1); }
const workflow = JSON.parse(readFileSync(workflowPath)); const errors = []; const workRoot = join(runRoot, 'work');
const allowed = new Set(['goto', 'click', 'fill', 'select', 'press', 'scroll', 'wait', 'assert', 'extract', 'upload', 'download', 'handle_challenge', 'checkpoint', 'resume', 'mutate_file']);
const interactive = new Set(['click', 'fill', 'select', 'press', 'scroll', 'upload', 'download']); const stateChanging = new Set(['goto', ...interactive]);
const target = (step) => step.target && typeof step.target === 'object' && Object.keys(step.target).length > 0;
const workPath = (path) => { if (typeof path !== 'string' || !path) return false; const rel = relative(workRoot, resolve(runRoot, path)); return rel !== '' && rel !== '..' && !rel.startsWith(`..${sep}`); };
if (!['edge', 'chrome'].includes(workflow.browser)) errors.push('browser 必须为 edge 或 chrome');
if (!Array.isArray(workflow.steps) || workflow.steps.length === 0) errors.push('steps 必须为非空数组');
let challengeCheckRequired = false; const snapshots = new Set();
for (const [index, step] of (workflow.steps || []).entries()) {
  const label = `步骤 ${index + 1}`; if (!step || !allowed.has(step.op)) { errors.push(`${label}：不支持的操作`); continue; }
  if (interactive.has(step.op) && challengeCheckRequired) errors.push(`${label}：上一状态变更后必须先执行 handle_challenge`);
  if (step.op === 'goto' && typeof step.url !== 'string') errors.push(`${label}：goto 必须包含 url`);
  if (['click', 'fill', 'select'].includes(step.op) && !target(step)) errors.push(`${label}：${step.op} 必须包含 target`);
  if (step.op === 'fill' && !Object.hasOwn(step, 'value')) errors.push(`${label}：fill 必须包含 value`);
  if (step.op === 'extract' && !workPath(step.output)) errors.push(`${label}：extract.output 必须位于 work/`);
  if (['upload', 'download', 'mutate_file'].includes(step.op) && !workPath(step.file || step.path || step.output)) errors.push(`${label}：文件路径必须位于 work/`);
  if (step.op === 'mutate_file') { if (typeof step.reason !== 'string' || !step.reason.trim()) errors.push(`${label}：mutate_file 必须包含 reason`); const file = step.file; if (!snapshots.has(file)) errors.push(`${label}：mutate_file 前必须有对应 snapshot 步骤`); }
  if (step.op === 'checkpoint' && step.kind === 'snapshot' && workPath(step.file)) snapshots.add(step.file);
  if (step.op === 'handle_challenge') { if (!step.evidence || !step.evidence.url || !step.evidence.tabId || !step.evidence.domSnapshot || !step.evidence.screenshot) errors.push(`${label}：handle_challenge 必须声明 URL、tab ID、DOM 快照和截图证据`); challengeCheckRequired = false; }
  if (step.effect === 'high') { const c = step.confirmation; if (!c || c.runId !== workflow.runId || !c.summary || !c.confirmedAt) errors.push(`${label}：高影响操作必须有当前运行的确认记录`); }
  if (stateChanging.has(step.op)) challengeCheckRequired = true;
}
if (challengeCheckRequired) errors.push('最后一个状态变更后必须执行 handle_challenge');
console.log(JSON.stringify({ ok: errors.length === 0, errors, steps: workflow.steps?.length || 0 }, null, 2)); process.exit(errors.length ? 1 : 0);
