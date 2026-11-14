# 应用观测版本化契约

本目录供应用实现、独立验证与后续ADR-005共用，正式语义入口为[接口文档](../../docs/接口文档.md)。

| 文件 | 用途 |
| --- | --- |
| `metrics_v1.json` | 唯一指标数据字典：名称、角色、单位、标签及合法元组、桶、初始化、快照来源、聚合与重启语义；应用运行时直接消费 |
| `capabilities_v1.json` | Draft2020-12能力文档Schema；`$defs.metrics_catalog`校验指标字典 |
| `application_v1.example.json` | 无密钥的实例输入样例，不代表实际运行网络；导出时以真实源码ref／指纹替换占位 |
| `log_v1.json` | 结构化日志严格Schema；字段可空不代表已保存trace，message为固定中文摘要 |
| `trace_origin_v1.json` | 内部不可变Task来源四字段Schema，不是HTTP输入契约 |
| `error_codes_v1.json` | 固定安全错误码白名单，未知码降为`UNKNOWN_ERROR`；禁止运行时从原始异常生成标签 |
| `report_v1.json` | 本轮开发验证报告Schema，明确passed/failed/blocked/not_run |

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m backend.tools.export_observability_contract --check
.\.venv\Scripts\python.exe -m backend.tools.export_observability_contract --output <受控输出路径>
```

导出工具只读核对实际HTTP声明与字典，排除Secret／runtime／artifacts生成相关源码指纹；不会探测外部服务或创建监控资源。镜像显式复制本目录，应用从仓库/镜像`/app`源码根加载。运行模块使用`python -m`或设置受控`PYTHONPATH=/app`，不要把脱离资源目录的单个Python包副本当完整部署。

`DEPENDENCY_READY`的postgres／redis元组分别绑定同名快照来源，不存在名为dependency的第五个来源。条件指标在首次成功前没有业务样本；之后即使来源失败也保留上次值，须同时判断valid与时间戳。
