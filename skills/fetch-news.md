---
name: fetch-news
description: 从配置的数据源抓取财经新闻，去重后写入本地缓存
---

# Fetch News Skill

## 触发方式
- Heartbeat 自动触发（每2分钟）
- 用户发送「抓取新闻」手动触发

## 执行步骤

### 1. 读取数据源配置
```bash
cat ~/.openclaw/workspace/sources.json
```
取出所有 `enabled: true` 的条目，分为 rss / api / browser 三类分别处理。

### 2. 抓取 RSS 源
对 sources.json 中 `rss` 列表里每个 `enabled: true` 的条目，用 web 工具抓取：
- 提取：标题、摘要（前200字）、来源、发布时间、链接
- 单个源失败时跳过，继续处理其他源，不中断整体流程
- 网络超时：10秒

### 3. 抓取 API 源
对 sources.json 中 `api` 列表里每个 `enabled: true` 的条目：
```bash
# 读取对应 API Key
openclaw config get skills.entries.feishu_news.env.<key_ref>
```
按各 API 文档格式请求，提取标题、摘要、时间、链接。

### 4. 抓取 Browser 源（需要登录或 JS 渲染）
对 sources.json 中 `browser` 列表里每个 `enabled: true` 的条目：
```bash
agent-browser open <url>
agent-browser snapshot
```
从快照中提取新闻条目。若该源标记 `requires_auth: true` 但 session 不存在，跳过并记录警告。

### 5. 去重处理
```bash
cat ~/.openclaw/workspace/news-cache.json
```
对每条新闻用标题前50字做哈希去重，跳过已存在条目。

### 6. 写入缓存
将新条目追加到 raw-news.json（保留最新300条）：
```bash
# 原子写入：先写临时文件，再替换
echo '<updated_json>' > ~/.openclaw/workspace/raw-news.json.tmp
mv ~/.openclaw/workspace/raw-news.json.tmp ~/.openclaw/workspace/raw-news.json
```
更新去重缓存（只保留24小时内哈希）：
```bash
echo '<updated_cache>' > ~/.openclaw/workspace/news-cache.json.tmp
mv ~/.openclaw/workspace/news-cache.json.tmp ~/.openclaw/workspace/news-cache.json
```

### 7. 输出统计
- 本次新增条数
- 跳过重复条数
- 失败的数据源（如有）
- 当前缓存总量

不推送飞书，等待 filter-news skill 处理。
