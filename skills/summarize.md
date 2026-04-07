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

快报末尾加成本行：
```
─────────────────────────
[N]板块 · [M]条新闻
> ⚙️ ~{in_tokens+out_tokens} tokens
```

POST 到 FEISHU_SECTOR_WEBHOOK，同步推 Telegram TELEGRAM_SECTOR_CHAT_ID（未配置静默跳过）。

**5. 记录成本**
```bash
ENTRY=$(jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg skill "summarize_sector" \
  --argjson in_tokens <实际或估算> \
  --argjson out_tokens <实际或估算> \
  '{ts: $ts, skill: $skill, in_tokens: $in_tokens, out_tokens: $out_tokens}')

jq --argjson e "$ENTRY" '. + [$e] | .[-500:]' \
  ~/.openclaw/workspace/cost-log.json > ~/.openclaw/workspace/cost-log.json.tmp
mv ~/.openclaw/workspace/cost-log.json.tmp ~/.openclaw/workspace/cost-log.json
```

---

### 早报模式（每天08:00）

**1. 读取数据**
```bash
# 取过去12小时内的全量新闻
jq --arg cutoff "$(date -u -d '12 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-12H +%Y-%m-%dT%H:%M:%SZ)" \
   '[.[] | select(.ts >= $cutoff)]' \
   ~/.openclaw/workspace/filtered-news.json

cat ~/.openclaw/workspace/sentiment-snapshot.json
cat ~/.openclaw/workspace/watchlist.json
```

**2. 生成早报 JSON**

将所有新闻信息综合分析，生成以下结构的 JSON（用于 PDF 生成脚本），**内容要详尽，每个字段都要认真填写**：

```json
{
  "date": "YYYY-MM-DD",
  "weekday": "星期X",

  "market_cards": [
    {"label": "纳斯达克", "value": "18,234", "change": "-0.8%", "up": false},
    {"label": "标普500",  "value": "5,123",  "change": "-0.5%", "up": false},
    {"label": "道琼斯",   "value": "38,456", "change": "-0.3%", "up": false},
    {"label": "VIX恐慌指数", "value": "18.2","change": "+1.3",  "up": true}
  ],

  "us_market": [
    "纳指收跌0.8%，英伟达领跌-2.1%，美联储官员偏鹰言论压制科技股估值",
    "特斯拉Q1交付量46.2万辆不及预期49万辆，盘后跌4.3%",
    "能源股逆势走强，埃克森美孚涨1.8%，油价受中东局势支撑",
    "10年期美债收益率升至4.42%，美元指数小幅走强至104.1"
  ],

  "macro_policy": [
    "美联储官员Waller：通胀仍有黏性，不急于降息，点阵图暗示年内仅1次",
    "欧央行拉加德：欧元区通胀继续回落，6月首次降息概率升至80%",
    "日本央行3月会议纪要：委员们讨论进一步加息时机，关注工资-通胀螺旋"
  ],

  "watch_today": [
    {"time": "09:30", "event": "A股开盘"},
    {"time": "10:00", "event": "国家统计局发布3月CPI数据（预期+0.4%，前值+0.7%）"},
    {"time": "10:30", "event": "澳洲联储利率决议（预期维持4.35%不变）"},
    {"time": "15:30", "event": "A股收盘"},
    {"time": "20:30", "event": "欧元区2月工业产出数据"},
    {"time": "21:30", "event": "🔴 美国3月非农就业数据（预期+18.5万，前值+27.5万）"},
    {"time": "23:00", "event": "美国3月密歇根大学消费者信心指数"}
  ],

  "sentiment": {
    "半导体": {
      "score": 71, "delta": 3, "label": "偏乐观",
      "top_signal": "台积电3月营收同比+42%创历史新高",
      "detail": "台积电超预期营收提振板块信心，AI芯片需求持续旺盛；华为Mate70系列市占率突破20%，国产替代加速。A股半导体ETF早盘净流入8.3亿元。"
    },
    "AI": {
      "score": 58, "delta": 0, "label": "中性",
      "top_signal": "OpenAI新一代模型发布",
      "detail": "OpenAI发布新模型推理能力超前代40%，国内大模型厂商积极跟进；但美联储偏鹰压制成长股估值，板块整体维持震荡。"
    }
  },

  "news_by_sector": {
    "宏观": [
      {
        "title": "美联储Waller：通胀仍有黏性，不急于降息",
        "summary": "美联储理事Waller表示通胀下行路径曲折，劳动力市场依然强劲，支持维持限制性利率更长时间。市场年内降息预期从2次下调至1次。",
        "source": "Bloomberg",
        "time": "06:32",
        "url": "https://..."
      }
    ],
    "半导体": [],
    "新能源": [],
    "AI": [],
    "地产": [],
    "消费": [],
    "金融": [],
    "医药": []
  },

  "watchlist_stocks": [
    {
      "name": "比亚迪",
      "news": "3月销量41.5万辆，同比+32%，创历史新高；新能源乘用车市占率升至35.2%",
      "sentiment": "positive",
      "url": "https://..."
    },
    {
      "name": "宁德时代",
      "news": "固态电池量产路线图更新，2027年小批量交付，海外产能布局加速",
      "sentiment": "positive",
      "url": "https://..."
    }
  ],

  "tokens": "~3,200"
}
```

**填写要求：**
- `us_market`：4-6条，含具体涨跌数字，不要含糊表述
- `macro_policy`：来自新闻中的宏观政策信息，2-4条
- `watch_today`：今日真实可能发生的事件，重要的用🔴标注
- `sentiment.detail`：每个板块写2-3句分析，不少于50字
- `news_by_sector`：每个有新闻的板块写2-5条，每条含 summary（1-2句话概括要点）
- `watchlist_stocks`：watchlist 中有动态的个股全部写入

**3. 生成 PDF 并发送**

将早报结构化数据（含 top_news 列表、sentiment 快照、us_market、watch_today、tokens 数）序列化为 JSON，通过 stdin 传给 PDF 生成脚本：

```bash
echo '<report_json>' | python3 ~/.openclaw/skills/FEISHU_NEWS/scripts/generate-morning-pdf.py
```

脚本输出 `PDF_PATH:/path/to/file.pdf`（或 `HTML_PATH:...` 若 PDF 库未安装）。

**发送文件到飞书（优先）：**
```bash
APP_ID=$(openclaw config get skills.entries.feishu_news.env.FEISHU_APP_ID)
APP_SECRET=$(openclaw config get skills.entries.feishu_news.env.FEISHU_APP_SECRET)
CHAT_ID=$(openclaw config get skills.entries.summarize.env.FEISHU_MORNING_CHAT_ID)

python3 ~/.openclaw/skills/FEISHU_NEWS/scripts/send-feishu-file.py \
  "<pdf_path>" "$CHAT_ID" "$APP_ID" "$APP_SECRET"
```

APP_ID / APP_SECRET 未配置时，回退到通过 Webhook 发送文字版早报（原有逻辑）：
```bash
POST 到 FEISHU_MORNING_WEBHOOK（文字早报）
```

同步推 Telegram TELEGRAM_MORNING_CHAT_ID（未配置静默跳过）。

存档到 `~/.openclaw/workspace/reports/YYYY-MM-DD-morning.pdf`。

**4. 记录成本**
```bash
ENTRY=$(jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg skill "summarize_morning" \
  --argjson in_tokens <实际或估算> \
  --argjson out_tokens <实际或估算> \
  '{ts: $ts, skill: $skill, in_tokens: $in_tokens, out_tokens: $out_tokens}')

jq --argjson e "$ENTRY" '. + [$e] | .[-500:]' \
  ~/.openclaw/workspace/cost-log.json > ~/.openclaw/workspace/cost-log.json.tmp
mv ~/.openclaw/workspace/cost-log.json.tmp ~/.openclaw/workspace/cost-log.json
```
