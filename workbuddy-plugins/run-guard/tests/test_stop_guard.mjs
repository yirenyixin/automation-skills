import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const script = new URL('../scripts/stop_guard.mjs', import.meta.url).pathname.replace(/^\/(.:)/, '$1');
const temp = mkdtempSync(join(tmpdir(), 'run-guard-test-'));
const run = (records, extra = {}) => {
  const file = join(temp, Math.random().toString(16).slice(2) + '.jsonl');
  writeFileSync(file, records.map(JSON.stringify).join('\n'), 'utf8');
  return JSON.parse(execFileSync(process.execPath, [script], {
    input: JSON.stringify({ hook_event_name: 'Stop', transcript_path: file, ...extra }),
    encoding: 'utf8'
  }));
};
const assert = (ok, message) => { if (!ok) throw new Error(message); };

try {
  const failed = [
    { type: 'user', message: { role: 'user', content: '打开百度' } },
    { type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text: '开始检查' }] } },
    { type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: '1', is_error: true, content: 'command not found，退出码 127' }] } },
    { type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text: '好的，继续执行。让我先注册 Edge MCP。' }] } }
  ];
  assert(run(failed).continue === false, '失败后只承诺下一步时必须阻止停止');
  const explicit = failed.slice(0, -1).concat([{ type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text: '执行失败：退出码 127。需要用户操作。' }] } }]);
  assert(run(explicit).continue === true, '明确报告失败时应允许停止');
  const success = [
    { type: 'user', message: { role: 'user', content: '打开百度' } },
    { type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: '1', content: 'ok' }] } },
    { type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text: '已完成。' }] } }
  ];
  assert(run(success).continue === true, '正常完成应允许停止');
  assert(run(failed, { stop_hook_active: true }).continue === true, '必须避免无限循环');
  console.log('run-guard 全部测试通过。');
} finally { rmSync(temp, { recursive: true, force: true }); }
