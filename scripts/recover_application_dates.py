# -*- coding: utf-8 -*-
"""
一次性回補：03_應徵主檔「應徵批次日期」被_build_master_rows/build_rows的舊bug
覆寫成「同步當天」（已在hr_schema.py加進S3_PROTECT_ON_UPDATE修好，這支只處理
過去已經寫壞的831筆歷史資料）。

回補來源：resume_library/*.json 每位候選人的「來源檔案」欄——履歷PDF的檔名/
路徑幾乎都嵌著真正的批次日期，只是格式不只一種，依精確度優先序嘗試解析：
  1. 檔名開頭 YYYYMMDD（含後面接時分秒或流水號都可，例："20260514-1.pdf"、
     "20260714143323_...pdf"）——最精確
  2. 檔名開頭 MMDD（例："0708人資搜.pdf"、"0622主動投遞.pdf"）——假設年份為2026，
     精確到日
  3. 路徑資料夾名裡的 YYYY.MM 或 YYYYMM（例："2026.03 三創晚班"、
     "202606 零件-採購專員"、"2025.11採購助理"）——只有精確到月，day補01

用 application_id（跟_build_master_rows同一套規則：APP-{104代碼}-{job_safe}）
精確比對，不是只憑候選人代碼——同一人應徵不同職缺可能來自不同批次、不同日期。
真的解析不出來的就留空，不亂猜。
"""
import glob
import json
import re

import gspread
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials as _impersonated_credentials


def job_safe(jd_name):
    return re.sub(r'[^\w\-]', '_', jd_name)[:20]


RE_YYYYMMDD = re.compile(r'(20\d{2})(\d{2})(\d{2})')
# 2026-08-03修正：原本只用^錨定開頭，抓不到「[主動投遞]0713主動投.pdf」這種
# MMDD前面還有中括號標籤文字的檔名。改成search()＋數字邊界(?<!\d)/(?!\d)，
# 只要求恰好4個連續數字前後都不是數字，不管出現在檔名哪個位置。
RE_MMDD = re.compile(r'(?<!\d)(\d{2})(\d{2})(?!\d)')
RE_FOLDER_DOT = re.compile(r'(20\d{2})\.(\d{2})')
RE_FOLDER_PLAIN = re.compile(r'(20\d{2})(\d{2})(?!\d)')


def extract_date(src_path):
    """回傳 (date_str, precision) 或 (None, None)。precision: 'day' / 'month'。"""
    if not src_path:
        return None, None
    basename = src_path.replace('\\', '/').split('/')[-1]

    m = RE_YYYYMMDD.search(basename)
    if m:
        y, mo, d = m.groups()
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{mo}-{d}", "day"

    m = RE_MMDD.search(basename)
    if m:
        mo, d = m.groups()
        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"2026-{mo}-{d}", "day"

    # 路徑資料夾層級（含所有中段資料夾名，不只最後檔名）
    for part in src_path.replace('\\', '/').split('/')[:-1]:
        m = RE_FOLDER_DOT.search(part)
        if m:
            y, mo = m.groups()
            if 1 <= int(mo) <= 12:
                return f"{y}-{mo}-01", "month"
        m = RE_FOLDER_PLAIN.search(part)
        if m:
            y, mo = m.groups()
            if 1 <= int(mo) <= 12:
                return f"{y}-{mo}-01", "month"

    # 2026-08-03補：完全沒有資料夾路徑、只有裸檔名的情況（例如
    # "[主動投遞]202606-零件部-外貿業務助理.pdf"），YYYYMM嵌在檔名本身，
    # 不是資料夾層級——再對basename本身試一次月精度解析，當最後手段。
    m = RE_FOLDER_DOT.search(basename)
    if m:
        y, mo = m.groups()
        if 1 <= int(mo) <= 12:
            return f"{y}-{mo}-01", "month"
    m = RE_FOLDER_PLAIN.search(basename)
    if m:
        y, mo = m.groups()
        if 1 <= int(mo) <= 12:
            return f"{y}-{mo}-01", "month"

    return None, None


def main():
    app_id_dates = {}   # application_id -> (date_str, precision)
    stats = {"day": 0, "month": 0, "none": 0}

    for fp in glob.glob("resume_library/*.json"):
        if fp.endswith(".bak"):
            continue
        with open(fp, encoding="utf-8") as f:
            lib = json.load(f)
        jd_name = lib.get("jd_name", "")
        if not jd_name:
            continue
        js = job_safe(jd_name)
        for c in lib.get("candidates", []):
            code = str(c.get("104代碼", "") or "")
            if not code:
                continue
            app_id = f"APP-{code}-{js}"
            date_str, precision = extract_date(c.get("來源檔案", ""))
            if date_str:
                app_id_dates[app_id] = (date_str, precision)
                stats[precision] += 1
            else:
                stats["none"] += 1

    print(f"履歷庫可解析日期：day精確 {stats['day']} 筆、月精確(day補01) {stats['month']} 筆、"
          f"解析不出來 {stats['none']} 筆")

    with open("gsheet_config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    source_creds, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    target_creds = _impersonated_credentials.Credentials(
        source_credentials=source_creds,
        target_principal=cfg["impersonate_sa"],
        target_scopes=["https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive.readonly"],
    )
    gc = gspread.authorize(target_creds)
    sh = gc.open_by_key(cfg["spreadsheet_id"])
    ws3 = sh.worksheet("03_應徵主檔")
    hdr = ws3.row_values(1)
    col_appid = hdr.index("application_id")
    col_date = hdr.index("應徵批次日期") + 1  # 1-based for update_cell
    rows = ws3.get_all_values()[1:]

    updates = []
    matched = 0
    for i, row in enumerate(rows, start=2):
        app_id = row[col_appid] if len(row) > col_appid else ""
        if app_id in app_id_dates:
            new_date, precision = app_id_dates[app_id]
            cur = row[col_date - 1] if len(row) >= col_date else ""
            if cur != new_date:
                updates.append(gspread.Cell(i, col_date, new_date))
            matched += 1

    print(f"03_應徵主檔831筆裡，能對到履歷庫日期的：{matched} 筆；實際需要更新（跟現值不同）：{len(updates)} 筆")

    if updates:
        ws3.update_cells(updates, value_input_option="RAW")
        print("已寫入。")
    else:
        print("沒有需要更新的（可能都已經一致）。")


if __name__ == "__main__":
    main()
