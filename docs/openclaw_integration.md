# OpenClaw 接入说明

本文档说明 Autoresearch 如何接入本机 OpenClaw 和 QQ bot。当前仓库只提供安全的
`autoresearch` skill 和 `litagent job` 白名单命令；不要让 OpenClaw 直接执行任意 shell。

## 当前确认结果

在当前 `/app` 容器内：

- 没有发现 `openclaw` 可执行文件。
- 没有发现 `powershell.exe` 或 Windows 盘挂载。
- 没有直接访问到宿主机 OpenClaw 配置和 QQ bot 配置。
- 用户加入的 `openclaw/Openclaw/OpenClaw.app` 是 macOS 应用包，版本为 `2026.3.2`，
  其二进制是 Mach-O universal binary，不能在当前 Linux 容器中直接运行。
- 用户加入的 `openclaw/Openclaw/qqbot/` 是外部 QQBot channel 插件源码，
  包名为 `@sliverp/qqbot`，插件 ID 为 `qqbot`，不是 Autoresearch skill 本身。
- QQBot 插件读取 `channels.qqbot.appId` / `channels.qqbot.clientSecret`，
  也支持 `QQBOT_APP_ID` / `QQBOT_CLIENT_SECRET` 环境变量；不要把这些值写入仓库。
- Codex 规则历史里出现过 Windows 侧 `openclaw config ...` 命令，以及
  `D:/study/AI安全/AutoWiki-skill/skills` 这样的 AutoWiki-skill 路径。

因此，当前不能从容器内确认“正在运行的 OpenClaw 是否就是用户说的 QQ bot 实例”。需要在
宿主机 OpenClaw 环境中确认。

## 需要在宿主机确认

在 Windows 宿主机或 OpenClaw 实际运行环境中执行：

```powershell
openclaw health
openclaw config validate
openclaw config get skills
openclaw config get skills.load.extraDirs
openclaw skills list
```

如果 QQ bot 是 OpenClaw 的一个 channel / connector，还需要查看对应配置项。不同版本字段名
可能不同，优先使用：

```powershell
openclaw config --help
openclaw config get channels
openclaw config get connectors
openclaw config get bots
```

只需要确认：

- 当前 OpenClaw 是否连接了 QQ bot。
- QQ bot 是否是你正在使用的那个账号或群。
- OpenClaw skill 加载路径是否包含 Autoresearch 的 skill 路径。
- OpenClaw 执行环境是否能运行 `litagent`。

不要把 token、cookie、QQ 凭据或 `.env` 内容发到聊天里。

## Skill 路径

本仓库提供：

```text
openclaw/skills/autoresearch/SKILL.md
```

建议把 `openclaw/skills` 目录加入 OpenClaw 的 skill source / extraDirs，而不是只加入单个
`SKILL.md` 文件。

示例，按你的宿主机实际路径调整：

```powershell
openclaw config set skills.load.extraDirs[0] "D:/study/Autoresearch/openclaw/skills"
openclaw config validate
openclaw skills list
```

如果你已经配置了 AutoWiki-skill，不要覆盖它。应追加 Autoresearch 路径，例如：

```powershell
openclaw config get skills.load.extraDirs
openclaw config set skills.load.extraDirs[1] "D:/study/Autoresearch/openclaw/skills"
```

具体索引以当前 `skills.load.extraDirs` 返回值为准。

## 推荐命令映射

OpenClaw / QQ bot 只映射以下白名单命令：

```text
/research new <topic>
/research run-next
/research status <job_id>
/research list
/research cancel <job_id>
/research logs <job_id>
/research result <job_id>
/research report <job_id>
/research library
/research sync <workspace>
```

内部命令：

```bash
litagent job create --topic "<topic>" --workspace "<workspace>" --sync-library --json
litagent job run-next --json
litagent job status "<job_id>" --json
litagent job list --json
litagent job cancel "<job_id>" --json
litagent job logs "<job_id>" --json
litagent job result "<job_id>" --write-report --pdf --json
litagent job run "<job_id>" --json
litagent library-status --json
litagent export-wiki "<workspace>" --format autowiki --out "<vault-out>" --json
```

不要映射：

```text
任意 shell
任意 PowerShell
curl / wget
git
rm / del
python -c
浏览器自动化抓取
```

## 手机端摘要、长版报告与自然语言入口

手机端查看结果使用：

```text
/research result <job_id>
```

该命令固定映射到：

```bash
litagent job result "<job_id>" --write-report --pdf --json
```

返回内容优先给手机可读的“知识点摘要”：领域边界、文献类型分布、技术主线、代表阅读、
benchmark/评测重点和可做机会。运行信息（job_id、状态、质量标签、selected/parsed/notes/evidence
规模、`wiki-vault/START_HERE.md` 路径）只能作为后置元数据。不要把完整报告、完整 evidence table
或完整日志直接发送到 QQ。

同时会在 workspace 下生成长版报告文件：

```text
reports/mobile_brief.md
reports/mobile_brief.html
reports/mobile_brief.pdf
reports/agent_synthesis_pack.md
reports/agent_synthesis_prompt.md
reports/codex_synthesis.md
```

`mobile_brief.md` 是可复查和继续编辑的 Markdown 源文件，`mobile_brief.html` 是手机端优先查看的富文本
文件。`mobile_brief.pdf` 依赖宿主机 Edge/Chrome headless 渲染；如果浏览器权限或环境限制导致 PDF
失败，bridge 仍应发送 HTML/Markdown，并在消息中保留简短失败原因。

其中 `agent_synthesis_pack.md` 和 `agent_synthesis_prompt.md` 是给 Codex / Agent 的输入材料，不是最终报告。
真正的深度研究报告应由 Codex / Agent 读取证据包、notes、evidence table 和知识页后写入
`reports/codex_synthesis.md`。`litagent job result --write-report --pdf --json` 不会硬编码生成这份深度综合；
它只在 `codex_synthesis.md` 已存在时，把该 Agent-authored 文稿复制/渲染为 `mobile_brief.md/html/pdf`。
如果该文件不存在，返回的 `mobile_brief.*` 只是 deterministic summary，适合作为兜底，不应当作研究级报告。

自然语言入口使用：

```text
/research 请你帮我调研一下多模态大模型领域
```

native bridge 会把它当作主题请求。默认创建真实检索 job，`max-papers` 默认约 60，并立即在后台
运行该 job。由于真实检索、下载和解析可能超过 QQ 消息回合超时，bridge 会先回复 job_id 和工作区，
流程完成后再主动推送 `/research result` 同等摘要和长版报告文件；用户不需要再发送 `/research run-next` 或
`/research result <job_id>`。

可选参数：

- `--max-papers N`：调整论文规模，允许 1 到 70。
- `--mock`：只跑离线 smoke test。
- `--queue`：只创建 queued job，不自动运行。

## 路径注意事项

如果 OpenClaw 在 Windows 宿主机运行，不要使用容器内路径：

```text
/app
/home/vscode
```

应使用 Windows 可访问路径，例如：

```text
D:/study/Autoresearch/.autoresearch/topics/<topic-slug>
D:/study/Autoresearch/.autoresearch/jobs.db
D:/study/Autoresearch/.autoresearch/library.db
D:/study/ResearchVault
```

如果 OpenClaw 运行在 WSL 或容器内，则使用对应环境真实路径。

## 最小验证

在 OpenClaw 宿主环境中先做 mock 验证：

```powershell
set AUTORESEARCH_DATA_ROOT=D:\study\Autoresearch\.autoresearch
litagent job create --topic "agentic literature review automation" --workspace "D:/study/Autoresearch/.autoresearch/topics/openclaw-smoke" --max-papers 5 --mock --sync-library --json
litagent job run-next --json
litagent job list --json
```

验证通过后再让 QQ bot 触发真实任务。

## 成功标准

- QQ bot 消息能创建 job。
- 用户能通过 QQ bot 查到 job status。
- `job run-next` 能完成 mock workflow。
- 用户能通过 QQ bot 发送 `/research result <job_id>` 查看报告/知识页手机摘要，并收到
  `mobile_brief.html` / `mobile_brief.md`，PDF 可用时优先收到 `mobile_brief.pdf`。
- `run_state.json`、`run_log.jsonl`、`artifacts_manifest.json`、`errors.json` 存在。
- `library.db` 能看到同步后的 topic 和 papers。
- OpenClaw 没有获得任意 shell 权限。

## `/research` 没有触发 Autoresearch 时

如果 QQBot 对 `/research library` 回复“你想研究哪种 library”，说明 OpenClaw 没有加载或没有选择
`autoresearch` skill，而是把 `library` 当成普通英文词处理。

先在宿主机确认 skill 是否可见：

```powershell
openclaw config get skills.load.extraDirs
openclaw skills list
```

正常应同时看到 AutoWiki-skill 和 `autoresearch`。如果没有 `autoresearch`，重新设置路径并重启：

```powershell
openclaw config set skills.load.extraDirs[1] "D:/study/Autoresearch/openclaw/skills"
openclaw config validate
openclaw gateway restart
openclaw skills list
```

如果 `openclaw skills list` 已经能看到 `autoresearch`，但 QQBot 仍然不触发，可能是旧 QQ 会话持有
旧的 skills snapshot。重启 gateway 后开启新的 QQ 会话，或让用户发送更明确的命令：

```text
/research library
请使用 autoresearch skill，执行 litagent library-status。
```

不要把这个问题误判为 `litagent` 失败。只要宿主机 `litagent job --help` 和 mock job 已通过，
CLI 层就是可用的；问题在 OpenClaw skill 加载或会话触发层。

如果 QQBot 明确回复：

```text
当前可用技能列表里没有 autoresearch skill
```

说明当前 QQ 会话仍在使用旧的 `skillsSnapshot`。继续在聊天里提示“请使用 autoresearch skill”不会
刷新这个快照。需要重置或删除当前 QQ session，让 OpenClaw 重新构建 skill snapshot。

优先使用 OpenClaw 控制台：

```text
http://localhost:18789
```

进入 `Sessions`，删除或 reset 当前 QQ 私聊 session。历史上常见的 session key 形如：

```text
agent:main:qqbot:direct:<qq-openid-hash>
agent:main:main
```

如果使用 CLI/gateway RPC，请只调用 session reset/delete，不要读取或打印 token、cookie、`.env` 或
session transcript 内容。重置后重新发送：

```text
/research library
```

## Skill 已理解但无法执行命令时

如果 QQBot 回复类似：

```text
当前环境里没有可直接调用的 autoresearch 技能 / litagent library-status 命令能力暴露
```

这说明问题已经从“命令被当成普通聊天”前进到“运行时没有暴露执行能力”。`SKILL.md` 只是技能
说明，不会自动把 `litagent` 变成 OpenClaw tool。

需要补齐以下二选一：

1. 配置一个安全 command bridge，把 `/research library`、`/research list`、
   `/research status <job_id>` 等固定命令映射到白名单 `litagent` CLI。
2. 临时使用 OpenClaw 已有的 `coding-agent` skill 执行单步白名单命令，例如只运行
   `litagent library-status --json`，并禁止读取 `.env`、token、cookie、session 等私密文件。

临时验证提示词：

```text
/research library
请使用 autoresearch skill。如果没有直接命令工具，请委托 coding-agent 在
D:/study/Autoresearch 中只运行 litagent library-status --json。
不要运行其他命令，不要读取或打印 .env、API key、QQ token、cookie 或 session 文件。
只返回论文数、主题数、runs 数、evidence 数和最近 topic 摘要。
```

长期方案应该是 command bridge / native command，而不是让聊天 agent 拥有任意 shell 权限。

## Skill 已理解但只回复占位话术时

如果 QQBot 对 `/research library` 只回复：

```text
我先帮你查当前文献库状态。
```

但没有后续结果，且：

```powershell
openclaw gateway call tools.catalog --params '{\"agentId\":\"main\",\"includePlugins\":true}' --json
openclaw approvals get --gateway
litagent library-status --json
```

分别确认了 `exec`/`process` 存在、gateway approvals 已配置、`litagent` 本机可运行，同时
approvals 的 `Last Used` 仍然是 `unknown`，说明问题不是 `litagent`、gateway 或 approvals，
而是当前 agent turn 没有真的发起 `exec` tool call。

这时优先处理：

1. 重置当前 QQ session，让新的 `SKILL.md` 和 tool profile 快照生效。
2. 确认 `openclaw/skills/autoresearch/SKILL.md` 包含硬执行规则：`/research library` 必须直接调用
   `exec` 执行 `litagent library-status --json`，禁止先回复占位话术。
3. 重新发送：

```text
/research library
```

验证方式：

```powershell
openclaw approvals get --gateway
Get-Content "C:\Windows\TEMP\openclaw\openclaw-2026-04-29.log" -Tail 300 |
  Select-String -Pattern "exec|approval|litagent|denied|safeBin|tool|error"
```

成功时，allowlist 的 `Last Used` 应更新，日志中应出现 `exec` / `litagent` 相关记录。

如果重置 session、更新 skill 描述和 approvals 后仍然只回复占位话术，不要继续调提示词。
这时应改成确定性的 native command bridge：在 QQBot channel 收到精确的
`/research library` 时，先于 agent 分发直接执行固定命令：

```text
litagent library-status --json
```

实现要求：

- 只匹配精确的 `/research library`，不要把任意用户文本拼进命令。
- 使用固定参数数组或固定命令行，不开放任意 shell executor。
- 只允许 `litagent`、`litagent.exe`、`litagent.cmd` 或 `litagent.bat` 作为执行入口。
- 输出只摘要 `papers`、`topics`、`runs`、`evidence_spans` 和最近 topic。
- 不读取、不打印 `.env`、API key、QQ token、cookie、session transcript 或完整日志。

注意：native bridge 不会经过 OpenClaw 的 `exec` tool，所以
`openclaw approvals get --gateway` 的 `Last Used` 可能仍然是 `unknown`。这不是失败信号。
新的验证方式是：

```powershell
openclaw gateway restart
# 在 QQ 发送：
# /research library

Get-Content "C:\Windows\TEMP\openclaw\openclaw-2026-04-29.log" -Tail 300 |
  Select-String -Pattern "autoresearch bridge|library-status|litagent|error"
```

成功时，QQ 应直接返回文献库统计，而不是“我先帮你查”或“无法直接执行”。

当前 native bridge 的推荐手机端 smoke 顺序：

```text
/research new agentic literature review automation --mock
/research list
/research run-next
/research status <job_id>
/research library
/research logs <job_id>
```

`<job_id>` 中的尖括号只是占位符。当前 bridge 已兼容 `/research logs <job-...>`，
但推荐手机端直接发送不带尖括号的真实 id：

```text
/research logs job-20260429T140315Z-25c5e1e4
```

实现边界：

- `/research new` 默认创建 mock job，避免手机端误触真实检索和外部 API。
- 只有显式使用 `--real` 才创建真实检索任务，例如
  `/research new 多智能体文献调研自动化工具 --real --max-papers 10`。
- 自然语言 `/research <topic>` 默认创建真实检索 job，`max-papers` 默认约 60，并自动后台运行；
  完成后主动推送手机摘要。
- `/research run-next` 仍可作为手动调试入口，但自然语言一键流程不要求用户手动调用。
- `/research status` 不带 job id 时返回最近任务列表；`/research logs` 不带 job id 时返回最近任务和正确用法。
- `job_id` 解析会去掉 ASCII / full-width 尖括号，因此 `/research logs <job-...>` 和
  `/research logs job-...` 都可用。
- 参数解析错误会直接回到手机端，不应再静默卡住。
- bridge 只构造固定 `litagent` 参数数组，不把用户文本拼进自由 shell。

2026-04-29 手机端 mock smoke 已跑通：

- `/research new ... --mock` 创建 queued job。
- `/research run-next` 执行 `topic-run` mock workflow 并成功结束。
- 成功任务自动 `sync-library`，`/research library` 可看到 5 papers、1 topic、1 run、10 evidence spans。
- `/research logs job-20260429T140315Z-25c5e1e4` 返回 `succeeded`，最近事件包括
  `job_created`、`job_started`、`job_succeeded`，最近步骤包括 `export-wiki`、`audit` 和
  `inspect-workspace` 的 succeeded 记录。

## `/research library` 报 `litagent.cmd` 不是内部或外部命令时

如果 QQBot 返回类似：

```text
执行 litagent library-status --json 失败：'\"C:\Users\Gan\.local\bin\litagent.cmd\"' 不是内部或外部命令
```

先区分两个路径：

- 仓库内的 `.openclaw/` 可能只是项目副本。
- 实际运行的 OpenClaw 通常在 `%USERPROFILE%\.openclaw`，日志里会显示
  `C:\Users\Gan\.openclaw\extensions\qqbot\index.ts`。

推荐修复方式是在真实 gateway 脚本中固定 Autoresearch 后端入口，避免让 QQBot 进程通过 PATH
猜测 `litagent.cmd`：

```bat
set "AUTORESEARCH_CWD=D:\study\Autoresearch"
set "AUTORESEARCH_DATA_ROOT=D:\study\Autoresearch\.autoresearch"
set "AUTORESEARCH_LITAGENT_BIN=D:\study\Autoresearch\.venv\Scripts\litagent.exe"
```

`AUTORESEARCH_DATA_ROOT` controls the phone-side jobs DB, library DB, and topic workspaces; this
keeps new OpenClaw runs under `D:\study\Autoresearch\.autoresearch` instead of `%USERPROFILE%`.

这两行应写入 `%USERPROFILE%\.openclaw\gateway.cmd`，位置在
`OPENCLAW_SERVICE_VERSION` 之后、启动 `node.exe ... openclaw ... gateway` 之前。写入后运行：

```powershell
openclaw gateway restart
openclaw health
```

`openclaw gateway restart` 可能因为端口健康检查误报 timeout；只要 `openclaw health` 正常、日志显示
QQBot `WebSocket connected`，即可在手机端重新发送：

```text
/research library
```

宿主机验证命令：

```powershell
& D:\study\Autoresearch\.venv\Scripts\litagent.exe library-status --json
node -e "const {execFile}=require('child_process'); execFile('D:\\study\\Autoresearch\\.venv\\Scripts\\litagent.exe',['library-status','--json'],{cwd:'D:\\study\\Autoresearch',windowsHide:true},(e,stdout,stderr)=>{if(e){console.error(stderr||stdout||e.message);process.exit(1)} console.log(stdout)})"
```

两条都成功时，说明问题不在 `litagent`，而在 OpenClaw gateway 进程的环境或旧进程未重启。

2026-04-29 已验证的最终原因和修复：

- 真实运行目录是 `C:\Users\Gan\.openclaw`，不是仓库里的 `.openclaw` 副本。
- gateway 原先仍通过 PATH 解析 `litagent.cmd`，手机端进程拿到的命令路径/quoting 不可靠。
- 最终将真实 `%USERPROFILE%\.openclaw\gateway.cmd` 固定到
  `D:\study\Autoresearch\.venv\Scripts\litagent.exe`，并设置
  `AUTORESEARCH_CWD=D:\study\Autoresearch`。
- `openclaw health` 正常、QQBot WebSocket 重连、Node `execFile` 调用成功后，手机端
  `/research library` 已直接返回文献库统计：5 papers、1 topic、1 run、10 evidence spans。
