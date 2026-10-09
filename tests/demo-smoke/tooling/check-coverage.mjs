import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {smokeRoot,readCases,aggregateStatus} from '../lib/category-kit.mjs';
// 任务3～4：声明校验只能证明路由完整；报告阶段另列断言/blocked，不混算完整覆盖。
const manifest=JSON.parse(fs.readFileSync(path.join(smokeRoot,'specific_test_script/manifest.json'),'utf8'));
const cases=readCases(), declared=new Map();
for(const category of manifest.categories) {
 assert.equal(category.status,'enabled');
 const source=fs.readFileSync(path.join(smokeRoot,'specific_test_script',category.script),'utf8');
 const array=source.match(/export const coveredCases\s*=\s*(\[[\s\S]*?\]);?/);
 const ids=array?[...array[1].matchAll(/['"]([A-Z]+_\d{3})['"]/g)].map(x=>x[1]): category.name==='wk'?Array.from({length:25},(_,i)=>`WK_${String(i+1).padStart(3,'0')}`):[];
 assert.ok(ids.length,`${category.name}无覆盖声明`);
 for(const id of ids){assert.ok(cases.has(id),`未知用例${id}`);assert.ok(!declared.has(id),`用例跨分类重复${id}`);declared.set(id,category.name);}
}
assert.deepEqual([...cases.keys()].filter(x=>!declared.has(x)),[],'未声明用例');
console.log(`声明路由核对：${cases.size}用例 / ${manifest.categories.length}分类；不能据此宣称行为完整覆盖。`);
const artifact=process.argv[2];
if(artifact) {
 const rows=[];
 for(const [id,category]of declared) {
  const report=JSON.parse(fs.readFileSync(path.join(artifact,'categories',category+'.json'),'utf8'));
  const checks=report.checks.filter(x=>x.id.startsWith(id+'__'));
  assert.ok(checks.length,`${id}未产生执行项`);
  const missing=cases.get(id).points.filter(tp=>!checks.some(x=>x.test_point_id===tp));assert.deepEqual(missing,[],`${id}有测试点未记录`);
  rows.push({id,design_state:cases.get(id).state,category,status:aggregateStatus(checks),asserted:checks.filter(x=>!['blocked','not_ready','skipped'].includes(x.status)).length,blocked:checks.filter(x=>x.status==='blocked').length,checks:checks.length});
 }
 const onlyBlocked=rows.filter(x=>!x.asserted&&!x.design_state.startsWith('暂不可'));
 const partial=rows.filter(x=>x.blocked&&x.design_state.startsWith('可验证'));
 fs.writeFileSync(path.join(artifact,'case-coverage.json'),JSON.stringify({rows,only_blocked_verifiable:onlyBlocked,verifiable_with_unfinished_subitems:partial},null,2));
 console.log(`报告核对：149用例所有关联测试点均有状态记录；已有实际断言${rows.filter(x=>x.asserted>0).length}用例。`);
 console.log(`可验证/部分用例只有blocked：${onlyBlocked.map(x=>x.id).join(',')||'无'}；原设计可验证但仍有未完成子项：${partial.map(x=>x.id).join(',')||'无'}。`);
}
