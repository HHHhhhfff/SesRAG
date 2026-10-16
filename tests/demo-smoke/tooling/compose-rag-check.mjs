import fs from 'node:fs'
import path from 'node:path'
import {randomUUID} from 'node:crypto'
import {Context,parseArgs,execute,executeTree,repoRoot,assert,redact} from '../lib/category-kit.mjs'
import {registerResource,resourceIdentity,closeResource} from './pg-execution.mjs'

const keys=['VECTOR_DIMENSION','RAG_TOP_K','CHUNK_SIZE','CHUNK_OVERLAP']
export function composeEvidence(ctx,name,result){
 // 先对原始字符串脱敏再交结构对象，避免路径正则吞掉JSON中的引号转义。
 const safe={...result}
 for(const key of ['stdout','stderr','error']) if(typeof safe[key]==='string') safe[key]=redact(safe[key],ctx.secrets)
 const relative=ctx.evidence(name,safe)
 const stored=JSON.parse(fs.readFileSync(path.join(ctx.args.ArtifactDir,relative),'utf8'))
 assert.equal(stored.code,result.code,'落盘证据必须保留真实进程退出码')
 return relative
}
function rootConfig(ctx,values){
 const env={DATABASE_URL:ctx.env.DATABASE_URL,POSTGRES_PASSWORD:'synthetic-compose-only',...values}
 const result=execute('docker',['compose','--env-file','NUL','-f',path.join(repoRoot,'docker-compose.yml'),'config','--format','json'],{env,timeoutMs:30000})
 assert.equal(result.code,0,'根Compose解析失败')
 // 完整配置含DSN，只在内存消费；输出只保留本次四个非敏感字段。
 const config=JSON.parse(result.stdout)
 return Object.fromEntries(['api','worker'].map(service=>[service,Object.fromEntries(keys.map(key=>[key,config.services[service].environment[key]]))]))
}

export async function composeRagCheck(ctx){
 const defaults=rootConfig(ctx,Object.fromEntries(keys.map(key=>[key,''])))
 for(const service of ['api','worker']) assert.deepEqual(defaults[service],{VECTOR_DIMENSION:'384',RAG_TOP_K:'5',CHUNK_SIZE:'800',CHUNK_OVERLAP:'120'})
 ctx.evidence('compose-rag/root-defaults.json',defaults)
 const values={VECTOR_DIMENSION:'384',RAG_TOP_K:'1',CHUNK_SIZE:'96',CHUNK_OVERLAP:'8'}
 const config=rootConfig(ctx,values)
 ctx.evidence('compose-rag/root-config.json',config)
 for(const service of ['api','worker']) assert.deepEqual(config[service],values,`${service}根Compose四配置必须实际接线`)
 const reports=[]
 for(const service of ['api','worker']){
  for(const invalid of [null,{VECTOR_DIMENSION:'128'},{RAG_TOP_K:'0'},{CHUNK_SIZE:'0'},{CHUNK_OVERLAP:'96'}]){
   const token=randomUUID().replaceAll('-','').slice(0,8),resource=resourceIdentity(ctx.context.compose_project,ctx.args.RunId,token)
   registerResource(ctx,resource,'planned')
   const consumed=rootConfig(ctx,{...values,...invalid})[service]
   const args=['run','--rm','--name',resource.name,'--network',`${resource.project}_default`,
    ...Object.entries(resource.labels).flatMap(([k,v])=>['--label',`${k}=${v}`]),
    '--volume',`${repoRoot.replaceAll('\\','/')}:/work:ro`,'--workdir','/work',
    '--env','DATABASE_URL','--env','PYTHONPATH=/work','--env','PYTHONDONTWRITEBYTECODE=1',
    '--env',`PG_SCENARIO_TOKEN=${token}`,...Object.entries(consumed).flatMap(([k,v])=>['--env',`${k}=${v}`]),
    '--entrypoint','python',`${resource.project}-backend:local`,
    ...(invalid?['-c',`import backend.${service==='api'?'app':'workers.main'}`]:['tests/demo-smoke/tooling/compose_rag_consumer.py'])]
   try{
    const result=await executeTree('docker',args,{timeoutMs:45000,env:{DATABASE_URL:ctx.env.DATABASE_URL}})
    const evidence=composeEvidence(ctx,`compose-rag/${service}-${token}.json`,{settings:consumed,invalid,...result})
    assert.equal(result.timed_out,false)
    if(invalid){assert.notEqual(result.code,0);assert.match(result.stderr,/ValidationError/)}
    else {assert.equal(result.code,0);assert.match(result.stdout,/COMPOSE_RAG:/)}
    reports.push({service,invalid,exit_code:result.code,evidence})
   }finally{closeResource(ctx,resource)}
  }
 }
 return reports
}

if(process.argv[1]===new URL(import.meta.url).pathname.replace(/^\/(?:([A-Za-z]:))/, '$1') || process.argv[1]?.endsWith('compose-rag-check.mjs')){
 const ctx=new Context(parseArgs());console.log(JSON.stringify(await composeRagCheck(ctx)))
}
