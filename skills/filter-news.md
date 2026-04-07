---
name: filter-news
description: 过滤 raw-news.json，保留与监控名单相关的有效新闻，写入 filtered-news.json
---

# Filter News Skill

## 触发方式
- Heartbeat 自动触发（fetch-news 完成且有新增条目时）
- 用户发送「过滤新闻」手动触发

## 执行步骤

### 1. 读取数据（只读标题，不读摘要）

```bash
# 只提取 id + title + source + ts + url，不加载无关字段
jq '[.[] | {id, title, source, ts, url}]' ~/.openclaw/workspace/raw-news.json

# 读取监控名单
cat ~/.openclaw/workspace/watchlist.json

# 读取已过滤新闻的 id 列表（仅用于去重，不读全文）
jq '[.[] | .id]' ~/.openclaw/workspace/filtered-news.json
```

### 2. 过滤规则

对每条新闻的 **标题** 做关键词匹配（不需要读正文）：

**命中条件（保留）：**
- 标题包含 watchlist.stocks 中任意个股名称
- 标题包含 watchlist.sectors 中任意板块名称
- 标题包含 watchlist.keywords 中任意关键词
- 标题包含宏观词：GDP、CPI、PPI、非农、美联储、降息、加息

**丢弃条件：**
- 标题少于8字
- id 已在 filtered-news.json 的 id 列表中（链接去重）

### 3. 写入结果

将命中条目追加到 filtered-news.json（**保留最新 200 条**），原子写入：
```bash
echo '<updated_json>' > ~/.openclaw/workspace/filtered-news.json.tmp
mv ~/.openclaw/workspace/filtered-news.json.tmp ~/.openclaw/workspace/filtered-news.json
```

### 4. 输出统计
- 本次命中条数（**心跳依赖此数字决定是否运行 monitor**）
- 丢弃条数
