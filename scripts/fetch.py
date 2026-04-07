#!/usr/bin/env python3
"""
RSS 抓取脚本 - 解析多个 RSS 源，去重后写入 raw-news.json
只保留 id/title/source/ts/url，不存摘要
"""
import json, os, hashlib, urllib.request
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
SKILLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_RAW = 100


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def title_hash(title):
    return hashlib.md5(title[:50].encode("utf-8")).hexdigest()[:12]


def fetch_url(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FeishuNews/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb2312", errors="replace")
    except Exception as e:
        return None


def parse_rss(xml_text, source_name):
    items = []
    try:
        # 屏蔽默认命名空间，避免解析失败
        xml_text = xml_text.replace(' xmlns="', ' xmlns_ignore="')
        root = ET.fromstring(xml_text.encode("utf-8"))

        # RSS 2.0
        entries = root.findall(".//item")
        ns = ""
        # Atom
        if not entries:
            ns = "{http://www.w3.org/2005/Atom}"
            entries = root.findall(f".//{ns}entry")

        for entry in entries:
            def text(tag, ns=""):
                el = entry.find(f"{ns}{tag}")
                return (el.text or "").strip() if el is not None else ""

            title = text("title") or text("title", ns)
            link  = text("link")  or text("link", ns)
            if not link and ns:
                el = entry.find(f"{ns}link")
                link = (el.attrib.get("href", "") if el is not None else "")
            ts = (text("pubDate") or text("published", ns) or text("updated", ns)
                  or datetime.now(timezone.utc).isoformat())

            title = title.strip()
            if len(title) < 6:
                continue

            items.append({
                "id":     title_hash(title),
                "title":  title,
                "source": source_name,
                "ts":     ts,
                "url":    link.strip(),
            })
    except Exception:
        pass
    return items


def main():
    # 优先用 workspace 下的 sources.json（用户可能已自定义）
    sources_path = os.path.join(WORKSPACE, "sources.json")
    if not os.path.exists(sources_path):
        sources_path = os.path.join(SKILLS_DIR, "sources.json")

    sources  = load_json(sources_path, {"rss": [], "api": [], "browser": []})
    cache    = load_json(os.path.join(WORKSPACE, "news-cache.json"), {})
    raw_news = load_json(os.path.join(WORKSPACE, "raw-news.json"), [])

    existing_ids = {item["id"] for item in raw_news}

    new_items      = []
    skipped        = 0
    failed_sources = []

    for source in sources.get("rss", []):
        if not source.get("enabled"):
            continue
        xml_text = fetch_url(source["url"])
        if xml_text is None:
            failed_sources.append(source["name"])
            continue
        for item in parse_rss(xml_text, source["name"]):
            if item["id"] in cache or item["id"] in existing_ids:
                skipped += 1
            else:
                new_items.append(item)
                cache[item["id"]] = True
                existing_ids.add(item["id"])

    # 新条目在前，保留最新 MAX_RAW 条
    updated = (new_items + raw_news)[:MAX_RAW]

    # 缓存只保留最近 2000 条哈希
    if len(cache) > 2000:
        cache = dict(list(cache.items())[-2000:])

    save_json(os.path.join(WORKSPACE, "raw-news.json"), updated)
    save_json(os.path.join(WORKSPACE, "news-cache.json"), cache)

    # 输出给心跳决策用
    print(f"NEW:{len(new_items)}")
    print(f"SKIPPED:{skipped}")
    if failed_sources:
        print(f"FAILED:{','.join(failed_sources)}")


if __name__ == "__main__":
    main()
