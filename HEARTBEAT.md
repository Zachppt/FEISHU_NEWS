# 金融情报系统 · 心跳任务

## ⚠️ 静默模式（最重要的规则）

心跳期间**禁止在对话中输出任何内容**，包括：
- 执行步骤描述（"Now let me..."、"正在运行..."）
- 脚本输出内容
- 统计表格
- 任何解释性文字

**唯一允许的对话输出**：
- 无事发生时：`HEARTBEAT_OK`
- 脚本报错时：一行错误摘要（例：`ERROR: fetch.py 失败 - 网络超时`）

推送到飞书的预警消息不受此限制，正常发送。

---

## 执行流程

### 第一步：抓取新闻
```bash
python3 ~/.openclaw/skills/FEISHU_NEWS/scripts/fetch.py
```
读取脚本输出中的 `NEW:N`，N 即本次新增条数。

**N = 0**：输出 `HEARTBEAT_OK`，结束。

**N > 0**：继续第二步。

---

### 第二步：过滤新闻
运行 filter-news skill。

**精筛后新增条数 = 0**：输出 `HEARTBEAT_OK`，结束。

**精筛后新增条数 > 0**：继续第三步。

---

### 第三步：预警扫描
```bash
bash ~/.openclaw/skills/FEISHU_NEWS/scripts/monitor-scan.sh
```

**无输出**：输出 `HEARTBEAT_OK`，结束。

**有 HIT 行**：运行 monitor skill，格式化后推送飞书，完成后输出 `HEARTBEAT_OK`。

---

## 静默时间

00:00–06:00 跳过前两步，只运行第三步的预警扫描。
