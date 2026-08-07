# -*- coding: utf-8 -*-
"""一次性修復：daily_health_check.py 08-06 第一次實跑抓到的兩項真實資料問題。

1. 「外貿業務助理」6筆應徵紀錄——使用者確認這是「零件部-外貿業務助理」改名前的舊名稱，
   03_應徵主檔 這6列的 職缺名稱/job_id 沒跟著改名，改成正確值即可（不搬列、不動其他欄）。

2. 侯政宇（application_id=APP-H5dcf694840-電商系統工程師）「錄取審核」查不到面試紀錄——
   查證後發現不是真的漏記錄：他的面試在05_面試主檔第11列，日期2026-08-05 10:00、通過，
   但application_id還是08-05 ID撞號修復（migrate_colliding_app_ids.py）之前的舊值
   APP-未知代碼-電商系統工程師。那次修復只改了03_應徵主檔，05_面試主檔沒有跟著改，
   紀錄變成孤兒。已確認05_面試主檔裡只有這一列受影響（其他撞號列本來就沒有面試紀錄）。

先跑 --dry-run。
"""
import argparse
import json
import sys

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

OLD_JOB_NAME = '外貿業務助理'
NEW_JOB_NAME = '零件部-外貿業務助理'

HOU_OLD_APP_ID = 'APP-未知代碼-電商系統工程師'
HOU_NEW_APP_ID = 'APP-H5dcf694840-電商系統工程師'
HOU_OLD_CAND_ID = 'CAND-未知代碼'
HOU_NEW_CAND_ID = 'CAND-H5dcf694840'
HOU_JOB_NAME = '電商系統工程師'


def connect():
    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(cfg['spreadsheet_id'])


def fix_job_rename(sh, dry_run):
    ws = sh.worksheet('03_應徵主檔')
    values = ws.get_all_values()
    header = values[0]
    c_job = header.index('job_id')
    c_jobname = header.index('職缺名稱')
    c_name = header.index('姓名')

    cells = []
    print(f"【1】職缺改名：「{OLD_JOB_NAME}」→「{NEW_JOB_NAME}」")
    for i, row in enumerate(values[1:], start=2):
        if len(row) > c_jobname and row[c_jobname] == OLD_JOB_NAME:
            print(f"  row{i} 姓名={row[c_name] or '(空白)'}　"
                  f"職缺名稱：{row[c_jobname]} -> {NEW_JOB_NAME}　"
                  f"job_id：{row[c_job]} -> {NEW_JOB_NAME}")
            cells.append(gspread.Cell(i, c_jobname + 1, NEW_JOB_NAME))
            cells.append(gspread.Cell(i, c_job + 1, NEW_JOB_NAME))
    print(f"  {'[dry-run] 會改' if dry_run else '已改'} {len(cells)//2} 列\n")
    if cells and not dry_run:
        ws.update_cells(cells, value_input_option='RAW')


def fix_hou_interview(sh, dry_run):
    ws = sh.worksheet('05_面試主檔')
    values = ws.get_all_values()
    header = values[0]
    c_app = header.index('application_id')
    c_cand = header.index('candidate_id')
    c_jobname = header.index('職缺名稱')

    cells = []
    print(f"【2】侯政宇面試紀錄改回現在的 application_id")
    for i, row in enumerate(values[1:], start=2):
        if len(row) > c_app and row[c_app] == HOU_OLD_APP_ID:
            print(f"  row{i}：application_id {HOU_OLD_APP_ID} -> {HOU_NEW_APP_ID}")
            print(f"          candidate_id  {HOU_OLD_CAND_ID} -> {HOU_NEW_CAND_ID}")
            print(f"          職缺名稱      (空白) -> {HOU_JOB_NAME}")
            cells.append(gspread.Cell(i, c_app + 1, HOU_NEW_APP_ID))
            cells.append(gspread.Cell(i, c_cand + 1, HOU_NEW_CAND_ID))
            cells.append(gspread.Cell(i, c_jobname + 1, HOU_JOB_NAME))
    print(f"  {'[dry-run] 會改' if dry_run else '已改'} {len(cells)//3} 列\n")
    if cells and not dry_run:
        ws.update_cells(cells, value_input_option='RAW')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    sh = connect()
    fix_job_rename(sh, args.dry_run)
    fix_hou_interview(sh, args.dry_run)


if __name__ == '__main__':
    main()
