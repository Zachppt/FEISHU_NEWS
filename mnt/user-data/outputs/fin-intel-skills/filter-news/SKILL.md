---
name: filter-news
description: 读取原始新闻，先做规则预过滤，再用 AI 判断相关性，输出有效新闻到 filtered-news.json
---

# Filter News Skill

## 触发方式
- fetch-news 完成后自动触发
- 用户发送"过滤新闻"或"filter news"手动触发

## 执行步骤

### 1. 读取数据
用 exec 工具读取：
```bash
cat ~/workspace/raw-news.json
cat ~/workspace/watchlist.json
cat ~/workspace/filtered-news.json
```

### 2. 规则预过滤（不消耗 AI token）
直接丢弃包含以下词的条目：
- 广告、推广、赞助、软文
- 招聘、求职、内推
- 优惠券、折扣、限时、秒杀
- 加微信、私信我、博彩、赌博

同时丢弃：
- 标题少于10个字的条目
- 发布时间超过6小时的条目

### 3. AI 相关性判断
对通过规则过滤的条目，结合 watchlist.json 中的板块和个股列表，判断每条新闻：
- 是否与关注的板块或个股相关
- 相关性评分 1-10 分
- 新闻类别：宏观 / 行业 / 个股 / 情绪 / 数据

只保留评分 5 分及以上的条目。

### 4. 写入过滤结果
将通过过滤的新条目合并到 filtered-news.json（保留最新500条）：
```bash
echo '<updated_filtered_json>' > ~/workspace/filtered-news.json
```

每条记录增加字段：
- `ai_score`：相关性评分
- `ai_category`：新闻类别
- `filtered_at`：过滤时间戳

### 5. 完成报告
输出过滤统计：
- 原始条数 → 规则过滤后 → AI 过滤后
- 各类别分布

不推送飞书。

## 注意事项
- 批量处理时每批最多20条，避免 token 过多
- filtered-news.json 格式与 raw-news.json 相同，增加 ai_score、ai_category、filtered_at 字段
- 已存在于 filtered-news.json 中的条目跳过，不重复处理
