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

### 第二阶段：精筛（由你自己直接判断，不调用任何外部 API）

**不要调用 Ollama、不要调用任何本地端点、不要调用任何外部 API。**
你就是 LLM，直接阅读候选标题，判断哪些与监控对象相关，输出保留的 id 列表即可。

读取监控名单：
```bash
cat ~/.openclaw/workspace/watchlist.json
```

根据 watchlist 中的个股、板块、关键词，检查每条候选标题：
- 明显相关 → 保留
- 边缘相关（可能有关）→ 保留
- 明显无关 → 丢弃

**直接在内部判断完成，输出一个 JSON 数组**（只含需要保留的 id）：
```json
["abc123", "def456", "ghi789"]
```

不要输出解释，不要输出打分，不要输出过程。

---

### 写入结果

根据 LLM 返回的 id 列表，从候选 JSON 中取出对应条目，追加到 filtered-news.json（保留最新200条），原子写入：
```bash
echo '<updated_json>' > ~/.openclaw/workspace/filtered-news.json.tmp
mv ~/.openclaw/workspace/filtered-news.json.tmp ~/.openclaw/workspace/filtered-news.json
```

### 记录成本

LLM 精筛完成后，将本次调用信息追加到 cost-log.json：
```bash
ENTRY=$(jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg skill "filter" \
  --argjson in_tokens <估算输入token数> \
  --argjson out_tokens <估算输出token数> \
  --argjson kept <保留条数> \
  '{ts: $ts, skill: $skill, in_tokens: $in_tokens, out_tokens: $out_tokens, kept: $kept}')

jq --argjson e "$ENTRY" '. + [$e] | .[-500:]' \
  ~/.openclaw/workspace/cost-log.json > ~/.openclaw/workspace/cost-log.json.tmp
mv ~/.openclaw/workspace/cost-log.json.tmp ~/.openclaw/workspace/cost-log.json
```

token 数从本次对话的实际用量中读取（OpenClaw 提供 `$OPENCLAW_LAST_IN_TOKENS` / `$OPENCLAW_LAST_OUT_TOKENS` 环境变量；若不可用则估算：输入按候选标题字符数 ÷ 2，输出按返回 id 列表长度 × 8）。

### 输出
**心跳模式下不输出任何内容**，只在内部完成写入，将最终保留条数传递给心跳流程。
手动触发时（用户发送「过滤新闻」）可输出简洁统计：初筛N条 → 精筛保留M条。
