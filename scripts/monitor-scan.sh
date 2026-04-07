#!/usr/bin/env bash
# 规则预警扫描 - 检查 filtered-news.json 中命中预警词的未推送条目
# 输出：每条命中的完整 JSON（前缀 HIT），无命中则无输出
# 用法：bash monitor-scan.sh
set -euo pipefail
export LC_ALL=en_US.UTF-8

WORKSPACE=~/.openclaw/workspace

# ── 预警关键词（高精度，命中即推） ──
ALERT_PATTERN=\
"暴雷|资金链断裂|流动性危机|\
退市|摘牌|暂停上市|终止上市|\
ST |\\*ST|风险警示板|\
违约|债务违约|信用违约|展期|无法偿还|\
破产|破产重整|破产清算|破产申请|\
重大资产重组|借壳上市|重大重组|\
要约收购|私有化要约|\
美联储利率决议|FOMC决议|加息落地|降息落地|\
非农数据|就业数据超预期|\
监管处罚|行政处罚|没收违法所得|罚款|立案调查|立案稽查|\
证监会问询|问询函|监管函|警示函|\
大股东减持|控股股东减持|实控人减持|减持计划|\
财报造假|财务造假|虚假陈述|信息披露违规|\
审计意见|无法出具|保留意见|否定意见|非标意见|\
涨停|跌停"

# ── 读取已推送 id ──
PUSHED_IDS=$(jq -r '.pushed_ids // [] | .[]' "$WORKSPACE/monitor-state.json" 2>/dev/null || echo "")

# ── 扫描最新 50 条，输出命中且未推送的条目 ──
jq -c '.[-50:] | .[] | {id, title, source, ts, url}' \
  "$WORKSPACE/filtered-news.json" 2>/dev/null \
  | grep -E "$ALERT_PATTERN" \
  | while IFS= read -r line; do
      id=$(printf '%s' "$line" | jq -r '.id')
      if ! printf '%s\n' "$PUSHED_IDS" | grep -qxF "$id"; then
        printf 'HIT %s\n' "$line"
      fi
    done
