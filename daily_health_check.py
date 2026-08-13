# -*- coding: utf-8 -*-
"""每日資料健檢：對六主檔做唯讀一致性檢查，用中文報出「哪一列／哪個職缺／哪個人」出了問題。

背景：這一年的維護史都是同一個模式——資料悄悄壞掉，過了幾週才因為某個數字看起來
怪被發現（應徵批次日期被蓋成今天、面試通過率永遠 0%、01_職缺主檔從沒被寫過、
欄位錯位第9欄後全錯...）。這支腳本的職責只有「發現並報告」，不修資料。

用法：
    python daily_health_check.py            # 印報告
    python daily_health_check.py --email     # 有問題才寄信給自己
"""
import argparse
import glob
import json
import os
import datetime
import sys
import time
from collections import Counter

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

from hr_schema import S3_COLS, FLOW_TO_STAGE

# 健檢警報收件人（使用者實際會看的信箱）。刻意寫死而非讀 email_config.json 的
# recipients——那份清單是候選人推薦信收件主管名單（7位部門主管），用途完全不同，
# 混用會把內部資料健檢報告寄給不相關的外部收件人。
ADMIN_EMAIL = 'yunyu@ls3c.com.tw'

# 檢查項總數。報告裡的 [n/N] 與「檢查 N 項」都讀這個值——以前寫死 9，加檢查時
# 很容易漏改其中一處，變成「[10/9]」這種對不上的編號。
TOTAL_CHECKS = 11


# 已知並「決定不處理」的例外。這裡的每一筆都會照樣出現在報告底部（所以健檢是不是
# 還活著、隨時看得出來——如果哪天連這幾行都消失了，代表健檢本身壞了，不是資料變乾淨
# 了），但**不會觸發寄信**。
#
# 為什麼要這個機制：每天寄一封提醒同一筆已知舊資料的信，會養成「這封信不用看」的
# 習慣，真正的新問題就會跟著被忽略。狼來了一次，這個健檢就等於沒做。
#
# key 是會出現在報告明細行裡的字串（用 in 比對，所以要夠具體）；value 是為什麼放行。
# 資料修好之後這一筆會比對不到任何東西，留著無害，但可以順手刪掉。
KNOWN_EXCEPTIONS = {
    '王美嵐': (
        '職缺欄位卡著「➕ 新增自訂職缺」佔位字串。履歷庫查無任何佐證，判斷不出她原本'
        '應徵哪個職缺；依 2026-08-03 定的原則「沒有客觀佐證就不刪、不猜」保留原狀。'
        '同時刻意留作健檢的活體樣本（金絲雀）——它消失了就代表健檢自己壞了。'
    ),
}


def _split_known(lines):
    """把一項檢查的明細行分成 (新問題, 已知例外)。"""
    new_lines, known_lines = [], []
    for line in lines:
        hit = next((k for k in KNOWN_EXCEPTIONS if k in line), None)
        (known_lines if hit else new_lines).append(line)
    return new_lines, known_lines


class Issue:
    """一項檢查發現的問題：no=檢查編號, title=標題, lines=逐筆明細, why=意義, advice=建議"""
    def __init__(self, no, title, lines, why, advice):
        self.no = no
        self.title = title
        self.lines = lines
        self.why = why
        self.advice = advice


def connect():
    cfg = json.load(open('gsheet_config.json', encoding='utf-8'))
    src, _ = google_auth_default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    creds = _impersonated_credentials.Credentials(
        source_credentials=src, target_principal=cfg['impersonate_sa'],
        target_scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(cfg['spreadsheet_id'])


def check_1_header(s3_values):
    """03 表頭健康：重複欄名、空白欄名，或欄數 != schema 欄數。"""
    header = s3_values[0] if s3_values else []
    lines = []
    dup = [name for name, cnt in Counter(header).items() if cnt > 1 and name != '']
    if dup:
        lines.append(f"重複欄名：{'、'.join(dup)}")
    blank_positions = [i + 1 for i, name in enumerate(header) if name.strip() == '']
    if blank_positions:
        lines.append(f"空白欄名：第 {'、'.join(str(p) for p in blank_positions)} 欄")
    if len(header) != len(S3_COLS):
        lines.append(f"欄數 {len(header)} ≠ schema 定義的 {len(S3_COLS)} 欄")
    if not lines:
        return None
    return Issue(
        1, "03 表頭異常", lines,
        "表頭塌掉會讓看板寫入時對錯欄位，且是全表系統性錯誤，不是單筆資料問題。",
        "先不要用系統寫入任何資料，人工檢查 03_應徵主檔 第 1 列，跟 hr_schema.py 的 S3_COLS 逐欄比對。",
    )


def _idx(header, name):
    """header 裡找欄位位置；找不到就退回 schema 定義順序（表頭本身異常時的最後手段）。"""
    if name in header:
        return header.index(name)
    return S3_COLS.index(name)


def check_2_row_width(s3_values):
    """每列欄數：任一列欄數 != schema 欄數 → 從那欄之後全部錯位。"""
    expected = len(S3_COLS)
    header = s3_values[0] if s3_values else []
    c_app = header.index('application_id') if 'application_id' in header else 0
    c_job = header.index('職缺名稱') if '職缺名稱' in header else 3
    lines = []
    for i, row in enumerate(s3_values[1:], start=2):
        if len(row) != expected:
            aid = row[c_app] if len(row) > c_app else '(缺)'
            job = row[c_job] if len(row) > c_job else '(缺)'
            lines.append(f"第 {i} 列：目前 {len(row)} 欄，應為 {expected} 欄（application_id={aid}／職缺={job}）")
    if not lines:
        return None
    return Issue(
        2, "欄數錯位", lines,
        "這幾列從欄數不對的那一欄開始，後面每一格資料都被讀成別的欄位（例如AI評級被讀成HR複審日）。",
        "先不要用系統寫入這幾列，人工比對 Google Sheets 上這幾列實際內容跟欄位定義。",
    )


def check_3_duplicate_app_id(s3_values):
    """application_id 唯一：同一個 ID 出現在多列 → 多人在看板上被合併成一人。"""
    header = s3_values[0] if s3_values else []
    c_app = _idx(header, 'application_id')
    c_name = _idx(header, '姓名')
    groups = {}
    for i, row in enumerate(s3_values[1:], start=2):
        aid = row[c_app] if len(row) > c_app else ''
        if not aid:
            continue
        groups.setdefault(aid, []).append((i, row[c_name] if len(row) > c_name else ''))
    dups = {aid: rows for aid, rows in groups.items() if len(rows) > 1}
    if not dups:
        return None
    lines = []
    for aid, rows in sorted(dups.items()):
        row_nos = '、'.join(str(r[0]) for r in rows)
        names = '／'.join(r[1] or '(空白)' for r in rows)
        lines.append(f"{aid}：第 {row_nos} 列（姓名：{names}）")
    return Issue(
        3, f"application_id 重複 —— {len(dups)} 組", lines,
        "這些人在招募看板上會被合併成一個人，按推進會改到錯的人。",
        "跑 scripts/migrate_colliding_app_ids.py --dry-run 看修法。",
    )


def check_4_job_id_orphan(s3_values, s1_values):
    """職缺對得上：03 的 job_id 在 01_職缺主檔找不到 → 01 沒同步過這個職缺。"""
    header1 = s1_values[0] if s1_values else []
    c1_job = header1.index('job_id') if 'job_id' in header1 else 0
    known_jobs = {row[c1_job] for row in s1_values[1:] if len(row) > c1_job and row[c1_job]}

    header3 = s3_values[0] if s3_values else []
    c_job = _idx(header3, 'job_id')
    c_jobname = _idx(header3, '職缺名稱')
    c_name = _idx(header3, '姓名')
    missing = {}
    for i, row in enumerate(s3_values[1:], start=2):
        jid = row[c_job] if len(row) > c_job else ''
        if not jid or jid in known_jobs:
            continue
        jobname = row[c_jobname] if len(row) > c_jobname else ''
        name = row[c_name] if len(row) > c_name else ''
        missing.setdefault((jid, jobname), []).append((i, name))
    if not missing:
        return None
    lines = []
    for (jid, jobname), rows in sorted(missing.items()):
        row_desc = '；'.join(f"第{i}列（{n or '(空白)'}）" for i, n in rows)
        lines.append(f"job_id={jid}（職缺名稱：{jobname or '(空白)'}）：{row_desc}")
    return Issue(
        4, f"職缺在 01_職缺主檔 找不到 —— {len(missing)} 個職缺", lines,
        "這個職缺在招募看板上完全看不到，即使底下有應徵人在跑流程。",
        "確認這個職缺是否該存在；若是，補跑一次該職缺的同步讓 01 補上這筆。",
    )


def check_5_placeholder(s3_values):
    """無佔位字串：職缺名稱／job_id 含「➕ 新增自訂職缺」或開頭 __ → 之後所有比對都找不到那筆。"""
    header = s3_values[0] if s3_values else []
    c_job = _idx(header, 'job_id')
    c_jobname = _idx(header, '職缺名稱')
    c_name = _idx(header, '姓名')
    c_app = _idx(header, 'application_id')
    lines = []
    for i, row in enumerate(s3_values[1:], start=2):
        jid = row[c_job] if len(row) > c_job else ''
        jobname = row[c_jobname] if len(row) > c_jobname else ''
        if '➕ 新增自訂職缺' in jobname or '➕ 新增自訂職缺' in jid or jid.startswith('__') or jobname.startswith('__'):
            aid = row[c_app] if len(row) > c_app else ''
            name = row[c_name] if len(row) > c_name else ''
            lines.append(f"第 {i} 列：application_id={aid}／姓名={name or '(空白)'}／職缺名稱={jobname or '(空白)'}／job_id={jid}")
    if not lines:
        return None
    return Issue(
        5, f"佔位字串寫進主檔 —— {len(lines)} 筆", lines,
        "這筆的職缺欄位是介面上的按鈕文字，不是真正的職缺名稱，之後所有用職缺名稱/job_id比對的地方都會找不到這筆。",
        "人工確認這筆原本該歸到哪個職缺，用 Google Sheets 手動改回正確的職缺名稱／job_id。",
    )


def check_6_flow_status(s3_values):
    """流程狀態合法：值不在 FLOW_TO_STAGE 的 key 裡 → 看板讀成 screening，那個人從看板消失。"""
    header = s3_values[0] if s3_values else []
    c_flow = _idx(header, '流程狀態')
    c_name = _idx(header, '姓名')
    c_app = _idx(header, 'application_id')
    valid = set(FLOW_TO_STAGE.keys()) | {''}
    lines = []
    for i, row in enumerate(s3_values[1:], start=2):
        flow = row[c_flow] if len(row) > c_flow else ''
        if flow not in valid:
            aid = row[c_app] if len(row) > c_app else ''
            name = row[c_name] if len(row) > c_name else ''
            lines.append(f"第 {i} 列：application_id={aid}／姓名={name or '(空白)'}／流程狀態=「{flow}」")
    if not lines:
        return None
    return Issue(
        6, f"流程狀態值不在合法清單 —— {len(lines)} 筆", lines,
        "看板不認得這個文字，會把這個人歸類成初篩中或直接讀不到，等於從看板上消失。",
        "跟 hr_schema.py 的 FLOW_TO_STAGE 比對，確認這是打錯字還是新流程階段沒登記，用 Google Sheets 改回合法值。",
    )


def check_7_missing_interview(s3_values, s5_values):
    """面試紀錄不缺：流程狀態是「錄取審核」或「已通知」，但 05 用 application_id 查不到。"""
    header5 = s5_values[0] if s5_values else []
    c5_app = header5.index('application_id') if 'application_id' in header5 else 1
    interviewed_ids = {row[c5_app] for row in s5_values[1:] if len(row) > c5_app and row[c5_app]}

    header3 = s3_values[0] if s3_values else []
    c_flow = _idx(header3, '流程狀態')
    c_app = _idx(header3, 'application_id')
    c_name = _idx(header3, '姓名')
    target_flows = {'錄取審核', '已通知'}
    lines = []
    for i, row in enumerate(s3_values[1:], start=2):
        flow = row[c_flow] if len(row) > c_flow else ''
        if flow not in target_flows:
            continue
        aid = row[c_app] if len(row) > c_app else ''
        if aid and aid not in interviewed_ids:
            name = row[c_name] if len(row) > c_name else ''
            lines.append(f"第 {i} 列：application_id={aid}／姓名={name or '(空白)'}／流程狀態=「{flow}」，但 05_面試主檔查不到面試紀錄")
    if not lines:
        return None
    return Issue(
        7, f"流程狀態超前面試紀錄 —— {len(lines)} 筆", lines,
        "這個人在看板上顯示已經面試過（甚至錄取），但面試主檔沒有這筆記錄，面試通過率等統計會失真。",
        "確認這個人實際有沒有面試過；有的話補一筆 05_面試主檔記錄，沒有的話回頭確認流程狀態是不是點錯階段。",
    )


def check_8_batch_date(s3_values):
    """應徵批次日期沒被覆寫：不重複日期值 < 8 種，或單一日期佔全表 > 40% → 日期被蓋掉。

    2026-08-06 校準：原本用「單日筆數 > 100」當門檻，但那會對真實的大批次誤報
    （0708 那天真的一次篩了 131 份，檔名 0708人資搜.pdf）。原始事故的特徵不是
    絕對筆數大，而是「少數幾個日期值吃掉整張表」——831 筆只剩 4 種值、其中一天
    佔 87%。所以改用比例，絕對筆數多但分散是健康的。
    會叫的健檢才有人看，誤報一次就會被忽略一輩子。
    """
    header = s3_values[0] if s3_values else []
    c_date = _idx(header, '應徵批次日期')
    dates = [row[c_date] for row in s3_values[1:] if len(row) > c_date and row[c_date]]
    counter = Counter(dates)
    distinct = len(counter)
    total = len(dates)
    max_date, max_count = (counter.most_common(1)[0] if counter else ('', 0))
    max_share = (max_count / total) if total else 0
    if distinct >= 8 and max_share <= 0.40:
        return None
    top5 = counter.most_common(5)
    lines = [f"不重複日期值共 {distinct} 種／最集中的一天「{max_date}」佔 {max_share:.0%}"]
    lines += [f"「{d}」：{c} 筆" for d, c in top5]
    return Issue(
        8, "應徵批次日期疑似被同步覆寫", lines,
        "這些人應徵的真實日期消失了，全部被同步流程蓋成同一天（通常是今天），新進候選人數字、招募時效分析都會失真。",
        "檢查最近一次同步是否誤把「應徵批次日期」排除在保護清單外；確認 hr_schema.py 的 S3_PROTECT_ON_UPDATE 是否含這一欄。",
    )


def check_9_library_vs_sheet(s3_values):
    """履歷庫 vs Sheets 筆數：任一職缺兩邊筆數差 > 2 → 同步漏跑，靜默少人。"""
    header = s3_values[0] if s3_values else []
    c_jobname = _idx(header, '職缺名稱')
    sheet_counts = Counter(row[c_jobname] for row in s3_values[1:] if len(row) > c_jobname and row[c_jobname])

    lines = []
    for fp in sorted(glob.glob(os.path.join('resume_library', '*.json'))):
        if fp.endswith('.bak'):
            continue
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        jd = d.get('jd_name')
        if not jd:
            continue
        lib_count = len(d.get('candidates', []))
        sheet_count = sheet_counts.get(jd, 0)
        diff = lib_count - sheet_count
        if abs(diff) > 2:
            lines.append(f"「{jd}」：履歷庫 {lib_count} 筆／03_應徵主檔 {sheet_count} 筆（差 {diff:+d}）")
    if not lines:
        return None
    return Issue(
        9, f"履歷庫與 Sheets 筆數不一致 —— {len(lines)} 個職缺", lines,
        "兩邊筆數對不上，代表這個職缺有人在履歷庫裡卻沒同步進 Sheets（或反過來），該職缺的看板人數是錯的。",
        "對這個職缺重新跑一次同步；若差距是已知的孤兒紀錄（例如已知的單筆對不上個案），可略過。",
    )


def check_10_first_entry_date(s3_values, s2_values):
    """初次進庫日期不得晚於該人最早的應徵批次日期。

    2026-08-10 加入。成因：2026-08-06 的撞號修復腳本替 11 位候選人在 02_候選人主檔
    新開列，初次進庫日期直接寫成「執行當天」而不是真正的應徵日期，結果六、七月的
    10 個人被算進八月的「新進候選人」，來源圓餅圖也憑空多出 10 個「未指定」。

    這是遷移腳本的通用失敗形狀（用 today 覆蓋歷史日期），跟 check_8 是同一類但不同
    層：check_8 看 03 的應徵批次日期被覆寫，這裡看 02 的初次進庫日期被覆寫。
    分析報表的區間篩選走的是 02 這一欄，所以它錯了整份報表就錯。

    反方向（進庫早於應徵）是正常的：人才庫裡的舊人之後才投新職缺。
    """
    h3 = s3_values[0] if s3_values else []
    h2 = s2_values[0] if s2_values else []
    c_cid, c_batch, c_name = _idx(h3, 'candidate_id'), _idx(h3, '應徵批次日期'), _idx(h3, '姓名')
    # 02 的欄位不能用 _idx()——它找不到時會退回 S3_COLS 的順序（另一張表的 schema），
    # 用在 02 上會拿到毫無關係的欄號、甚至直接 ValueError 讓整份健檢掛掉。
    # 02 表頭壞掉是 check_1 之外的另一回事，這裡查不到欄位就安靜跳過這項檢查。
    if 'candidate_id' not in h2 or '初次進庫日期' not in h2:
        return None
    k_cid, k_first = h2.index('candidate_id'), h2.index('初次進庫日期')

    earliest, names = {}, {}
    for row in s3_values[1:]:
        cid = row[c_cid] if len(row) > c_cid else ''
        batch = (row[c_batch] if len(row) > c_batch else '').strip()
        if not cid or not batch:
            continue
        if cid not in earliest or batch < earliest[cid]:
            earliest[cid] = batch
        names.setdefault(cid, (row[c_name] if len(row) > c_name else '') or '(無姓名)')

    lines = []
    for n, row in enumerate(s2_values[1:], start=2):
        cid = row[k_cid] if len(row) > k_cid else ''
        cur = (row[k_first] if len(row) > k_first else '').strip()
        want = earliest.get(cid)
        if not cid or not cur or not want:
            continue
        if cur[:10] > want[:10]:
            lines.append(f"02 第{n}列 {names.get(cid, '')}（{cid}）："
                         f"初次進庫 {cur} 晚於最早應徵 {want}")
    if not lines:
        return None
    return Issue(
        10, f"初次進庫日期晚於應徵日期 —— {len(lines)} 筆", lines,
        "分析報表的統計區間是用「初次進庫日期」篩的，這一欄被蓋成執行當天的話，"
        "舊月份的人會被算進當月，新進候選人數、來源分布、漏斗全部失真。",
        "跑 scripts/fix_first_entry_date_after_migration.py --dry-run 確認後修正；"
        "並回頭檢查最近執行過的遷移腳本，是否在新增 02 列時用了 today 而非真實應徵日期。",
    )


def check_11_interview_ahead_of_stage(s3_values, s5_values):
    """05 有「已完成」的面試紀錄，但 03 的流程狀態沒到「已面試」。

    2026-08-12 加入，補 check_7 的反方向：check_7 抓「流程狀態超前面試紀錄」
    （看板說面試過了但沒紀錄），這裡抓「面試紀錄超前流程狀態」（有記分卡但看板
    還停在前面的階段）。兩邊都會讓漏斗的「進行面試」跟面試場次對不起來。

    只看面試結果是「通過」或「未通過」的紀錄——那代表面試真的發生且被評估過。
    「待定」是排了還沒填結果、「面試未到」是人根本沒出席，這兩種流程狀態停在
    約定面試是正確的，不該報。
    """
    h3 = s3_values[0] if s3_values else []
    h5 = s5_values[0] if s5_values else []
    if '面試結果' not in h5 or 'application_id' not in h5:
        return None
    i_app, i_flow = _idx(h3, 'application_id'), _idx(h3, '流程狀態')
    i_pre, i_name = _idx(h3, '結案前階段'), _idx(h3, '姓名')
    j_app, j_res = h5.index('application_id'), h5.index('面試結果')
    j_name = h5.index('姓名') if '姓名' in h5 else j_app
    j_date = h5.index('面試日期') if '面試日期' in h5 else j_app

    _ORDER = ['screening', 'recommended', 'invited', 'interview_scheduled',
              'interviewed', 'offer_pending', 'hired']
    stage_rank = {k: i for i, k in enumerate(_ORDER)}

    def rank_of(row):
        flow = (row[i_flow] if len(row) > i_flow else '').strip()
        stage = FLOW_TO_STAGE.get(flow, 'screening')
        if stage == 'rejected':
            pre = (row[i_pre] if len(row) > i_pre else '').strip()
            stage = FLOW_TO_STAGE.get(pre, 'screening')
        return stage_rank.get(stage, 0)

    by_app = {row[i_app]: row for row in s3_values[1:] if len(row) > i_app and row[i_app]}
    lines = []
    for row in s5_values[1:]:
        res = (row[j_res] if len(row) > j_res else '').strip()
        if res not in ('通過', '未通過'):
            continue
        app_id = row[j_app] if len(row) > j_app else ''
        target = by_app.get(app_id)
        if target is None:
            continue  # 孤兒紀錄是 check_7 的守備範圍，這裡不重複報
        if rank_of(target) < stage_rank['interviewed']:
            who = (row[j_name] if len(row) > j_name else '') or '(無姓名)'
            when = (row[j_date] if len(row) > j_date else '') or '(無日期)'
            flow = (target[i_flow] if len(target) > i_flow else '').strip()
            pre = (target[i_pre] if len(target) > i_pre else '').strip()
            lines.append(f"{who}（{app_id}）：05 有「{res}」紀錄（{when}），"
                         f"但 03 流程狀態＝{flow or '(空白)'}"
                         f"{f'／結案前＝{pre}' if pre else ''}")
    if not lines:
        return None
    return Issue(
        11, f"面試紀錄超前流程狀態 —— {len(lines)} 筆", lines,
        "這個人有已完成的面試記分卡，但看板上的階段還停在面試之前，"
        "漏斗的「進行面試」會少算他，面試場次跟漏斗數字對不起來。",
        "確認這個人是不是真的面試過；是的話把看板階段推到「已面試」，"
        "不是的話（例如人沒出席）把 05 那筆的面試結果改成「面試未到」。",
    )


# ── 待催辦 ────────────────────────────────────────────────────────────────
# 這一段刻意**不做成 check_N**：它不是「資料壞了」，是「有人該催了」。混進健檢的
# Issue 清單會讓主旨的 ⚠️ 同時代表兩件性質完全不同的事，久了就分不出哪封該急。
# 但它照樣出現在同一封每日信裡（信本來就每個工作日都寄），並在主旨帶一個數字。
#
# 為什麼追這個：HR推薦 46 → 主管推進 21，**55% 的流失卡在主管端**，是整條漏斗最大
# 的單一斷點，而在 2026-08-12 之前完全沒有測量基礎——「推薦日」849 筆裡只有 13 筆
# 有值（全是手動填的），因為寄推薦信那條路徑從來沒寫過這一欄。
FOLLOWUP_RULES = [
    # (流程狀態, 等誰, 幾個工作日算逾期)
    ('已推薦主管', '用人主管', 3),
    ('已傳邀約',   '候選人',   3),
]


def _workdays_since(date_str, today):
    """date_str 到 today 之間的工作日數（不含起日、含today）；不可解析回 None。

    刻意不處理國定假日——維護一份假日表的成本高於它帶來的精度，而這個數字的用途
    是「該不該催」，差一兩天不影響判斷。
    """
    try:
        d = datetime.date.fromisoformat(str(date_str)[:10])
    except Exception:
        return None
    if d > today:
        return None
    n, cur = 0, d
    while cur < today:
        cur += datetime.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def build_followup_lines(s3_values, today=None):
    """回傳 (逾期明細行, 逾期筆數, 無日期可判斷的筆數)。"""
    today = today or datetime.date.today()
    h = s3_values[0] if s3_values else []
    i_flow, i_name = _idx(h, '流程狀態'), _idx(h, '姓名')
    i_job, i_upd = _idx(h, '職缺名稱'), _idx(h, '人才狀態更新日')
    i_rec, i_recd = _idx(h, '推薦主管'), _idx(h, '推薦日')

    def g(row, i):
        return (row[i] if len(row) > i else '').strip()

    rows, no_date = [], 0
    for row in s3_values[1:]:
        flow = g(row, i_flow)
        rule = next((r for r in FOLLOWUP_RULES if r[0] == flow), None)
        if not rule:
            continue
        _, who, threshold = rule
        # 推薦日優先（語意最精準：推薦這件事發生在哪天），沒有才退回人才狀態更新日
        basis = g(row, i_recd) if flow == '已推薦主管' and g(row, i_recd) else g(row, i_upd)
        days = _workdays_since(basis, today) if basis else None
        if days is None:
            no_date += 1
            continue
        if days < threshold:
            continue
        target = g(row, i_rec) if flow == '已推薦主管' else who
        rows.append((days, f"{g(row, i_name) or '(無姓名)'}｜{g(row, i_job)}｜"
                           f"卡在「{flow}」{days} 個工作日｜等 {target or who}"))
    rows.sort(key=lambda x: -x[0])
    return [line for _, line in rows], len(rows), no_date


def format_followup(s3_values, today=None):
    lines, n, no_date = build_followup_lines(s3_values, today)
    out = []
    if lines:
        out.append(f"⏰ 待催辦 —— {n} 筆（超過 3 個工作日沒有進展）")
        for line in lines:
            out.append(f"   {line}")
        out.append("")
    if no_date:
        out.append(f"   （另有 {no_date} 筆卡在這些階段但沒有日期可判斷，"
                   "多半是 2026-08-12 補寫入路徑之前的舊資料，會隨新的推薦自然汰換）")
        out.append("")
    return out, n


def format_report(issues, known, total_rows, followup_lines=None):
    out = []
    if followup_lines:
        out.extend(followup_lines)
        out.append("── 資料健檢 ──────────────────────────────────────")
    if issues:
        for issue in issues:
            out.append(f"⚠️ [{issue.no}/{TOTAL_CHECKS}] {issue.title} —— {len(issue.lines)} 項" if len(issue.lines) != 1
                        else f"⚠️ [{issue.no}/{TOTAL_CHECKS}] {issue.title}")
            for line in issue.lines:
                out.append(f"   {line}")
            out.append(f"   → 意義：{issue.why}")
            out.append(f"   → 建議：{issue.advice}")
            out.append("")
    else:
        out.append(f"✅ 今日健檢通過（檢查 {TOTAL_CHECKS} 項 / {total_rows} 筆應徵紀錄）")
        out.append("")

    if known:
        out.append("── 已知例外（決定不處理，不觸發通知）───────────────")
        for issue, lines in known:
            for line in lines:
                out.append(f"   [{issue.no}/{TOTAL_CHECKS}] {line}")
        out.append("")
        for k, why in KNOWN_EXCEPTIONS.items():
            out.append(f"   ※ {k}：{why}")
        out.append("")
        out.append("   （這幾行是健檢的活體樣本：它們消失代表健檢自己壞了，不是資料變乾淨了）")
    return '\n'.join(out).rstrip()


def run_checks():
    sh = connect()
    s3_values = sh.worksheet('03_應徵主檔').get_all_values()
    s1_values = sh.worksheet('01_職缺主檔').get_all_values()
    s5_values = sh.worksheet('05_面試主檔').get_all_values()
    s2_values = sh.worksheet('02_候選人主檔').get_all_values()
    total_rows = max(0, len(s3_values) - 1)

    checks = [
        check_1_header(s3_values),
        check_2_row_width(s3_values),
        check_3_duplicate_app_id(s3_values),
        check_4_job_id_orphan(s3_values, s1_values),
        check_5_placeholder(s3_values),
        check_6_flow_status(s3_values),
        check_7_missing_interview(s3_values, s5_values),
        check_8_batch_date(s3_values),
        check_9_library_vs_sheet(s3_values),
        check_10_first_entry_date(s3_values, s2_values),
        check_11_interview_ahead_of_stage(s3_values, s5_values),
    ]
    # 把已知例外從「新問題」裡分出來：新問題才會寄信，已知例外只列在報告底部
    issues, known = [], []
    for c in checks:
        if c is None:
            continue
        new_lines, known_lines = _split_known(c.lines)
        if known_lines:
            known.append((c, known_lines))
        if new_lines:
            c.lines = new_lines
            issues.append(c)
    return issues, known, total_rows, s3_values


def load_email_config():
    if os.path.exists('email_config.json'):
        with open('email_config.json', 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def send_report_email(report, has_issues, followup_n=0):
    """寄健檢報告到 ADMIN_EMAIL。

    2026-08-10 改成「每個工作日都寄」（原本只在有問題時寄）。改的原因：使用者連續
    兩次問「怎麼沒收到信」——因為「沒收到信」有歧義，分不出是「今天沒問題」還是
    「健檢又壞了」。08-07 那次真的是壞了（排程有跑但 print 崩潰），從信箱看起來
    卻跟正常的日子一模一樣。

    原本擔心的「每天都寄會被忽略」用**主旨列**解決：正常是「✅ 一切正常」、有問題是
    「⚠️ 發現 N 個問題」，掃一眼主旨就知道要不要開。可以在 Gmail 設篩選器把 ✅ 的
    自動封存，只讓 ⚠️ 的留在收件匣。

    2026-08-13 從 SMTP（smtplib + app_password）改成呼叫跟 app.py 推薦信同一個
    GAS 郵件轉發服務。原本用的那組 Gmail 應用程式密碼已經在同一天因為明文外洩
    風險被使用者撤銷（見 app.py 那次改動），這支腳本原封不動的話明天早上就會
    寄信失敗。改用轉發服務後，這個專案不再有任何一處存放明文密碼。
    """
    config = load_email_config()
    relay_url = config.get('relay_url', '')
    relay_secret = config.get('relay_secret', '')
    if not relay_url or not relay_secret:
        print('（--email 已指定，但 email_config.json 沒有 relay_url/relay_secret，跳過寄信）')
        return

    _today = time.strftime('%m/%d')
    _state = (f"⚠️ HireFlow 健檢發現問題（{_today}）" if has_issues
              else f"✅ HireFlow 健檢正常（{_today}）")
    # 待催辦數放進主旨：Opus 2026-08-12 的建議——每天都寄綠燈信有習慣化風險，
    # 主旨要能 0.5 秒掃完並讓需要行動的日子在視覺上跳出來。
    subject = f"{_state}｜待催辦 {followup_n}" if followup_n else _state

    # 2026-08-13 實測：Apps Script 是先真正執行 doPost（信已經寄出去了）才把
    # 執行結果回傳給呼叫端；「取得確認回應」這一步偶爾會斷線/逾時/回傳非預期
    # 內容，但信通常已經寄出——連續測試 18 封裡，被判定「失敗」的幾封事後全
    # 部在信箱裡找到了。這裡不重試（重試 = 再寄一封重複的健檢信），單純把
    # 「無法確認」跟「真的沒寄」的訊息分開印，讓使用者不會誤判連寄信服務也壞了。
    import requests
    try:
        resp = requests.post(relay_url, json={
            "secret": relay_secret,
            "to": ADMIN_EMAIL,
            "subject": subject,
            "body": report,
        }, timeout=30)
    except Exception as e:
        print(f'（⚠️ 無法確認健檢報告是否寄出，連線例外：{type(e).__name__}: {e}｜'
              f'Google 端通常已經執行完寄信，只是確認回應沒送達，不代表真的沒寄到）')
        return
    try:
        result = resp.json()
    except Exception:
        print(f'（⚠️ 無法確認健檢報告是否寄出，收到非預期回應 HTTP {resp.status_code}｜'
              f'信通常已經寄出，只是確認回應失敗）')
        return
    if not result.get('ok'):
        print(f"（⚠️ 健檢報告確定沒有寄出，郵件轉發服務回報：{result.get('error', '未知錯誤')}）")
        return
    print(f"（已寄出健檢報告給：{ADMIN_EMAIL}）")


def main():
    # Windows 工作排程器啟動時的工作目錄不保證是本檔案所在目錄，但腳本內所有
    # 相對路徑（gsheet_config.json、email_config.json、resume_library/）都假設
    # cwd 是專案根目錄——固定 cwd 到本檔案所在目錄，不管從哪裡被呼叫都能跑。
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Windows 工作排程器的 stdout 預設是 cp950（繁體中文），印 ✅ ⚠️ 這類字元會
    # UnicodeEncodeError。2026-08-07 真實事故：排程 08:35 有跑但 exit 1，因為
    # print(report) 先炸掉、根本沒走到 send_report_email 那行，使用者既沒收到通知
    # 也看不到任何錯誤——健檢等於整個靜默失效。
    # 手動測試時因為指令裡有 PYTHONIOENCODING=utf-8 而完全測不出來，所以這種
    # 「只在排程環境才會發生」的問題，一定要用排程完全相同的指令重現過才算驗證。
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument('--email', action='store_true', help='有問題時寄報告給自己')
    args = ap.parse_args()

    issues, known, total_rows, s3_values = run_checks()
    followup_lines, followup_n = format_followup(s3_values)
    report = format_report(issues, known, total_rows, followup_lines)
    # 上面已經把 stdout 轉成 utf-8，理論上不會再炸；這層是保險——「印不出來」是
    # 顯示問題，絕不該讓它擋掉真正重要的通知（這正是 08-07 事故的形狀）。
    try:
        print(report)
    except Exception:
        print(report.encode('ascii', 'replace').decode('ascii'))

    # 每個工作日都寄（不管有沒有問題）——「沒收到信」對使用者來說有歧義，分不出是
    # 沒問題還是健檢自己壞了。改成天天寄、用主旨列區分 ✅/⚠️，這樣「該來的信沒來」
    # 本身就是一個明確的故障訊號。
    if args.email:
        send_report_email(report, bool(issues), followup_n)


if __name__ == '__main__':
    main()
