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
    # 2026-07-15 新增：結案時記錄「結案前是卡在哪個階段」，供漏斗數據計算用
    # （流程狀態一旦變成「已結案」，原本走到哪一步就看不出來了）。
    "結案前階段",
    # 2026-07-23 新增：結案原因（訊息未回/面試未到/面試未通過/候選人婉拒），
    # 之前結案沒有記原因，事後完全查不出來是為什麼結案、面試通過率也因此
    # 失真，這欄就是為了不要再靠事後回補猜測。
    "結案原因",
]
# 2026-07-09 修正：原本只有13欄，跟 Google Sheets 實際的19欄結構錯位，
# 從第9欄開始全部寫錯位置（AI評級被寫成"待定"、AI分數被寫成"初篩完成"等）。
# 已比對真實試算表逐欄校正；HR初篩狀態/HR複審日/推薦主管/推薦日/人才狀態/
# 流程狀態/人才狀態更新日/備註 這幾欄改由 update_stage 等函式按欄名動態寫入，
# _build_master_rows 產生的批次同步只在「新建列」時給預設值，「更新既有列」時
# 靠 _upsert_rows 的 protect_cols 機制跳過，避免覆蓋 HR 已填的資料。
S3_PROTECT_ON_UPDATE = [
    "HR初篩狀態", "HR複審日", "推薦主管", "推薦日",
    "人才狀態", "流程狀態", "人才狀態更新日", "備註", "結案前階段", "結案原因",
]

# 結案原因選項（單一來源，看板/候選人頁的結案按鈕共用）
CLOSE_REASONS = ["訊息未回", "面試未到", "面試未通過", "候選人婉拒"]
# 選了這些原因，結案時順便同步一筆05_面試主檔紀錄（面試結果=未通過），
# 避免分析報表的面試通過率又因為沒人回頭填記分卡而失真。
CLOSE_REASON_TO_INTERVIEW_NOTE = {
    "面試未到": "no-show，約定面試未出席",
    "面試未通過": "面試未通過",
}
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
    # 2026-07-15 新增：AI初篩總數目前只存在app.py本機的resume_library檔案，
    # dashboard.py讀不到——每次批次初篩完成就append一列，讓dashboard算得出
    # 「總共初篩了多少履歷」這個使用者最想看的漏斗起點數字。append-only，
    # 不是維護一個累計cell：重跑批次頂多多一列，看得到、刪得掉，還能拆
    # per職缺/per時間的切片。
    "07_AI初篩統計": [
        "批次日期", "job_id", "職缺名稱", "初篩份數", "合格數",
    ],
}

# ── UI 顯示用的流程階段標籤表（來源：dashboard.py STAGES）────────────────
# key, label, icon, bg, fg
STAGES = [
    ("screening",           "初篩中",      "🔍", "#ede9fe", "#5b21b6"),  # violet
    ("recommended",         "已推薦主管",  "👔", "#fef9c3", "#713f12"),  # yellow
    # 2026-07-15 新增：已推薦主管→約定面試之間補一個「已傳邀約」，代表
    # HR已發面試邀請信件/電話給候選人、還在等對方回覆時間。
    ("invited",             "已傳邀約",    "📨", "#ffedd5", "#9a3412"),  # orange
    ("interview_scheduled", "約定面試",    "📅", "#fef3c7", "#92400e"),  # amber
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

# ── Grade（AI綜合推薦度）徽章顏色 —— 單一權威來源 ─────────────────────
# 2026-07-14 Fable設計審查前，app.py跟dashboard.py各自重複定義了一份、
# 顏色還互相打架（Grade B在app.py是藍色系、dashboard.py是靛紫色系）。
# 收斂結論：跟隨系統主色（藍），dashboard.py那份靛紫版本淘汰。
GRADE_META = {
    "A": {"bg": "#fffbeb", "fg": "#92400e", "border": "#f59e0b", "icon": "🏆"},
    "B": {"bg": "#eff6ff", "fg": "#1e40af", "border": "#3b82f6", "icon": "✅"},
    "C": {"bg": "#f3f4f6", "fg": "#374151", "border": "#9ca3af", "icon": "📋"},
}
GRADE_DEFAULT = {"bg": "#f8fafc", "fg": "#475569", "border": "#9ca3af", "icon": "📋"}


def grade_badge_html(grade: str) -> str:
    """小型圓角徽章（適合看板卡片、清單列這類空間有限的地方）。"""
    m = GRADE_META.get(grade, GRADE_DEFAULT)
    return (f'<span style="background:{m["bg"]};color:{m["fg"]};'
            f'border:1.5px solid {m["border"]};border-radius:4px;'
            f'padding:1px 5px;font-weight:800;font-size:0.68rem;">'
            f'{m["icon"]}{grade}</span>')

# ── 「流程狀態」中文文字 ↔ UI stage key 映射（來源：dashboard.py）──────────
# 2026-07-15：新增「已傳邀約」階段，並把 interview_scheduled 的顯示文字從
# 「已約面試」改成「約定面試」。FLOW_TO_STAGE 同時保留舊文字「已約面試」
# 做向下相容——Google Sheets裡舊資料寫的是這個字，不會因為改名就讀不到。
FLOW_TO_STAGE = {
    "初篩完成":   "screening",
    "已推薦主管": "recommended",
    "已傳邀約":   "invited",
    "已約面試":   "interview_scheduled",  # 舊資料相容（改名前寫入的文字）
    "約定面試":   "interview_scheduled",
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
    "invited":             "已傳邀約",
    "interview_scheduled": "約定面試",
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
