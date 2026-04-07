---
name: filter-news
description: 两阶段过滤：脚本宽泛初筛 + LLM 精筛，保留与监控名单相关的新闻
---

# Filter News Skill

## 触发方式
- Heartbeat 自动触发（fetch-news 有新增条目时）
- 用户发送「过滤新闻」手动触发

## 执行步骤

### 第一阶段：脚本宽泛初筛（无 LLM，零成本）

```bash
bash ~/.openclaw/skills/FEISHU_NEWS/scripts/prefilter.sh
```

脚本输出候选新闻的 JSON 数组，每条只含 `{id, title, source, ts, url}`。

**候选数为 0 时**：输出 `HEARTBEAT_OK`，结束，不进入第二阶段。

---

### 第二阶段：LLM 精筛（只看标题，去掉明显无关条目）

读取当前监控名单：
```bash
cat ~/.openclaw/workspace/watchlist.json
```

将以下内容发给 LLM（**极短 prompt**）：

---
监控对象：
- 个股：{watchlist.stocks 列表}
- 板块：{watchlist.sectors 列表}
- 关键词：{watchlist.keywords 列表}

以下是关键词初筛后的候选标题，请去掉**明显**与以上监控对象无关的条目，边缘相关的保留。
只输出需要保留的 id 列表，JSON 数组格式，不要解释。

候选：
{候选 JSON 数组}
---

**LLM 输出示例**：
```json
["abc123", "def456", "ghi789"]
```

---

### 写入结果

根据 LLM 返回的 id 列表，从候选 JSON 中取出对应条目，追加到 filtered-news.json（保留最新200条），原子写入：
```bash
echo '<updated_json>' > ~/.openclaw/workspace/filtered-news.json.tmp
mv ~/.openclaw/workspace/filtered-news.json.tmp ~/.openclaw/workspace/filtered-news.json
```

### 输出
- 第一阶段初筛命中数
- 第二阶段精筛后保留数
- 最终写入 filtered-news.json 的条数（心跳用此判断是否运行 monitor）
