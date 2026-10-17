import { Context, Suite, parseArgs } from '../lib/category-kit.mjs'
import { httpContractMatrix } from './http-contract-matrix.mjs'
const suite = new Suite('qlt', new Context(parseArgs()))
await suite.check('QLT_006','TP-QLT-006','full-http-field-contract','真实HTTP全响应/Event联合契约及tmp类型diff',()=>httpContractMatrix(suite.ctx))
process.exitCode = suite.finish().status === 'passed' ? 0 : 1
