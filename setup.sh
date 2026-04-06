#!/bin/bash
# ═══════════════════════════════════════════════════
# 金融情报系统 · FEISHU_NEWS 部署脚本
#
# 使用方式：
#   首次部署：bash setup.sh
#   更新版本：cd ~/.openclaw/skills/FEISHU_NEWS && git pull
#
# 特性：
#   - 所有工作区文件只追加合并，不覆盖原有内容
#   - 已存在的配置自动跳过，不重复写入
#   - Cron job 已存在时跳过，不重复添加
#   - 重复运行安全，任何时候都可以再跑一次
# ═══════════════════════════════════════════════════

set -e

SKILLS_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE=~/.openclaw/workspace

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  金融情报系统 · 部署脚本"
echo "  Skills 目录: $SKILLS_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 工具检查 ──
check_tool() {
  if ! command -v "$1" &>/dev/null; then
    echo "  [!] 缺少工具 $1，尝试安装..."
    apt-get install -y -qq "$1" 2>/dev/null || \
    brew install "$1" 2>/dev/null || \
    { echo "  [!] 无法自动安装 $1，请手动安装后重试"; exit 1; }
  fi
}
check_tool jq
check_tool curl

# ════════════════════════════════════════
# 第一步：初始化工作区目录和数据文件
# ════════════════════════════════════════
echo ""
echo "[1/5] 初始化工作区..."
mkdir -p "$WORKSPACE"

init_if_missing() {
  local file="$1"
  local content="$2"
  if [ ! -f "$file" ]; then
    echo "$content" > "$file"
    echo "  ✓ 创建: $(basename $file)"
  else
    echo "  - 已存在，跳过: $(basename $file)"
  fi
}

init_if_missing "$WORKSPACE/raw-news.json"            "[]"
init_if_missing "$WORKSPACE/filtered-news.json"       "[]"
init_if_missing "$WORKSPACE/news-cache.json"          "{}"
init_if_missing "$WORKSPACE/sentiment-snapshot.json"  "{}"
init_if_missing "$WORKSPACE/monitor-state.json"       "{}"

# ════════════════════════════════════════
# 第二步：合并 HEARTBEAT.md
# ════════════════════════════════════════
echo ""
echo "[2/5] 配置 HEARTBEAT.md..."

HEARTBEAT_FILE="$WORKSPACE/HEARTBEAT.md"
HEARTBEAT_MARKER="## 金融情报任务"

if [ ! -f "$HEARTBEAT_FILE" ]; then
  cp "$SKILLS_DIR/HEARTBEAT.md" "$HEARTBEAT_FILE"
  echo "  ✓ HEARTBEAT.md 已创建"
elif grep -q "$HEARTBEAT_MARKER" "$HEARTBEAT_FILE" 2>/dev/null; then
  echo "  - 已包含金融情报任务，跳过"
else
  echo "" >> "$HEARTBEAT_FILE"
  echo "---" >> "$HEARTBEAT_FILE"
  cat "$SKILLS_DIR/HEARTBEAT.md" >> "$HEARTBEAT_FILE"
  echo "  ✓ 已追加金融情报任务到现有 HEARTBEAT.md"
fi

# ════════════════════════════════════════
# 第三步：合并 AGENTS.md
# ════════════════════════════════════════
echo ""
echo "[3/5] 配置 AGENTS.md..."

AGENTS_FILE="$WORKSPACE/AGENTS.md"
AGENTS_MARKER="金融情报助手"

if [ ! -f "$AGENTS_FILE" ]; then
  cp "$SKILLS_DIR/AGENTS.md" "$AGENTS_FILE"
  echo "  ✓ AGENTS.md 已创建"
elif grep -q "$AGENTS_MARKER" "$AGENTS_FILE" 2>/dev/null; then
  echo "  - 已包含金融情报配置，跳过"
else
  echo "" >> "$AGENTS_FILE"
  echo "---" >> "$AGENTS_FILE"
  cat "$SKILLS_DIR/AGENTS.md" >> "$AGENTS_FILE"
  echo "  ✓ 已追加金融情报配置到现有 AGENTS.md"
fi

# ════════════════════════════════════════
# 第四步：合并 watchlist.json
# ════════════════════════════════════════
echo ""
echo "[4/5] 配置 watchlist.json..."

WATCHLIST_FILE="$WORKSPACE/watchlist.json"
WATCHLIST_DEFAULT="$SKILLS_DIR/watchlist.json"

if [ ! -f "$WATCHLIST_FILE" ]; then
  cp "$WATCHLIST_DEFAULT" "$WATCHLIST_FILE"
  echo "  ✓ watchlist.json 已创建（含默认监控名单）"
else
  MERGED=$(jq -s '
    .[0].stocks   = (.[0].stocks   + .[1].stocks   | unique) |
    .[0].sectors  = (.[0].sectors  + .[1].sectors  | unique) |
    .[0].keywords = (.[0].keywords + .[1].keywords | unique) |
    .[0]
  ' "$WATCHLIST_FILE" "$WATCHLIST_DEFAULT")
  echo "$MERGED" > "$WATCHLIST_FILE.tmp" && mv "$WATCHLIST_FILE.tmp" "$WATCHLIST_FILE"
  echo "  ✓ watchlist.json 已合并（原有数据保留）"
fi

# ════════════════════════════════════════
# 第五步：配置推送渠道 + Cron Jobs
# ════════════════════════════════════════
echo ""
echo "[5/5] 配置推送渠道和定时任务..."

# ── 通用：读取已配置则跳过，否则交互输入 ──
get_config() {
  local key="$1"
  local label="$2"
  local existing
  existing=$(openclaw config get "$key" 2>/dev/null || true)
  if [ -n "$existing" ] && [ "$existing" != "null" ]; then
    echo "  - $label 已配置，跳过"
  else
    read -p "  $label: " val
    if [ -n "$val" ]; then
      openclaw config set "$key" "$val"
      echo "  ✓ $label 已配置"
    else
      echo "  - $label 跳过（可后续手动配置）"
    fi
  fi
}

# ── 飞书 Webhook ──
echo ""
echo "  【飞书推送】（飞书群 → 设置 → 群机器人 → 自定义机器人 获取 URL，不用可直接回车跳过）"
echo ""
get_config "skills.entries.monitor.env.FEISHU_ALERT_WEBHOOK"       "飞书即时预警频道 Webhook"
get_config "skills.entries.sentiment.env.FEISHU_SENTIMENT_WEBHOOK" "飞书情绪日报频道 Webhook"
get_config "skills.entries.summarize.env.FEISHU_SECTOR_WEBHOOK"    "飞书板块监控频道 Webhook"
get_config "skills.entries.summarize.env.FEISHU_MORNING_WEBHOOK"   "飞书早报汇总频道 Webhook"

# ── Telegram Bot ──
echo ""
echo "  【Telegram 推送】（@BotFather 创建 Bot 获取 Token，不用可直接回车跳过）"
echo ""
get_config "skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN"       "Telegram Bot Token"
get_config "skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID"       "Telegram 即时预警频道 Chat ID"
get_config "skills.entries.sentiment.env.TELEGRAM_SENTIMENT_CHAT_ID" "Telegram 情绪日报频道 Chat ID"
get_config "skills.entries.summarize.env.TELEGRAM_SECTOR_CHAT_ID"    "Telegram 板块监控频道 Chat ID"
get_config "skills.entries.summarize.env.TELEGRAM_MORNING_CHAT_ID"   "Telegram 早报汇总频道 Chat ID"

# ── Heartbeat（幂等配置，重复写入无副作用）──
openclaw config set agents.defaults.heartbeat.every "2m"
openclaw config set agents.defaults.heartbeat.isolatedSession true
openclaw config set agents.defaults.heartbeat.target "none"
echo "  ✓ Heartbeat 已配置（每2分钟）"

# ── Cron Jobs（已存在同名则跳过）──
add_cron_if_missing() {
  local name="$1"
  shift
  if openclaw cron list 2>/dev/null | grep -q "\"$name\""; then
    echo "  - Cron「$name」已存在，跳过"
  else
    openclaw cron add --name "$name" "$@"
    echo "  ✓ Cron「$name」已添加"
  fi
}

add_cron_if_missing "情绪快照" \
  --cron "*/15 * * * *" \
  --session isolated \
  --message "运行 sentiment skill，读取最近15分钟 filtered-news.json，对各板块做情绪分析，推送飞书和 Telegram 情绪日报频道" \
  --model haiku

add_cron_if_missing "板块快报" \
  --cron "0 */2 * * *" \
  --session isolated \
  --message "运行 summarize skill，读取最近2小时 filtered-news.json，按板块生成快报，推送飞书和 Telegram 板块监控频道" \
  --model sonnet \
  --announce

add_cron_if_missing "早报" \
  --cron "0 8 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "运行 summarize skill 早报模式，汇总过去12小时所有内容，生成完整早报，推送飞书和 Telegram 早报频道" \
  --model sonnet \
  --announce

# ════════════════════════════════════════
# 完成
# ════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  部署完成！"
echo ""
echo "  验证命令："
echo "  openclaw cron list        查看定时任务"
echo "  openclaw gateway status   查看网关状态"
echo "  openclaw channels list    查看飞书连接"
echo ""
echo "  更新 Skills（不影响任何配置和数据）："
echo "  cd ~/.openclaw/skills/FEISHU_NEWS && git pull"
echo ""
echo "  重新运行本脚本（安全幂等，可随时重跑）："
echo "  bash ~/.openclaw/skills/FEISHU_NEWS/setup.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
