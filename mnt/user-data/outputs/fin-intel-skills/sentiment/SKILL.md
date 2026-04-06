---
name: sentiment
description: 对过滤后的新闻按板块做情绪分析，评分 -100 到 +100，推送飞书和 Telegram 情绪日报频道
---

# Sentiment Skill

## 触发方式
- Cron job 每15分钟触发（isolated session）
- 用户发送"/sentiment 板块名"查询特定板块

## 执行步骤（定时触发模式）

### 1. 读取最近数据
用 exec 工具读取：
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/sentiment-snapshot.json
```
处理范围：`filtered_at` 晚于 `sentiment-snapshot.json` 中 `last_analyzed_at` 的所有条目（而非固定15分钟窗口），确保 Cron 延迟或失败时不丢失数据。`sentiment-snapshot.json` 不存在时处理最近2小时的条目。

### 2. 按板块分组分析

对每个有新内容的板块，综合分析所有相关新闻，**输出完整详细内容，不限字数**：

情绪评分标准：
- +80 ~ +100：极度乐观，重大利好
- +40 ~ +80：偏多，利好消息为主
- -40 ~ +40：中性，多空交织
- -80 ~ -40：偏空，利空消息为主
- -100 ~ -80：极度悲观，重大利空

输出格式：
```
🧠 [板块名] 情绪快照 · [时间]
━━━━━━━━━━━━━━━━━━
情绪分：[分数] / 100　[对应等级描述]
本期分析新闻：[N]条

**看多因素**
- [具体新闻标题或事件]：[为什么构成利多，影响程度]
- [具体新闻标题或事件]：[分析]
（逐条列出所有支撑看多的新闻）

**看空因素**
- [具体新闻标题或事件]：[为什么构成利空，影响程度]
- [具体新闻标题或事件]：[分析]
（逐条列出所有支撑看空的新闻）

**热议话题**
- [话题1]：[简述为何热议，市场关注点]
- [话题2]：[同上]

**重点标的**
- [股票名]：[当前情绪偏向，相关新闻简述，短期关注点]
（列出本期被提及的所有个股）

**综合判断**
[2-3句完整分析：多空力量对比、近期情绪变化趋势、未来15分钟到1小时的关键变量]
```

### 3. 更新快照文件（原子写入）
快照格式：`{"last_analyzed_at": "[时间戳]", "sectors": {"板块名": {...}}}`，`last_analyzed_at` 记录本次分析完成的时间，供下次 Cron 确定处理起点。
```bash
echo '<updated_sentiment_json>' > ~/.openclaw/workspace/sentiment-snapshot.json.tmp && mv ~/.openclaw/workspace/sentiment-snapshot.json.tmp ~/.openclaw/workspace/sentiment-snapshot.json
```

### 4. 推送情绪日报
飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SENTIMENT_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_SENTIMENT_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "interactive",
    "card": {
      "header": {
        "title": {"tag": "plain_text", "content": "🧠 情绪快照 · [时间]"},
        "template": "purple"
      },
      "elements": [{
        "tag": "div",
        "text": {"tag": "lark_md", "content": "[情绪内容]"}
      }]
    }
  }'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SENTIMENT_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "'"$TELEGRAM_SENTIMENT_CHAT_ID"'",
    "parse_mode": "Markdown",
    "text": "🧠 *情绪快照 · [时间]*\n\n[情绪内容]"
  }'
```

### 5. 输出运行成本

```
💰 本次运行成本估算（情绪快照）
模型：claude-haiku-4-5
Input tokens：~[N]k  ×  $0.80/MTok  =  $[x]
Output tokens：~[N]k  ×  $4.00/MTok  =  $[x]
合计：~$[x]
```
Token 数基于处理的新闻字数和生成内容字数估算（1 token ≈ 1.5 中文字）。

---

## 用户查询模式（"/sentiment 板块名"）

1. 读取 `~/.openclaw/workspace/sentiment-snapshot.json`
2. 找到对应板块的最新快照
3. 以完整详细格式回复用户（同定时触发的输出格式）
4. 不推送飞书/Telegram 频道

---

## 注意事项
- 如果某板块本期没有新内容，跳过该板块，不生成空快照
- FEISHU_SENTIMENT_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SENTIMENT_CHAT_ID 均从环境变量读取
- 两端推送相互独立，任意端未配置则静默跳过
- 情绪分数用整数，不要小数
- **报告详细程度**：默认完整详细版；用户明确说"简版"时才输出精简格式
