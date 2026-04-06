---
name: summarize
description: 每2小时对过滤后新闻生成板块快报，每天08:00生成早报，同步推送飞书和 Telegram
---

# Summarize Skill

## 触发方式
- Cron job 每2小时触发（isolated session）→ 板块快报
- Cron job 每天 08:00 触发（isolated session）→ 早报
- 用户发送"生成汇总"手动触发

---

## 板块快报模式（每2小时）

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
openclaw config get skills.entries.feishu_news.model.summarize
```
只处理最近2小时内的新条目。无实质内容的板块直接跳过。

### 2. 按板块生成详细快报

每个板块输出以下格式（**不限字数，完整性优先**）：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 [板块名] 板块快报 · [HH:MM]–[HH:MM]
本期新闻：[N]条　|　有效事件：[N]条
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【市场概览】
[3-5句：本周期板块整体格局，多空主要驱动力，资金面/政策面/基本面概述]

【核心事件】

① [事件标题]
   详情：[完整描述：发生了什么、涉及哪些公司、具体数据/金额/政策内容、背景]
   影响：[对板块或具体标的的短中期影响，利多/利空程度，预期持续时间]
   标的：[股票名]([代码]) [↑利多/↓利空/→中性]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一个事件，格式同上]

③ [按重要程度排列，列出本周期所有值得关注的事件]

【重点标的汇总】
| 标的 | 代码 | 方向 | 核心逻辑 |
|------|------|------|---------|
| [股票名] | [代码] | ↑利多 | [一句话] |
| [股票名] | [代码] | ↓利空 | [一句话] |
| [股票名] | [代码] | →中性 | [一句话] |

【深度分析】
[板块逻辑链：本周期多空博弈的核心矛盾，近期趋势方向，
需要跟踪的关键变量，下个2小时窗口的重要节点]

【风险提示】
• [风险点]：[详细说明，影响程度]
• [风险点]：[同上]
（无实质风险可省略此块）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3. 推送板块快报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SECTOR_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_SECTOR_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📊 [板块名]快报 · [时间]"},"template":"turquoise"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[报告内容]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SECTOR_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_SECTOR_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[报告内容]"}'
```

### 4. 输出运行成本（板块快报）

读取模型并按定价估算，输出到对话：

```
💰 本次成本估算 · 板块快报
模型：[用户配置的模型名]
Input：~[N]k tokens × $[x]/MTok = $[x]
Output：~[N]k tokens × $[x]/MTok = $[x]
合计：~$[x]
```

---

## 早报模式（每天 08:00）

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
openclaw config get skills.entries.feishu_news.model.summarize
```
处理过去12小时的全部内容。

### 2. 生成详细早报

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 金融情报早报 · [YYYY-MM-DD]
覆盖时段：昨日 [HH:MM] — 今日 [HH:MM]　|　处理新闻：[N]条
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【隔夜要闻】
① [事件标题]
   [完整描述：发生了什么、涉及哪些主体、数据/金额/政策内容、背景信息]
   影响：[对市场的影响分析]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一条，格式同上，按重要程度排列，列出所有重要事件]

【板块动态】
（只写有实质动态的板块，每个板块单独展开）

### [板块名]
[本板块过去12小时完整动态]
重要事件：
• [事件] — [一句话影响] · [来源] · [原文链接]
• [事件] — [同上]
重点标的：[股票名] [方向] / [股票名] [方向]
今日关注：[需跟踪的关键变量]

【今日关注】
• [时间] [事项]：[说明，预期影响]
• [时间] [事项]：[同上]
（重要数据发布、财报、政策窗口、重大会议等）

【市场情绪总览】
[整体多空格局、资金偏好、主要驱动因素、需要警惕的反转信号]

【风险雷达】
• [风险]：[详细说明，触发条件，影响范围]
• [风险]：[同上]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3. 推送早报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_MORNING_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_MORNING_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📰 早报 · [日期]"},"template":"blue"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[报告内容]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_MORNING_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_MORNING_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[报告内容]"}'
```

### 4. 输出运行成本（早报）

```
💰 本次成本估算 · 早报
模型：[用户配置的模型名]
Input：~[N]k tokens × $[x]/MTok = $[x]
Output：~[N]k tokens × $[x]/MTok = $[x]
合计：~$[x]
```

---

## 模型定价参考

| 模型 | Input | Output |
|------|-------|--------|
| claude-haiku-4-5 | $0.80/MTok | $4.00/MTok |
| claude-sonnet-4-6 | $3.00/MTok | $15.00/MTok |
| claude-opus-4-6 | $15.00/MTok | $75.00/MTok |

token 数按处理新闻字数 + 生成内容字数估算，1 token ≈ 1.5 中文字。

---

## 注意事项
- 原文链接从新闻条目的 `url` 字段读取；无链接时标注"（无原文链接）"
- FEISHU_SECTOR_WEBHOOK、FEISHU_MORNING_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SECTOR_CHAT_ID、TELEGRAM_MORNING_CHAT_ID 均从环境变量读取
- 两端推送相互独立，任意端未配置则静默跳过
- 同一板块2小时内只推送一次，避免刷屏
- 默认完整详细版；用户明确说"简报"时才输出精简格式
