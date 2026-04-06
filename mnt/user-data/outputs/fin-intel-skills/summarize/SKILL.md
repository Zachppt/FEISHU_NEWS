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
```
只处理最近2小时内的新条目。

### 2. 按板块生成详细快报

对每个有新内容的板块，生成完整详细的快报，**不限字数**，信息量优先：

```
## [板块名]板块快报 · [时间]

**核心事件**
列出本周期内所有值得关注的事件，每条包含：
- **[事件标题]**
  - 事件详情：[完整描述，包括涉及公司、数据、政策内容等]
  - 市场影响：[对板块或具体标的的短期、中期影响分析]
  - 信息来源：[来源名称] · [发布时间]

**市场分析**
[深度分析：本周期板块整体走势逻辑，多空博弈，资金面/政策面/基本面各自驱动力，
预计未来2-4小时的演变方向，需要注意的关键节点]

**重点标的**
- [股票名]：[具体影响分析，包括利多/利空程度、预期涨跌幅方向、需关注的催化剂]
- [股票名]：[同上]
（列出所有在本周期新闻中被提及的个股）

**风险提示**
- [风险点1]：[说明]
- [风险点2]：[说明]
（若无实质风险可省略）

**数据来源统计**
本周期处理新闻：[N]条 | 命中本板块：[N]条 | 数据源：[来源列表]
```

没有任何实质内容的板块直接跳过，不生成空报告。

### 3. 推送板块快报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SECTOR_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_SECTOR_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📊 [板块名]快报 · [时间]"},"template":"turquoise"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[快报内容]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SECTOR_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_SECTOR_CHAT_ID"'","parse_mode":"Markdown","text":"📊 *[板块名]快报 · [时间]*\n\n[快报内容]"}'
```

### 4. 输出运行成本

每次运行结束后输出本次成本估算：
```
💰 本次运行成本估算（板块快报）
模型：claude-sonnet-4-5
Input tokens：~[N]k  ×  $3.00/MTok  =  $[x]
Output tokens：~[N]k  ×  $15.00/MTok =  $[x]
合计：~$[x]
```
Token 数基于处理的新闻字数和生成内容字数估算（1 token ≈ 1.5 中文字）。

---

## 早报模式（每天 08:00）

### 汇总范围
过去12小时的 filtered-news.json 全部内容。

### 早报格式

生成完整详细的早报，**不限字数**：

```
## 金融情报早报 · [日期]

**隔夜要闻**（列出所有重要事件，每条完整描述）
- **[事件标题]**
  [完整描述：发生了什么、涉及哪些主体、数据/金额/政策内容、背景信息]
  影响：[对市场的影响分析]

**板块动态**（只写有动态的板块，每个板块单独分析）
### [板块名]
[本板块过去12小时的完整动态，重要事件逐条列出，分析逻辑链条，
关注的重点标的，今日需要跟踪的关键变量]

**今日关注**
- [事项1]：[说明，包括时间、预期影响]
- [事项2]：[说明]
（重要数据发布、财报、政策窗口、重大会议等）

**市场情绪**
[整体情绪分析：多空分布、资金偏好、主要驱动因素、需要警惕的反转信号]

**风险雷达**
- [风险1]：[详细说明]
- [风险2]：[详细说明]
```

### 推送早报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_MORNING_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_MORNING_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📰 早报 · [日期]"},"template":"blue"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[早报内容]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_MORNING_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_MORNING_CHAT_ID"'","parse_mode":"Markdown","text":"📰 *早报 · [日期]*\n\n[早报内容]"}'
```

### 输出运行成本

```
💰 本次运行成本估算（早报）
模型：claude-sonnet-4-5
Input tokens：~[N]k  ×  $3.00/MTok  =  $[x]
Output tokens：~[N]k  ×  $15.00/MTok =  $[x]
合计：~$[x]
```

---

## 注意事项
- FEISHU_SECTOR_WEBHOOK、FEISHU_MORNING_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SECTOR_CHAT_ID、TELEGRAM_MORNING_CHAT_ID 均从环境变量读取
- 两端推送相互独立，任意端未配置则静默跳过
- 早报和板块快报用不同的频道，飞书和 Telegram 各自对应两个目标
- 同一板块2小时内只推送一次，避免刷屏
- **报告详细程度**：默认输出完整详细版本；用户明确说"简报"或"摘要"时才输出精简版
