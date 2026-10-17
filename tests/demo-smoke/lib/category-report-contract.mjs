import fs from 'node:fs';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {assert,smokeRoot,readCases,aggregateStatus} from './category-kit.mjs';

const ajv=new Ajv2020({allErrors:true});addFormats(ajv);
const validate=ajv.compile(JSON.parse(fs.readFileSync(path.join(smokeRoot,'specific_test_script/category-result.schema.json'),'utf8')));
// QLT_007：子分类有部分通过报告不等于完整浏览器门禁；完整集合和身份必须单独校验。
export function requireCategoryChecks(report,runId,category,expectedIds) {
 assert.ok(validate(report),`分类报告Schema不合法：${JSON.stringify(validate.errors)}`);
 assert.equal(report.run_id,runId);assert.equal(report.category,category);
 assert.equal(report.status,aggregateStatus(report.checks),'分类状态与逐项结果不一致');
 assert.equal(new Set(report.checks.map(x=>x.id)).size,report.checks.length,'分类报告检查ID重复');
 const cases=readCases();
 for(const check of report.checks){
  const [caseId,tp]=check.id.split('__');
  assert.ok(caseId.startsWith(category.toUpperCase()+'_')&&cases.get(caseId)?.points.includes(tp),'未知用例或测试点身份');
  assert.equal(tp,check.test_point_id,'检查ID与测试点身份不匹配');
 }
 assert.ok(expectedIds.length>0,'必测集合不能为空');
 const required=new Set(expectedIds);
 assert.equal(required.size,expectedIds.length,'必测集合ID重复');
 const selected=report.checks.filter(x=>required.has(x.id));
 assert.deepEqual(selected.map(x=>x.id).sort(),[...expectedIds].sort(),'必测检查集合不完整');
 for(const check of selected){
  assert.equal(check.test_point_id,check.id.split('__')[1],'检查ID与测试点身份不匹配');
  assert.equal(check.status,'passed',`必测检查未通过：${check.id}`);
 }
 return selected;
}
