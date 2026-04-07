#!/usr/bin/env python3
"""
用法：
  python3 manage_sources.py add <url> [name]   # 添加数据源（自动检测类型）
  python3 manage_sources.py remove <name>       # 按名称删除数据源
  python3 manage_sources.py list                # 列出所有数据源及状态
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SOURCES_FILE = SCRIPT_DIR / "sources.json"
FETCH_TIMEOUT = 20


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


def fetch_url(url):
    """抓取 URL，返回 (raw_bytes, content_type)"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FeishuNewsBot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def try_parse_rss(raw_bytes):
    """尝试解析 RSS/Atom，返回 (ok, sample_titles)"""
    try:
        # 处理 GB2312 等编码
        head = raw_bytes[:200].decode("ascii", errors="replace")
        encoding = "utf-8"
        m = re.search(r'encoding=["\']([^"\']+)["\']', head)
        if m:
            enc = m.group(1).lower().replace("-", "").replace("_", "")
            if enc in ("gb2312", "gbk", "gb18030"):
                raw_bytes = raw_bytes.decode("gb18030", errors="replace").encode("utf-8")
        root = ET.fromstring(raw_bytes)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        titles = []
        for item in items[:3]:
            t = item.find("title") or item.find("atom:title", ns)
            if t is not None and t.text:
                titles.append(t.text.strip()[:60])
        return True, titles
    except Exception:
        return False, []


def try_parse_json(raw_bytes):
    """尝试解析 JSON，返回 (ok, sample_titles, guessed_api_type)"""
    try:
        text = raw_bytes.decode("utf-8", errors="replace")
        data = json.loads(text)
        # 华尔街见闻
        items = data.get("data", {}).get("items", []) if isinstance(data, dict) else []
        if items and isinstance(items[0], dict) and "content_text" in items[0]:
            titles = [(i.get("title") or i.get("content_text", ""))[:60] for i in items[:3]]
            return True, titles, "wallstreetcn"
        # 新浪财经
        items = data.get("result", {}).get("data", []) if isinstance(data, dict) else []
        if items and isinstance(items[0], dict) and "intro" in items[0]:
            titles = [i.get("title", "")[:60] for i in items[:3]]
            return True, titles, "sina_finance"
        # 东方财富公告
        items = data.get("data", {}).get("list", []) if isinstance(data, dict) else []
        if items and isinstance(items[0], dict) and "title_ch" in items[0]:
            titles = [i.get("title_ch", "")[:60] for i in items[:3]]
            return True, titles, "eastmoney_ann"
        # 通用 JSON（有 items/data/list 字段但未识别格式）
        if isinstance(data, list) and len(data) > 0:
            return True, ["（JSON 列表，需自定义解析器）"], "custom"
        if isinstance(data, dict):
            return True, ["（JSON 对象，需自定义解析器）"], "custom"
        return False, [], ""
    except Exception:
        return False, [], ""


def detect_source_type(url):
    """
    访问 URL，自动检测类型。
    返回 dict: {type, api_type, sample_titles, error}
    """
    try:
        raw_bytes, content_type = fetch_url(url)
    except urllib.error.HTTPError as e:
        return {"type": None, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"type": None, "error": str(e)}

    ct = content_type.lower()

    # 1. 明确声明 XML / RSS
    if "xml" in ct or "rss" in ct or "atom" in ct:
        ok, titles = try_parse_rss(raw_bytes)
        if ok:
            return {"type": "rss", "sample_titles": titles}

    # 2. 明确声明 JSON
    if "json" in ct:
        ok, titles, api_type = try_parse_json(raw_bytes)
        if ok:
            return {"type": "api", "api_type": api_type, "sample_titles": titles}

    # 3. 未明确声明，逐个尝试
    ok, titles = try_parse_rss(raw_bytes)
    if ok:
        return {"type": "rss", "sample_titles": titles}

    ok, titles, api_type = try_parse_json(raw_bytes)
    if ok:
        return {"type": "api", "api_type": api_type, "sample_titles": titles}

    # 4. 降级为 browser
    return {"type": "browser", "sample_titles": [], "note": "无法直接解析，需 Agent Browser"}


def cmd_add(url, name=None):
    print(f"正在检测：{url}")
    result = detect_source_type(url)

    if result.get("error"):
        print(f"❌ 访问失败：{result['error']}")
        return

    src_type = result["type"]
    sample = result.get("sample_titles", [])

    # 自动推断名称
    if not name:
        domain = re.sub(r"https?://([^/]+).*", r"\1", url)
        name = domain

    sources = load_json(SOURCES_FILE, {"rss": [], "api": [], "browser": []})

    # 检查重复
    all_sources = (
        sources.get("rss", []) +
        sources.get("api", []) +
        sources.get("browser", [])
    )
    for s in all_sources:
        if s.get("url") == url:
            print(f"⚠️  该 URL 已存在（名称：{s.get('name')}）")
            return
        if s.get("name") == name:
            print(f"⚠️  名称「{name}」已被使用，请用 /add-source <url> <其他名称> 指定别名")
            return

    new_entry = {"name": name, "url": url, "enabled": True}

    if src_type == "rss":
        sources.setdefault("rss", []).append(new_entry)
        print(f"✅ 已添加 RSS 源：{name}")
    elif src_type == "api":
        api_type = result.get("api_type", "custom")
        new_entry["api_type"] = api_type
        if api_type == "custom":
            new_entry["note"] = "JSON API，需在 fetch_news.py 中添加自定义解析器"
        sources.setdefault("api", []).append(new_entry)
        print(f"✅ 已添加 API 源：{name}（api_type={api_type}）")
    else:
        new_entry["note"] = result.get("note", "需 Agent Browser")
        sources.setdefault("browser", []).append(new_entry)
        print(f"✅ 已添加 Browser 源：{name}（需 Agent Browser 渲染）")

    if sample:
        print(f"   抓取样本（前{len(sample)}条）：")
        for t in sample:
            print(f"   · {t}")

    atomic_write(SOURCES_FILE, sources)


def cmd_remove(name):
    sources = load_json(SOURCES_FILE, {"rss": [], "api": [], "browser": []})
    removed = False
    for key in ("rss", "api", "browser"):
        before = len(sources.get(key, []))
        sources[key] = [s for s in sources.get(key, []) if s.get("name") != name]
        if len(sources[key]) < before:
            removed = True
    if removed:
        atomic_write(SOURCES_FILE, sources)
        print(f"✅ 已移除：{name}")
    else:
        print(f"❌ 未找到名称「{name}」，请用 list 确认名称")


def cmd_list():
    sources = load_json(SOURCES_FILE, {"rss": [], "api": [], "browser": []})
    total = sum(len(sources.get(k, [])) for k in ("rss", "api", "browser"))
    print(f"📡 当前数据源（共 {total} 个）\n")

    for label, key in [("RSS", "rss"), ("JSON API", "api"), ("Browser", "browser")]:
        items = sources.get(key, [])
        if not items:
            continue
        print(f"【{label}】")
        for s in items:
            status = "✓" if s.get("enabled") else "✗"
            extra = ""
            if key == "api":
                extra = f"  api_type={s.get('api_type','?')}"
            note = f"  [{s.get('note','')}]" if s.get("note") else ""
            print(f"  {status} {s['name']}{extra}{note}")
            print(f"    {s['url']}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "add":
        if len(sys.argv) < 3:
            print("用法：python3 manage_sources.py add <url> [name]")
            sys.exit(1)
        url = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_add(url, name)
    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("用法：python3 manage_sources.py remove <name>")
            sys.exit(1)
        cmd_remove(sys.argv[2])
    elif cmd == "list":
        cmd_list()
    else:
        print(f"未知命令：{cmd}")
        print(__doc__)
        sys.exit(1)
