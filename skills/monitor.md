---
name: monitor
description: 扫描 filtered-news.json，检测预警信号，命中时立即推送飞书即时预警频道
---

# Monitor Skill

## 触发方式
- Heartbeat 自动触发（filter-news 命中条数 > 0 时）
- 静默期（00:00-06:00）仍运行，但只扫描已有数据不抓新内容

## 执行步骤

### 1. 读取数据（只读最新 50 条）

```bash
# 只取最新50条，不全量加载
jq '.[-50:]' ~/.openclaw/workspace/filtered-news.json

cat ~/.openclaw/workspace/monitor-state.json
```

### 2. 预警规则

**重大事件（立即推送）：**
- 个股：暴雷、退市、ST、违约、破产、重大重组、并购、分拆上市
- 宏观：美联储利率决议、非农数据、重大政策出台
- 市场：单日涨跌超过 ±5% 的板块或个股

**风险预警（立即推送）：**
- 监管处罚、证监会问询
- 大股东减持公告
- 财报造假、审计问题

**一般信息（不单独推送，留给快报汇总）：**
- 普通公司公告
- 行业分析报告

### 3. 去重推送
读取 monitor-state.json 中的 `pushed_ids`，已推送的不重复推送。

### 4. 推送飞书

命中预警规则时，POST 到 FEISHU_ALERT_WEBHOOK：
```bash
openclaw config get skills.entries.feishu_news.env.FEISHU_ALERT_WEBHOOK
```

**消息格式：**
```
━━━━━━━━━━━━━━━━━━━
🚨 重大预警 | [板块/个股]
━━━━━━━━━━━━━━━━━━━
[标题]

📍 [来源] · [HH:MM]
🔗 [原文链接]
```

### 5. 同步推送 Telegram

```bash
openclaw config get skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN
openclaw config get skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID
```
未配置时静默跳过。

### 6. 更新状态
将已推送 id 追加到 monitor-state.json 的 `pushed_ids`（保留最近 500 条）。

### 7. 输出
- 本次扫描条数
- 命中预警条数（0条时输出 `HEARTBEAT_OK`）
- 推送成功/失败
