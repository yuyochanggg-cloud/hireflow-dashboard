"""
hr_schema.py — 六主檔欄名與狀態值映射的單一來源（Single Source of Truth）

收斂自 app.py（真實來源，寫入路徑主體）、dashboard.py（讀取/顯示路徑）、
sync_to_gsheet.py（獨立 CLI 同步腳本）。三個檔案原本各自定義部分重複的
欄名/狀態值常數；此檔統一定義後，三處改為 import 使用。

注意：本檔只搬移常數定義，不改變任何函式行為邏輯。
"""

# ── 02/03/04 主檔欄名（來源：app.py _S2_COLS/_S3_COLS/_S4_COLS，寫入路徑主體）──
S2_COLS = [
    "candidate_id", "真實姓名", "104代碼", "Email",
    "電話（遮蔽）", "居住地", "最近應徵職缺",
    "初次進庫日期", "最後更新日期", "來源檔案", "備註",
]
S3_COLS = [
    "application_id", "job_id", "candidate_id",
    "職缺名稱", "姓名", "104代碼",
    "應徵批次日期", "應徵來源",
    "AI初篩狀態", "AI評級", "AI分數",
    "HR初篩狀態", "HR複審日",
    "推薦主管", "推薦日",
    "人才狀態", "流程狀態",
    "人才狀態更新日", "備註",
]
# 2026-07-09 修正：原本只有13欄，跟 Google Sheets 實際的19欄結構錯位，
# 從第9欄開始全部寫錯位置（AI評級被寫成"待定"、AI分數被寫成"初篩完成"等）。
# 已比對真實試算表逐欄校正；HR初篩狀態/HR複審日/推薦主管/推薦日/人才狀態/
# 流程狀態/人才狀態更新日/備註 這幾欄改由 update_stage 等函式按欄名動態寫入，
# _build_master_rows 產生的批次同步只在「新建列」時給預設值，「更新既有列」時
# 靠 _upsert_rows 的 protect_cols 機制跳過，避免覆蓋 HR 已填的資料。
S3_PROTECT_ON_UPDATE = [
    "HR初篩狀態", "HR複審日", "推薦主管", "推薦日",
    "人才狀態", "流程狀態", "人才狀態更新日", "備註",
]
S4_COLS = [
    "score_id", "application_id", "candidate_id", "job_id",
    "職缺名稱", "姓名", "104代碼",
    "初篩判定", "綜合推薦度", "加權總分", "技能契合分數",
    "穩定度評估", "居住地", "通勤評估",
    "客觀戰功亮點", "缺口與潛在地雷", "面試深挖題",
    "未來適配建議",
    "薪資期待", "可到職日", "下次聯繫日",
    "評分維度明細（JSON）", "評分日期", "來源檔案",
]

# ── 05/06 主檔 header（來源：sync_to_gsheet.py SHEET_HEADERS，僅此腳本使用，
#    初始化工作表 header 用；並非跨檔重複定義，搬移至此僅為集中管理）──────
SHEET_HEADERS = {
    "05_面試主檔": [
        "interview_id", "application_id", "candidate_id", "job_id",
        "職缺名稱", "姓名",
        "面試日期", "面試時間", "面試官", "面試類型", "面試結果",
        "維度1名稱", "維度1分數",
        "維度2名稱", "維度2分數",
        "維度3名稱", "維度3分數",
        "維度4名稱", "維度4分數",
        "面試官備註", "下一步行動", "記錄時間",
    ],
    "06_員工主檔": [
        "employee_id", "candidate_id", "job_id",
        "真實姓名", "職位", "部門", "工作地點",
        "預計報到日", "實際報到日", "薪資（月）",
        "銀行帳號已收", "錄取通知寄出", "報到前Form已填", "MIS聯絡單已送",
        "Workspace帳號", "POS帳號", "華苓帳號", "飛騰帳號",
        "門禁卡", "雲端學院帳號",
        "OJT主管", "試用期結束日", "Onboarding狀態", "備註",
        # 2026-07-13 新增：招募→留任回饋迴路（E），供日後回頭檢視AI評分準不準
        "三個月考核結果", "試用期通過", "離職日", "離職原因類別",
        # 2026-07-14 新增：聘用類型（加在尾端，避免中段插入造成既有資料欄位錯位）
        "聘用類型",
    ],
}

# ── UI 顯示用的流程階段標籤表（來源：dashboard.py STAGES）────────────────
# key, label, icon, bg, fg
STAGES = [
    ("screening",           "初篩中",      "🔍", "#ede9fe", "#5b21b6"),  # violet
    ("recommended",         "已推薦主管",  "👔", "#fef9c3", "#713f12"),  # yellow
    ("interview_scheduled", "已約面試",    "📅", "#fef3c7", "#92400e"),  # amber
    ("interviewed",         "已面試",      "✅", "#d1fae5", "#065f46"),  # emerald
    ("offer_pending",       "錄取審核",    "📋", "#fce7f3", "#9d174d"),  # rose
    ("hired",               "已通知",      "🎉", "#dcfce7", "#14532d"),  # green
    ("rejected",            "已結案",      "🏁", "#f0f9ff", "#0369a1"),  # blue
]
STAGE_KEYS  = [s[0] for s in STAGES]
STAGE_LABEL = {s[0]: s[1] for s in STAGES}
STAGE_ICON  = {s[0]: s[2] for s in STAGES}
STAGE_BG    = {s[0]: s[3] for s in STAGES}
STAGE_FG    = {s[0]: s[4] for s in STAGES}

# ── 「流程狀態」中文文字 ↔ UI stage key 映射（來源：dashboard.py）──────────
FLOW_TO_STAGE = {
    "初篩完成":   "screening",
    "已推薦主管": "recommended",
    "已約面試":   "interview_scheduled",
    "已面試":     "interviewed",
    "面試完成":   "interviewed",
    "錄取審核":   "offer_pending",
    "已錄取":     "hired",
    "已通知":     "hired",
    "已結案":     "rejected",
    "已拒絕":     "rejected",
}
STAGE_TO_FLOW = {
    "screening":           "初篩完成",
    "recommended":         "已推薦主管",
    "interview_scheduled": "已約面試",
    "interviewed":         "已面試",
    "offer_pending":       "錄取審核",
    "hired":               "已通知",
    "rejected":            "已結案",
}

# ── 面試結果映射（來源：dashboard.py _RESULT_MAP）────────────────────────
RESULT_MAP = {
    "通過": "pass", "pass": "pass",
    "未通過": "fail", "fail": "fail",
    "待定": "pending",
}

# ── 職缺狀態映射（來源：dashboard.py _STATUS_MAP）────────────────────────
STATUS_MAP = {
    "招募中": "open", "暫停中": "paused", "已結束": "closed",
    "open": "open", "paused": "paused", "closed": "closed",
}
