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
        print(f"WARN: missing csv {path}")
        return pd.DataFrame()
    return pd.read_csv(path)


def read_json_safe(path: Path):
    if not path.exists():
        print(f"WARN: missing json {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_records(df: pd.DataFrame, limit=None):
    if df is None or df.empty:
        return []
    if limit:
        df = df.head(limit)
    return json.loads(df.where(pd.notnull(df), None).to_json(orient="records", force_ascii=False))


def num(x, digits=2):
    try:
        if pd.isna(x):
            return None
        return round(float(x), digits)
    except Exception:
        return None


def latest_trade_date(*dfs):
    for df in dfs:
        if df is not None and not df.empty and "trade_date" in df.columns:
            v = df["trade_date"].dropna()
            if len(v) > 0:
                return str(v.iloc[0])
    return None


company = read_csv_safe(LATEST_DIR / "company_daily.csv")
index = read_csv_safe(LATEST_DIR / "index_daily.csv")
daily_report = read_json_safe(LATEST_DIR / "daily_report.json")
summary = read_json_safe(LATEST_DIR / "longai_summary.json")

trade_date = summary.get("trade_date") or latest_trade_date(index, company) or daily_report.get("trade_date")

now_bj = datetime.utcnow() + timedelta(hours=8)
now_dubai = datetime.utcnow() + timedelta(hours=4)

# 排序准备
company_rank = company.copy()
if not company_rank.empty and "pct_chg" in company_rank.columns:
    company_rank["pct_chg"] = pd.to_numeric(company_rank["pct_chg"], errors="coerce")
    company_rank = company_rank.sort_values("pct_chg", ascending=False)

index_rank = index.copy()
if not index_rank.empty and "pct_chg" in index_rank.columns:
    index_rank["pct_chg"] = pd.to_numeric(index_rank["pct_chg"], errors="coerce")
    index_rank = index_rank.sort_values("pct_chg", ascending=False)

# 板块排行
sector_rank = pd.DataFrame()
if not company.empty and "sector" in company.columns and "pct_chg" in company.columns:
    tmp = company.copy()
    tmp["pct_chg"] = pd.to_numeric(tmp["pct_chg"], errors="coerce")
    agg = {"pct_chg": "mean"}
    if "amount_yi" in tmp.columns:
        tmp["amount_yi"] = pd.to_numeric(tmp["amount_yi"], errors="coerce")
        agg["amount_yi"] = "sum"
    if "pe_ttm" in tmp.columns:
        tmp["pe_ttm"] = pd.to_numeric(tmp["pe_ttm"], errors="coerce")
        agg["pe_ttm"] = "median"
    if "pb" in tmp.columns:
        tmp["pb"] = pd.to_numeric(tmp["pb"], errors="coerce")
        agg["pb"] = "median"

    sector_rank = tmp.groupby("sector", dropna=False).agg(agg).reset_index()
    sector_rank = sector_rank.rename(columns={
        "sector": "name",
        "pct_chg": "avg_pct_chg",
        "amount_yi": "amount_yi",
        "pe_ttm": "median_pe_ttm",
        "pb": "median_pb",
    })
    sector_rank = sector_rank.sort_values("avg_pct_chg", ascending=False)

# 核心指标
score = summary.get("longai_score")
sentiment = summary.get("sentiment")
stars = summary.get("stars")
top_sector = summary.get("top_sector")
top_company = summary.get("top_company")

# 市场概览
market = daily_report.get("market", {}) if isinstance(daily_report, dict) else {}
market_brief = {
    "trade_date": trade_date,
    "total_amount_yi": market.get("total_amount_yi"),
    "stock_count": market.get("stock_count"),
    "up_count": market.get("up_count"),
    "down_count": market.get("down_count"),
    "flat_count": market.get("flat_count"),
}

# 结论
if score is None:
    conclusion = "LongAI 数据已生成，但评分数据暂缺。"
elif score >= 75:
    conclusion = f"AI核心资产偏强，当前最强板块为 {top_sector}，领涨公司为 {top_company}。"
elif score >= 50:
    conclusion = f"AI核心资产整体中性，结构性机会主要集中在 {top_sector}。"
else:
    conclusion = f"AI核心资产偏弱，短期建议重点观察龙头修复和成交回暖。"

api = {
    "meta": {
        "name": "LongAI Daily API",
        "version": "v1",
        "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
        "generated_at_dubai": now_dubai.strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": trade_date,
        "timezone_note": "Dubai is UTC+4; Beijing is UTC+8.",
        "data_source": "Tushare Pro + GitHub Actions",
    },
    "dashboard": {
        "longai_score": score,
        "sentiment": sentiment,
        "stars": stars,
        "top_sector": top_sector,
        "top_company": top_company,
        "conclusion": conclusion,
        "score_parts": summary.get("score_parts", {}),
    },
    "market": market_brief,
    "indices": to_records(index_rank, 20),
    "sectors": to_records(sector_rank, 30),
    "companies": {
        "top_gainers": to_records(company_rank, 20),
        "top_losers": to_records(company_rank.sort_values("pct_chg", ascending=True) if not company_rank.empty and "pct_chg" in company_rank.columns else company_rank, 20),
        "all": to_records(company, None),
    },
    "files": {
        "markdown_report": "LongAI-Daily-FIX/data/latest/longai_daily.md",
        "svg_report": "LongAI-Daily-FIX/data/latest/longai_daily.svg",
        "summary_json": "LongAI-Daily-FIX/data/latest/longai_summary.json",
        "company_json": "LongAI-Daily-FIX/data/latest/company_daily.json",
        "index_json": "LongAI-Daily-FIX/data/latest/index_daily.json",
    }
}

out_api = LATEST_DIR / "api.json"
history_api = HISTORY_DIR / f"api_{trade_date}.json"

with open(out_api, "w", encoding="utf-8") as f:
    json.dump(api, f, ensure_ascii=False, indent=2)

with open(history_api, "w", encoding="utf-8") as f:
    json.dump(api, f, ensure_ascii=False, indent=2)

print(f"Generated {out_api}")
print(f"Generated {history_api}")
