// 技术浏览器探针；不代替后续workspace产品用例。
import { createRequire } from 'node:module';
const require = createRequire('/test-tools/package.json');
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const response = await page.goto(process.argv[2] ?? 'http://frontend:5173', { waitUntil: 'domcontentloaded', timeout: 30000 });
  if (!response?.ok()) throw new Error('BROWSER_FRONTEND_UNAVAILABLE');
  const ready = await page.evaluate(async () => (await fetch('/health/ready')).json());
  if (ready.database !== 'ready' || ready.worker !== 'ready') throw new Error('BROWSER_SAME_ORIGIN_NOT_READY');
  console.log(JSON.stringify({ browser: await browser.version(), html_status: response.status(), same_origin: true, worker: ready.worker }));
  await context.close();
} finally {
  await browser.close();
}
