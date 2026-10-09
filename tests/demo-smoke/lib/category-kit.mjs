import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync, spawn } from 'node:child_process';

export { assert };
export const smokeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const repoRoot = path.resolve(smokeRoot, '../..');

export function parseArgs(argv = process.argv.slice(2)) {
  const result = {};
  const keys = ['BaseUrl','FrontendUrl','RunId','ArtifactDir','RuntimeDir','FixtureDir'];
  for (let i=0; i<argv.length; i+=2) {
    const key=argv[i]?.replace(/^-/, '');
    if (!keys.includes(key) || !argv[i+1] || key in result) throw new Error('分类参数无效');
    result[key]=argv[i+1];
  }
  for (const key of keys) if (!result[key]) throw new Error(`缺少分类参数：${key}`);
  return result;
}

export function readCases() {
  const source=fs.readFileSync(path.join(smokeRoot,'test-cases.md'),'utf8');
  const result=new Map();
  for (const match of source.matchAll(/^#### ([A-Z]+_\d{3})：(.*?)\r?\n([\s\S]*?)(?=^#### |^### |^## |$(?![\s\S]))/gm)) {
    const field=name=>match[3].match(new RegExp(`^- ${name}：([^\\r\\n]*)`,'m'))?.[1] ?? '';
    result.set(match[1],{id:match[1],title:match[2],points:[...field('对应测试点').matchAll(/TP-[A-Z]+-\d{3}/g)].map(x=>x[0]),state:field('当前可验证状态'),expected:field('预期结果'),flow:field('测试流程'),preconditions:field('前置条件'),source:field('代码依据')});
  }
  return result;
}

export function aggregateStatus(checks) {
  if (!checks.length) return 'not_ready';
  for (const state of ['failed','not_ready','blocked','skipped']) if (checks.some(x=>x.status===state)) return state;
  return 'passed';
}

export function redact(value,secrets=[]) {
  let text=typeof value==='string' ? value : JSON.stringify(value);
  for (const secret of secrets.filter(x=>x && x.length>=8)) text=text.split(secret).join('[已脱敏]');
  return text.replace(/(postgres(?:ql)?(?:\+\w+)?:\/\/[^:\s]+:)[^@\s]+@/gi,'$1[已脱敏]@')
    .replace(/Bearer\s+[^\s"']+/gi,'Bearer [已脱敏]')
    .replace(/((?:api[_-]?key|model_api_key|password|SMOKE_DB_PASSWORD)["']?\s*[=:]\s*["']?)[^\s,"'}/]+/gi,'$1[已脱敏]')
    .replace(/(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s"'\r\n<>]+/g,'[宿主路径已脱敏]')
    .replace(/\/(?:data\/uploads|usr\/local|app|tmp|home|Users)\/[^\s"'\r\n<>]+/g,'[运行路径已脱敏]');
}

export function safeChild(root,name) {
  if (!name || path.isAbsolute(name) || /^(?:[A-Za-z]:|[\\/])/.test(name)) throw new Error('证据路径越界');
  const base=path.resolve(root), target=path.resolve(base,name);
  if (target===base || !target.startsWith(base+path.sep)) throw new Error('证据路径越界');
  let parent=target;
  while (parent.startsWith(base+path.sep)) {
    if (fs.existsSync(parent) && fs.lstatSync(parent).isSymbolicLink()) throw new Error('证据路径越界：符号链接');
    parent=path.dirname(parent);
  }
  return target;
}

export function execute(command,args,options={}) {
  const result=spawnSync(command,args,{cwd:repoRoot,encoding:'utf8',timeout:options.timeoutMs??60000,maxBuffer:16*1024*1024,windowsHide:true,input:options.input,env:{...process.env,PYTHONIOENCODING:'utf-8',...options.env}});
  return {code:result.status ?? -1,stdout:result.stdout??'',stderr:result.stderr??'',error:result.error?.message};
}

export async function executeTree(command,args,options={}) {
  // QLT_007独立FE辅助：超时必须终止Chromium/Vitest后代，不只杀直接Node；保留真实非零退出。
  const child=spawn(command,args,{cwd:repoRoot,windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONIOENCODING:'utf-8',...options.env}});
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
  let stdout='',stderr='',timedOut=false,launchError;
  child.stdout.on('data',chunk=>{stdout+=chunk;});child.stderr.on('data',chunk=>{stderr+=chunk;});
  const timer=setTimeout(()=>{
    timedOut=true;
    if(process.platform==='win32')execute('taskkill',['/PID',String(child.pid),'/T','/F'],{timeoutMs:15000});
    else child.kill('SIGKILL');
  },options.timeoutMs??60000);
  try {
    const code=await new Promise(resolve=>{child.on('error',error=>{launchError=error.message;resolve(-1);});child.on('close',value=>resolve(value??-1));});
    return {code:timedOut?124:code,stdout,stderr,timed_out:timedOut,error:launchError??(timedOut?'辅助进程树超时':undefined)};
  }finally{clearTimeout(timer);}
}

export class Context {
  constructor(args) {
    this.args=args;
    this.context=JSON.parse(fs.readFileSync(path.join(args.RuntimeDir,'context.json'),'utf8').replace(/^\uFEFF/,''));
    assert.equal(this.context.run_id,args.RunId);
    assert.equal(this.context.marker,'sesrag-demo-smoke-v1');
    assert.match(this.context.compose_project,/^sesrag-demo-smoke-[a-z0-9-]+$/);
    this.env={};
    for (const line of fs.readFileSync(path.join(args.RuntimeDir,'compose.env'),'utf8').split(/\r?\n/)) {
      const match=line.replace(/^\uFEFF/,'').match(/^(SMOKE_[A-Z_]+)=(.*)$/);
      if (match) this.env[match[1]]=match[2];
    }
    assert.equal(this.env.SMOKE_PROJECT,this.context.compose_project);
    this.secrets=[this.env.SMOKE_DB_PASSWORD];
    this.evidencePaths=[];
  }
  evidence(name,value) {
    const relative=`evidence/${name}`;
    const target=safeChild(this.args.ArtifactDir,relative);
    fs.mkdirSync(path.dirname(target),{recursive:true});
    fs.writeFileSync(target,redact(value,this.secrets),'utf8');
    const nameInReport=relative.replaceAll('\\','/');
    this.evidencePaths.push(nameInReport);
    return nameInReport;
  }
  compose(args,timeoutMs=60000) {
    // 所有容器操作绑定六参数传入的本次 project，拒绝分类自行销毁环境。
    assert.ok(!args.some(x=>['down','rm','prune'].includes(x)),'分类无环境销毁权限');
    return execute('docker',['compose','--project-name',this.context.compose_project,'--project-directory',repoRoot,'--env-file',path.join(this.args.RuntimeDir,'compose.env'),'-f',path.join(repoRoot,'docker-compose.yml'),'-f',path.join(smokeRoot,'compose/docker-compose.demo-smoke.yml'),...args],{timeoutMs,env:this.env});
  }
  sql(sql) {
    assert.match(sql.trim(),/^SELECT\b/i,'仅允许只读SELECT');
    assert.ok(!/;|\b(?:insert|update|delete|drop|alter|truncate|copy|pg_sleep|dblink)\b/i.test(sql),'禁止修改事实或无界SQL');
    const r=this.compose(['exec','-T','postgres','psql','-U','sesrag','-d','sesrag','-qAtc',`BEGIN READ ONLY; SELECT coalesce(json_agg(t),'[]'::json) FROM (${sql}) t; COMMIT;`],15000);
    assert.equal(r.code,0,redact(r.stderr,this.secrets));
    return JSON.parse(r.stdout.trim());
  }
  python(source,{service='api',timeoutMs=30000}={}) {
    assert.ok(['api','worker'].includes(service));
    // stdin必须交给独立进程，而不是shell字符串插值。
    const args=['compose','--project-name',this.context.compose_project,'--project-directory',repoRoot,'--env-file',path.join(this.args.RuntimeDir,'compose.env'),'-f',path.join(repoRoot,'docker-compose.yml'),'-f',path.join(smokeRoot,'compose/docker-compose.demo-smoke.yml'),'exec','-T',service,'python','-'];
    const real=execute('docker',args,{timeoutMs,input:source,env:this.env});
    assert.equal(real.code,0,redact(real.stderr||real.stdout,this.secrets));
    const line=real.stdout.split(/\r?\n/).findLast(x=>x.startsWith('SMOKE_JSON:'));
    assert.ok(line,'Python驱动没有输出SMOKE_JSON报告');
    return JSON.parse(line.slice('SMOKE_JSON:'.length));
  }
  async request(route,{method='GET',body,headers={},timeoutMs=10000}={}) {
    const form=body instanceof FormData;
    try {
      const response=await fetch(new URL(route,this.args.BaseUrl),{method,body:body===undefined?undefined:form?body:JSON.stringify(body),headers:form?headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...headers},signal:AbortSignal.timeout(timeoutMs)});
      const text=await response.text();
      let value; try {value=JSON.parse(text);} catch {value=text;}
      return {status:response.status,body:value,headers:Object.fromEntries(response.headers)};
    }catch(error){
      // 传输失败不能仅输出fetch failed或自动重试写请求；保留安全错误码用于与产品HTTP失败区分。
      throw new Error(`HTTP传输未完成：${method} ${route}；${error.name}/${error.cause?.code??'无底层码'}；${redact(error.cause?.message??error.message,this.secrets)}`,{cause:error});
    }
  }
  async thread(title='测试会话') {const r=await this.request('/api/v1/threads',{method:'POST',body:{title}});assert.equal(r.status,201);return r.body;}
  async submit(id,content='测试问题',key) {const r=await this.request(`/api/v1/threads/${id}/messages`,{method:'POST',body:{content},headers:key?{'Idempotency-Key':key}:{}});assert.ok([200,201].includes(r.status),`提交返回${r.status}`);return r.body;}
  async detail(id) {const r=await this.request(`/api/v1/threads/${id}`);assert.equal(r.status,200);return r.body;}
  async run(id) {const r=await this.request(`/api/v1/runs/${id}`);assert.equal(r.status,200);return r.body;}
  async events(id,after=0) {const r=await this.request(`/api/v1/runs/${id}/events?after_seq=${after}`);assert.equal(r.status,200);return r.body.events;}
  async waitRun(id,timeoutMs=15000) {return poll(async()=>{const r=await this.run(id);return ['succeeded','failed','cancelled'].includes(r.status)?r:null;},timeoutMs,`Run ${id}未进入终态`);}
  async upload(name,bytes,mime='text/plain') {const form=new FormData();form.append('file',new Blob([bytes],{type:mime}),name);return this.request('/api/v1/documents',{method:'POST',body:form});}
  async waitDoc(id,timeoutMs=15000) {return poll(async()=>{const r=await this.request('/api/v1/documents');assert.equal(r.status,200);const doc=r.body.documents.find(x=>x.document_id===id);return doc && ['indexed','failed'].includes(doc.status)?doc:null;},timeoutMs,`Document ${id}未完成索引`);}
  async ready(timeoutMs=15000) {return poll(async()=>{try {const r=await this.request('/health/ready');return r.status===200&&r.body.worker_count>0?r.body:null;}catch{return null;}},timeoutMs,'恢复后环境未就绪');}
}

export async function poll(fn,timeoutMs=15000,message='等待条件超时') {
  const until=performance.now()+timeoutMs;
  while (performance.now()<until) {const r=await fn();if(r) return r;await new Promise(resolve=>setTimeout(resolve,150));}
  throw new Error(message);
}

export class Suite {
  constructor(name,ctx) {this.name=name;this.ctx=ctx;this.checks=[];this.started=new Date().toISOString();this.cases=readCases();}
  note(message) {process.stdout.write(`【${this.name}】${redact(message,this.ctx.secrets)}\n`);}
  async check(caseId,tpId,sub,expected,fn) {
    assert.ok(this.cases.get(caseId)?.points.includes(tpId),`未知用例/测试点：${caseId}/${tpId}`);
    const id=`${caseId}__${tpId}__${sub}`;
    assert.ok(!this.checks.some(x=>x.id===id),'check ID重复');
    this.note(`${id} 开始；预期：${expected}`);
    const started_at=new Date().toISOString();
    const evidenceStart=this.ctx.evidencePaths.length;
    let status='passed',actual;
    try {actual=await fn(this.ctx);if(actual===undefined) actual='全部独立断言通过';} catch(error) {status=error.blocked?'blocked':'failed';actual=error.message;}
    const evidence=this.ctx.evidence(`${this.name}/${id}.json`,{case_id:caseId,test_point_id:tpId,status,expected,actual,started_at,finished_at:new Date().toISOString()});
    this.checks.push({id,test_point_id:tpId,status,expected,actual:redact(actual,this.ctx.secrets),evidence:[...new Set([...this.ctx.evidencePaths.slice(evidenceStart),evidence])],code_source:this.cases.get(caseId).source});
    this.note(`${id} ${status==='passed'?'通过':status==='failed'?'失败':'受阻'}；实际：${redact(actual,this.ctx.secrets)}`);
    return status;
  }
  block(caseId,tpId,sub,expected,reason) {
    const id=`${caseId}__${tpId}__${sub}`;
    assert.ok(this.cases.get(caseId)?.points.includes(tpId));
    assert.ok(!this.checks.some(x=>x.id===id));
    this.checks.push({id,test_point_id:tpId,status:'blocked',expected,actual:reason,evidence:[]});
    this.note(`${id} 受阻：${reason}`);
  }
  blockCase(caseId,reason) {for(const tp of this.cases.get(caseId).points) this.block(caseId,tp,'full-scenario',this.cases.get(caseId).expected,reason);}
  finish() {
    const status=aggregateStatus(this.checks);
    const report={schema_version:1,run_id:this.ctx.args.RunId,category:this.name,status,started_at:this.started,finished_at:new Date().toISOString(),checks:this.checks,evidence:this.checks.flatMap(x=>x.evidence)};
    const target=safeChild(this.ctx.args.ArtifactDir,`categories/${this.name}.json`);
    fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,JSON.stringify(report,null,2),'utf8');
    this.note(`完成：${this.checks.length} 个子项；${status}；报告 categories/${this.name}.json`);
    return report;
  }
}

export async function runCategory(name,fn) {
  const suite=new Suite(name,new Context(parseArgs()));
  try {await fn(suite);} finally {const report=suite.finish();process.exitCode=report.status==='passed'?0:report.status==='blocked'?2:1;}
}

export function registerNestedRun(ctx,state) {
  // 嵌套身份在收到stdout时即写父runtime，外层kill分类树后仍能精确恢复。
  assert.equal(state.marker,'sesrag-demo-smoke-v1');
  assert.match(state.run_id,/^[a-z0-9][a-z0-9-]{0,100}$/);
  assert.match(state.compose_project,/^sesrag-demo-smoke-[a-z0-9-]+$/);
  assert.notEqual(state.run_id,ctx.args.RunId);assert.notEqual(state.compose_project,ctx.context.compose_project);
  const target=path.join(ctx.args.RuntimeDir,'nested-runs.json');
  const registry=fs.existsSync(target)?JSON.parse(fs.readFileSync(target,'utf8')):{schema_version:1,parent_run_id:ctx.args.RunId,nested:[]};
  assert.equal(registry.parent_run_id,ctx.args.RunId);
  if(!registry.nested.some(x=>x.run_id===state.run_id))registry.nested.push({run_id:state.run_id,compose_project:state.compose_project});
  const temporary=target+'.tmp';fs.writeFileSync(temporary,JSON.stringify(registry,null,2),'utf8');fs.renameSync(temporary,target);
}

export function createNestedRunObserver(ctx,runtimeRoot=path.join(smokeRoot,'runtime')) {
  // DOC_003/RAG_003：回调I/O异常必须回到await/finally；先留精确身份，不能让未捕获异常跳过恢复。
  let output='';
  const observer={runId:undefined,project:undefined,error:undefined,observe(chunk) {
    output+=chunk;
    const match=output.match(/Run: ([a-z0-9-]+)；project: (sesrag-demo-smoke-[a-z0-9-]+)\r?\n/);
    if(!match||observer.runId)return;
    observer.runId=match[1];observer.project=match[2];
    try {
      assert.notEqual(observer.runId,ctx.args.RunId);assert.notEqual(observer.project,ctx.context.compose_project);
      const runtime=safeChild(runtimeRoot,observer.runId);
      const state=JSON.parse(fs.readFileSync(path.join(runtime,'context.json'),'utf8').replace(/^\uFEFF/,''));
      assert.equal(state.run_id,observer.runId);assert.equal(state.compose_project,observer.project);
      registerNestedRun(ctx,state);
    }catch(error){observer.error=error;}
  }};
  return observer;
}

export async function executeNestedScenario(ctx,scenario) {
  // RAG_003：独立新知识库由总入口拥有完整生命周期，分类不直接创建/销毁Docker资源。
  assert.ok(['rag-empty','doc-limit'].includes(scenario),'不允许任意嵌套环境场景');
  const project=ctx.context.compose_project;
  const child=spawn('pwsh',['-NoProfile','-File',path.join(smokeRoot,'run-demo-smoke.ps1'),'-ProjectName',`sesrag-demo-smoke-${scenario}`,'-HarnessScenario',scenario,'-Build:$false','-BackendImage',`${project}-backend:local`,'-FrontendImage',`${project}-frontend:local`],{cwd:repoRoot,windowsHide:true,stdio:['ignore','pipe','pipe']});
  let stdout='',stderr='',timedOut=false;
  const observer=createNestedRunObserver(ctx);
  child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
  child.stdout.on('data',chunk=>{stdout+=chunk;observer.observe(chunk);});
  child.stderr.on('data',chunk=>{stderr+=chunk;});
  const timer=setTimeout(()=>{timedOut=true;if(process.platform==='win32')execute('taskkill',['/PID',String(child.pid),'/T','/F'],{timeoutMs:15000});else child.kill('SIGKILL');},240000);
  try {
    const code=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',x=>resolve(x??-1));});
    if(observer.error)throw observer.error;
    const {runId,project:childProject}=observer;
    assert.ok(runId,'独立场景未输出run_id');assert.notEqual(runId,ctx.args.RunId);assert.notEqual(childProject,project);
    const dir=safeChild(path.join(smokeRoot,'artifacts'),runId);
    assert.ok(!timedOut,'独立场景240秒超时；finally恢复精确清理');
    assert.ok(fs.existsSync(path.join(dir,'summary.json')),'独立场景没有最终summary；finally恢复精确清理');
    const summary=JSON.parse(fs.readFileSync(path.join(dir,'summary.json'),'utf8').replace(/^\uFEFF/,''));
    const cleanup=JSON.parse(fs.readFileSync(path.join(dir,'cleanup.json'),'utf8').replace(/^\uFEFF/,''));
    const reportPath=path.join(dir,'categories',`${scenario}.json`);
    const report=fs.existsSync(reportPath)?JSON.parse(fs.readFileSync(reportPath,'utf8').replace(/^\uFEFF/,'')):null;
    ctx.evidence(`nested/${scenario}-summary.json`,{summary,cleanup,report,output:redact(stdout+stderr,ctx.secrets)});
    assert.equal(cleanup.status,'passed','独立场景清理未成功，不能通过');
    assert.equal(code,0,`独立${scenario}场景失败，见evidence/nested/${scenario}-summary.json`);
    return {summary,cleanup,report};
  } finally {
    clearTimeout(timer);
    const {runId,project:childProject}=observer;
    if(runId && runId!==ctx.args.RunId && childProject!==project) {
      const runtime=safeChild(path.join(smokeRoot,'runtime'),runId);
      if(fs.existsSync(runtime)) {
        const state=JSON.parse(fs.readFileSync(path.join(runtime,'context.json'),'utf8').replace(/^\uFEFF/,''));
        assert.equal(state.run_id,runId);assert.equal(state.compose_project,childProject);
        const recovery=execute('pwsh',['-NoProfile','-File',path.join(smokeRoot,'run-demo-smoke.ps1'),'-CleanupRunId',runId],{timeoutMs:180000});
        ctx.evidence(`nested/${scenario}-recovery.log`,redact(recovery.stdout+recovery.stderr,ctx.secrets));
        assert.ok(!fs.existsSync(runtime),'嵌套场景恢复清理失败，需按保存run_id恢复');
      }
    }
  }
}
