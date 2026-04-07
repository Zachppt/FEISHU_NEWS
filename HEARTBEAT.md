# 金融情报系统 · 心跳任务

每次心跳按顺序执行以下三个脚本：

1. `python3 ~/.openclaw/skills/FEISHU_NEWS/fetch_news.py`
2. `python3 ~/.openclaw/skills/FEISHU_NEWS/filter_news.py`
3. `python3 ~/.openclaw/skills/FEISHU_NEWS/monitor.py`

## 规则
- 脚本静默成功；输出错误行时记录，不中断后续脚本
- 执行完成后静默结束，不输出任何内容
- 心跳执行时间上限为 120 秒（脚本执行，无 LLM 调用）

## 静默时间
00:00 - 06:00 只运行 monitor.py，跳过 fetch 和 filter。
