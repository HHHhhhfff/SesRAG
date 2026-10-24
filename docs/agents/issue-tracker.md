# Issue tracker：GitHub

仓库：[HHHhhhfff/SesRAG](https://github.com/HHHhhhfff/SesRAG)。工程技能产生的问题、需求拆解和实施票据使用 GitHub Issues，通过 `gh` CLI 操作，并显式指定 `--repo HHHhhhfff/SesRAG`。

现有 `docs/prd/`、`docs/adr/`、`docs/pr/` 和 `docs/test/` 的职责不变。Issue 引用对应正式文档，不替代仓库规定的权威文档。

## 常用操作

- 创建：`gh issue create --repo HHHhhhfff/SesRAG --title "..." --body "..."`
- 读取：`gh issue view <编号> --repo HHHhhhfff/SesRAG --json number,title,body,labels,comments`
- 列表：`gh issue list --repo HHHhhhfff/SesRAG --state open --json number,title,body,labels`
- 评论：`gh issue comment <编号> --repo HHHhhhfff/SesRAG --body "..."`
- 标签：`gh issue edit <编号> --repo HHHhhhfff/SesRAG --add-label "..."`；移除时使用 `--remove-label`。
- 关闭：`gh issue close <编号> --repo HHHhhhfff/SesRAG --comment "..."`

多行正文通过临时正文文件和 `--body-file` 传入，避免 Shell 转义问题。

父子票据优先使用当前 `gh`/GitHub 支持的子 Issue；不支持时，通过父票据任务列表和子票据中的 `Part of #编号` 关联。依赖关系优先使用原生依赖，不支持时记录 `Blocked by: #编号`。

## 技能用语映射

- “发布到问题跟踪系统”：创建 GitHub Issue。
- “获取相关票据”：读取指定 Issue 的正文、评论和标签。
- 状态标签映射见 [triage-labels.md](triage-labels.md)。
- 配置本身不授权自动领取、实施、关闭票据或提交代码。

## PR 请求入口

PRs as a request surface: no.
