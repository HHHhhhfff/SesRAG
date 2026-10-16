import fs from 'node:fs'
import {test} from 'node:test'
import assert from 'node:assert/strict'

// M1：计算完整有限预算；少算特殊420或任何恢复预留不能宣称覆盖最坏上界。
test('LIFE完整预算逐项加总且正式manifest不得更短',()=>{
 const budget=JSON.parse(fs.readFileSync('tests/demo-smoke/specific_test_script/life-budget.json'))
 const manifest=JSON.parse(fs.readFileSync('tests/demo-smoke/specific_test_script/manifest.json'))
 assert.equal(budget.parts.reduce((sum,row)=>sum+row.count*row.seconds,0),budget.total_seconds)
 assert.equal(budget.nested_recovery_seconds,420)
 assert.ok(manifest.categories.find(row=>row.name==='life').timeout_seconds>=budget.total_seconds)
})
