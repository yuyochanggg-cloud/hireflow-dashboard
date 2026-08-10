# -*- coding: utf-8 -*-
"""一次性修復：02_候選人主檔「初次進庫日期」被遷移腳本蓋成執行當天。

事故成因
--------
2026-08-06 執行 migrate_colliding_app_ids.py 修「未知代碼撞號」時，替那批候選人
在 02_候選人主檔「新開列」，初次進庫日期直接寫成執行當天（2026-08-06），
而不是他們真正的應徵批次日期（06-22 / 06-24 / 07-23）。

後果：dashboard 的分析報表區間篩選走 created_at = 02 的「初次進庫日期」，
所以六、七月的人被算進八月的「新進候選人」，來源圓餅圖也多出 10 個「未指定」。

修法
----
規則：**一個人的初次進庫日期，不可能晚於他自己在 03_應徵主檔最早的應徵批次日期。**
凡違反此規則者，把 02 的初次進庫日期改成該人最早的應徵批次日期。只改這一欄。

這條規則同時已加進 daily_health_check.py（check_10），未來任何遷移腳本再犯
同樣的錯會被健檢當天抓到。

先跑 --dry-run。
"""
import argparse
import json
import sys

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def connect():
    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(cfg['spreadsheet_id'])


def col_letter(idx0):
    """0-based 欄號轉 A1 欄名（支援超過 Z）。"""
    n, s = idx0 + 1, ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    sh = connect()
    ws2 = sh.worksheet('02_候選人主檔')
    v2 = ws2.get_all_values()
    h2 = v2[0]
    i_cid, i_first = h2.index('candidate_id'), h2.index('初次進庫日期')

    v3 = sh.worksheet('03_應徵主檔').get_all_values()
    h3 = v3[0]
    j_cid, j_batch, j_name, j_job = (h3.index('candidate_id'), h3.index('應徵批次日期'),
                                     h3.index('姓名'), h3.index('職缺名稱'))

    # 每個 candidate_id 最早的應徵批次日期（空值不算）
    earliest, jobs = {}, {}
    for r in v3[1:]:
        cid = r[j_cid] if j_cid < len(r) else ''
        b = (r[j_batch] if j_batch < len(r) else '').strip()
        if not cid or not b:
            continue
        if cid not in earliest or b < earliest[cid]:
            earliest[cid] = b
        jobs.setdefault(cid, []).append((r[j_name], r[j_job]))

    fixes = []
    for n, r in enumerate(v2[1:], start=2):
        cid = r[i_cid] if i_cid < len(r) else ''
        cur = (r[i_first] if i_first < len(r) else '').strip()
        want = earliest.get(cid)
        if not cid or not want or not cur:
            continue
        # 只修「初次進庫日期晚於最早應徵批次日期」的情形。
        # 反過來（進庫早於應徵）是正常的：人才庫的人可能之後才投新職缺。
        if cur[:10] > want[:10]:
            fixes.append((n, cid, cur, want, jobs.get(cid, [])))

    print(f'違反規則（初次進庫日期 晚於 最早應徵批次日期）：{len(fixes)} 列\n')
    for n, cid, cur, want, js in fixes:
        who = js[0][0] if js else ''
        joblist = '、'.join(sorted({j for _, j in js}))
        print(f'  row{n:>4} | {cid:<28} | {cur} → {want} | {who or "(無姓名)"} | {joblist}')

    if not fixes:
        print('沒有需要修的列。')
        return

    if args.dry_run:
        print(f'\n[DRY-RUN] 未寫入。將更新 02_候選人主檔「初次進庫日期」共 {len(fixes)} 格。')
        return

    letter = col_letter(i_first)
    ws2.batch_update([
        {'range': f'{letter}{n}', 'values': [[want]]} for n, _, _, want, _ in fixes
    ])
    print(f'\n[已寫入] 更新 {len(fixes)} 格（02_候選人主檔 {letter} 欄）。')


if __name__ == '__main__':
    main()
