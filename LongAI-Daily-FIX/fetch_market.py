import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import tushare as ts

TOKEN = os.getenv("TUSHARE_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Missing TUSHARE_TOKEN. Please set it in GitHub Secrets.")

ts.set_token(TOKEN)
pro = ts.pro_api()

ROOT = Path(__file__).resolve().parent
LATEST_DIR = ROOT / "data" / "latest"
HISTORY_DIR = ROOT / "data" / "history"
LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def call_api(fn, retries=3, sleep_seconds=2, **kwargs):
    last_err = None
    for i in range(retries):
        try:
            return fn(**kwargs)
        except Exception as e:
            last_err = e
            time.sleep(sleep_seconds * (i + 1))
fn_name = getattr(fn, "__name__", "api_call")
print(f"WARN: API call failed: {fn_name} {kwargs} -> {last_err}")
return pd.DataFrame()


def get_trade_date():
    today = datetime.utcnow() + timedelta(hours=8)
    end = today.strftime("%Y%m%d")
    start = (today - timedelta(days=14)).strftime("%Y%m%d")
    cal = call_api(pro.trade_cal, exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal.empty:
        return end
    return str(cal.sort_values("cal_date").iloc[-1]["cal_date"])


def fmt_pct(x):
    try:
        return round(float(x), 2)
    except Exception:
        return None


def df_records(df, limit=None):
    if df is None or df.empty:
        return []
    if limit:
        df = df.head(limit)
    return json.loads(df.where(pd.notnull(df), None).to_json(orient="records", force_ascii=False))


trade_date = get_trade_date()
end_dt = trade_date
start_dt = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=20)).strftime("%Y%m%d")

# 主要指数
index_codes = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000300.SH": "沪深300",
    "000688.SH": "科创50",
    "000852.SH": "中证1000",
}
indices = []
for code, name in index_codes.items():
    df = call_api(pro.index_daily, ts_code=code, start_date=start_dt, end_date=end_dt)
    if not df.empty:
        row = df.sort_values("trade_date", ascending=False).iloc[0]
        indices.append({
            "name": name,
            "ts_code": code,
            "trade_date": str(row.get("trade_date")),
            "close": float(row.get("close")) if pd.notnull(row.get("close")) else None,
            "pct_chg": fmt_pct(row.get("pct_chg")),
            "amount_yi": round(float(row.get("amount", 0)) / 100000, 2) if pd.notnull(row.get("amount")) else None,
        })
    time.sleep(0.35)

# 全市场日线基础：用于成交额、涨跌家数（Tushare股票日线口径）
daily_basic = call_api(pro.daily, trade_date=trade_date)
market = {"trade_date": trade_date}
if not daily_basic.empty:
    market["stock_count"] = int(len(daily_basic))
    market["up_count"] = int((daily_basic["pct_chg"] > 0).sum()) if "pct_chg" in daily_basic else None
    market["down_count"] = int((daily_basic["pct_chg"] < 0).sum()) if "pct_chg" in daily_basic else None
    market["flat_count"] = int((daily_basic["pct_chg"] == 0).sum()) if "pct_chg" in daily_basic else None
    market["total_amount_yi"] = round(float(daily_basic["amount"].sum()) / 100000, 2) if "amount" in daily_basic else None
    # top gainers / losers
    top_up = daily_basic.sort_values("pct_chg", ascending=False).head(10) if "pct_chg" in daily_basic else pd.DataFrame()
    top_down = daily_basic.sort_values("pct_chg", ascending=True).head(10) if "pct_chg" in daily_basic else pd.DataFrame()
else:
    top_up = top_down = pd.DataFrame()

# 近10个交易日成交额
cal = call_api(pro.trade_cal, exchange="SSE", start_date=(datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=40)).strftime("%Y%m%d"), end_date=trade_date, is_open="1")
turnover_10d = []
if not cal.empty:
    dates = cal.sort_values("cal_date")["cal_date"].astype(str).tolist()[-10:]
    for dte in dates:
        tmp = call_api(pro.daily, trade_date=dte)
        turnover_10d.append({
            "trade_date": dte,
            "total_amount_yi": round(float(tmp["amount"].sum()) / 100000, 2) if not tmp.empty and "amount" in tmp else None
        })
        time.sleep(0.35)

# 龙虎榜
top_list = call_api(pro.top_list, trade_date=trade_date)

# 融资融券（可能当日未更新）
margin = call_api(pro.margin, trade_date=trade_date)

report = {
    "generated_at_beijing": (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
    "trade_date": trade_date,
    "data_source": {
        "primary": "Tushare Pro",
        "notes": "涨跌家数、成交额为Tushare股票日线口径；部分数据可能在盘后延迟更新。"
    },
    "market": market,
    "indices": indices,
    "turnover_10d": turnover_10d,
    "top_gainers": df_records(top_up, 10),
    "top_losers": df_records(top_down, 10),
    "top_list": df_records(top_list, 30),
    "margin": df_records(margin, 20),
    "quality_check": {
        "has_market": bool(market.get("total_amount_yi")),
        "has_indices": len(indices) > 0,
        "has_turnover_10d": len(turnover_10d) >= 5,
        "has_top_list": len(top_list) > 0 if isinstance(top_list, pd.DataFrame) else False,
        "has_margin": len(margin) > 0 if isinstance(margin, pd.DataFrame) else False,
    }
}

json_path = LATEST_DIR / "daily_report.json"
xlsx_path = LATEST_DIR / "daily_report.xlsx"
history_path = HISTORY_DIR / f"{trade_date}.json"

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
with open(history_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    pd.DataFrame([market]).to_excel(writer, sheet_name="market", index=False)
    pd.DataFrame(indices).to_excel(writer, sheet_name="indices", index=False)
    pd.DataFrame(turnover_10d).to_excel(writer, sheet_name="turnover_10d", index=False)
    if not top_up.empty:
        top_up.head(50).to_excel(writer, sheet_name="top_gainers", index=False)
    if not top_down.empty:
        top_down.head(50).to_excel(writer, sheet_name="top_losers", index=False)
    if isinstance(top_list, pd.DataFrame) and not top_list.empty:
        top_list.head(100).to_excel(writer, sheet_name="top_list", index=False)
    if isinstance(margin, pd.DataFrame) and not margin.empty:
        margin.to_excel(writer, sheet_name="margin", index=False)

print(f"Generated {json_path}")
print(f"Generated {xlsx_path}")
print(f"Generated {history_path}")
