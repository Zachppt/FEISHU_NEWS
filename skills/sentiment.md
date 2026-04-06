---
name: sentiment
description: 对 filtered-news.json 中各板块新闻做情绪分析，更新 sentiment-snapshot.json，推送飞书情绪日报频道
---

# Sentiment Skill

## 触发方式
- Cron 每15分钟自动触发
- 用户发送 `/sentiment [板块]` 查询特定板块

## 执行步骤

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/sentiment-snapshot.json
```
取最近15分钟内的新闻（按 ts 字段过滤）。

### 2. 情绪打分
对每个板块（watchlist.sectors）下的相关新闻，综合评估情绪：

**评分维度：**
- 正面信号：政策支持、业绩超预期、机构增持、技术突破
- 负面信号：监管收紧、业绩下滑、大股东减持、行业风险
- 中性：普通公告、例行披露

**输出格式（每个板块）：**
```json
{
  "sector": "新能源",
  "score": 65,
  "label": "偏乐观",
  "signal_count": 3,
  "top_signal": "宁德时代发布新一代电池技术",
  "updated_at": "2026-04-06T10:15:00Z"
}
```
分值：0-100，50为中性，>60偏乐观，<40偏悲观。

### 3. 更新快照
原子写入 sentiment-snapshot.json，只更新有新信号的板块，其余保留原值。

### 4. 推送飞书（仅当有明显变化时）
情绪分值变化超过 ±15 时推送到 FEISHU_SENTIMENT_WEBHOOK：
```
📊 板块情绪更新 HH:MM
🟢 新能源 65分（↑12）宁德时代电池技术突破
🔴 地产   32分（↓18）多家房企债务违约
```

### 5. 用户查询响应
收到 `/sentiment 新能源` 时，读取 sentiment-snapshot.json 对应板块，直接回复对话，不推送飞书。
