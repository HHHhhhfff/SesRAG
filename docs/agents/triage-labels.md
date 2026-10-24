# Triage labels

| 技能中的角色 | GitHub 标签 | 含义 |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | 待维护者评估 |
| `needs-info` | `needs-info` | 等待报告者补充信息 |
| `ready-for-agent` | `ready-for-agent` | 需求明确，可交给 AI 实施 |
| `ready-for-human` | `ready-for-human` | 需要人工实现或关键操作 |
| `wontfix` | `wontfix` | 明确不处理 |

以上是状态标签，与 `bug`、`enhancement` 等类型标签分开使用。一个已分诊 Issue 应只有一个状态标签；发现冲突时先报告。

通常由 `needs-triage` 转入其他状态；`needs-info` 在收到补充信息后返回 `needs-triage`。

标签本身不启动自动实施。执行分诊技能时，评论、关闭或状态变更遵循该技能的确认流程。
