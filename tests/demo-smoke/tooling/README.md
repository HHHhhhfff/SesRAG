# 测试工具与运行器协议探针

本目录存放工具检查、覆盖校核和固定harness输入；工具哨兵和协议探针不进入正式产品manifest，不回填用例正式验收结果。任务3新增`check-coverage.mjs`和`harness-fixtures/`：LIFE用明确自检manifest故意触发错误协议，DOC/RAG薄入口调用specific_test_script中的独立边界断言，不将哨兵passed当产品passed。

## 文件职责

| 文件 | 职责/何时使用 |
| --- | --- |
| check-tools.mjs | Chromium中文DOM/关闭、Ajv契约工具、ESLint真实解析/拒绝非法语法、Vitest组件工具启动自检。依赖安装后运行。 |
| check-python-tools.py | Python3.12、开发依赖导入/版本和JSON Schema正反哨兵校验。使用根.venv运行。 |
| vitest-tool-probe.test.ts | 独立Vue组件及Pinia驱动组件两探针，核对挂载/点击/更新/卸载、测试目录依赖解析；非产品用例。 |
| vitest-tools.config.mjs | 专门选择上述探针，不能混入正式组件测试include。 |
| dispatch-probe.ps1/.mjs | 六参数、含空格路径和中文输出哨兵；由父目录self-tests调用，无HTTP或数据库副作用。 |
| check-coverage.mjs | 149用例/191测试点的声明路由及本次报告核对；另列只有blocked和可验证基线仍有受限子项。不是行为全覆盖证明。 |
| render-summary.mjs | 读取本次summary/categories，生成summary-详细.md中文投影，不回填用例卡片。 |
| lint-frontend.mjs | 固定仓库根调用ESLint真实扫描frontend/src；空/全部ignored必须失败，产品错误返回1。npm lint:frontend使用此入口。 |
| harness-fixtures/ | 固定LIFE协议/超时/登记兜底故障输入，以及DOC/RAG专属边界薄入口；只允许总入口的HarnessScenario白名单选择。 |

父目录[eslint.config.mjs](../eslint.config.mjs)限定frontend/src，独立于frontend旧的lint=vue-tsc；[vitest.config.mjs](../vitest.config.mjs)限定specific_test_script中的test/spec，**没有用例退出非零**。Vue Node入口及test-utils/Pinia/vue-demi内联配置保证同一测试runtime；Vue为前端同版本3.5.43，Pinia alias明确指向frontend安装的同一模块，避免测试包另装一份activePinia。不改变产品bundle；因此宿主frontend依赖也须按锁安装。

## 重装与调用

ESLint针对TS/带TS的Vue不启用core `no-undef`，因为它误将DOM类型当运行时变量；未定义标识由独立`vue-tsc`门禁检查，其他TS/Vue推荐规则保留。工具自检包含DOM类型正哨兵及非法TS语法负哨兵。Vitest工具探针显式替换include集合，不合并产品组件用例；产品失败不能变成工具依赖缺失。

当前总入口调度分类并生成中文详细摘要，需要本机**Node24.15+的24.x或26+**（本次24.18；依赖不支持25），不能继续按历史“仅PowerShell/Docker即可完整闭环”理解。PowerShell7.4+/Docker/Compose负责环境生命周期；不升级frontend容器的Node20。Python必须3.12，不能使用PATH中的3.11；无需uv或全局安装。

仓库根运行（Python3.12绝对路径替换为机器实际安装路径）：

```powershell
& '<Python3.12绝对路径>' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tests/demo-smoke/requirements-tools.txt --cache-dir tests/demo-smoke/.cache/pip
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
npm ci --prefix tests/demo-smoke --cache tests/demo-smoke/.cache/npm
# 前端锁文件不改动；宿主typecheck、build及Pinia工具探针需要实际源码依赖。
npm ci --prefix frontend --cache tests/demo-smoke/.cache/npm
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path (Get-Location) 'tests/demo-smoke/.cache/ms-playwright'
node tests/demo-smoke/node_modules/playwright/cli.js install chromium
.\.venv\Scripts\python.exe tests/demo-smoke/tooling/check-python-tools.py
npm run tools:check --prefix tests/demo-smoke
pwsh -NoProfile -File tests/demo-smoke/self-tests.ps1
```

Windows/Python3.12的完整依赖快照在[requirements-tools.txt](../requirements-tools.txt)，不作为Linux应用镜像新锁；Node精确直接版本和完整传递依赖见package.json/package-lock.json。JSON Schema分别可用PS Test-Json、Node Ajv2020+formats或Python jsonschema；HTTP/SSE用PS/.NET或Node原生fetch流，SQL诊断用容器psql，无需另安装宿主数据库客户端。

## 产品门禁与分类命令

```powershell
# 真正的独立ESLint；不得把产品失败规则静默关闭。
npm run lint:frontend --prefix tests/demo-smoke
# 已接入真实Workspace组件断言，失败返回1；不是工具探针。
npm run unit:frontend --prefix tests/demo-smoke
# 原有前端类型检查/构建仍按frontend/package.json运行。
npm run typecheck --prefix frontend
npm run build --prefix frontend
# 使用项目Python而非系统3.11；任务3～4试跑不代替任务5稳定性验收。
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend tests migrations
.\.venv\Scripts\python.exe -m ruff format --check backend tests migrations
.\.venv\Scripts\python.exe -m mypy backend
```

安装工具不代表产品Lint/单测/浏览器门禁通过。E2/E4/O/C慢任务、提交屏障、双owner、特殊配置和HTTP替身是后续测试驱动，不是pip/npm缺包，不能用依赖安装来解除所有blocked。

PowerShell分类开头必须设置`[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)`及`$OutputEncoding=[Console]::OutputEncoding`；Python输出用UTF-8。运行器进程适配器按UTF-8读stdout/stderr并传PYTHONIOENCODING。Node原生UTF-8。详细协议见[分类README](../specific_test_script/README.md)。
