# TEST-002 冻结构建模块实施记录

- 日期：2026-10-21
- 范围：新增冻结镜像工具与工具自身测试；不编写产品用例，不操作真实 Docker，不提交或推送。
- 依据：`.superpowers/test-002-frozen-brief.md`、TEST-002 §7.1、仓库 `AGENTS.md` 和测试实施规范。

## 实际文件

| 文件 | 用途 |
| --- | --- |
| `tests/sesrag-persistent-session-workspace-test/tooling/frozen-builds.mjs` | 保存/加载内容指纹镜像归档，核验安全元数据、依赖记录、来源、归档及镜像身份。 |
| `tests/sesrag-persistent-session-workspace-test/tooling/frozen-builds.test.mjs` | 进程内 Docker 替身、合成 tar 归档、临时缓存及保护分支自测。 |
| `.superpowers/test-002-frozen-report.md` | 本模块真实实施和验证记录；不是环境或产品验收报告。 |

## 导出接口

```javascript
saveFrozenBuild(session, { docker, cacheRoot } = {})
loadFrozenBuild(session, fingerprint, { docker, cacheRoot } = {})
// 两者返回 { fingerprint, manifest }
```

默认 `docker` 使用 `resources.mjs` 的受约束调用器；默认 `cacheRoot` 为本 suite `.cache/frozen-builds`。测试显式注入进程内替身和 `mkdtemp` 新建的缓存，结束清除该临时目录，不调用真实 Docker。

`session` 读取字段：

- `run_id`：本轮合法 run ID，用于严格核验当前 `sesrag-ws-{app|frontend|tools}:<run_id>` tag。
- `source_before.source_digest`：64 位小写 SHA256；`source_before.files` 存在时抽取已知锁文件的安全 hash。
- `images`：恰好 app/frontend/tools 三项；save 要求各项已有 `id`，load 允许未填或已填相同的 `id`。
- `dependencies`：save 必填 `{python_version, packages:[{name,version}], node_version?}`；只投影白名单字段，包名规范化并排序、拒绝重复。load 未提供时回填冻结记录；已提供时要求匹配。

load 先验证所有导入镜像 ID/来源，再原地写入 `session.images[].id` 并按本轮 tag 创建引用；成功后回填安全 `session.dependencies`。不在模块内构建、运行容器或删除镜像，部分操作失败由主入口按已有创建意图和资源账本清理。

## 冻结内容与边界

- 指纹包含协议/工具版本、源码指纹、当前 Node 版本、白名单解析依赖、已知锁文件 hash、三个名称及镜像 ID；不包含 run 专属 tag 或任意 session 内容。
- 只读 inspect 只请求 ID、RepoDigests、suite/source 标签，不请求原始 Config.Env。
- 导出使用镜像 ID；save/load 最长 30 分钟，inspect/tag/查询最长 30 秒。
- `.cache/frozen-builds/<fingerprint>/images.tar` 以 SHA256 和字节数核验；manifest 临时写入后原子 rename。已存在指纹目录只校验复用，不覆盖不同或损坏内容。
- 缓存根、指纹目录及文件拒绝符号链接/junction；fingerprint 只接受 64 位小写 hash，不能接收路径。
- tar 校验不解压文件，校验安全路径、普通文件/目录、校验和、结束块、镜像配置内容 hash 和匿名标签；拒绝 RepoTags、legacy repositories 或 OCI 索引恢复普通 tag。载入后再次核验全部 ID 和 suite/source 标签。
- 当前 tag 已指向其他镜像时在 load/tag 前拒绝覆盖。失败错误只保留稳定错误码，不返回驱动原始异常。

## 实际验证

首次执行测试时模块尚未实现，18 项因缺失目标模块失败，随后实现；新增 tag 冲突测试先观察到缺失拒绝行为，再补实现并全量复测。

```powershell
node --test tests/sesrag-persistent-session-workspace-test/tooling/frozen-builds.test.mjs
node --check tests/sesrag-persistent-session-workspace-test/tooling/frozen-builds.mjs
node --check tests/sesrag-persistent-session-workspace-test/tooling/frozen-builds.test.mjs
```

实际结果：24 tests、24 pass、0 fail、0 skipped；两个语法检查退出码均为 0。自测包括成功 save/load 同 ID、仅创建本轮 tag、依赖和秘密投影、重复保存不覆盖、源码变化、归档篡改、非法路径、缺文件、镜像 ID/来源变化、旧 run tag 注入、部分导出失败清理、根/指纹目录 junction、依赖缺失/不匹配以及当前 tag 冲突。

## 未验证项与限制

- 未操作真实 Docker，尚未证明当前 Docker Engine 导出的实际 archive 格式与本模块校验器完全兼容；真实 save/load 演练由后续 ready 的 Selected/All 集成验证，不将替身自测写成 Docker 通过。
- tar 入口采用保守白名单，只接受未压缩普通镜像 tar；PAX/特殊链接或超过元数据/条目上限的归档会安全拒绝，需要根据实际导出证据扩展后再复验。
- 不负责获取依赖、创建资源账本、核对 Engine/context 或 Environment/Selected/All 模式路由；这些由 runner 保持职责和时序。
- 本模块没有执行任何 PRD 产品验收，也未宣称八类产品测试可用。
