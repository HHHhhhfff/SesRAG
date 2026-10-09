import fs from 'node:fs';
import path from 'node:path';
import {readCases,aggregateStatus,redact} from '../lib/category-kit.mjs';
// 运行产物的人读投影，不回填用例文档、不把一轮试跑作为稳定性报告。
const directory=path.resolve(process.argv[2]);
const summary=JSON.parse(fs.readFileSync(path.join(directory,'summary.json'),'utf8').replace(/^\uFEFF/,''));
const definitions=readCases(),groups=new Map(),categories=[];
for(const item of summary.categories) {
 const target=path.join(directory,'categories',item.name+'.json');
 const report=fs.existsSync(target)?JSON.parse(fs.readFileSync(target,'utf8').replace(/^\uFEFF/,'')):null;
 const counts={passed:0,failed:0,blocked:0,skipped:0,not_ready:0};
 for(const check of report?.checks??[]) {
  counts[check.status]++;
  const id=check.id.split('__')[0];if(!definitions.has(id))continue;
  if(!groups.has(id))groups.set(id,[]);groups.get(id).push(check);
 }
 categories.push({name:item.name,status:item.status,exit:item.exit_code??'未执行',counts});
}
const labels={passed:'通过',failed:'失败',blocked:'受阻',skipped:'跳过',not_ready:'未就绪'};
const rows=[],totals={passed:0,failed:0,blocked:0,skipped:0,not_ready:0};
for(const id of definitions.keys()) {
 if(!groups.has(id))continue;const checks=groups.get(id),state=aggregateStatus(checks);totals[state]++;
 const counts=['passed','failed','blocked'].map(x=>checks.filter(y=>y.status===x).length).join('/');
 const problems=checks.filter(x=>x.status!=='passed').map(x=>`${x.id}：${x.actual}`).join('；')||'所有已执行子项通过';
 const evidence=checks.flatMap(x=>x.evidence).filter((x,i,a)=>a.indexOf(x)===i).slice(0,3).map(x=>`[证据](${x})`).join(' ');
 rows.push(`| ${id} | ${definitions.get(id).title} | ${labels[state]} | ${counts} | ${redact(problems).replaceAll('|','\\|').replace(/\r?\n/g,' ').slice(0,750)} | ${evidence} |`);
}
const content=[`# Demo试跑详细摘要：${summary.run_id}`,'',`- 总体：${summary.status} / exit ${summary.exit_code}；部署：${summary.stages.startup}；报告：${summary.stages.report_collection}；清理：${summary.cleanup_status}。`,`- 用例聚合：通过${totals.passed}、失败${totals.failed}、受阻${totals.blocked}；本报告记录${groups.size}用例。任何blocked子项不构成通过；此文件不是任务5的稳定性结论。`,'- 用例聚合只按已记录子项计算，不证明整个分类协议通过；子进程非零/Schema或身份不合法时总入口分类仍failed。辅助子分类报告请直接查categories，未被选择的类别不算all覆盖。',`- 执行commit：${summary.git_commit}；工作区修改：${summary.git_dirty}；UTC：${summary.started_at} → ${summary.finished_at}。`,`- ${summary.harness_scenario?'明确子场景：'+summary.harness_scenario+'；LIFE协议哨兵不能计成产品passed。':'正式manifest分类试跑；完整受限目标以原用例及分类checks为准。'}`,'','## 分类结果','', '| 分类 | 总入口状态 | 退出 | 子项通过/失败/受阻 |','| --- | --- | --- | --- |',...categories.map(x=>`| ${x.name} | ${labels[x.status]??x.status} | ${x.exit} | ${x.counts.passed}/${x.counts.failed}/${x.counts.blocked} |`),'','## 用例逐项摘要','', '| 用例 | 标题 | 聚合状态 | 通过/失败/受阻 | 说明 | 证据示例 |','| --- | --- | --- | --- | --- |',...rows,'','完整中文过程见logs/category-*.log，全部子项预期/实际/源码依据与证据见categories/*.json；容器/网络/卷/匿名卷/tag及tmp/runtime释放见cleanup.json。'];
fs.writeFileSync(path.join(directory,'summary-详细.md'),content.join('\n'),'utf8');
console.log(`中文详细摘要已生成：${groups.size}用例，分类${categories.length}；不回填正式用例結果。`);
