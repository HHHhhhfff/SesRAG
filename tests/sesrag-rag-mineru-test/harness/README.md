# local控制面与传输装配

`local_entry.py`只供local API/Worker启动：检查lane，替换索引的gateway/provider工厂及Run/diagnostic两处检索编排引用，并输出安全装配身份。先执行生产配置/counter守卫，只有Mock Profile装配受控Port；真实未验证配置保持拒绝。real覆盖清除harness挂载与入口，使用正常产品入口。

`transport_fixtures.py`对MinerU使用生产客户端＋httpx.MockTransport；生产HTTPS/domain白名单仍有效，控制面仅作为内部计划传输，不能称已验证DNS/TLS。生产出站安全负例需后续独立测试。生成使用独立dummy HTTP/SSE Profile及离线tiktoken。

`scenario_control.py`在专属control卷的SQLite中持久计划/计数/远端合成状态；连接每次显式关闭。只记录请求hash和调用数，不写产品DB或成功状态，不保存真实Authorization、全文Prompt。控制面仅internal网络，管理API需专属Bearer令牌；没有宿主端口和Docker socket。

API（不是正式产品接口）：

- `PUT /plans/{scope}/{kind}`：动作数组，最多100项/64KiB，最后一项重复至用例结束。kind只允许mineru_submit/mineru_put/mineru_poll/mineru_download/embedding/rerank/before_publish/generation。
- `POST /step/{scope}/{kind}`：原子取下一动作、累计计数，最多10000次；延迟/屏障最多120秒。
- `model_request`为本地生成输入观察点，按Task/generation记录逐消息role/字符数/sha256，不保存全文Prompt，可在生成前设置有界屏障。
- `GET /observations/{scope}`：返回各kind调用数及最后请求hash。
- `PUT /barriers/{name}/release`：解除命名屏障。
- `GET /health`：技术就绪；`POST /v1/chat/completions`仅接受dummy生成Key，输出固定SSE。

动作可声明status、delay_seconds、fault（connection/empty/bad_vector/bad_index/disconnect）、state、barrier、response_json、package（safe/escape/empty/html/nested）。无任意代码/文件/目标URL字段。办公scope为parse_job_id，跨代保持同远端身份；向量/重排/发布scope为`task_id:generation`。生成HTTP优先使用`gen:<本例冻结model_name>`的generation计划，未配置才使用默认`generation`；并发例可导入独占的local生成Profile/model_name，避免按全局顺序分配故障。

发布屏障位于索引handler开始publish阶段前；同代迟到可阻塞Embedding外发后再终止/换代。更深的事务内竞争使用本suite真PG多连接和约束观察；不得以此发布前屏障冒称已经覆盖commit内每个时点。控制面重启后计划/调用数保留，容器销毁时control卷随本轮销毁。
