import {runCategory,assert} from '../lib/category-kit.mjs';
import {chromium} from 'playwright';
export const coveredCases=['SEC_001','SEC_002','SEC_003','SEC_004','SEC_005'];

await runCategory('sec',async s=>{
 const c=s.ctx;
 // SEC_001：只请求已知测试文件候选直链，不枚举宿主文件。
 await s.check('SEC_001','TP-SEC-001','static-paths','API/frontend上传候选直链不能暴露原始正文',async()=>{
  const marker='PUBLIC_FILE_SENTINEL_SAFE';const u=await c.upload('private.txt',Buffer.from(marker));assert.equal(u.status,201);await c.waitDoc(u.body.document_id);const row=c.sql(`SELECT storage_key FROM documents WHERE document_id='${u.body.document_id}'`)[0];const observations=[];
  for(const origin of [c.args.BaseUrl,c.args.FrontendUrl])for(const prefix of ['/uploads/','/data/uploads/','/']) {const response=await fetch(origin+prefix+row.storage_key,{signal:AbortSignal.timeout(5000)});const text=await response.text();assert.ok(!text.includes(marker),'原始测试文件从静态HTTP泄漏');observations.push({origin:origin===c.args.BaseUrl?'api':'frontend',path:prefix+'<测试storage_key>',status:response.status});}return observations;
 });
 // SEC_002：容器内专属TemporaryDirectory/symlink，异常必须拒绝实际外部哨兵读取。
 await s.check('SEC_002','TP-SEC-002','traversal-symlink','正常key可读，../绝对key和解析后symlink逃逸全部拒绝',()=>{
  const r=c.python(`import json,tempfile\nfrom pathlib import Path\nfrom backend.infrastructure.storage.local_files import LocalFileStorage\nwith tempfile.TemporaryDirectory(prefix='sesrag-sec-') as d:\n base=Path(d);root=base/'uploads';store=LocalFileStorage(root);outside=base/'outside.txt';outside.write_bytes(b'SAFE_SENTINEL')\n key,h=store.save('test-id','.txt',b'normal');normal=store.read(key)==b'normal';(root/'link.txt').symlink_to(outside)\n rows=[]\n for x in ['../outside.txt',str(outside),'link.txt']:\n  try: store.read(x); rejected=False\n  except ValueError: rejected=True\n  rows.append({'kind':'absolute' if x==str(outside) else x,'rejected':rejected})\n print('SMOKE_JSON:'+json.dumps({'normal':normal,'rows':rows}))`);assert.ok(r.normal);assert.ok(r.rows.every(x=>x.rejected));return r;
 });
 // SEC_003：真实双角色持久正文进入真实浏览器组件后才检验清洗。
 // 安全和正常格式分别断言；Mock前缀影响首行h1，后续行首h2/代码仍是真实Markdown正常内容。
 for(const role of ['user','assistant'])for(const part of ['safety','normal-format'])await s.check('SEC_003','TP-SEC-003',`${role}-${part}`,part==='safety'?`${role}实际攻击Markdown不执行，危险属性/URL被清洗`:`${role}清洗后保留后续行首标题与代码`,async()=>{
  const payload='# 安全标题\n\n<script>window.__sesrag_xss=1</script><img src="/safe-xss-probe" onerror="window.__sesrag_xss=2"><a href="javascript:window.__sesrag_xss=3">危险链接</a>\n\n## 持久正常小标题\n\n`安全代码`';
  const u=await c.upload('xss-proof.txt',Buffer.from(payload));assert.equal(u.status,201);await c.waitDoc(u.body.document_id);
  const thread=await c.thread(`SEC_003真实${role}-${part}清洗`);const r=await c.submit(thread.thread_id,payload);assert.equal((await c.waitRun(r.run_id)).status,'succeeded');const detail=await c.detail(thread.thread_id);const user=detail.messages.find(x=>x.role==='user'),assistant=detail.messages.find(x=>x.role==='assistant');assert.ok(user.content.includes('<script>'));assert.ok(assistant?.content.includes('<script>'),'攻击样例未进入assistant正文，不能以空白判清洗通过');
  const browser=await chromium.launch({headless:true});try {const page=await browser.newPage();let dialogs=0;page.on('dialog',async d=>{dialogs++;await d.dismiss();});await page.goto(c.args.FrontendUrl);await page.getByRole('button',{name:thread.title,exact:true}).click();await page.locator('.message.assistant').waitFor();
   const article=page.locator(`.message.${role}`);await article.waitFor();
   if(part==='safety'){assert.equal(await article.locator('script,[onerror],a[href^="javascript:"]').count(),0);assert.equal(await page.evaluate(()=>window.__sesrag_xss),undefined);assert.equal(dialogs,0);}
   else {assert.equal(await article.locator('h2').textContent(),'持久正常小标题');assert.equal(await article.locator('code').textContent(),'安全代码');}
   return {thread_id:thread.thread_id,run_id:r.run_id,role,part,attack_original_confirmed:true,actual:'安全哨兵未执行或对应正常格式保留，按本子项独立判断'};
  }finally {await browser.close();}
 });
 await s.check('SEC_004','TP-SEC-004','safe-errors','缺对象/校验错误无凭据、堆栈和宿主路径，协议分别判',async()=>{
  const missing=await c.request('/api/v1/threads/00000000-0000-0000-0000-000000000000');assert.equal(missing.status,404);assert.equal(missing.body.code,'THREAD_NOT_FOUND');
  const invalid=await c.request('/api/v1/threads',{method:'POST',body:{title:''}});assert.equal(invalid.status,422);assert.ok(Array.isArray(invalid.body.detail));for(const r of [missing,invalid])assert.ok(!/Traceback|postgresql:\/\/|[A-Z]:\\/.test(JSON.stringify(r.body)));return {missing,invalid};
 });
 await s.check('SEC_004','TP-SEC-005','normal-facts','正常snapshot/Event/Message和默认日志不泄漏本次临时密码',async()=>{
  const t=await c.thread('SEC_004事实');const m=await c.submit(t.thread_id,'公开测试问题');await c.waitRun(m.run_id);const facts={detail:await c.detail(t.thread_id),events:await c.events(m.run_id),snapshot:c.sql(`SELECT snapshot_json FROM runs WHERE run_id='${m.run_id}'`)};const logs=c.compose(['logs','--no-color','--tail','200','api','worker']);const combined=JSON.stringify(facts)+logs.stdout;assert.ok(!combined.includes(c.env.SMOKE_DB_PASSWORD));assert.ok(!JSON.stringify(facts).includes('model_api_key'));return {run_id:m.run_id,normal_secret_leak:false};
 });
 for(const tp of ['TP-SEC-004','TP-SEC-005'])s.block('SEC_004',tp,'exception-sentinel','存储/Provider异常源敏感哨兵在全部输出面脱敏','E2/E4异常驱动尚未完成；正常事实无密码不代表异常str(exc)已脱敏。DB故障响应另HLT_002真实执行。');
 await s.check('SEC_005','TP-SEC-006','bounded-upload-review','上传应在全量读前有界拒绝，而不是读完才检查10MiB',()=>{
  const result=c.python(`import ast,json,pathlib\nt=ast.parse(pathlib.Path('backend/api/routes/documents.py').read_text())\nf=next(n for n in ast.walk(t) if isinstance(n,ast.AsyncFunctionDef) and n.name=='upload_document')\nreads=[n for n in ast.walk(f) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='read']\nprint('SMOKE_JSON:'+json.dumps({'unbounded_reads':sum(not n.args and not n.keywords for n in reads),'read_calls':len(reads)}))`);
  c.evidence('sec/upload-memory-review.json',{...result,review:'数据流已审阅：await file.read -> create_document大小检查；app无请求体上限。AST仅检测此已确认路径的无界read形态，未来改变结构需重审，不自动推断其他中间件正确。',dynamic_resource_exhaustion:'未运行'});
  assert.equal(result.unbounded_reads,0,'上传函数仍无参数全量read，在大小校验前分配内存');return result;
 });
});
