# -*- coding: utf-8 -*-
"""一次性修正：把「約了沒出席」的面試紀錄從「未通過」改成新類別「面試未到」。

背景：2026-08-12 之前，結案原因選「面試未到」時，系統會在 05_面試主檔寫一筆
面試結果=「未通過」的紀錄。但沒出席的人根本沒被評估過，卻會進面試通過率的
分母把通過率壓低，而且會讓健檢 check_11（面試紀錄超前流程狀態）誤報。

判準刻意保守：**只改備註明確寫了 no-show／未出席的紀錄**，不靠日期或結果推論。
不確定的一律不動——寧可漏改，也不要把真的面試未通過改成沒出席。

先跑 --dry-run。
"""
import argparse
import json
import sys

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 判定為 no-show 的備註關鍵字（小寫比對）
NO_SHOW_MARKERS = ['no-show', 'no show', 'noshow', '未出席', '沒出席', '未到']


def connect():
    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(cfg['spreadsheet_id'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    sh = connect()
    ws = sh.worksheet('05_面試主檔')
    values = ws.get_all_values()
    header = values[0]
    i_res = header.index('面試結果')
    i_note = header.index('面試官備註')
    i_name = header.index('姓名')
    i_date = header.index('面試日期')

    fixes = []
    for n, row in enumerate(values[1:], start=2):
        res = (row[i_res] if len(row) > i_res else '').strip()
        note = (row[i_note] if len(row) > i_note else '').strip()
        if res != '未通過':
            continue
        if not any(m in note.lower() for m in NO_SHOW_MARKERS):
            continue
        fixes.append((n, row[i_name] if len(row) > i_name else '',
                      row[i_date] if len(row) > i_date else '', note))

    print(f'符合「未通過 + 備註寫明未出席」的紀錄：{len(fixes)} 筆\n')
    for n, who, when, note in fixes:
        print(f'  row{n} | {who} | {when} | 備註：{note}')
        print(f'         面試結果：未通過 → 面試未到')

    print(f'\n（其餘 {len(values)-1-len(fixes)} 筆未通過/通過/待定紀錄不動）')
    if not fixes:
        return
    if args.dry_run:
        print('\n[DRY-RUN] 未寫入。')
        return

    col = chr(ord('A') + i_res) if i_res < 26 else None
    assert col, '面試結果欄超過 Z 欄，需改用多字母欄名'
    ws.batch_update([{'range': f'{col}{n}', 'values': [['面試未到']]}
                     for n, _, _, _ in fixes])
    print(f'\n[已寫入] 更新 {len(fixes)} 格（05_面試主檔 {col} 欄）。')


if __name__ == '__main__':
    main()
