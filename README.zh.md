# TikTok 达人发现工具

在本地 Mac 上运行的 TikTok 达人搜索与审核工具，无需服务器。

[English](README.md)

---

## 功能

- **API 搜索** — 按关键词搜索 TikTok，审核达人主页，将合格达人写入 Excel
- **iMessage 机器人** — 从手机发送 TikTok 链接 → 自动回复相似达人推荐；或通过 `scout #活动名 关键词` 触发搜索
- **数据看板** — 自动生成 HTML 看板，支持按活动和关键词筛选
- **消息通知** — 搜索过程中可通过 iMessage 推送进度（可选）

---

## 环境要求

| 要求 | 说明 |
|---|---|
| **macOS** | iMessage 功能依赖 macOS |
| **[uv](https://docs.astral.sh/uv/)** | Python 运行工具 — `setup.sh` 自动安装 |
| **[TikHub API Key](https://tikhub.io)** | 免费套餐可用，在 tikhub.io 申请 |
| **Messages.app** | 需在 Mac 上登录 iMessage |

无需安装 Node.js、npm 或 Python。

---

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/ruijun1110/Influencer-Mobile-Scout.git
cd Influencer-Mobile-Scout
```

### 2. 运行安装脚本

在 Finder 中双击 **`setup.command`**。

脚本将自动完成：
- 安装 `uv`（如未安装）
- 根据本机路径生成 launchd plist 文件
- 从模板创建 `.claude/.env` 并打开供编辑
- 自动启动 iMessage 机器人

### 3. 填写 API Key

`.claude/.env` 打开后，填入 TikHub API Key：

```
TIKHUB_API_KEY=你的key
NOTIFY_PHONE=+86XXXXXXXXXXX   # 可选，用于接收搜索进度通知
```

保存并关闭文件。

### 4. 授予终端"完全磁盘访问"权限

iMessage 机器人需要读取 `~/Library/Messages/chat.db`，必须手动开启权限：

**系统设置 → 隐私与安全性 → 完全磁盘访问 → 开启你使用的终端应用**

此步骤无法通过脚本自动完成，只需操作一次。

---

## iMessage 机器人

**首次使用：** 机器人会在 `setup.command` 结束时自动启动。

**手动停止后或重新安装后：** 在 Finder 中双击 **`start.command`**。

机器人在每次登录时自动启动，正常情况下安装后无需再做任何操作。

启动后，从任意可以 iMessage 你 Mac 的手机发送以下内容：

| 消息内容 | 效果 |
|---|---|
| TikTok 达人主页或视频链接 | 回复最多 10 个相似达人 |
| `scout #<活动名>` | 搜索该活动中所有待处理关键词 |
| `scout #<活动名> <关键词>` | 针对指定关键词触发搜索 |
| `scout #<未知活动名>` | 回复当前可用活动列表 |

活动名称不区分大小写。假设你有一个名为 `Beauty` 的活动：
- `scout #Beauty` — 搜索所有待处理关键词
- `scout #Beauty glass skin` — 仅搜索"glass skin"这个关键词

机器人在登录时自动启动。

查看日志：`tail -f /tmp/tiktok-lookup.log`

---

## 活动配置

活动定义了目标受众、筛选阈值和关键词队列。每个活动位于 `context/campaigns/<活动名>/` 目录下，需要两个文件。

### `campaign.md`

```yaml
---
persona: |
  描述目标受众、内容类型，以及什么样的达人符合要求。
  越具体越好 — AI 会根据此描述生成相关关键词。
view_threshold: 10000        # 搜索结果中视频的最低播放量门槛
min_video_views: 50000       # 达人近期视频需达到的最低播放量（用于资质审核）
recent_video_count: 10       # 审核达人时采样的近期视频数量
max_candidates_per_keyword: 5  # 每个关键词最多审核的达人数量
---
```

### `keywords.md`

用于追踪关键词搜索状态的 Markdown 表格：

```markdown
| keyword | status | source | date |
|---|---|---|---|
| 你的关键词 | pending | manual | 2026-03-10 |
```

- **status**：`pending`（未搜索）或 `searched`（已完成）
- **source**：`manual`（手动添加）或 `ai`（自动生成）
- **date**：关键词添加日期

关键词可以手动添加，也可以由 AI 根据活动 persona 自动生成。每次搜索完成后状态自动更新为 `searched`。

---

## 输出结果

所有结果写入 `data/influencers.xlsx`：

- **Influencers** 表 — 合格达人及播放量数据
- **Candidates** 表 — 所有审核过的达人及其状态
- **Search Log** 表 — 各活动关键词搜索历史

在浏览器中打开 `data/dashboard.html` 查看可视化看板，支持按活动和关键词筛选。

---

## 目录结构

```
├── context/
│   └── campaigns/          ← 每个活动一个文件夹
├── data/                   ← Excel 输出与看板（已加入 .gitignore）
├── setup.sh                ← 一次性安装脚本
└── .claude/
    ├── .env                ← API Key（已加入 .gitignore）
    ├── .env.example        ← 配置模板
    └── skills/
        ├── scout-api/      ← 搜索脚本
        └── tiktok-lookup/  ← iMessage 机器人 (bot.py)
```

---

## 常见问题

| 错误 | 解决方法 |
|---|---|
| 机器人无法读取消息 | 授予终端完全磁盘访问权限（步骤 4） |
| `TIKHUB_API_KEY not set` | 检查 `.claude/.env` 文件 |
| `uv: command not found` | 重新运行 `bash setup.sh` |
| 机器人不回复消息 | 确认 Messages.app 已登录；查看 `/tmp/tiktok-lookup.err` |
| 找不到 plist 文件 | 重新运行 `bash setup.sh` 重新生成 |
