# PRD-003 独立固定输入

本目录不引用前轮正式验收数据。`manifest.json` 固定九格式源文件的字节数、SHA-256及第三方来源；`generate_fixtures.py` 可用项目可选 `rag-fixtures` 依赖重新生成 txt/md/docx/pdf/xls/xlsx/pptx 和扫描 PDF。重新生成Office/PDF可能改变容器时间戳及hash，须重新核对manifest，不能拿新输入冒充旧联调证据。

- `knowledge.*`：公开可读的合成 SesRAG 规则，其中txt/md/docx/pdf/xls/xlsx含20条事实；PPTX是6页子集。`knowledge-scan.pdf` 为单独的图像扫描文本样本。
- `public-word.doc`、`public-slides.ppt`：Apache POI 公共测试样本，下载地址和hash在manifest中，许可Apache-2.0；不是改后缀伪造的旧格式。来源说明见`NOTICE`和`LICENSE-APACHE-2.0.txt`。
- `provider-observations.json`：2026-10-30真实MinerU原批次产物的安全统计，以及真实1024维Embedding／原生rerank协议探针结果。没有Key、远端batch、签名URL或用户文件。成功解析不等于所有格式结构质量、Recall或整体上线验收均通过；模型counter仍unverified。

生成命令（Windows；Linux改为`.venv/bin/python`）：

```powershell
.venv/Scripts/python.exe -m pip install -e '.[dev,rag-fixtures]'
.venv/Scripts/python.exe tests/fixtures/rag-v3/generate_fixtures.py --fetch-public
```

`--fetch-public` 才联网下载两个公开样本；正常pytest不联网，不调用MinerU。真实探针需显式`--allow-synthetic-outbound`和独立运行时配置，见[Runbook](../../../docs/runbooks/rag-v3-development.md)。本目录不是临时凭据／下载包保存位置。
