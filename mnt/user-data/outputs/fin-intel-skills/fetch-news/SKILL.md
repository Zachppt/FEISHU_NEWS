---
name: fetch-news
description: 用 Agent Browser 抓取 sources.json 中 browser 类型的新闻源，结果追加写入 raw-news.json
---

# Fetch-News Browser Skill

## 触发方式
- Cron job 每 30 分钟触发（isolated session）
- 用户手动发送"抓取新闻"时触发

---

## 执行步骤

### 1. 读取配置
```bash
cat ~/.openclaw/skills/FEISHU_NEWS/sources.json
cat ~/.openclaw/workspace/raw-news.json
cat ~/.openclaw/workspace/news-cache.json
```

从 `sources.json` 中取出 `browser` 数组，只处理 `enabled: true` 的源。

`news-cache.json` 是已处理文章的 MD5 hash 表（key = hash，value = ISO 时间戳），用于去重。

---

### 2. 逐源抓取

对每个 browser 源，用 WebFetch 或 Agent Browser 工具访问 URL，从页面中提取文章列表。

每篇文章提取以下字段：
- `title`：文章标题（必须，空则跳过）
- `url`：原文链接（必须，空则跳过）
- `summary`：摘要或正文前 150 字（没有则留空字符串）
- `ts`：发布时间，转为 ISO8601 UTC 格式（`YYYY-MM-DDTHH:MM:SSZ`）；无时间则用当前时间

---

#### 财联社电报（`https://www.cls.cn/telegraph`）

页面结构：每条电报包含时间戳和内容文本。

提取规则：
- `title`：每条电报正文前 60 字，去除末尾标点
- `url`：`https://www.cls.cn/telegraph`（电报无独立链接，用页面 URL + 内容 hash 区分）
- `summary`：电报完整正文
- `ts`：电报时间戳（页面显示 HH:MM，结合当前日期补全）

---

#### 第一财经（`https://www.yicai.com/news/`）

提取规则：
- `title`：文章标题
- `url`：文章链接（补全 `https://www.yicai.com` 前缀）
- `summary`：文章摘要
- `ts`：发布时间

---

#### Reuters 中文（`https://cn.reuters.com/news/archive/CNTopNews`）

提取规则：
- `title`：新闻标题
- `url`：完整链接
- `summary`：导语
- `ts`：发布时间

---

### 3. 去重 & 写入

对每篇提取到的文章：
1. 计算 `hash = MD5(title[:50])`（十六进制字符串）
2. 如果 hash 已在 `news-cache.json` 中，跳过
3. 否则构造条目：
```json
{
  "hash": "<md5>",
  "title": "<title>",
  "summary": "<summary>",
  "url": "<url>",
  "source": "<sources.json 中的 name 字段>",
  "ts": "<ISO8601 UTC>"
}
```

收集所有新条目后，**原子写入** `raw-news.json`：

```bash
# 将新条目追加到现有 raw-news.json 头部，合并后最多保留 300 条
python3 -c "
import json, os, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKSPACE = Path.home() / '.openclaw/workspace'
raw_file = WORKSPACE / 'raw-news.json'
cache_file = WORKSPACE / 'news-cache.json'

new_items = <新条目列表 JSON>

raw = json.loads(raw_file.read_text(encoding='utf-8')) if raw_file.exists() else []
cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}

combined = new_items + raw
combined = combined[:300]

tmp = raw_file.with_suffix('.tmp')
tmp.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8')
os.replace(tmp, raw_file)

# 更新 cache，清理 24h 前条目
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)
for item in new_items:
    cache[item['hash']] = item['ts']
pruned = {h: t for h, t in cache.items()
          if datetime.fromisoformat(t.replace('Z','+00:00')) > cutoff}
tmp2 = cache_file.with_suffix('.tmp')
tmp2.write_text(json.dumps(pruned, ensure_ascii=False, indent=2), encoding='utf-8')
os.replace(tmp2, cache_file)

print(f'[fetch-news-browser] 写入 {len(new_items)} 条新闻')
"
```

---

### 4. 输出规则
- 成功且有新条目：输出 `[fetch-news-browser] 写入 N 条：财联社 X 条 / 第一财经 Y 条 / ...`
- 成功但无新条目：**静默，不输出任何内容**
- 某源抓取失败：输出 `[fetch-news-browser] 源失败: <name> <错误>`，继续处理其他源

---

## 注意事项
- 每个 browser 源独立抓取，任意一源失败不影响其他源
- 财联社电报无独立 URL，用 `https://www.cls.cn/telegraph#<hash[:8]>` 作为唯一标识 URL
- 时区统一转为 UTC，中国时间（CST = UTC+8）需减 8 小时
- 不向飞书/Telegram 推送，仅写入 raw-news.json 供后续 filter_news.py 处理
