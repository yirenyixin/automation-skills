import { readFileSync } from 'node:fs';

const snapshotPath = process.argv[2];
if (!snapshotPath) { console.error('Use: node discover_page.mjs <mcp-dom-snapshot.json>'); process.exit(1); }
const snapshot = JSON.parse(readFileSync(snapshotPath)); const nodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
const actionable = nodes.filter((node) => node.visible !== false && ['button', 'link', 'textbox', 'combobox', 'checkbox', 'radio', 'tab'].includes(String(node.role).toLowerCase()))
  .map(({ role, name, id, testId, selector, disabled }) => ({ role, name, id, testId, selector, disabled: Boolean(disabled) }));
console.log(JSON.stringify({ url: snapshot.url ?? null, title: snapshot.title ?? null, actionable, forms: nodes.filter((n) => String(n.role).toLowerCase() === 'form').length }, null, 2));
