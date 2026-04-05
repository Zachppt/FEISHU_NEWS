---
name: summarize
description: 每2小时对过滤后新闻生成板块快报推送飞书，每天08:00生成早报
---

# Summarize Skill

## 触发方式
- Cron job 每2小时触发（isolated session）→ 板块快报
- Cron job 每天 08:00 触发（isolated session）→ 早报
- 用户发送"生成汇总"手动触发

## 板块快报模式（每2小时）

### 1. 读取数据
```bash
cat ~/workspace/filtered-news.json
cat ~/workspace/watchlist.json
```
只处理最近2小时内的新条目。

### 2. 按板块生成快报
对每个有新内容的板块，生成如下格式的快报：

```
## [板块名]板块快报 · [时间]

**核心事件**
- **[事件标题]**：[一句话影响说明]
- **[事件标题]**：[一句话影响说明]

**市场分析**
[2-3句话，说明对板块的短期影响]

**重点标的**
- [股票名]：[具体影响]

**需关注**
[潜在风险，若无可省略]
```

要求：
- 最多3条核心事件
- 不写废话，没有实质内容的板块直接跳过
- 全文不超过300字

### 3. 推送飞书板块监控频道
```bash
curl -s -X POST "$FEISHU_SECTOR_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📊 [板块名]快报 · [时间]"},"template":"turquoise"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[快报内容]"}}]}}'
```

## 早报模式（每天 08:00）

### 汇总范围
过去12小时的 filtered-news.json 全部内容。

### 早报格式
```
## 金融情报早报 · [日期]

**隔夜要闻**
- [要点1]
- [要点2]
- [要点3]

**板块动态**
- 新能源：[一句话总结]
- 半导体：[一句话总结]
- AI：[一句话总结]
（只写有动态的板块）

**今日关注**
[今天需要重点关注的事项，如重要数据发布、公司业绩等]

**市场情绪**
[整体情绪一句话总结]
```

### 推送飞书早报频道
```bash
curl -s -X POST "$FEISHU_MORNING_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📰 早报 · [日期]"},"template":"blue"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[早报内容]"}}]}}'
```

## 注意事项
- FEISHU_SECTOR_WEBHOOK 和 FEISHU_MORNING_WEBHOOK 从环境变量读取
- 早报和板块快报用不同的 Webhook，推送到不同飞书群
- 同一板块2小时内只推送一次，避免刷屏
