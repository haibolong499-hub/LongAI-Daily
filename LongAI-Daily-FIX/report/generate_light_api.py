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


def read_json_safe(path: Path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def to_records(df: pd.DataFrame, limit=None):
    if df.empty:
        return []
    if limit:
        df = df.head(limit)
    return json.loads(df.where(pd.notnull(df), None).to_json(orient="records", force_ascii=False))


def write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


now_bj = datetime.utcnow() + timedelta(hours=8)
now_dubai = datetime.utcnow() + timedelta(hours=4)

api = read_json_safe(LATEST_DIR / "api.json")
summary = read_json_safe(LATEST_DIR / "longai_summary.json")
company = read_csv_safe(LATEST_DIR / "company_daily.csv")
index = read_csv_safe(LATEST_DIR / "index_daily.csv")

meta = api.get("meta", {})
dashboard = api.get("dashboard", {})
market = api.get("market", {})

# 1. summary.json：最轻量入口
summary_light = {
    "name": "LongAI Summary",
    "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    "generated_at_dubai": now_dubai.strftime("%Y-%m-%d %H:%M:%S"),
    "trade_date": meta.get("trade_date") or summary.get("trade_date"),
    "longai_score": dashboard.get("longai_score") or summary.get("longai_score"),
    "sentiment": dashboard.get("sentiment") or summary.get("sentiment"),
    "stars": dashboard.get("stars") or summary.get("stars"),
    "top_sector": dashboard.get("top_sector") or summary.get("top_sector"),
    "top_company": dashboard.get("top_company") or summary.get("top_company"),
    "conclusion": dashboard.get("conclusion"),
    "market": market,
    "links": {
        "api": "LongAI-Daily-FIX/data/latest/api.json",
        "company_top": "LongAI-Daily-FIX/data/latest/company_top.json",
        "index_brief": "LongAI-Daily-FIX/data/latest/index_brief.json",
        "sector_brief": "LongAI-Daily-FIX/data/latest/sector_brief.json",
        "history_index": "LongAI-Daily-FIX/data/latest/history_index.json",
        "svg_report": "LongAI-Daily-FIX/data/latest/longai_daily.svg",
    }
}

# 2. company_top.json
company_top = {
    "name": "LongAI Company Top",
    "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    "trade_date": summary_light.get("trade_date"),
    "top_gainers": [],
    "top_losers": [],
}

if not company.empty and "pct_chg" in company.columns:
    company["pct_chg"] = pd.to_numeric(company["pct_chg"], errors="coerce")
    company_top["top_gainers"] = to_records(company.sort_values("pct_chg", ascending=False), 20)
    company_top["top_losers"] = to_records(company.sort_values("pct_chg", ascending=True), 20)
else:
    company_top["all"] = to_records(company, 20)

# 3. index_brief.json
index_brief = {
    "name": "LongAI Index Brief",
    "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    "trade_date": summary_light.get("trade_date"),
    "indices": [],
}

if not index.empty and "pct_chg" in index.columns:
    index["pct_chg"] = pd.to_numeric(index["pct_chg"], errors="coerce")
    index_brief["indices"] = to_records(index.sort_values("pct_chg", ascending=False), 20)
else:
    index_brief["indices"] = to_records(index, 20)

# 4. sector_brief.json
sector_brief = {
    "name": "LongAI Sector Brief",
    "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
    "trade_date": summary_light.get("trade_date"),
    "sectors": [],
}

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

    sector_df = tmp.groupby("sector", dropna=False).agg(agg).reset_index()
    sector_df = sector_df.rename(columns={
        "sector": "name",
        "pct_chg": "avg_pct_chg",
        "amount_yi": "amount_yi",
        "pe_ttm": "median_pe_ttm",
        "pb": "median_pb",
    })
    sector_df = sector_df.sort_values("avg_pct_chg", ascending=False)
    sector_brief["sectors"] = to_records(sector_df, 30)

write_json(LATEST_DIR / "summary.json", summary_light)
write_json(LATEST_DIR / "company_top.json", company_top)
write_json(LATEST_DIR / "index_brief.json", index_brief)
write_json(LATEST_DIR / "sector_brief.json", sector_brief)

# 历史也保存一份 summary，方便后续做趋势
trade_date = summary_light.get("trade_date") or now_bj.strftime("%Y%m%d")
write_json(HISTORY_DIR / f"summary_{trade_date}.json", summary_light)

print("Generated light APIs:")
print(LATEST_DIR / "summary.json")
print(LATEST_DIR / "company_top.json")
print(LATEST_DIR / "index_brief.json")
print(LATEST_DIR / "sector_brief.json")
