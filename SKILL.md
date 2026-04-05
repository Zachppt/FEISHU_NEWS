---
name: fetch-news
description: 从 Bloomberg、Reuters、新浪财经、X 等数据源抓取财经新闻，去重后写入本地缓存
---

# Fetch News Skill

## 触发方式
- Heartbeat 自动触发（每2分钟）
- 用户发送"抓取新闻"或"fetch news"手动触发

## 执行步骤

### 1. 读取监控配置
用 exec 工具执行：
```bash
cat ~/workspace/watchlist.json
```
获取关注的板块列表和个股列表，用于后续过滤。

### 2. 抓取 RSS 数据源
用 web 工具依次抓取以下 RSS：
- https://feeds.bloomberg.com/markets/news.rss
- https://cn.reuters.com/rssFeed/CNTopNews
- https://rss.sina.com.cn/news/fin/stock.xml
- https://wallstreetcn.com/feed

每条新闻提取：标题、摘要（前200字）、来源、发布时间、链接。

### 3. 去重处理
用 exec 工具读取去重缓存：
```bash
cat ~/workspace/news-cache.json
```
对每条新闻用标题前50字做去重判断，跳过已存在的条目。

### 4. 写入缓存
将新条目追加到原始新闻文件（保留最新300条）：
```bash
# 读取现有数据，合并新条目，截断到300条，写回文件
cat ~/workspace/raw-news.json
```
用 exec 工具写入更新后的 JSON：
```bash
echo '<updated_json>' > ~/workspace/raw-news.json
```

更新去重哈希缓存（只保留24小时内的哈希）：
```bash
echo '<updated_cache_json>' > ~/workspace/news-cache.json
```

### 5. 完成报告
输出采集统计：
- 本次新增条数
- 跳过重复条数
- 当前缓存总量

不推送飞书，等待 filter-news skill 处理。

## 注意事项
- 如果某个 RSS 源请求失败，跳过该源继续处理其他源，不中断整个流程
- 网络超时设置为 10 秒
- raw-news.json 格式：`[{"title":"...", "body":"...", "source":"...", "url":"...", "ts":"..."}]`
