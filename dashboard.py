"""
ECLIFE HireFlow — 招募任用儀表板
dashboard.py — 獨立於 app.py 運行
啟動：python -m streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import json, os, html as _html, io, calendar as _cal
from datetime import datetime, date, timedelta
import urllib.parse

try:
    import gspread
    from google.oauth2.service_account import Credentials as _SACredentials
    import google.oauth2.credentials
    import subprocess as _sp
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

_SA_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="ECLIFE HireFlow",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* ── Design tokens ────────────────────────────────────── */
:root {
  --p:       #4f46e5;   /* indigo-600  — primary     */
  --p-lite:  #e0e7ff;   /* indigo-100  — tint        */
  --p-dark:  #3730a3;   /* indigo-800  — hover/dark  */
  --accent:  #818cf8;   /* indigo-400  — light accent */

  --ok:      #059669;  --ok-bg:   #ecfdf5;  --ok-bd:   #6ee7b7;
  --warn:    #d97706;  --warn-bg: #fffbeb;  --warn-bd: #fcd34d;
  --err:     #dc2626;  --err-bg:  #fef2f2;  --err-bd:  #fca5a5;

  --text:    #111827;
  --muted:   #6b7280;
  --border:  #e5e7eb;
  --surface: #f9fafb;
  --surf-2:  #f3f4f6;
  --white:   #ffffff;

  --sh-xs:  0 1px 2px rgba(0,0,0,.06);
  --sh-sm:  0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04);
  --sh-md:  0 4px 12px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.04);
  --sh-p:   0 4px 14px rgba(79,70,229,.28);

  --r-sm: 7px; --r: 10px; --r-lg: 14px;

  --font-d: "Outfit", system-ui, sans-serif;
  --font-b: "DM Sans", system-ui, sans-serif;
  --font-m: "JetBrains Mono", monospace;
}

/* ── Base ─────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: var(--font-b) !important;
  color: var(--text) !important;
  -webkit-font-smoothing: antialiased !important;
}

/* Headings */
h1 {
  font-family: var(--font-d) !important;
  font-weight: 800 !important;
  font-size: 1.65rem !important;
  letter-spacing: -.035em !important;
  color: var(--text) !important;
  line-height: 1.15 !important;
}
h2, h3 {
  font-family: var(--font-d) !important;
  font-weight: 700 !important;
  letter-spacing: -.02em !important;
}

/* ── Metric cards ─────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--white) !important;
  border: 1px solid var(--border) !important;
  border-left: 4px solid var(--p) !important;
  border-radius: var(--r) !important;
  padding: 16px 20px !important;
  box-shadow: var(--sh-xs) !important;
  transition: box-shadow .18s, transform .18s !important;
}
[data-testid="stMetric"]:hover {
  box-shadow: var(--sh-md) !important;
  transform: translateY(-1px) !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-family: var(--font-m) !important;
  font-size: 2.1rem !important;
  font-weight: 700 !important;
  color: var(--p) !important;
  letter-spacing: -.02em !important;
}
[data-testid="stMetric"] label {
  font-size: 0.65rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: .1em !important;
  color: var(--muted) !important;
  font-family: var(--font-b) !important;
}

/* ── Buttons ──────────────────────────────────────────── */
[data-testid="stButton"] button[kind="primary"] {
  background: var(--p) !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-family: var(--font-b) !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  color: #fff !important;
  letter-spacing: .01em !important;
  box-shadow: var(--sh-xs) !important;
  transition: background .15s, box-shadow .15s, transform .12s !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
  background: var(--p-dark) !important;
  box-shadow: var(--sh-p) !important;
  transform: translateY(-1px) !important;
}
[data-testid="stButton"] button[kind="secondary"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-sm) !important;
  background: var(--white) !important;
  color: var(--text) !important;
  font-family: var(--font-b) !important;
  font-size: 0.875rem !important;
  transition: border-color .15s, background .15s !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover {
  border-color: var(--p) !important;
  background: var(--p-lite) !important;
  color: var(--p) !important;
}

/* ── Cards / containers ───────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] > div {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  box-shadow: var(--sh-xs) !important;
  padding: 14px 18px !important;
  background: var(--white) !important;
  transition: box-shadow .18s, transform .15s !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div:hover {
  box-shadow: var(--sh-md) !important;
}

/* ── Expanders ────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  background: var(--white) !important;
  box-shadow: var(--sh-xs) !important;
}
[data-testid="stExpander"] summary {
  font-weight: 600 !important;
  font-family: var(--font-b) !important;
  color: var(--text) !important;
}

/* ── Form elements ────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
  border-radius: var(--r-sm) !important;
  border-color: var(--border) !important;
  font-family: var(--font-b) !important;
  transition: border-color .15s, box-shadow .15s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--p) !important;
  box-shadow: 0 0 0 3px rgba(79,70,229,.15) !important;
  outline: none !important;
}
[data-testid="stSelectbox"] > div > div {
  border-radius: var(--r-sm) !important;
  border-color: var(--border) !important;
}

/* ── Tabs ─────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
  font-family: var(--font-b) !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  color: var(--muted) !important;
  transition: color .15s !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--p) !important;
  border-bottom-color: var(--p) !important;
}

/* ── Alerts ───────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: var(--r) !important; }

/* ── HR ───────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── Download button ──────────────────────────────────── */
[data-testid="stDownloadButton"] button {
  border-radius: var(--r-sm) !important;
  font-family: var(--font-b) !important;
}

/* ── Sidebar ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #0c1220 !important;
  border-right: 1px solid #1a2540 !important;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; }
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }

/* Nav items */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  display: block !important;
  padding: 9px 14px !important;
  border-radius: var(--r-sm) !important;
  font-size: 0.875rem !important;
  font-weight: 500 !important;
  font-family: var(--font-b) !important;
  color: #94a3b8 !important;
  cursor: pointer !important;
  transition: background .15s, color .15s !important;
  margin-bottom: 2px !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: #1a2540 !important;
  color: #e2e8f0 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] label:has([aria-checked="true"]) {
  background: #1a2540 !important;
  color: #c7d2fe !important;
  border-left: 3px solid var(--accent) !important;
}

/* Sidebar caption / small text */
[data-testid="stSidebar"] [data-testid="stText"] small,
[data-testid="stSidebar"] small { color: #475569 !important; }

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* ── Checkbox ─────────────────────────────────────────── */
[data-testid="stCheckbox"] label {
  font-family: var(--font-b) !important;
  font-size: 0.875rem !important;
}

/* ── Spinner ──────────────────────────────────────────── */
[data-testid="stSpinner"] { color: var(--p) !important; }

/* ── Plotly chart borders ─────────────────────────────── */
[data-testid="stPlotlyChart"] {
  border-radius: var(--r) !important;
  overflow: hidden !important;
}

/* ── Caption ──────────────────────────────────────────── */
[data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: 0.78rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────
CONFIG_FILE       = "gsheet_config.json"   # shared with sync_to_gsheet.py
LAST_RESULTS_FILE = "last_session_results.json"

STAGES = [
    # key,                   label,      icon, bg,        fg
    ("screening",           "初篩中",   "🔍", "#ede9fe", "#5b21b6"),  # violet
    ("interview_scheduled", "已約面試", "📅", "#fef3c7", "#92400e"),  # amber
    ("interviewed",         "已面試",   "✅", "#d1fae5", "#065f46"),  # emerald
    ("offer_pending",       "錄取審核", "📋", "#fce7f3", "#9d174d"),  # rose
    ("hired",               "已錄取",   "🎉", "#dcfce7", "#14532d"),  # green
    ("rejected",            "已結案",   "❌", "#f3f4f6", "#374151"),  # slate
]
STAGE_KEYS  = [s[0] for s in STAGES]
STAGE_LABEL = {s[0]: s[1] for s in STAGES}
STAGE_ICON  = {s[0]: s[2] for s in STAGES}
STAGE_BG    = {s[0]: s[3] for s in STAGES}
STAGE_FG    = {s[0]: s[4] for s in STAGES}

GRADE_META = {
    # grade: (bg, text, border, icon)
    "A": ("#fffbeb", "#78350f", "#f59e0b", "🏆"),  # amber
    "B": ("#ede9fe", "#3730a3", "#6366f1", "✅"),  # indigo
    "C": ("#f3f4f6", "#374151", "#9ca3af", "📋"),  # slate
}
RESULT_LABEL = {"pending": "待定", "pass": "通過", "fail": "未通過"}
RESULT_COLOR = {"pending": "#d97706", "pass": "#059669", "fail": "#dc2626"}
WD_ZH = ["一", "二", "三", "四", "五", "六", "日"]

# ── Config ────────────────────────────────────────────────────
# CONFIG_FILE shared with sync_to_gsheet.py

@st.cache_data(ttl=30)
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def db_ok() -> bool:
    return bool(_get_spreadsheet_id())

def _get_spreadsheet_id() -> str:
    sid = load_config().get("spreadsheet_id", "")
    if sid:
        return sid
    try:
        return (st.secrets.get("gcp", {}).get("spreadsheet_id") or
                st.secrets.get("spreadsheet_id", ""))
    except Exception:
        return ""

@st.cache_resource(ttl=3000)
def _get_gc():
    """Return authorised gspread client. Priority: st.secrets SA → local SA JSON → gcloud token."""
    if not HAS_GSPREAD:
        return None
    # 1. Streamlit Cloud / st.secrets service account
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        creds = _SACredentials.from_service_account_info(sa_info, scopes=_SA_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        pass
    # 2. Local service_account.json
    local_sa = os.path.join(os.path.dirname(__file__), "service_account.json")
    if os.path.exists(local_sa):
        try:
            creds = _SACredentials.from_service_account_file(local_sa, scopes=_SA_SCOPES)
            return gspread.authorize(creds)
        except Exception:
            pass
    # 3. Fallback: gcloud ADC token (local dev)
    try:
        result = _sp.run("gcloud auth print-access-token",
                         capture_output=True, text=True, shell=True)
        token = result.stdout.strip()
        if token:
            creds = google.oauth2.credentials.Credentials(token=token)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def _get_sheet():
    gc = _get_gc()
    if not gc:
        return None
    sid = _get_spreadsheet_id()
    if not sid:
        return None
    try:
        return gc.open_by_key(sid)
    except Exception:
        return None

# ── Stage / status mapping ────────────────────────────────────
FLOW_TO_STAGE = {
    "初篩完成":   "screening",
    "已推薦主管": "interview_scheduled",
    "已約面試":   "interview_scheduled",
    "已面試":     "interviewed",
    "面試完成":   "interviewed",
    "錄取審核":   "offer_pending",
    "已錄取":     "hired",
    "已結案":     "rejected",
    "已拒絕":     "rejected",
}
STAGE_TO_FLOW = {
    "screening":           "初篩完成",
    "interview_scheduled": "已約面試",
    "interviewed":         "已面試",
    "offer_pending":       "錄取審核",
    "hired":               "已錄取",
    "rejected":            "已結案",
}
_RESULT_MAP = {
    "通過": "pass", "pass": "pass",
    "未通過": "fail", "fail": "fail",
    "待定": "pending",
}
_STATUS_MAP = {
    "招募中": "open", "暫停中": "paused", "已結束": "closed",
    "open": "open", "paused": "paused", "closed": "closed",
}

# ── Sheets reader ─────────────────────────────────────────────
def _sheet_to_dicts(sh, name: str) -> list:
    try:
        ws = sh.worksheet(name)
        rows = ws.get_all_values()
        if len(rows) < 1:
            return []
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:] if any(row)]
    except Exception as e:
        st.error(f"讀取 {name} 失敗：{e}")
        return []

@st.cache_data(ttl=60, show_spinner="載入資料中…")
def _load_all_sheets() -> dict:
    sh = _get_sheet()
    if not sh:
        return {}
    names = ["01_職缺主檔", "02_候選人主檔", "03_應徵主檔",
             "04_評分主檔", "05_面試主檔", "06_員工主檔"]
    return {n: _sheet_to_dicts(sh, n) for n in names}

def _invalidate():
    _load_all_sheets.clear()

# ── Fetch functions ───────────────────────────────────────────
def fetch_all_jobs() -> list:
    data = _load_all_sheets()
    result = []
    for row in data.get("01_職缺主檔", []):
        jid = row.get("job_id", "")
        if not jid:
            continue
        result.append({
            "id":         jid,
            "title":      row.get("職缺名稱", ""),
            "department": row.get("工作地點", ""),
            "headcount":  1,
            "status":     _STATUS_MAP.get(row.get("狀態", ""), "open"),
        })
    return result

def fetch_all_candidates() -> list:
    data = _load_all_sheets()
    apps  = data.get("03_應徵主檔", [])
    score = data.get("04_評分主檔", [])
    cands = data.get("02_候選人主檔", [])

    app_map: dict = {}
    for a in apps:
        cid = a.get("candidate_id", "")
        if not cid:
            continue
        # 同一候選人有多筆 application，保留流程狀態最後更新的那筆
        existing = app_map.get(cid)
        if not existing:
            app_map[cid] = a
        else:
            # 以建立時間較新者為主（較新 = 更能代表目前進度）
            if a.get("建立時間", "") > existing.get("建立時間", ""):
                app_map[cid] = a

    score_map: dict = {}
    for s in score:
        cid = s.get("candidate_id") or s.get("cand_id", "")
        if cid and cid not in score_map:
            score_map[cid] = s

    result = []
    for c in cands:
        cid = c.get("candidate_id", "")
        if not cid:
            continue
        a = app_map.get(cid, {})
        s = score_map.get(cid, {})
        grade_raw = (a.get("綜合推薦度") or s.get("綜合推薦度") or "").strip().upper()
        grade = grade_raw[0] if grade_raw and grade_raw[0] in ("A", "B", "C") else "C"
        stage = FLOW_TO_STAGE.get(a.get("流程狀態", ""), "screening")
        result.append({
            "id":              cid,
            "name":            c.get("真實姓名", ""),
            "code_104":        c.get("104代碼", ""),
            "email":           c.get("Email", ""),
            "source":          c.get("來源", a.get("應徵來源", "")),
            "job_opening_id":  a.get("job_id", ""),
            "grade":           grade,
            "stage":           stage,
            "created_at":      c.get("建立日期", a.get("建立時間", "")),
            "stability":       s.get("穩定度評估", ""),
            "commute":         s.get("通勤評估", ""),
            "highlights":      s.get("客觀戰功亮點", ""),
            "gaps":            s.get("缺口與潛在地雷", ""),
            "screening_notes": a.get("初篩判定", s.get("初篩判定", "")),
        })
    return result

def fetch_all_interviews() -> list:
    data = _load_all_sheets()
    result = []
    for row in data.get("05_面試主檔", []):
        ivid = row.get("interview_id", "")
        if not ivid:
            continue
        d = row.get("面試日期", "")
        t = row.get("面試時間", "")
        if d and t:
            scheduled_at = f"{d}T{t}" if "T" not in d else d
        else:
            scheduled_at = d
        result.append({
            "id":               ivid,
            "candidate_id":     row.get("candidate_id", ""),
            "application_id":   row.get("application_id", ""),
            "scheduled_at":     scheduled_at,
            "interviewer":      row.get("面試官", ""),
            "result":           _RESULT_MAP.get(row.get("面試結果", ""), "pending"),
            "notes":            row.get("面試官備註", ""),
            "duration_minutes": 60,
            "location":         "",
        })
    return result

def fetch_all_hires() -> list:
    data = _load_all_sheets()
    result = []
    for row in data.get("06_員工主檔", []):
        eid = row.get("employee_id", "")
        cid = row.get("candidate_id", "")
        if not (eid or cid):
            continue
        result.append({
            "id":              eid or cid,
            "candidate_id":    cid,
            "job_id":          row.get("job_id", ""),
            "start_date":      row.get("預計報到日", ""),
            "employment_type": "全職",
            "proposed_salary": None,
            # 06_員工主檔 checklist 欄位直接用中文 key
            "錄取通知寄出":    row.get("錄取通知寄出", ""),
            "銀行帳號已收":    row.get("銀行帳號已收", ""),
            "報到前Form已填":  row.get("報到前Form已填", ""),
            "MIS聯絡單已送":   row.get("MIS聯絡單已送", ""),
            "Workspace帳號":   row.get("Workspace帳號", ""),
            "POS帳號":         row.get("POS帳號", ""),
            "華苓帳號":        row.get("華苓帳號", ""),
            "飛騰帳號":        row.get("飛騰帳號", ""),
            "門禁卡":          row.get("門禁卡", ""),
            "雲端學院帳號":    row.get("雲端學院帳號", ""),
        })
    return result

def _candidates_with_join(rows: list, jobs: list) -> list:
    job_map = {j["id"]: j["title"] for j in jobs}
    result = []
    for c in rows:
        c2 = dict(c)
        c2["_job_title"] = job_map.get(str(c.get("job_opening_id", "")), "")
        result.append(c2)
    return result

def _interviews_with_join(ivs: list, cands: list, jobs: list) -> list:
    cand_map = {c["id"]: c for c in cands}
    job_map  = {j["id"]: j["title"] for j in jobs}
    result = []
    for iv in ivs:
        iv2 = dict(iv)
        c = cand_map.get(str(iv.get("candidate_id", "")), {})
        iv2["_cand_name"]  = c.get("name", "?")
        iv2["_cand_stage"] = c.get("stage", "")
        iv2["_job_title"]  = job_map.get(str(c.get("job_opening_id", "")), "")
        result.append(iv2)
    return sorted(result, key=lambda x: str(x.get("scheduled_at") or ""))

# ── Write Helpers ─────────────────────────────────────────────
def _upsert_row(ws, key_col: str, data: dict) -> bool:
    rows = ws.get_all_values()
    if not rows:
        return False
    headers = rows[0]
    key_val = str(data.get(key_col, ""))
    row_n = None
    if key_val and key_col in headers:
        col_idx = headers.index(key_col)
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > col_idx and row[col_idx] == key_val:
                row_n = i
                break
    if row_n:
        cells = []
        for ci, h in enumerate(headers):
            if h in data:
                cells.append(gspread.Cell(row_n, ci + 1, str(data[h])))
        if cells:
            ws.update_cells(cells, value_input_option="RAW")
    else:
        ws.append_row([str(data.get(h, "")) for h in headers],
                      value_input_option="RAW", insert_data_option="INSERT_ROWS")
    return True

# ── Write Wrappers ────────────────────────────────────────────
def update_stage(cid: str, new_stage: str) -> bool:
    sh = _get_sheet()
    if not sh:
        return False
    try:
        ws = sh.worksheet("03_應徵主檔")
        flow = STAGE_TO_FLOW.get(new_stage, new_stage)
        rows = ws.get_all_values()
        if not rows:
            return False
        headers = rows[0]
        if "candidate_id" not in headers or "流程狀態" not in headers:
            return False
        cid_col  = headers.index("candidate_id")
        flow_col = headers.index("流程狀態")
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > cid_col and row[cid_col] == cid:
                ws.update_cell(i, flow_col + 1, flow)
                break  # 只更新第一筆，避免多職缺應徵互蓋
        _invalidate()
        return True
    except Exception as e:
        st.error(f"更新失敗：{e}")
        return False

def save_interview(data: dict) -> bool:
    sh = _get_sheet()
    if not sh:
        return False
    try:
        ws = sh.worksheet("05_面試主檔")
        sched = data.get("scheduled_at", "")
        iv_date, iv_time = "", ""
        if "T" in sched:
            parts = sched.split("T")
            iv_date = parts[0]
            iv_time = parts[1][:5] if len(parts) > 1 else ""
        elif sched:
            iv_date = sched
        row_data = {
            "interview_id":   data.get("id", ""),
            "candidate_id":   data.get("candidate_id", ""),
            "application_id": data.get("application_id", ""),
            "job_id":         data.get("job_id", data.get("job_opening_id", "")),
            "姓名":           data.get("name", ""),
            "面試日期":       iv_date,
            "面試時間":       iv_time,
            "面試官":         data.get("interviewer", ""),
            "面試類型":       data.get("interview_type", ""),
            "面試結果":       {"pass": "通過", "fail": "未通過"}.get(data.get("result", ""), "待定"),
            "面試官備註":     data.get("notes", ""),
            "下一步行動":     data.get("next_action", ""),
            "記錄時間":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        if not row_data["interview_id"]:
            import time as _time
            row_data["interview_id"] = f"IV-{row_data['candidate_id']}-{int(_time.time())}"
        _upsert_row(ws, "interview_id", row_data)
        _invalidate()
        return True
    except Exception as e:
        st.error(f"面試記錄儲存失敗：{e}")
        return False

def save_hire(data: dict) -> bool:
    sh = _get_sheet()
    if not sh:
        return False
    try:
        ws = sh.worksheet("06_員工主檔")
        def _b(v):
            if isinstance(v, bool):
                return "是" if v else ""
            return str(v) if v else ""
        cid = data.get("candidate_id", data.get("id", ""))
        row_data = {
            "employee_id":    data.get("id", cid),
            "candidate_id":   cid,
            "job_id":         data.get("job_id", data.get("job_opening_id", "")),
            "預計報到日":     str(data.get("start_date", "")),
            "錄取通知寄出":   _b(data.get("錄取通知寄出", "")),
            "銀行帳號已收":   _b(data.get("銀行帳號已收", "")),
            "報到前Form已填": _b(data.get("報到前Form已填", "")),
            "MIS聯絡單已送":  _b(data.get("MIS聯絡單已送", "")),
            "Workspace帳號":  _b(data.get("Workspace帳號", "")),
            "POS帳號":        _b(data.get("POS帳號", "")),
            "華苓帳號":       _b(data.get("華苓帳號", "")),
            "飛騰帳號":       _b(data.get("飛騰帳號", "")),
            "門禁卡":         _b(data.get("門禁卡", "")),
            "雲端學院帳號":   _b(data.get("雲端學院帳號", "")),
        }
        _upsert_row(ws, "candidate_id", row_data)
        _invalidate()
        return True
    except Exception as e:
        st.error(f"任用記錄儲存失敗：{e}")
        return False

def save_job(data: dict) -> bool:
    sh = _get_sheet()
    if not sh:
        return False
    try:
        import re as _re, time as _time
        ws = sh.worksheet("01_職缺主檔")
        status_zh = {"open": "招募中", "paused": "暫停中", "closed": "已結束"}.get(
            data.get("status", "open"), "招募中")
        jid = data.get("id", "")
        if not jid:
            title = data.get("title", "")
            jid = _re.sub(r"[^\w\-]", "_", title)[:20] + "_" + _time.strftime("%m%d%H%M")
        row_data = {
            "job_id":   jid,
            "職缺名稱": data.get("title", ""),
            "工作地點": data.get("department", ""),
            "狀態":     status_zh,
            "建立日期": _time.strftime("%Y-%m-%d"),
        }
        _upsert_row(ws, "job_id", row_data)
        _invalidate()
        return True
    except Exception as e:
        st.error(f"職缺儲存失敗：{e}")
        return False

# ── Helpers ───────────────────────────────────────────────────
def parse_dt(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

def grade_badge(grade: str) -> str:
    gm = GRADE_META.get(grade, ("#f8fafc", "#475569", "#94a3b8", "📋"))
    g = _html.escape(str(grade))
    return (f'<span style="background:{gm[0]};color:{gm[1]};border:2px solid {gm[2]};'
            f'border-radius:5px;font-weight:800;font-size:0.85rem;padding:2px 8px;'
            f'font-family:var(--font-mono);">{gm[3]} {g}</span>')

def stage_badge(stage: str) -> str:
    bg = STAGE_BG.get(stage, "#f1f5f9")
    fg = STAGE_FG.get(stage, "#475569")
    return (f'<span style="background:{bg};color:{fg};border:1px solid {fg}44;'
            f'border-radius:5px;font-weight:700;font-size:0.78rem;padding:3px 9px;">'
            f'{STAGE_ICON.get(stage,"")} {STAGE_LABEL.get(stage,stage)}</span>')

def gcal_link(title: str, start_dt: datetime, duration_min=60, desc="", location="公司") -> str:
    fmt = "%Y%m%dT%H%M%S"
    end_dt = start_dt + timedelta(minutes=duration_min)
    p = {"action": "TEMPLATE", "text": title,
         "dates": f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}",
         "details": desc, "location": location}
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(p)

def import_from_screening(results: list, job_id: str) -> int:
    sh = _get_sheet()
    if not sh:
        return 0
    import re as _re, time as _time
    existing_codes = {str(c.get("code_104", "")) for c in fetch_all_candidates() if c.get("code_104")}
    today = _time.strftime("%Y-%m-%d")
    try:
        ws02 = sh.worksheet("02_候選人主檔")
        ws03 = sh.worksheet("03_應徵主檔")
        h02 = ws02.row_values(1)
        h03 = ws03.row_values(1)
    except Exception as e:
        st.error(f"匯入失敗：{e}")
        return 0

    imported = 0
    job_safe = _re.sub(r"[^\w\-]", "_", job_id)[:20]
    for r in results:
        if r.get("初篩判定") != "合格":
            continue
        grade = str(r.get("綜合推薦度", "")).strip().upper()
        if not grade or grade[0] not in ("A", "B"):
            continue
        code = str(r.get("104代碼", "")).strip()
        if code and code not in ("未知代碼", "") and code in existing_codes:
            continue
        name = r.get("真實姓名", "未知")
        cand_id = f"CAND-{code}" if code and code != "未知代碼" else f"CAND-{_re.sub(r'[^\\w]','_',name)[:6]}"
        app_id  = f"APP-{code or name[:4]}-{job_safe}"
        try:
            c02 = {h: "" for h in h02}
            c02.update({"candidate_id": cand_id, "真實姓名": name,
                         "104代碼": code, "Email": r.get("Email", ""),
                         "來源": "104投遞", "建立日期": today})
            ws02.append_row([c02.get(h, "") for h in h02],
                             value_input_option="RAW", insert_data_option="INSERT_ROWS")
            a03 = {h: "" for h in h03}
            a03.update({"application_id": app_id, "job_id": job_id,
                         "candidate_id": cand_id, "姓名": name, "104代碼": code,
                         "應徵日期": today, "應徵來源": "104投遞",
                         "初篩判定": r.get("初篩判定", ""),
                         "綜合推薦度": grade[0],
                         "加權總分": str(r.get("加權總分", "")),
                         "人才狀態": "待定", "流程狀態": "初篩完成",
                         "建立時間": today})
            ws03.append_row([a03.get(h, "") for h in h03],
                             value_input_option="RAW", insert_data_option="INSERT_ROWS")
            imported += 1
        except Exception as e:
            st.warning(f"匯入失敗（{name}）：{e}")
            continue
    if imported:
        _invalidate()
    return imported

# ══════════════════════════════════════════════════════════════
# PAGE 1 — 本週 + 下週總覽
# ══════════════════════════════════════════════════════════════
def page_overview():
    today = date.today()
    # 本週 Mon–Sun
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)
    # 下週
    next_start = week_start + timedelta(days=7)
    next_end   = next_start + timedelta(days=6)

    all_cands = fetch_all_candidates()
    all_ivs   = fetch_all_interviews()
    all_jobs  = fetch_all_jobs()
    all_hires = fetch_all_hires()

    ivs_joined = _interviews_with_join(all_ivs, all_cands, all_jobs)
    cand_map   = {c["id"]: c for c in all_cands}

    # ── 指標列 ────────────────────────────────────────────────
    active = sum(1 for c in all_cands if c.get("stage") not in ("hired", "rejected"))
    this_week_ivs = [iv for iv in ivs_joined
                     if parse_dt(iv.get("scheduled_at")) and
                     week_start <= parse_dt(iv["scheduled_at"]).date() <= week_end]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("在途候選人", active)
    m2.metric("待面試",     sum(1 for c in all_cands if c.get("stage") == "interview_scheduled"))
    m3.metric("本週面試",   len(this_week_ivs))
    m4.metric("已錄取",     sum(1 for c in all_cands if c.get("stage") == "hired"))
    m5.metric("開缺數",     sum(1 for j in all_jobs  if j.get("status") == "open"))

    st.markdown("---")

    # ── 雙週排程（左：本週｜右：下週）────────────────────────
    def render_week(col, label: str, start: date, end: date):
        col.markdown(
            f'<div style="font-weight:700;font-size:0.82rem;color:var(--c-primary);'
            f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
            f'📅 {label}（{start.strftime("%m/%d")}–{end.strftime("%m/%d")}）</div>',
            unsafe_allow_html=True,
        )
        # 收集該週所有事件 (面試 + 報到)
        day_events: dict[date, list] = {start + timedelta(i): [] for i in range(7)}

        for iv in ivs_joined:
            dt = parse_dt(iv.get("scheduled_at"))
            if not dt:
                continue
            d = dt.date()
            if start <= d <= end:
                day_events[d].append({
                    "icon": "🗣️", "color": "#1e40af", "bg": "#dbeafe",
                    "title": iv["_cand_name"],
                    "sub":   f'{dt.strftime("%H:%M")} · {iv["_job_title"]}',
                })

        for h in all_hires:
            sd = h.get("start_date")
            if not sd:
                continue
            try:
                d = date.fromisoformat(str(sd)[:10])
            except Exception:
                continue
            if start <= d <= end:
                c = cand_map.get(str(h.get("candidate_id", "")), {})
                day_events[d].append({
                    "icon": "🎉", "color": "#064e3b", "bg": "#d1fae5",
                    "title": c.get("name", "?"),
                    "sub":   "報到日",
                })

        has_any = False
        for d in sorted(day_events.keys()):
            evs = day_events[d]
            is_today  = (d == today)
            is_past   = (d < today)
            hdr_bg    = "#0f766e" if is_today else ("#94a3b8" if is_past else "#1e40af")
            wd        = WD_ZH[d.weekday()]
            tag       = " 今天" if is_today else ""
            col.markdown(
                f'<div style="background:{hdr_bg};color:#fff;border-radius:5px;'
                f'padding:3px 10px;margin:8px 0 3px;font-weight:700;font-size:0.78rem;">'
                f'{d.strftime("%m/%d")} 週{wd}{tag}</div>',
                unsafe_allow_html=True,
            )
            if evs:
                has_any = True
                for ev in evs:
                    col.markdown(
                        f'<div style="display:flex;align-items:center;gap:7px;'
                        f'background:{ev["bg"]};border-left:3px solid {ev["color"]};'
                        f'border-radius:0 5px 5px 0;padding:4px 9px;margin-bottom:3px;">'
                        f'<span>{ev["icon"]}</span>'
                        f'<div><div style="font-weight:600;font-size:0.82rem;color:{ev["color"]};">'
                        f'{_html.escape(ev["title"])}</div>'
                        f'<div style="font-size:0.71rem;color:#64748b;">{_html.escape(ev["sub"])}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                col.markdown(
                    '<div style="font-size:0.75rem;color:#94a3b8;padding:2px 8px;">—</div>',
                    unsafe_allow_html=True,
                )
        if not has_any:
            col.info("本週無面試或報到安排。")

    col_left, col_right = st.columns(2)
    render_week(col_left,  "本週", week_start, week_end)
    render_week(col_right, "下週", next_start, next_end)

    # ── 待處理 Action Items ────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:0.82rem;color:var(--c-primary);'
        'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        '⚡ 待處理事項</div>',
        unsafe_allow_html=True,
    )

    actions = []

    # 在「已面試」超過 3 天仍未決定
    for c in all_cands:
        if c.get("stage") == "interviewed":
            dt = parse_dt(c.get("created_at"))
            if dt and (datetime.now() - dt).days >= 3:
                actions.append(f'⏳ **{c.get("name","?")}** — 已面試 {(datetime.now()-dt).days} 天，尚未進入錄取審核')

    # offer_pending 等待審核
    for c in all_cands:
        if c.get("stage") == "offer_pending":
            actions.append(f'📋 **{c.get("name","?")}** — 錄取審核中，待確認')

    # onboarding 未完成項目（已錄取的人）
    hires_map = {h["candidate_id"]: h for h in all_hires}
    OB_CHECKLIST = [
        ("錄取通知寄出",   "錄取通知"),
        ("銀行帳號已收",   "銀行帳號"),
        ("報到前Form已填", "報到Form"),
        ("MIS聯絡單已送",  "MIS單"),
        ("Workspace帳號",  "Workspace"),
        ("POS帳號",        "POS"),
        ("飛騰帳號",       "飛騰"),
        ("門禁卡",         "門禁卡"),
        ("雲端學院帳號",   "雲端學院"),
    ]
    for c in all_cands:
        if c.get("stage") == "hired":
            h = hires_map.get(str(c.get("id", "")), {})
            missing = [lbl for k, lbl in OB_CHECKLIST if not h.get(k)]
            if missing:
                actions.append(f'✅ **{c.get("name","?")}** — 到職流程待完成：{" / ".join(missing)}')

    if actions:
        for a in actions:
            st.markdown(
                f'<div style="background:#fffbeb;border-left:3px solid #f59e0b;'
                f'border-radius:0 6px 6px 0;padding:6px 12px;margin-bottom:4px;font-size:0.85rem;">'
                f'{a}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ 目前無待處理事項！")

# ══════════════════════════════════════════════════════════════
# PAGE 2 — 招募看板（Kanban）
# ══════════════════════════════════════════════════════════════
def page_kanban():
    all_cands = fetch_all_candidates()
    all_jobs  = fetch_all_jobs()
    job_map   = {j["id"]: j["title"] for j in all_jobs}

    # Filter
    f1, f2 = st.columns([3, 1])
    with f1:
        job_opts = ["全部職缺"] + [j["title"] for j in all_jobs if j.get("status") == "open"]
        sel_job = f1.selectbox("職缺篩選", job_opts, key="kb_job", label_visibility="collapsed")
    with f2:
        show_rejected = f2.checkbox("顯示已結案", value=False, key="kb_rejected")

    if sel_job != "全部職缺":
        jid = next((j["id"] for j in all_jobs if j["title"] == sel_job), None)
        all_cands = [c for c in all_cands if str(c.get("job_opening_id", "")) == str(jid)]

    visible_stages = STAGES if show_rejected else [s for s in STAGES if s[0] != "rejected"]

    # Kanban 欄位
    cols = st.columns(len(visible_stages))
    for col, (sk, label, icon, bg, fg) in zip(cols, visible_stages):
        stage_cands = [c for c in all_cands if c.get("stage") == sk]
        col.markdown(
            f'<div style="background:{bg};border:1px solid {fg}33;border-radius:7px;'
            f'padding:6px 10px;text-align:center;margin-bottom:8px;">'
            f'<div style="font-weight:800;color:{fg};font-size:0.8rem;">{icon} {label}</div>'
            f'<div style="font-family:var(--font-mono);font-size:1.3rem;font-weight:700;color:{fg};">'
            f'{len(stage_cands)}</div></div>',
            unsafe_allow_html=True,
        )
        for c in stage_cands:
            cid   = c["id"]
            name  = c.get("name", "?")
            grade = c.get("grade", "?")
            jtitle = job_map.get(str(c.get("job_opening_id", "")), "")
            gm    = GRADE_META.get(grade, ("#f8fafc", "#475569", "#94a3b8", "📋"))
            dt    = parse_dt(c.get("created_at"))
            days  = (datetime.now() - dt).days if dt else 0

            with col.container(border=True):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:700;font-size:0.88rem;">{_html.escape(name)}</span>'
                    f'<span style="background:{gm[0]};color:{gm[1]};border:1.5px solid {gm[2]};'
                    f'border-radius:4px;font-size:0.72rem;font-weight:800;padding:1px 5px;">'
                    f'{gm[3]}{grade}</span></div>'
                    f'<div style="font-size:0.72rem;color:#64748b;margin-top:2px;">'
                    f'{_html.escape(jtitle[:18])} · {days}天</div>',
                    unsafe_allow_html=True,
                )
                # 前進按鈕
                cur_idx = STAGE_KEYS.index(sk) if sk in STAGE_KEYS else 0
                next_stages = STAGE_KEYS[cur_idx + 1: cur_idx + 2]  # 只顯示下一個
                for ns in next_stages:
                    if ns == "rejected":
                        continue
                    if st.button(f"→ {STAGE_LABEL[ns]}", key=f"kb_adv_{cid}",
                                 use_container_width=True):
                        if update_stage(cid, ns):
                            st.toast(f"✅ {name} → {STAGE_LABEL[ns]}")
                            st.rerun()
                if sk not in ("hired", "rejected"):
                    if st.button("❌ 結案", key=f"kb_rej_{cid}",
                                 use_container_width=True):
                        if update_stage(cid, "rejected"):
                            st.toast(f"{name} 已結案")
                            st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE 3 — 候選人
# ══════════════════════════════════════════════════════════════
def page_candidates():
    all_jobs  = fetch_all_jobs()
    all_cands = _candidates_with_join(fetch_all_candidates(), all_jobs)
    job_map   = {j["id"]: j["title"] for j in all_jobs}

    # Filters
    f1, f2, f3, f4 = st.columns([2.5, 2, 1.2, 2])
    with f1:
        job_opts = ["全部職缺"] + [j["title"] for j in all_jobs]
        sel_job = st.selectbox("職缺", job_opts, key="c_job", label_visibility="collapsed")
        sel_jid = next((j["id"] for j in all_jobs if j["title"] == sel_job), None)
    with f2:
        stage_opts = ["全部階段"] + [STAGE_LABEL[s] for s in STAGE_KEYS]
        sel_stage_lbl = st.selectbox("階段", stage_opts, key="c_stage", label_visibility="collapsed")
        sel_stage = next((k for k, v in STAGE_LABEL.items() if v == sel_stage_lbl), None)
    with f3:
        sel_grade = st.selectbox("等級", ["全部", "A", "B", "C"], key="c_grade", label_visibility="collapsed")
    with f4:
        search = st.text_input("🔍 搜尋姓名 / 104代碼", key="c_search", label_visibility="collapsed",
                               placeholder="搜尋姓名 / 104代碼")

    # Apply filters
    rows = all_cands
    if sel_jid:
        rows = [c for c in rows if str(c.get("job_opening_id", "")) == str(sel_jid)]
    if sel_stage:
        rows = [c for c in rows if c.get("stage") == sel_stage]
    if sel_grade != "全部":
        rows = [c for c in rows if c.get("grade") == sel_grade]
    if search.strip():
        kw = search.strip()
        rows = [c for c in rows if kw in c.get("name", "") or kw in str(c.get("code_104", ""))]

    # Export button
    col_count, col_export = st.columns([4, 1])
    col_count.caption(f"共 {len(rows)} 位候選人")
    if rows:
        df_export = pd.DataFrame([{
            "姓名": c.get("name"), "等級": c.get("grade"), "階段": STAGE_LABEL.get(c.get("stage",""), c.get("stage","")),
            "職缺": c.get("_job_title"), "來源": c.get("source"), "穩定度": c.get("stability"),
            "通勤": c.get("commute"), "亮點": c.get("highlights"), "缺口": c.get("gaps"),
            "104代碼": c.get("code_104"), "建立時間": c.get("created_at"),
        } for c in rows])
        buf = io.BytesIO()
        df_export.to_excel(buf, index=False)
        col_export.download_button("⬇ 匯出 Excel", buf.getvalue(),
                                   file_name="candidates.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)

    if not rows:
        st.info("無符合條件的候選人。")
    else:
        for c in rows:
            _render_candidate_card(c, job_map, all_jobs)

    st.divider()
    _render_import_section(all_jobs)

def _render_candidate_card(c: dict, job_map: dict, all_jobs: list):
    cid    = c["id"]
    grade  = c.get("grade", "?")
    stage  = c.get("stage", "screening")
    name   = c.get("name", "?")
    code   = str(c.get("code_104") or "—")
    stab   = c.get("stability", "")
    jtitle = c.get("_job_title") or job_map.get(str(c.get("job_opening_id", "")), "")
    stab_color = {"高": "#15803d", "中": "#92400e", "低": "#b91c1c"}.get(stab, "#64748b")
    cur_idx = STAGE_KEYS.index(stage) if stage in STAGE_KEYS else 0

    with st.container(border=True):
        cg, ci, cs, ca = st.columns([0.6, 3.5, 1.5, 2])
        cg.markdown(grade_badge(grade), unsafe_allow_html=True)
        ci.markdown(
            f'<div style="font-weight:700;font-size:1rem;">{_html.escape(name)}'
            f'<span style="font-weight:400;color:#64748b;font-size:0.77rem;margin-left:8px;">'
            f'#{_html.escape(code)} · {_html.escape(jtitle)}</span></div>'
            f'<div style="font-size:0.78rem;color:#64748b;margin-top:2px;">'
            f'穩定度：<span style="color:{stab_color};font-weight:600;">{_html.escape(stab)}</span>'
            f' · {_html.escape((c.get("commute") or "")[:40])}</div>',
            unsafe_allow_html=True,
        )
        cs.markdown(stage_badge(stage), unsafe_allow_html=True)
        with ca:
            next_s = STAGE_KEYS[cur_idx + 1: cur_idx + 3]
            for ns in next_s:
                if st.button(f"→ {STAGE_LABEL[ns]}", key=f"fwd_{cid}_{ns}", use_container_width=True):
                    if update_stage(cid, ns):
                        st.toast(f"✅ {name} → {STAGE_LABEL[ns]}")
                        st.rerun()
            if stage not in ("rejected", "hired"):
                if st.button("❌ 結案", key=f"rej_{cid}", use_container_width=True):
                    if update_stage(cid, "rejected"):
                        st.toast(f"{name} 已結案")
                        st.rerun()

        with st.expander("詳細 / 快速安排面試", expanded=False):
            dc1, dc2 = st.columns(2)
            dc1.markdown(
                f'<div style="background:var(--c-ok-bg);border:1px solid var(--c-ok-border);'
                f'border-radius:6px;padding:8px 10px;font-size:0.82rem;">'
                f'<b style="color:var(--c-ok);">✨ 戰功亮點</b><br>'
                f'{_html.escape(c.get("highlights") or "—")}</div>',
                unsafe_allow_html=True,
            )
            dc2.markdown(
                f'<div style="background:var(--c-err-bg);border:1px solid var(--c-err-border);'
                f'border-radius:6px;padding:8px 10px;font-size:0.82rem;">'
                f'<b style="color:var(--c-err);">⚠️ 缺口地雷</b><br>'
                f'{_html.escape(c.get("gaps") or "—")}</div>',
                unsafe_allow_html=True,
            )
            if c.get("screening_notes"):
                st.caption(f"初篩備注：{c['screening_notes']}")

            if stage in ("screening", "interview_scheduled"):
                st.markdown("**快速安排面試**")
                qs1, qs2, qs3 = st.columns(3)
                iv_date = qs1.date_input("日期", value=date.today() + timedelta(days=3), key=f"qd_{cid}")
                iv_time = qs2.time_input("時間", value=datetime(2024,1,1,10,0).time(), key=f"qt_{cid}")
                iv_itvr = qs3.text_input("面試官", key=f"qi_{cid}")
                iv_loc  = st.text_input("地點", value="公司", key=f"ql_{cid}")
                if st.button("確認安排", key=f"qsched_{cid}", type="primary"):
                    sdt = datetime.combine(iv_date, iv_time)
                    if save_interview({"candidate_id": cid, "scheduled_at": sdt.isoformat(),
                                       "duration_minutes": 60, "interviewer": iv_itvr,
                                       "location": iv_loc, "result": "pending"}):
                        update_stage(cid, "interview_scheduled")
                        link = gcal_link(f"面試：{name}（{jtitle}）", sdt, location=iv_loc)
                        st.success("✅ 面試已安排！")
                        st.link_button("📅 加入 Google 行事曆", link)
                        st.rerun()

def _render_import_section(all_jobs: list):
    with st.expander("📥 從 AI 初篩匯入候選人", expanded=False):
        if not os.path.exists(LAST_RESULTS_FILE):
            st.info("找不到 last_session_results.json，請先在初篩引擎完成篩選。")
            return
        if not all_jobs:
            st.warning("請先建立職缺後再匯入。")
            return
        try:
            with open(LAST_RESULTS_FILE, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            st.error("last_session_results.json 格式錯誤。")
            return
        a_n = sum(1 for r in results if r.get("初篩判定") == "合格"
                  and str(r.get("綜合推薦度", "")).upper().startswith("A"))
        b_n = sum(1 for r in results if r.get("初篩判定") == "合格"
                  and str(r.get("綜合推薦度", "")).upper().startswith("B"))
        st.info(f"上次初篩：🏆 A 級 {a_n} 人 · ✅ B 級 {b_n} 人（共可匯入 {a_n+b_n} 人）")
        import_job = st.selectbox("匯入至職缺", [j["title"] for j in all_jobs], key="imp_job")
        import_jid = next((j["id"] for j in all_jobs if j["title"] == import_job), None)
        if st.button("🔄 執行匯入", type="primary", key="do_import"):
            if import_jid:
                with st.spinner("匯入中…"):
                    n = import_from_screening(results, import_jid)
                if n > 0:
                    st.success(f"✅ 成功匯入 {n} 位候選人！")
                    st.rerun()
                else:
                    st.info("無新候選人（已全部存在或無 A/B 級）。")

# ── Calendar render helpers ───────────────────────────────────

def _build_cal_events(ivs_joined: list, all_hires: list, cand_map: dict) -> list:
    """把面試和報到日統一轉成 calendar event dict。"""
    events = []
    for iv in ivs_joined:
        dt = parse_dt(iv.get("scheduled_at"))
        if not dt:
            continue
        events.append({
            "date":    dt.date(),
            "dt":      dt,
            "title":   iv.get("_cand_name", "?"),
            "sub":     iv.get("_job_title", ""),
            "time":    dt.strftime("%H:%M"),
            "dur_min": int(iv.get("duration_minutes") or 60),
            "color":   "#1e40af", "bg": "#dbeafe", "border": "#3b82f6",
        })
    for h in all_hires:
        sd = h.get("start_date")
        if not sd:
            continue
        try:
            d = date.fromisoformat(str(sd)[:10])
        except Exception:
            continue
        c = cand_map.get(str(h.get("candidate_id", "")), {})
        events.append({
            "date":    d,
            "dt":      datetime.combine(d, datetime.min.time().replace(hour=9)),
            "title":   c.get("name", "?"),
            "sub":     "報到日",
            "time":    "全天",
            "dur_min": 60,
            "color":   "#064e3b", "bg": "#d1fae5", "border": "#10b981",
        })
    return events


def _render_week_cal(week_start: date, events: list) -> str:
    """Google Calendar 風格週視圖 HTML。"""
    WD_HDR  = ["一", "二", "三", "四", "五", "六", "日"]
    today_d = date.today()
    days    = [week_start + timedelta(days=i) for i in range(7)]

    H_START, H_END, PX_HR = 8, 20, 64
    total_h = (H_END - H_START) * PX_HR

    # 把事件按日期分組並計算像素位置
    day_evs: dict[date, list] = {d: [] for d in days}
    for ev in events:
        if ev["date"] in day_evs:
            off = ev["dt"].hour + ev["dt"].minute / 60 - H_START
            top = max(0, min(off * PX_HR, total_h - 20))
            h   = max(22, min(ev["dur_min"] / 60 * PX_HR - 2, total_h - top))
            day_evs[ev["date"]].append({**ev, "top": top, "h": h})

    # ── Header ────────────────────────────────────────────────
    hdr = ('<div style="display:flex;border-bottom:2px solid #cbd5e1;'
           'background:#f8fafc;position:sticky;top:0;z-index:10;">'
           '<div style="width:52px;min-width:52px;"></div>')
    for d in days:
        is_today = (d == today_d)
        is_wkend = d.weekday() >= 5
        num_bg  = "#1e40af" if is_today else "transparent"
        num_fg  = "#fff"    if is_today else ("#94a3b8" if is_wkend else "#0f172a")
        lbl_fg  = "#94a3b8" if is_wkend else "#6b7280"
        hdr += (
            f'<div style="flex:1;text-align:center;padding:6px 2px;'
            f'border-left:1px solid #e2e8f0;">'
            f'<div style="font-size:0.68rem;font-weight:600;color:{lbl_fg};'
            f'text-transform:uppercase;letter-spacing:.04em;">週{WD_HDR[d.weekday()]}</div>'
            f'<div style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:30px;height:30px;border-radius:50%;background:{num_bg};'
            f'font-size:0.95rem;font-weight:800;color:{num_fg};margin-top:1px;">'
            f'{d.day}</div></div>'
        )
    hdr += '</div>'

    # ── Body ──────────────────────────────────────────────────
    body = ('<div style="display:flex;overflow-y:auto;max-height:528px;">'
            f'<div style="width:52px;min-width:52px;position:relative;'
            f'height:{total_h}px;border-right:1px solid #e2e8f0;background:#f8fafc;">')
    for i in range(H_END - H_START):
        body += (
            f'<div style="position:absolute;top:{i * PX_HR - 8}px;right:6px;'
            f'font-size:0.6rem;color:#9ca3af;font-family:monospace;">'
            f'{H_START + i:02d}:00</div>'
        )
    body += '</div>'

    for d in days:
        is_today = (d == today_d)
        is_wkend = d.weekday() >= 5
        col_bg   = "#fafafa" if is_wkend else ("#f0f9ff" if is_today else "#fff")
        body += (
            f'<div style="flex:1;position:relative;height:{total_h}px;'
            f'background:{col_bg};border-left:1px solid #e2e8f0;overflow:hidden;">'
        )
        # hour gridlines
        for i in range(H_END - H_START):
            lc = "#e0f2fe" if is_today else ("#f4f4f5" if is_wkend else "#f1f5f9")
            body += f'<div style="position:absolute;top:{i*PX_HR}px;left:0;right:0;border-top:1px solid {lc};"></div>'
            body += f'<div style="position:absolute;top:{i*PX_HR+PX_HR//2}px;left:0;right:0;border-top:1px dashed {lc};"></div>'

        # current-time indicator
        if is_today:
            now = datetime.now()
            now_top = (now.hour + now.minute / 60 - H_START) * PX_HR
            if 0 <= now_top <= total_h:
                body += (
                    f'<div style="position:absolute;top:{now_top:.1f}px;left:0;right:0;'
                    f'border-top:2px solid #ef4444;z-index:5;">'
                    f'<div style="position:absolute;left:-4px;top:-4px;width:8px;height:8px;'
                    f'background:#ef4444;border-radius:50%;"></div></div>'
                )

        # events
        for ev in day_evs.get(d, []):
            show_sub = ev["h"] > 30
            body += (
                f'<div title="{_html.escape(ev["title"])} {ev["time"]}" '
                f'style="position:absolute;top:{ev["top"]:.1f}px;height:{ev["h"]:.1f}px;'
                f'left:3px;right:3px;background:{ev["bg"]};border-left:3px solid {ev["border"]};'
                f'border-radius:0 4px 4px 0;padding:2px 5px;overflow:hidden;z-index:2;'
                f'box-shadow:0 1px 3px rgba(0,0,0,.1);">'
                f'<div style="font-weight:700;font-size:0.72rem;color:{ev["color"]};'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'{_html.escape(ev["title"])}</div>'
                + (f'<div style="font-size:0.62rem;color:#475569;white-space:nowrap;'
                   f'overflow:hidden;text-overflow:ellipsis;">'
                   f'{ev["time"]} · {_html.escape(ev["sub"])}</div>' if show_sub else "")
                + '</div>'
            )
        body += '</div>'
    body += '</div>'

    return (
        '<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;'
        'font-family:sans-serif;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.06);">'
        + hdr + body + '</div>'
    )


def _render_month_cal(year: int, month: int, events: list) -> str:
    """Google Calendar 風格月視圖 HTML。"""
    WD_HDR  = ["一", "二", "三", "四", "五", "六", "日"]
    today_d = date.today()

    ev_by_day: dict[date, list] = {}
    for ev in events:
        ev_by_day.setdefault(ev["date"], []).append(ev)

    weeks = _cal.Calendar(firstweekday=0).monthdatescalendar(year, month)

    html = ('<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;'
            'font-family:sans-serif;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.06);">')

    # Day-of-week header
    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);background:#f8fafc;border-bottom:2px solid #e2e8f0;">'
    for i, wd in enumerate(WD_HDR):
        c = "#94a3b8" if i >= 5 else "#6b7280"
        html += (f'<div style="text-align:center;padding:8px 4px;font-size:0.72rem;'
                 f'font-weight:700;color:{c};">週{wd}</div>')
    html += '</div>'

    for week in weeks:
        html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);border-bottom:1px solid #f1f5f9;">'
        for d in week:
            in_month = (d.month == month)
            is_today = (d == today_d)
            is_wkend = d.weekday() >= 5
            num_bg   = "#1e40af" if is_today else "transparent"
            num_fg   = "#fff" if is_today else ("#0f172a" if in_month else "#cbd5e1")
            cell_bg  = "#f0f9ff" if is_today else ("#fafafa" if is_wkend else "#fff")
            if not in_month:
                cell_bg = "#f9fafb"
            evs = ev_by_day.get(d, [])
            html += (
                f'<div style="min-height:88px;padding:4px;border-right:1px solid #f1f5f9;background:{cell_bg};">'
                f'<div style="display:flex;justify-content:flex-end;margin-bottom:3px;">'
                f'<div style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:26px;height:26px;border-radius:50%;background:{num_bg};'
                f'font-size:0.8rem;font-weight:{"800" if is_today else "600"};color:{num_fg};">'
                f'{d.day}</div></div>'
            )
            for ev in evs[:3]:
                t_lbl = "🎉" if ev["time"] == "全天" else ev["time"]
                html += (
                    f'<div title="{_html.escape(ev["title"])}" '
                    f'style="background:{ev["bg"]};border-left:3px solid {ev["border"]};'
                    f'border-radius:0 3px 3px 0;padding:1px 4px;margin-bottom:2px;'
                    f'font-size:0.67rem;font-weight:600;color:{ev["color"]};'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{t_lbl} {_html.escape(ev["title"])}</div>'
                )
            if len(evs) > 3:
                html += f'<div style="font-size:0.65rem;color:#64748b;padding:0 4px;">+{len(evs)-3} 筆</div>'
            html += '</div>'
        html += '</div>'

    html += '</div>'
    return html


# ══════════════════════════════════════════════════════════════
# PAGE 4 — 面試管理（行事曆 + 記分卡）
# ══════════════════════════════════════════════════════════════
def page_interviews():
    all_cands = fetch_all_candidates()
    all_ivs   = fetch_all_interviews()
    all_jobs  = fetch_all_jobs()
    all_hires = fetch_all_hires()
    ivs       = _interviews_with_join(all_ivs, all_cands, all_jobs)
    cand_map  = {c["id"]: c for c in all_cands}
    cal_evs   = _build_cal_events(ivs, all_hires, cand_map)

    itab1, itab2 = st.tabs(["📅 行事曆", "📝 記分卡"])

    # ── 行事曆 ────────────────────────────────────────────────
    with itab1:
        today = date.today()

        # Session state for navigation
        if "cal_view"     not in st.session_state: st.session_state.cal_view     = "週"
        if "cal_week_off" not in st.session_state: st.session_state.cal_week_off = 0
        if "cal_mo_off"   not in st.session_state: st.session_state.cal_mo_off   = 0

        # ── Navigation bar ────────────────────────────────────
        nav1, nav2, nav3, nav_sp, nav4 = st.columns([0.7, 0.7, 2.5, 1.5, 2])

        if nav1.button("◀", key="cal_prev", use_container_width=True):
            if st.session_state.cal_view == "週":
                st.session_state.cal_week_off -= 1
            else:
                st.session_state.cal_mo_off -= 1
            st.rerun()

        if nav2.button("▶", key="cal_next", use_container_width=True):
            if st.session_state.cal_view == "週":
                st.session_state.cal_week_off += 1
            else:
                st.session_state.cal_mo_off += 1
            st.rerun()

        view_mode = nav4.radio(
            "view", ["週視圖", "月視圖"], horizontal=True,
            key="cal_view", label_visibility="collapsed",
        )

        # Compute current range label + reset button
        if view_mode == "週視圖":
            week_start = (today - timedelta(days=today.weekday())
                          + timedelta(weeks=st.session_state.cal_week_off))
            week_end   = week_start + timedelta(days=6)
            range_lbl  = f"**{week_start.strftime('%Y 年 %m/%d')} – {week_end.strftime('%m/%d')}**"
            is_current = (st.session_state.cal_week_off == 0)
        else:
            base_year, base_month = today.year, today.month
            mo_off = st.session_state.cal_mo_off
            target_month = base_month + mo_off
            target_year  = base_year + (target_month - 1) // 12
            target_month = ((target_month - 1) % 12) + 1
            range_lbl    = f"**{target_year} 年 {target_month} 月**"
            is_current   = (mo_off == 0)

        nav3.markdown(range_lbl)
        if not is_current:
            if nav_sp.button("↩ 回今天", key="cal_reset", use_container_width=True):
                st.session_state.cal_week_off = 0
                st.session_state.cal_mo_off   = 0
                st.rerun()

        # ── Render calendar ───────────────────────────────────
        if view_mode == "週視圖":
            st.markdown(
                _render_week_cal(week_start, cal_evs),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                _render_month_cal(target_year, target_month, cal_evs),
                unsafe_allow_html=True,
            )

        st.divider()
        with st.expander("➕ 安排新面試", expanded=False):
            eligible = [c for c in all_cands
                        if c.get("stage") in ("screening", "interview_scheduled")]
            if not eligible:
                st.info("目前無可安排面試的候選人。")
            else:
                job_map = {j["id"]: j["title"] for j in all_jobs}
                opts = {f"{c['name']} — {job_map.get(str(c.get('job_opening_id','')),'')}": c
                        for c in eligible}
                sel_c = opts[st.selectbox("候選人", list(opts.keys()), key="cal_cand")]
                sc1, sc2, sc3 = st.columns(3)
                iv_date = sc1.date_input("日期", value=today + timedelta(days=3), key="cal_d")
                iv_time = sc2.time_input("時間", value=datetime(2024,1,1,10,0).time(), key="cal_t")
                iv_dur  = sc3.number_input("時長(分)", value=60, step=15, key="cal_dur")
                sc4, sc5 = st.columns(2)
                iv_itvr = sc4.text_input("面試官", key="cal_itvr")
                iv_loc  = sc5.text_input("地點", value="公司", key="cal_loc")
                iv_note = st.text_area("備注", key="cal_note")
                if st.button("確認安排", type="primary", key="cal_sched"):
                    sdt = datetime.combine(iv_date, iv_time)
                    if save_interview({
                        "candidate_id": sel_c["id"], "scheduled_at": sdt.isoformat(),
                        "duration_minutes": int(iv_dur), "interviewer": iv_itvr,
                        "location": iv_loc, "notes": iv_note, "result": "pending",
                    }):
                        update_stage(sel_c["id"], "interview_scheduled")
                        link = gcal_link(f"面試：{sel_c['name']}", sdt, int(iv_dur), iv_note, iv_loc)
                        st.success(f"✅ 面試安排完成！")
                        st.link_button("📅 加入 Google 行事曆", link)
                        st.rerun()

    # ── 記分卡 ────────────────────────────────────────────────
    with itab2:
        eligible2 = [c for c in all_cands
                     if c.get("stage") in ("interview_scheduled", "interviewed")]
        if not eligible2:
            st.info("目前無需填寫記分卡的候選人。")
            return

        job_map2 = {j["id"]: j["title"] for j in all_jobs}
        opts2 = {f"{c['name']} — {job_map2.get(str(c.get('job_opening_id','')),'')}": c
                 for c in eligible2}
        sel_c2 = opts2[st.selectbox("選擇候選人", list(opts2.keys()), key="sc_cand")]
        cid2   = sel_c2["id"]

        # 既有記錄
        existing = [iv for iv in all_ivs if str(iv.get("candidate_id","")) == str(cid2)]
        if existing:
            st.markdown("**已有記錄**")
            for iv in sorted(existing, key=lambda x: str(x.get("scheduled_at",""))):
                dt  = parse_dt(iv.get("scheduled_at"))
                dts = dt.strftime("%Y/%m/%d %H:%M") if dt else "—"
                res = iv.get("result", "pending")
                rc  = RESULT_COLOR.get(res, "#64748b")
                rl  = RESULT_LABEL.get(res, res)
                st.markdown(
                    f'<div style="background:var(--c-surface-2);border:1px solid var(--c-border);'
                    f'border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:0.82rem;">'
                    f'<b>{dts}</b>　<span style="color:{rc};font-weight:700;">● {rl}</span>'
                    + (f'<br><span style="color:#64748b;">{_html.escape((iv.get("notes") or "")[:120])}</span>'
                       if iv.get("notes") else "")
                    + '</div>', unsafe_allow_html=True,
                )

        st.divider()
        st.markdown("**填寫 / 更新記分卡**")

        # 評分
        sc_cols = st.columns(4)
        labels = ["溝通能力", "專業能力", "工作態度", "穩定性"]
        keys   = ["comm", "skill", "attitude", "stability"]
        scores = {}
        for col, lbl, key in zip(sc_cols, labels, keys):
            scores[key] = col.slider(lbl, 1, 5, 3, key=f"sc_{key}_{cid2}")

        result_opts = {"pending (待定)": "pending", "pass (通過)": "pass", "fail (未通過)": "fail"}
        sel_res_lbl = st.selectbox("面試結果", list(result_opts.keys()), key=f"sc_res_{cid2}")
        sel_res     = result_opts[sel_res_lbl]
        notes_text  = st.text_area(
            "面試觀察記錄", height=140, key=f"sc_notes_{cid2}",
            placeholder="行為事例、能力評估、非語言觀察…"
        )

        def star(n): return "★" * n + "☆" * (5 - n)
        score_block = "\n".join([
            "=== 評分 ===",
            f"溝通能力: {star(scores['comm'])} ({scores['comm']})",
            f"專業能力: {star(scores['skill'])} ({scores['skill']})",
            f"工作態度: {star(scores['attitude'])} ({scores['attitude']})",
            f"穩定性:   {star(scores['stability'])} ({scores['stability']})",
            "=== 備注 ===",
            notes_text,
        ])

        if st.button("儲存記分卡", type="primary", key=f"sc_save_{cid2}"):
            payload = {"result": sel_res, "notes": score_block}
            if existing:
                payload["id"] = existing[-1]["id"]
            else:
                payload["candidate_id"] = cid2
                payload["scheduled_at"] = datetime.now().isoformat()
            if save_interview(payload):
                if sel_res == "pass":
                    update_stage(cid2, "interviewed")
                    st.success(f"✅ 記分卡已儲存！{sel_c2['name']} → 已面試（通過）")
                elif sel_res == "fail":
                    update_stage(cid2, "rejected")
                    st.success(f"✅ 記分卡已儲存！{sel_c2['name']} → 已結案（未通過）")
                else:
                    st.success("✅ 記分卡已儲存！")
                st.rerun()

        if sel_c2.get("stage") == "interviewed":
            st.divider()
            if st.button("📋 進入錄取審核", key=f"sc_offer_{cid2}", type="primary"):
                if update_stage(cid2, "offer_pending"):
                    st.success(f"✅ {sel_c2['name']} 已進入錄取審核！")
                    st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE 5 — 到職流程（Onboarding Checklist）
# ══════════════════════════════════════════════════════════════
def page_onboarding():
    all_cands = fetch_all_candidates()
    all_hires = fetch_all_hires()
    all_jobs  = fetch_all_jobs()
    job_map   = {j["id"]: j["title"] for j in all_jobs}

    # 找「已錄取」或「offer_pending」的候選人
    target_cands = [c for c in all_cands
                    if c.get("stage") in ("offer_pending", "hired")]
    hires_map = {h.get("candidate_id"): h for h in all_hires}

    CHECKLIST = [
        ("錄取通知寄出",   "📧 錄取通知"),
        ("銀行帳號已收",   "🏦 銀行帳號"),
        ("報到前Form已填", "📋 報到Form"),
        ("MIS聯絡單已送",  "🖥️ MIS單"),
        ("Workspace帳號",  "💻 Workspace"),
        ("POS帳號",        "🖥️ POS"),
        ("飛騰帳號",       "⚡ 飛騰"),
        ("門禁卡",         "🔑 門禁卡"),
        ("雲端學院帳號",   "🎓 雲端學院"),
    ]

    if not target_cands:
        st.info("目前無進行中的到職流程（需要「錄取審核」或「已錄取」狀態的候選人）。")
        return

    for c in target_cands:
        cid     = c["id"]
        name    = c.get("name", "?")
        stage   = c.get("stage", "")
        jtitle  = job_map.get(str(c.get("job_opening_id", "")), "")
        h       = hires_map.get(str(cid), {})
        done_n  = sum(1 for key, _ in CHECKLIST if h.get(key))
        total_n = len(CHECKLIST)

        with st.container(border=True):
            hc1, hc2 = st.columns([4, 2])
            hc1.markdown(
                f'<div style="font-weight:700;font-size:1rem;">{_html.escape(name)}'
                f'<span style="color:#64748b;font-size:0.8rem;margin-left:8px;">{_html.escape(jtitle)}</span></div>'
                f'<div style="font-size:0.78rem;margin-top:2px;">'
                + stage_badge(stage) + '</div>',
                unsafe_allow_html=True,
            )
            prog_color = "#15803d" if done_n == total_n else "#1e40af"
            hc2.markdown(
                f'<div style="text-align:right;font-weight:700;color:{prog_color};font-size:1.1rem;">'
                f'{done_n}/{total_n} 完成</div>'
                f'<div style="background:#e2e8f0;border-radius:99px;height:6px;margin-top:4px;">'
                f'<div style="background:{prog_color};width:{int(done_n/total_n*100)}%;'
                f'height:6px;border-radius:99px;"></div></div>',
                unsafe_allow_html=True,
            )

            # Checklist items
            check_cols = st.columns(total_n)
            changed = False
            new_h = dict(h)
            for col, (key, label) in zip(check_cols, CHECKLIST):
                current = bool(h.get(key))
                checked = col.checkbox(label, value=current, key=f"ob_{cid}_{key}")
                if checked != current:
                    new_h[key] = checked
                    changed = True

            if changed:
                new_h["candidate_id"] = cid
                if save_hire(new_h):
                    # 所有勾完 → 自動升為 hired
                    all_done = all(new_h.get(k) for k, _ in CHECKLIST)
                    if all_done and stage != "hired":
                        update_stage(cid, "hired")
                        st.toast(f"🎉 {name} 所有流程完成，已標記為入職！")
                    st.rerun()

            # Offer 薪資資訊
            with st.expander("薪資 / Offer 詳情", expanded=False):
                oc1, oc2, oc3 = st.columns(3)
                emp_type = oc1.selectbox("聘用類型",
                    ["全職", "兼職", "約聘", "試用"],
                    index=["全職","兼職","約聘","試用"].index(h.get("employment_type","全職"))
                    if h.get("employment_type") in ["全職","兼職","約聘","試用"] else 0,
                    key=f"ob_emp_{cid}")
                salary = oc2.number_input("月薪（元）", value=int(h.get("proposed_salary") or 0),
                                          step=1000, key=f"ob_sal_{cid}")
                start_val = None
                if h.get("start_date"):
                    try:
                        start_val = date.fromisoformat(str(h["start_date"])[:10])
                    except Exception:
                        pass
                start_date = oc3.date_input("報到日期", value=start_val or date.today() + timedelta(days=14),
                                             key=f"ob_start_{cid}")
                if st.button("儲存 Offer 資訊", key=f"ob_save_{cid}", type="primary"):
                    new_h2 = dict(h)
                    new_h2.update({
                        "candidate_id":    cid,
                        "employment_type": emp_type,
                        "proposed_salary": salary,
                        "start_date":      start_date.isoformat(),
                    })
                    if save_hire(new_h2):
                        st.success("✅ 已儲存！")
                        st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE 6 — 分析報表
# ══════════════════════════════════════════════════════════════
def page_analytics():
    if not HAS_PLOTLY:
        st.warning("請安裝 plotly：`pip install plotly`")
        return

    all_cands = fetch_all_candidates()
    all_ivs   = fetch_all_interviews()
    all_hires = fetch_all_hires()

    # 時間範圍選擇
    today = date.today()
    col_r1, col_r2, col_r3 = st.columns([2, 2, 3])
    period = col_r1.selectbox(
        "統計區間",
        ["本月", "上個月", "本季", "本年度", "全部", "自訂區間"],
        key="ana_period",
    )

    def get_preset_range(p):
        if p == "本月":
            return date(today.year, today.month, 1), today
        elif p == "上個月":
            first  = date(today.year, today.month, 1)
            last_m = first - timedelta(days=1)
            return date(last_m.year, last_m.month, 1), last_m
        elif p == "本季":
            q = (today.month - 1) // 3
            return date(today.year, q * 3 + 1, 1), today
        elif p == "本年度":
            return date(today.year, 1, 1), today
        else:
            return date(2020, 1, 1), today

    if period == "自訂區間":
        cr1, cr2 = col_r2.columns(2)
        start_d = cr1.date_input("開始", value=date(today.year, today.month, 1),
                                  key="ana_custom_start", label_visibility="collapsed")
        end_d   = cr2.date_input("結束", value=today,
                                  key="ana_custom_end", label_visibility="collapsed")
        col_r3.caption(f"自訂：{start_d.strftime('%Y/%m/%d')} – {end_d.strftime('%Y/%m/%d')}")
    else:
        start_d, end_d = get_preset_range(period)
        col_r2.caption(f"{start_d.strftime('%Y/%m/%d')} – {end_d.strftime('%Y/%m/%d')}")

    def in_range(row, field):
        dt = parse_dt(row.get(field))
        return dt and start_d <= dt.date() <= end_d

    cands_f = [c for c in all_cands if in_range(c, "created_at")]
    ivs_f   = [iv for iv in all_ivs  if in_range(iv, "scheduled_at")]
    hires_f = [h  for h  in all_hires if in_range(h,  "start_date")]

    # ── 指標行 ────────────────────────────────────────────────
    st.markdown("---")
    am1, am2, am3, am4 = st.columns(4)
    am1.metric("新進候選人", len(cands_f))
    am2.metric("進行面試", len(ivs_f))
    hired_n = sum(1 for h in hires_f)
    am3.metric("完成錄取", hired_n)
    pass_rate = (sum(1 for iv in ivs_f if iv.get("result") == "pass") / len(ivs_f) * 100
                 if ivs_f else 0)
    am4.metric("面試通過率", f"{pass_rate:.0f}%")
    st.markdown("---")

    ch1, ch2 = st.columns(2)

    # ── 招募漏斗 ──────────────────────────────────────────────
    with ch1:
        st.subheader("📊 招募漏斗")
        # 計算每個 stage 曾經到達的人數
        # 用「目前 stage 的 index >= stage_index」來估計
        funnel_labels = [STAGE_LABEL[s] for s in STAGE_KEYS if s != "rejected"]
        funnel_keys   = [s for s in STAGE_KEYS if s != "rejected"]
        funnel_counts = []
        for i, sk in enumerate(funnel_keys):
            cnt = sum(
                1 for c in cands_f
                if STAGE_KEYS.index(c.get("stage", STAGE_KEYS[0])) >= i
                   if c.get("stage") != "rejected"
            )
            funnel_counts.append(cnt)

        fig_funnel = go.Figure(go.Funnel(
            y=funnel_labels, x=funnel_counts,
            textinfo="value+percent initial",
            marker={"color": ["#1e40af","#2563eb","#3b82f6","#60a5fa","#93c5fd"]},
        ))
        fig_funnel.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=300,
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_funnel, use_container_width=True)

    # ── 候選人來源分布 ────────────────────────────────────────
    with ch2:
        st.subheader("🔍 候選人來源")
        if cands_f:
            src_df = pd.Series([c.get("source", "其他") or "其他" for c in cands_f]).value_counts()
            fig_src = px.pie(values=src_df.values, names=src_df.index,
                             color_discrete_sequence=px.colors.qualitative.Set3)
            fig_src.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=300,
                                   paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_src, use_container_width=True)
        else:
            st.info("此區間無候選人資料。")

    ch3, ch4 = st.columns(2)

    # ── 每月新增候選人趨勢 ────────────────────────────────────
    with ch3:
        st.subheader("📈 每月新增候選人")
        if cands_f:
            months = []
            for c in cands_f:
                dt = parse_dt(c.get("created_at"))
                if dt:
                    months.append(dt.strftime("%Y-%m"))
            if months:
                mo_df = pd.Series(months).value_counts().sort_index()
                fig_mo = px.bar(x=mo_df.index, y=mo_df.values,
                                labels={"x": "月份", "y": "人數"},
                                color_discrete_sequence=["#1e40af"])
                fig_mo.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280,
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_mo, use_container_width=True)
        else:
            st.info("此區間無資料。")

    # ── 評等分布 ─────────────────────────────────────────────
    with ch4:
        st.subheader("🏆 AI 評等分布")
        if cands_f:
            grade_df = pd.Series([c.get("grade", "?") or "?" for c in cands_f]).value_counts()
            color_map = {"A": "#f59e0b", "B": "#3b82f6", "C": "#94a3b8"}
            colors = [color_map.get(g, "#e2e8f0") for g in grade_df.index]
            fig_grade = px.bar(x=grade_df.index, y=grade_df.values,
                               labels={"x": "評等", "y": "人數"},
                               color=grade_df.index,
                               color_discrete_map=color_map)
            fig_grade.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280,
                                     showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
                                     paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_grade, use_container_width=True)
        else:
            st.info("此區間無資料。")

    # ── 匯出 Excel ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⬇ 匯出報告")
    if st.button("產生 Excel 報告", type="primary", key="ana_export"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            # 摘要
            summary = pd.DataFrame({
                "指標": ["新進候選人", "進行面試", "完成錄取", "面試通過率"],
                "數值": [len(cands_f), len(ivs_f), hired_n, f"{pass_rate:.0f}%"],
            })
            summary.to_excel(writer, sheet_name="摘要", index=False)
            # 候選人
            if cands_f:
                pd.DataFrame([{
                    "姓名": c.get("name"), "等級": c.get("grade"),
                    "階段": STAGE_LABEL.get(c.get("stage",""), c.get("stage","")),
                    "來源": c.get("source"), "穩定度": c.get("stability"),
                    "建立時間": c.get("created_at"),
                } for c in cands_f]).to_excel(writer, sheet_name="候選人", index=False)
            # 面試
            if ivs_f:
                pd.DataFrame([{
                    "候選人ID": iv.get("candidate_id"),
                    "面試時間": iv.get("scheduled_at"),
                    "面試官":   iv.get("interviewer"),
                    "結果":     RESULT_LABEL.get(iv.get("result",""), iv.get("result","")),
                    "備注":     iv.get("notes"),
                } for iv in ivs_f]).to_excel(writer, sheet_name="面試記錄", index=False)
            # 錄取
            if hires_f:
                pd.DataFrame([{
                    "候選人ID":   h.get("candidate_id"),
                    "聘用類型":   h.get("employment_type"),
                    "月薪":       h.get("proposed_salary"),
                    "報到日":     h.get("start_date"),
                    "錄取通知":  h.get("錄取通知寄出"),
                    "MIS單":     h.get("MIS聯絡單已送"),
                } for h in hires_f]).to_excel(writer, sheet_name="錄取", index=False)

        fn = f"HireFlow_{period}_{today.strftime('%Y%m%d')}.xlsx"
        st.download_button("📥 下載 Excel", buf.getvalue(), file_name=fn,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ══════════════════════════════════════════════════════════════
# PAGE — 職缺管理
# ══════════════════════════════════════════════════════════════
def page_jobs():
    jobs = fetch_all_jobs()
    if jobs:
        for j in jobs:
            status = j.get("status", "open")
            sc = {"open": "#15803d", "paused": "#b45309", "closed": "#475569"}.get(status, "#64748b")
            sl = {"open": "招募中", "paused": "暫停中", "closed": "已結束"}.get(status, status)
            jc1, jc2, jc3, jc4 = st.columns([3.5, 1.2, 1, 1.2])
            jc1.markdown(
                f'<b>{_html.escape(j.get("title",""))}</b>'
                f'<span style="color:#64748b;font-size:0.82rem;margin-left:8px;">'
                f'{_html.escape(j.get("department",""))}</span>',
                unsafe_allow_html=True,
            )
            jc2.markdown(f'<span style="color:{sc};font-weight:700;">● {sl}</span>', unsafe_allow_html=True)
            jc3.caption(f"需求 {j.get('headcount',1)} 人")
            with jc4:
                if status == "open":
                    if st.button("關閉", key=f"close_{j['id']}"):
                        save_job({"id": j["id"], "status": "closed"})
                        st.rerun()
                elif status == "closed":
                    if st.button("重開", key=f"reopen_{j['id']}"):
                        save_job({"id": j["id"], "status": "open"})
                        st.rerun()
    else:
        st.info("尚無職缺，請新增。")

    st.divider()
    st.markdown("**新增職缺**")
    with st.form("new_job_form"):
        nj1, nj2, nj3 = st.columns([3, 2, 1])
        new_title = nj1.text_input("職缺名稱 *", placeholder="門市銷售人員")
        new_dept  = nj2.text_input("部門",       placeholder="零售事業部")
        new_hc    = nj3.number_input("需求人數", value=1, min_value=1)
        if st.form_submit_button("新增職缺", type="primary"):
            if not new_title.strip():
                st.error("職缺名稱不可為空。")
            else:
                if save_job({"title": new_title.strip(), "department": new_dept.strip(),
                              "headcount": int(new_hc), "status": "open"}):
                    st.success(f"✅ 已新增：{new_title.strip()}")
                    st.rerun()

# ══════════════════════════════════════════════════════════════
# Setup Screen
# ══════════════════════════════════════════════════════════════
def render_setup():
    st.warning("⚙️ **尚未設定 Google Sheets 連線**，請填入試算表 ID。")
    st.markdown("""
**取得 Spreadsheet ID**

開啟你的六主檔試算表，網址格式如下：

```
https://docs.google.com/spreadsheets/d/**{Spreadsheet ID}**/edit
```

複製 `/d/` 和 `/edit` 之間那段 ID，貼到下方。

> 確認本機已執行 `gcloud auth login` 並有試算表讀寫權限。
""")
    with st.form("setup_form"):
        sid = st.text_input("Spreadsheet ID",
                            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")
        if st.form_submit_button("儲存設定", type="primary"):
            sid = sid.strip()
            if not sid or "/" in sid:
                st.error("請貼入 Spreadsheet ID（不含網址其他部分）。")
            else:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"spreadsheet_id": sid}, f, ensure_ascii=False, indent=2)
                load_config.clear()
                _load_all_sheets.clear()
                st.success("✅ 設定已儲存！")
                st.rerun()

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if not db_ok():
    st.title("🚀 ECLIFE HireFlow")
    render_setup()
    st.stop()

# Sidebar navigation
with st.sidebar:
    st.markdown(
        '<div style="font-family:\'Outfit\',sans-serif;font-size:1.35rem;font-weight:800;'
        'letter-spacing:-.03em;color:#f1f5f9;margin-bottom:2px;line-height:1.1;">'
        '🚀 HireFlow</div>'
        '<div style="font-size:0.68rem;font-weight:500;color:#475569;'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:18px;">'
        'ECLIFE · 招募任用儀表板</div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "導覽",
        ["🏠 本週 + 下週總覽",
         "🗂️ 招募看板",
         "👤 候選人",
         "📅 面試管理",
         "✅ 到職流程",
         "📈 分析報表",
         "📋 職缺管理"],
        key="nav",
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("🔄 重新整理資料", use_container_width=True):
        _invalidate()
        st.rerun()
    st.caption(f"今天：{date.today().strftime('%Y/%m/%d')}")

# Render selected page
if page == "🏠 本週 + 下週總覽":
    st.title("🏠 本週 + 下週總覽")
    page_overview()
elif page == "🗂️ 招募看板":
    st.title("🗂️ 招募看板")
    page_kanban()
elif page == "👤 候選人":
    st.title("👤 候選人管理")
    page_candidates()
elif page == "📅 面試管理":
    st.title("📅 面試管理")
    page_interviews()
elif page == "✅ 到職流程":
    st.title("✅ 到職流程")
    page_onboarding()
elif page == "📈 分析報表":
    st.title("📈 分析報表")
    page_analytics()
elif page == "📋 職缺管理":
    st.title("📋 職缺管理")
    page_jobs()
