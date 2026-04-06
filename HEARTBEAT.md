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

00:00 - 06:00 跳过 fetch-news 和 filter-news，只运行 monitor。

monitor 在静默期检查的是已有 filtered-news.json 中尚未推送的条目（依赖 pushed_ids 去重），而非实时新内容。这可以捕捉到：凌晨前积压但未被监控命中的新闻、以及系统重启后需要补检的条目。不要期望静默期能收到全新新闻，早报由 08:00 Cron 统一汇总隔夜内容。
