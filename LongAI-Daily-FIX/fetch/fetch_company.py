import os
import json
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

company_path = CONFIG_DIR / "company_master.csv"
companies = pd.read_csv(company_path)

today = datetime.utcnow() + timedelta(hours=8)
trade_date = today.strftime("%Y%m%d")

daily = pro.daily(trade_date=trade_date)
daily_basic = pro.daily_basic(
    trade_date=trade_date,
    fields="ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,total_mv,circ_mv"
)

df = companies.merge(daily, on="ts_code", how="left")
df = df.merge(daily_basic, on="ts_code", how="left", suffixes=("", "_basic"))

df["generated_at"] = today.strftime("%Y-%m-%d %H:%M:%S")

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
