import { existsSync, lstatSync, realpathSync, readdirSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

export function fail(message) { throw new Error(message); }

export function assertDirectoryNotLink(path, label = '目录') {
  const absolute = resolve(path);
  if (!existsSync(absolute) || !lstatSync(absolute).isDirectory() || lstatSync(absolute).isSymbolicLink()) fail(`${label}必须是存在且非符号链接的目录。`);
  return realpathSync.native(absolute);
}

export function assertNoLinks(root, target, { mustExist = true } = {}) {
  const realRoot = assertDirectoryNotLink(root, '根目录');
  const absolute = resolve(target);
  const rel = relative(realRoot, absolute);
  if (rel === '' || rel === '..' || rel.startsWith(`..${sep}`) || rel.split(/[\\/]/).includes('..')) fail('目标必须位于允许的根目录之下。');
  let current = realRoot;
  for (const part of rel.split(/[\\/]/)) {
    current = join(current, part);
    if (!existsSync(current)) {
      if (mustExist) fail(`目标不存在：${current}`);
      break;
    }
    if (lstatSync(current).isSymbolicLink()) fail(`不允许符号链接：${current}`);
  }
  if (mustExist && !existsSync(absolute)) fail(`目标不存在：${absolute}`);
  if (existsSync(absolute) && !realpathSync.native(absolute).startsWith(`${realRoot}${sep}`)) fail('目标真实路径超出允许根目录。');
  return absolute;
}

export function assertRunWorkFile(runRoot, file, { mustExist = true } = {}) {
  const realRunRoot = assertDirectoryNotLink(runRoot, '运行目录');
  const workRoot = join(realRunRoot, 'work');
  const realWorkRoot = assertDirectoryNotLink(workRoot, '工作目录');
  const target = resolve(realRunRoot, file);
  assertNoLinks(realWorkRoot, target, { mustExist });
  return { runRoot: realRunRoot, workRoot: realWorkRoot, file: target, relativePath: relative(realWorkRoot, target) };
}

export function assertTreeHasNoLinks(path) {
  const stat = lstatSync(path);
  if (stat.isSymbolicLink()) fail(`导入源含有符号链接：${path}`);
  if (stat.isDirectory()) {
    for (const { name } of readdirSync(path, { withFileTypes: true })) assertTreeHasNoLinks(join(path, name));
  }
}
