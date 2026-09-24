const [command, ...raw] = process.argv.slice(2); const options = Object.fromEntries(raw.filter((v, i) => i % 2 === 0 && v.startsWith('--')).map((v, i) => [v.slice(2), raw[i * 2 + 1]]));
const fail = (message) => { console.error(message); process.exit(1); };
const allowed = new Set(['listTabs', 'activateTab', 'navigate', 'snapshotDom', 'evaluate', 'click', 'type', 'select', 'pressKey', 'scroll', 'screenshot', 'waitForDownload']);
const interactive = new Set(['click', 'type', 'select', 'pressKey', 'scroll']);
if (command === 'capabilities') console.log(JSON.stringify({ browsers: ['edge', 'chrome'], operations: [...allowed], guards: ['challengeState', 'confirmation'] }, null, 2));
else if (command === 'request') {
  const action = JSON.parse(options.action || fail('--action JSON 是必需项')); if (!['edge', 'chrome'].includes(action.browser)) fail('browser 必须为 edge 或 chrome'); if (!allowed.has(action.operation)) fail(`不支持的操作：${action.operation}`);
  const payload = action.payload ?? {};
  if (interactive.has(action.operation) && payload.challengeState !== 'clear') fail('挑战状态未确认解除；拒绝交互请求。');
  if (payload.effect === 'high') { const c = payload.confirmation; if (!c?.runId || !c?.summary || !c?.confirmedAt) fail('高影响操作缺少本次运行的用户确认记录。'); }
  console.log(JSON.stringify({ browser: action.browser, operation: action.operation, tabId: action.tabId ?? null, payload }, null, 2));
} else fail('用法：capabilities 或 request。');
