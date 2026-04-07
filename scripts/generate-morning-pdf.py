#!/usr/bin/env python3
"""
早报 PDF 生成脚本
输入：从 stdin 读取早报 JSON 数据
输出：PDF 文件路径（stdout 最后一行）

依赖（按优先级）：
  1. weasyprint  → pip install weasyprint
  2. fpdf2       → pip install fpdf2
安装：pip install weasyprint || pip install fpdf2
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

WORKSPACE   = os.path.expanduser("~/.openclaw/workspace")
REPORTS_DIR = os.path.join(WORKSPACE, "reports")
CST         = timezone(timedelta(hours=8))

os.makedirs(REPORTS_DIR, exist_ok=True)


# ─────────────────────────────────────────
# 读取输入
# ─────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_report_data():
    """从 stdin 读取早报 JSON，或回退到读取工作区文件"""
    if not sys.stdin.isatty():
        try:
            return json.load(sys.stdin)
        except Exception:
            pass
    # fallback：直接读工作区
    return {
        "sentiment": load_json(os.path.join(WORKSPACE, "sentiment-snapshot.json"), {}),
        "filtered":  load_json(os.path.join(WORKSPACE, "filtered-news.json"), []),
        "date":      datetime.now(CST).strftime("%Y-%m-%d"),
        "tokens":    "~",
    }


# ─────────────────────────────────────────
# HTML 模板
# ─────────────────────────────────────────
def build_html(data: dict) -> str:
    date_str  = data.get("date", datetime.now(CST).strftime("%Y-%m-%d"))
    gen_time  = datetime.now(CST).strftime("%H:%M")
    tokens    = data.get("tokens", "~")

    # ── 板块情绪表格行 ──
    sentiment = data.get("sentiment", {})
    sentiment_rows = ""
    for sector, info in sentiment.items():
        score = info.get("score", 50)
        delta = info.get("delta", 0)
        top   = info.get("top_signal", "")
        if score >= 60:
            color, icon = "#16a34a", "🟢"
        elif score >= 40:
            color, icon = "#d97706", "🟡"
        else:
            color, icon = "#dc2626", "🔴"
        if delta > 3:
            d_str = f"<span style='color:#16a34a'>↑{abs(delta)}</span>"
        elif delta < -3:
            d_str = f"<span style='color:#dc2626'>↓{abs(delta)}</span>"
        else:
            d_str = "<span style='color:#6b7280'>→</span>"
        sentiment_rows += f"""
        <tr>
          <td>{icon} {sector}</td>
          <td style="font-weight:700;color:{color}">{score}</td>
          <td>{d_str}</td>
          <td style="color:#374151">{top}</td>
        </tr>"""

    # ── 重要新闻列表 ──
    top_news   = data.get("top_news", [])
    news_items = ""
    for i, item in enumerate(top_news, 1):
        sector  = item.get("sector", "")
        title   = item.get("title", "")
        url     = item.get("url", "#")
        source  = item.get("source", "")
        ts      = item.get("time", "")
        news_items += f"""
        <div class="news-row">
          <span class="num">{i}</span>
          <div class="news-body">
            <div>
              <span class="tag">{sector}</span>
              <a href="{url}" class="title">{title}</a>
            </div>
            <div class="meta">{source} · {ts}</div>
          </div>
        </div>"""
    if not news_items:
        # fallback：取 filtered-news 最新10条
        filtered = data.get("filtered", [])[-10:]
        for i, item in enumerate(filtered, 1):
            url   = item.get("url", "#")
            title = item.get("title", "")
            src   = item.get("source", "")
            ts    = item.get("ts", "")[:16].replace("T", " ")
            news_items += f"""
        <div class="news-row">
          <span class="num">{i}</span>
          <div class="news-body">
            <div><a href="{url}" class="title">{title}</a></div>
            <div class="meta">{src} · {ts}</div>
          </div>
        </div>"""

    # ── 隔夜美股 / 今日关注 ──
    def list_html(items):
        return "".join(f"<li>{x}</li>" for x in items) if items else "<li>暂无数据</li>"

    us_html   = list_html(data.get("us_market", []))
    watch_html= list_html(data.get("watch_today", []))

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif;
     font-size:13px;color:#111827;background:#fff;padding:36px 40px}}

/* Header */
.header{{display:flex;justify-content:space-between;align-items:flex-end;
         border-bottom:2.5px solid #2563eb;padding-bottom:14px;margin-bottom:28px}}
.header h1{{font-size:20px;font-weight:700;color:#2563eb}}
.header .sub{{font-size:11px;color:#6b7280;margin-top:4px}}
.header .meta{{font-size:11px;color:#9ca3af;text-align:right}}

/* Section */
.section{{margin-bottom:26px}}
.section-title{{font-size:13px;font-weight:700;color:#1e3a8a;
               border-left:3px solid #2563eb;padding-left:8px;margin-bottom:12px}}

/* Lists */
ul.bullet{{list-style:none}}
ul.bullet li{{padding:4px 0 4px 16px;position:relative;line-height:1.65;color:#374151}}
ul.bullet li::before{{content:"•";position:absolute;left:0;color:#2563eb;font-weight:700}}

/* Sentiment table */
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#eff6ff;color:#1e40af;font-weight:600;
   padding:7px 10px;text-align:left;border-bottom:1.5px solid #bfdbfe}}
td{{padding:7px 10px;border-bottom:1px solid #f3f4f6;vertical-align:top;color:#374151}}

/* News */
.news-row{{display:flex;gap:10px;padding:10px 0;
           border-bottom:1px solid #f3f4f6;align-items:flex-start}}
.num{{min-width:20px;height:20px;background:#2563eb;color:#fff;border-radius:50%;
      font-size:10px;font-weight:700;display:flex;align-items:center;
      justify-content:center;flex-shrink:0;margin-top:2px}}
.news-body{{flex:1}}
.tag{{display:inline-block;background:#eff6ff;color:#2563eb;
      font-size:10px;padding:1px 5px;border-radius:3px;margin-right:5px;
      font-weight:500;white-space:nowrap}}
a.title{{color:#111827;text-decoration:none;font-weight:500;line-height:1.55}}
a.title:hover{{color:#2563eb;text-decoration:underline}}
.meta{{font-size:11px;color:#9ca3af;margin-top:3px}}

/* Footer */
.footer{{margin-top:30px;padding-top:12px;border-top:1px solid #e5e7eb;
         display:flex;justify-content:space-between;font-size:11px;color:#9ca3af}}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>📰 金融情报早报</h1>
    <div class="sub">FEISHU_NEWS · 金融情报系统</div>
  </div>
  <div class="meta">{date_str}<br>生成于 {gen_time} CST</div>
</div>

<div class="section">
  <div class="section-title">隔夜美股</div>
  <ul class="bullet">{us_html}</ul>
</div>

<div class="section">
  <div class="section-title">今日关注</div>
  <ul class="bullet">{watch_html}</ul>
</div>

<div class="section">
  <div class="section-title">板块情绪</div>
  <table>
    <tr><th>板块</th><th>评分</th><th>变化</th><th>核心信号</th></tr>
    {sentiment_rows if sentiment_rows else '<tr><td colspan="4" style="color:#9ca3af">暂无情绪数据</td></tr>'}
  </table>
</div>

<div class="section">
  <div class="section-title">重要新闻（点击标题查看原文）</div>
  {news_items if news_items else '<div style="color:#9ca3af;padding:8px 0">暂无新闻数据</div>'}
</div>

<div class="footer">
  <span>金融情报系统 · FEISHU_NEWS</span>
  <span>⚙️ {tokens} tokens</span>
</div>

</body>
</html>"""


# ─────────────────────────────────────────
# PDF 生成
# ─────────────────────────────────────────
def generate_pdf(html: str, output_path: str) -> bool:
    # 方案1：weasyprint
    try:
        from weasyprint import HTML
        HTML(string=html, base_url=None).write_pdf(output_path)
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[weasyprint error] {e}", file=sys.stderr)

    # 方案2：fpdf2（纯文本回退，无链接样式）
    try:
        from fpdf import FPDF
        data = _extract_text_for_fpdf(html)
        pdf = FPDF()
        pdf.add_page()
        # 尝试加载中文字体（用户系统可能有）
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        font_loaded = False
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    pdf.add_font("CJK", "", fp, uni=True)
                    font_loaded = True
                    break
                except Exception:
                    pass
        if font_loaded:
            pdf.set_font("CJK", size=11)
        else:
            pdf.set_font("Helvetica", size=11)
        for line in data:
            pdf.multi_cell(0, 7, txt=line)
        pdf.output(output_path)
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[fpdf2 error] {e}", file=sys.stderr)

    return False


def _extract_text_for_fpdf(html: str) -> list:
    """从 HTML 粗略提取纯文本行（fpdf fallback 用）"""
    import re
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&nbsp;', ' ', text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines


# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
def main():
    data     = load_report_data()
    date_str = data.get("date", datetime.now(CST).strftime("%Y-%m-%d"))
    filename = f"{date_str}-morning-report.pdf"
    out_path = os.path.join(REPORTS_DIR, filename)

    # 同时保存 HTML（便于调试 / 浏览器查看）
    html_path = out_path.replace(".pdf", ".html")
    html = build_html(data)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    ok = generate_pdf(html, out_path)
    if ok:
        print(f"PDF_PATH:{out_path}")
    else:
        # PDF 生成失败，至少有 HTML 版本
        print(f"HTML_PATH:{html_path}")
        print("PDF_FAILED: 请安装 weasyprint 或 fpdf2", file=sys.stderr)


if __name__ == "__main__":
    main()
