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
#   - 脚本只做文件和 Cron 配置，推送渠道由 Agent 引导完成
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
echo "[1/4] 初始化工作区..."
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
init_if_missing "$WORKSPACE/cost-log.json"            "[]"
mkdir -p "$WORKSPACE/reports"
chmod +x "$SKILLS_DIR/scripts/prefilter.sh"
chmod +x "$SKILLS_DIR/scripts/monitor-scan.sh"

# ── PDF 依赖检测 ──
echo "  检测 PDF 生成依赖..."
if python3 -c "import weasyprint" 2>/dev/null; then
  echo "  ✓ weasyprint 已安装（PDF 生成就绪）"
elif python3 -c "import fpdf" 2>/dev/null; then
  echo "  ✓ fpdf2 已安装（PDF 生成就绪，样式受限）"
else
  echo "  - PDF 库未安装，尝试安装 weasyprint..."
  pip install weasyprint -q 2>/dev/null && \
    echo "  ✓ weasyprint 安装成功" || \
    { pip install fpdf2 -q 2>/dev/null && echo "  ✓ fpdf2 安装成功（备选）" || \
      echo "  [!] PDF 库安装失败，早报将回退为文字版。手动安装：pip install weasyprint"; }
fi

# ════════════════════════════════════════
# 第二步：合并 HEARTBEAT.md / AGENTS.md
# ════════════════════════════════════════
echo ""
echo "[2/4] 配置工作区文件..."

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
# 第三步：合并 watchlist.json
# ════════════════════════════════════════
echo ""
echo "[3/4] 配置 watchlist.json..."

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
# 第四步：配置 Heartbeat + Cron Jobs
# ════════════════════════════════════════
echo ""
echo "[4/4] 配置定时任务..."

# Heartbeat（幂等）
openclaw config set agents.defaults.heartbeat.every "5m"
openclaw config set agents.defaults.heartbeat.isolatedSession true
openclaw config set agents.defaults.heartbeat.target "none"
openclaw config set agents.defaults.timeoutSeconds 120
echo "  ✓ Heartbeat 已配置（每5分钟）"

# Cron Jobs（已存在同名则跳过）
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
  --cron "*/30 * * * *" \
  --session isolated \
  --message "运行 sentiment skill，读取最近30分钟 filtered-news.json，对各板块做情绪分析，有明显变化时推送飞书和 Telegram 情绪日报频道"

add_cron_if_missing "板块快报" \
  --cron "0 */4 * * *" \
  --session isolated \
  --message "运行 summarize skill，读取最近4小时 filtered-news.json，按板块生成快报，推送飞书和 Telegram 板块监控频道" \
  --announce

add_cron_if_missing "早报" \
  --cron "0 8 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "运行 summarize skill 早报模式，汇总过去12小时所有内容，生成完整早报，推送飞书和 Telegram 早报频道" \
  --announce

# ════════════════════════════════════════
# 检测推送渠道配置状态，输出标记供 Agent 读取
# ════════════════════════════════════════
echo ""

check_config() {
  local key="$1"
  local label="$2"
  local val
  val=$(openclaw config get "$key" 2>/dev/null || true)
  if [ -z "$val" ] || [ "$val" = "null" ]; then
    echo "  MISSING_CONFIG: $key | $label"
    return 1
  fi
  return 0
}

MISSING=0

check_config "skills.entries.monitor.env.FEISHU_ALERT_WEBHOOK"       "飞书即时预警 Webhook"   || MISSING=1
check_config "skills.entries.sentiment.env.FEISHU_SENTIMENT_WEBHOOK" "飞书情绪日报 Webhook"   || MISSING=1
check_config "skills.entries.summarize.env.FEISHU_SECTOR_WEBHOOK"    "飞书板块监控 Webhook"   || MISSING=1
check_config "skills.entries.summarize.env.FEISHU_MORNING_WEBHOOK"   "飞书早报汇总 Webhook"   || MISSING=1
check_config "skills.entries.feishu_news.env.FEISHU_APP_ID"          "飞书应用 App ID（早报PDF发送用，可选）" || true
check_config "skills.entries.feishu_news.env.FEISHU_APP_SECRET"      "飞书应用 App Secret（早报PDF发送用，可选）" || true
check_config "skills.entries.summarize.env.FEISHU_MORNING_CHAT_ID"   "飞书早报群 Chat ID（早报PDF发送用，可选）" || true
check_config "skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN"     "Telegram Bot Token"     || MISSING=1
check_config "skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID"     "Telegram 即时预警 Chat ID" || MISSING=1
check_config "skills.entries.sentiment.env.TELEGRAM_SENTIMENT_CHAT_ID" "Telegram 情绪日报 Chat ID" || MISSING=1
check_config "skills.entries.summarize.env.TELEGRAM_SECTOR_CHAT_ID"  "Telegram 板块监控 Chat ID" || MISSING=1
check_config "skills.entries.summarize.env.TELEGRAM_MORNING_CHAT_ID" "Telegram 早报汇总 Chat ID" || MISSING=1

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$MISSING" = "1" ]; then
  echo "  SETUP_PARTIAL"
  echo ""
  echo "  文件和定时任务已就绪，推送渠道待配置。"
  echo "  请告知 Agent 继续完成配置，或手动执行："
  echo "  openclaw config set <key> <value>"
else
  echo "  SETUP_DONE"
  echo ""
  echo "  部署完成，所有推送渠道已配置就绪！"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
