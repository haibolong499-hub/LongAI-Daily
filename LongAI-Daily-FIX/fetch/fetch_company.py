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
LATEST_DIR = ROOT / "data" / "latest"
HISTORY_DIR = ROOT / "data" / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def call_api(fn, **kwargs):
    for i in range(3):
        try:
            return fn(**kwargs)
        except Exception as e:
            print(f"WARN retry {i+1}: {e}")
            time.sleep(2 * (i + 1))
    return pd.DataFrame()


def get_latest_trade_date():
    today = datetime.utcnow() + timedelta(hours=8)
    for i in range(10):
        d = (today - timedelta(days=i)).strftime("%Y%m%d")
        test = call_api(pro.daily, trade_date=d)
        if not test.empty:
            return d
    return today.strftime("%Y%m%d")


trade_date = get_latest_trade_date()

companies = pd.read_csv(CONFIG_DIR / "company_master.csv")

daily = call_api(pro.daily, trade_date=trade_date)
daily_basic = call_api(
    pro.daily_basic,
    trade_date=trade_date,
    fields="ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,total_mv,circ_mv"
)

df = companies.merge(daily, on="ts_code", how="left")
df = df.merge(daily_basic, on="ts_code", how="left", suffixes=("", "_basic"))

# 单位处理：Tushare amount 单位为千元，转亿元；市值单位万元，转亿元
if "amount" in df.columns:
    df["amount_yi"] = pd.to_numeric(df["amount"], errors="coerce") / 100000

if "total_mv" in df.columns:
    df["total_mv_yi"] = pd.to_numeric(df["total_mv"], errors="coerce") / 10000

if "circ_mv" in df.columns:
    df["circ_mv_yi"] = pd.to_numeric(df["circ_mv"], errors="coerce") / 10000

df["generated_at_beijing"] = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
df["generated_at_dubai"] = (datetime.utcnow() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

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

print(f"trade_date={trade_date}")
print(f"Generated {out_csv}")
print(f"Generated {out_json}")
print(f"Generated {history_csv}")
