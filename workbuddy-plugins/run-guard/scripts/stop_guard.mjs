import { readFileSync } from 'node:fs';

const readStdin = async () => {
  let data = '';
  for await (const chunk of process.stdin) data += chunk;
  return data;
};
const reply = (value) => process.stdout.write(JSON.stringify(value));
const hasToolShape = (node) => {
  if (!node || typeof node !== 'object') return false;
  if (Array.isArray(node)) return node.some(hasToolShape);
  for (const [key, value] of Object.entries(node)) {
    if (['tool_result', 'tool_response', 'toolUseResult', 'tool_use_id', 'tool_name'].includes(key)) return true;
    if (key === 'type' && ['tool', 'tool_result', 'tool_response'].includes(value)) return true;
    if (hasToolShape(value)) return true;
  }
  return false;
};
const roleOf = (record) => record?.message?.role || record?.role || record?.type || '';
const assistantText = (record) => {
  const content = record?.message?.content ?? record?.content ?? '';
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content.filter((block) => block?.type === 'text' && typeof block.text === 'string')
    .map((block) => block.text).join('\n');
};
const allowStop = () => reply({ continue: true, suppressOutput: true });

let input;
try { input = JSON.parse(await readStdin()); } catch { allowStop(); process.exit(0); }
if (input.stop_hook_active === true) { allowStop(); process.exit(0); }

let records;
try {
  records = readFileSync(input.transcript_path, 'utf8').split(/\r?\n/).filter(Boolean)
    .map((line) => { try { return JSON.parse(line); } catch { return null; } }).filter(Boolean);
} catch { allowStop(); process.exit(0); }

const recent = records.slice(-160);
let lastPlainUser = -1;
for (let i = 0; i < recent.length; i += 1) {
  if (roleOf(recent[i]) === 'user' && !hasToolShape(recent[i])) lastPlainUser = i;
}
const turn = recent.slice(Math.max(0, lastPlainUser));
const failurePattern = /(?:exit(?:ed)?\s*(?:code|status)?\s*[:=]?\s*(?:[1-9]\d*)|退出码\s*[:：]?\s*(?:[1-9]\d*)|执行失败|command not found|is_error"?\s*:\s*true|success"?\s*:\s*false)/i;
const hasFailedTool = turn.some((record) => hasToolShape(record) && failurePattern.test(JSON.stringify(record)));
let finalText = '';
for (const record of turn) {
  if (roleOf(record) === 'assistant') {
    const value = assistantText(record).trim();
    if (value) finalText = value;
  }
}
const futureOnly = /(让我先|接下来(?:我)?(?:会|将|先)|我现在去|继续执行|准备(?:先)?|稍后我会)/;
const terminal = /(已完成|执行失败|需要用户操作|已阻塞|已取消|无法继续|注册已成功.{0,40}需要新建)/s;

if (hasFailedTool && futureOnly.test(finalText) && !terminal.test(finalText)) {
  reply({
    continue: false,
    reason: '检测到最近的工具调用失败，但当前回复只描述了下一步，没有实际重试或明确终止。若是可修正的 shell、路径或参数错误，立即修正并实际重试一次；否则向用户明确报告失败阶段、退出码、原因和下一步。不要再以“让我先”或“继续执行”结束。'
  });
} else {
  allowStop();
}
