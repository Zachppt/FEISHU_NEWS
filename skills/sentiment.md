---
name: sentiment
description: 对 filtered-news.json 中各板块新闻做情绪分析，更新 sentiment-snapshot.json，推送飞书情绪日报频道
---

# Sentiment Skill

## 触发方式
- Cron 每30分钟自动触发
- 用户发送 `/sentiment [板块]` 查询特定板块

## 执行步骤

### 1. 读取数据

```bash
# 只取最近30分钟内的新闻标题（不读摘要）
jq --arg cutoff "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
   '[.[] | select(.ts >= $cutoff) | {id, title, ts}]' \
   ~/.openclaw/workspace/filtered-news.json

cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/sentiment-snapshot.json
```

**如果近30分钟新增条数 < 3**：
→ 输出 `SENTIMENT_SKIP: 新增条目不足，跳过本次分析`，结束。

### 2. 情绪打分（一次性处理所有板块）

将所有板块和新闻标题合并为**一个请求**，同时评估所有板块，不分批调用。

**评分维度：**
- 正面：政策支持、业绩超预期、机构增持、技术突破、利好公告
- 负面：监管收紧、业绩下滑、大股东减持、债务问题、行业风险
- 中性：普通公告、例行披露

**输出结构（每个板块）：**
```json
{
  "sector": "新能源",
  "score": 65,
  "label": "偏乐观",
  "delta": 12,
  "signal_count": 3,
  "top_signal": "宁德时代发布固态电池路线图",
  "updated_at": "2026-04-07T10:30:00Z"
}
```
分值：0-100，50 为中性，>60 偏乐观，<40 偏悲观。
`delta` 为相对上次快照的变化量。

### 3. 更新快照
原子写入 sentiment-snapshot.json，只更新有新信号的板块，其余保留原值。

### 4. 推送飞书（仅当有板块变化 ≥ ±10 时推送）

**只推送发生变化的板块**，未变化板块不展示：

```
📊 板块情绪 · HH:MM

🟢 新能源  65 ↑12  宁德时代固态电池路线图
🔴 地产    33 ↓18  多家房企债务违约

[N条新信号]
```

情绪图标规则：
- score ≥ 60 → 🟢
- 40 ≤ score < 60 → 🟡
- score < 40 → 🔴

POST 到 FEISHU_SENTIMENT_WEBHOOK，同步推 Telegram TELEGRAM_SENTIMENT_CHAT_ID（未配置静默跳过）。

**无变化时（所有板块 delta < ±10）：不推送，静默结束。**

### 5. 记录成本并推送

将本次调用信息追加到 cost-log.json：
```bash
ENTRY=$(jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg skill "sentiment" \
  --argjson in_tokens <实际或估算输入tokens> \
  --argjson out_tokens <实际或估算输出tokens> \
  --argjson new_items <本次分析的新增条目数> \
  --argjson pushed <是否推送，0或1> \
  '{ts: $ts, skill: $skill, in_tokens: $in_tokens, out_tokens: $out_tokens, new_items: $new_items, pushed: $pushed}')

jq --argjson e "$ENTRY" '. + [$e] | .[-500:]' \
  ~/.openclaw/workspace/cost-log.json > ~/.openclaw/workspace/cost-log.json.tmp
mv ~/.openclaw/workspace/cost-log.json.tmp ~/.openclaw/workspace/cost-log.json
```

推送的飞书消息末尾加一行成本注释（灰色小字，用 `>` 引用格式）：
```
> ⚙️ ~{in_tokens+out_tokens} tokens
```

### 6. 用户查询响应
收到 `/sentiment 新能源` 时，读取 sentiment-snapshot.json 对应板块，直接回复对话，不推送飞书。
