---
name: fetch-news
description: 从配置的数据源抓取财经新闻，去重后写入本地缓存
---

# Fetch News Skill

## 触发方式
- Heartbeat 自动触发（每5分钟）
- 用户发送「抓取新闻」手动触发

## 执行步骤

### 1. 运行抓取脚本
```bash
python3 ~/.openclaw/skills/FEISHU_NEWS/scripts/fetch.py
```

脚本会自动处理：
- 读取 sources.json 中所有 `enabled: true` 的 RSS 源
- 解析 XML（兼容 RSS 2.0 / Atom，兼容 UTF-8 / GB2312 编码）
- 去重（标题前50字哈希），跳过已存在条目
- 每条新闻只保存 id / title / source / ts / url，不存摘要
- 写入 raw-news.json（保留最新100条），更新 news-cache.json

### 2. 读取输出
脚本输出格式：
```
NEW:N        ← 本次新增条数
SKIPPED:N    ← 跳过重复条数
FAILED:xxx   ← 失败数据源（可能没有这行）
```

### 3. 告知心跳结果
将 `NEW:N` 中的 N 报告给心跳流程，心跳据此决定是否继续运行 filter-news。

N = 0 时：直接回复 `HEARTBEAT_OK`，结束。
