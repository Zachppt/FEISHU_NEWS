---
name: monitor
description: 监控 watchlist 中的个股和关键词，命中时立即推送飞书即时预警频道，支持用户管理监控名单
---

# Monitor Skill

## 触发方式
- Heartbeat 每次运行时自动检查
- Webhook 收到数据源推送时立即触发
- 用户发送"/add 名称"、"/remove 名称"、"/list"管理监控名单

## 预警检测模式（Heartbeat 触发）

### 1. 读取数据
```bash
cat ~/workspace/watchlist.json
cat ~/workspace/filtered-news.json
cat ~/workspace/monitor-state.json
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

### 4. 推送飞书即时预警频道
命中时立即推送，不等下一个心跳：
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

等级 emoji：🚨 高 / ⚡ 中 / 📌 低

### 5. 更新检查状态
```bash
echo '{"last_check": "[时间戳]"}' > ~/workspace/monitor-state.json
```

## 用户指令模式

### /add [名称]
1. 读取 watchlist.json
2. 判断是个股还是关键词（中文股票名加入 stocks，其他加入 keywords）
3. 写入更新后的 watchlist.json
4. 回复"已添加 [名称] 到监控名单"

```bash
cat ~/workspace/watchlist.json
echo '<updated_watchlist>' > ~/workspace/watchlist.json
```

### /remove [名称]
1. 读取 watchlist.json
2. 从所有列表中删除该名称
3. 写回文件
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

## 注意事项
- FEISHU_ALERT_WEBHOOK 从环境变量读取
- 同一条新闻对同一标的只推送一次，防止重复预警
- monitor-state.json 不存在时，只处理最近1小时的新闻（避免首次运行刷屏）
- watchlist.json 格式：
  `{"stocks": [], "sectors": [], "keywords": []}`
