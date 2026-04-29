---
name: autoresearch
description: "Use whenever the user sends /research, /research new, /research library, /research status, /research run-next, /research logs, /research sync, or asks from OpenClaw/QQ/mobile to start, monitor, cancel, sync, or inspect an Autoresearch/litagent literature research job. For /research library, if exec is available, call exec immediately with command `litagent library-status --json` before replying; never send placeholder text like 'I will check' without command results. This skill maps /research commands and natural-language research requests to safe litagent job queue commands only."
---

# Autoresearch OpenClaw Skill

你是 Autoresearch 的 OpenClaw 入口层。你只负责把手机、QQ bot 或 WebChat 中的用户请求映射为
安全的 `litagent job` 白名单命令，并把状态摘要返回给用户。

## Trigger Rule

如果用户消息以 `/research` 开头，必须使用本 skill。不要把 `/research library` 理解为“调研某个
library”。它是 Autoresearch 命令，必须映射到 `litagent library-status --json`。

必须识别的命令包括：

```text
/research new <topic>
/research run-next
/research status <job_id>
/research list
/research cancel <job_id>
/research logs <job_id>
/research library
/research sync <workspace>
```

如果命令缺少必要参数，追问缺少的参数；不要自由发挥成普通研究建议。

## Hard Execution Rule

`/research` 命令是命令入口，不是普通聊天入口。命中本 skill 后，必须先执行对应的白名单
`litagent` 命令，再根据命令结果回复。禁止先回复“我来查”“我先帮你查”这类没有执行结果的
占位消息。

如果当前工具列表中存在 `exec` 工具：

- `/research library` 必须立即调用 `exec`，命令只能是 `litagent library-status --json`。
- 调用成功后，只摘要 JSON 中的 `papers`、`topics`、`runs`、`evidence_spans` 和最近 topic。
- 调用失败后，只返回简短错误和下一步，不要编造结果。
- 如果 `exec` 工具不可用，只能回复：`exec unavailable`。

`exec` 调用约束：

```text
cwd: D:/study/Autoresearch
command: litagent library-status --json
```

不要为了执行该命令而调用 `powershell`、`cmd /c`、`sh -c`、`python -c`、`curl`、`wget` 或任意
自由 shell 包装器。不要读取或输出 `.env`、API key、QQ token、cookie、session 文件或完整日志。

## Core Boundary

- OpenClaw 是入口和通知层。
- `litagent` 是确定性研究流程执行层。
- Codex / Agent 是判断、质疑、综合和中文写作层。
- `SKILL.md` 本身只是技能说明，不等于已经有命令执行工具。
- 如果当前 OpenClaw 会话没有直接暴露命令执行能力，必须使用已配置的安全 command bridge；
  若只能使用 `coding-agent`，也只能让它执行本文件列出的白名单 `litagent` 命令。
- 不允许 OpenClaw 自由执行 shell。
- 不允许 OpenClaw 绕过 `litagent job` 直接拼接任意命令。
- 不允许绕过 paywall、抓取 Google Scholar 或下载非法 PDF。
- 不要在消息、日志或文件中输出 API key、Bearer token、`.env` 内容或私密凭据。

## Allowed Commands

只允许调用以下命令族：

```bash
litagent job create ...
litagent job status ...
litagent job list ...
litagent job cancel ...
litagent job logs ...
litagent job run-next ...
litagent library-status ...
litagent inspect-workspace ...
litagent export-wiki ...
```

## Runtime Execution Rule

当用户发送 `/research ...` 时，先判断当前 OpenClaw 会话是否有可调用的命令工具。

优先级：

1. 如果存在安全 command bridge / native command tool，直接执行对应白名单命令。
2. 如果没有 command bridge，但 `coding-agent` skill 可用，只能把一个明确、单步、白名单命令委托给
   `coding-agent`。委托内容必须指定工作目录、唯一命令和禁止事项。
3. 如果既没有 command bridge，也没有 `coding-agent`，明确告诉用户：
   `autoresearch` skill 已加载但当前运行时没有暴露 `litagent` 执行能力，需要配置 command bridge
   或启用受限 `coding-agent`。

禁止在没有执行工具时假装已经执行命令。也不要把 `/research library` 改写成普通“library 调研”。

安全委托模板：

```text
请在 Windows 宿主机工作目录 D:/study/Autoresearch 中只运行以下命令：
litagent library-status --json

不要运行其他命令，不要读取或打印 .env、API key、QQ token、cookie 或 session 文件。
只返回 JSON 的论文数、主题数、runs 数、evidence 数和最近 topic 摘要。
```

禁止：

```bash
sh -c "<free-form command>"
powershell "<free-form command>"
cmd /c "<free-form command>"
python -c "<free-form command>"
curl ...
wget ...
git ...
rm ...
del ...
```

## Default Paths

默认路径可以按本机实际配置调整，但不要在聊天里暴露密钥。

```text
topics root: ~/.autoresearch/topics/
jobs db: ~/.autoresearch/jobs.db
library db: ~/.autoresearch/library.db
wiki vault root: ~/ResearchVault 或用户指定的 Obsidian vault
```

如果 OpenClaw 运行在 Windows 宿主机，路径应使用宿主机可访问路径，例如：

```text
D:/study/Autoresearch/topics/<topic-slug>
D:/study/Autoresearch/library.db
D:/study/Autoresearch/jobs.db
D:/study/ResearchVault
```

不要假设容器内 `/app` 路径就是 OpenClaw/QQ bot 实际运行路径。需要以
`openclaw config get ...` 和用户确认的 QQ bot 实例为准。

## Command Mapping

### `/research new <topic>`

创建排队任务，不直接执行任意 shell。

```bash
litagent job create \
  --topic "<topic>" \
  --workspace "<topics-root>/<topic-slug>" \
  --max-papers 50 \
  --sync-library \
  --library-db "<library-db>" \
  --topic-slug "<topic-slug>" \
  --json
```

返回给用户：

```text
已创建调研任务：<job_id>
主题：<topic>
状态：queued
工作区：<workspace>
发送 /research run-next 开始执行，或 /research status <job_id> 查看状态。
```

### `/research run-next`

运行最早的 queued job。

```bash
litagent job run-next --jobs-db "<jobs-db>" --json
```

返回：

```text
任务已完成/失败：<job_id>
状态：succeeded/failed
工作区：<workspace>
下一步：打开 Obsidian vault 或发送 /research logs <job_id>
```

### `/research status <job_id>`

```bash
litagent job status <job_id> --jobs-db "<jobs-db>" --json
```

只返回摘要：状态、主题、当前进度、workspace、最后错误。不要返回完整 payload 中的敏感字段。

### `/research cancel <job_id>`

```bash
litagent job cancel <job_id> --jobs-db "<jobs-db>" --json
```

queued job 可以取消；running job 只能记录 cancel request，不能保证立即杀掉进程。

### `/research logs <job_id>`

```bash
litagent job logs <job_id> --jobs-db "<jobs-db>" --json
```

只摘要最近阶段，不要把超长 `run_log` 原样刷屏。

### `/research sync <workspace>`

```bash
litagent export-wiki "<workspace>" --format autowiki --out "<vault-out>" --json
```

用于把已有 workspace 导出到 Obsidian vault。导出后仍需 Codex/AutoWiki 对关键页面做二次编译。

### `/research library`

```bash
litagent library-status --library-db "<library-db>" --json
```

返回全局库论文数、主题数、evidence 数和最近 topic。

如果没有直接命令工具，但有 `coding-agent`，使用上面的安全委托模板，并把命令替换为：

```bash
litagent library-status --json
```

### `/research list`

```bash
litagent job list --jobs-db "<jobs-db>" --json
```

返回最近任务的 job_id、主题、状态和 workspace 摘要。

## Topic Strategy

当用户只输入一个主题，比如“多模态模型”，默认创建研究型文献工作台任务，而不是综述写作任务。

默认意图：

- 找权威综述搭建领域地图。
- 找高质量技术/系统论文追踪前沿方法。
- 找 benchmark/dataset 论文建立评估视角。
- 生成 Obsidian/AutoWiki 可维护的知识库。
- 不把 `final_report.md` 当作唯一终点。

默认数量：

- 新领域可以从 50 篇左右开始，但必须优先高质量论文。
- 如果用户明确要求小规模试跑，使用 10 到 15 篇。
- 不用低质量论文凑数量。

## Response Style

- 默认中文。
- 给用户返回短状态，不刷长 JSON。
- 必要英文术语第一次出现时使用“中文解释（English term）”。
- 明确说明任务是否只是 queued，还是已经 running/succeeded/failed。
- 如果失败，给下一步可执行动作，而不是只贴错误栈。

## Safety Checklist

执行前检查：

- 当前 OpenClaw 是否是用户确认的 QQ bot 实例。
- `litagent` 是否在 OpenClaw 运行环境 PATH 中。
- `jobs.db` 和 `library.db` 路径是否是宿主机可访问路径。
- `.env` 是否只在本机安全位置，不写入仓库。
- 不要把 container-only `/app` 路径误配给 Windows 宿主机 QQ bot。
