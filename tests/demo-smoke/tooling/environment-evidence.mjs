import path from 'node:path'
import { Context, parseArgs, execute, repoRoot, assert } from '../lib/category-kit.mjs'
const ctx = new Context(parseArgs())
const source = `import json,sys,importlib.metadata as m
print('SMOKE_JSON:'+json.dumps({'python':sys.version,'packages':{n:m.version(n) for n in ['fastapi','starlette','SQLAlchemy','httpx','alembic','pydantic']}}))`
const host = execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-c',source])
assert.equal(host.code,0)
const results={host:JSON.parse(host.stdout.trim().slice('SMOKE_JSON:'.length)),api:ctx.python(source),worker:ctx.python(source,{service:'worker'}),
  host_pip_check:execute(path.join(repoRoot,'.venv/Scripts/python.exe'),['-m','pip','check']),
  api_pip_check:ctx.compose(['exec','-T','api','python','-m','pip','check']),worker_pip_check:ctx.compose(['exec','-T','worker','python','-m','pip','check'])}
ctx.evidence('qlt/dependency-versions.json',results)
for(const name of ['host_pip_check','api_pip_check','worker_pip_check'])assert.equal(results[name].code,0)
console.log('宿主/API/Worker实际依赖摘要已保存，三者pip check通过')
