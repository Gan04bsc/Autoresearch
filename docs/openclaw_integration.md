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

## 路径注意事项

如果 OpenClaw 在 Windows 宿主机运行，不要使用容器内路径：

```text
/app
/home/vscode
```

应使用 Windows 可访问路径，例如：

```text
D:/study/Autoresearch/topics/<topic-slug>
D:/study/Autoresearch/jobs.db
D:/study/Autoresearch/library.db
D:/study/ResearchVault
```

如果 OpenClaw 运行在 WSL 或容器内，则使用对应环境真实路径。

## 最小验证

在 OpenClaw 宿主环境中先做 mock 验证：

```powershell
litagent job create --topic "agentic literature review automation" --workspace "D:/study/Autoresearch/tmp/openclaw-smoke" --max-papers 5 --mock --sync-library --json
litagent job run-next --json
litagent job list --json
```

验证通过后再让 QQ bot 触发真实任务。

## 成功标准

- QQ bot 消息能创建 job。
- 用户能通过 QQ bot 查到 job status。
- `job run-next` 能完成 mock workflow。
- `run_state.json`、`run_log.jsonl`、`artifacts_manifest.json`、`errors.json` 存在。
- `library.db` 能看到同步后的 topic 和 papers。
- OpenClaw 没有获得任意 shell 权限。
