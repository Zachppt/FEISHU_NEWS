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
openclaw config get skills.entries.feishu_news.model.summarize
```
只处理最近2小时内的新条目。该时段内无新条目的板块直接跳过。

条目选取原则（板块快报和早报均适用）：
- `priority == "high"` 的条目必须纳入
- 其余条目综合 score、时效性、与其他条目的互补性，由你判断取舍
- 避免选入内容高度重叠的条目（同一事件多篇报道只取一篇）
- 每个板块最多 3 条，宁缺毋滥

### 2. 按板块生成详细快报（仅供内部处理，不输出到对话窗口）

**Cron 自动触发时：不向对话窗口输出任何内容。** 完整分析仅保存在内存中供步骤3推送使用。
用户主动发送"生成汇总"时，才在对话窗口输出完整分析。

每个板块完整分析格式（用户查询时使用）：

```
📊 [板块名] 板块快报 · [HH:MM]–[HH:MM]
本期新闻：[N]条　|　有效事件：[N]条

【市场概览】
[3-5句：本周期板块整体格局，多空主要驱动力，资金面/政策面/基本面概述]

【核心事件】

① [事件标题]
   详情：[完整描述：发生了什么、涉及哪些公司、具体数据/金额/政策内容、背景]
   影响：[对板块或具体标的的短中期影响，利多/利空程度，预期持续时间]
   标的：[股票名]([代码]) [↑利多/↓利空/→中性]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一个事件，格式同上]

【重点标的汇总】
[股票名]([代码]) ↑  [一句话核心逻辑]
[股票名]([代码]) ↓  [一句话核心逻辑]
[股票名]([代码]) →  [一句话核心逻辑]

【深度分析】
[板块逻辑链：本周期多空博弈的核心矛盾，近期趋势方向，
需要跟踪的关键变量，下个2小时窗口的重要节点]

【风险提示】
• [风险点]：[详细说明，影响程度]
（本块始终输出；若本周期无风险信号，写"暂无明显风险信号"）
```

### 3. 推送板块快报（精简格式）

每个板块生成一条推送消息，格式如下：

```
📊 [板块名]快报 · [HH:MM]–[HH:MM]

① [事件标题]
   影响：[一句话影响判断]
   来源：[媒体名称] · [时间]

② [事件标题]
   影响：[一句话影响判断]
   来源：[媒体名称] · [时间]

↑ [股票名]  ↓ [股票名]  → [股票名]
```

规则：
- 每个板块一条消息，独立发送
- 不使用表格，改用简洁列表
- 不使用 `━━━━` 分隔符，段落之间用空行分隔
- 来源只写媒体名称和时间，不附原文链接（链接在对话窗口完整版中保留）
- 消息字符数超过 4000（飞书）/ 4096（Telegram）时，按空行边界拆分成多条连续发送，不在句子中间截断

飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_SECTOR_WEBHOOK 已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "$FEISHU_SECTOR_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📊 [板块名]快报 · [时间]"},"template":"turquoise"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[单条消息内容，≤4000字符]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_SECTOR_CHAT_ID 均已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_SECTOR_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[单条消息内容，≤4096字符]"}'
```

**字符截断保护逻辑：**

推送前检查消息长度：
1. 飞书上限 4000 字符，Telegram 上限 4096 字符
2. 若超出上限，从末尾向前找最近的空行（`\n\n`）作为切分点
3. 将切分点之前的内容作为第一条发送，之后的内容递归检查后再发送
4. 始终在段落边界切分，不在句子或行中间截断

### 4. 输出运行成本（板块快报）

读取用户配置：
```bash
openclaw config get skills.entries.feishu_news.model.summarize
openclaw config get skills.entries.feishu_news.model.summarize_in_price
openclaw config get skills.entries.feishu_news.model.summarize_out_price
openclaw config get skills.entries.feishu_news.model.summarize_currency
```

输出到对话（不推送飞书/Telegram）：
```
💰 本次成本估算 · 板块快报
模型：[model.summarize 的值]
Input：~[N]k tokens × [summarize_in_price]/MTok = [计算结果] [currency]
Output：~[N]k tokens × [summarize_out_price]/MTok = [计算结果] [currency]
合计：~[总计] [currency]
（token 数按处理新闻字数 + 生成内容字数估算，1 token ≈ 1.5 中文字）
```

若定价未配置，输出：
```
💰 本次成本估算 · 板块快报
模型：[model.summarize 的值]（未配置定价，无法估算成本）
```

---

## 早报模式（每天 08:00）

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/watchlist.json
openclaw config get skills.entries.feishu_news.model.summarize
```
处理过去12小时的全部内容。

### 2. 生成详细早报（仅供内部处理和 PDF 使用，不输出到对话窗口）

**Cron 自动触发时：不向对话窗口输出任何内容。** 完整内容用于生成 PDF 和步骤3摘要推送。

完整早报格式（PDF 内容 / 用户主动查询时使用）：

```
📰 金融情报早报 · [YYYY-MM-DD]
覆盖时段：昨日 [HH:MM] — 今日 [HH:MM]　|　处理新闻：[N]条

【隔夜要闻】
① [事件标题]
   [完整描述：发生了什么、涉及哪些主体、数据/金额/政策内容、背景信息]
   影响：[对市场的影响分析]
   来源：[媒体名称] · [时间] · [原文链接]

② [下一条，格式同上]

【板块动态】
（只写有实质动态的板块，每个板块单独展开）

[板块名]
[本板块过去12小时完整动态]
• [事件] — [一句话影响] · [来源] · [原文链接]
• [事件] — [同上]
重点标的：[股票名] [方向] / [股票名] [方向]
今日关注：[需跟踪的关键变量]

【今日关注】
• [时间] [事项]：[说明，预期影响]
• [时间] [事项]：[同上]
（重要数据发布、财报、政策窗口、重大会议等）

【市场情绪总览】
[整体多空格局、资金偏好、主要驱动因素、需要警惕的反转信号]

【风险雷达】
• [风险]：[详细说明，触发条件，影响范围]
```

### 3. 推送早报摘要（飞书 / Telegram，精简3条）

早报拆分为以下三条摘要消息分别推送，每条独立发送：

**第一条 — 隔夜要闻：**
```
📰 早报 · [YYYY-MM-DD] · 隔夜要闻

① [事件标题]
   影响：[一句话影响]
   来源：[媒体名称] · [时间]

② [事件标题]
   影响：[一句话影响]
   来源：[媒体名称] · [时间]
```

**第二条 — 板块动态：**
```
📰 早报 · [YYYY-MM-DD] · 板块动态

[板块名]
• [事件] — [一句话影响]
↑ [股票名]  ↓ [股票名]  → [股票名]

[板块名]
• [事件] — [一句话影响]
↑ [股票名]
```

**第三条 — 今日关注：**
```
📰 早报 · [YYYY-MM-DD] · 今日关注

• [时间] [事项]：[说明]
• [时间] [事项]：[说明]

[市场情绪总览，2-3句]

⚠️ 风险：[风险点，一句话]

📎 详细版 PDF 已生成，路径：~/.openclaw/workspace/reports/[DATE]-morning.pdf
如需发送请运行 /发送早报PDF
```

规则：
- 三条消息按顺序连续发送
- 不使用表格，改用简洁列表
- 不使用 `━━━━` 分隔符，段落之间用空行分隔
- 每条消息字符数超过 4000（飞书）/ 4096（Telegram）时，按空行边界拆分成多条连续发送
- 来源只写媒体名称和时间，不附原文链接

飞书和 Telegram 同步推送，未配置的端静默跳过。

**推送飞书（FEISHU_MORNING_WEBHOOK 已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "$FEISHU_MORNING_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"interactive","card":{"header":{"title":{"tag":"plain_text","content":"📰 早报 · [日期] · [板块标题]"},"template":"blue"},"elements":[{"tag":"div","text":{"tag":"lark_md","content":"[单条消息内容，≤4000字符]"}}]}}'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_MORNING_CHAT_ID 均已配置时）：**

对每条待发消息执行：
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"'"$TELEGRAM_MORNING_CHAT_ID"'","parse_mode":"Markdown","disable_web_page_preview":true,"text":"[单条消息内容，≤4096字符]"}'
```

---

### 4. 生成详细早报 PDF

摘要推送完成后，生成包含完整内容的 PDF 文件供用户查阅。

**PDF 内容结构（与步骤2对话窗口完整版相同）：**
- 封面：金融情报早报 · YYYY-MM-DD
- 隔夜要闻（每条含完整描述、影响分析、原文链接）
- 板块动态（每个板块展开，含重点标的）
- 今日关注（含时间、事项、预期影响）
- 市场情绪总览
- 风险雷达

**生成步骤：**

1. 将完整早报内容写入临时 Markdown 文件：
```bash
cat > /tmp/morning-report-[YYYY-MM-DD].md << 'EOF'
[完整早报内容，UTF-8编码]
EOF
```

2. 使用当前环境中可用的工具将 Markdown 转为 PDF，**按以下优先级尝试**，成功即停止：

**优先级1 — WeasyPrint（推荐，中文支持最佳）：**
```bash
python3 -c "
from weasyprint import HTML, CSS
import tempfile, os

md_content = open('/tmp/morning-report-[YYYY-MM-DD].md', encoding='utf-8').read()
html = '''<!DOCTYPE html>
<html><head><meta charset=\"utf-8\">
<style>
  body { font-family: \"PingFang SC\", \"Noto Sans CJK SC\", \"Microsoft YaHei\", sans-serif;
         font-size: 14px; line-height: 1.8; padding: 40px; color: #1a1a1a; }
  h1 { font-size: 22px; color: #0052cc; border-bottom: 2px solid #0052cc; padding-bottom: 8px; }
  h2 { font-size: 16px; color: #333; margin-top: 24px; }
  p  { margin: 8px 0; }
  a  { color: #0052cc; }
</style></head><body>''' + md_content.replace('\n', '<br>') + '</body></html>'
HTML(string=html).write_pdf('/tmp/morning-report-[YYYY-MM-DD].pdf')
print('OK')
"
```

**优先级2 — pandoc（需系统已安装）：**
```bash
pandoc /tmp/morning-report-[YYYY-MM-DD].md \
  -o /tmp/morning-report-[YYYY-MM-DD].pdf \
  --pdf-engine=xelatex \
  -V mainfont="PingFang SC" \
  -V CJKmainfont="PingFang SC" \
  -V geometry:margin=2cm \
  --from markdown
```

**优先级3 — Python reportlab（纯代码，无外部依赖）：**
```bash
python3 -c "
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import textwrap

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
content = open('/tmp/morning-report-[YYYY-MM-DD].md', encoding='utf-8').read()
c = canvas.Canvas('/tmp/morning-report-[YYYY-MM-DD].pdf', pagesize=A4)
c.setFont('STSong-Light', 12)
y = 780
for line in content.split('\n'):
    for wrapped in textwrap.wrap(line, 60) or ['']:
        if y < 60:
            c.showPage()
            c.setFont('STSong-Light', 12)
            y = 780
        c.drawString(40, y, wrapped)
        y -= 20
c.save()
print('OK')
"
```

**优先级4 — 降级处理（三种方式均不可用时）：**
- 将完整早报内容存为 UTF-8 编码的 `.txt` 文件
- 告知用户 PDF 生成工具未安装，已保存为文本文件，并说明如何安装 WeasyPrint：`pip install weasyprint`

3. PDF 生成成功后：
   - 将文件复制到 `~/.openclaw/workspace/reports/[YYYY-MM-DD]-morning.pdf`
   - 删除 `/tmp/` 下的临时文件
   - **仅通过 Telegram 自动发送文件**（TELEGRAM_BOT_TOKEN 和 TELEGRAM_MORNING_CHAT_ID 均已配置时）：
     ```bash
     curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendDocument" \
       -F chat_id="$TELEGRAM_MORNING_CHAT_ID" \
       -F document=@"$PDF_PATH" \
       -F caption="📰 早报详细版 · [YYYY-MM-DD]"
     ```
   - **飞书不自动发送文件**（飞书 webhook 不支持文件消息）：在第三条摘要消息末尾附加以下说明（替换原有的 `📎 详细版 PDF 已生成` 行）：
     ```
     📎 详细版 PDF 已生成，路径：~/.openclaw/workspace/reports/[DATE]-morning.pdf
     如需发送请运行 /发送早报PDF
     ```
   - 在对话中告知用户：`📄 早报 PDF 已生成：~/.openclaw/workspace/reports/[YYYY-MM-DD]-morning.pdf`（Telegram 已自动发送；飞书需手动运行 /发送早报PDF）

**防乱码要点（所有方式均须遵守）：**
- 所有文本操作明确指定 `encoding='utf-8'`
- 字体优先级：PingFang SC → Noto Sans CJK SC → Microsoft YaHei → STSong-Light
- 不使用系统默认编码（不依赖 locale）

### 5. 输出运行成本（早报）

同板块快报，读取 `model.summarize` 相关配置后输出，格式相同，标题改为"早报"。

---

## 注意事项
- 原文链接从新闻条目的 `url` 字段读取；无链接时标注"（无原文链接）"
- FEISHU_SECTOR_WEBHOOK、FEISHU_MORNING_WEBHOOK、TELEGRAM_BOT_TOKEN、TELEGRAM_SECTOR_CHAT_ID、TELEGRAM_MORNING_CHAT_ID 均从环境变量读取
- 两端推送相互独立，任意端未配置则静默跳过
- 同一板块2小时内只推送一次，避免刷屏
- 推送消息（飞书/Telegram）始终使用精简格式，去掉表格和分隔符
- Agent 对话窗口始终输出完整详细版；用户明确说"简报"时对话窗口也可输出精简格式
