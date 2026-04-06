---
name: summarize
description: 按板块汇总 filtered-news.json，生成快报或早报，推送对应飞书频道
---

# Summarize Skill

## 触发方式
- Cron 每2小时：板块快报模式
- Cron 每天08:00：早报模式
- 用户发送「生成汇总」：立即触发快报模式

## 执行步骤

### 板块快报模式（每2小时）

**1. 读取数据**
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/sentiment-snapshot.json
cat ~/.openclaw/workspace/watchlist.json
```
取最近2小时内的新闻。

**2. 按板块分组**
将新闻按 watchlist.sectors 分组，每个板块取最重要的3条。

**3. 生成快报**
```
📋 板块快报 HH:MM

🔋 新能源（情绪：偏乐观 65分）
• 宁德时代发布固态电池路线图，计划2027年量产
• 比亚迪Q1销量创新高，同比+45%
• 光伏装机量超预期，政策补贴延续

💻 半导体（情绪：中性 52分）
• 华为海思新一代芯片流片成功
• 美国芯片禁令新规细则待定，市场观望
```

**4. 推送飞书**
POST 到 FEISHU_SECTOR_WEBHOOK。

---

### 早报模式（每天08:00）

**1. 读取数据**
取过去12小时所有 filtered-news.json 内容，叠加 sentiment-snapshot.json。

**2. 生成早报结构**
```
📰 金融情报早报 YYYY-MM-DD

【隔夜美股】
• 纳指 +1.2%，科技股普涨，英伟达 +3.5%
• 美联储官员发言偏鸽，降息预期升温

【今日关注】
• 10:00 国家统计局发布3月CPI数据
• 14:00 央行公开市场操作

【板块情绪】
🟢 半导体 72分 | 🟢 AI 68分 | 🟡 消费 51分 | 🔴 地产 35分

【重要新闻】
（按板块列出昨夜至今最重要的10条）
```

**3. 推送飞书**
POST 到 FEISHU_MORNING_WEBHOOK。
同时存档到 `~/.openclaw/workspace/reports/YYYY-MM-DD-morning.md`。
