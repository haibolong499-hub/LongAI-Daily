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
DATA_DIR = ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
HISTORY_DIR = DATA_DIR / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def get_trade_date():
    today = datetime.utcnow() + timedelta(hours=8)
    end = today.strftime("%Y%m%d")
    start = (today - timedelta(days=20)).strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal.empty:
        return end
    return str(cal.sort_values("cal_date").iloc[-1]["cal_date"])


trade_date = get_trade_date()

index_list = [
    {"ts_code": "000001.SH", "name": "上证指数"},
    {"ts_code": "000016.SH", "name": "上证50"},
    {"ts_code": "000300.SH", "name": "沪深300"},
    {"ts_code": "000905.SH", "name": "中证500"},
    {"ts_code": "000852.SH", "name": "中证1000"},
    {"ts_code": "000688.SH", "name": "科创50"},
    {"ts_code": "399001.SZ", "name": "深证成指"},
    {"ts_code": "399006.SZ", "name": "创业板指"},
]

rows = []

for item in index_list:
    code = item["ts_code"]
    name = item["name"]

    daily = pro.index_daily(ts_code=code, trade_date=trade_date)
    basic = pro.index_dailybasic(ts_code=code, trade_date=trade_date)

    row = {
        "trade_date": trade_date,
        "ts_code": code,
        "name": name,
    }

    if not daily.empty:
        d = daily.iloc[0]
        row.update({
            "close": d.get("close"),
            "pct_chg": d.get("pct_chg"),
            "amount": d.get("amount"),
        })

    if not basic.empty:
        b = basic.iloc[0]
        row.update({
            "pe": b.get("pe"),
            "pe_ttm": b.get("pe_ttm"),
            "pb": b.get("pb"),
            "turnover_rate": b.get("turnover_rate"),
        })

    rows.append(row)

df = pd.DataFrame(rows)

out_csv = LATEST_DIR / "index_daily.csv"
out_json = LATEST_DIR / "index_daily.json"
history_csv = HISTORY_DIR / f"index_daily_{trade_date}.csv"

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
