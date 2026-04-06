# FEISHU_NEWS · 金融情报系统

> 基于 **OpenClaw 框架**的 7×24 小时金融新闻监控 Agent。
> 自动抓取多数据源，按监控名单过滤，情绪分析后推送飞书。

---

## 一键安装

将以下链接发送给你的 OpenClaw Agent：

```
请帮我安装这个 skill：https://github.com/Zachppt/FEISHU_NEWS
```

Agent 会自动完成安装并引导你配置飞书 Webhook 和数据源 API Key。

---

## 手动安装

```bash
cd ~/.openclaw/skills
git clone https://github.com/Zachppt/FEISHU_NEWS
bash FEISHU_NEWS/setup.sh
```

---

## 数据源

| 数据源 | 类型 | 是否需要申请 |
|---|---|---|
| Bloomberg Markets | RSS | 免费 |
| Reuters 中文 | RSS | 免费 |
| 华尔街见闻 | RSS | 免费 |
| 新浪财经 | RSS | 免费 |
| 财联社 | RSS | 免费 |
| BlockBeats | API | 需申请 → [申请地址](https://www.theblockbeats.info/) |

添加更多数据源：发送 `/添加信息源 <URL>` 给 Agent，自动检测类型并接入。

---

## 推送频道

需要在飞书创建以下群并添加自定义机器人：

| 群用途 | 推送内容 | 频率 |
|---|---|---|
| 即时预警群 | 重大新闻实时推送 | 实时 |
| 情绪日报群 | 板块情绪快照 | 每15分钟 |
| 板块监控群 | 板块新闻快报 | 每2小时 |
| 早报群 | 完整早报 | 每天08:00 |

---

## 可用指令

```
/add 比亚迪          添加到监控名单
/remove 比亚迪       从监控名单移除
/list                查看完整监控名单
/sentiment 新能源    查询板块最新情绪
/添加信息源 <URL>    添加新数据源
/数据源列表          查看当前数据源状态
抓取新闻             立即触发一次采集
生成汇总             立即生成板块快报
系统状态             查看 Cron 运行情况
```

---

## 更新

**方式一：告诉 Agent**
```
更新系统
```
Agent 会自动拉取最新代码、重跑 setup.sh 检测新功能，并引导你配置新增的配置项。

**方式二：手动更新**
```bash
cd ~/.openclaw/skills/FEISHU_NEWS && git pull
bash ~/.openclaw/skills/FEISHU_NEWS/setup.sh
```

**安全性：** 更新不会影响任何已有数据和配置。
- 监控名单、历史新闻、情绪快照：完整保留
- 飞书/Telegram 配置、已有 Cron 任务：完整保留
- 新版本新增的配置项：setup.sh 自动检测，Agent 引导补全
