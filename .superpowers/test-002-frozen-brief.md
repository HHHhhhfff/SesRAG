# 冻结构建工具子任务

在suite `tests/sesrag-persistent-session-workspace-test/` 新建 `tooling/frozen-builds.mjs` 与 `tooling/frozen-builds.test.mjs`，不改其他文件、不启动Docker、不提交/推送。先读根AGENTS与测试规范，并遵守TDD。

依据TEST-002 §7.1：Selected/All首次构建后，将3个image ID导出为不含run专属tag引用的归档，位于`.cache/frozen-builds/<64位构建指纹>/images.tar`和manifest.json。manifest记录源码/工具指纹、image IDs、归档SHA256、依赖记录；后续FrozenBuild只允许指纹而非任意路径，校验源码/归档hash后docker load并给同ID挂本轮tag，不能静默重建。Environment不要求归档。

导出API与runner协调：
- `saveFrozenBuild(session, {docker=...}={}) -> {fingerprint,manifest}`
- `loadFrozenBuild(session, fingerprint, {docker=...}={}) -> {fingerprint,manifest}`
session字段：source_before.source_digest、images=[{name:'app'|'frontend'|'tools',tag,id}]，当前resources.mjs导出docker(args,options)，可用注入替身自测；suite root从preflight导入。恢复load前镜像tag创建意图已由runner登记，不在此删除资源。
- 实际docker save使用image ID（不是tag），避免恢复旧run tag；dump不能把全局inspectEnv写出。docker load限制30分钟，export/save同样有界。只读inspect记录RepoDigests/Id/Config.Labels里suite/source（不要原始Env）。manifest先写临时后原子rename，目录已经存在必须校验一致不能覆盖不同构建。hash=source digest+image IDs+必要版本组合，校验空/未知name/缺失ID/符号链接/路径逃逸。
- 测试可用临时cacheRoot参数（默认suite/.cache/frozen-builds）；只用进程内替身模拟docker命令与写tar，覆盖成功导出/load同ID、拒绝源码变化、归档篡改、任意路径/符号链接、镜像ID变化、缺失文件、重复保存不覆盖已有归档。不要实际导出大镜像。

完成报告 `.superpowers/test-002-frozen-report.md`，含实际命令结果和限制，向主代理返回简短结果。不要派子代理。
