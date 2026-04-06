#!/bin/bash
# ═══════════════════════════════════════════════════
# 金融情报系统 · FEISHU_NEWS 部署脚本
#
# 使用方式：
#   首次部署：bash setup.sh
#   Agent 调用：bash setup.sh --non-interactive
#   更新版本：cd ~/.openclaw/skills/FEISHU_NEWS && git pull
#
# 安全承诺：
#   - 所有数据文件只追加合并，绝不覆盖原有内容
#   - 已存在的命令和配置自动跳过
#   - 重复运行完全安全，任何时候都可以再跑
# ═══════════════════════════════════════════════════

set -e

SKILLS_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
NON_INTERACTIVE=false

# 参数解析
for arg in "$@"; do
  case $arg in
    --non-interactive) NON_INTERACTIVE=true ;;
  esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  金融情报系统 · 部署脚本"
echo "  Skills 目录: $SKILLS_DIR"
echo "  Workspace:   $WORKSPACE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 工具检查 ──────────────────────────────────────────────────────────────────
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

# ── 辅助函数 ──────────────────────────────────────────────────────────────────

# 文件不存在时才创建
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

# 用 marker 防重复追加
append_if_missing() {
  local file="$1"
  local marker="$2"
  local source="$3"
  if [ ! -f "$file" ]; then
    cp "$source" "$file"
    echo "  ✓ 创建: $(basename $file)"
  elif grep -q "$marker" "$file" 2>/dev/null; then
    echo "  - 已包含 $marker，跳过"
  else
    echo "" >> "$file"
    echo "---" >> "$file"
    cat "$source" >> "$file"
    echo "  ✓ 已追加到: $(basename $file)"
  fi
}

# ════════════════════════════════════════
# 第一步：初始化工作区
# ════════════════════════════════════════
echo ""
echo "[1/7] 初始化工作区..."
mkdir -p "$WORKSPACE"

init_if_missing "$WORKSPACE/raw-news.json"           "[]"
init_if_missing "$WORKSPACE/filtered-news.json"      "[]"
init_if_missing "$WORKSPACE/news-cache.json"         "{}"
init_if_missing "$WORKSPACE/sentiment-snapshot.json" "{}"
init_if_missing "$WORKSPACE/monitor-state.json"      "{}"

# ════════════════════════════════════════
# 第二步：合并 sources.json（数据源配置）
# ════════════════════════════════════════
echo ""
echo "[2/7] 配置数据源 sources.json..."

SOURCES_FILE="$WORKSPACE/sources.json"
SOURCES_DEFAULT="$SKILLS_DIR/sources.json"

if [ ! -f "$SOURCES_FILE" ]; then
  cp "$SOURCES_DEFAULT" "$SOURCES_FILE"
  echo "  ✓ sources.json 已创建（含默认数据源）"
else
  # 合并：保留用户已有源，追加默认源中用户没有的
  MERGED=$(jq -s '
    def merge_by_name(a; b):
      (a + b) | group_by(.name) | map(.[0]);
    {
      rss:     merge_by_name(.[0].rss;     .[1].rss),
      api:     merge_by_name(.[0].api;     .[1].api),
      browser: merge_by_name(.[0].browser; .[1].browser)
    }
  ' "$SOURCES_FILE" "$SOURCES_DEFAULT")
  echo "$MERGED" > "$SOURCES_FILE.tmp" && mv "$SOURCES_FILE.tmp" "$SOURCES_FILE"
  echo "  ✓ sources.json 已合并（原有数据源保留）"
fi

# ════════════════════════════════════════
# 第三步：合并 watchlist.json
# ════════════════════════════════════════
echo ""
echo "[3/7] 配置 watchlist.json..."

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
# 第四步：合并 HEARTBEAT.md / AGENTS.md
# ════════════════════════════════════════
echo ""
echo "[4/7] 合并工作区配置文件..."

append_if_missing "$WORKSPACE/HEARTBEAT.md" "FEISHU_NEWS_HEARTBEAT" "$SKILLS_DIR/HEARTBEAT.md"
append_if_missing "$WORKSPACE/AGENTS.md"    "FEISHU_NEWS_AGENTS"    "$SKILLS_DIR/AGENTS.md"

# ════════════════════════════════════════
# 第五步：安装 agent-browser
# ════════════════════════════════════════
echo ""
echo "[5/7] 检查 agent-browser..."

if command -v agent-browser &>/dev/null; then
  echo "  - agent-browser 已安装，跳过"
else
  if command -v npm &>/dev/null; then
    npm install -g @vercel-labs/agent-browser -q && echo "  ✓ agent-browser 已安装"
  else
    echo "  [!] npm 未找到，跳过 agent-browser 安装（需要登录的数据源将不可用）"
  fi
fi

# ════════════════════════════════════════
# 第六步：OpenClaw 配置
# ════════════════════════════════════════
echo ""
echo "[6/7] 配置 OpenClaw..."

if ! command -v openclaw &>/dev/null; then
  echo "  [!] openclaw 命令未找到，跳过 OpenClaw 配置"
else
  # Heartbeat
  openclaw config set agents.defaults.heartbeat.every "2m"
  openclaw config set agents.defaults.heartbeat.isolatedSession true
  openclaw config set agents.defaults.heartbeat.target "none"
  echo "  ✓ Heartbeat 已配置（每2分钟）"

  # Cron Jobs（幂等：已存在则跳过）
  add_cron_if_missing() {
    local name="$1"; shift
    if openclaw cron list 2>/dev/null | grep -q "\"$name\""; then
      echo "  - Cron「$name」已存在，跳过"
    else
      openclaw cron add --name "$name" "$@"
      echo "  ✓ Cron「$name」已添加"
    fi
  }

  add_cron_if_missing "情绪快照" \
    --cron "*/15 * * * *" --session isolated --model haiku \
    --message "运行 sentiment skill，读取最近15分钟 filtered-news.json，对各板块做情绪分析，推送飞书情绪日报频道"

  add_cron_if_missing "板块快报" \
    --cron "0 */2 * * *" --session isolated --model sonnet --announce \
    --message "运行 summarize skill，读取最近2小时 filtered-news.json，按板块生成快报，推送飞书板块监控频道"

  add_cron_if_missing "早报" \
    --cron "0 8 * * *" --tz "Asia/Shanghai" --session isolated --model sonnet --announce \
    --message "运行 summarize skill 早报模式，汇总过去12小时所有内容，生成完整早报，推送飞书早报频道"
fi

# ════════════════════════════════════════
# 第七步：检测缺失配置，输出给 Agent
# ════════════════════════════════════════
echo ""
echo "[7/7] 检测配置状态..."

MISSING_CONFIGS=()

check_config() {
  local key="$1"
  local label="$2"
  local link="$3"
  local val
  val=$(openclaw config get "$key" 2>/dev/null || true)
  if [ -z "$val" ] || [ "$val" = "null" ]; then
    MISSING_CONFIGS+=("$key|$label|$link")
    echo "  MISSING: $key ($label)"
  else
    echo "  ✓ 已配置: $label"
  fi
}

if command -v openclaw &>/dev/null; then
  check_config "skills.entries.feishu_news.env.FEISHU_ALERT_WEBHOOK"     "飞书即时预警 Webhook"  "https://open.feishu.cn/app"
  check_config "skills.entries.feishu_news.env.FEISHU_SENTIMENT_WEBHOOK" "飞书情绪日报 Webhook"  "https://open.feishu.cn/app"
  check_config "skills.entries.feishu_news.env.FEISHU_SECTOR_WEBHOOK"    "飞书板块监控 Webhook"  "https://open.feishu.cn/app"
  check_config "skills.entries.feishu_news.env.FEISHU_MORNING_WEBHOOK"   "飞书早报 Webhook"      "https://open.feishu.cn/app"
fi

# ════════════════════════════════════════
# 完成
# ════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ${#MISSING_CONFIGS[@]} -gt 0 ]; then
  echo "  SETUP_PARTIAL: 安装完成，以下配置待填写"
  for item in "${MISSING_CONFIGS[@]}"; do
    echo "  MISSING_CONFIG: $item"
  done
  echo ""
  if [ "$NON_INTERACTIVE" = false ]; then
    echo "  请告知你的 Agent 完成剩余配置，或手动运行："
    echo "  openclaw config set <key> <value>"
  fi
else
  echo "  SETUP_DONE: 部署完成，所有配置已就绪"
fi

echo ""
echo "  更新 Skills（不影响任何配置和数据）："
echo "  cd ~/.openclaw/skills/FEISHU_NEWS && git pull"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
