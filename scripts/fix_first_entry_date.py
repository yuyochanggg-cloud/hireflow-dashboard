# -*- coding: utf-8 -*-
"""
一次性修正腳本：02_候選人主檔「初次進庫日期」曾被同步流程誤覆寫成「今天」
（bug已在 app.py/sync_to_gsheet.py 修復，本腳本只處理過去已寫壞的資料）。

修法：用該候選人在03_應徵主檔裡所有應徵紀錄的「應徵批次日期」取最早一筆，
當作「初次進庫日期」的正確值（目前系統能取得的最佳近似——沒有比這更早的
歷史紀錄可查）。只更新真的不一致的列，不動本來就正確的。
"""
import json
import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

with open("gsheet_config.json", encoding="utf-8") as f:
    cfg = json.load(f)

source_creds, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
target_creds = _impersonated_credentials.Credentials(
    source_credentials=source_creds,
    target_principal=cfg["impersonate_sa"],
    target_scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.readonly"],
)
gc = gspread.authorize(target_creds)
sh = gc.open_by_key(cfg["spreadsheet_id"])

ws3 = sh.worksheet("03_應徵主檔")
s3_rows = ws3.get_all_records()

earliest = {}
for r in s3_rows:
    cid = r.get("candidate_id")
    d = r.get("應徵批次日期", "")
    if not cid or not d:
        continue
    if cid not in earliest or d < earliest[cid]:
        earliest[cid] = d

ws2 = sh.worksheet("02_候選人主檔")
hdr2 = ws2.row_values(1)
col_cid = hdr2.index("candidate_id") + 1
col_first = hdr2.index("初次進庫日期") + 1
s2_all = ws2.get_all_values()[1:]  # skip header

cells = []
for i, row in enumerate(s2_all, start=2):
    cid = row[col_cid - 1] if len(row) >= col_cid else ""
    cur = row[col_first - 1] if len(row) >= col_first else ""
    correct = earliest.get(cid)
    if correct and cur != correct:
        cells.append(gspread.Cell(i, col_first, correct))

print(f"需要修正 {len(cells)} 筆「初次進庫日期」")
if cells:
    ws2.update_cells(cells, value_input_option="RAW")
    print("已批次寫入。")
