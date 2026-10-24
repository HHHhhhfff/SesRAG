# API固定契约样本

`v2-contract-samples.json`是开发测试自身持有的独立字面样本，供`tests/api/test_v2_schemas.py`同时验证后端DTO和`contracts/`的JSON Schema。固定UUID、owner、正文、时间与hash均为合成数据；没有真实用户或凭据，不是数据库seed，不导入Thread/Run/Task/Event。

样本包含Thread/Branch/Message、摘要/计划、v2及legacy Run和16种v2事件payload。正样本必须通过，额外secret字段等负样本必须被拒绝；事件类型集合与正式DTO映射核对，避免漏掉类型后假通过。样本不可从待测DTO自动生成，也不依赖任何PRD验收目录。契约变更须同时评审这些字面样本和断言。
