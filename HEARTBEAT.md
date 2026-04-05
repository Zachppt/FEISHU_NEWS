# 金融情报系统 · 心跳任务

每次心跳按顺序执行以下检查：

## 任务列表

1. 运行 fetch-news skill，采集最新财经新闻
2. 运行 filter-news skill，过滤垃圾新闻
3. 运行 monitor skill，检查是否有预警命中

## 规则

- 如果没有新内容，回复 HEARTBEAT_OK，不推送飞书
- 如果 monitor 命中预警，立即推送飞书即时预警频道
- 不要主动推送板块汇总和情绪快照，这两个由 Cron job 负责
- 每次心跳执行时间控制在 60 秒以内

## 静默时间

00:00 - 06:00 跳过 fetch-news，只运行 monitor（检查隔夜重大消息）
