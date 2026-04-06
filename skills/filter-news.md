---
name: filter-news
description: 过滤 raw-news.json，保留与监控名单相关的有效新闻，写入 filtered-news.json
---

# Filter News Skill

## 触发方式
- Heartbeat 自动触发（fetch-news 完成后）
- 用户发送「过滤新闻」手动触发

## 执行步骤

### 1. 读取数据
```bash
cat ~/.openclaw/workspace/raw-news.json
cat ~/.openclaw/workspace/watchlist.json
cat ~/.openclaw/workspace/filtered-news.json
```

### 2. 过滤规则
对 raw-news.json 中每条新闻，检查是否命中以下任一条件：

**命中条件（保留）：**
- 标题或摘要包含 watchlist.stocks 中任意个股名称
- 标题或摘要包含 watchlist.sectors 中任意板块名称
- 标题或摘要包含 watchlist.keywords 中任意关键词
- 涉及宏观经济数据（GDP、CPI、PPI、非农、美联储）

**过滤条件（丢弃）：**
- 标题少于10字（广告或无效条目）
- 纯娱乐、体育、生活类内容
- 已存在于 filtered-news.json 中（按链接去重）

### 3. 写入结果
将通过过滤的新闻追加到 filtered-news.json（保留最新500条），原子写入：
```bash
echo '<updated_json>' > ~/.openclaw/workspace/filtered-news.json.tmp
mv ~/.openclaw/workspace/filtered-news.json.tmp ~/.openclaw/workspace/filtered-news.json
```

### 4. 输出统计
- 本次过滤前条数
- 通过过滤条数
- 丢弃条数及原因分布
