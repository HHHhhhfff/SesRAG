import fs from 'node:fs';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { assertSafeArtifactPath } from './report.mjs';
import { runCommand } from './process-registry.mjs';

const ajv = new Ajv2020({ allErrors: true }); addFormats(ajv);
const validate = ajv.compile(JSON.parse(fs.readFileSync(new URL('../schemas/category-result.schema.json', import.meta.url))));
export function validateCategoryResult(result, context, artifactRoot, exitCode) {
  if (!validate(result)) throw new Error(`分类报告不符合 Schema：${JSON.stringify(validate.errors)}`);
  for (const key of ['run_id', 'environment_id', 'category']) if (result[key] !== context[key]) throw new Error(`分类报告身份不符：${key}`);
  const actual = result.cases.map((item) => item.case_id);
  if (new Set(actual).size !== actual.length || JSON.stringify([...actual].sort()) !== JSON.stringify([...context.expected_case_ids].sort())) throw new Error('分类 case 缺失、额外或重复');
  const state = result.cases.some((item) => item.status === 'failed') ? 'failed'
    : result.cases.some((item) => item.status === 'blocked' || item.status === 'not_run') ? 'blocked' : 'passed';
  if (result.status !== state || exitCode !== ({ passed: 0, failed: 1, blocked: 3 }[state])) throw new Error('分类汇总/退出码与逐例结果不一致');
  for (const relative of [...result.evidence, ...result.cases.flatMap((item) => item.evidence_paths)]) {
    assertSafeArtifactPath(relative);
    const target = path.resolve(artifactRoot, relative);
    if (!target.startsWith(path.resolve(artifactRoot) + path.sep) || !fs.existsSync(target) || !fs.lstatSync(target).isFile() || fs.lstatSync(target).isSymbolicLink() || !fs.realpathSync(target).startsWith(fs.realpathSync(artifactRoot) + path.sep)) throw new Error('分类证据不存在、不是普通文件或越界');
  }
  return result;
}
export async function invokeCategoryProcess({ command, args, resultPath, timeoutMs, context, artifactRoot, ...options }) {
  if (fs.existsSync(resultPath)) throw new Error('分类报告路径已存在，拒绝复用历史遗留报告');
  if (artifactRoot && (!path.resolve(resultPath).startsWith(path.resolve(artifactRoot) + path.sep) || fs.lstatSync(artifactRoot).isSymbolicLink())) throw new Error('分类报告路径越界');
  const run = await runCommand(command, args, { ...options, timeoutMs });
  if (run.timedOut) throw new Error('分类执行超时');
  if (run.truncated) throw new Error('分类日志超限并被截断，证据不完整');
  if (!fs.existsSync(resultPath)) throw new Error(`分类退出 ${run.code} 但未产生报告`);
  if (!context || !artifactRoot) throw new Error('分类调用缺少身份上下文或证据根目录');
  const stat = fs.lstatSync(resultPath);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 5 * 1024 * 1024 || !fs.realpathSync(resultPath).startsWith(fs.realpathSync(artifactRoot) + path.sep)) throw new Error('分类报告文件无效、过大或越界');
  return { run, result: validateCategoryResult(JSON.parse(fs.readFileSync(resultPath, 'utf8')), context, artifactRoot, run.code) };
}
