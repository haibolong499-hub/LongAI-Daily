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
        print(f"WARN: missing file {path}")
        return pd.DataFrame()
    return pd.read_csv(path)


def to_num(s):
    try:
        return pd.to_numeric(s, errors="coerce")
    except Exception:
        return s


def fmt_num(x, digits=2):
    try:
        if pd.isna(x):
            return "—"
        return f"{float(x):,.{digits}f}"
    except Exception:
        return "—"


def fmt_pct(x):
    try:
        if pd.isna(x):
            return "—"
        x = float(x)
        sign = "+" if x > 0 else ""
        return f"{sign}{x:.2f}%"
    except Exception:
        return "—"


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def table_md(df: pd.DataFrame, columns, limit=10):
    if df.empty:
        return "暂无数据\n"

    real_cols = []
    for label, candidates in columns:
        c = pick_col(df, candidates)
        if c:
            real_cols.append((label, c))

    if not real_cols:
        return "暂无可展示字段\n"

    rows = []
    rows.append("| " + " | ".join([x[0] for x in real_cols]) + " |")
    rows.append("| " + " | ".join(["---"] * len(real_cols)) + " |")

    for _, r in df.head(limit).iterrows():
        vals = []
        for label, c in real_cols:
            v = r.get(c)
            lc = c.lower()
            if "涨跌" in label or "pct" in lc:
                vals.append(fmt_pct(v))
            elif label in ["PE", "PE(TTM)", "PB", "换手率", "市值(亿)", "成交额(亿)", "收盘"]:
                vals.append(fmt_num(v, 2))
            else:
                vals.append(str(v) if pd.notna(v) else "—")
        rows.append("| " + " | ".join(vals) + " |")

    return "\n".join(rows) + "\n"


def score_to_text(score):
    if score >= 85:
        return "极强"
    if score >= 75:
        return "强"
    if score >= 65:
        return "偏强"
    if score >= 50:
        return "中性"
    if score >= 35:
        return "偏弱"
    return "弱"


def score_to_stars(score):
    if score >= 85:
        return "★★★★★"
    if score >= 70:
        return "★★★★☆"
    if score >= 55:
        return "★★★☆☆"
    if score >= 40:
        return "★★☆☆☆"
    return "★☆☆☆☆"


company = read_csv_safe(LATEST_DIR / "company_daily.csv")
index = read_csv_safe(LATEST_DIR / "index_daily.csv")

now_bj = datetime.utcnow() + timedelta(hours=8)
generated_at = now_bj.strftime("%Y-%m-%d %H:%M:%S")

trade_date = "未知"
for df in [index, company]:
    if not df.empty and "trade_date" in df.columns:
        val = df["trade_date"].dropna()
        if len(val) > 0:
            trade_date = str(val.iloc[0])
            break

# 数值列处理
for df in [company, index]:
    if not df.empty:
        for col in df.columns:
            if col not in ["ts_code", "name", "sector", "sub_sector", "level", "country", "watch", "trade_date", "generated_at"]:
                df[col] = to_num(df[col])

# 指数排序
index_show = index.copy()
if not index_show.empty and "pct_chg" in index_show.columns:
    index_show = index_show.sort_values("pct_chg", ascending=False)

# 公司排序
company_show = company.copy()
if not company_show.empty and "pct_chg" in company_show.columns:
    company_show = company_show.sort_values("pct_chg", ascending=False)

# 板块统计
sector_summary = pd.DataFrame()
if not company.empty and "sector" in company.columns:
    agg = {}
    if "pct_chg" in company.columns:
        agg["pct_chg"] = "mean"
    if "amount" in company.columns:
        agg["amount"] = "sum"
    if "pe_ttm" in company.columns:
        agg["pe_ttm"] = "median"
    if "pb" in company.columns:
        agg["pb"] = "median"

    if agg:
        sector_summary = company.groupby("sector", dropna=False).agg(agg).reset_index()
        sector_summary = sector_summary.rename(columns={
            "sector": "板块",
            "pct_chg": "平均涨跌幅",
            "amount": "成交额",
            "pe_ttm": "PE_TTM中位数",
            "pb": "PB中位数",
        })
        if "成交额" in sector_summary.columns:
            sector_summary["成交额"] = sector_summary["成交额"] / 100000
        if "平均涨跌幅" in sector_summary.columns:
            sector_summary = sector_summary.sort_values("平均涨跌幅", ascending=False)

# 真实 LongAI Score
score_parts = {}

if not company.empty and "pct_chg" in company.columns:
    valid_pct = company["pct_chg"].dropna()
    if len(valid_pct) > 0:
        up_ratio = (valid_pct > 0).mean()
        avg_pct = valid_pct.mean()
        score_parts["公司上涨比例"] = min(30, max(0, up_ratio * 30))
        score_parts["公司平均涨跌"] = min(25, max(0, 12.5 + avg_pct * 4))
    else:
        score_parts["公司上涨比例"] = 15
        score_parts["公司平均涨跌"] = 12
else:
    score_parts["公司上涨比例"] = 15
    score_parts["公司平均涨跌"] = 12

if not index.empty and "pct_chg" in index.columns:
    idx_pct = index["pct_chg"].dropna()
    if len(idx_pct) > 0:
        idx_avg = idx_pct.mean()
        score_parts["指数环境"] = min(20, max(0, 10 + idx_avg * 4))
    else:
        score_parts["指数环境"] = 10
else:
    score_parts["指数环境"] = 10

if not sector_summary.empty and "平均涨跌幅" in sector_summary.columns:
    sec_pct = sector_summary["平均涨跌幅"].dropna()
    if len(sec_pct) > 0:
        best_sector = sec_pct.max()
        score_parts["板块强度"] = min(15, max(0, 7.5 + best_sector * 3))
    else:
        score_parts["板块强度"] = 7
else:
    score_parts["板块强度"] = 7

if not company.empty and "amount" in company.columns:
    total_amount_yi = company["amount"].fillna(0).sum() / 100000
    score_parts["成交活跃度"] = min(10, max(0, total_amount_yi / 50))
else:
    total_amount_yi = None
    score_parts["成交活跃度"] = 5

longai_score = int(round(sum(score_parts.values())))
longai_score = max(0, min(100, longai_score))

sentiment = score_to_text(longai_score)
stars = score_to_stars(longai_score)

# 结论生成
top_sector = "暂无"
top_sector_pct = None
if not sector_summary.empty and "平均涨跌幅" in sector_summary.columns:
    top_row = sector_summary.iloc[0]
    top_sector = str(top_row.get("板块", "暂无"))
    top_sector_pct = top_row.get("平均涨跌幅")

top_company = "暂无"
top_company_pct = None
if not company_show.empty and "pct_chg" in company_show.columns:
    top_row = company_show.iloc[0]
    top_company = str(top_row.get("name", "暂无"))
    top_company_pct = top_row.get("pct_chg")

if longai_score >= 75:
    conclusion = f"AI核心资产整体偏强，当前最强板块为 {top_sector}，领涨公司为 {top_company}。"
elif longai_score >= 50:
    conclusion = f"AI核心资产整体中性偏稳，当前结构性机会主要集中在 {top_sector}。"
else:
    conclusion = f"AI核心资产整体偏弱，短期建议重点观察成交额与龙头修复情况。"

md = f"""# LongAI Daily V3

生成时间：{generated_at}  
交易日：{trade_date}

---

## 1. LongAI Dashboard

| 指标 | 结果 |
|---|---:|
| LongAI Score | {longai_score} |
| AI市场情绪 | {sentiment} |
| 情绪星级 | {stars} |
| 最强板块 | {top_sector} |
| 领涨公司 | {top_company} |
| 数据来源 | Tushare + GitHub Actions |
| 当前版本 | V3 Real Score |

---

## 2. 今日核心观点

**{conclusion}**

评分拆解：

| 因子 | 分数 |
|---|---:|
| 公司上涨比例 | {fmt_num(score_parts.get("公司上涨比例"), 1)} / 30 |
| 公司平均涨跌 | {fmt_num(score_parts.get("公司平均涨跌"), 1)} / 25 |
| 指数环境 | {fmt_num(score_parts.get("指数环境"), 1)} / 20 |
| 板块强度 | {fmt_num(score_parts.get("板块强度"), 1)} / 15 |
| 成交活跃度 | {fmt_num(score_parts.get("成交活跃度"), 1)} / 10 |

---

## 3. 指数表现与估值

{table_md(index_show, [
    ("指数", ["name"]),
    ("收盘", ["close"]),
    ("涨跌幅", ["pct_chg"]),
    ("PE", ["pe"]),
    ("PE(TTM)", ["pe_ttm"]),
    ("PB", ["pb"]),
], 12)}

---

## 4. AI产业链板块表现

{table_md(sector_summary, [
    ("板块", ["板块"]),
    ("平均涨跌幅", ["平均涨跌幅"]),
    ("成交额(亿)", ["成交额"]),
    ("PE(TTM)", ["PE_TTM中位数"]),
    ("PB", ["PB中位数"]),
], 20)}

---

## 5. AI Core 公司涨幅榜

{table_md(company_show, [
    ("公司", ["name"]),
    ("代码", ["ts_code"]),
    ("板块", ["sector"]),
    ("细分", ["sub_sector"]),
    ("涨跌幅", ["pct_chg"]),
    ("PE(TTM)", ["pe_ttm"]),
    ("PB", ["pb"]),
    ("市值(亿)", ["total_mv"]),
], 15)}

---

## 6. AI Core 公司跌幅榜

{table_md(company.sort_values("pct_chg", ascending=True) if not company.empty and "pct_chg" in company.columns else company, [
    ("公司", ["name"]),
    ("代码", ["ts_code"]),
    ("板块", ["sector"]),
    ("细分", ["sub_sector"]),
    ("涨跌幅", ["pct_chg"]),
    ("PE(TTM)", ["pe_ttm"]),
    ("PB", ["pb"]),
    ("市值(亿)", ["total_mv"]),
], 15)}

---

## 7. 下一步计划

- 接入财务数据：ROE、毛利率、营收同比、净利润同比
- 接入资金数据：主力资金、龙虎榜、两融
- 自动生成 PNG 图片日报
"""

out_md = LATEST_DIR / "longai_daily.md"
out_json = LATEST_DIR / "longai_summary.json"
history_md = HISTORY_DIR / f"longai_daily_{trade_date}.md"

with open(out_md, "w", encoding="utf-8") as f:
    f.write(md)

with open(history_md, "w", encoding="utf-8") as f:
    f.write(md)

summary = {
    "generated_at": generated_at,
    "trade_date": trade_date,
    "longai_score": longai_score,
    "sentiment": sentiment,
    "stars": stars,
    "top_sector": top_sector,
    "top_company": top_company,
    "company_rows": len(company),
    "index_rows": len(index),
    "score_parts": score_parts,
}

with open(out_json, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"Generated {out_md}")
print(f"Generated {history_md}")
print(f"Generated {out_json}")
