---
name: monitor
description: 脚本扫描预警关键词，命中时 LLM 格式化后推送飞书即时预警频道
---

# Monitor Skill

## 触发方式
- Heartbeat 自动触发（filter-news 有新增条目时）
- 静默期（00:00-06:00）仍运行，扫描已有缓存中尚未推送的条目

## 执行步骤

### 第一步：脚本规则扫描（无 LLM，零成本）

```bash
bash ~/.openclaw/skills/FEISHU_NEWS/scripts/monitor-scan.sh
```

脚本输出格式：每条命中为一行 `HIT {json}`，无命中则无输出。

**无输出时**：回复 `HEARTBEAT_OK`，结束，不调用 LLM。

---

### 第二步：LLM 格式化 + 推送（仅在有命中时执行）

读取飞书 Webhook：
```bash
openclaw config get skills.entries.feishu_news.env.FEISHU_ALERT_WEBHOOK
```

对每条命中的新闻，生成以下格式的飞书消息并推送：

```
━━━━━━━━━━━━━━━━━━━
🚨 [预警级别] | [板块/个股]
━━━━━━━━━━━━━━━━━━━
[标题]

📍 [来源] · [HH:MM]
🔗 [原文链接]
```

预警级别判断：
- 命中破产/违约/退市/ST/暴雷 → **重大预警**
- 命中监管处罚/证监会/大股东减持/财报造假 → **风险预警**
- 命中涨停/跌停 → **市场预警**

用 web 工具 POST 到 FEISHU_ALERT_WEBHOOK。

同步推 Telegram（未配置则静默跳过）：
```bash
openclaw config get skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN
openclaw config get skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID
```

---

### 第三步：更新推送状态

将已推送的 id 追加到 monitor-state.json 的 `pushed_ids`（保留最近500条）：
```bash
echo '<updated_json>' > ~/.openclaw/workspace/monitor-state.json.tmp
mv ~/.openclaw/workspace/monitor-state.json.tmp ~/.openclaw/workspace/monitor-state.json
```

### 记录成本（仅在调用 LLM 格式化时记录）

```bash
ENTRY=$(jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg skill "monitor" \
  --argjson in_tokens <实际或估算输入tokens> \
  --argjson out_tokens <实际或估算输出tokens> \
  --argjson alerts <本次推送预警条数> \
  '{ts: $ts, skill: $skill, in_tokens: $in_tokens, out_tokens: $out_tokens, alerts: $alerts}')

jq --argjson e "$ENTRY" '. + [$e] | .[-500:]' \
  ~/.openclaw/workspace/cost-log.json > ~/.openclaw/workspace/cost-log.json.tmp
mv ~/.openclaw/workspace/cost-log.json.tmp ~/.openclaw/workspace/cost-log.json
```

### 输出
**心跳模式下不输出任何内容到对话**，只推送飞书消息，完成后心跳回复 `HEARTBEAT_OK`。
手动触发时可输出简洁结果：扫描N条，命中M条，推送状态。
