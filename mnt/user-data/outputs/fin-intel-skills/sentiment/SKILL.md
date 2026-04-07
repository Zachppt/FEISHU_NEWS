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

### 1b. 抓取当日价格数据（可选，失败不中断）

读取 `watchlist.json` 后，尝试通过 subprocess 执行以下 Python 脚本抓取 watchlist.stocks 中个股的当日涨跌幅：

```python
# 尝试 AKShare（国内 A 股）
try:
    import akshare as ak
    # 获取 A 股实时行情
    df = ak.stock_zh_a_spot_em()
    # 过滤出 watchlist 里的个股
    price_data = {row['名称']: {'change_pct': row['涨跌幅'], 'price': row['最新价']}
                  for _, row in df.iterrows() if row['名称'] in watchlist_stocks}
except ImportError:
    price_data = {}  # AKShare 未安装时静默跳过
```

- AKShare 未安装或抓取失败时：`price_data = {}`，不报错，不中断后续步骤
- `watchlist_stocks` 为 `watchlist.json` 中 stocks 字段的名称列表

### 2. 按板块生成情绪报告（仅供内部处理，不输出到对话窗口）

**Cron 自动触发时：不向对话窗口输出任何内容。** 分析结果仅用于更新快照和步骤4推送。
用户发送 `/sentiment 板块名` 时，才在对话窗口输出完整分析。

每个板块完整分析格式（用户查询时使用）：

```
🧠 [板块名] 情绪快照 · [HH:MM]
情绪分：[分数] [等级描述]　|　本期新闻：[N]条　|　时段：[开始]–[结束]

【总体判断】
[2-3句：多空力量对比、当前情绪主要驱动因素、近期趋势变化]

【看多因素】
① [新闻标题或事件简述]
   详情：[完整事件描述，包括数据、涉及公司、政策内容]
   影响：[为何构成利多，影响程度判断]
   来源：[媒体名称] · [时间] · [原文链接]

【看空因素】
① [新闻标题或事件简述]
   详情：[完整事件描述]
   影响：[为何构成利空，影响程度判断]
   来源：[媒体名称] · [时间] · [原文链接]

【重点标的】
• [股票名]（[代码]）：[利多↑ / 利空↓ / 中性→]　[一句话说明核心逻辑]

【热议话题】
• [话题]：[为何热议，市场核心关注点]

【下期关注】
[未来15–30分钟需要跟踪的关键变量或事件节点]
```

情绪评分规则（LLM 综合判断）：

基于新闻的完整语义打分，而非关键词匹配。关键词只是参考，最终分数由上下文决定：
- "超预期下滑"是利空，不是利多
- "监管出台政策"需结合内容判断是利多还是利空
- 同一事件对不同板块影响方向可能相反

评分维度（供参考，不作硬性公式）：
- 基本面变化（业绩、营收、利润）
- 政策环境（支持/收紧）
- 资金面（机构增持/减持、北向流入/流出）
- 产业链信号（供需、价格、库存）
- 风险事件（违约、监管、地缘）

分数范围 -100 到 +100，0 为中性，输出整数：
- +60 ~ +100：偏乐观，利好为主
- -60 ~ +60：中性，多空交织
- -100 ~ -60：偏悲观，利空为主

### 3. 更新快照文件（原子写入）
```bash
echo '<updated_json>' > ~/.openclaw/workspace/sentiment-snapshot.json.tmp && \
mv ~/.openclaw/workspace/sentiment-snapshot.json.tmp ~/.openclaw/workspace/sentiment-snapshot.json
```
快照格式：`{"last_analyzed_at": "[ISO时间戳]", "sectors": {"板块名": {...}}}`

### 4. 推送情绪快照（精简格式）

每个板块生成一条推送消息，格式如下：

```
🧠 [板块名] · [+/-分数]分 [等级] · [HH:MM]
价格：[股票名] [+/-X.X%] [印证符号]  [股票名] [+/-X.X%] [印证符号]  （[印证说明]）
↑ [看多信号标题，一行]
↑ [看多信号标题，一行]
↓ [看空信号标题，一行]
→ [中性信号标题，一行]
```

价格行叠加规则（price_data 非空且有对应个股数据时才显示）：
- 情绪分 > 0 且个股普涨（change_pct > 0）→ 个股后显示 `✅`，行末加 `（与情绪方向一致）`
- 情绪分 > 0 但个股下跌（change_pct ≤ 0）→ 个股后显示 `⚠️`，行末加 `（价格与情绪背离）`
- 情绪分 < 0 且个股下跌（change_pct ≤ 0）→ 个股后显示 `✅`，行末加 `（与情绪方向一致）`
- price_data 为空或该板块无对应股票数据 → 不显示价格行，不报错

示例：
```
🧠 新能源 · +65分 偏多 · 14:30
价格：宁德时代 +3.2% ✅  比亚迪 +1.8% ✅  （与情绪方向一致）
↑ 宁德时代固态电池路线图公布
↓ 光伏补贴政策存在退出预期
```

规则：
- 每条信号只占一行：方向箭头（↑/↓/→）+ 空格 + 新闻标题，**不展开详情/影响/来源**
- 每条消息对应一个板块，独立发送
- 消息字符数超过 4000（飞书）/ 4096（Telegram）时，按空行边界拆分成多条连续发送，不在句子中间截断
- 各板块消息逐条发送，不合并

飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SENTIMENT_WEBHOOK 已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "$FEISHU_SENTIMENT_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"🧠 情绪快照 · [板块名] · [时间]"},"template":"purple"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[单条消息内容，≤4000字符]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SENTIMENT_CHAT_ID 均已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_SENTIMENT_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[单条消息内容，≤4096字符]"}'
```

**字符截断保护逻辑：**

推送前检查消息长度：
1. 飞书上限 4000 字符，Telegram 上限 4096 字符
2. 若超出上限，从末尾向前找最近的空行（`\n\n`）作为切分点
3. 将切分点之前的内容作为第一条发送，之后的内容递归检查后再发送
4. 始终在段落边界切分，不在句子或行中间截断

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
3. 以完整格式回复用户（同上方 Agent 对话窗口的详细报告格式）
4. 不推送飞书/Telegram

---

## 注意事项
- 某板块本期无新内容则跳过，不生成空报告
- 原文链接从新闻条目的 `url` 字段读取，无链接时注明"来源：[媒体名称] · [时间]（无原文链接）"
- FEISHU_SENTIMENT_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SENTIMENT_CHAT_ID 均从环境变量读取
- 情绪分数用整数，不要小数
- 推送消息（飞书/Telegram）始终使用精简格式（板块名 + 情绪分 + 每信号一行）
- Agent 对话窗口始终输出完整详细版；用户明确说"简版"时对话窗口也可输出精简格式
