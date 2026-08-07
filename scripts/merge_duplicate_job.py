# -*- coding: utf-8 -*-
"""一次性合併重複職缺：「外貿業務助理」併入「零件部-外貿業務助理」。

背景：同一個真實職缺在系統裡被拆成兩份履歷庫（6筆＋7筆，104代碼完全不重疊），
而 Sheets 上 13 人的 職缺名稱／job_id 都已經是「零件部-外貿業務助理」，但其中 6 人的
application_id／score_id 還帶著「-外貿業務助理」——列本身內部不一致（推測是有人在
Sheets 手動改過職缺名稱，但 ID 欄改不動）。直接同步會產生 6 筆重複列。

保留名稱由使用者決定為「零件部-外貿業務助理」：Sheets 上 13 筆都已是這個名字（改動
最小），也符合其他職缺的命名慣例（物流部-電子元件倉儲助理）。

做法（照 2026-07-14「電商品牌→電商-品牌營運PM」那次的先例）：
1. 履歷庫：6 筆併入 13 筆，舊檔改名為 _merged_into_{目標}_{來源}.json.bak
2. jd_profiles.json：key 改名（保留較新的 07-27 那份條件）
3. Sheets 03/04：把 ID 欄原地改名成新公式算出的值（不新增列、不刪列——刪列會讓
   列號位移，而 dashboard 用快取列號寫入，位移會寫到別人身上）

先跑 --dry-run。
"""
import argparse
import json
import os
import shutil
import sys

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402  用它的 make_master_ids，ID 公式只有一份

SOURCE = '外貿業務助理'
TARGET = '零件部-外貿業務助理'


def merge_libraries(dry_run):
    src_path = os.path.join('resume_library', f'{SOURCE}.json')
    tgt_path = os.path.join('resume_library', f'{TARGET}.json')
    src = json.load(open(src_path, encoding='utf-8'))
    tgt = json.load(open(tgt_path, encoding='utf-8'))

    tgt_codes = {str(c.get('104代碼')) for c in tgt['candidates']}
    incoming = [c for c in src['candidates'] if str(c.get('104代碼')) not in tgt_codes]
    dup = len(src['candidates']) - len(incoming)
    print(f"履歷庫：{TARGET} 原有 {len(tgt['candidates'])} 筆，"
          f"併入 {len(incoming)} 筆（{dup} 筆因代碼重複略過）"
          f" → 共 {len(tgt['candidates']) + len(incoming)} 筆")
    if dry_run:
        return
    tgt['candidates'].extend(incoming)
    tgt['summary'] = {
        'total': len(tgt['candidates']),
        'qualified': sum(1 for c in tgt['candidates'] if c.get('初篩判定') == '合格'),
    }
    json.dump(tgt, open(tgt_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    bak = os.path.join('resume_library', f'_merged_into_{TARGET}_{SOURCE}.json.bak')
    shutil.move(src_path, bak)
    print(f"  舊檔已改名 → {os.path.basename(bak)}")


def rename_jd_profile(dry_run):
    profiles = json.load(open('jd_profiles.json', encoding='utf-8'))
    if SOURCE not in profiles:
        print(f"jd_profiles.json：找不到「{SOURCE}」，跳過")
        return
    if TARGET in profiles:
        print(f"jd_profiles.json：「{TARGET}」已存在，保留它、只刪除「{SOURCE}」")
    else:
        print(f"jd_profiles.json：「{SOURCE}」→「{TARGET}」（保留 07-27 那份較新的條件）")
    if dry_run:
        return
    if TARGET not in profiles:
        profiles[TARGET] = profiles[SOURCE]
    del profiles[SOURCE]
    json.dump(profiles, open('jd_profiles.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=4)


def migrate_sheet_ids(dry_run):
    """把 03/04 裡這個職缺的 ID 欄改成新公式算出的值。

    ⚠️ 必須同時比對「104代碼」**和**「職缺名稱」。dry-run 實測踩到過：只用 104代碼
    比對時，代碼 30000006723243 那個人同時應徵了「零件採購專員」，腳本差點把他那筆
    完全無關的應徵紀錄也改成外貿業務助理。一人可以有多筆應徵紀錄是這個系統的常態，
    任何查詢都要假設這件事（跟 2026-07-15 candidate_id/application_id 混用、
    2026-08-05 APP-- 撞號是同一種錯誤）。
    這裡 職缺名稱 欄可信（13 筆都已經是 TARGET），不可信的只有 ID 欄。
    """
    # 從「目標庫 + 來源庫（若還存在）」一起算目標 ID，不是只讀目標庫——否則
    # --dry-run 時合併還沒發生，那 6 人不在目標庫裡，會誤報「0 格要改」。
    cands = json.load(open(os.path.join('resume_library', f'{TARGET}.json'),
                           encoding='utf-8'))['candidates'][:]
    _src_path = os.path.join('resume_library', f'{SOURCE}.json')
    if os.path.exists(_src_path):
        cands += json.load(open(_src_path, encoding='utf-8'))['candidates']

    # 目標 ID：code -> (cand_id, app_id, scr_id, job_safe)
    want = {}
    for c in cands:
        code = str(c.get('104代碼') or '')
        if code and code != '未知代碼':
            want[code] = app.make_master_ids(c, TARGET)

    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sh = gspread.authorize(creds).open_by_key(cfg['spreadsheet_id'])

    total = 0
    for ws_name, id_specs in [
        # (欄名, 取 want tuple 的哪一個 index)
        ('03_應徵主檔', [('application_id', 1), ('candidate_id', 0), ('job_id', 3)]),
        ('04_評分主檔', [('score_id', 2), ('application_id', 1), ('candidate_id', 0), ('job_id', 3)]),
    ]:
        ws = sh.worksheet(ws_name)
        values = ws.get_all_values()
        header = values[0]
        c_code = header.index('104代碼')
        c_jobname = header.index('職缺名稱')
        cells = []
        for row_i, row in enumerate(values[1:], start=2):
            if len(row) <= max(c_code, c_jobname):
                continue
            code = row[c_code]
            # 只動這個職缺（含合併前的舊名）的列——不能只憑代碼，同一人可能還有
            # 其他職缺的應徵紀錄
            if row[c_jobname] not in (SOURCE, TARGET):
                continue
            if code not in want:
                continue
            for col_name, want_idx in id_specs:
                ci = header.index(col_name)
                new_val = want[code][want_idx]
                if len(row) > ci and row[ci] != new_val:
                    print(f"  {ws_name} row{row_i} {col_name}: {row[ci]} -> {new_val}")
                    cells.append(gspread.Cell(row_i, ci + 1, new_val))
        print(f"{ws_name}：需要改 {len(cells)} 格")
        total += len(cells)
        if cells and not dry_run:
            ws.update_cells(cells, value_input_option='RAW')
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    merge_libraries(args.dry_run)
    print()
    rename_jd_profile(args.dry_run)
    print()
    migrate_sheet_ids(args.dry_run)
    print()
    if args.dry_run:
        print('[dry-run] 以上都沒有實際執行')
    else:
        print('完成。下一步：跑一次「零件部-外貿業務助理」的同步，再跑健檢確認 [9/9] 消失。')


if __name__ == '__main__':
    main()
