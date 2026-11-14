# 阿里云 ECS：GitHub 自托管 Runner 环境核验与接入步骤

- 日期：2026-11-13（America/New_York）。
- 适用范围：`HHHhhhfff/SesRAG` 的仓库级 GitHub Actions 自托管 Runner；属于运维接入调研，不改变 PRD-003 的产品范围或测试结论。
- 状态：已实际连接并只读核验；未安装 Runner、未创建服务账号、未生成注册令牌、未修改 GitHub 配置或云端网络。
- 信息来源：用户指定的私密实例资料、阿里云 ECS 只读 API、Workbench 实际执行、GitHub REST API，以及文末官方资料。本文不保存密钥、账号密码或令牌。

## 1. 结论及实际环境

**这台实例具备尝试运行 Linux x64 轻量 Runner 的基础，但目前不能判定已满足稳定注册和运行条件。** 首先需要处理不稳定的 GitHub 下载／checkout 网络、补 Git、创建专用用户，再实际注册及运行 smoke。Alibaba Cloud Linux 不在 GitHub 官方支持系统清单中，基础库符合相关门槛不等同官方支持或二进制已验证。完整 SesRAG Docker／Chromium 验收建议使用独立的受支持系统和更大规格。

| 项目 | 2026-11-13实测结果 | 含义 |
| --- | --- | --- |
| 实例／地域 | `i-2ze7liy7l0dosws1jwlj`，北京，Running | 已通过用户资料所指的 Workbench 通道成功执行 `id`，当前连接用户为root；无需本次另开公网SSH |
| 系统／架构 | Alibaba Cloud Linux 3.2104 U13.4，OpenAnolis Edition，x86_64 | 可选 Linux x64 包；官方支持清单没有单列该系统 |
| 内核／运行库 | kernel 5.10，glibc 2.32，GLIBCXX最高3.4.28，OpenSSL1.1.1、ICU60、krb5、zlib存在 | 满足所查Node24 GNU/Linux通用基线；尚未执行打包Runner，不能据此保证整个包可运行 |
| 原生依赖分支 | `/etc/redhat-release`存在；`lttng-ust`未安装 | 官方依赖脚本应进入RedHat分支；安装结果尚未验证，缺该包本身不足以断言Runner必然启动失败 |
| CPU／内存 | 2vCPU，标称2GiB，系统可见1870MiB，检查时available约1450MiB | 适合单个轻量任务；4GiB swap不等于额外物理内存 |
| 磁盘 | 系统盘40GiB，ext4，约9.2GiB已用／29GiB可用 | 当前足够Runner包和轻量工作区；没有验证完整镜像／浏览器／构建缓存的长期容量 |
| 公网 | EIP，配置带宽1Mbps | 该配置主要约束公网出方向；向外发送10MiB原件按1Mbps理论约84秒。不能直接用它推算Runner包或镜像的入方向下载速度，本次未测下载吞吐 |
| Docker | Engine26.1.3，Compose2.27.0，服务active，cgroup v1／overlay2 | 当时无镜像、容器、卷、构建缓存；本次未拉镜像，现有镜像加速配置未验证有效性 |
| 工具 | bash/curl/tar/gzip/systemd已有；Python3.6.8；Git、系统Node/npm、PowerShell未找到 | Git需补；Runner自带.NET及Node，系统Node缺失不阻止Runner本体；项目任务另需其语言环境 |
| 原有Runner | 所查服务、常用目录、专用用户均未发现 | GitHub仓库接口也返回0个Runner；未以目录扫描推断整台服务器绝无其他软件 |
| GitHub仓库 | PUBLIC，默认分支main，当前登录账号ADMIN，Actions已开启 | 有资格从仓库设置创建Runner；当前0个工作流、0个Runner |
| GitHub策略 | allowed_actions=all；工作流默认token只读；外部PR批准策略first_time_contributors | 自托管公开仓库不能只靠此批准策略防止恶意代码；最初只接可信手动任务 |

本次是主机与接入条件检查，没有执行项目CI、容器构建、Runner二进制、注册握手、任务调度或服务重启测试。

## 2. 网络实测与必须先解决的部分

所有探测使用系统信任链，未关闭TLS校验、未写hosts、未改DNS／代理。探测原始输出只保存在本机系统临时目录，不进入仓库。

| 目标 | 实测 | 判定边界 |
| --- | --- | --- |
| github.com | 首次收到200，但正文下载达到12秒限制；随后小请求超时 | 首次curl退出28不能写成完整下载成功；网络有波动 |
| api.github.com | HTTPS返回200；另一路HEAD返回404 | TLS／HTTP可达；404不代表该API资源通过 |
| 官方Runner安装包地址 | HEAD跟随重定向1次后200 | 下载路径当次可达，未下载完整228MB或验证传输稳定性 |
| 仓库Git info/refs入口 | 连接超时 | 尚不能保证checkout／clone可用 |
| raw.githubusercontent.com | 两次TLS错误，curl35 | 下载原始文件路径不可靠；不是本机此前MinerU DNS问题的延续结论 |
| codeload.github.com | 301 | 初始端点可达；未以301当作完整源码包下载成功 |
| objects／release-assets.githubusercontent.com | 根路径404 | HTTPS可达；根目录无资源404并非网络失败 |
| vstoken／broker／results-receiver.actions.githubusercontent.com | 根路径404 | 部分Actions服务可达；未注册前不能枚举所有实际分配的服务域 |
| registry-1.docker.io、auth.docker.io | 超时／拒绝连接 | 直连Docker Hub不通；现有镜像代理是否能替代尚未执行pull确认 |
| ghcr.io/v2/ | 401 | Registry认证挑战可达；未证明具体镜像／blob拉取成功 |
| nodejs.org、PyPI、npm registry | 307／200／200 | 各初始端点可达；不代表其全部CDN／包下载路径均验证 |

主机DNS配置指向阿里云内网解析器`100.100.2.136`、`100.100.2.138`，当前命令环境未设置HTTP(S)代理。不能仅根据一次解析值断言原因必然是DNS，也不能通过随意替换IP规避TLS／出站策略。

建议顺序：先确保GitHub控制、Git传输、动作源码和Runner包稳定，再处理Docker镜像来源。若当前地域无法稳定访问，可选合规的服务端出站代理／网络方案，或评估另一地域的专用Runner；本机VPN不会自动替ECS提供代理。镜像优先采用自己管理、已同步并核验digest的阿里云ACR或明确可信的镜像源，不能把现有多条第三方代理配置视为已验收。

Runner主动向GitHub发起出站HTTPS连接，**不需要为GitHub额外放开入站端口**。需按[官方通信域名表](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#communication)配置出站TCP443，并处理其CNAME与动态目标。GitHub注册成功后，还要验证实际分配的Actions／日志／artifact端点。

## 3. 本机与阿里云控制台：先确定执行范围

1. **选择用途。** 保留现机可先做Runner注册及轻量smoke；完整后端／前端／PG／Redis／Chromium验收建议独立Ubuntu22.04或24.04 LTS x64实例，起步4核8GiB、至少60GiB磁盘、较高带宽。这是结合本项目的建议，不是GitHub注册的官方最低硬件要求，也不是已实测容量结论。
2. **需要升级时，在阿里云控制台操作。** 核实费用、备份和停机影响后，调整规格／带宽／磁盘；更换系统会影响现有数据，优先新建专用实例，不直接覆盖当前机器。本次没有执行这些操作。
3. **整理网络。** 在ECS上复测下节的端点；若采用代理，配置在ECS自身和必要的Runner服务环境中，Docker daemon出站也需独立验证。代理凭据只进受限配置，不能贴进工作流、仓库或报告。
4. **检查安全组。** 本次看到22和3389对`0.0.0.0/0`开放；这不是Runner要求。核实管理依赖后，将直接SSH限制到固定管理IP／32；不需要RDP时关闭3389。保留已验证的Workbench管理入口，不在尚未确认替代通道时切断管理访问。
5. **连接。** 本机已有Workbench1.0.4，配置可用，执行：

```powershell
workbench connect --region cn-beijing --instance-id i-2ze7liy7l0dosws1jwlj
```

交互中`/exit`关闭，`/detach`保留。资料中的阿里云账号密码／RAM AccessKey不等于Linux用户SSH密码。无需为了配置Runner向GitHub提供阿里云AccessKey。

## 4. ECS：补依赖、创建专用用户与验证网络

以下为**后续操作示例，尚未执行**。保留Alibaba Cloud Linux时，在刚连接的root终端安装基础工具并创建普通用户；若用户名已存在，先检查其用途，不覆盖：

```bash
dnf install -y git curl tar gzip
useradd --create-home --shell /bin/bash actionsrunner
install -d -o actionsrunner -g actionsrunner -m 0750 /home/actionsrunner/actions-runner
su - actionsrunner
```

选择Ubuntu时对应包管理器为apt，创建同样的专用普通用户；不要照抄dnf。初期不用给actionsrunner免密sudo或Docker组权限。注册配置与运行使用actionsrunner，不设置`RUNNER_ALLOW_RUNASROOT`绕过root限制。

以Runner用户执行小请求，检查HTTP码和curl退出码，连续多轮观察，并在Git安装后验证实际传输：

```bash
curl -I -L --connect-timeout 10 --max-time 30 https://github.com
curl --fail --show-error --connect-timeout 10 --max-time 30 -o /dev/null https://api.github.com
curl --fail --show-error --connect-timeout 10 --max-time 30 -o /dev/null https://raw.githubusercontent.com/actions/runner/main/README.md
timeout 60 git ls-remote https://github.com/HHHhhhfff/SesRAG.git HEAD
curl -I --connect-timeout 10 --max-time 30 https://registry-1.docker.io/v2/
```

Docker Registry返回401通常说明已到达认证层；连接超时／拒绝不是认证成功。Git应退出0并输出HEAD hash。不要用`curl -k`、关闭Git证书校验或未经核实的hosts固定IP制造通过。完整Docker任务接入前，另用最终选定来源执行一次小镜像pull、记录digest，并核对清理范围；本次没有做该写入测试。

## 5. GitHub仓库：获取注册信息

1. 打开[SesRAG仓库](https://github.com/HHHhhhfff/SesRAG) → **Settings → Actions → Runners → New self-hosted runner**。
2. 选择 **Linux／x64**。页面会生成官方安装包、校验及`config.sh`注册命令；注册令牌通常1小时有效，临近执行时再生成。
3. 令牌只在服务器受限终端使用，不放进GitHub仓库Secret或提交的脚本，也不把本机`gh auth token`复制给服务器。Runner不需要长期保存个人PAT来领任务。
4. 当前仓库是PUBLIC。初期只添加下文的`workflow_dispatch`工作流，且只运行自己审查过的代码。不要把已有外部PR、`pull_request_target`或外部输入直接交给该持久Runner；first_time_contributors批准策略不提供执行隔离。

## 6. ECS：下载、校验与注册

本次从官方Release API核实的版本为 **v2.338.2**，Linux x64包大小228071396字节。后续操作时优先使用当时仓库设置页给出的受支持版本和对应SHA256；不要把过时版本永久固定。

在actionsrunner终端执行以下本次版本示例，下载重试有界；网络很差时不要盲目反复下载：

```bash
cd /home/actionsrunner/actions-runner
curl --fail --location --retry 2 --connect-timeout 15 --max-time 5400 \
  -o actions-runner-linux-x64-2.338.2.tar.gz \
  https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-x64-2.338.2.tar.gz
printf '%s\n' 'baebf204307bac6193480852732f0aba2ae97b6c5597c244f4d5558390147c40  actions-runner-linux-x64-2.338.2.tar.gz' | sha256sum -c -
```

**只有下载退出0且SHA256显示OK才解压**：

```bash
tar xzf actions-runner-linux-x64-2.338.2.tar.gz
```

若ECS下载仍不稳定，可在Windows本机下载**同一个官方包**，用`Get-FileHash -Algorithm SHA256`校验，通过`workbench upload --help`确认传输参数后上传到ECS，再用`sha256sum`重复校验；不要用来历不明的二次分发包。离线传包不解决Runner运行时对GitHub出站连接的要求。

依赖安装需要root，在另一个Workbench root终端执行：

```bash
cd /home/actionsrunner/actions-runner
./bin/installdependencies.sh
```

本机实测`/etc/redhat-release`存在，当前官方脚本应走yum分支补含lttng-ust等依赖；未执行过，失败需保留包名和安全错误信息定位。不要修改系统发行标识冒充Ubuntu。Runner2.338.2源码使用self-contained .NET8，并带Node20／24；无须先替换系统Python或安装系统.NET来注册，具体仍以包内依赖检查为准。

回到actionsrunner终端注册；以下占位符不是可用令牌，使用GitHub页面新生成的值，或通过隐藏输入传给命令，避免写入shell历史：

```bash
cd /home/actionsrunner/actions-runner
read -r -s -p 'GitHub Runner registration token: ' RUNNER_REG_TOKEN
printf '\n'
./config.sh --url https://github.com/HHHhhhfff/SesRAG \
  --token "$RUNNER_REG_TOKEN" \
  --name sesrag-ecs-bj-light \
  --labels sesrag-ecs-light \
  --work _work
unset RUNNER_REG_TOKEN
```

保留默认self-hosted／linux／x64标签，不启用`--disableupdate`，不使用`--replace`覆盖未知现有Runner。令牌只短时存在于该受控进程中，禁止同时采集进程完整命令行。成功后先前台运行：

```bash
./run.sh
```

观察连接成功／等待任务，再去GitHub查看Runner为Idle。**此时才确认注册与在线连接已完成**；出现Offline、依赖错误或断线则仍未完成。前台Ctrl+C停止后，按下一节安装服务。

## 7. ECS：安装持久服务

在root终端执行，服务明确以普通账号运行：

```bash
cd /home/actionsrunner/actions-runner
./svc.sh install actionsrunner
./svc.sh start
./svc.sh status
```

使用生成的实际service名称查看状态／日志，不猜另一个实例的服务名。日志中不贴令牌、`.credentials`、`.env`或签名URL。需代理时，确认服务环境也有对应代理配置；仅在交互终端export不会自动保证systemd服务继承。注册凭据属于此Runner，目录只供专用账号与管理员访问。

smoke通过且无任务运行后，可先`./svc.sh stop`再`./svc.sh start`验证服务恢复，并确认GitHub重新Idle。整机重启会影响其它服务，安排维护窗口后再测；本次没有重启或宣称已验证开机恢复。

Runner及任务都在宿主执行。后续确需Docker daemon时，可由管理员将actionsrunner加入docker组并重启Runner服务；**docker组具有近似宿主root的能力**，不适合处理不可信PR。当前轻量smoke只执行Docker CLI版本，不要求Docker组权限；不为方便默认添加免密sudo。

## 8. GitHub与本机：添加一个手动smoke工作流

当前远端默认分支是`main`，当前开发分支是`sesrag_v0.3`。`workflow_dispatch`需工作流文件先存在于默认分支，Actions页面才会提供相应手动入口。不要仅在本机未推送的文件里添加，也不要为创建工作流切换并覆盖当前有大量未提交修改的工作区。

推荐在GitHub页面 **Add file → Create new file**，文件名`.github/workflows/runner-smoke.yml`，通过新分支及PR审核后进入main。此文件是后续需要用户添加的内容，本次没有创建或推送工作流。实际进入仓库后再dispatch，标签需与注册时一致：

```yaml
name: ECS Runner smoke
on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ecs-light-smoke
  cancel-in-progress: false

jobs:
  smoke:
    if: github.event_name == 'workflow_dispatch' && github.repository == 'HHHhhhfff/SesRAG'
    runs-on: [self-hosted, linux, x64, sesrag-ecs-light]
    timeout-minutes: 10
    steps:
      - name: 核对普通用户与主机
        shell: bash
        run: |
          test "$(id -u)" -ne 0
          uname -m
          getconf GNU_LIBC_VERSION
          git --version
          df -h .
      - name: 检出可信仓库代码
        # 本次核验actions/checkout的v4指向此官方commit，后续按受支持版本维护。
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
          fetch-depth: 1
      - name: 核对检出和Docker工具
        shell: bash
        run: |
          git rev-parse HEAD
          test -f README.md
          docker --version
          docker compose version
```

然后进入 **Actions → ECS Runner smoke → Run workflow**，首次选择main，等待通过。确认：任务显示运行在`sesrag-ecs-bj-light`，普通用户断言通过，checkout返回正确commit，任务日志回传且Runner回到Idle。不要把本例通过当作SesRAG构建／数据库／浏览器／真实模型验收通过。

本机可只读复核，不需要把GitHub PAT传给ECS：

```powershell
gh api repos/HHHhhhfff/SesRAG/actions/runners --jq '.runners[] | {name,status,busy}'
gh workflow run runner-smoke.yml --repo HHHhhhfff/SesRAG --ref main
gh run list --repo HHHhhhfff/SesRAG --workflow runner-smoke.yml --limit 5
```

`gh workflow run`会实际启动任务，只在前面工作流及Runner准备好后由操作者执行；本次没有执行。后续可用`gh run view <run-id> --log-failed`查看失败步骤，不上传整份含敏感环境的诊断包。

## 9. 后续接入项目测试与维护

- **语言工具按任务安装。** 当前Python3.6.8不能运行本项目现代Python环境；选择独立Python3.12／虚拟环境或产品工具容器。前端需要兼容Node，独立测试总入口还需要PowerShell7.4+、Python3.11+、Docker／Compose／Git。Runner自带Node不等于项目已安装npm构建环境；不要替换系统Python。
- **完整测试另设计workflow。** 先扩资源并解决镜像／浏览器／包CDN，再按当前TEST-003总入口执行、采证和finally清理。本次不改变旧PRD验收文件，不承诺把Windows结果自动迁移成Linux通过；真实模型计数受限也不会因换服务器自动解除。
- **持久Runner不是隔离沙箱。** 不把生产凭据／部署服务与公开仓库的不可信任务混用；只放必需的、有限权限Secret，真实外发及计费测试保留原授权／预算门槛。面向外部PR时优先GitHub-hosted或专门的临时隔离Runner方案。
- **更新与容量。** 保持Runner自动更新；当前官方更新窗口资料为63天，关键安全更新可提前阻止派工，不把旧版30天口径永久写死。检查`_work`、`_diag`和镜像缓存占用，不执行全局`docker system prune`破坏其它数据。
- **停用。** 先停止接新任务、等待busy结束，再root执行`./svc.sh stop`、`./svc.sh uninstall`；在GitHub Runner设置页移除，必要时按页面删除令牌执行`config.sh remove`。核对实际专用目录和无待保存证据后再删除，不用宽泛路径递归清理。
- **RAM密钥轮换。** 本次首次资料读取的工具输出包含RAM AccessKey，建议在RAM控制台创建替代密钥，用本机`workbench config`安全更新并重新验证连接，再禁用／删除旧密钥及更新私有资料。不要把真实新密钥写进命令行参数或本文。轮换不是Runner注册条件，本次没有擅自更换凭据或切断管理通道。

本次实际服务器检查只读取状态、包和网络，没有安装依赖／开端口／改Docker源／拉镜像。创建的Workbench会话已显式关闭并确认会话列表为空；没有停止既有Docker或阿里云Agent。

## 10. 官方依据

1. [GitHub：Self-hosted runners reference](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)：支持的系统／架构、硬件随任务变化、通信域及出站要求。
2. [GitHub：Adding self-hosted runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)：仓库注册权限、设置路径及注册令牌。
3. [GitHub：Configuring a service](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application)：Linux的svc.sh安装／启停。
4. [GitHub：Managing repository Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)：公开仓库、自托管与外部PR批准边界。
5. [GitHub：Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)、[Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)：workflow_dispatch、默认分支与标签选择。
6. [官方Runner v2.338.2 Release](https://github.com/actions/runner/releases/tag/v2.338.2)、[Release API](https://api.github.com/repos/actions/runner/releases/latest)：本次版本、包大小及SHA256；后续应重新核对。
7. [Runner依赖脚本](https://github.com/actions/runner/blob/v2.338.2/src/Misc/layoutbin/installdependencies.sh)、[config.sh](https://github.com/actions/runner/blob/v2.338.2/src/Misc/layoutroot/config.sh)、[Listener项目](https://github.com/actions/runner/blob/v2.338.2/src/Runner.Listener/Runner.Listener.csproj)：发行版依赖分支、启动检查与.NET8。
8. [Runner externals](https://github.com/actions/runner/blob/v2.338.2/src/Misc/externals.sh)、[Node GNU/Linux构建基线](https://github.com/nodejs/node/blob/v24.x/BUILDING.md)：随包Node版本及原生库要求。

整体校审口径：连接成功、主机具备基础、网络单项可达、已注册Idle、工作流成功、项目测试通过是不同证据层；本文仅前几层有实测，注册之后的步骤均明确留给后续实施。
