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
git clone <repo-url>
cd influencer-search-agent
```

### 2. 运行安装脚本

```bash
bash setup.sh
```

脚本将自动完成：
- 安装 `uv`（如未安装）
- 根据本机路径生成 launchd plist 文件
- 从模板创建 `.claude/.env` 并打开供编辑

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

启动后台守护进程：

```bash
launchctl load ~/Library/LaunchAgents/com.tiktok-lookup.plist
```

启动后，从任意可以 iMessage 你的 Mac 的手机发送：

| 消息内容 | 效果 |
|---|---|
| `https://www.tiktok.com/@某达人` | 回复最多 10 个相似达人 |
| `scout #Beauty glass skin` | 以"glass skin"为关键词搜索 Beauty 活动 |
| `scout #Beauty` | 搜索 Beauty 活动中所有待处理关键词 |
| `scout #未知活动` | 回复当前可用活动列表 |

机器人在登录时自动启动。

查看日志：`tail -f /tmp/tiktok-lookup.log`

---

## 活动配置

活动文件夹位于 `context/campaigns/<活动名>/`，每个活动需要两个文件：

**`campaign.md`** — 定义目标受众和筛选阈值：
```yaml
---
persona: |
  描述目标受众和内容类型。
view_threshold: 10000
min_video_views: 50000
recent_video_count: 10
max_candidates_per_keyword: 5
---
```

**`keywords.md`** — 关键词队列：
```markdown
| keyword | status | source | date |
|---|---|---|---|
| skincare routine | pending | manual | 2026-03-10 |
| glass skin | pending | manual | 2026-03-10 |
```

状态流转：`pending` → `searched`

---

## 输出结果

所有结果写入 `data/influencers.xlsx`：

- **Influencers** 表 — 合格达人及播放量数据
- **Candidates** 表 — 所有审核过的达人
- **Search Log** 表 — 关键词搜索历史

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
