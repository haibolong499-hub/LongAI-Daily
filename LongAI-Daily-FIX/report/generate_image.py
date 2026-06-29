import html
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
HISTORY_DIR = DATA_DIR / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def read_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_pct(x):
    try:
        if pd.isna(x):
            return "—"
        x = float(x)
        sign = "+" if x > 0 else ""
        return f"{sign}{x:.2f}%"
    except Exception:
        return "—"


def fmt_num(x, digits=2):
    try:
        if pd.isna(x):
            return "—"
        return f"{float(x):,.{digits}f}"
    except Exception:
        return "—"


def esc(x):
    return html.escape(str(x)) if x is not None else "—"


def color_pct(x):
    try:
        x = float(x)
        if x > 0:
            return "#E53935"
        if x < 0:
            return "#1B8F3A"
        return "#334155"
    except Exception:
        return "#334155"


company = read_csv_safe(LATEST_DIR / "company_daily.csv")
index = read_csv_safe(LATEST_DIR / "index_daily.csv")
summary = read_json_safe(LATEST_DIR / "longai_summary.json")

score = int(summary.get("longai_score", 0) or 0)
sentiment = summary.get("sentiment", "未知")
stars = summary.get("stars", "—")
top_sector = summary.get("top_sector", "—")
top_company = summary.get("top_company", "—")
trade_date = str(summary.get("trade_date", "未知"))

now_bj = datetime.utcnow() + timedelta(hours=8)
now_dubai = datetime.utcnow() + timedelta(hours=4)

# 指数 Top
index_rows = []
if not index.empty:
    show = index.copy()
    if "pct_chg" in show.columns:
        show = show.sort_values("pct_chg", ascending=False)
    for _, r in show.head(6).iterrows():
        index_rows.append({
            "name": r.get("name", "—"),
            "pct": r.get("pct_chg"),
            "pe": r.get("pe_ttm", r.get("pe", None)),
            "pb": r.get("pb", None),
        })

# 公司 Top
company_rows = []
if not company.empty:
    show = company.copy()
    if "pct_chg" in show.columns:
        show = show.sort_values("pct_chg", ascending=False)
    for _, r in show.head(8).iterrows():
        company_rows.append({
            "name": r.get("name", "—"),
            "sector": r.get("sector", "—"),
            "pct": r.get("pct_chg"),
            "pe": r.get("pe_ttm", r.get("pe", None)),
            "pb": r.get("pb", None),
        })

# 板块统计
sector_rows = []
if not company.empty and "sector" in company.columns and "pct_chg" in company.columns:
    tmp = company.copy()
    tmp["pct_chg"] = pd.to_numeric(tmp["pct_chg"], errors="coerce")
    sec = tmp.groupby("sector", dropna=False)["pct_chg"].mean().reset_index()
    sec = sec.sort_values("pct_chg", ascending=False)
    for _, r in sec.head(6).iterrows():
        sector_rows.append({"sector": r.get("sector", "—"), "pct": r.get("pct_chg")})

if score >= 75:
    conclusion = f"AI核心资产偏强，{top_sector}表现领先，{top_company}领涨。"
elif score >= 50:
    conclusion = f"AI核心资产整体中性，结构性机会集中在{top_sector}。"
else:
    conclusion = f"AI核心资产偏弱，短期关注龙头修复与成交回暖。"

# SVG helpers
def text(x, y, content, size=28, weight="400", fill="#0F172A", anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(content)}</text>'


def card(x, y, w, h, title):
    return f'''
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="#FFFFFF" stroke="#D9E2F2"/>
    <text x="{x+28}" y="{y+48}" font-size="28" font-weight="800" fill="#123C8C">{esc(title)}</text>
    '''


def row_text(x, y, name, value, value_color="#0F172A", sub=None):
    s = text(x, y, name, 24, "600", "#334155")
    s += text(x + 330, y, value, 24, "800", value_color, "end")
    if sub:
        s += text(x + 345, y, sub, 20, "500", "#64748B")
    return s


svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#F8FBFF"/>
      <stop offset="100%" stop-color="#EAF2FF"/>
    </linearGradient>
    <linearGradient id="blue" x1="0" x2="1">
      <stop offset="0%" stop-color="#0B3B8C"/>
      <stop offset="100%" stop-color="#1976D2"/>
    </linearGradient>
  </defs>

  <rect width="1080" height="1920" fill="url(#bg)"/>
  <rect x="0" y="0" width="1080" height="250" fill="url(#blue)"/>
  <circle cx="930" cy="90" r="90" fill="#FFFFFF" opacity="0.08"/>
  <circle cx="1010" cy="190" r="130" fill="#FFFFFF" opacity="0.06"/>

  {text(56, 90, "LongAI Daily", 64, "900", "#FFFFFF")}
  {text(60, 135, "AI投研日报｜真实数据自动生成", 28, "500", "#DCEBFF")}
  {text(60, 182, f"交易日：{trade_date}", 24, "600", "#FFFFFF")}
  {text(1020, 92, "AI", 54, "900", "#FFFFFF", "end")}

  <rect x="50" y="290" width="980" height="230" rx="28" fill="#FFFFFF" stroke="#D9E2F2"/>
  {text(90, 350, "LongAI Score", 34, "800", "#123C8C")}
  {text(90, 440, str(score), 82, "900", "#0B3B8C")}
  {text(260, 430, stars, 34, "800", "#F59E0B")}
  {text(260, 470, f"AI市场情绪：{sentiment}", 26, "700", "#334155")}
  <rect x="720" y="340" width="250" height="82" rx="18" fill="#EFF6FF"/>
  {text(845, 392, top_sector, 32, "800", "#123C8C", "middle")}
  {text(845, 455, "最强板块", 22, "600", "#64748B", "middle")}

  <rect x="50" y="550" width="980" height="150" rx="28" fill="#FFFFFF" stroke="#D9E2F2"/>
  {text(90, 610, "今日核心观点", 30, "800", "#123C8C")}
  {text(90, 662, conclusion, 27, "700", "#0F172A")}

  {card(50, 735, 475, 360, "指数表现与估值")}
'''

y = 820
for r in index_rows:
    name = r["name"]
    pct = r["pct"]
    pe = r["pe"]
    pb = r["pb"]
    svg += row_text(88, y, name, fmt_pct(pct), color_pct(pct))
    svg += text(88, y + 34, f"PE {fmt_num(pe)}  PB {fmt_num(pb)}", 19, "500", "#64748B")
    y += 52

svg += card(555, 735, 475, 360, "AI产业链热度")
y = 820
for r in sector_rows:
    pct = r["pct"]
    svg += row_text(595, y, r["sector"], fmt_pct(pct), color_pct(pct))
    y += 52

svg += card(50, 1125, 980, 500, "AI Core 龙头公司")
y = 1210
for r in company_rows:
    pct = r["pct"]
    svg += text(88, y, r["name"], 24, "800", "#0F172A")
    svg += text(260, y, r["sector"], 20, "600", "#64748B")
    svg += text(500, y, fmt_pct(pct), 24, "900", color_pct(pct), "end")
    svg += text(720, y, f"PE {fmt_num(r['pe'])}", 22, "700", "#334155", "end")
    svg += text(950, y, f"PB {fmt_num(r['pb'])}", 22, "700", "#334155", "end")
    y += 46

svg += f'''
  <rect x="50" y="1660" width="980" height="150" rx="28" fill="#0B3B8C"/>
  {text(90, 1725, "数据说明", 28, "800", "#FFFFFF")}
  {text(90, 1768, "数据来源：Tushare Pro + GitHub Actions；本报告自动生成，仅供研究参考。", 22, "500", "#DCEBFF")}
  {text(90, 1805, f"北京时间：{now_bj.strftime('%Y-%m-%d %H:%M')}｜迪拜时间：{now_dubai.strftime('%Y-%m-%d %H:%M')}", 22, "500", "#DCEBFF")}

  {text(540, 1875, "LongAI Daily · AI驱动 · 数据先行", 24, "800", "#123C8C", "middle")}
</svg>
'''

out_svg = LATEST_DIR / "longai_daily.svg"
history_svg = HISTORY_DIR / f"longai_daily_{trade_date}.svg"

with open(out_svg, "w", encoding="utf-8") as f:
    f.write(svg)

with open(history_svg, "w", encoding="utf-8") as f:
    f.write(svg)

print(f"Generated {out_svg}")
print(f"Generated {history_svg}")
