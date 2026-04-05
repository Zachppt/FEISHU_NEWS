---
name: sentiment
description: 对过滤后的新闻按板块做情绪分析，评分 -100 到 +100，推送飞书情绪日报频道
---

# Sentiment Skill

## 触发方式
- Cron job 每15分钟触发（isolated session）
- 用户发送"/sentiment 板块名"查询特定板块

## 执行步骤（定时触发模式）

### 1. 读取最近数据
用 exec 工具读取：
```bash
cat ~/workspace/filtered-news.json
cat ~/workspace/watchlist.json
cat ~/workspace/sentiment-snapshot.json
```
只处理最近15分钟内的新条目（通过 filtered_at 字段判断）。

### 2. 按板块分组分析
对每个有新内容的板块，综合分析所有相关新闻：

情绪评分标准：
- +80 ~ +100：极度乐观，重大利好
- +40 ~ +80：偏多，利好消息为主
- -40 ~ +40：中性，多空交织
- -80 ~ -40：偏空，利空消息为主
- -100 ~ -80：极度悲观，重大利空

输出格式：
```
板块: [板块名]
情绪分: [分数]
看多: [理由1] / [理由2]
看空: [理由1] / [理由2]
热议: [话题1] / [话题2] / [话题3]
一句话总结: [...]
```

### 3. 更新快照文件
```bash
echo '<updated_sentiment_json>' > ~/workspace/sentiment-snapshot.json
```

### 4. 推送飞书情绪日报频道
用 exec 工具调用飞书 Webhook：
```bash
curl -s -X POST "$FEISHU_SENTIMENT_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "interactive",
    "card": {
      "header": {
        "title": {"tag": "plain_text", "content": "🧠 情绪快照 · [时间]"},
        "template": "purple"
      },
      "elements": [{
        "tag": "div",
        "text": {"tag": "lark_md", "content": "[情绪内容]"}
      }]
    }
  }'
```

## 用户查询模式（"/sentiment 板块名"）

1. 读取 ~/workspace/sentiment-snapshot.json
2. 找到对应板块的最新快照
3. 格式化后直接回复用户
4. 不推送飞书频道

## 注意事项
- 如果某板块15分钟内没有新内容，跳过该板块，不生成空快照
- FEISHU_SENTIMENT_WEBHOOK 从环境变量读取
- 情绪分数用整数，不要小数
