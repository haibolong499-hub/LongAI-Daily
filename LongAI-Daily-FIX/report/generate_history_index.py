import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LATEST_DIR = DATA_DIR / "latest"
HISTORY_DIR = DATA_DIR / "history"

LATEST_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

now_bj = datetime.utcnow() + timedelta(hours=8)
now_dubai = datetime.utcnow() + timedelta(hours=4)

history_files = []

for path in sorted(HISTORY_DIR.iterdir()):
    if path.is_file():
        history_files.append({
            "file_name": path.name,
            "path": f"LongAI-Daily-FIX/data/history/{path.name}",
            "suffix": path.suffix.replace(".", ""),
            "size": path.stat().st_size,
            "modified_time": datetime.utcfromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })

api_files = [x for x in history_files if x["file_name"].startswith("api_") and x["file_name"].endswith(".json")]
company_files = [x for x in history_files if x["file_name"].startswith("company_daily_") and x["file_name"].endswith(".csv")]
index_files = [x for x in history_files if x["file_name"].startswith("index_daily_") and x["file_name"].endswith(".csv")]
report_files = [x for x in history_files if x["file_name"].startswith("longai_daily_") and x["file_name"].endswith(".md")]

history_index = {
    "meta": {
        "name": "LongAI History Index",
        "version": "v1",
        "generated_at_beijing": now_bj.strftime("%Y-%m-%d %H:%M:%S"),
        "generated_at_dubai": now_dubai.strftime("%Y-%m-%d %H:%M:%S"),
        "base_path": "LongAI-Daily-FIX/data/history/"
    },
    "counts": {
        "all_files": len(history_files),
        "api_json": len(api_files),
        "company_daily_csv": len(company_files),
        "index_daily_csv": len(index_files),
        "longai_daily_md": len(report_files),
    },
    "files": {
        "api_json": api_files,
        "company_daily_csv": company_files,
        "index_daily_csv": index_files,
        "longai_daily_md": report_files,
        "all": history_files,
    }
}

out_path = LATEST_DIR / "history_index.json"

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(history_index, f, ensure_ascii=False, indent=2)

print(f"Generated {out_path}")
print(f"History files: {len(history_files)}")
