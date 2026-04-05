# 金融情报系统 · OpenClaw Skills

基于 OpenClaw 的量化基金金融情报自动化系统，运行在 AethirClaw VPS 上，通过飞书推送实时金融情报。

## 系统架构

```
数据源（Bloomberg / Reuters / 新浪财经 / X）
         ↓ Heartbeat 每2分钟触发
    fetch-news → filter-news → monitor → 飞书即时预警

         ↓ Cron 每15分钟
      sentiment → 飞书情绪日报

         ↓ Cron 每2小时
      summarize → 飞书板块监控

         ↓ Cron 每天08:00
      summarize（早报）→ 飞书早报频道
```

## 快速部署

在飞书里对 Claw 说：帮我执行：
```bash
cd ~/.openclaw/skills && git clone https://github.com/你的用户名/fin-intel-skills.git && bash ~/.openclaw/skills/fin-intel-skills/setup.sh
```

## 飞书指令

| 指令 | 效果 |
|------|------|
| `/add 小米` | 添加个股到监控 |
| `/remove 小米` | 从监控移除 |
| `/list` | 查看完整监控名单 |
| `/sentiment 新能源` | 查询板块最新情绪 |
| `抓取新闻` | 立即触发一次采集 |
| `生成汇总` | 立即生成板块快报 |
| `系统状态` | 查看 Cron 运行情况 |

## 更新

```bash
cd ~/.openclaw/skills/fin-intel-skills && git pull
```
