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
DATA_DIR = ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
HISTORY_DIR = DATA_DIR / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def call_api(fn, **kwargs):
    try:
        return fn(**kwargs)
    except Exception as e:
        print(f"WARN: {fn.__name__} failed: {kwargs} -> {e}")
        return pd.DataFrame()


def get_latest_trade_date():
    today_bj = datetime.utcnow() + timedelta(hours=8)
    end = today_bj.strftime("%Y%m%d")
    start = (today_bj - timedelta(days=20)).strftime("%Y%m%d")
    cal = call_api(pro.trade_cal, exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal.empty:
        return end
    return str(cal.sort_values("cal_date").iloc[-1]["cal_date"])


trade_date = get_latest_trade_date()

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

    daily = call_api(pro.index_daily, ts_code=code, start_date=trade_date, end_date=trade_date)
    basic = call_api(
        pro.index_dailybasic,
        ts_code=code,
        trade_date=trade_date,
        fields="ts_code,trade_date,total_mv,float_mv,total_share,float_share,free_share,turnover_rate,turnover_rate_f,pe,pe_ttm,pb"
    )

    row = {
        "trade_date": trade_date,
        "ts_code": code,
        "name": name,
        "close": None,
        "pct_chg": None,
        "amount_yi": None,
        "pe": None,
        "pe_ttm": None,
        "pb": None,
        "turnover_rate": None,
        "total_mv_yi": None,
        "float_mv_yi": None,
    }

    if not daily.empty:
        d = daily.sort_values("trade_date", ascending=False).iloc[0]
        row["close"] = d.get("close")
        row["pct_chg"] = d.get("pct_chg")
        row["amount_yi"] = round(float(d.get("amount", 0)) / 100000, 2) if pd.notna(d.get("amount")) else None

    if not basic.empty:
        b = basic.iloc[0]
        row["pe"] = b.get("pe")
        row["pe_ttm"] = b.get("pe_ttm")
        row["pb"] = b.get("pb")
        row["turnover_rate"] = b.get("turnover_rate")
        row["total_mv_yi"] = round(float(b.get("total_mv", 0)) / 10000, 2) if pd.notna(b.get("total_mv")) else None
        row["float_mv_yi"] = round(float(b.get("float_mv", 0)) / 10000, 2) if pd.notna(b.get("float_mv")) else None

    rows.append(row)
    time.sleep(0.25)

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
