#!/usr/bin/env python3
"""
早报 PDF 生成脚本 — 专业金融报告样式
从 stdin 读取早报 JSON，输出 PDF 文件路径

依赖（按优先级）：
  pip install weasyprint   ← 推荐，完整 CSS 支持
  pip install fpdf2        ← 备选，纯 Python
"""
import json, os, sys, re
from datetime import datetime, timezone, timedelta

WORKSPACE   = os.path.expanduser("~/.openclaw/workspace")
REPORTS_DIR = os.path.join(WORKSPACE, "reports")
CST         = timezone(timedelta(hours=8))
os.makedirs(REPORTS_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────
# 数据读取
# ──────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_report_data() -> dict:
    if not sys.stdin.isatty():
        try:
            return json.load(sys.stdin)
        except Exception:
            pass
    return {
        "date":     datetime.now(CST).strftime("%Y-%m-%d"),
        "weekday":  ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][datetime.now(CST).weekday()],
        "sentiment": load_json(os.path.join(WORKSPACE, "sentiment-snapshot.json"), {}),
        "filtered":  load_json(os.path.join(WORKSPACE, "filtered-news.json"), []),
        "tokens":   "~",
    }


# ──────────────────────────────────────────────────────
# HTML 构建
# ──────────────────────────────────────────────────────
def esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def sentiment_color(score: int) -> tuple[str, str]:
    if score >= 60: return "#16a34a", "🟢"
    if score >= 40: return "#d97706", "🟡"
    return "#dc2626", "🔴"

def delta_html(delta) -> str:
    try: d = int(delta)
    except: return "<span class='d-flat'>→</span>"
    if d >  3: return f"<span class='d-up'>↑{abs(d)}</span>"
    if d < -3: return f"<span class='d-dn'>↓{abs(d)}</span>"
    return "<span class='d-flat'>→</span>"

def change_class(up) -> str:
    return "card-up" if up else "card-dn"

def build_html(data: dict) -> str:
    date_str = data.get("date",    datetime.now(CST).strftime("%Y-%m-%d"))
    weekday  = data.get("weekday", "")
    gen_time = datetime.now(CST).strftime("%H:%M")
    tokens   = data.get("tokens",  "~")

    # ── 市场概况卡片 ──
    cards_html = ""
    for card in data.get("market_cards", []):
        cls = change_class(card.get("up", True))
        arrow = "▲" if card.get("up", True) else "▼"
        cards_html += f"""
        <div class="mcard">
          <div class="mcard-label">{esc(card.get('label',''))}</div>
          <div class="mcard-value">{esc(card.get('value','—'))}</div>
          <div class="mcard-change {cls}">{arrow} {esc(card.get('change',''))}</div>
        </div>"""

    # ── 隔夜美股 ──
    us_html = "".join(f"<li>{esc(x)}</li>" for x in data.get("us_market", []))
    if not us_html: us_html = "<li>暂无数据</li>"

    # ── 宏观政策 ──
    macro_html = "".join(f"<li>{esc(x)}</li>" for x in data.get("macro_policy", []))
    if not macro_html: macro_html = "<li>暂无数据</li>"

    # ── 今日关注 ──
    watch_rows = ""
    for ev in data.get("watch_today", []):
        t   = esc(ev.get("time",""))
        evt = esc(ev.get("event",""))
        imp = "watch-imp" if "🔴" in ev.get("event","") else ""
        watch_rows += f'<tr class="{imp}"><td class="watch-time">{t}</td><td>{evt}</td></tr>'
    if not watch_rows:
        watch_rows = '<tr><td colspan="2" class="empty">暂无日程</td></tr>'

    # ── 板块情绪全览 ──
    sentiment = data.get("sentiment", {})
    sent_rows = ""
    for sector, info in sentiment.items():
        score  = info.get("score", 50)
        delta  = info.get("delta", 0)
        detail = esc(info.get("detail", info.get("top_signal", "")))
        color, icon = sentiment_color(score)
        bar_w = score  # 0-100 → px width out of 100
        sent_rows += f"""
        <tr>
          <td class="sent-sector">{icon} {esc(sector)}</td>
          <td>
            <div class="score-wrap">
              <div class="score-bar" style="width:{bar_w}px;background:{color}"></div>
              <span class="score-num" style="color:{color}">{score}</span>
            </div>
          </td>
          <td>{delta_html(delta)}</td>
          <td class="sent-detail">{detail}</td>
        </tr>"""
    if not sent_rows:
        sent_rows = '<tr><td colspan="4" class="empty">暂无情绪数据</td></tr>'

    # ── 分板块新闻 ──
    sectors_html = ""
    news_by_sector = data.get("news_by_sector", {})
    idx = 1
    for sector, items in news_by_sector.items():
        if not items: continue
        rows = ""
        for item in items:
            title   = esc(item.get("title",""))
            summary = esc(item.get("summary",""))
            source  = esc(item.get("source",""))
            time_   = esc(item.get("time",""))
            url     = item.get("url","#")
            rows += f"""
            <div class="news-card">
              <div class="news-header">
                <span class="news-idx">{idx}</span>
                <a href="{url}" class="news-title">{title}</a>
              </div>
              {"<p class='news-summary'>" + summary + "</p>" if summary else ""}
              <div class="news-meta">{source}{"&nbsp;·&nbsp;" + time_ if time_ else ""}</div>
            </div>"""
            idx += 1
        sectors_html += f"""
        <div class="sector-block">
          <div class="sector-label">{esc(sector)}</div>
          {rows}
        </div>"""
    if not sectors_html:
        # fallback：取 filtered-news 最新20条
        filtered = data.get("filtered", [])[-20:]
        rows = ""
        for i, item in enumerate(filtered, 1):
            url   = item.get("url","#")
            title = esc(item.get("title",""))
            src   = esc(item.get("source",""))
            rows += f"""
            <div class="news-card">
              <div class="news-header">
                <span class="news-idx">{i}</span>
                <a href="{url}" class="news-title">{title}</a>
              </div>
              <div class="news-meta">{src}</div>
            </div>"""
        sectors_html = f'<div class="sector-block"><div class="sector-label">综合</div>{rows}</div>'

    # ── 个股动态 ──
    stocks_html = ""
    for stk in data.get("watchlist_stocks", []):
        name = esc(stk.get("name",""))
        news = esc(stk.get("news",""))
        url  = stk.get("url","#")
        sent = stk.get("sentiment","neutral")
        dot  = "🟢" if sent=="positive" else ("🔴" if sent=="negative" else "🟡")
        stocks_html += f"""
        <div class="stock-row">
          <span class="stock-name">{dot} {name}</span>
          <span class="stock-news"><a href="{url}">{news}</a></span>
        </div>"""

    stocks_section = f"""
    <div class="section">
      <div class="section-title">个股动态</div>
      {stocks_html if stocks_html else '<p class="empty">暂无监控个股动态</p>'}
    </div>""" if stocks_html else ""

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<style>
/* ── Reset & Base ── */
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
body {{
  font-family: 'PingFang SC','Hiragino Sans GB','Microsoft YaHei',
               'Noto Sans CJK SC','Arial',sans-serif;
  font-size: 12px; color: #1f2329; background: #fff;
  padding: 28px 36px;
}}
a {{ color: inherit; text-decoration: none; }}
a:hover {{ color: #2563eb; text-decoration: underline; }}

/* ── Header ── */
.header {{
  background: linear-gradient(135deg,#1e3a8a 0%,#1d4ed8 100%);
  color: #fff; border-radius: 8px;
  padding: 20px 24px; margin-bottom: 20px;
  display: flex; justify-content: space-between; align-items: center;
}}
.header-left h1 {{ font-size:20px; font-weight:700; letter-spacing:.5px; }}
.header-left .sub {{ font-size:11px; opacity:.75; margin-top:3px; }}
.header-right {{ text-align:right; }}
.header-right .date-big {{ font-size:16px; font-weight:700; }}
.header-right .date-sub {{ font-size:11px; opacity:.75; margin-top:2px; }}

/* ── Market Cards ── */
.mcards {{ display:flex; gap:10px; margin-bottom:20px; }}
.mcard {{
  flex:1; border:1px solid #e5e7eb; border-radius:7px;
  padding:12px 14px; background:#fafafa;
}}
.mcard-label {{ font-size:10px; color:#6b7280; margin-bottom:4px; font-weight:500; }}
.mcard-value {{ font-size:15px; font-weight:700; color:#111827; }}
.mcard-change {{ font-size:12px; font-weight:600; margin-top:3px; }}
.card-up {{ color:#16a34a; }}
.card-dn {{ color:#dc2626; }}

/* ── Two-column layout ── */
.two-col {{ display:flex; gap:18px; margin-bottom:20px; }}
.col-left {{ flex:1.1; }}
.col-right {{ flex:0.9; }}

/* ── Section ── */
.section {{ margin-bottom:20px; }}
.section-title {{
  font-size:12px; font-weight:700; color:#1e3a8a;
  border-left:3px solid #2563eb; padding-left:8px;
  margin-bottom:10px; text-transform:uppercase; letter-spacing:.3px;
}}

/* ── Bullet lists ── */
ul.blist {{ list-style:none; }}
ul.blist li {{
  padding: 4px 0 4px 14px; position:relative;
  line-height:1.65; color:#374151; border-bottom:1px solid #f3f4f6;
}}
ul.blist li::before {{
  content:"›"; position:absolute; left:0;
  color:#2563eb; font-weight:700; font-size:14px;
}}
ul.blist li:last-child {{ border-bottom:none; }}

/* ── Watch table ── */
.watch-table {{ width:100%; border-collapse:collapse; font-size:11px; }}
.watch-table td {{ padding:5px 8px; border-bottom:1px solid #f3f4f6; }}
.watch-time {{ color:#2563eb; font-weight:600; white-space:nowrap; width:50px; }}
.watch-imp td {{ background:#fff7ed; font-weight:600; }}
.watch-imp .watch-time {{ color:#c2410c; }}

/* ── Sentiment table ── */
.sent-table {{ width:100%; border-collapse:collapse; font-size:11px; }}
.sent-table th {{
  background:#eff6ff; color:#1e40af; font-weight:600;
  padding:7px 8px; text-align:left; border-bottom:2px solid #bfdbfe;
  font-size:10px; text-transform:uppercase; letter-spacing:.3px;
}}
.sent-table td {{ padding:7px 8px; border-bottom:1px solid #f3f4f6; vertical-align:middle; }}
.sent-sector {{ font-weight:600; white-space:nowrap; }}
.sent-detail {{ color:#4b5563; line-height:1.5; }}
.score-wrap {{ display:flex; align-items:center; gap:6px; }}
.score-bar  {{ height:6px; border-radius:3px; min-width:4px; }}
.score-num  {{ font-weight:700; font-size:12px; white-space:nowrap; }}
.d-up   {{ color:#16a34a; font-weight:700; }}
.d-dn   {{ color:#dc2626; font-weight:700; }}
.d-flat {{ color:#9ca3af; }}

/* ── News cards ── */
.sector-block {{ margin-bottom:14px; }}
.sector-label {{
  font-size:10px; font-weight:700; color:#2563eb;
  background:#eff6ff; padding:3px 8px; border-radius:4px;
  display:inline-block; margin-bottom:6px; text-transform:uppercase;
  letter-spacing:.3px;
}}
.news-card {{
  padding:8px 0 8px 10px; border-left:2px solid #e5e7eb;
  margin-bottom:6px;
}}
.news-header {{ display:flex; gap:8px; align-items:flex-start; margin-bottom:3px; }}
.news-idx {{
  min-width:18px; height:18px; background:#2563eb; color:#fff;
  border-radius:50%; font-size:10px; font-weight:700;
  display:flex; align-items:center; justify-content:center; flex-shrink:0;
}}
a.news-title {{
  color:#111827; font-weight:600; line-height:1.5; font-size:12px;
}}
a.news-title:hover {{ color:#2563eb; }}
.news-summary {{ color:#4b5563; line-height:1.6; margin:3px 0 3px 26px; font-size:11px; }}
.news-meta {{ color:#9ca3af; font-size:10px; margin-left:26px; }}

/* ── Stocks ── */
.stock-row {{
  display:flex; gap:10px; padding:6px 0;
  border-bottom:1px solid #f3f4f6; align-items:flex-start;
}}
.stock-name {{ white-space:nowrap; font-weight:700; min-width:70px; }}
.stock-news {{ color:#374151; line-height:1.5; font-size:11px; }}
.stock-news a {{ color:#374151; }}

/* ── Footer ── */
.footer {{
  margin-top:24px; padding-top:10px; border-top:2px solid #e5e7eb;
  display:flex; justify-content:space-between; align-items:center;
  font-size:10px; color:#9ca3af;
}}
.footer-brand {{ color:#2563eb; font-weight:600; }}

/* ── Misc ── */
.divider {{ border:none; border-top:1px solid #e5e7eb; margin:16px 0; }}
.empty {{ color:#9ca3af; font-style:italic; padding:6px 0; }}
</style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
  <div class="header-left">
    <h1>📰 金融情报早报</h1>
    <div class="sub">FEISHU_NEWS · 金融情报系统 · 7×24 小时监控</div>
  </div>
  <div class="header-right">
    <div class="date-big">{date_str}</div>
    <div class="date-sub">{weekday} &nbsp;·&nbsp; 生成于 {gen_time} CST</div>
  </div>
</div>

<!-- ── Market Cards ── -->
{"<div class='mcards'>" + cards_html + "</div>" if cards_html else ""}

<!-- ── Two column: 美股 + 今日关注 ── -->
<div class="two-col">
  <div class="col-left">
    <div class="section">
      <div class="section-title">隔夜美股</div>
      <ul class="blist">{us_html}</ul>
    </div>
    <div class="section">
      <div class="section-title">宏观与政策</div>
      <ul class="blist">{macro_html}</ul>
    </div>
  </div>
  <div class="col-right">
    <div class="section">
      <div class="section-title">今日关注</div>
      <table class="watch-table">
        {watch_rows}
      </table>
    </div>
  </div>
</div>

<hr class="divider">

<!-- ── 板块情绪全览 ── -->
<div class="section">
  <div class="section-title">板块情绪全览</div>
  <table class="sent-table">
    <tr>
      <th style="width:80px">板块</th>
      <th style="width:120px">情绪评分</th>
      <th style="width:50px">变化</th>
      <th>核心驱动</th>
    </tr>
    {sent_rows}
  </table>
</div>

<hr class="divider">

<!-- ── 分板块新闻 ── -->
<div class="section">
  <div class="section-title">重要新闻（点击标题查看原文）</div>
  {sectors_html}
</div>

{stocks_section}

<!-- ── Footer ── -->
<div class="footer">
  <span><span class="footer-brand">FEISHU_NEWS</span> &nbsp;·&nbsp; 金融情报系统</span>
  <span>⚙️ {esc(str(tokens))} tokens &nbsp;·&nbsp; 本文件由系统自动生成，仅供参考，不构成投资建议</span>
</div>

</body>
</html>"""


# ──────────────────────────────────────────────────────
# PDF 生成
# ──────────────────────────────────────────────────────
def generate_pdf(html: str, out: str) -> bool:
    # 方案1：weasyprint
    try:
        from weasyprint import HTML, CSS
        HTML(string=html, base_url=None).write_pdf(out)
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[weasyprint] {e}", file=sys.stderr)

    # 方案2：pdfkit (wkhtmltopdf)
    try:
        import pdfkit
        pdfkit.from_string(html, out, options={"encoding": "utf-8", "quiet": ""})
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[pdfkit] {e}", file=sys.stderr)

    return False


# ──────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────
def main():
    data     = load_report_data()
    date_str = data.get("date", datetime.now(CST).strftime("%Y-%m-%d"))
    base     = os.path.join(REPORTS_DIR, f"{date_str}-morning-report")
    html_path = base + ".html"
    pdf_path  = base + ".pdf"

    html = build_html(data)

    # 始终保存 HTML（浏览器可直接打开）
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    if generate_pdf(html, pdf_path):
        print(f"PDF_PATH:{pdf_path}")
    else:
        print(f"HTML_PATH:{html_path}")
        print("PDF_FAILED: 请安装 weasyprint 或 pdfkit+wkhtmltopdf", file=sys.stderr)
        print("  pip install weasyprint", file=sys.stderr)


if __name__ == "__main__":
    main()
