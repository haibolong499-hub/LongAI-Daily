import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

LATEST = ROOT / "data" / "latest"

company = pd.read_csv(LATEST / "company_daily.csv")

# -----------------------------
# 每个一级板块统计
# -----------------------------

sector_result = []

for sector, df in company.groupby("sector"):

    total = len(df)

    up = (df["pct_chg"] > 0).sum()

    avg = round(df["pct_chg"].mean(), 2)

    amount = round(df["amount"].sum() / 10000, 2)

    up_ratio = round(up / total * 100, 1)

    score = avg * 8 + up_ratio * 0.4

    sector_result.append(
        {
            "sector": sector,
            "company_count": total,
            "avg_pct_chg": avg,
            "up_ratio": up_ratio,
            "amount": amount,
            "score": round(score, 2),
        }
    )

sector_df = pd.DataFrame(sector_result)

sector_df = sector_df.sort_values(
    "score",
    ascending=False,
).reset_index(drop=True)

# -----------------------------
# 星级
# -----------------------------

def score_to_star(score):

    if score >= 40:
        return "★★★★★"

    elif score >= 30:
        return "★★★★☆"

    elif score >= 20:
        return "★★★☆☆"

    elif score >= 10:
        return "★★☆☆☆"

    else:
        return "★☆☆☆☆"


sector_df["star"] = sector_df["score"].apply(score_to_star)

sector_df["rank"] = sector_df.index + 1

# -----------------------------
# 输出
# -----------------------------

sector_df.to_json(
    LATEST / "sector_summary.json",
    orient="records",
    force_ascii=False,
    indent=2,
)

print("Generated sector_summary.json")
