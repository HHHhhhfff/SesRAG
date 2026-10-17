// 任务2的Node六参数协议哨兵；不访问业务系统，不冒充产品分类。
const args = process.argv.slice(2)
const received = {}
for (let index = 0; index < args.length; index += 2) {
  if (!args[index].startsWith('-') || args[index + 1] === undefined) process.exit(1)
  received[args[index].slice(1)] = args[index + 1]
}
received.message = '六参数中文调用成功'
console.log(JSON.stringify(received))
