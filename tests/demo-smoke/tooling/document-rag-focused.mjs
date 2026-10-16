import { runCategory } from '../lib/category-kit.mjs';
import { documentRagCoverage } from '../specific_test_script/document-rag-coverage.mjs';

// 仅新增5b检查；独立ArtifactDir，不可代替正式全分类/all结果。
const category=process.env.SMOKE_DOCUMENT_RAG_CATEGORY;
if(!['doc','par','chk','idx','rag','sec','arc'].includes(category)) throw new Error('缺少固定5b专项分类');
await runCategory(category,suite=>documentRagCoverage(suite,process.env.SMOKE_DOCUMENT_RAG_SUB));
