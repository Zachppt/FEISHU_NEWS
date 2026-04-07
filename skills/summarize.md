---
name: summarize
description: 按板块汇总 filtered-news.json，生成快报或早报，推送对应飞书频道
---

# Summarize Skill

## 触发方式
- Cron 每4小时：板块快报模式
- Cron 每天08:00：早报模式
- 用户发送「生成汇总」：立即触发快报模式

## 执行步骤

---

### 板块快报模式（每4小时）

**1. 读取数据（只读标题）**
```bash
# 取最近4小时内的新闻，只读标题字段
jq --arg cutoff "$(date -u -d '4 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-4H +%Y-%m-%dT%H:%M:%SZ)" \
   '[.[] | select(.ts >= $cutoff) | {id, title, source, ts, url}]' \
   ~/.openclaw/workspace/filtered-news.json

cat ~/.openclaw/workspace/sentiment-snapshot.json
cat ~/.openclaw/workspace/watchlist.json
```

**如果近4小时无新增条目**：输出 `SUMMARIZE_SKIP: 无新内容`，结束。

**2. 按板块分组**
将新闻按 watchlist.sectors 分组，每个板块取最重要的 **3条**。
没有任何新闻的板块不展示。

**3. 生成快报**

格式：
```
📋 板块快报 · MM-DD HH:MM
─────────────────────────
🔋 新能源  🟢65 ↑5
• 宁德时代固态电池路线图发布，2027年量产
• 比亚迪Q1销量同比+45%，创历史新高
• 光伏补贴政策延续至2027年

💻 半导体  🟡52 →0
• 华为海思新芯片流片成功
• 美国芯片出口限制细则尚未落定

─────────────────────────
[N]板块 · [M]条新闻
```

情绪图标规则：score ≥ 60 → 🟢，40–59 → 🟡，< 40 → 🔴
情绪方向：变化 > +3 → ↑N，< -3 → ↓N，否则 →0

**4. 推送飞书**
POST 到 FEISHU_SECTOR_WEBHOOK，同步推 Telegram TELEGRAM_SECTOR_CHAT_ID（未配置静默跳过）。

---

### 早报模式（每天08:00）

**1. 读取数据（只读标题）**
```bash
# 取过去12小时内的新闻，只读标题字段
jq --arg cutoff "$(date -u -d '12 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-12H +%Y-%m-%dT%H:%M:%SZ)" \
   '[.[] | select(.ts >= $cutoff) | {id, title, source, ts, url}]' \
   ~/.openclaw/workspace/filtered-news.json

cat ~/.openclaw/workspace/sentiment-snapshot.json
```

**2. 生成早报**

格式：
```
📰 金融情报早报 · YYYY-MM-DD
━━━━━━━━━━━━━━━━━━━━━━

【隔夜美股】
• 纳指 +1.2%，英伟达 +3.5%
• 美联储官员偏鸽，降息预期升温

【今日关注】
• 10:00 国家统计局 CPI 数据
• 14:00 央行公开市场操作

【板块情绪】
🟢 半导体 72 | 🟢 AI 68 | 🟡 消费 51 | 🔴 地产 35

【重要新闻 Top10】
1. [新能源] 宁德时代固态电池路线图发布，2027年量产
2. [半导体] 华为海思新一代芯片流片成功
3. [宏观] 美联储官员：年内仍有降息空间
（共10条，按重要性排序）

━━━━━━━━━━━━━━━━━━━━━━
```

**3. 推送飞书**
POST 到 FEISHU_MORNING_WEBHOOK，同步推 Telegram TELEGRAM_MORNING_CHAT_ID（未配置静默跳过）。

存档到 `~/.openclaw/workspace/reports/YYYY-MM-DD-morning.md`。
