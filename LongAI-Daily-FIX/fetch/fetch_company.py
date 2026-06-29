import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import tushare as ts

TOKEN = os.getenv("TUSHARE_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Missing TUSHARE_TOKEN")

ts.set_token(TOKEN)
pro = ts.pro_api()

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
HISTORY_DIR = DATA_DIR / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def call_api(fn, **kwargs):
    try:
        return fn(**kwargs)
    except Exception as e:
        print(f"WARN: {getattr(fn, '__name__', 'api_call')} failed: {kwargs} -> {e}")
        return pd.DataFrame()


def get_latest_trade_date():
    today_bj = datetime.utcnow() + timedelta(hours=8)
    end = today_bj.strftime("%Y%m%d")
    start = (today_bj - timedelta(days=20)).strftime("%Y%m%d")
    cal = call_api(pro.trade_cal, exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal.empty:
        return end
    return str(cal.sort_values("cal_date").iloc[-1]["cal_date"])


company_path = CONFIG_DIR / "company_master.csv"
companies = pd.read_csv(company_path)

trade_date = get_latest_trade_date()
now_bj = datetime.utcnow() + timedelta(hours=8)

daily = call_api(pro.daily, trade_date=trade_date)
daily_basic = call_api(
    pro.daily_basic,
    trade_date=trade_date,
    fields="ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,total_mv,circ_mv"
)

if daily.empty:
    print(f"WARN: daily is empty for {trade_date}")

if daily_basic.empty:
    print(f"WARN: daily_basic is empty for {trade_date}")

df = companies.merge(daily, on="ts_code", how="left")
df = df.merge(daily_basic, on="ts_code", how="left", suffixes=("", "_basic"))

# 统一字段，方便后续图片和日报读取
if "close_basic" in df.columns and "close" not in df.columns:
    df["close"] = df["close_basic"]

if "amount" in df.columns:
    df["amount_yi"] = pd.to_numeric(df["amount"], errors="coerce") / 100000
else:
    df["amount_yi"] = None

if "total_mv" in df.columns:
    df["total_mv_yi"] = pd.to_numeric(df["total_mv"], errors="coerce") / 10000
else:
    df["total_mv_yi"] = None

if "circ_mv" in df.columns:
    df["circ_mv_yi"] = pd.to_numeric(df["circ_mv"], errors="coerce") / 10000
else:
    df["circ_mv_yi"] = None

df["generated_at"] = now_bj.strftime("%Y-%m-%d %H:%M:%S")

# 只保留后续日报需要的核心字段
keep_cols = [
    "ts_code",
    "name",
    "sector",
    "sub_sector",
    "level",
    "country",
    "watch",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
    "amount_yi",
    "turnover_rate",
    "volume_ratio",
    "pe",
    "pe_ttm",
    "pb",
    "total_mv",
    "total_mv_yi",
    "circ_mv",
    "circ_mv_yi",
    "generated_at",
]

for col in keep_cols:
    if col not in df.columns:
        df[col] = None

df = df[keep_cols]

# 排序：先按板块，再按涨跌幅
if "pct_chg" in df.columns:
    df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
    df = df.sort_values(["sector", "pct_chg"], ascending=[True, False])

out_csv = LATEST_DIR / "company_daily.csv"
out_json = LATEST_DIR / "company_daily.json"
history_csv = HISTORY_DIR / f"company_daily_{trade_date}.csv"

df.to_csv(out_csv, index=False, encoding="utf-8-sig")
df.to_csv(history_csv, index=False, encoding="utf-8-sig")

with open(out_json, "w", encoding="utf-8") as f:
    json.dump(
        json.loads(df.where(pd.notnull(df), None).to_json(orient="records", force_ascii=False)),
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f"Generated {out_csv}")
print(f"Generated {out_json}")
print(f"Generated {history_csv}")
print(f"Rows: {len(df)}")
print(f"Trade date: {trade_date}")
