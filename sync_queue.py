"""
sync_queue.py — 流程狀態同步失敗的本機待補佇列（app.py 寫入/重試，dashboard.py 唯讀顯示）

單人維運，不用資料庫/訊息佇列，就一個 JSON 檔案。
"""
import json
import os
from datetime import datetime

PENDING_FILE = os.path.join(os.path.dirname(__file__), "pending_status_sync.json")


def load_pending():
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(items):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def add_pending(job_name, candidate, new_status, error):
    items = load_pending()
    key = f"{candidate.get('104代碼', '')}|{job_name}|{new_status}"
    items = [x for x in items if x["key"] != key]
    items.append({
        "key": key, "job_name": job_name,
        "code": str(candidate.get("104代碼", "") or ""),
        "name": str(candidate.get("真實姓名", "") or ""),
        "new_status": new_status, "error": error,
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save(items)


def remove_pending(key):
    _save([x for x in load_pending() if x["key"] != key])
