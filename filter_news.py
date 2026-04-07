#!/usr/bin/env python3
# 纯 Python 字符串处理，不调用任何 AI/LLM

import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORKSPACE = Path.home() / ".openclaw/workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

RAW_NEWS_FILE = WORKSPACE / "raw-news.json"
FILTERED_NEWS_FILE = WORKSPACE / "filtered-news.json"
WATCHLIST_FILE = SCRIPT_DIR / "watchlist.json"
ALIASES_FILE = SCRIPT_DIR / "aliases.json"

MAX_FILTERED = 500

# ── 常量词表 ──────────────────────────────────────────────────────────────────

MACRO_TERMS = [
    # 中文
    "美联储", "降息", "加息", "利率决议", "央行", "MLF", "LPR",
    "非农", "债券违约", "评级下调", "证监会", "退市", "暴雷", "并购", "重组",
    # 英文宏观数据与政策
    "Fed", "FOMC", "GDP", "CPI", "PPI", "PCE", "PMI",
    "interest rate", "rate cut", "rate hike", "central bank",
    "Federal Reserve", "Powell", "Yellen", "Treasury",
    "inflation", "deflation", "recession", "stagflation",
    "earnings", "revenue", "profit", "loss",
    # 能源与大宗
    "oil", "crude", "natural gas", "LNG", "coal", "copper", "gold",
    # 贸易与地缘
    "tariff", "trade war", "sanctions", "embargo",
    "geopolitical", "war", "conflict",
    # 信贷与评级
    "default", "bankruptcy", "credit rating", "downgrade", "upgrade",
    "Moody's", "Fitch", "S&P",
    # 资本市场
    "IPO", "merger", "acquisition", "buyout", "delisting",
]

HIGH_VALUE_TERMS = [
    # 中文
    "退市", "暴雷", "违约", "破产", "立案", "拘留", "IPO撤单", "实控人",
    # 英文监管与风险
    "SEC", "DOJ", "FBI", "CFTC",
    "fraud", "bankrupt", "default", "delisted", "insolvent",
    "sanctions", "arrested", "investigation", "subpoena",
    "lawsuit", "settlement", "penalty", "fine",
    # 市场冲击
    "crash", "collapse", "plunge", "surge", "record high", "record low",
    "bailout", "rescue", "emergency",
]

# ST 单独处理：只匹配 A 股风险警示前缀格式，不做通用词匹配
ST_PATTERN = re.compile(r'(?:^|\s|\()[\*\*]?ST\s*[\u4e00-\u9fff]')

FINANCE_WORDS = ["净利润", "营收", "毛利率", "同比", "环比"]

SPAM_WORDS = [
    "广告", "推广", "赞助", "软文", "招聘", "求职",
    "优惠券", "折扣", "秒杀", "限时", "博彩", "赌博",
]

BREAKING_WORDS = ["暴雷", "退市", "停牌", "紧急", "突发"]
MACRO_DATA_WORDS = ["CPI", "PPI", "GDP", "非农", "PMI"]
RESEARCH_WORDS = ["研报", "分析师", "评级", "目标价"]
OFFICIAL_WORDS = ["交易所", "证监会", "公告", "披露"]

# 行情播报正则：股票名 + 今日/昨日 + 涨/跌 + 数字% + 结尾
MARKET_REPORT_RE = re.compile(
    r"^[\u4e00-\u9fff\w]{2,6}[（(]?[\w]+[）)]?\s*[今昨][日天]\s*[涨跌][幅]?\s*[\d.]+%\s*$"
)


# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def load_json(path, default):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def atomic_write(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def strip_punct_digits(text):
    """去除标点和数字，用于相似度计算"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z]", "", text)


def similarity(a, b):
    """公共字符数 / min(len(a), len(b))，去标点数字后"""
    a = strip_punct_digits(a)
    b = strip_punct_digits(b)
    if not a or not b:
        return 0.0
    # 基于多重集交集的字符重叠
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    common = sum((ca & cb).values())
    return common / min(len(a), len(b))


def contains_any(text, terms):
    """检查 text 是否含 terms 中任意词，返回命中词列表。
    中文词：直接子串匹配。
    纯英文/数字词（如 ST、Fed、CPI）：要求词边界，避免误匹配英文单词内部。
    """
    matched = []
    for term in terms:
        if re.search(r'[a-zA-Z0-9]', term) and not re.search(r'[\u4e00-\u9fff]', term):
            # 纯英文/数字词：词边界匹配（大小写不敏感）
            pattern = r'(?<![a-zA-Z0-9])' + re.escape(term) + r'(?![a-zA-Z0-9])'
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(term)
        else:
            # 中文词或中英混合词：直接子串匹配
            if term.lower() in text.lower():
                matched.append(term)
    return matched


def has_finance_number(text):
    """title 或 summary 含具体数字 + 财务词"""
    has_num = bool(re.search(r"\d+\.?\d*\s*[%亿万元]?", text))
    has_fin = any(w in text for w in FINANCE_WORDS)
    return has_num and has_fin


def count_chinese(text):
    return len([c for c in text if "\u4e00" <= c <= "\u9fff"])


def timeliness_cutoff(item):
    """根据新闻内容返回时效截止小时数"""
    text = (item.get("title", "") + " " + item.get("summary", "") +
            " " + item.get("source", ""))
    if any(w in text for w in OFFICIAL_WORDS):
        return 72
    if any(w in text for w in RESEARCH_WORDS):
        return 48
    if any(w in text for w in MACRO_DATA_WORDS):
        return 24
    if any(w in text for w in BREAKING_WORDS):
        return 12
    return 6


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main():
    raw_news = load_json(RAW_NEWS_FILE, [])
    filtered_existing = load_json(FILTERED_NEWS_FILE, [])
    watchlist = load_json(WATCHLIST_FILE, {"stocks": [], "sectors": [], "keywords": []})
    aliases_map = load_json(ALIASES_FILE, {})

    # 展开 stocks 别名为扁平词表
    stock_terms = list(watchlist.get("stocks", []))
    for canonical, alias_list in aliases_map.items():
        stock_terms.append(canonical)
        stock_terms.extend(alias_list)
    stock_terms = list(dict.fromkeys(stock_terms))  # 去重保序

    sector_terms = watchlist.get("sectors", [])
    keyword_terms = watchlist.get("keywords", [])

    # 已过滤新闻的 URL 集合
    existing_urls = {item["url"] for item in filtered_existing}
    # 已过滤新闻的 title（去标点数字）用于相似度检测
    existing_titles = [strip_punct_digits(item["title"]) for item in filtered_existing]

    # 基准时间 = 本批次最新 ts
    if raw_news:
        try:
            base_time = max(
                datetime.fromisoformat(item["ts"].replace("Z", "+00:00"))
                for item in raw_news
                if item.get("ts")
            )
        except Exception:
            base_time = datetime.now(timezone.utc)
    else:
        base_time = datetime.now(timezone.utc)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_filtered = []

    for item in raw_news:
        title = item.get("title", "")
        summary = item.get("summary", "")
        url = item.get("url", "")
        ts_str = item.get("ts", "")
        combined = title + " " + summary

        # ── 硬性丢弃 ──────────────────────────────────────────────────────────
        # 1. 中文标题字数 < 10 且英文 < 20
        zh_count = count_chinese(title)
        en_count = len(re.findall(r"[A-Za-z]", title))
        if zh_count < 10 and en_count < 20:
            continue

        # 2. URL 已在 filtered-news 中
        if url in existing_urls:
            continue

        # 3. 相似度 > 85%
        title_stripped = strip_punct_digits(title)
        too_similar = any(
            similarity(title_stripped, et) > 0.85
            for et in existing_titles
            if et
        )
        if too_similar:
            continue

        # ── 时效性检查 ────────────────────────────────────────────────────────
        try:
            item_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            cutoff_hours = timeliness_cutoff(item)
            if (base_time - item_time) > timedelta(hours=cutoff_hours):
                continue
        except Exception:
            pass

        # ── 评分 ──────────────────────────────────────────────────────────────
        score = 0
        matched_terms = []
        match_dimension = ""
        priority = "normal"

        # +3 stocks
        stock_hits = contains_any(combined, stock_terms)
        if stock_hits:
            score += 3
            matched_terms.extend(stock_hits)
            match_dimension = "stocks"

        # +2 sectors
        sector_hits = contains_any(combined, sector_terms)
        if sector_hits:
            score += 2
            matched_terms.extend(sector_hits)
            if not match_dimension:
                match_dimension = "sectors"

        # +2 keywords
        kw_hits = contains_any(combined, keyword_terms)
        if kw_hits:
            score += 2
            matched_terms.extend(kw_hits)
            if not match_dimension:
                match_dimension = "keywords"

        # +2 macro
        macro_hits = contains_any(combined, MACRO_TERMS)
        if macro_hits:
            score += 2
            matched_terms.extend(macro_hits)
            if not match_dimension:
                match_dimension = "macro"

        # +2 high-value events
        hv_hits = contains_any(combined, HIGH_VALUE_TERMS)
        # ST 单独检测：只匹配 "ST 某公司" 格式，不匹配英文单词内的 st
        if ST_PATTERN.search(combined):
            hv_hits.append("ST")
        if hv_hits:
            score += 2
            matched_terms.extend(hv_hits)
            priority = "high"
            match_dimension = "high_value"

        # +1 数字 + 财务词
        if has_finance_number(combined):
            score += 1

        # -2 纯行情播报
        if MARKET_REPORT_RE.match(title.strip()):
            score -= 2

        # -3 垃圾词
        spam_hits = contains_any(combined, SPAM_WORDS)
        if spam_hits:
            score -= 3

        # 门槛过滤（≥2：至少命中一个宏观/高价值词，或两个其他维度）
        if score < 2:
            continue

        # priority 规则
        if score >= 6:
            priority = "high"

        # 去重 matched_terms
        matched_terms = list(dict.fromkeys(matched_terms))
        if not match_dimension:
            match_dimension = "keywords"

        filtered_item = {
            **item,
            "matched_terms": matched_terms,
            "match_dimension": match_dimension,
            "priority": priority,
            "score": score,
            "filtered_at": now_str,
        }
        new_filtered.append(filtered_item)

        # 同步更新本次已见标题，防止批次内重复
        existing_urls.add(url)
        existing_titles.append(title_stripped)

    if not new_filtered:
        return

    # 合并，保留最新 500 条（新条目在前）
    combined_filtered = new_filtered + filtered_existing
    combined_filtered = combined_filtered[:MAX_FILTERED]
    atomic_write(FILTERED_NEWS_FILE, combined_filtered)


if __name__ == "__main__":
    main()
