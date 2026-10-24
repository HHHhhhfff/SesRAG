import fs from 'node:fs';
import path from 'node:path';
import { helper } from '../tooling/product-category.mjs';
import { assert, key, thread, answer, request, run, detail, until } from './support.mjs';
import { openBrowser, openPage, waitText } from './browser-support.mjs';

export const modelRuntime = {
  // MOD_001：导入基线读取与两个实际HTTP模型调用，不用展示名称猜快照。
  async MOD_001({ context: c }) {
    const listed = (await request(c, '/api/v2/models')).data;
    assert.equal(listed.models.length, 4); assert.equal(listed.models.filter((item) => item.is_default).length, 1);
    assert.deepEqual(listed.default_profile, { profile_id: 'mock-default', version: 1 }); const results = [];
    for (const model of ['ws-http-a', 'ws-http-b']) {
      const t = await thread(c, `MOD_001-${model}-${key().slice(0, 8)}`); const created = await answer(c, t, '显式选择真实受控HTTP模型', model);
      assert.equal(created.finished.model.profile_id, model); assert.equal(created.finished.model.version, 1); results.push({ model, run_id: created.run_id });
    }
    return { actual: '四Profile均可区分且唯一默认；HTTP A/B各自真实成功执行，快照ID/version与显式选择一致。', results };
  },
  // MOD_006：事实字段、原始服务日志、API与真实浏览器公开网络/Storage一起审计。
  async MOD_006(suite) {
    const c = suite.context; const t = await thread(c, `MOD_006-${key().slice(0, 8)}`); const created = await answer(c, t, '凭据公开面审计', 'ws-http-a');
    const secrets = [process.env.MODEL_API_KEY, process.env.PROVIDER_CONTROL_TOKEN];
    const publicData = [await run(c, created.run_id), await detail(c, t.thread_id), (await request(c, '/api/v2/models')).data, (await request(c, `/api/v2/runs/${created.run_id}/events`)).data];
    assert.ok(secrets.every((secret) => !JSON.stringify(publicData).includes(secret)));
    const browser = await openBrowser(); let session; const seen = []; const pending = []; const readErrors = [];
    try {
      session = await openPage(browser, c, t, undefined, { beforeNavigate(page) {
        page.on('response', (response) => { if (/\/api\//.test(response.url()) && !response.url().includes('/stream')) {
          pending.push(response.text().then((body) => seen.push({ path: new URL(response.url()).pathname, body })).catch((error) => readErrors.push(error.message)));
        } });
      } });
      await waitText(session.page, '凭据公开面审计');
      const required = ['/api/v2/models', `/api/v2/threads/${t.thread_id}`, `/api/v2/runs/${created.run_id}`, `/api/v2/runs/${created.run_id}/events`, `/api/v2/runs/${created.run_id}/context`];
      await until(() => required.every((endpoint) => seen.some((item) => item.path === endpoint)), Boolean, '浏览器必需公开响应全部采证');
      await Promise.all(pending); assert.deepEqual(readErrors, [], '响应正文读取失败不能跳过');
      const storage = await session.page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
      assert.ok(secrets.every((secret) => !storage.includes(secret) && seen.every(({ body }) => !body.includes(secret))));
    } finally { await session?.session.close(); await browser.close(); }
    const audit = await helper(c, 'audit-public-secrets'); assert.equal(audit.result.log_secret_matches, 0);
    const facts = JSON.parse(fs.readFileSync(path.join(suite.tmp, 'secret-facts.json'), 'utf8')); assert.equal(facts.status, 'passed');
    const evidence = suite.evidence('secret-facts.json', facts);
    return { actual: `实际认证HTTP执行后，6类PG事实字段、原始默认服务日志、API公开响应及真实浏览器${seen.length}项网络观察/Storage均未发现运行凭据。`, audit: audit.result, facts, evidence_paths: [evidence] };
  },
};
