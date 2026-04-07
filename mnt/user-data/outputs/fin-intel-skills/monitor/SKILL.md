---
name: monitor
description: 监控 watchlist 中的个股和关键词，命中时立即推送飞书和 Telegram 即时预警频道，支持用户管理监控名单
---

# Monitor Skill

## 触发方式
- Heartbeat 每次运行时自动检查
- Webhook 收到数据源推送时立即触发
- 用户发送"/add 名称"、"/remove 名称"、"/list"管理监控名单

## 预警检测模式（Heartbeat 触发）

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/filtered-news.json
cat ~/.openclaw/workspace/monitor-state.json
```
monitor-state.json 记录上次检查的时间戳，只处理新增条目。

### 2. 关键词匹配
对每条新条目，检查是否命中 watchlist.json 中的：
- stocks：个股名称列表
- sectors：板块关键词列表
- keywords：特别关注关键词列表（如"暴雷"、"退市"、"美联储"）

### 3. 计算预警等级
- 高（red）：命中 keywords 中的关键词，或同时命中3个以上标的
- 中（orange）：命中 stocks 中的个股
- 低（blue）：仅命中 sectors 板块关键词

### 4. 推送即时预警
命中时立即推送，不等下一个心跳。飞书和 Telegram 同步推送，未配置的端静默跳过。

等级 emoji：🚨 高 / ⚡ 中 / 📌 低

**推送飞书（FEISHU_ALERT_WEBHOOK 已配置时）：**
```bash
curl -s -X POST "$FEISHU_ALERT_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "interactive",
    "card": {
      "header": {
        "title": {"tag": "plain_text", "content": "[等级emoji] [命中标的] 相关消息"},
        "template": "[red/orange/blue]"
      },
      "elements": [
        {"tag": "div", "text": {"tag": "lark_md", "content": "**来源：**[source]　**时间：**[time]\n\n[摘要，100字以内]"}},
        {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "查看原文"}, "type": "default", "url": "[url]"}]}
      ]
    }
  }'
```

**推送 Telegram（TELEGRAM_BOT_TOKEN 和 TELEGRAM_ALERT_CHAT_ID 均已配置时）：**
```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "'"$TELEGRAM_ALERT_CHAT_ID"'",
    "parse_mode": "Markdown",
    "text": "[等级emoji] *[命中标的] 相关消息*\n来源：[source]　时间：[time]\n\n[摘要，100字以内]\n\n[查看原文]([url])"
  }'
```

### 5. 更新检查状态
将本次命中的新闻 URL 列表合并到 pushed_ids（只保留最近24小时内的），防止重启后重复推送：
```bash
echo '{"last_check": "[时间戳]", "pushed_ids": ["[url1]", "[url2]", ...]}' > ~/.openclaw/workspace/monitor-state.json.tmp && mv ~/.openclaw/workspace/monitor-state.json.tmp ~/.openclaw/workspace/monitor-state.json
```

### 6. 输出规则
**无命中时：完全静默，不输出任何内容。**
有命中预警时：仅输出一行 `[monitor] 预警: <标题前20字>`。
推送失败时：输出 `[monitor] 推送失败: <HTTP状态码>`。
任何情况下都不打印扫描条数、统计信息或 HEARTBEAT_OK。

## 用户指令模式

### /add [名称] [类型?]

**步骤 1：写入 watchlist.json**

读取并更新 watchlist.json，判断归属列表：
- 用户明确说"板块"或输入已知板块词 → 加入 sectors
- 纯中文股票名（2-4字）或英文股票代码 → 加入 stocks
- 其他关键词 → 加入 keywords

原子写入：
```bash
cat ~/.openclaw/workspace/watchlist.json
echo '<updated_watchlist>' > ~/.openclaw/workspace/watchlist.json.tmp && mv ~/.openclaw/workspace/watchlist.json.tmp ~/.openclaw/workspace/watchlist.json
```

**步骤 2：更新 aliases.json（仅当加入 stocks 时）**

对新加入 stocks 的名称，尝试用 AKShare 查询别名，补充到 aliases.json：

```python
import subprocess, json
from pathlib import Path

ALIASES_FILE = Path("~/.openclaw/skills/FEISHU_NEWS/aliases.json").expanduser()
name = "[用户输入的股票名]"

aliases = json.loads(ALIASES_FILE.read_text(encoding="utf-8")) if ALIASES_FILE.exists() else {}

# 已有别名则跳过
if name not in aliases:
    try:
        import akshare as ak
        # 查 A 股代码和全称
        df = ak.stock_info_a_code_name()
        match = df[df["name"] == name]
        if not match.empty:
            code = match.iloc[0]["code"]          # 如 "002142"
            full_name = match.iloc[0]["name"]
            aliases[name] = [full_name, code, f"{code}.SZ" if code.startswith("0") or code.startswith("3") else f"{code}.SH"]
        else:
            # 查港股
            df_hk = ak.stock_hk_spot_em()
            match_hk = df_hk[df_hk["名称"] == name]
            if not match_hk.empty:
                hk_code = str(match_hk.iloc[0]["代码"]).zfill(4)
                aliases[name] = [name, hk_code, f"{hk_code}.HK"]
            else:
                # 查不到时写入空别名占位，后续可手动补充
                aliases[name] = [name]
    except ImportError:
        aliases[name] = [name]  # AKShare 未安装，仅保留原名
    except Exception:
        aliases[name] = [name]  # 查询失败，静默降级

    tmp = ALIASES_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(ALIASES_FILE)
```

**步骤 3：回复用户**

- 成功找到代码：回复"已添加 **宁波银行**（002142）到监控名单，同时更新别名表"
- 未找到代码：回复"已添加 **XXX** 到监控名单（未找到股票代码，仅匹配中文名）"
- 加入 sectors/keywords：回复"已添加 **XXX** 到[板块/关键词]监控"

### /remove [名称]
1. 读取 watchlist.json
2. 从所有列表中删除该名称
3. 原子写回文件
4. 回复"已移除 [名称]"

### /list
1. 读取 watchlist.json
2. 格式化输出：
```
📋 当前监控名单

个股（N只）：腾讯 / 比亚迪 / 宁德时代 / ...
板块（N个）：新能源 / 半导体 / AI / ...
关键词（N个）：美联储 / 暴雷 / 退市 / ...
```

---

## 数据源管理指令

### /add-source [URL] [名称?]

自动检测 URL 类型并添加到 sources.json。

执行：
```bash
python3 ~/.openclaw/skills/FEISHU_NEWS/manage_sources.py add "[URL]" "[名称]"
```

类型检测优先级：
1. 能解析为 RSS/Atom XML → 加入 `rss` 数组
2. 能解析为已知 JSON API 格式 → 加入 `api` 数组，填入对应 `api_type`
3. 返回未知 JSON → 加入 `api` 数组，`api_type=custom`，提示需要自定义解析器
4. 其他（HTML、需JS渲染、访问被拦截）→ 加入 `browser` 数组

回复格式：
```
✅ 已添加 RSS 源：[名称]
   抓取样本（前3条）：
   · [标题1]
   · [标题2]
   · [标题3]
```
或：
```
❌ 访问失败：HTTP 403
```
或：
```
✅ 已添加 Browser 源：[名称]（需 Agent Browser 渲染）
```

### /remove-source [名称]

从 sources.json 中删除对应名称的数据源。

执行：
```bash
python3 ~/.openclaw/skills/FEISHU_NEWS/manage_sources.py remove "[名称]"
```

回复：`✅ 已移除：[名称]` 或 `❌ 未找到名称「[名称]」`

### /list-sources

列出所有已配置数据源及状态。

执行：
```bash
python3 ~/.openclaw/skills/FEISHU_NEWS/manage_sources.py list
```

回复格式：
```
📡 当前数据源（共 N 个）

【RSS】
  ✓ Bloomberg Markets
    https://feeds.bloomberg.com/markets/news.rss

【JSON API】
  ✓ 华尔街见闻快讯  api_type=wallstreetcn
    https://api-one-wscn.awtmt.com/...

【Browser】
  ✓ 财联社电报  [需 Agent Browser 渲染]
    https://www.cls.cn/telegraph
```

## 注意事项
- FEISHU_ALERT_WEBHOOK 从 `skills.entries.monitor.env.FEISHU_ALERT_WEBHOOK` 读取
- TELEGRAM_BOT_TOKEN 从 `skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN` 读取
- TELEGRAM_ALERT_CHAT_ID 从 `skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID` 读取
- 两端推送相互独立：飞书推送失败不影响 Telegram，反之亦然
- 任意端未配置（空值或 null）则静默跳过，不报错
- 同一条新闻对同一标的只推送一次：推送前检查 url 是否已在 pushed_ids 中，推送后将 url 写入 pushed_ids
- pushed_ids 只保留最近24小时内的条目，防止无限增长
- monitor-state.json 不存在时，只处理最近1小时的新闻（避免首次运行刷屏）
- watchlist.json 格式：
  `{"stocks": [], "sectors": [], "keywords": []}`
