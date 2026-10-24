import fs from 'node:fs';
import path from 'node:path';

const PREFIXES = {
  session: 'SES', context: 'CTX', model: 'MOD', run: 'RUN',
  workspace: 'UI', compatibility: 'COMP', performance: 'PERF', quality: 'QLT',
};

// 只提取正式用例标题，不扫描覆盖表；执行结果回填不改变编号集合。
export function readCaseCatalog(suiteRoot) {
  const source = path.join(suiteRoot, 'test-cases.md');
  if (!fs.existsSync(source) || !fs.lstatSync(source).isFile() || fs.lstatSync(source).isSymbolicLink()) {
    throw new TypeError('缺少本套件正式测试用例文档或文档为链接');
  }
  const categories = Object.fromEntries(Object.keys(PREFIXES).map((key) => [key, []]));
  const seen = new Set();
  let category;
  for (const line of fs.readFileSync(source, 'utf8').split(/\r?\n/)) {
    const section = /^### 3\.\d+ ([a-z]+)[：:]/.exec(line);
    if (section) category = section[1];
    const item = /^#### ([A-Z]+_\d{3})\s+/.exec(line);
    if (!item) continue;
    const id = item[1];
    if (!(category in PREFIXES) || !id.startsWith(`${PREFIXES[category]}_`) || seen.has(id)) {
      throw new TypeError(`测试用例编号重复或分类错误：${id}`);
    }
    categories[category].push(id);
    seen.add(id);
  }
  if (Object.values(categories).some((ids) => !ids.length)) throw new TypeError('正式用例文档缺少必需分类或用例');
  return { case_count: seen.size, categories };
}

export function assertCompleteRegistration(entry, catalog) {
  const expected = catalog.categories[entry.category];
  if (JSON.stringify([...entry.case_ids].sort()) !== JSON.stringify([...expected].sort())) {
    throw new TypeError(`分类 ${entry.category} 用例登记不完整或包含未知编号；必须覆盖文档中的全部 ${expected.length} 个用例`);
  }
}
