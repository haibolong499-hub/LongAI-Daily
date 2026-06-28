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
            if "涨跌" in label or "pct" in c.lower():
                vals.append(fmt_pct(v))
            elif label in ["PE", "PE(TTM)", "PB", "换手率", "市值(亿)", "成交额(亿)"]:
                vals.append(fmt_num(v, 2))
            else:
                vals.append(str(v) if pd.notna(v) else "—")
        rows.append("| " + " | ".join(vals) + " |")

    return "\n".join(rows) + "\n"


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

# 指数表
index_show = index.copy()
if not index_show.empty:
    if "pct_chg" in index_show.columns:
        index_show = index_show.sort_values("pct_chg", ascending=False)

# AI核心公司表
company_show = company.copy()
if not company_show.empty:
    if "pct_chg" in company_show.columns:
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

# 简单评分
longai_score = 50
if not company.empty and "pct_chg" in company.columns:
    up_ratio = (company["pct_chg"] > 0).mean()
    avg_pct = company["pct_chg"].mean()
    longai_score = int(max(0, min(100, 50 + up_ratio * 30 + avg_pct * 3)))

if longai_score >= 80:
    sentiment = "强"
elif longai_score >= 65:
    sentiment = "偏强"
elif longai_score >= 50:
    sentiment = "中性"
elif longai_score >= 35:
    sentiment = "偏弱"
else:
    sentiment = "弱"

md = f"""# LongAI Daily V2 Alpha

生成时间：{generated_at}  
交易日：{trade_date}

---

## 1. LongAI Dashboard

| 指标 | 结果 |
|---|---:|
| LongAI Score | {longai_score} |
| AI市场情绪 | {sentiment} |
| 数据来源 | Tushare + GitHub Actions |
| 当前版本 | V2 Alpha |

---

## 2. 指数表现与估值

{table_md(index_show, [
    ("指数", ["name"]),
    ("收盘", ["close"]),
    ("涨跌幅", ["pct_chg"]),
    ("PE", ["pe"]),
    ("PE(TTM)", ["pe_ttm"]),
    ("PB", ["pb"]),
], 12)}

---

## 3. AI产业链板块表现

{table_md(sector_summary, [
    ("板块", ["板块"]),
    ("平均涨跌幅", ["平均涨跌幅"]),
    ("成交额(亿)", ["成交额"]),
    ("PE(TTM)", ["PE_TTM中位数"]),
    ("PB", ["PB中位数"]),
], 20)}

---

## 4. AI Core 公司涨幅榜

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

## 5. AI Core 公司跌幅榜

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

## 6. 今日结论

当前 LongAI Score 为 **{longai_score}**，AI市场情绪判断为 **{sentiment}**。

本版本已经完成：
- 自动抓取指数行情与估值
- 自动抓取 AI Core 公司行情与估值
- 自动生成 Markdown 日报

下一步建议接入：
- 财务数据：ROE、毛利率、营收同比、净利润同比
- 资金数据：主力资金、龙虎榜、两融
- 图片日报：自动生成 PNG
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
    "company_rows": len(company),
    "index_rows": len(index),
}

with open(out_json, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"Generated {out_md}")
print(f"Generated {history_md}")
print(f"Generated {out_json}")
