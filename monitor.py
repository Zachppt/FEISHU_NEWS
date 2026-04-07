#!/usr/bin/env python3
# 依赖：标准库（urllib、json、subprocess）

import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

FILTERED_NEWS_FILE = WORKSPACE / "filtered-news.json"
MONITOR_STATE_FILE = WORKSPACE / "monitor-state.json"


# ── 配置读取 ──────────────────────────────────────────────────────────────────

def openclaw_config_get(key):
    """通过 openclaw config get 读取配置值，失败返回空字符串"""
    try:
        result = subprocess.run(
            ["openclaw", "config", "get", key],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ── 文件读写 ──────────────────────────────────────────────────────────────────

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


# ── 推送逻辑 ──────────────────────────────────────────────────────────────────

def send_feishu(webhook_url, emoji, color, title_text, source, ts_str, summary, url):
    matched_display = title_text[:20]
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{emoji} {matched_display} 相关消息",
                },
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**来源：**{source}　**时间：**{ts_str}\n\n"
                            f"{summary[:100]}"
                        ),
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看原文"},
                            "type": "default",
                            "url": url,
                        }
                    ],
                },
            ],
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            if status != 200:
                print(f"[monitor] 推送失败: {status}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"[monitor] 推送失败: {e.code}", file=sys.stderr)
    except Exception as e:
        print(f"[monitor] 推送失败: {e}", file=sys.stderr)


def send_telegram(token, chat_id, emoji, title_text, source, ts_str, summary, url):
    matched_display = title_text[:20]
    text = (
        f"{emoji} *{matched_display} 相关消息*\n"
        f"来源：{source}　时间：{ts_str}\n\n"
        f"{summary[:100]}\n\n"
        f"[查看原文]({url})"
    )
    params = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "false",
    }).encode("utf-8")
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(api_url, data=params, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            if status != 200:
                print(f"[monitor] 推送失败: {status}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"[monitor] 推送失败: {e.code}", file=sys.stderr)
    except Exception as e:
        print(f"[monitor] 推送失败: {e}", file=sys.stderr)


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def extract_company_key(item):
    """从公告标题提取公司名，用于同公司去重。
    东方财富公告格式：'*ST云网:关于...'，取冒号前部分。
    其他来源返回空字符串（不做公司去重）。
    """
    source = item.get("source", "")
    if "东方财富" in source or "公告" in source:
        title = item.get("title", "")
        if ":" in title:
            return title.split(":")[0].strip()
        if "：" in title:
            return title.split("：")[0].strip()
    return ""


def main():
    filtered_news = load_json(FILTERED_NEWS_FILE, [])
    state = load_json(MONITOR_STATE_FILE, {})

    pushed_ids = set(state.get("pushed_ids", []))

    # 若 monitor-state.json 不存在，只处理最近 1 小时的条目
    state_existed = MONITOR_STATE_FILE.exists()
    now = datetime.now(timezone.utc)
    if not state_existed:
        cutoff_time = now - timedelta(hours=1)
    else:
        cutoff_time = None

    # 读取配置
    feishu_webhook = openclaw_config_get("skills.entries.monitor.env.FEISHU_ALERT_WEBHOOK")
    tg_token = openclaw_config_get("skills.entries.feishu_news.env.TELEGRAM_BOT_TOKEN")
    tg_chat_id = openclaw_config_get("skills.entries.monitor.env.TELEGRAM_ALERT_CHAT_ID")

    # 本次运行已预警的公司集合（防同公司刷屏）
    alerted_companies = set()

    for item in filtered_news:
        url = item.get("url", "")
        if url in pushed_ids:
            continue

        # 时效过滤（仅无 state 文件时启用）
        if cutoff_time:
            try:
                item_time = datetime.fromisoformat(
                    item["ts"].replace("Z", "+00:00")
                )
                if item_time < cutoff_time:
                    continue
            except Exception:
                pass

        # 同公司去重：每次运行同一家公司只推第一条（评分最高，因 filtered_news 已按 score 排列）
        company_key = extract_company_key(item)
        if company_key:
            if company_key in alerted_companies:
                pushed_ids.add(url)  # 标记已处理，避免下次重复
                continue
            alerted_companies.add(company_key)

        priority = item.get("priority", "normal")
        match_dimension = item.get("match_dimension", "")
        title = item.get("title", "")
        summary = item.get("summary", "")
        source = item.get("source", "")
        ts_str = item.get("ts", "")
        matched_terms = item.get("matched_terms", [])

        # 确定预警级别
        if priority == "high":
            emoji = "🚨"
            color = "red"
        elif match_dimension == "stocks":
            emoji = "⚡"
            color = "orange"
        else:
            emoji = "📌"
            color = "blue"

        # 飞书推送
        if feishu_webhook:
            send_feishu(feishu_webhook, emoji, color, title, source, ts_str, summary, url)

        # Telegram 推送
        if tg_token and tg_chat_id:
            send_telegram(tg_token, tg_chat_id, emoji, title, source, ts_str, summary, url)

        pushed_ids.add(url)
        print(f"[monitor] 预警: {title[:20]}")

    # 更新 monitor-state.json，pushed_ids 只保留最近 24 小时内的 URL
    # 由于 pushed_ids 只存 URL 无时间戳，使用 filtered_news 中的 ts 来过滤
    ts_map = {item["url"]: item.get("ts", "") for item in filtered_news}
    cutoff_24h = now - timedelta(hours=24)
    pruned_ids = []
    for uid in pushed_ids:
        ts_val = ts_map.get(uid, "")
        try:
            ts_dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            if ts_dt > cutoff_24h:
                pruned_ids.append(uid)
        except Exception:
            # 无法解析时间则保留
            pruned_ids.append(uid)

    new_state = {
        "last_check": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pushed_ids": pruned_ids,
    }
    atomic_write(MONITOR_STATE_FILE, new_state)


if __name__ == "__main__":
    main()
