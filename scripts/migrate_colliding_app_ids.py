# -*- coding: utf-8 -*-
"""一次性遷移：把 03_應徵主檔 裡撞號的 application_id 原地改名成新公式算出的唯一 ID。

背景（2026-08-05 P0）：104代碼 空白／「未知代碼」時，舊公式拼出 `APP--職缺`，
同一職缺的這些人互相撞號被合併成一列。修好 resolve_candidate_code 之後，
如果直接同步，這些人會產生「新的一列」，舊列上的 HR 進度（例如侯政宇已經
到「錄取審核」）就會被孤立在舊列上。所以要先原地改名，不是新增列。

配對方式：同一職缺內，把 Sheets 的列（依列號順序）跟履歷庫的無代碼候選人
（依庫內順序）依序配對——兩邊都是同一次同步、同一個順序寫出來的，所以這是
最可能正確的配對，不是隨機猜。而且這些列的 HR 欄位全都是空的（除了侯政宇
那筆），配錯也不會遺失任何人工填的資料；AI評級/AI分數不在保護清單內，
下次同步會自動校正成正確值。

先跑 --dry-run。
"""
import argparse
import glob
import json
import os
import re
import sys

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402  用它的 resolve_candidate_code，公式只有一份


def build_expected(jd_name, candidates):
    """回傳這個職缺「無代碼候選人」的 (舊app_id, 新app_id, 新cand_id) 依庫內順序。"""
    job_safe = re.sub(r'[^\w\-]', '_', jd_name)[:20]
    out = []
    for c in candidates:
        raw = str(c.get('104代碼', '') or '').strip()
        if raw and raw != '未知代碼':
            continue
        new_code = app.resolve_candidate_code(c)
        out.append((f"APP-{raw}-{job_safe}", f"APP-{new_code}-{job_safe}", f"CAND-{new_code}"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # 履歷庫側：每個職缺的無代碼候選人應有的新 ID
    expected = {}
    for fp in sorted(glob.glob(os.path.join('resume_library', '*.json'))):
        if fp.endswith('.bak'):
            continue
        d = json.load(open(fp, encoding='utf-8'))
        jd = d.get('jd_name')
        if not jd:
            continue
        got = build_expected(jd, d.get('candidates', []))
        if got:
            expected[jd] = got

    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    ws = gspread.authorize(creds).open_by_key(cfg['spreadsheet_id']).worksheet('03_應徵主檔')

    values = ws.get_all_values()
    header = values[0]
    c_app = header.index('application_id')
    c_cand = header.index('candidate_id')
    c_job = header.index('職缺名稱')
    c_name = header.index('姓名')
    c_flow = header.index('流程狀態')

    # Sheets 側：依職缺分組，收集需要改名的列（依列號順序）
    by_job = {}
    for i, row in enumerate(values[1:], start=2):
        if len(row) <= c_app:
            continue
        aid = row[c_app]
        if not (aid.startswith('APP--') or '未知代碼' in aid):
            continue
        by_job.setdefault(row[c_job], []).append((i, row))

    cells = []
    for jd, rows in sorted(by_job.items()):
        exp = expected.get(jd, [])
        if len(rows) != len(exp):
            print(f"⚠️ 「{jd}」Sheets {len(rows)} 列 vs 履歷庫 {len(exp)} 筆，數量對不上，"
                  f"整個職缺跳過不動（需人工確認）")
            continue
        for (row_i, row), (_old, new_app, new_cand) in zip(rows, exp):
            print(f"  row{row_i} 「{jd}」姓名={row[c_name] or '(空白)'} "
                  f"流程={row[c_flow]}\n"
                  f"        {row[c_app]} -> {new_app}")
            cells.append(gspread.Cell(row_i, c_app + 1, new_app))
            cells.append(gspread.Cell(row_i, c_cand + 1, new_cand))

    print(f"\n{'[dry-run] 會改' if args.dry_run else '已改'} {len(cells)//2} 列")
    if cells and not args.dry_run:
        ws.update_cells(cells, value_input_option='RAW')
        print("完成。下一步：跑一次全職缺同步，讓這些人的姓名/評級等欄位補齊。")


if __name__ == '__main__':
    main()
