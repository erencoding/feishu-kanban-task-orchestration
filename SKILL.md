---
name: feishu-kanban-task-orchestration
description: 把"飞书多维表格"做成任务源、Hermes Kanban 做执行总线、orchestrator/worker profiles 做执行人的全套任务编排体系。包含飞书实时事件监听(WebSocket via lark-cli)、kanban 状态自动写回、双向同步、清单字段约定。当用户在飞书任务表创建/编辑任务时即时通知；当 kanban 任务推进时把进展、交付物、复核状态、QA 写回飞书。
---

# 飞书 ↔ Hermes Kanban 任务编排 Skill

## 这是什么

一套把「飞书多维表格」当成任务管理 UI、把 Hermes Kanban 当成执行队列、把 orchestrator/worker profile 当作执行体的多 Agent 协作模板。

```
[人 在飞书表打字] ──实时事件──▶ [base_event_listener] ──通知──▶ [orchestrator profile]
                                                                      │
                                                              spawn worker
                                                                      ▼
[飞书表自动更新] ◀──3min 轮询写回── [kanban_watch] ◀──状态──── [Hermes Kanban]
```

零 LLM token 消耗的监控（cron + no_agent），秒级延迟的事件监听。

## 核心组件

| 文件 | 用途 | 触发方式 |
|---|---|---|
| `scripts/base_event_listener.py` | 解析飞书 WebSocket 事件、拉记录、发 DM | tmux 内 stdin pipe |
| `scripts/base_watch_supervisor.py` | tmux 保活 + drive subscribe API | cron 每 60s |
| `scripts/kanban_watch.py` | kanban → 飞书表写回 | cron 每 3 分钟 |
| `templates/feishu-base-schema.json` | 20 字段任务表的字段定义 | 一次性建表 |
| `templates/cron-jobs.yaml` | hermes cronjob 定义清单 | hermes cronjob 注册 |
| `config.example.yaml` | 全部参数集中点 | 复制为 config.yaml |

## 使用前提

- Hermes Agent 已安装（`hermes` CLI 可用）
- `lark-cli` 已安装并完成 OAuth 绑定（参考 `lark-shared` skill）
- Hermes app 已订阅事件 `drive.file.bitable_record_changed_v1`、`im.message.receive_v1`，并在「应用身份」勾选 `bitable:app:readonly`
- 系统装了 `tmux`、`python3`、`pyyaml`

## 快速上手（5 步）

### 1. 建飞书任务表

参考 `templates/feishu-base-schema.json`（20 字段），用 `lark-cli base +table-create` 或飞书界面创建。建好后跑一次：

```bash
lark-cli api GET /open-apis/bitable/v1/apps/<base_token>/tables/<table_id>/fields --as bot
```

把每个字段的 `field_id` 抄进 `config.yaml` 的 `field_ids:` 段。

### 2. 写 config.yaml

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入 base_token / table_id / chat_id / 字段 ID
```

### 3. 部署脚本

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/cron/state
cp scripts/*.py ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*.py
```

`config.yaml` 默认会从脚本目录 `../config.yaml` 加载，也可以放 `~/.hermes/feishu-kanban-task-orchestration/config.yaml`，或用环境变量 `FKTO_CONFIG=/path/to/config.yaml` 指定。

### 4. 注册 cron 任务

参考 `templates/cron-jobs.yaml` 用 hermes cron 注册：

```bash
hermes cron add --no-agent --schedule "* * * * *"   --script ~/.hermes/scripts/base_watch_supervisor.py --name "飞书事件监听守护"
hermes cron add --no-agent --schedule "*/3 * * * *" --script ~/.hermes/scripts/kanban_watch.py --name "Kanban→飞书写回"
```

### 5. 验证

- 在飞书表新增/编辑一行 → 应在 1~3 秒内收到 DM
- 跑一个 kanban 任务，标记 done → 3 分钟内飞书表对应行进展变「已完成」

## 数据流详解

详见 `docs/architecture.md`。关键约定：

- **Kanban链**字段记录任务的 kanban id 链：`t_a1b2c3d4 ← ✅t_e5f6g7h8`
- **澄清记录**字段是 append-only 的多轮 Q/A 日志
- **复核状态**默认「待复核」→ 用户复核后改「通过」/「有问题」/「已修正」
- worker 在 kanban comment 里发 `[QUESTION]` / `[ANSWER]` 触发澄清流转

## 已知坑（必读）

详见 `docs/setup-guide.md`。最容易踩的两个：

1. **drive 类事件订阅是两步**：飞书后台勾事件类型只是第一步，每张表还要调 `POST /open-apis/drive/v1/files/{token}/subscribe?file_type=bitable` 显式挂单，否则只能收 IM 事件、收不到 bitable 事件。
2. **「用户身份」≠「应用身份」**：飞书后台权限管理有两栏，事件订阅走 `--as bot` 必须勾**应用身份**那栏，改完还要去「应用发布」重新创建版本并上线。

## 仓库

源码：https://github.com/erencoding/feishu-kanban-task-orchestration

## License

MIT
