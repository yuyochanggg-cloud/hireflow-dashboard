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
import smtplib
from collections import Counter
from email.mime.text import MIMEText

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials

from hr_schema import S3_COLS, FLOW_TO_STAGE

# 健檢警報收件人（使用者實際會看的信箱）。刻意寫死而非讀 email_config.json 的
# recipients——那份清單是候選人推薦信收件主管名單（7位部門主管），用途完全不同，
# 混用會把內部資料健檢報告寄給不相關的外部收件人。
ADMIN_EMAIL = 'yunyu@ls3c.com.tw'


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


def format_report(issues, total_rows):
    if not issues:
        return f"✅ 今日健檢通過（檢查 9 項 / {total_rows} 筆應徵紀錄）"
    out = []
    for issue in issues:
        out.append(f"⚠️ [{issue.no}/9] {issue.title} —— {len(issue.lines)} 項" if len(issue.lines) != 1
                    else f"⚠️ [{issue.no}/9] {issue.title}")
        for line in issue.lines:
            out.append(f"   {line}")
        out.append(f"   → 意義：{issue.why}")
        out.append(f"   → 建議：{issue.advice}")
        out.append("")
    return '\n'.join(out).rstrip()


def run_checks():
    sh = connect()
    s3_values = sh.worksheet('03_應徵主檔').get_all_values()
    s1_values = sh.worksheet('01_職缺主檔').get_all_values()
    s5_values = sh.worksheet('05_面試主檔').get_all_values()
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
    ]
    issues = [c for c in checks if c is not None]
    return issues, total_rows


def load_email_config():
    if os.path.exists('email_config.json'):
        with open('email_config.json', 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def send_report_email(report):
    """只在有問題時被呼叫——每天都寄會被忽略，等於沒做。寄到 ADMIN_EMAIL。"""
    config = load_email_config()
    sender = config.get('sender_email', '')
    password = config.get('app_password', '')
    if not sender or not password:
        print('（--email 已指定，但 email_config.json 沒有 sender_email/app_password，跳過寄信）')
        return
    smtp_server = config.get('smtp_server', 'smtp.gmail.com')
    smtp_port = int(config.get('smtp_port', 465))

    msg = MIMEText(report, 'plain', 'utf-8')
    msg['From'] = sender
    msg['To'] = ADMIN_EMAIL
    msg['Subject'] = "【HireFlow 每日健檢】發現問題"

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception:
        with smtplib.SMTP(smtp_server, 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
    print(f"（已寄出健檢報告給：{ADMIN_EMAIL}）")


def main():
    # Windows 工作排程器啟動時的工作目錄不保證是本檔案所在目錄，但腳本內所有
    # 相對路徑（gsheet_config.json、email_config.json、resume_library/）都假設
    # cwd 是專案根目錄——固定 cwd 到本檔案所在目錄，不管從哪裡被呼叫都能跑。
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    ap = argparse.ArgumentParser()
    ap.add_argument('--email', action='store_true', help='有問題時寄報告給自己')
    args = ap.parse_args()

    issues, total_rows = run_checks()
    report = format_report(issues, total_rows)
    print(report)

    if args.email and issues:
        send_report_email(report)


if __name__ == '__main__':
    main()
