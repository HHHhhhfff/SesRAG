import {runCategory,assert,execute,repoRoot} from '../lib/category-kit.mjs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {deploymentFaultChecks} from '../tooling/lifecycle-focused.mjs';
import {composeRagCheck} from '../tooling/compose-rag-check.mjs';
export const coveredCases=['DEP_001','DEP_002','DEP_003','DEP_004','DEP_005','DEP_006','DEP_007','DEP_008','DEP_009'];

await runCategory('dep',async s=>{
 const c=s.ctx;
 await s.check('DEP_006','TP-DEP-007','root-compose-rag-consumption','根Compose四字段实际传到隔离API/Worker启动，快照、切分、TopK消费及非法启动拒绝',()=>composeRagCheck(c));
 // DEP_001：容器真实拓扑与新卷迁移，不以健康HTTP替代数据库结构。
 await s.check('DEP_001','TP-DEP-001','topology','六服务来自本次隔离容器，迁移成功，五服务运行',async()=>{
  const r=c.compose(['ps','-a','--format','json']);assert.equal(r.code,0);
  const rows=r.stdout.trim().startsWith('[')?JSON.parse(r.stdout):r.stdout.trim().split(/\r?\n/).map(JSON.parse);
  for(const name of ['frontend','api','worker','postgres','redis']) {const item=rows.find(x=>x.Service===name);assert.equal(item?.State,'running',name);}
  const migration=rows.find(x=>x.Service==='migrate');assert.equal(migration?.ExitCode,0);assert.equal(migration.State,'exited');
  return rows.map(x=>({service:x.Service,state:x.State,health:x.Health,exit_code:x.ExitCode}));
 });
 await s.check('DEP_001','TP-DEP-002','schema','Alembic head、vector和七业务表实际存在',()=>{
  const head=execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-c','from alembic.config import Config;from alembic.script import ScriptDirectory;print(ScriptDirectory.from_config(Config("alembic.ini")).get_current_head())']);assert.equal(head.code,0);
  const version=c.sql('SELECT version_num FROM alembic_version');assert.equal(version[0].version_num,head.stdout.trim());
  const tables=c.sql("SELECT tablename FROM pg_tables WHERE schemaname='public'").map(x=>x.tablename);
  for(const name of ['threads','messages','runs','tasks','run_events','documents','chunks'])assert.ok(tables.includes(name),name);
  assert.equal(c.sql("SELECT extname FROM pg_extension WHERE extname='vector'")[0].extname,'vector');return {version,tables};
 });
 // DEP_002：本用例自己建立事实后重复实际迁移，比对ID/内容及约束。
 await s.check('DEP_002','TP-DEP-003','repeat-migration','重复upgrade head不改变已提交的七类事实及约束',async()=>{
  const t=await c.thread('DEP_002迁移保留'), m=await c.submit(t.thread_id,'迁移保留问题');await c.waitRun(m.run_id);
  const doc=await c.upload('dep-repeat.txt',Buffer.from('迁移保留文档'));assert.equal(doc.status,201);await c.waitDoc(doc.body.document_id);
  const snapshot=async()=>({detail:await c.detail(t.thread_id),run:await c.run(m.run_id),tasks:c.sql(`SELECT * FROM tasks WHERE task_id='${m.task_id}' OR document_id='${doc.body.document_id}' ORDER BY task_id`),events:await c.events(m.run_id),docs:c.sql(`SELECT * FROM documents WHERE document_id='${doc.body.document_id}'`),chunks:c.sql(`SELECT chunk_id,document_id,index_batch_id,seq,text,start_offset,end_offset,embedding::text FROM chunks WHERE document_id='${doc.body.document_id}' ORDER BY seq`),constraints:c.sql("SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conname")});
  const before=await snapshot();
  // migrate已退出，因此在API容器注入同一迁移配置执行真实upgrade；不更改产品迁移。
  const repeat=c.python(`import json\nfrom alembic.config import Config\nfrom alembic import command\nfrom backend.config import Settings\nc=Config('alembic.ini');c.set_main_option('sqlalchemy.url',Settings().database_url);command.upgrade(c,'head')\nprint('SMOKE_JSON:'+json.dumps({'exit':'head'}))`);
  assert.equal(repeat.exit,'head');assert.deepEqual(await snapshot(),before);return {thread_id:t.thread_id,run_id:m.run_id,document_id:doc.body.document_id,repeat:'不变'};
 });
 await s.check('DEP_003','TP-DEP-004','declared-migration-gate','根Compose及当前覆盖后的API/Worker声明migrate成功退出依赖',()=>{
  const r=execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-c',"import json,yaml;d=yaml.safe_load(open('docker-compose.yml',encoding='utf8'));print(json.dumps({name:d['services'][name]['depends_on']['migrate']['condition'] for name in ['api','worker']}))"]);assert.equal(r.code,0);const root=JSON.parse(r.stdout);const merged=c.compose(['config','--format','json']);assert.equal(merged.code,0);const config=JSON.parse(merged.stdout);for(const name of ['api','worker']){assert.equal(root[name],'service_completed_successfully');assert.equal(config.services[name].depends_on.migrate.condition,'service_completed_successfully');}return {root,merged:{api:config.services.api.depends_on.migrate.condition,worker:config.services.worker.depends_on.migrate.condition},scope:'静态依赖声明；不代表首次迁移故障已实测'};
 });
 await deploymentFaultChecks(s,['migration-failure'],'DEP_003','TP-DEP-004');
 // DEP_004：API写入与Worker读取同文件哈希，重启后依然存在。
 await s.check('DEP_004','TP-DEP-005','shared-restart','原始字节/哈希/文档/分块在API与Worker共享且重启后保留',async()=>{
  const bytes=Buffer.from('DEP_004共享原文\n中文存储证据');const uploaded=await c.upload('shared.txt',bytes);assert.equal(uploaded.status,201);const id=uploaded.body.document_id;await c.waitDoc(id);
  const before=c.sql(`SELECT document_id,storage_key,content_hash,active_index_batch_id FROM documents WHERE document_id='${id}'`)[0];
  const beforeChunks=c.sql(`SELECT * FROM chunks WHERE document_id='${id}' ORDER BY seq`);assert.ok(beforeChunks.length>0);
  const probe=service=>c.python(`import json,hashlib\nfrom pathlib import Path\nfrom backend.config import Settings\np=Settings().upload_path/${JSON.stringify(before.storage_key)}\nprint('SMOKE_JSON:'+json.dumps({'hash':hashlib.sha256(p.read_bytes()).hexdigest()}))`,{service});
  const expected=createHash('sha256').update(bytes).digest('hex');assert.equal(probe('api').hash,expected);assert.equal(probe('worker').hash,expected);
  const r=c.compose(['restart','api','worker']);assert.equal(r.code,0);await c.ready();assert.deepEqual(c.sql(`SELECT document_id,storage_key,content_hash,active_index_batch_id FROM documents WHERE document_id='${id}'`)[0],before);assert.equal(probe('worker').hash,expected);assert.deepEqual(c.sql(`SELECT * FROM chunks WHERE document_id='${id}' ORDER BY seq`),beforeChunks);return {document_id:id,hash:expected,chunk_ids:beforeChunks.map(x=>x.chunk_id),restart:'持久事实不变'};
 });
 // DEP_005：独立人工数据流校审结论；直接解析根部署，不把测试覆盖当产品修复。
 await s.check('DEP_005','TP-DEP-006','root-secret-review','根部署Secret由运行时传入，不能写死或进入前端/镜像',()=>{
  const r=execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-c',"import yaml,json;d=yaml.safe_load(open('docker-compose.yml',encoding='utf8'));s=d['services'];print(json.dumps({'db_runtime': '${' in str(s['postgres']['environment'].get('POSTGRES_PASSWORD','')), 'api_url_runtime': '${' in str(s['api']['environment'].get('DATABASE_URL','')), 'frontend_secret_keys': [k for k in s['frontend'].get('environment',{}) if 'KEY' in k or 'PASSWORD' in k]}))"]);
  assert.equal(r.code,0);const result=JSON.parse(r.stdout);c.evidence('dep/root-secret-review.json',{...result,review:'Dockerfile COPY与.dockerignore边界、前端仅VITE_API_BASE_URL已逐项审阅；根Compose密码/URL通过运行时必填注入，测试使用本次随机密码。'});assert.ok(result.db_runtime&&result.api_url_runtime,'根Compose数据库密码/连接串仍为固定字面值；不是运行时Secret注入');assert.deepEqual(result.frontend_secret_keys,[]);return result;
 });
 // DEP_006：对真实Settings构造逐个非法值，不以配置字段存在为通过。
 await s.check('DEP_006','TP-DEP-007','invalid-settings','正值有效，0/负值和heartbeat>=TTL在使用前拒绝',()=>{
  const result=c.python(`import json\nfrom backend.config import Settings\nitems=[]\nfor k in ['task_lease_ttl','task_heartbeat_interval','task_max_attempts','task_deadline']:\n for v in [0,-1]:\n  try: Settings(**{k:v}); rejected=False\n  except ValueError: rejected=True\n  items.append({'field':k,'value':v,'rejected':rejected})\nfor hb in [30,31]:\n try: Settings(task_lease_ttl=30,task_heartbeat_interval=hb); rejected=False\n except ValueError: rejected=True\n items.append({'field':'heartbeat>=TTL','value':hb,'rejected':rejected})\nvalid=Settings(task_lease_ttl=30,task_heartbeat_interval=10)\nprint('SMOKE_JSON:'+json.dumps({'items':items,'valid':valid.task_lease_ttl==30}))`);
  c.evidence('dep/invalid-settings.json',result);assert.ok(result.valid);assert.ok(result.items.every(x=>x.rejected),'Settings接受无效周期/期限/次数组合');return result;
 });
 await s.check('DEP_007','TP-DEP-008','vector-config','384匹配，128必须拒绝或存在匹配PG列',()=>{
  const column=c.sql("SELECT format_type(a.atttypid,a.atttypmod) AS type FROM pg_attribute a WHERE a.attrelid='chunks'::regclass AND a.attname='embedding'")[0].type;
  const r=c.python(`import json\nfrom backend.config import Settings\nfrom backend.infrastructure.providers.mock import MockEmbeddingProvider\na=Settings(vector_dimension=384)\ntry: Settings(vector_dimension=128);accepted=True\nexcept ValueError: accepted=False\nprint('SMOKE_JSON:'+json.dumps({'default':len(MockEmbeddingProvider(a.vector_dimension).embed('q')),'accepted128':accepted}))`);
  c.evidence('dep/vector-dimension.json',{column,...r});assert.equal(column,'vector(384)');assert.equal(r.default,384);assert.ok(!r.accepted128||column==='vector(128)','Settings接受128，数据库固定384且无启动拒绝');return {column,...r};
 });
 await s.check('DEP_008','TP-DEP-009','constraints','外键、seq唯一、用户消息唯一、幂等复合unique及Task kind CHECK齐全',()=>{
  const rows=c.sql("SELECT conrelid::regclass::text AS table_name,contype,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE connamespace='public'::regnamespace");c.evidence('dep/constraints.json',rows);
  const has=(table,kind,regex)=>rows.some(x=>x.table_name===table&&x.contype===kind&&regex.test(x.definition));
  for(const [table,regex] of [['messages',/UNIQUE \(thread_id, seq\)/],['run_events',/UNIQUE \(run_id, seq\)/],['chunks',/UNIQUE \(document_id, index_batch_id, seq\)/],['runs',/UNIQUE \(user_message_id\)/]])assert.ok(has(table,'u',regex),table);
  const foreignKeys=[['messages',/FOREIGN KEY \(thread_id\) REFERENCES threads\(thread_id\)/],['runs',/FOREIGN KEY \(thread_id\) REFERENCES threads\(thread_id\)/],['tasks',/FOREIGN KEY \(run_id\) REFERENCES runs\(run_id\)/],['run_events',/FOREIGN KEY \(run_id\) REFERENCES runs\(run_id\)/],['chunks',/FOREIGN KEY \(document_id\) REFERENCES documents\(document_id\)/]];
  for(const [table,definition]of foreignKeys)assert.ok(has(table,'f',definition),`${table}外键${definition}缺失`);
  c.evidence('dep/application-only-relationships.json',{review:'Run.user_message_id/assistant_message_id/primary_task_id和Task.document_id目前为String，无正式FK；ADR要求关系由应用校验，未逐条承诺均为DB外键。此差异记录为约束加固风险，不额外创造验收约束。',checked_declared_foreign_keys:foreignKeys.map(x=>x[0])});
  const checks=rows.filter(x=>x.table_name==='tasks'&&x.contype==='c').map(x=>x.definition.replace(/^CHECK\s*/,'').replace(/\s+NOT VALID$/,''));
  const expression=checks.length?checks.map(x=>`(${x}) IS DISTINCT FROM FALSE`).join(' AND '):'TRUE';
  // 只读VALUES真值表评估实际CHECK，kind非空等弱约束不能冒充kind/关联互斥保护。
  const actual=c.sql(`SELECT kind,run_id,document_id,(${expression}) AS admitted FROM (VALUES (1,'run'::text,'r'::text,NULL::text),(2,'run',NULL,NULL),(3,'run',NULL,'d'),(4,'run','r','d'),(5,'index_document',NULL,'d'),(6,'index_document',NULL,NULL),(7,'index_document','r',NULL),(8,'index_document','r','d'),(9,'unknown',NULL,NULL),(10,'unknown','r',NULL),(11,'unknown',NULL,'d'),(12,'unknown','r','d')) AS input(n,kind,run_id,document_id) ORDER BY n`);
  // 完整12组合包括index_document双关联；仅两个合法kind/单一身份组合可以入库。
  const expected=[true,false,false,false,true,false,false,false,false,false,false,false];
  c.evidence('dep/task-check-truth-table.json',{expressions:checks,rows:actual,expected_admitted:expected});
  const missing=[];if(!has('messages','u',/thread_id, idempotency_key/))missing.push('messages(thread_id,idempotency_key) unique');if(JSON.stringify(actual.map(x=>x.admitted))!==JSON.stringify(expected))missing.push('tasks kind/run_id/document_id CHECK语义不完整');assert.deepEqual(missing,[],'用例规定约束缺失/不完整');return rows;
 });
 await s.check('DEP_009','TP-DEP-010','cold-start-dependency-review','通知可降级：API/Worker冷启动不由Redis healthy硬门禁阻断',()=>{
  const r=execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-c',"import json,yaml;d=yaml.safe_load(open('docker-compose.yml',encoding='utf8'));print(json.dumps({name:d['services'][name]['depends_on'].get('redis') for name in ['api','worker']}))"]);assert.equal(r.code,0);const result=JSON.parse(r.stdout);c.evidence('dep/redis-cold-dependency.json',{dependencies:result,review:'根Compose未以Redis healthy阻断启动；冷启动降级与真实Run完成另由独立固定场景验证。'});assert.ok(!Object.values(result).some(x=>x?.condition==='service_healthy'),'根编排仍硬依赖Redis healthy，冷启动无法执行通知降级');return result;
 });
 await deploymentFaultChecks(s,['redis-cold'],'DEP_009','TP-DEP-010');
});
