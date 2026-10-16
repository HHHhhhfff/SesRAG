import { runCategory } from '../lib/category-kit.mjs';
import { executionCoverage } from '../specific_test_script/execution-coverage.mjs';

// 仅5a新增检查专项；ArtifactDir必须另指task5a-focused，不能替代完整分类/all。
const category = process.env.SMOKE_EXECUTION_CATEGORY;
if (!['msg','run','wk','can','evt','sse','hlt'].includes(category)) throw new Error('缺少固定专项分类');
await runCategory(category, suite => executionCoverage(suite, process.env.SMOKE_EXECUTION_SUB));
