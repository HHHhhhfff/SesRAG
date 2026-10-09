import fs from 'node:fs';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {assert,smokeRoot} from './category-kit.mjs';

const ajv=new Ajv2020({allErrors:true});addFormats(ajv);
const validate=ajv.compile(JSON.parse(fs.readFileSync(path.join(smokeRoot,'specific_test_script/category-result.schema.json'),'utf8')));
// QLT_007：子分类有部分通过报告不等于完整浏览器门禁；完整集合和身份必须单独校验。
export function requireCategoryChecks(report,runId,category,expectedIds) {
 assert.ok(validate(report),`分类报告Schema不合法：${JSON.stringify(validate.errors)}`);
 assert.equal(report.run_id,runId);assert.equal(report.category,category);
 assert.equal(new Set(report.checks.map(x=>x.id)).size,report.checks.length,'分类报告检查ID重复');
 const browser=report.checks.filter(x=>x.id.includes('__browser-'));
 assert.deepEqual(browser.map(x=>x.id).sort(),[...expectedIds].sort(),'浏览器检查集合不完整或出现未约定项');
 for(const check of browser)assert.equal(check.test_point_id,check.id.split('__')[1],'检查ID与测试点身份不匹配');
 return browser;
}
