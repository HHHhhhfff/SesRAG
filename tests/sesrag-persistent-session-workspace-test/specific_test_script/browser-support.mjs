import { chromium } from 'playwright';
import { assert, until } from './support.mjs';

export async function openBrowser() { return chromium.launch({ headless: true }); }

// UI/PERF均使用真实同源工作台；偏好只保存身份，不向浏览器注入Provider凭据。
export async function openPage(browser, context, item, branchId = item?.default_branch_id, extras = {}) {
  const { beforeNavigate, ...preferences } = extras;
  const session = await browser.newContext();
  await session.addInitScript(({ tid, bid, savedModel, invalidStorage }) => {
    // 仅给全新浏览器Context初始化一次；reload不得覆写用户刚选中的子分支/模型偏好。
    if (!localStorage.getItem('ws.fixture.initialized')) {
      if (tid) localStorage.setItem('sesrag.selectedThreadId', tid);
      if (bid) localStorage.setItem('sesrag.selectedBranchId', bid);
      if (savedModel) localStorage.setItem('sesrag.selectedModel', savedModel);
      localStorage.setItem('ws.fixture.initialized', '1');
    }
    if (invalidStorage) Object.defineProperty(Storage.prototype, 'setItem', { value: () => { throw new Error('synthetic-storage-disabled'); } });
  }, { tid: item?.thread_id, bid: branchId, ...preferences });
  const page = await session.newPage();
  page.setDefaultTimeout(20000);
  if (beforeNavigate) await beforeNavigate(page);
  await page.goto(context.frontend_base_url);
  await page.locator('.thread-panel').waitFor();
  if (item?.title) await waitTitle(page, item.title);
  return { page, session };
}
export async function waitTitle(page, title) {
  await until(() => page.locator('.topbar h2').textContent(), (value) => value === title, '当前会话标题');
}
export async function waitText(page, text) {
  await until(() => page.locator('.message-list').innerText(), (value) => value.includes(text), `页面显示${text.slice(0, 20)}`);
}
export async function selectThread(page, item) {
  await page.locator('.thread-item').filter({ hasText: item.title }).click(); await waitTitle(page, item.title);
}
export async function assertEventsUnique(page) {
  const seq = await page.locator('.event-seq').allTextContents();
  assert.equal(seq.length, new Set(seq).size);
  assert.deepEqual(seq.map(Number), seq.map(Number).sort((a, b) => a - b));
  return seq.map(Number);
}

// UI_011：label内option的Playwright 1.64 isDisabled会误判；核对原生语义及真实键盘行为。
export async function assertUnavailableModel(page, value, reason) {
  const select = page.locator('.workspace-controls select').nth(1);
  const option = select.locator(`option[value="${value}"]`);
  const native = await option.evaluate((element) => ({ html: element.outerHTML, disabled: element.disabled, pseudo_disabled: element.matches(':disabled') }));
  assert.equal(native.disabled, true, '不可用模型必须设置原生disabled');
  assert.equal(native.pseudo_disabled, true, '不可用模型必须匹配浏览器:disabled语义');
  assert.ok((await option.innerText()).includes(reason), '不可用原因必须明确显示');
  assert.equal(await select.isEnabled(), true, '本场景须能实际操作模型选择器');
  const enabled = await select.locator('option').evaluateAll((options) => options.filter((item) => !item.disabled).map((item) => item.value));
  assert.ok(enabled.length > 0, '至少存在一个可用选项，不能以全控件禁用掩盖单项禁用');
  const selected = []; const writes = [];
  const onRequest = (request) => { if (request.method() === 'POST') writes.push(new URL(request.url()).pathname); };
  page.on('request', onRequest);
  try {
    // Home/上下箭头通过浏览器原生选择行为，不用会强制设置option的selectOption API。
    const count = await select.locator('option').count();
    await select.focus();
    for (let index = 0; index <= count; index++) {
      await select.press(index === 0 ? 'Home' : 'ArrowDown'); selected.push(await select.inputValue());
    }
    await select.press('End'); selected.push(await select.inputValue());
    for (let index = 0; index < count; index++) { await select.press('ArrowUp'); selected.push(await select.inputValue()); }
    assert.ok(!selected.includes(value), '真实键盘选择不能进入禁用模型');
    assert.deepEqual([...new Set(selected)].sort(), [...enabled].sort(), '必须实际遍历全部可用项，不能未操作便通过');
    assert.deepEqual(writes, [], '切换模型选项不应自动提交业务写入');
  } finally { page.off('request', onRequest); }
  return { native, keyboard_selections: selected, enabled_options: enabled, business_posts: writes.length };
}
export async function pageRunId(page) {
  // 原生details默认折叠；先按真实用户动作展开，再读取可见身份。
  await page.locator('.run-detail').waitFor();
  if (!(await page.locator('.run-detail').getAttribute('open') === '')) await page.locator('.run-detail > summary').click();
  await until(() => page.locator('.run-detail').innerText(), (value) => /Run [0-9a-f-]{36}/.test(value), '工作台Run身份');
  return /Run ([0-9a-f-]{36})/.exec(await page.locator('.run-detail').innerText())[1];
}
