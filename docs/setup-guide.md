# 部署指南

## 0. 前置依赖

- Linux 服务器(任何能跑 cron 和 tmux 的环境)
- Python 3.9+，`pip install pyyaml`
- `tmux`(`apt install tmux` / `yum install tmux`)
- Hermes Agent 已装并 `hermes` CLI 可用
- `lark-cli` 已装并完成绑定(参考 [lark-shared](https://hermes-agent.nousresearch.com/))

## 1. 飞书后台权限准备(最容易踩坑)

在 https://open.feishu.cn/app 找到你的 app，做下面三件事：

### 1.1 添加权限

进「权限管理」，**两栏都要勾**：

| 权限 | 用户身份 | 应用身份 |
|---|---|---|
| `bitable:app:readonly` | ✓ | ✓ |
| `im:message` (发消息) | ✓ | ✓ |
| `drive:drive:readonly` 或 `drive:file:readonly` | ✓ | ✓ |

⚠️ **「用户身份」和「应用身份」是两栏不同权限**。事件订阅走 `--as bot` 必须勾**应用身份**那栏。这是 99991672 permission denied 的最常见原因。

### 1.2 订阅事件

进「事件订阅」，订阅这两个事件：

- `drive.file.bitable_record_changed_v1`(多维表格记录变更)
- `im.message.receive_v1`(IM 消息接收，可选，用于响应 @ 提及)

### 1.3 重新创建版本并发布

权限和事件订阅改完，必须去「应用发布」**重新创建一个版本**并上线，否则改动不生效。

---

## 2. 创建任务表

参考 `templates/feishu-base-schema.json`，用 `lark-cli` 或飞书界面建一张 20 字段表。

建好后跑：

```bash
lark-cli api GET \
  /open-apis/bitable/v1/apps/<base_token>/tables/<table_id>/fields \
  --as bot
```

把每个 `field.field_id` 抄到 `config.yaml` 的 `field_ids:` 段。

---

## 3. 显式订阅 bitable 文件(第二个最容易踩坑)

仅在飞书后台勾事件类型 **不够**。drive 类事件还需要每张表显式挂单：

```bash
lark-cli api POST \
  /open-apis/drive/v1/files/<base_token>/subscribe \
  --params '{"file_type":"bitable"}' \
  --as bot
```

返回 `{"code":0, "msg":"Success"}` 即成功。`base_watch_supervisor.py` 启动 tmux 时会自动调一次这个 API,所以只要 supervisor cron 跑过就不用手工调。

⚠️ 这步如果漏了，listener 只能收到 IM 事件，**收不到任何 bitable 事件**。这是 lark-cli 文档没明说的坑。

---

## 4. 安装脚本

```bash
mkdir -p ~/.hermes/scripts ~/.hermes/cron/state ~/.hermes/feishu-kanban-task-orchestration
cp scripts/_config.py scripts/*.py ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*.py
cp config.example.yaml ~/.hermes/feishu-kanban-task-orchestration/config.yaml
# 编辑 ~/.hermes/feishu-kanban-task-orchestration/config.yaml,填入实际值
```

`_config.py` 会按这个顺序找 config.yaml：

1. `$FKTO_CONFIG` 环境变量
2. 脚本同级 `../config.yaml`
3. `~/.hermes/feishu-kanban-task-orchestration/config.yaml`
4. `/etc/feishu-kanban-task-orchestration/config.yaml`

---

## 5. 第一次手工启动 supervisor 测试

```bash
python3 ~/.hermes/scripts/base_watch_supervisor.py
# 应该看到：
# [HH:MM:SS] tmux session missing, restarting...
# [HH:MM:SS] drive subscribe ok
# [HH:MM:SS] tmux session 'larkwatch' started

tmux ls
# 应该看到：larkwatch: 1 windows ...

tail -f /tmp/larkwatch.log
# 应该看到 lark-cli 的连接日志(connected to wss://...)
# 然后去飞书表添加一行,几秒内 listener 应解析到事件
```

---

## 6. 注册 cron

参考 `templates/cron-jobs.yaml`：

```bash
hermes cron add --no-agent --schedule "* * * * *" \
  --script ~/.hermes/scripts/base_watch_supervisor.py \
  --name "飞书事件监听守护(tmux保活)"

hermes cron add --no-agent --schedule "*/3 * * * *" \
  --script ~/.hermes/scripts/kanban_watch.py \
  --name "Kanban → 飞书写回"
```

也可以用 hermes UI 创建，效果一样。

---

## 7. 故障排查

### tmux session 起不来

```bash
tmux kill-session -t larkwatch 2>/dev/null
python3 ~/.hermes/scripts/base_watch_supervisor.py
tmux ls
```

如果还是起不来，多半是 `lark-cli` 自己有问题：

```bash
LARK_CLI_NO_PROXY=1 lark-cli event +subscribe \
  --as bot --event-types drive.file.bitable_record_changed_v1
# 看错误信息
```

### 收到 IM 事件但收不到 bitable 事件

99% 是没做第 3 步的显式订阅。手工再调一次 drive subscribe API。

### bot 报 99991672 permission denied

回到第 1.1 步，确认**应用身份**那栏勾了 `bitable:app:readonly`，并且第 1.3 步重新创建版本上线了。

### kanban_watch 写不回

```bash
# 直接跑一次看错误
python3 ~/.hermes/scripts/kanban_watch.py
# 检查 hermes kanban CLI 是否能输出 JSON
hermes kanban list --tenant <你的 tenant> --json | head -20
```

### lark-cli 经代理报 [WARN] proxy detected

设置 `env.LARK_CLI_NO_PROXY: "1"` (config.yaml 里默认已设)。
