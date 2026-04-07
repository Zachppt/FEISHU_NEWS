#!/usr/bin/env python3
# 依赖：chardet（可选，用于 charset 检测）
# 安装：pip install chardet

import json
import hashlib
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORKSPACE = Path.home() / ".openclaw/workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

RAW_NEWS_FILE = WORKSPACE / "raw-news.json"
NEWS_CACHE_FILE = WORKSPACE / "news-cache.json"
SOURCES_FILE = SCRIPT_DIR / "sources.json"

MAX_RAW_NEWS = 300
FETCH_TIMEOUT = 30


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


def detect_encoding(http_content_type, raw_bytes):
    """从 HTTP Content-Type header 或 XML 声明检测 charset"""
    if http_content_type:
        for part in http_content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part.split("=", 1)[1].strip().strip('"')
    try:
        head = raw_bytes[:500].decode("ascii", errors="replace")
        if "encoding=" in head:
            import re
            m = re.search(r'encoding=["\']([^"\']+)["\']', head)
            if m:
                return m.group(1)
    except Exception:
        pass
    try:
        import chardet
        result = chardet.detect(raw_bytes)
        if result and result.get("encoding"):
            return result["encoding"]
    except ImportError:
        pass
    return "utf-8"


def normalize_to_utf8(raw_bytes, encoding):
    """将字节解码并重新编码为 UTF-8"""
    enc_lower = encoding.lower().replace("-", "").replace("_", "")
    if enc_lower in ("gb2312", "gbk", "gb18030"):
        try:
            text = raw_bytes.decode("gb18030", errors="replace")
            return text.encode("utf-8")
        except Exception:
            pass
    try:
        text = raw_bytes.decode(encoding, errors="replace")
        return text.encode("utf-8")
    except Exception:
        return raw_bytes


def parse_pubdate(pubdate_str):
    """将 pubDate 转为 ISO8601 UTC 字符串"""
    if not pubdate_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = parsedate_to_datetime(pubdate_str)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(pubdate_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_iso(ts_int):
    """Unix 时间戳转 ISO8601 UTC"""
    try:
        return datetime.fromtimestamp(int(ts_int), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get_json(url):
    """HTTP GET 返回解析后的 JSON"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FeishuNewsBot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def make_item(title, summary, url, source_name, ts):
    """构造标准新闻条目"""
    hash_val = hashlib.md5(title[:50].encode("utf-8")).hexdigest()
    return {
        "hash": hash_val,
        "title": title,
        "summary": summary[:200] if summary else "",
        "url": url,
        "source": source_name,
        "ts": ts,
    }


# ── RSS 抓取 ─────────────────────────────────────────────────────────────────

def fetch_rss(source):
    """抓取单个 RSS 源，返回新闻列表"""
    name = source.get("name", "")
    url = source.get("url", "")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FeishuNewsBot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        content_type = resp.headers.get("Content-Type", "")
        raw_bytes = resp.read()

    encoding = detect_encoding(content_type, raw_bytes)
    utf8_bytes = normalize_to_utf8(raw_bytes, encoding)

    root = ET.fromstring(utf8_bytes)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", ns)

    news_list = []
    for item in items:
        def get_text(tag, atom_tag=None):
            el = item.find(tag)
            if el is None and atom_tag:
                el = item.find(atom_tag, ns)
            if el is not None:
                return (el.text or "").strip()
            return ""

        title = get_text("title", "atom:title")
        description = get_text("description", "atom:summary")
        summary = description[:200] if description else ""

        link_el = item.find("link")
        if link_el is not None and link_el.text:
            link = link_el.text.strip()
        else:
            link_el = item.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""

        pubdate = get_text("pubDate", "atom:published") or get_text("atom:updated", None)
        ts = parse_pubdate(pubdate)

        if not title or not link:
            continue

        news_list.append(make_item(title, summary, link, name, ts))

    return news_list


# ── JSON API 抓取 ─────────────────────────────────────────────────────────────

def fetch_wallstreetcn(source):
    """华尔街见闻 7x24 快讯"""
    name = source["name"]
    data = http_get_json(source["url"])
    items = data.get("data", {}).get("items", [])
    news_list = []
    for item in items:
        title = item.get("title", "").strip()
        content = item.get("content_text", "").strip()
        # 快讯 title 为空时，用正文前50字作标题
        if not title:
            title = content[:50].rstrip("，。！？") if content else ""
        if not title:
            continue
        url = item.get("uri", "")
        if not url:
            continue
        ts = unix_to_iso(item.get("display_time", 0))
        news_list.append(make_item(title, content, url, name, ts))
    return news_list


def fetch_sina_finance(source):
    """新浪财经滚动新闻"""
    name = source["name"]
    data = http_get_json(source["url"])
    items = data.get("result", {}).get("data", [])
    news_list = []
    for item in items:
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        if not title or not url:
            continue
        summary = item.get("intro", "").strip()
        ts = unix_to_iso(item.get("ctime", 0))
        news_list.append(make_item(title, summary, url, name, ts))
    return news_list


def fetch_eastmoney_ann(source):
    """东方财富沪深上市公司公告"""
    name = source["name"]
    data = http_get_json(source["url"])
    items = data.get("data", {}).get("list", [])
    news_list = []
    for item in items:
        title = item.get("title_ch", "").strip() or item.get("title", "").strip()
        if not title:
            continue
        art_code = item.get("art_code", "")
        # 构造公告链接
        url = f"https://data.eastmoney.com/notices/detail/{art_code}.html" if art_code else ""
        if not url:
            continue
        ts_raw = item.get("display_time", "") or item.get("notice_date", "")
        # display_time 格式: "2026-04-07 21:20:47:267"
        try:
            ts_clean = ts_raw.split(":")[0] + ":" + ts_raw.split(":")[1] + ":" + ts_raw.split(":")[2]
            dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # summary: 涉及公司名称
        codes = item.get("codes", [])
        short_name = codes[0].get("short_name", "") if codes else ""
        summary = f"公司：{short_name}" if short_name else ""
        news_list.append(make_item(title, summary, url, name, ts))
    return news_list


API_FETCHERS = {
    "wallstreetcn": fetch_wallstreetcn,
    "sina_finance": fetch_sina_finance,
    "eastmoney_ann": fetch_eastmoney_ann,
}


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main():
    sources_data = load_json(SOURCES_FILE, {"rss": [], "api": [], "browser": []})
    raw_news = load_json(RAW_NEWS_FILE, [])
    cache = load_json(NEWS_CACHE_FILE, {})

    existing_hashes = set(cache.keys())
    new_items = []

    # RSS 源
    for source in sources_data.get("rss", []):
        if not source.get("enabled", False):
            continue
        name = source.get("name", source.get("url", ""))
        try:
            items = fetch_rss(source)
            for item in items:
                if item["hash"] not in existing_hashes:
                    new_items.append(item)
                    existing_hashes.add(item["hash"])
        except Exception as e:
            print(f"[fetch-news] 源失败: {name} {e}", file=sys.stderr)

    # JSON API 源
    for source in sources_data.get("api", []):
        if not source.get("enabled", False):
            continue
        api_type = source.get("api_type", "")
        fetcher = API_FETCHERS.get(api_type)
        if not fetcher:
            continue
        name = source.get("name", source.get("url", ""))
        try:
            items = fetcher(source)
            for item in items:
                if item["hash"] not in existing_hashes:
                    new_items.append(item)
                    existing_hashes.add(item["hash"])
        except Exception as e:
            print(f"[fetch-news] 源失败: {name} {e}", file=sys.stderr)

    # browser 源由 fetch-news SKILL 处理，此处跳过
    # （browser 源条目由 Agent 写入 raw-news.json，格式相同）

    if not new_items:
        return

    # 追加到 raw-news 头部，保留最新 300 条
    combined = new_items + raw_news
    combined = combined[:MAX_RAW_NEWS]
    atomic_write(RAW_NEWS_FILE, combined)

    # 更新 cache：添加新条目，清理超过 24 小时的 hash
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    for item in new_items:
        cache[item["hash"]] = item["ts"]

    pruned_cache = {}
    for h, ts_str in cache.items():
        try:
            ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts_dt > cutoff:
                pruned_cache[h] = ts_str
        except Exception:
            pruned_cache[h] = ts_str

    atomic_write(NEWS_CACHE_FILE, pruned_cache)


if __name__ == "__main__":
    main()
