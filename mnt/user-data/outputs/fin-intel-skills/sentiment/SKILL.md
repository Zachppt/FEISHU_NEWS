---
name: sentiment
description: 对过滤后的新闻按板块做情绪分析，评分 -100 到 +100，推送飞书和 Telegram 情绪日报频道
---

# Sentiment Skill

## 触发方式
- Cron job 每15分钟触发（isolated session）
- 用户发送"/sentiment 板块名"查询特定板块

---

## 执行步骤（定时触发模式）

### 1. 读取配置与数据
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/sentiment-snapshot.json
openclaw config get skills.entries.feishu_news.model.sentiment
```

处理范围：`filtered_at` 晚于 `sentiment-snapshot.json` 中 `last_analyzed_at` 的所有条目。
`sentiment-snapshot.json` 不存在时处理最近2小时的条目。

### 2. 按板块生成详细情绪报告

对每个有新内容的板块，输出以下格式（**不限字数，信息完整优先**）：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 [板块名] 情绪快照 · [HH:MM]
情绪分：[分数] [等级描述]　|　本期新闻：[N]条　|　时段：[开始]–[结束]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【总体判断】
[2-3句：多空力量对比、当前情绪主要驱动因素、近期趋势变化]

【看多因素】
① [新闻标题或事件简述]
   详情：[完整事件描述，包括数据、涉及公司、政策内容]
   影响：[为何构成利多，影响程度判断]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一条，格式同上]
（逐条列出所有支撑看多的新闻，无则省略整个【看多因素】块）

【看空因素】
① [新闻标题或事件简述]
   详情：[完整事件描述]
   影响：[为何构成利空，影响程度判断]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一条，格式同上]
（逐条列出所有支撑看空的新闻，无则省略整个【看空因素】块）

【重点标的】
• [股票名]（[代码]）：[利多↑ / 利空↓ / 中性→]　[一句话说明核心逻辑]
• [股票名]（[代码]）：[同上]
（列出本期被提及的所有个股）

【热议话题】
• [话题]：[为何热议，市场核心关注点]
• [话题]：[同上]

【下期关注】
[未来15–30分钟需要跟踪的关键变量或事件节点]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

情绪评分标准：
- +80 ~ +100：极度乐观，重大利好
- +40 ~ +80：偏多，利好消息为主
- -40 ~ +40：中性，多空交织
- -80 ~ -40：偏空，利空消息为主
- -100 ~ -80：极度悲观，重大利空

### 3. 更新快照文件（原子写入）
```bash
echo '<updated_json>' > ~/.openclaw/workspace/sentiment-snapshot.json.tmp && \
mv ~/.openclaw/workspace/sentiment-snapshot.json.tmp ~/.openclaw/workspace/sentiment-snapshot.json
```
快照格式：`{"last_analyzed_at": "[ISO时间戳]", "sectors": {"板块名": {...}}}`

### 4. 推送情绪日报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SENTIMENT_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_SENTIMENT_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"🧠 情绪快照 · [时间]"},"template":"purple"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[报告内容]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SENTIMENT_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_SENTIMENT_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[报告内容]"}'
```

### 5. 输出运行成本

读取用户配置：
```bash
openclaw config get skills.entries.feishu_news.model.sentiment
openclaw config get skills.entries.feishu_news.model.sentiment_in_price
openclaw config get skills.entries.feishu_news.model.sentiment_out_price
openclaw config get skills.entries.feishu_news.model.sentiment_currency
```

输出到对话（不推送飞书/Telegram）：

```
💰 本次成本估算 · 情绪快照
模型：[model.sentiment 的值]
Input：~[N]k tokens × [sentiment_in_price]/MTok = [计算结果] [currency]
Output：~[N]k tokens × [sentiment_out_price]/MTok = [计算结果] [currency]
合计：~[总计] [currency]
（token 数按处理新闻字数 + 生成内容字数估算，1 token ≈ 1.5 中文字）
```

若定价未配置，输出：
```
💰 本次成本估算 · 情绪快照
模型：[model.sentiment 的值]（未配置定价，无法估算成本）
```

---

## 用户查询模式（"/sentiment 板块名"）

1. 读取 `~/.openclaw/workspace/sentiment-snapshot.json`
2. 找到对应板块的最新快照
3. 以完整格式回复用户（同上方报告格式）
4. 不推送飞书/Telegram

---

## 注意事项
- 某板块本期无新内容则跳过，不生成空报告
- 原文链接从新闻条目的 `url` 字段读取，无链接时注明"来源：[媒体名称] · [时间]（无原文链接）"
- FEISHU_SENTIMENT_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SENTIMENT_CHAT_ID 均从环境变量读取
- 情绪分数用整数，不要小数
- 默认完整详细版；用户明确说"简版"时才输出精简格式
