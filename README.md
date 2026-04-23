# garveyclaw-py

一个基于 Claude Agent SDK 和 Telegram Bot 的个人 Agent 项目。

它既包含一套可以继续扩展的正式工程，也包含一份适合学习和培训的课程版代码。

如果你想快速理解这个项目，推荐先看：

- 正式工程入口：[src/garveyclaw](/E:/AICode/AIProRepo/garveyclaw_py/src/garveyclaw)
- 课程版单文件：[claw_course_bot.py](/E:/AICode/AIProRepo/garveyclaw_py/claw_course_bot.py)
- 课程教材：[COURSE_GUIDE.md](/E:/AICode/AIProRepo/garveyclaw_py/COURSE_GUIDE.md)

当前项目已经具备这些能力：

- 通过 Telegram 接收消息并回复
- 使用 Claude Agent SDK 调用模型服务
- 支持常见 Markdown 在 Telegram 中的格式化显示
- 支持内置 Claude 工具和自定义 MCP 工具
- 支持工作区目录内的文件工具
- 支持只允许指定 owner 使用机器人
- 支持连续会话和会话重置
- 支持长期记忆文件和对话记录落盘
- 支持单次 / 每天 / 每周定时任务
- 支持简单自然语言创建定时任务

## 快速开始

如果你只是想把这个 Agent 跑起来，按下面 4 步做就够了：

1. 创建并激活 Conda 环境

```powershell
conda create -n garveyclaw python=3.12 -y
conda activate garveyclaw
```

2. 安装依赖

```powershell
python -m pip install -e .
```

3. 复制环境变量模板并填写你自己的配置

```powershell
Copy-Item .env.example .env
```

至少需要改这些值：

- `TELEGRAM_BOT_TOKEN`
- `OWNER_ID`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`

4. 启动正式工程

```powershell
python -m garveyclaw
```

启动成功后终端会看到：

```text
Bot is running...
```

## 项目结构

```text
garveyclaw_py/
├─ pyproject.toml
├─ .env
├─ claw_course_bot.py
├─ COURSE_GUIDE.md
└─ src/
   └─ garveyclaw/
      ├─ __main__.py
      ├─ access.py
      ├─ agent_tools.py
      ├─ app.py
      ├─ claude_client.py
      ├─ config.py
      ├─ memory_store.py
      ├─ scheduler.py
      ├─ scheduler_store.py
      ├─ session_store.py
      ├─ telegram_bot.py
      └─ telegram_formatting.py
```

各模块职责如下：

- `app.py`：程序入口，初始化日志并启动 Telegram 轮询
- `config.py`：读取 `.env` 并提供运行配置
- `access.py`：处理 owner 身份判断
- `agent_tools.py`：定义工作区工具和 Telegram 发送工具
- `claude_client.py`：组装 Claude 运行时、工具、hooks 和模型调用逻辑
- `memory_store.py`：负责长期记忆文件和对话记录的读写
- `scheduler_store.py`：负责定时任务数据库初始化
- `scheduler.py`：负责定时任务解析、存储、调度执行与任务管理
- `session_store.py`：负责本地 session_id 的读写和清空
- `telegram_bot.py`：处理 Telegram 命令、消息和异常
- `telegram_formatting.py`：把常见 Markdown 转成 Telegram 可渲染的 HTML
- `claw_course_bot.py`：课程版单文件示例
- `COURSE_GUIDE.md`：课程版教材

## 环境准备

推荐使用独立的 Conda 环境：

```powershell
conda create -n garveyclaw python=3.12 -y
conda activate garveyclaw
python -m pip install -e .
```

## 环境变量

项目通过 `.env` 读取配置。仓库中已经提供了示例文件：

- `.env.example`

拿到项目后，建议先复制一份：

```powershell
Copy-Item .env.example .env
```

然后把 `.env` 里的占位值替换成你自己的真实配置。

至少需要这些变量：

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_telegram_user_id
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://your-compatible-endpoint
ANTHROPIC_MODEL=qwen3.6-plus
```

可选变量：

```env
WORKSPACE_DIR=E:\AICode\AIProRepo\garveyclaw_py\workspace
```

说明：

- `TELEGRAM_BOT_TOKEN`：Telegram 机器人令牌
- `OWNER_ID`：允许使用机器人的 Telegram 用户 ID
- `ANTHROPIC_API_KEY`：模型服务鉴权 key
- `ANTHROPIC_BASE_URL`：兼容 Anthropic 协议的服务地址
- `ANTHROPIC_MODEL`：默认模型名
- `WORKSPACE_DIR`：工具默认工作的目录；不配置时默认使用项目根目录下的 `workspace/`
- `SCHEDULER_INTERVAL_SECONDS`：定时任务轮询间隔，默认 `30`

运行时还会自动在项目根目录创建：

- `data/garveyclaw_session.json`：用于保存当前连续会话的 `session_id`
- `data/garveyclaw_tasks.db`：用于保存定时任务

并在工作区目录下维护：

- `memory/CLAUDE.md`：长期记忆文件
- `memory/conversations/YYYY-MM-DD.jsonl`：按天归档的对话记录

## 启动方式

推荐方式：

```powershell
python -m garveyclaw
```

如果已经执行过 `pip install -e .`，也可以直接运行：

```powershell
garveyclaw
```

启动成功后终端会看到：

```text
Bot is running...
```

如果你想运行课程版单文件，而不是正式工程，可以执行：

```powershell
python claw_course_bot.py
```

## 克隆后如何替换成自己的配置

如果别人把这个项目克隆到自己的电脑上，通常只需要改这几类内容就能运行：

1. 替换 `.env` 中的私有配置

- `TELEGRAM_BOT_TOKEN`
- `OWNER_ID`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_MODEL`

2. 按需要修改工作区目录

如果不想用默认的 `workspace/`，可以在 `.env` 中修改：

```env
WORKSPACE_DIR=你的项目工作区路径
```

3. 如果要改课程版文件名

当前课程版文件是：

- `claw_course_bot.py`

如果你想把它改成自己的名字，比如：

- `my_agent_bot.py`

那么通常只需要改：

- 文件名本身
- 课程文档里对这个文件名的引用
- 如果代码中的启动提示文案想一起个性化，也可以顺手调整

代码逻辑本身不会因为文件名变化而失效，因为当前课程版没有依赖固定模块导入名。

## 部署建议

本地开发阶段，直接运行：

```powershell
python -m garveyclaw
```

如果你准备长期运行这个 Agent，建议至少做到下面几点：

1. 使用独立的 Conda 环境

- 不要把项目依赖混在系统 Python 或别的项目环境里

2. 单独保存 `.env`

- 真实 `.env` 不要上传 GitHub
- 仓库里只保留 `.env.example`

3. 保留 `data/` 和 `workspace/`

- `data/` 里保存 session 和定时任务数据库
- `workspace/` 里保存长期记忆和对话记录

4. 用守护方式常驻

Windows 本地可以先简单保持终端运行；如果后面上服务器，再考虑：

- Windows 任务计划
- `pm2`
- `supervisor`
- Docker / 容器化

5. 先从 owner 单用户模式开始

- 当前项目默认只服务 `OWNER_ID`
- 这样更安全，也更适合个人 Agent 阶段

## 当前工具能力

当前正式工程已经接入这些工具：

- `get_current_time`：获取当前服务器本地时间
- `list_workspace_files`：列出工作区顶层文件和目录
- `read_workspace_file`：读取工作区内文本文件
- `send_message`：向当前 Telegram 会话额外发送一条消息

同时还开启了 Claude Code 内置工具集，可在白名单允许时使用：

- `Read`
- `Write`
- `Edit`
- `Glob`
- `Grep`
- `WebSearch`
- `WebFetch`
- `Bash`

## 定时任务能力

当前正式工程已经支持：

- `/schedule_in 秒数 任务内容`：命令式创建单次任务
- `/tasks`：查看当前待执行任务
- `/cancel 任务ID`：取消任务

同时也支持简单自然语言定时表达，例如：

- `30秒后提醒我喝水`
- `今晚8点提醒我开会`
- `明天早上9点提醒我整理日报`
- `每天下午3点提醒我站起来活动一下`
- `每周一早上9点提醒我开例会`

定时任务保存在：

- `data/garveyclaw_tasks.db`

## 权限说明

- 只有 `OWNER_ID` 对应的 Telegram 用户会被处理
- 其他用户发送 `/start` 或普通消息时，机器人会直接忽略
- 文件工具只允许访问工作区目录内的路径

## 会话说明

- 机器人会把当前会话的 `session_id` 保存到 `data/garveyclaw_session.json`
- 下一条消息会优先尝试恢复这个 session，从而实现连续会话
- 可以通过 `/reset` 清空本地保存的 session，下一条消息会从新会话开始

## 记忆说明

- 长期稳定信息保存在工作区下的 `memory/CLAUDE.md`
- 每轮对话会追加保存到 `memory/conversations/` 下按日期命名的 `jsonl` 文件
- 可以通过 `/memory` 查看当前长期记忆内容
- 可以通过 `/remember 你的内容` 追加一条长期记忆

## 异常处理

当前项目已经补了基础异常处理：

- 模型调用失败时，会给用户返回友好的失败提示
- Telegram 格式化发送失败时，会自动回退成纯文本
- Telegram 网络或 API 异常会记录日志，并提示稍后重试
- 未捕获异常会进入全局错误处理器，便于排查

## 日志说明

当前默认日志策略偏安静，主要保留警告和错误：

- 正常轮询过程不会持续刷 `httpx` 请求日志
- 模型调用失败、Telegram 发送失败等问题仍会输出日志
- 启动成功时会输出 `Bot is running...`

## 停止运行

本地开发时，直接在终端按 `Ctrl + C` 即可停止机器人。
