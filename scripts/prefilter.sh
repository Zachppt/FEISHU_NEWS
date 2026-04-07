#!/usr/bin/env bash
# 宽泛关键词初筛 - 高召回率，宁可多要不漏掉
# 输出：候选条目 JSON 数组（id + title），供 LLM 精筛
# 用法：bash prefilter.sh
set -euo pipefail
export LC_ALL=en_US.UTF-8

WORKSPACE=~/.openclaw/workspace

# ── 从 watchlist.json 读取用户配置的关键词 ──
WATCHLIST_PATTERN=$(jq -r '
  [.stocks[], .sectors[], .keywords[]] | map(select(length > 0)) | join("|")
' "$WORKSPACE/watchlist.json" 2>/dev/null || echo "")

# ── 内置宽泛金融关键词（覆盖常见别名、简称、英文） ──
BUILTIN_PATTERN=\
"美联储|Fed|FOMC|Powell|鲍威尔|耶伦|Yellen|\
非农|NFP|CPI|PPI|GDP|PMI|失业率|通胀|通缩|核心PCE|\
降息|加息|利率|货币政策|财政政策|量化宽松|QE|缩表|\
证监会|银保监|央行|人民银行|国资委|发改委|外管局|\
暴雷|违约|破产|退市|摘牌|ST |\\*ST|风险警示|\
重组|并购|收购|分拆|借壳|IPO|上市|定增|配股|回购|股权激励|可转债|要约|举牌|私有化|\
大股东|减持|增持|实控人|控股股东|质押|\
涨停|跌停|熔断|暂停上市|\
财报|业绩|净利润|营收|亏损|盈利预警|业绩预告|商誉减值|\
BYD|CATL|Tencent|Alibaba|BABA|Xiaomi|NVIDIA|NVDA|Apple|AAPL|Tesla|TSLA|Microsoft|MSFT|\
招行|招商银行|工行|建行|中行|农行|茅台|贵州茅台|宁德|比亚迪|\
光伏|储能|风电|电动车|EV|新能源汽车|锂电|固态电池|磷酸铁锂|三元锂|\
半导体|芯片|晶圆|光刻机|EDA|HBM|先进制程|台积电|TSMC|\
大模型|GPT|AGI|Sora|Claude|Gemini|人工智能|AI眼镜|具身智能|\
地产|房价|楼市|开发商|碧桂园|恒大|万科|保利|招商蛇口|\
原油|WTI|布伦特|黄金|COMEX|铜价|铁矿|铝|螺纹钢|大宗商品|期货|\
港股|A股|美股|纳指|道指|标普|恒指|科创板|北交所|\
关税|贸易战|制裁|出口限制|实体清单|卡脖子"

# ── 合并所有关键词 ──
if [ -n "$WATCHLIST_PATTERN" ]; then
  FULL_PATTERN="${WATCHLIST_PATTERN}|${BUILTIN_PATTERN}"
else
  FULL_PATTERN="$BUILTIN_PATTERN"
fi

# ── 读取已过滤新闻的 id 列表（去重） ──
EXISTING_IDS=$(jq -r '.[].id' "$WORKSPACE/filtered-news.json" 2>/dev/null || echo "")

# ── 对 raw-news.json 做关键词匹配，输出候选 JSON ──
jq -c '.[] | {id, title, source, ts, url}' "$WORKSPACE/raw-news.json" 2>/dev/null \
  | grep -E "$FULL_PATTERN" \
  | while IFS= read -r line; do
      id=$(printf '%s' "$line" | jq -r '.id')
      if ! printf '%s\n' "$EXISTING_IDS" | grep -qxF "$id"; then
        printf '%s\n' "$line"
      fi
    done \
  | jq -s '.'
