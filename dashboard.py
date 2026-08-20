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
    from google.auth import default as _google_auth_default
    from google.auth import impersonated_credentials as _impersonated_credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

_SA_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# 用服務帳號模擬（impersonation）取代 gcloud 使用者 token，避免 Google 對 gcloud
# 預設 client 的敏感 scope 封鎖；與 app.py 用同一個 SA，不需要下載金鑰檔案。
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
from theme import inject_theme, render_brand_header
inject_theme()

# ── Design tokens（2026-07-14起：改為引用theme.py共用的顏色/字體/圓角/陰影，
#    這裡的變數名稱維持不變只是換成alias，全檔既有的 var(--p)/var(--text)/...
#    用法都不用改，只有:root宣告這裡換成指到共用token）────────────────────
st.markdown("""
<style>
:root {
  --p:       var(--c-primary);
  --p-lite:  var(--c-primary-lite);
  --p-dark:  var(--c-primary-dark);
  --accent:  var(--c-accent);

  --ok:      var(--c-ok);      --ok-bg:   var(--c-ok-bg);      --ok-bd:   var(--c-ok-border);
  --warn:    var(--c-warn);    --warn-bg: var(--c-warn-bg);    --warn-bd: var(--c-warn-border);
  --err:     var(--c-err);     --err-bg:  var(--c-err-bg);     --err-bd:  var(--c-err-border);

  --text:    var(--c-text);
  --muted:   var(--c-text-muted);
  --border:  var(--c-border);
  --surface: var(--c-surface);
  --surf-2:  var(--c-surface-2);
  --white:   var(--c-card-bg);

  --sh-xs:  var(--shadow-sm);
  --sh-sm:  var(--shadow-sm);
  --sh-md:  var(--shadow-md);
  --sh-p:   var(--shadow-btn);

  --r-sm: var(--radius); --r: var(--radius); --r-lg: var(--radius-lg);

  --font-d: var(--font-ui);
  --font-b: var(--font-ui);
  --font-m: var(--font-data);
}

/* ── Base ─────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: var(--font-b) !important;
  color: var(--text) !important;
  -webkit-font-smoothing: antialiased !important;
}

/* Headings */
/* h1/h2/h3 font-size 由 theme.py 共用（--fs-2xl/xl/lg），這裡只留字重/字距 */
h1 {
  font-family: var(--font-d) !important;
  font-weight: 800 !important;
  letter-spacing: -.035em !important;
  color: var(--text) !important;
  line-height: 1.15 !important;
}
h2 {
  font-family: var(--font-d) !important;
  font-weight: 700 !important;
  letter-spacing: -.02em !important;
}
h3 {
  font-family: var(--font-d) !important;
  font-weight: 700 !important;
  letter-spacing: -.015em !important;
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
  font-size: var(--fs-data) !important;
  font-weight: 700 !important;
  color: var(--p) !important;
  letter-spacing: -.02em !important;
}
[data-testid="stMetric"] label {
  font-size: var(--fs-xs) !important;
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
  transition: border-color .15s, background .15s !important;
}
[data-testid="stButton"] button[kind="secondary"]:hover {
  border-color: var(--p) !important;
  background: var(--p-lite) !important;
  color: var(--p) !important;
}

/* ── Cards / containers ── Streamlit 1.57 拿掉了 stVerticalBlockBorderWrapper，
   border=True 的 container 不再有專屬 testid，只能靠 key= 產生的
   class="st-key-<key>" 鎖定；下面列出本檔所有 bordered card 的 key 前綴
   （kb_card / kb_job 是招募看板既有的 key，跟下面 page_kanban() 裡的
   專屬覆寫規則並存——那邊的規則在原始碼順序上更後面，specificity 相同時
   會蓋掉這裡的 padding/border-radius，是刻意的疊加，不是衝突）──────── */
[class*="st-key-kb_card"],
[class*="st-key-kb_job"],
[class*="st-key-card_stage_"],
[class*="st-key-card_hire_"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  box-shadow: var(--sh-xs) !important;
  padding: 14px 18px !important;
  background: var(--white) !important;
  transition: box-shadow .18s, transform .15s !important;
}
[class*="st-key-kb_card"]:hover,
[class*="st-key-kb_job"]:hover,
[class*="st-key-card_stage_"]:hover,
[class*="st-key-card_hire_"]:hover {
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
  font-size: var(--fs-sm) !important;
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
  background: var(--sb-bg) !important;
  border-right: 1px solid var(--sb-border) !important;
}
[data-testid="stSidebar"] * { color: var(--sb-muted) !important; }
[data-testid="stSidebar"] hr { border-color: var(--sb-border) !important; }

/* Nav items — hide radio circles */
[data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radio"],
[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"],
[data-testid="stSidebar"] [data-testid="stRadio"] span[data-baseweb="radio"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  display: block !important;
  padding: 9px 14px !important;
  border-radius: var(--r-sm) !important;
  font-size: var(--fs-sm) !important;
  font-weight: 500 !important;
  font-family: var(--font-b) !important;
  color: var(--sb-muted) !important;
  cursor: pointer !important;
  transition: background .15s, color .15s !important;
  margin-bottom: 2px !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: var(--sb-surface2) !important;
  color: var(--sb-text) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
[data-testid="stSidebar"] [data-testid="stRadio"] label:has([aria-checked="true"]) {
  background: var(--sb-surface2) !important;
  color: var(--sb-text) !important;
  border-left: 3px solid var(--accent) !important;
}

/* Sidebar caption / small text */
[data-testid="stSidebar"] [data-testid="stText"] small,
[data-testid="stSidebar"] small { color: var(--sb-muted) !important; }

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* ── Checkbox ─────────────────────────────────────────── */
[data-testid="stCheckbox"] label {
  font-family: var(--font-b) !important;
  font-size: var(--fs-sm) !important;
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
  font-size: var(--fs-xs) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────
CONFIG_FILE       = "gsheet_config.json"   # shared with sync_to_gsheet.py

# STAGES / STAGE_KEYS / STAGE_LABEL / STAGE_ICON / STAGE_BG / STAGE_FG
# 定義已搬移至 hr_schema.py（單一來源）
from hr_schema import STAGES, STAGE_KEYS, STAGE_LABEL, STAGE_ICON, STAGE_BG, STAGE_FG
from sync_queue import load_pending as _load_pending_sync, remove_pending as _remove_pending_sync

# Grade 顏色權威來源在 hr_schema.py（GRADE_META），這裡轉成既有程式碼慣用的
# (bg, text, border, icon) tuple 形狀，呼叫端不用改。
from hr_schema import GRADE_META as _GRADE_META_SRC
GRADE_META = {k: (v["bg"], v["fg"], v["border"], v["icon"]) for k, v in _GRADE_META_SRC.items()}
RESULT_LABEL = {"pending": "待定", "pass": "通過", "fail": "未通過", "no_show": "面試未到"}
RESULT_COLOR = {"pending": "#d97706", "pass": "#059669", "fail": "#dc2626", "no_show": "#64748b"}
WD_ZH = ["一", "二", "三", "四", "五", "六", "日"]

# ── Config ────────────────────────────────────────────────────
# CONFIG_FILE shared with sync_to_gsheet.py

@st.cache_data(ttl=30)
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _load_impersonate_sa() -> str:
    """讀取服務帳號模擬用的 SA email，不寫死在程式碼裡——這個 repo 有推公開 GitHub，
    寫死會把 GCP 專案 ID 跟 SA email 曝光。"""
    return load_config().get("impersonate_sa", "")

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
    """Return authorised gspread client。優先順序：st.secrets SA（Streamlit Cloud 部署用）→
    本機模擬 hr-sheets-sync 服務帳號（本機開發用，不需要下載金鑰檔案）。"""
    if not HAS_GSPREAD:
        return None
    # 1. Streamlit Cloud / st.secrets service account（雲端部署才會用到）
    try:
        sa_info = dict(st.secrets["gcp_service_account"])
        creds = _SACredentials.from_service_account_info(sa_info, scopes=_SA_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        pass
    # 2. 本機開發：模擬服務帳號（用現有 gcloud 登入身份換發 SA token，不需要金鑰檔案）
    try:
        source_creds, _ = _google_auth_default()
        creds = _impersonated_credentials.Credentials(
            source_credentials=source_creds,
            target_principal=_load_impersonate_sa(),
            target_scopes=_SA_SCOPES,
            lifetime=300,
        )
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
# FLOW_TO_STAGE / STAGE_TO_FLOW / _RESULT_MAP / _STATUS_MAP
# 定義已搬移至 hr_schema.py（單一來源），此處保留同名別名避免動到下游程式碼
import hr_schema  # 2026-08-13：看板卡片老化天數/首頁待催辦要用 hr_schema.workdays_since
from hr_schema import (
    FLOW_TO_STAGE, STAGE_TO_FLOW,
    RESULT_MAP as _RESULT_MAP,
    STATUS_MAP as _STATUS_MAP,
    CLOSE_REASONS, CLOSE_REASON_TO_INTERVIEW,
    S3_COLS, SHEET_HEADERS,
)

# ── 寫入前的兩道防護（2026-08-05 新增）────────────────────────────
def _safe_headers(target, schema_cols):
    """從快取列取回欄位順序，並確認它沒有被重複／空白欄名塌掉。
    _load_all_sheets 用 dict(zip(headers, padded)) 建每一列，表頭若出現重複或
    空白欄名，dict 會把它們併成同一個 key，headers 就整體變短，之後
    headers.index(欄名)+1 算出的欄號會左移，update_cell 靜靜寫到錯的欄位——
    而且是全表系統性寫錯，不是偶發一列。長度對不上就拒絕寫入。
    """
    headers = [k for k in target.keys() if k != "_row"]
    if len(headers) != len(schema_cols):
        st.error(
            f"試算表表頭異常：讀到 {len(headers)} 欄，應該有 {len(schema_cols)} 欄。"
            "可能是第 1 列有重複或空白的欄位名稱。為避免把資料寫到錯的欄位已中止，"
            "請先檢查試算表第 1 列。"
        )
        return None
    return headers

def _row_still_matches(ws, row_num, expected_id):
    """寫入前確認那一列真的還是那個人（A 欄是三張主檔共同的 key 欄）。
    _row 來自 60 秒 TTL 的快取。如果這段時間內有人直接在 Sheets 手動刪列／插列，
    列號會整體位移，寫入就會打到別人身上——2026-08-05 實際發生過：翁志魁被寫成
    「錄取審核」，但他根本還沒面試。多花 1 次單格讀取換掉這個風險。
    """
    try:
        return ws.acell(f"A{row_num}").value == expected_id
    except Exception:
        # 讀不到通常是配額／網路問題，此時接下來的寫入也會失敗並顯示錯誤，
        # 不需要在這裡多攔一層（維持原本行為，不製造新的死路）。
        return True

# ── Sheets reader ─────────────────────────────────────────────
def _sheet_to_dicts(sh, name: str) -> list:
    import time as _t
    # 六/七張主檔每次快取過期都要各讀一次，短時間內密集操作（連續切頁、連續
    # 重新整理）容易撞到Sheets API「每分鐘讀取次數」的配額上限。退讓從
    # 1s→2s拉長到1s→2s→4s→8s（4次嘗試），撐過同一個配額窗口的機率高很多。
    for attempt in range(4):
        try:
            ws = sh.worksheet(name)
            rows = ws.get_all_values()
            if not rows:
                return []
            headers = rows[0]
            result = []
            for r_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                # 補齊欄位，確保所有 header 都在 dict 裡（保留欄位順序供 update_stage 用）
                padded = row + [''] * max(0, len(headers) - len(row))
                d = dict(zip(headers, padded))
                d['_row'] = r_idx   # 保留實際列號，讓 update_stage 不需重新讀表
                result.append(d)
            return result
        except Exception as e:
            if '429' in str(e) and attempt < 3:
                _t.sleep(2 ** attempt)  # 1s → 2s → 4s → 8s
                continue
            st.error(f"讀取 {name} 失敗：{e}")
            return []
    return []

@st.cache_data(ttl=60, show_spinner="載入資料中…")
def _load_all_sheets() -> dict:
    sh = _get_sheet()
    if not sh:
        return {}
    names = ["01_職缺主檔", "02_候選人主檔", "03_應徵主檔",
             "04_評分主檔", "05_面試主檔", "06_員工主檔", "07_AI初篩統計"]
    result = {n: _sheet_to_dicts(sh, n) for n in names}
    # 若關鍵表（候選人/應徵）全空，代表可能是 429 快取污染，不存快取
    if not result.get("02_候選人主檔") and not result.get("03_應徵主檔"):
        _load_all_sheets.clear()
    st.session_state["_data_fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result

def _invalidate():
    _load_all_sheets.clear()

# ── Local backup ─────────────────────────────────────────────
def _sheet_rows_for_backup(sh, name: str) -> list:
    """近似 _sheet_to_dicts，但讀取失敗時 raise 例外而非吞掉並回傳空清單，
    確保備份功能不會把 429/連線失敗誤當成「這張表本來就是空的」而靜默寫出空檔。"""
    import time as _t
    for attempt in range(3):
        try:
            ws = sh.worksheet(name)
            rows = ws.get_all_values()
            if not rows:
                return []
            headers = rows[0]
            result = []
            for row in rows[1:]:
                if not any(row):
                    continue
                padded = row + [''] * max(0, len(headers) - len(row))
                result.append(dict(zip(headers, padded)))
            return result
        except Exception as e:
            if '429' in str(e) and attempt < 2:
                _t.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"讀取「{name}」失敗：{e}") from e
    return []

def backup_sheets_to_local() -> tuple:
    """把六主檔各存成一份 CSV 到 backups/{今天日期}/ 底下。回傳 (成功與否, 訊息)。
    同一天重複執行會直接覆蓋當天的備份檔（不做多版本）。"""
    sh = _get_sheet()
    if not sh:
        return False, "無法連線至 Google Sheets，請確認驗證設定與 spreadsheet_id 是否正確"
    names = ["01_職缺主檔", "02_候選人主檔", "03_應徵主檔",
             "04_評分主檔", "05_面試主檔", "06_員工主檔", "07_AI初篩統計"]
    today_str = date.today().strftime("%Y-%m-%d")
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups", today_str)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for name in names:
            rows = _sheet_rows_for_backup(sh, name)
            df = pd.DataFrame(rows)
            df.to_csv(os.path.join(backup_dir, f"{name}.csv"), index=False, encoding="utf-8-sig")
        return True, today_str
    except Exception as e:
        return False, str(e)

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
            # 2026-08-13：開缺存量表要算「開了幾天」，補上原本沒映射的建立日期
            "created_at": row.get("建立日期", ""),
        })
    return result

def fetch_all_candidates() -> list:
    """回傳「一筆應徵（application）= 一筆紀錄」的清單，操作單位是 application_id，
    不是 candidate_id。

    2026-07-15 修正一個真實bug：同一人（candidate_id相同）如果同時應徵/被篩選
    了兩個不同職缺，03_應徵主檔會有兩筆列，application_id不同、流程狀態也各自
    獨立。舊寫法用candidate_id去重（只留最新一筆），導致：(1) 同一人的其他職缺
    應徵紀錄整個消失在候選人清單/看板裡；(2) update_stage/update_note用
    candidate_id去找列時，遇到重複會抓到「表格裡第一個符合的」，可能改到錯的
    職缺申請（實際案例：鄧旻翠同時應徵商品採購規劃專員與零件採購專員，在後者
    按推進，改到的卻是前者）。
    現在每一筆03_應徵主檔的列都各自成為一筆輸出紀錄，"id" 欄位是 application_id，
    "candidate_id" 欄位保留人的識別碼供「06_員工主檔到職資料」這類本來就是
    per-person（不是per-application）的查找使用。
    """
    data = _load_all_sheets()
    apps  = data.get("03_應徵主檔", [])
    score = data.get("04_評分主檔", [])
    cands = data.get("02_候選人主檔", [])

    cand_map: dict = {c.get("candidate_id", ""): c for c in cands if c.get("candidate_id")}

    score_by_app: dict = {}
    score_by_cid: dict = {}
    for s in score:
        aid = s.get("application_id", "")
        cid = s.get("candidate_id") or s.get("cand_id", "")
        if aid and aid not in score_by_app:
            score_by_app[aid] = s
        if cid and cid not in score_by_cid:
            score_by_cid[cid] = s

    result = []
    seen_cids = set()
    for a in apps:
        app_id = a.get("application_id", "")
        cid = a.get("candidate_id", "")
        if not app_id or not cid:
            continue
        seen_cids.add(cid)
        c = cand_map.get(cid, {})
        s = score_by_app.get(app_id) or score_by_cid.get(cid, {})
        grade_raw = (a.get("綜合推薦度") or s.get("綜合推薦度") or "").strip().upper()
        grade = grade_raw[0] if grade_raw and grade_raw[0] in ("A", "B", "C") else "C"
        stage = FLOW_TO_STAGE.get(a.get("流程狀態", ""), "screening")
        result.append({
            "id":              app_id,
            "candidate_id":    cid,
            "name":            c.get("真實姓名", ""),
            "code_104":        c.get("104代碼", ""),
            "email":           c.get("Email", ""),
            "source":          c.get("來源", a.get("應徵來源", "")),
            "job_opening_id":  a.get("job_id", ""),
            "grade":           grade,
            "stage":           stage,
            "created_at":      c.get("初次進庫日期", a.get("應徵批次日期", "")),
            "stability":       s.get("穩定度評估", ""),
            "commute":         s.get("通勤評估", ""),
            "highlights":      s.get("客觀戰功亮點", ""),
            "gaps":            s.get("缺口與潛在地雷", ""),
            "screening_notes": a.get("初篩判定", s.get("初篩判定", "")),
            # AI初篩結果（合格/不合格），供候選人頁預設過濾用；獨立欄位，
            # 不要拿screening_notes字串做in判斷（那是自由文字判定理由）。
            "screening_result": a.get("AI初篩狀態", ""),
            "note":            a.get("備註", ""),
            "stage_updated_at": a.get("人才狀態更新日", ""),
            # 結案前是卡在哪個階段（漏斗轉換率計算用：已結案的人流程狀態變成
            # 「已結案」後，原本走到哪一步就看不出來了，靠這欄位回推）
            "prestage":        FLOW_TO_STAGE.get(a.get("結案前階段", ""), ""),
            # AI判不合格、HR從淘汰名單人工拉上來推薦的人（app.py的
            # mark_hr_override_batch寫入）。分析報表用這個算「人工覆核率」，
            # 偏高代表AI評分prompt/維度可能需要檢視，不是對外揭露用途。
            "hr_override":     a.get("HR初篩狀態", "") == "人工覆核通過",
            # 2026-08-13：首頁待催辦清單要用，跟 daily_health_check.py 判斷
            # 同一件事（卡在哪個流程狀態、推薦給誰、哪天推薦的），這裡補進來
            # 而不是另外重新查一次 Sheets——資料已經在手上，只是沒映射出來。
            "flow_status":     a.get("流程狀態", ""),
            "job_name":        a.get("職缺名稱", ""),
            "recommended_to":  a.get("推薦主管", ""),
            "recommended_at":  a.get("推薦日", ""),
        })

    # 候選人主檔裡有、但03_應徵主檔完全沒有對應列的人（極少見的邊界情況），
    # 仍然要讓他們出現在清單裡，用candidate_id當id（沒有application可用）。
    for cid, c in cand_map.items():
        if cid in seen_cids:
            continue
        result.append({
            "id": cid, "candidate_id": cid,
            "name": c.get("真實姓名", ""), "code_104": c.get("104代碼", ""),
            "email": c.get("Email", ""), "source": c.get("來源", ""),
            "job_opening_id": "", "grade": "C", "stage": "screening",
            "created_at": c.get("初次進庫日期", ""), "stability": "", "commute": "",
            "highlights": "", "gaps": "", "screening_notes": "", "note": "",
            "stage_updated_at": "", "prestage": "", "hr_override": False,
            "flow_status": "", "job_name": "", "recommended_to": "", "recommended_at": "",
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
            "actual_start_date": row.get("實際報到日", "") or None,
            "employment_type": row.get("聘用類型", "") or "全職",
            "proposed_salary": row.get("薪資（月）", "") or None,
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
            # 招募→留任回饋迴路（E）：日後回頭檢視AI評分準不準用
            "三個月考核結果":  row.get("三個月考核結果", ""),
            "試用期通過":      row.get("試用期通過", ""),
            "離職日":          row.get("離職日", ""),
            "離職原因類別":    row.get("離職原因類別", ""),
        })
    return result

def fetch_screening_stats() -> dict:
    """AI總共初篩了多少履歷／幾份合格。03_應徵主檔本來就是「每份被AI初篩過的
    履歷各一列」，AI初篩狀態欄位就有合格/不合格，不用等新的07_AI初篩統計表
    才有數字——直接數03_應徵主檔即可回溯到最早的批次，不是只從今天開始累計。
    """
    data = _load_all_sheets()
    rows = data.get("03_應徵主檔", [])
    total = len(rows)
    passed = sum(1 for r in rows if r.get("AI初篩狀態") == "合格")
    return {"total_screened": total, "total_passed": passed}

def _candidates_with_join(rows: list, jobs: list) -> list:
    job_map = {j["id"]: j["title"] for j in jobs}
    return [{**c, "_job_title": job_map.get(str(c.get("job_opening_id", "")), "")}
            for c in rows]

def _interviews_with_join(ivs: list, cands: list, jobs: list) -> list:
    # cands 的 "id" 現在是 application_id；面試紀錄理想上也該用 application_id
    # 對應到「哪一筆應徵」，只在舊面試紀錄沒有 application_id 時才退回用
    # candidate_id 配對（配到同一人的哪個職缺不保證正確，但至少不會整個查無此人）。
    cand_by_app = {c["id"]: c for c in cands}
    cand_by_cid = {c["candidate_id"]: c for c in cands if c.get("candidate_id")}
    job_map  = {j["id"]: j["title"] for j in jobs}
    result = []
    for iv in ivs:
        iv2 = dict(iv)
        c = cand_by_app.get(str(iv.get("application_id", ""))) \
            or cand_by_cid.get(str(iv.get("candidate_id", "")), {})
        iv2["_cand_name"]  = c.get("name", "?")
        iv2["_cand_stage"] = c.get("stage", "")
        iv2["_job_title"]  = job_map.get(str(c.get("job_opening_id", "")), "")
        result.append(iv2)
    return sorted(result, key=lambda x: str(x.get("scheduled_at") or ""))

# ── Write Helpers ─────────────────────────────────────────────
def _with_429_retry(fn):
    """比照 _sheet_to_dicts 的 429 指數退讓重試（1s → 2s），最多 3 次嘗試。"""
    import time as _t
    for attempt in range(3):
        try:
            return fn()
        except Exception as e:
            if '429' in str(e) and attempt < 2:
                _t.sleep(2 ** attempt)
                continue
            raise

def _upsert_row(ws, key_col: str, data: dict) -> bool:
    rows = _with_429_retry(lambda: ws.get_all_values())
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
            _with_429_retry(lambda: ws.update_cells(cells, value_input_option="RAW"))
    else:
        _with_429_retry(lambda: ws.append_row(
            [str(data.get(h, "")) for h in headers],
            value_input_option="RAW", insert_data_option="INSERT_ROWS"))
    return True

# ── Write Wrappers ────────────────────────────────────────────
def update_stage(app_id: str, new_stage: str, close_reason: str = "") -> bool:
    """app_id 是 application_id（一筆「人 × 職缺」的應徵紀錄），不是 candidate_id。
    2026-07-15 修正：舊版用 candidate_id 找列，同一人若同時應徵兩個職缺會抓到
    表格裡第一筆符合的列而改錯人（實際發生過：鄧旻翠同時應徵兩個職缺，在其中
    一個按推進，另一個被誤改）。改用 application_id 精準對應到唯一一列。

    close_reason 只在 new_stage=="rejected" 時有意義（訊息未回/面試未到/
    面試未通過/候選人婉拒，見hr_schema.CLOSE_REASONS）。2026-07-23新增：
    之前結案完全沒記原因，事後查不出來為什麼結案、面試通過率也因此失真，
    這裡把原因寫進「結案原因」欄，並且「面試未到/面試未通過」順便同步
    05_面試主檔，不用再事後手動回補。
    """
    sh = _get_sheet()
    if not sh:
        return False
    try:
        flow = STAGE_TO_FLOW.get(new_stage, new_stage)
        # 用快取資料找列號，避免額外 API read（防止 429）
        cached_apps = _load_all_sheets().get("03_應徵主檔", [])
        target = next((a for a in cached_apps if a.get("application_id") == app_id), None)
        if not target or "_row" not in target:
            st.error("找不到應徵紀錄，請重新整理後再試")
            return False
        row_num = target["_row"]
        # dict keys 保留欄位順序（Python 3.7+），排除 _row 後即為原始 headers
        headers = _safe_headers(target, S3_COLS)
        if headers is None:
            return False
        if "流程狀態" not in headers:
            st.error("試算表缺少「流程狀態」欄位")
            return False
        flow_col = headers.index("流程狀態") + 1  # gspread 1-indexed
        ws = sh.worksheet("03_應徵主檔")
        if not _row_still_matches(ws, row_num, app_id):
            _invalidate()
            st.error("資料已變動（試算表的列可能被手動增刪過），為避免改到別人的紀錄已中止。"
                     "請重新整理頁面後再試一次。")
            return False
        # 結案時把「原本卡在哪個階段」記下來，流程狀態一旦變成「已結案」就再
        # 也看不出來走到哪一步了——這欄供之後的漏斗轉換率計算用。
        old_stage = FLOW_TO_STAGE.get(target.get("流程狀態", ""), "screening")
        if new_stage == "rejected" and "結案前階段" in headers:
            prestage_col = headers.index("結案前階段") + 1
            ws.update_cell(row_num, prestage_col, target.get("流程狀態", ""))
        if new_stage == "rejected" and close_reason and "結案原因" in headers:
            reason_col = headers.index("結案原因") + 1
            ws.update_cell(row_num, reason_col, close_reason)
        ws.update_cell(row_num, flow_col, flow)
        # 結案原因是「面試未到」或「面試未通過」，順便同步一筆05_面試主檔
        # 紀錄，理由跟上面推進離開已面試自動同步通過是同一件事——
        # 不要再靠事後回補，資料要在動作發生的當下就記對。
        # 兩者寫進去的「面試結果」不同：未到寫「面試未到」、未通過寫「未通過」。
        if new_stage == "rejected" and close_reason in CLOSE_REASON_TO_INTERVIEW:
            _iv_result, _iv_note = CLOSE_REASON_TO_INTERVIEW[close_reason]
            _sync_interview_result_on_close(
                app_id, target.get("candidate_id", ""), target.get("job_id", ""),
                target.get("姓名", ""), _iv_result, _iv_note,
            )
        # 從「已面試」推進到更後面的階段，隱含面試結果是通過——但HR多半是
        # 直接在看板/候選人頁按推進，沒有另外回頭去面試管理的記分卡把結果
        # 填成「通過」，導致05_面試主檔那筆紀錄一直卡在「待定」，分析報表
        # 的面試通過率因此永遠算成0%（使用者實際回報的落差）。這裡在推進
        # 離開已面試階段時順便同步，只補「待定/空白」的情況，不覆蓋HR已經
        # 明確填過的未通過。
        if (old_stage == "interviewed" and new_stage not in ("interviewed", "rejected")
                and STAGE_KEYS.index(new_stage) > STAGE_KEYS.index("interviewed")):
            _sync_interview_pass_if_pending(app_id, target.get("candidate_id", ""))
        # 順便記錄「進入這個階段的日期」，供看板卡片顯示（例如「7/15 已傳邀約」）
        if "人才狀態更新日" in headers:
            updated_col = headers.index("人才狀態更新日") + 1
            ws.update_cell(row_num, updated_col, date.today().isoformat())
        _invalidate()
        return True
    except Exception as e:
        st.error(f"更新失敗：{e}")
        return False

def _sync_interview_pass_if_pending(app_id: str, candidate_id: str) -> None:
    """從已面試推進到更後面階段時，把05_面試主檔對應那筆的「面試結果」從
    待定/空白同步成「通過」——這是錦上添花的同步，找不到紀錄或寫入失敗
    都不影響update_stage本身的推進動作，所以不回傳成功與否、不拋例外。
    """
    sh = _get_sheet()
    if not sh:
        return
    try:
        ws = sh.worksheet("05_面試主檔")
        cached_ivs = _load_all_sheets().get("05_面試主檔", [])
        target_iv = next((iv for iv in cached_ivs if iv.get("application_id") == app_id), None)
        if not target_iv:
            # 舊面試紀錄可能沒有application_id欄位，退回candidate_id比對
            target_iv = next((iv for iv in cached_ivs if iv.get("candidate_id") == candidate_id), None)
        if not target_iv or "_row" not in target_iv:
            return
        if str(target_iv.get("面試結果", "")).strip() in ("", "待定"):
            headers = _safe_headers(target_iv, SHEET_HEADERS["05_面試主檔"])
            if headers and "面試結果" in headers:
                if not _row_still_matches(ws, target_iv["_row"], target_iv.get("interview_id", "")):
                    return
                col = headers.index("面試結果") + 1
                ws.update_cell(target_iv["_row"], col, "通過")
    except Exception:
        pass

def _sync_interview_result_on_close(app_id: str, candidate_id: str, job_id: str,
                                     name: str, result_text: str, note: str) -> None:
    """結案原因選「面試未到」或「面試未通過」時，把05_面試主檔對應那筆的
    面試結果明確寫成 result_text（這是HR當下明確選擇的原因，不是被動推論，
    所以直接覆蓋，不像_sync_interview_pass_if_pending只補待定/空白）；
    如果根本沒有面試紀錄（例如面試未到，從沒真的排過面試/沒建過紀錄），
    直接用save_interview建一筆，日期用今天（結案當下），備註寫結案原因。

    result_text 由 CLOSE_REASON_TO_INTERVIEW 決定：「面試未到」→「面試未到」、
    「面試未通過」→「未通過」。2026-08-12 之前兩者都寫「未通過」，讓沒出席的人
    進了面試通過率的分母。
    """
    sh = _get_sheet()
    if not sh:
        return
    try:
        cached_ivs = _load_all_sheets().get("05_面試主檔", [])
        target_iv = next((iv for iv in cached_ivs if iv.get("application_id") == app_id), None)
        if not target_iv:
            target_iv = next((iv for iv in cached_ivs if iv.get("candidate_id") == candidate_id), None)
        if target_iv and "_row" in target_iv:
            ws = sh.worksheet("05_面試主檔")
            headers = _safe_headers(target_iv, SHEET_HEADERS["05_面試主檔"])
            if not headers or not _row_still_matches(
                    ws, target_iv["_row"], target_iv.get("interview_id", "")):
                return
            if "面試結果" in headers:
                ws.update_cell(target_iv["_row"], headers.index("面試結果") + 1, result_text)
            if "面試官備註" in headers:
                ws.update_cell(target_iv["_row"], headers.index("面試官備註") + 1, note)
        else:
            save_interview({
                "candidate_id": candidate_id, "application_id": app_id,
                "job_id": job_id, "name": name,
                "scheduled_at": date.today().isoformat(), "interviewer": "",
                "result": _RESULT_MAP.get(result_text, "fail"), "notes": note,
            })
    except Exception:
        pass

def retry_pending_syncs() -> tuple[int, int]:
    """重試 app.py 端寫入失敗、暫存在 pending_status_sync.json 的流程狀態更新。
    application_id 用跟 app.py（update_application_status_gsheet）相同的規則現場組回
    來（佇列裡只存104代碼/職缺名稱，沒存application_id），組好後直接呼叫既有的
    update_stage，不重寫一份寫入邏輯。回傳 (成功數, 失敗數)。
    """
    import re as _re
    ok = fail = 0
    for p in _load_pending_sync():
        job_safe = _re.sub(r'[^\w\-]', '_', p.get("job_name", ""))[:20]
        app_id = f"APP-{p.get('code', '')}-{job_safe}"
        stage = FLOW_TO_STAGE.get(p.get("new_status", ""), "")
        if stage and update_stage(app_id, stage):
            _remove_pending_sync(p["key"])
            ok += 1
        else:
            fail += 1
    return ok, fail

def update_note(app_id: str, note: str) -> bool:
    """app_id 是 application_id，理由同 update_stage。"""
    sh = _get_sheet()
    if not sh:
        return False
    try:
        # 用快取資料找列號，避免額外 API read（防止 429）
        cached_apps = _load_all_sheets().get("03_應徵主檔", [])
        target = next((a for a in cached_apps if a.get("application_id") == app_id), None)
        if not target or "_row" not in target:
            st.error("找不到應徵紀錄，請重新整理後再試")
            return False
        row_num = target["_row"]
        headers = _safe_headers(target, S3_COLS)
        if headers is None:
            return False
        if "備註" not in headers:
            st.error("試算表缺少「備註」欄位")
            return False
        note_col = headers.index("備註") + 1  # gspread 1-indexed
        ws = sh.worksheet("03_應徵主檔")
        if not _row_still_matches(ws, row_num, app_id):
            _invalidate()
            st.error("資料已變動（試算表的列可能被手動增刪過），為避免改到別人的紀錄已中止。"
                     "請重新整理頁面後再試一次。")
            return False
        ws.update_cell(row_num, note_col, note)
        _invalidate()
        return True
    except Exception as e:
        st.error(f"備註更新失敗：{e}")
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
            "面試結果":       {"pass": "通過", "fail": "未通過",
                               "no_show": "面試未到"}.get(data.get("result", ""), "待定"),
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
            "實際報到日":     str(data.get("actual_start_date", "") or ""),
            "薪資（月）":     str(data.get("proposed_salary", "") or ""),
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
            "三個月考核結果": str(data.get("三個月考核結果", "") or ""),
            "試用期通過":     str(data.get("試用期通過", "") or ""),
            "離職日":         str(data.get("離職日", "") or ""),
            "離職原因類別":   str(data.get("離職原因類別", "") or ""),
            "聘用類型":       str(data.get("employment_type", "") or ""),
        }
        _upsert_row(ws, "candidate_id", row_data)
        _invalidate()
        return True
    except Exception as e:
        st.error(f"任用記錄儲存失敗：{e}")
        return False

def save_job(data: dict) -> bool:
    """更新既有職缺的狀態（招募中/暫停中/已結束）。

    2026-08-14：拿掉「新增職缺」功能，只保留更新既有職缺。原本的新增分支
    （data 沒帶 id 時自己生一個 job_id）已經沒有任何呼叫端會用到，一併移除，
    不留死程式碼——見 dashboard.py page_jobs() 的說明，新職缺一律從
    app.py（動態篩選引擎）建立，不能在這裡憑空生。

    data 必須帶 "id"（既有職缺的 job_id），否則直接失敗，不會生新職缺。
    """
    sh = _get_sheet()
    if not sh:
        return False
    jid = data.get("id", "")
    if not jid:
        st.error("職缺更新失敗：缺少 job_id（新職缺請到「動態篩選引擎」建立，不能在這裡新增）。")
        return False
    try:
        import time as _time
        ws = sh.worksheet("01_職缺主檔")
        status_zh = {"open": "招募中", "paused": "暫停中", "closed": "已結束"}.get(
            data.get("status", "open"), "招募中")
        row_data = {"job_id": jid, "狀態": status_zh}
        if data.get("title"):
            row_data["職缺名稱"] = data["title"]
        if data.get("department"):
            row_data["工作地點"] = data["department"]
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
            f'border-radius:5px;font-weight:800;font-size:var(--fs-sm);padding:2px 8px;'
            f'font-family:var(--font-m);">{gm[3]} {g}</span>')

def stage_badge(stage: str) -> str:
    bg = STAGE_BG.get(stage, "#f1f5f9")
    fg = STAGE_FG.get(stage, "#475569")
    return (f'<span style="background:{bg};color:{fg};border:1px solid {fg}44;'
            f'border-radius:5px;font-weight:700;font-size:var(--fs-xs);padding:3px 9px;">'
            f'{STAGE_ICON.get(stage,"")} {STAGE_LABEL.get(stage,stage)}</span>')

def gcal_link(title: str, start_dt: datetime, duration_min=60, desc="", location="公司") -> str:
    fmt = "%Y%m%dT%H%M%S"
    end_dt = start_dt + timedelta(minutes=duration_min)
    p = {"action": "TEMPLATE", "text": title,
         "dates": f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}",
         "details": desc, "location": location}
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(p)

# 2026-07-27新增：面試會議室固定訂2R，行事曆標題/備註格式統一，四處「約定面試」
# 排程入口（看板/候選人頁快速排程/候選人頁詳細排程/面試管理頁）都呼叫這一個，
# 不再各自兜格式——避免同一個功能在不同頁面長得不一樣（跟結案原因同一種教訓）。
INTERVIEW_ROOM = "會議室_總部-7-2R (6)"

def interview_gcal_link(job_title: str, name: str, start_dt: datetime, duration_min=60) -> str:
    jt = job_title or "未指定職缺"
    return gcal_link(
        f"(2R)面試-{jt}", start_dt, duration_min,
        desc=f"{jt}-{name}",  # 候選人姓名的超連結由使用者自己在Google行事曆貼上
        location=INTERVIEW_ROOM,
    )

def _pending_followups(all_cands, today=None):
    """待催辦清單：卡在「已推薦主管」或「已傳邀約」超過門檻工作日的人。

    2026-08-13 新增。跟 daily_health_check.py 的 build_followup_lines 做同一件事、
    共用 hr_schema.FOLLOWUP_RULES 與 workdays_since，但資料來源不同——健檢讀的是
    原始 Sheets rows（list of list），這裡讀的是 dashboard 已經載入、轉成 dict 的
    all_cands。兩邊各自實作是因為資料形狀不同，但規則跟門檻共用同一份定義，
    不會出現「信裡說卡5天、畫面上說卡3天」這種各算各的情況。

    這份清單以前只活在每天早上的健檢信裡，使用者平常操作是開 dashboard、不是
    回頭翻信——搬到首頁才會真的被每天看到、變成行動，信留著當備援。
    """
    today = today or date.today()
    rows = []
    for c in all_cands:
        flow = c.get("flow_status", "")
        rule = next((r for r in hr_schema.FOLLOWUP_RULES if r[0] == flow), None)
        if not rule:
            continue
        _, who, threshold = rule
        # 推薦日優先（語意最精準：推薦這件事發生在哪天），沒有才退回人才狀態更新日
        basis = (c.get("recommended_at") if flow == "已推薦主管" and c.get("recommended_at")
                 else c.get("stage_updated_at"))
        days = hr_schema.workdays_since(basis, today) if basis else None
        if days is None or days < threshold:
            continue
        target = c.get("recommended_to") if flow == "已推薦主管" else who
        rows.append({
            "days": days, "name": c.get("name") or "(無姓名)",
            "job_name": c.get("job_name", ""), "flow": flow,
            "target": target or who,
        })
    rows.sort(key=lambda r: -r["days"])
    return rows


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
    # 這裡要跟06_員工主檔（到職資料，本來就是per-person）對應，用candidate_id
    cand_map   = {c["candidate_id"]: c for c in all_cands if c.get("candidate_id")}

    # ── 待催辦：放在最上面，這是使用者每天真正會打開來看的頁面 ──────
    # 2026-08-13 新增。原本這份清單只在每天早上的健檢信裡，現在同時顯示在這裡，
    # 信留著當備援（萬一哪天沒開 dashboard）。HR推薦46→主管推進21，55%的流失
    # 卡在主管端，是整條漏斗最大的單一斷點，這份清單就是為了讓「卡太久」被看到。
    _followups = _pending_followups(all_cands, today)
    if _followups:
        st.warning(f"⏰ **待催辦 {len(_followups)} 筆**（超過 3 個工作日沒有進展）")
        for f in _followups:
            st.markdown(
                f"　・**{f['name']}**｜{f['job_name']}｜卡在「{f['flow']}」"
                f"**{f['days']} 個工作日**｜等 {f['target']}"
            )
        st.markdown("---")

    # ── 指標列 ────────────────────────────────────────────────
    # 原本有「在途候選人」（stage not in hired/rejected），但這個定義會把AI
    # 判定不合格、HR根本不會再處理的人也算進去（AI不合格的人只要沒被HR手動
    # 結案，stage還是screening，就被當成「在途」）——數字看起來大卻沒有實際
    # 行動意義，跟下面漏斗的AI合格/HR推薦主管重複，直接拿掉不留半調子版本。
    this_week_ivs = [iv for iv in ivs_joined
                     if parse_dt(iv.get("scheduled_at")) and
                     week_start <= parse_dt(iv["scheduled_at"]).date() <= week_end]
    m2, m3, m4, m5 = st.columns(4)
    m2.metric("待面試",     sum(1 for c in all_cands if c.get("stage") == "interview_scheduled"))
    m3.metric("本週面試",   len(this_week_ivs))
    m4.metric("已錄取",     sum(1 for c in all_cands if c.get("stage") == "hired"))
    m5.metric("開缺數",     sum(1 for j in all_jobs  if j.get("status") == "open"))

    st.markdown("---")

    # ── 招募漏斗：AI初篩→AI合格→HR推薦→主管推進→已面試→已通知 ──────
    # Fable架構審查P2：使用者最想看的關鍵數據。「曾經到達過」用累計判斷
    # （不是「目前正卡在」），已結案的人用「結案前階段」回推，不然一結案
    # 就會從漏斗裡消失，數字對不起來。
    st.markdown(
        '<div style="font-weight:700;font-size:var(--fs-sm);color:var(--p);'
        'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        '🔻 招募漏斗</div>',
        unsafe_allow_html=True,
    )
    _stats = fetch_screening_stats()
    _stage_idx = {sk: i for i, sk in enumerate(STAGE_KEYS)}

    def _ever_reached(c, stage_key):
        stage = c.get("stage")
        if stage == "rejected":
            stage = c.get("prestage") or "screening"
        return _stage_idx.get(stage, 0) >= _stage_idx.get(stage_key, 0)

    _funnel_steps = [
        ("🔍 AI初篩",     _stats["total_screened"]),
        ("✅ AI合格",     _stats["total_passed"]),
        ("👔 HR推薦主管", sum(1 for c in all_cands if _ever_reached(c, "recommended"))),
        ("📨 主管推進",   sum(1 for c in all_cands if _ever_reached(c, "invited"))),
        ("✅ 已面試",     sum(1 for c in all_cands if _ever_reached(c, "interviewed"))),
        ("🎉 已通知",     sum(1 for c in all_cands if c.get("stage") == "hired")),
    ]
    f_cols = st.columns(len(_funnel_steps))
    _prev_n = None
    for col, (label, n) in zip(f_cols, _funnel_steps):
        rate_html = ""
        if _prev_n:
            rate_html = (f'<div style="font-size:var(--fs-xs);color:#94a3b8;">'
                         f'{(n / _prev_n * 100 if _prev_n else 0):.0f}%</div>')
        col.markdown(
            f'<div style="text-align:center;padding:10px 4px;background:var(--surface);'
            f'border-radius:var(--r);border:1px solid var(--border);">'
            f'<div style="font-size:var(--fs-xs);color:#6b7280;font-weight:600;">{label}</div>'
            f'<div style="font-family:var(--font-m);font-size:var(--fs-xl);font-weight:800;'
            f'color:var(--p);">{n}</div>{rate_html}</div>',
            unsafe_allow_html=True,
        )
        _prev_n = n

    st.markdown("---")

    # ── 雙週排程（左：本週｜右：下週）────────────────────────
    def render_week(col, label: str, start: date, end: date):
        col.markdown(
            f'<div style="font-weight:700;font-size:var(--fs-sm);color:var(--p);'
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
                f'padding:3px 10px;margin:8px 0 3px;font-weight:700;font-size:var(--fs-xs);">'
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
                        f'<div><div style="font-weight:600;font-size:var(--fs-sm);color:{ev["color"]};">'
                        f'{_html.escape(ev["title"])}</div>'
                        f'<div style="font-size:var(--fs-xs);color:#64748b;">{_html.escape(ev["sub"])}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
            else:
                col.markdown(
                    '<div style="font-size:var(--fs-xs);color:#94a3b8;padding:2px 8px;">—</div>',
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
        '<div style="font-weight:700;font-size:var(--fs-sm);color:var(--p);'
        'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        '⚡ 待處理事項</div>',
        unsafe_allow_html=True,
    )

    actions = []

    # 在「已面試」超過 3 天仍未決定——用stage_updated_at（進入這個階段的日期），
    # 不是created_at（履歷建檔日期，可能是幾個月前，會把剛面試完的人也誤判成
    # 卡很久，這是找出的一個真bug，跟看板卡片用stage_updated_at顯示日期一致）
    for c in all_cands:
        if c.get("stage") == "interviewed":
            dt = parse_dt(c.get("stage_updated_at"))
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
            h = hires_map.get(str(c.get("candidate_id", "")), {})
            missing = [lbl for k, lbl in OB_CHECKLIST if not h.get(k)]
            if missing:
                actions.append(f'✅ **{c.get("name","?")}** — 到職流程待完成：{" / ".join(missing)}')

    if actions:
        for a in actions:
            st.markdown(
                f'<div style="background:#fffbeb;border-left:3px solid #f59e0b;'
                f'border-radius:0 6px 6px 0;padding:6px 12px;margin-bottom:4px;font-size:var(--fs-sm);">'
                f'{a}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ 目前無待處理事項！")

# ══════════════════════════════════════════════════════════════
# PAGE 2 — 招募看板（以職缺為單位，區塊內按階段並排欄位）
# ══════════════════════════════════════════════════════════════

def page_kanban():
    _col_refresh, _col_rej = st.columns([1, 5])
    with _col_refresh:
        if st.button("🔄 重新整理", key="kb_refresh"):
            _invalidate()
            st.rerun()

    all_cands = fetch_all_candidates()
    all_jobs  = fetch_all_jobs()
    all_hires_kb = fetch_all_hires()
    all_ivs_kb   = fetch_all_interviews()
    # 已通知(hired)且已經標記「實際報到」的人，代表招募任務已完成，不該再
    # 佔招募看板的版面——到職追蹤頁那邊仍然看得到，只是從這裡消失。
    _reported_cids = {h.get("candidate_id") for h in all_hires_kb if h.get("actual_start_date")}
    # 2026-08-14：面試/報到日期 join 給卡片顯示用。「約定面試」跟「已通知」
    # 這兩個階段本來就會等一段時間才輪到（面試通常一到三週後、報到通常兩週
    # 到一個月後），只顯示「卡N個工作日」會誤導成流程卡住——顯示排定日期
    # 才知道「還在等該等的時間」還是「該催了」。
    #   面試：優先用 application_id 對應（唯一），退回 candidate_id（舊資料相容）
    #   報到：06_員工主檔天生是 per-person，用 candidate_id
    _iv_by_appid = {iv.get("application_id"): iv for iv in all_ivs_kb
                    if iv.get("application_id")}
    _iv_by_cid = {iv.get("candidate_id"): iv for iv in all_ivs_kb
                  if iv.get("candidate_id") and not iv.get("application_id")}
    _hire_by_cid = {h.get("candidate_id"): h for h in all_hires_kb
                    if h.get("candidate_id")}

    show_rejected = _col_rej.checkbox("包含已結案候選人", value=False, key="kb_rejected")

    # 並排欄位（104式視覺化，非真拖曳）：每個職缺一個區塊，區塊內每個階段一欄
    BOARD_STAGES = [s for s in STAGES if s[0] in
                    ("recommended", "invited", "interview_scheduled", "interviewed", "offer_pending", "hired")]
    BOARD_KEYS = {s[0] for s in BOARD_STAGES}
    KANBAN_STAGES = BOARD_KEYS | ({"rejected"} if show_rejected else set())

    job_cands: dict[str, list] = {}
    no_job = []
    for c in all_cands:
        if c.get("stage") not in KANBAN_STAGES:
            continue
        if c.get("stage") == "hired" and str(c.get("candidate_id")) in _reported_cids:
            continue
        jid = str(c.get("job_opening_id", "")).strip()
        if jid:
            job_cands.setdefault(jid, []).append(c)
        else:
            no_job.append(c)

    # 所有開缺都列出來（即使目前還沒有人推進到「已推薦主管」以後的階段），
    # 讓HR一眼看出「這個職缺目前完全沒人在跑」，不是只顯示有進度的職缺。
    all_jobs_with_data = [j for j in all_jobs if j.get("status") == "open" or j["id"] in job_cands]
    if no_job:
        all_jobs_with_data.append({"id": "__none__", "title": "（未指定職缺）", "status": "open"})
        job_cands["__none__"] = no_job

    if not all_jobs_with_data:
        st.info("目前無候選人在招募流程中。")
        return

    # P1版面重排（Fable架構審查第2點）：職缺名稱從左側row label改成區塊上方
    # 整寬標題，把原本被它佔掉的一整欄寬度還給6個階段欄；每個階段欄額外用
    # bordered container包起來，卡片才有明確的欄位邊框，不會有「看不出來卡片
    # 屬於哪一欄」的問題。
    st.markdown("""
<style>
[class*="st-key-kb_card"] {
  padding: 10px 10px 11px !important; border-radius: 10px !important; gap: 1.1rem !important;
}
[class*="st-key-kb_card"] [data-testid="stButton"] button {
  padding: 0px 2px !important; border-radius: 6px !important;
  font-size: 0.6rem !important; min-height: 1rem !important;
}
/* 三顆動作按鈕依語意上色，不再全部長一樣的灰色框 */
[class*="st-key-kb_card"] [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stButton"] button {
  border-color: var(--c-accent) !important; color: var(--c-primary) !important;
}
[class*="st-key-kb_card"] [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stButton"] button {
  border-color: var(--c-err-border) !important; color: var(--c-err) !important;
}
[class*="st-key-kb_card"] [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stButton"] button {
  color: var(--c-text-muted) !important;
}
[class*="st-key-kb_job"] {
  padding: 10px 16px !important; border-radius: 12px !important;
}
[class*="st-key-kb_col"] {
  padding: 6px 6px !important; border-radius: 10px !important; background: #fafbfc !important;
}
/* 階段表頭凍結：往下捲動看很多職缺卡片時，標題列固定在畫面頂端。
   Streamlit的st.container(key=...)會多包一層外層div，sticky要設在那層
   外層（用:has()抓），設在st-key-kb_header自己身上因為它是flex子項不會生效。 */
div:has(> [class*="st-key-kb_header"]) {
  position: sticky !important; top: 2.9rem !important; z-index: 999 !important;
  background: var(--c-bg, #ffffff) !important; padding-top: 4px !important; padding-bottom: 4px !important;
}
</style>
""", unsafe_allow_html=True)

    # ── 階段表頭：整頁只出現一次，底下每個職缺共用同一組欄位對齊 ──────
    with st.container(key="kb_header"):
        _hdr_cols = st.columns(len(BOARD_STAGES))
        for _hc, (sk, label, icon, bg, fg) in zip(_hdr_cols, BOARD_STAGES):
            _hc.markdown(
                f'<div style="background:{bg};color:{fg};border-radius:4px;padding:5px 6px;'
                f'font-size:var(--fs-sm);font-weight:800;text-align:center;">{icon} {label}</div>',
                unsafe_allow_html=True,
            )
    st.write("")

    _kb_job_title_map = {j["id"]: j["title"] for j in all_jobs_with_data}

    # ── 共用：渲染單張候選人卡片 ──────────────────────────
    def _kb_card(c, jid, sk):
        cid    = c["id"]
        name   = c.get("name", "?")
        grade  = c.get("grade", "C")
        gm     = GRADE_META.get(grade, ("#f8fafc", "#475569", "#9ca3af", "📋"))
        dt     = parse_dt(c.get("created_at"))
        days   = (datetime.now() - dt).days if dt else 0
        source = c.get("source", "")
        note   = c.get("note", "")
        cur_i  = STAGE_KEYS.index(sk) if sk in STAGE_KEYS else 0
        next_s = [s for s in STAGE_KEYS[cur_i+1:cur_i+2] if s != "rejected"]
        has_rej = sk not in ("hired", "rejected")
        bpfx   = f"kb_{jid}_{sk}_{cid}"

        meta = f"{days}天 · {_html.escape(source)}" if source else f"{days}天"
        # 進入目前階段的日期（M/D），跟在等第徽章旁邊，一眼看出「卡多久了」
        stage_dt = parse_dt(c.get("stage_updated_at"))
        stage_date_txt = f"{stage_dt.month}/{stage_dt.day}" if stage_dt else ""
        # 2026-08-13：光有日期要心算才知道卡多久，直接算成工作日數顯示。這是
        # Opus 建議的「老化清單」在卡片上的最小實作——量體小時，比任何百分比
        # 或趨勢圖都更有行動意義。用 hr_schema.workdays_since 跟健檢信/首頁
        # 待催辦用同一套算法與門檻，三個地方不能出現三個互相矛盾的天數。
        _stage_days = (hr_schema.workdays_since(c.get("stage_updated_at"), date.today())
                       if c.get("stage_updated_at") else None)
        _aging_txt, _aging_color = "", "#94a3b8"
        if _stage_days is not None and sk not in ("hired", "rejected"):
            _aging_txt = f"卡{_stage_days}個工作日" if _stage_days else "今天進入"
            if _stage_days >= hr_schema.CARD_AGING_ALERT_DAYS:
                _aging_color = "#dc2626"  # 超過門檻才用警示色，平時維持中性灰

        # 2026-08-14：約定面試/已通知階段顯示排定日期，取代單純的「卡N個工作日」。
        # 理由：這兩個階段的等待是預期的（面試可能約在兩三週後、報到通常在兩到
        # 四週後），只顯示「卡N個工作日」會被誤讀成流程卡住，而其實是還在等
        # 該等的時間。有排定日期時：改成顯示「面試 M/D」或「報到 M/D」，並用
        # 「還剩N個工作日」取代「卡N個工作日」——同時把老化警示色關掉，因為
        # 「還剩幾天到那個排定日」跟「卡多久沒動」是完全不同的語意。
        _sched_dt = None
        _sched_label = ""
        if sk == "interview_scheduled":
            _iv = _iv_by_appid.get(cid) or _iv_by_cid.get(c.get("candidate_id"))
            if _iv:
                _sched_dt = parse_dt(_iv.get("scheduled_at"))
                _sched_label = "面試"
        elif sk == "hired":
            _h = _hire_by_cid.get(c.get("candidate_id"))
            if _h:
                _sched_dt = parse_dt(_h.get("start_date"))
                _sched_label = "報到"
        if _sched_dt:
            _sched_date = _sched_dt.date()
            _days_until = hr_schema.workdays_since(date.today(), _sched_date)
            _sched_txt = f"{_sched_label} {_sched_dt.month}/{_sched_dt.day}"
            if _days_until is None:
                # 排定日期是過去 → 這才是真的該處理了，維持警示色
                _sched_txt += "（已過）"
                _aging_txt, _aging_color = _sched_txt, "#dc2626"
            elif _days_until == 0:
                _aging_txt, _aging_color = f"{_sched_txt}（今天）", "#dc2626"
            else:
                _aging_txt = f"{_sched_txt}（剩{_days_until}個工作日）"
                _aging_color = "#94a3b8"  # 還在等該等的時間，不算卡住，不上警示色
        with st.container(border=True, key=f"kb_card_{bpfx}"):
            # 姓名+等第：字級拉到 --fs-sm（可讀），允許換行，不再用ellipsis
            # 硬裁字——裁字才是使用者真正在意的「看不到人在哪」的根源。
            # 天數/來源不再佔一整行，改成滑鼠停留在姓名上的title提示。
            st.markdown(
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;" title="{meta}">'
                f'<span style="font-size:var(--fs-base);font-weight:600;line-height:1.6;">'
                f'{_html.escape(name)}</span>'
                f'<span style="display:inline-flex;align-items:center;gap:2px;'
                f'background:{gm[0]};color:{gm[1]};border:1px solid {gm[2]};'
                f'border-radius:4px;font-size:var(--fs-sm);line-height:1.6;'
                f'padding:1px 6px;flex-shrink:0;">'
                f'<span>{gm[3]}</span><span>{grade}</span></span>'
                + (f'<span style="font-size:var(--fs-xs);color:#94a3b8;flex-shrink:0;" '
                   f'title="{STAGE_LABEL.get(sk, "")}進度更新於{stage_date_txt}">{stage_date_txt}</span>'
                   if stage_date_txt else '')
                + (f'<span style="font-size:var(--fs-xs);color:{_aging_color};'
                   f'font-weight:{"700" if _aging_color != "#94a3b8" else "400"};flex-shrink:0;" '
                   f'title="進入「{STAGE_LABEL.get(sk, "")}」已經 {_stage_days} 個工作日">'
                   f'{_aging_txt}</span>'
                   if _aging_txt else '')
                + '</div>',
                unsafe_allow_html=True,
            )

            # 推進/結案/備註三顆動作並排一行，卡片只剩兩行（手繪稿版型）
            if sk == "hired":
                bc1, bc2, bc3 = st.columns([2, 1, 1])
                if bc1.button("→ 到職追蹤", key=f"{bpfx}_goto_onboard", use_container_width=True):
                    st.session_state['_pending_nav'] = "✅ 到職流程"
                    st.session_state['_onboard_focus_cid'] = cid
                    st.rerun()
                with bc2:
                    if st.button("備" + ("●" if note else ""), key=f"{bpfx}_note_toggle",
                                 help=note if note else "新增備註", use_container_width=True):
                        st.session_state[f"{bpfx}_note_open"] = not st.session_state.get(f"{bpfx}_note_open", False)
                with bc3:
                    if st.button("⇅", key=f"{bpfx}_jump_toggle", help="跳到其他階段",
                                 use_container_width=True):
                        st.session_state[f"jump_open_{cid}"] = not st.session_state.get(f"jump_open_{cid}", False)
            else:
                bc1, bc2, bc3, bc4 = st.columns(4)
                _next_is_interview = bool(next_s) and next_s[0] == "interview_scheduled"
                if next_s:
                    if bc1.button("→", key=f"{bpfx}_{next_s[0]}", use_container_width=True,
                                  help=f"推進到「{STAGE_LABEL[next_s[0]]}」"):
                        if _next_is_interview:
                            # 使用者反饋：推進到「約定面試」卻沒有順便問哪天面試，
                            # 流程狀態變了但05_面試主檔沒有對應紀錄，之後行事曆也
                            # 看不到——改成推進前先問日期/時間，一次填完不斷資料。
                            # 用cid（application_id）當key而不是bpfx：確認排定後
                            # 這張卡會移到下一個階段欄、bpfx跟著換，用cid才能在
                            # 新位置繼續找到「加入Google行事曆」連結。
                            st.session_state[f"iv_open_{cid}"] = True
                            st.rerun()
                        elif update_stage(cid, next_s[0]):
                            st.toast(f"✅ {name} → {STAGE_LABEL[next_s[0]]}")
                            st.rerun()
                if has_rej:
                    if bc2.button("✕", key=f"{bpfx}_rejected", use_container_width=True, help="結案"):
                        # 結案原因（2026-07-23新增）：以前結案完全沒記原因，事後
                        # 完全查不出來為什麼結案，用cid當key因為結案後卡片會消失/
                        # 移動，用application_id才穩定。
                        st.session_state[f"close_open_{cid}"] = True
                        st.rerun()
                if bc3.button("備" + ("●" if note else ""), key=f"{bpfx}_note_toggle",
                              use_container_width=True, help=note if note else "新增備註"):
                    st.session_state[f"{bpfx}_note_open"] = not st.session_state.get(f"{bpfx}_note_open", False)
                if bc4.button("⇅", key=f"{bpfx}_jump_toggle", help="跳到其他階段",
                              use_container_width=True):
                    st.session_state[f"jump_open_{cid}"] = not st.session_state.get(f"jump_open_{cid}", False)

            # 「跳到其他階段」：2026-08-13 新增，解決「→」只能一步步往前推的
            # 限制——這個月使用者已經兩次因為卡片推錯階段/在約定面試就誤結案，
            # 得工程端寫腳本改 Sheets 才修回來。往後跳（退回）要求填原因寫進
            # 備註；跳進「約定面試」沿用既有的 iv_open_{cid} 問日期流程；跳到
            # 其他任何階段（包含直接跳「已面試」——門市店長自己約自己面完，
            # 不走系統排的面試）不強制問日期，維持使用者已經拍板的決定：
            # 「不用做預估日期標記，跟以前一樣就好」。
            if st.session_state.get(f"jump_open_{cid}"):
                _jump_options = [s for s in STAGE_KEYS if s not in ("rejected", sk)]
                _jump_labels = {s: STAGE_LABEL.get(s, s) for s in _jump_options}
                _jump_sel = st.selectbox(
                    "跳到", _jump_options, format_func=lambda s: _jump_labels[s],
                    key=f"{bpfx}_jump_target", label_visibility="collapsed",
                )
                _jump_target_i = STAGE_KEYS.index(_jump_sel) if _jump_sel in STAGE_KEYS else cur_i
                _is_backward = _jump_target_i < cur_i
                _jump_reason = ""
                if _is_backward:
                    _jump_reason = st.text_input(
                        "退回原因（必填）", key=f"{bpfx}_jump_reason",
                        placeholder="例如：按錯了、其實還沒面試",
                    )
                if st.button("確認跳轉", key=f"{bpfx}_jump_confirm", type="primary"):
                    if _is_backward and not _jump_reason.strip():
                        st.warning("退回階段要先填原因，才知道之後為什麼卡在這裡。")
                    elif _jump_sel == "interview_scheduled":
                        st.session_state[f"jump_open_{cid}"] = False
                        st.session_state[f"iv_open_{cid}"] = True
                        st.rerun()
                    else:
                        _ok = True
                        if _is_backward:
                            _stamp = date.today().strftime('%m/%d')
                            _new_note = (f"{note}\n" if note else "") + (
                                f"[退回 {STAGE_LABEL.get(sk, sk)}→{_jump_labels[_jump_sel]} "
                                f"{_stamp}] 原因：{_jump_reason.strip()}"
                            )
                            _ok = update_note(cid, _new_note)
                        if _ok and update_stage(cid, _jump_sel):
                            st.session_state[f"jump_open_{cid}"] = False
                            st.toast(f"✅ {name} → {_jump_labels[_jump_sel]}")
                            st.rerun()

            if st.session_state.get(f"{bpfx}_note_open"):
                new_note = st.text_area("備註", value=note, key=f"{bpfx}_note_ta", label_visibility="collapsed")
                if st.button("儲存", key=f"{bpfx}_note_save"):
                    if update_note(cid, new_note):
                        st.session_state[f"{bpfx}_note_open"] = False
                        st.toast(f"✅ {name} 備註已更新")
                        st.rerun()

            if st.session_state.get(f"iv_open_{cid}"):
                iv_d = st.date_input("面試日期", value=datetime.now().date(), key=f"{bpfx}_iv_date")
                iv_t = st.time_input("面試時間", value=datetime(2024, 1, 1, 10, 0).time(), key=f"{bpfx}_iv_time")
                iv_itvr = st.text_input("面試官（可留空）", key=f"{bpfx}_iv_itvr")
                if st.button("確認排定", key=f"{bpfx}_iv_confirm", type="primary"):
                    sdt = datetime.combine(iv_d, iv_t)
                    if update_stage(cid, "interview_scheduled") and save_interview({
                        "candidate_id": c.get("candidate_id", ""), "application_id": cid,
                        "job_id": c.get("job_opening_id", ""), "name": name,
                        "scheduled_at": sdt.isoformat(), "interviewer": iv_itvr, "result": "pending",
                    }):
                        st.session_state[f"iv_open_{cid}"] = False
                        st.session_state[f"iv_link_{cid}"] = interview_gcal_link(
                            _kb_job_title_map.get(jid, ""), name, sdt)
                        st.toast(f"✅ {name} → 約定面試")
                        st.rerun()
            if st.session_state.get(f"iv_link_{cid}"):
                st.link_button("📅 加入 Google 行事曆", st.session_state[f"iv_link_{cid}"],
                                use_container_width=True)

            if st.session_state.get(f"close_open_{cid}"):
                close_reason = st.selectbox("結案原因", CLOSE_REASONS, key=f"{bpfx}_close_reason")
                if st.button("確認結案", key=f"{bpfx}_close_confirm", type="primary"):
                    if update_stage(cid, "rejected", close_reason=close_reason):
                        st.session_state[f"close_open_{cid}"] = False
                        st.toast(f"{name} 已結案（{close_reason}）")
                        st.rerun()

    _EMPTY_SLOT = (
        '<div style="border:1.5px dashed #e2e8f0;border-radius:8px;min-height:56px;'
        'display:flex;align-items:center;justify-content:center;color:#cbd5e1;'
        'font-size:var(--fs-xs);">—</div>'
    )
    for job in all_jobs_with_data:
        jid    = job["id"]
        jtitle = job["title"]
        jcands = job_cands.get(jid, [])
        active = [c for c in jcands if c.get("stage") in BOARD_KEYS]
        rejected_list = [c for c in jcands if c.get("stage") == "rejected"]

        with st.container(border=True, key=f"kb_job_{jid}"):
            # 職缺名稱改成整寬標題（不再擠左側一欄），6個階段欄拿回原本被
            # row label佔掉的寬度。
            st.markdown(
                f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
                f'<span style="font-weight:800;font-size:var(--fs-lg);">{_html.escape(jtitle)}</span>'
                f'<span style="font-size:var(--fs-sm);font-weight:600;color:#6b7280;">{len(active)} 人</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            cols = st.columns(len(BOARD_STAGES))
            for i, (sk, label, icon, bg, fg) in enumerate(BOARD_STAGES):
                with cols[i]:
                    stage_list = [c for c in active if c.get("stage") == sk]
                    with st.container(border=True, key=f"kb_col_{jid}_{sk}"):
                        # 每欄頂端一個對應階段色的計數色塊，卡片跟欄位的歸屬
                        # 靠「垂直對齊表頭」+「顏色」雙重編碼，不用再看row label。
                        st.markdown(
                            f'<div style="background:{bg};color:{fg};border-radius:999px;'
                            f'padding:2px 0;text-align:center;font-weight:800;'
                            f'font-size:var(--fs-xs);margin-bottom:6px;">{len(stage_list)}</div>',
                            unsafe_allow_html=True,
                        )
                        if not stage_list:
                            st.markdown(_EMPTY_SLOT, unsafe_allow_html=True)
                            continue
                        for c in stage_list:
                            _kb_card(c, jid, sk)
            if show_rejected and rejected_list:
                with st.expander(f"已結案（{len(rejected_list)}）", expanded=False):
                    for c in rejected_list:
                        _kb_card(c, jid, "rejected")

# ══════════════════════════════════════════════════════════════
# PAGE 3 — 候選人
# ══════════════════════════════════════════════════════════════
def page_candidates():
    all_jobs  = fetch_all_jobs()
    all_cands = _candidates_with_join(fetch_all_candidates(), all_jobs)

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

    # 定位宣言（Fable架構審查）：資料全留（人才庫，一筆都不刪），但畫面預設
    # 只給合格/進行中的人看——不合格/已結案/職缺已關閉的人要「主動打開」
    # 才看得到，不是預設就把804筆全部倒出來。這三個checkbox預設關閉。
    f5, f6, f7 = st.columns(3)
    show_ai_reject   = f5.checkbox("包含AI不合格（淘汰名單）", value=False, key="c_show_reject")
    show_closed      = f6.checkbox("包含已結案候選人", value=False, key="c_show_closed")
    show_closed_jobs = f7.checkbox("包含已關閉職缺的候選人", value=False, key="c_show_closed_jobs")

    # Apply filters
    job_status_map = {j["id"]: j.get("status") for j in all_jobs}
    rows = all_cands
    if not show_ai_reject:
        rows = [c for c in rows if c.get("screening_result") != "不合格"]
    if not show_closed:
        rows = [c for c in rows if c.get("stage") != "rejected"]
    # 選了特定職缺時尊重使用者的明確選擇，不套用「排除已關閉職缺」——
    # 那是「全部職缺」情境下避免捲一堆已經沒人要處理的候選人才需要的預設值。
    if not show_closed_jobs and not sel_jid:
        rows = [c for c in rows
                if job_status_map.get(str(c.get("job_opening_id", "")), "open") != "closed"]
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
            _render_candidate_card(c, all_jobs)

    st.caption("💡 初篩結果會在篩選完成後自動同步至 Google Sheets，無需手動匯入。")

def _render_candidate_card(c: dict, all_jobs: list):
    cid    = c["id"]              # application_id
    pcid   = c["candidate_id"]    # candidate_id（面試紀錄的人員欄位要用這個）
    grade  = c.get("grade", "?")
    stage  = c.get("stage", "screening")
    name   = c.get("name", "?")
    code   = str(c.get("code_104") or "—")
    stab   = c.get("stability", "")
    jtitle = c.get("_job_title", "")
    stab_color = {"高": "#15803d", "中": "#92400e", "低": "#b91c1c"}.get(stab, "#64748b")
    cur_idx = STAGE_KEYS.index(stage) if stage in STAGE_KEYS else 0

    with st.container(border=True, key=f"card_stage_{cid}"):
        cg, ci, cs, ca = st.columns([0.6, 3.5, 1.5, 2])
        cg.markdown(grade_badge(grade), unsafe_allow_html=True)
        ci.markdown(
            f'<div style="font-weight:700;font-size:var(--fs-base);">{_html.escape(name)}'
            f'<span style="font-weight:400;color:#64748b;font-size:var(--fs-xs);margin-left:8px;">'
            f'#{_html.escape(code)} · {_html.escape(jtitle)}</span></div>'
            f'<div style="font-size:var(--fs-xs);color:#64748b;margin-top:2px;">'
            f'穩定度：<span style="color:{stab_color};font-weight:600;">{_html.escape(stab)}</span>'
            f' · {_html.escape((c.get("commute") or "")[:40])}</div>',
            unsafe_allow_html=True,
        )
        cs.markdown(stage_badge(stage), unsafe_allow_html=True)
        with ca:
            # 只給下一步（不是下兩步）、遇到interview_scheduled要先問日期，
            # 跟看板的_kb_card同一套規則——這裡原本可以直接跳兩步、繞過看板
            # 那邊「推進到約定面試先問日期」的保護，同一人在不同頁面推進
            # 規則不一致，且會漏開05_面試主檔紀錄。
            next_s = [s for s in STAGE_KEYS[cur_idx+1:cur_idx+2] if s != "rejected"]
            for ns in next_s:
                if st.button(f"→ {STAGE_LABEL[ns]}", key=f"fwd_{cid}_{ns}", use_container_width=True):
                    if ns == "interview_scheduled":
                        st.session_state[f"iv_open_{cid}"] = True
                        st.rerun()
                    elif update_stage(cid, ns):
                        st.toast(f"✅ {name} → {STAGE_LABEL[ns]}")
                        st.rerun()
            if stage not in ("rejected", "hired"):
                if st.button("❌ 結案", key=f"rej_{cid}", use_container_width=True):
                    st.session_state[f"close_open_{cid}"] = True
                    st.rerun()

        if st.session_state.get(f"close_open_{cid}"):
            close_reason = st.selectbox("結案原因", CLOSE_REASONS, key=f"cand_close_reason_{cid}")
            if st.button("確認結案", key=f"cand_close_confirm_{cid}", type="primary"):
                if update_stage(cid, "rejected", close_reason=close_reason):
                    st.session_state[f"close_open_{cid}"] = False
                    st.toast(f"{name} 已結案（{close_reason}）")
                    st.rerun()

        if st.session_state.get(f"iv_open_{cid}"):
            iv_d = st.date_input("面試日期", value=datetime.now().date(), key=f"cand_iv_date_{cid}")
            iv_t = st.time_input("面試時間", value=datetime(2024, 1, 1, 10, 0).time(), key=f"cand_iv_time_{cid}")
            iv_itvr = st.text_input("面試官（可留空）", key=f"cand_iv_itvr_{cid}")
            if st.button("確認排定", key=f"cand_iv_confirm_{cid}", type="primary"):
                sdt = datetime.combine(iv_d, iv_t)
                if update_stage(cid, "interview_scheduled") and save_interview({
                    "candidate_id": pcid, "application_id": cid,
                    "job_id": c.get("job_opening_id", ""), "name": name,
                    "scheduled_at": sdt.isoformat(), "interviewer": iv_itvr, "result": "pending",
                }):
                    st.session_state[f"iv_open_{cid}"] = False
                    st.session_state[f"iv_link_{cid}"] = interview_gcal_link(jtitle, name, sdt)
                    st.toast(f"✅ {name} → 約定面試")
                    st.rerun()
        if st.session_state.get(f"iv_link_{cid}"):
            st.link_button("📅 加入 Google 行事曆", st.session_state[f"iv_link_{cid}"],
                            use_container_width=True)

        with st.expander("詳細 / 快速安排面試", expanded=False):
            dc1, dc2 = st.columns(2)
            dc1.markdown(
                f'<div style="background:var(--ok-bg);border:1px solid var(--ok-bd);'
                f'border-radius:6px;padding:8px 10px;font-size:var(--fs-sm);">'
                f'<b style="color:var(--ok);">✨ 戰功亮點</b><br>'
                f'{_html.escape(c.get("highlights") or "—")}</div>',
                unsafe_allow_html=True,
            )
            dc2.markdown(
                f'<div style="background:var(--err-bg);border:1px solid var(--err-bd);'
                f'border-radius:6px;padding:8px 10px;font-size:var(--fs-sm);">'
                f'<b style="color:var(--err);">⚠️ 缺口地雷</b><br>'
                f'{_html.escape(c.get("gaps") or "—")}</div>',
                unsafe_allow_html=True,
            )
            if c.get("screening_notes"):
                st.caption(f"初篩備注：{c['screening_notes']}")

            if stage in ("screening", "invited", "interview_scheduled"):
                st.markdown("**快速安排面試**")
                qs1, qs2, qs3 = st.columns(3)
                iv_date = qs1.date_input("日期", value=date.today() + timedelta(days=3), key=f"qd_{cid}")
                iv_time = qs2.time_input("時間", value=datetime(2024,1,1,10,0).time(), key=f"qt_{cid}")
                iv_itvr = qs3.text_input("面試官", key=f"qi_{cid}")
                iv_loc  = st.text_input("地點", value=INTERVIEW_ROOM, key=f"ql_{cid}")
                if st.button("確認安排", key=f"qsched_{cid}", type="primary"):
                    sdt = datetime.combine(iv_date, iv_time)
                    if save_interview({"candidate_id": pcid, "application_id": cid,
                                       "scheduled_at": sdt.isoformat(),
                                       "duration_minutes": 60, "interviewer": iv_itvr,
                                       "location": iv_loc, "result": "pending"}):
                        update_stage(cid, "interview_scheduled")
                        link = interview_gcal_link(jtitle, name, sdt)
                        st.success("✅ 面試已安排！")
                        st.link_button("📅 加入 Google 行事曆", link)
                        st.rerun()

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
            f'<div style="font-size:var(--fs-2xs);font-weight:600;color:{lbl_fg};'
            f'text-transform:uppercase;letter-spacing:.04em;">週{WD_ZH[d.weekday()]}</div>'
            f'<div style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:30px;height:30px;border-radius:50%;background:{num_bg};'
            f'font-size:var(--fs-base);font-weight:800;color:{num_fg};margin-top:1px;">'
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
            f'font-size:var(--fs-2xs);color:#9ca3af;font-family:monospace;">'
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
                f'<div style="font-weight:700;font-size:var(--fs-xs);color:{ev["color"]};'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'{_html.escape(ev["title"])}</div>'
                + (f'<div style="font-size:var(--fs-2xs);color:#475569;white-space:nowrap;'
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
    today_d = date.today()

    ev_by_day: dict[date, list] = {}
    for ev in events:
        ev_by_day.setdefault(ev["date"], []).append(ev)

    weeks = _cal.Calendar(firstweekday=0).monthdatescalendar(year, month)

    html = ('<div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;'
            'font-family:sans-serif;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.06);">')

    # Day-of-week header
    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);background:#f8fafc;border-bottom:2px solid #e2e8f0;">'
    for i, wd in enumerate(WD_ZH):
        c = "#94a3b8" if i >= 5 else "#6b7280"
        html += (f'<div style="text-align:center;padding:8px 4px;font-size:var(--fs-xs);'
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
                f'font-size:var(--fs-sm);font-weight:{"800" if is_today else "600"};color:{num_fg};">'
                f'{d.day}</div></div>'
            )
            for ev in evs[:3]:
                t_lbl = "🎉" if ev["time"] == "全天" else ev["time"]
                html += (
                    f'<div title="{_html.escape(ev["title"])}" '
                    f'style="background:{ev["bg"]};border-left:3px solid {ev["border"]};'
                    f'border-radius:0 3px 3px 0;padding:1px 4px;margin-bottom:2px;'
                    f'font-size:var(--fs-2xs);font-weight:600;color:{ev["color"]};'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{t_lbl} {_html.escape(ev["title"])}</div>'
                )
            if len(evs) > 3:
                html += f'<div style="font-size:var(--fs-2xs);color:#64748b;padding:0 4px;">+{len(evs)-3} 筆</div>'
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
    # _build_cal_events 用candidate_id對06_員工主檔的報到日，這裡要用candidate_id當key
    cand_map  = {c["candidate_id"]: c for c in all_cands if c.get("candidate_id")}
    job_map   = {j["id"]: j["title"] for j in all_jobs}
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
                        if c.get("stage") in ("screening", "invited", "interview_scheduled")]
            if not eligible:
                st.info("目前無可安排面試的候選人。")
            else:
                opts = {f"{c['name']} — {job_map.get(str(c.get('job_opening_id','')),'')}": c
                        for c in eligible}
                sel_c = opts[st.selectbox("候選人", list(opts.keys()), key="cal_cand")]
                sc1, sc2, sc3 = st.columns(3)
                iv_date = sc1.date_input("日期", value=today + timedelta(days=3), key="cal_d")
                iv_time = sc2.time_input("時間", value=datetime(2024,1,1,10,0).time(), key="cal_t")
                iv_dur  = sc3.number_input("時長(分)", value=60, step=15, key="cal_dur")
                sc4, sc5 = st.columns(2)
                iv_itvr = sc4.text_input("面試官", key="cal_itvr")
                iv_loc  = sc5.text_input("地點", value=INTERVIEW_ROOM, key="cal_loc")
                iv_note = st.text_area("備注", key="cal_note")
                if st.button("確認安排", type="primary", key="cal_sched"):
                    sdt = datetime.combine(iv_date, iv_time)
                    if save_interview({
                        "candidate_id": sel_c["candidate_id"], "application_id": sel_c["id"],
                        "scheduled_at": sdt.isoformat(),
                        "duration_minutes": int(iv_dur), "interviewer": iv_itvr,
                        "location": iv_loc, "notes": iv_note, "result": "pending",
                    }):
                        update_stage(sel_c["id"], "interview_scheduled")
                        sel_jtitle = job_map.get(str(sel_c.get("job_opening_id", "")), "")
                        link = interview_gcal_link(sel_jtitle, sel_c["name"], sdt, int(iv_dur))
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

        opts2 = {f"{c['name']} — {job_map.get(str(c.get('job_opening_id','')),'')}": c
                 for c in eligible2}
        sel_c2 = opts2[st.selectbox("選擇候選人", list(opts2.keys()), key="sc_cand")]
        cid2   = sel_c2["id"]              # application_id
        pcid2  = sel_c2["candidate_id"]    # candidate_id（面試紀錄的人員欄位要用這個）

        # 既有記錄：優先用application_id比對，舊面試紀錄沒有application_id時才退回candidate_id
        existing = [iv for iv in all_ivs
                    if str(iv.get("application_id","")) == str(cid2)
                    or (not iv.get("application_id") and str(iv.get("candidate_id","")) == str(pcid2))]
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
                    f'border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:var(--fs-sm);">'
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

        result_opts = {"pending (待定)": "pending", "pass (通過)": "pass",
                       "fail (未通過)": "fail", "no_show (面試未到)": "no_show"}
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
                payload["candidate_id"] = pcid2
                payload["application_id"] = cid2
                payload["scheduled_at"] = datetime.now().isoformat()
            if save_interview(payload):
                if sel_res == "pass":
                    update_stage(cid2, "interviewed")
                    st.success(f"✅ 記分卡已儲存！{sel_c2['name']} → 已面試（通過）")
                elif sel_res == "fail":
                    update_stage(cid2, "rejected")
                    st.success(f"✅ 記分卡已儲存！{sel_c2['name']} → 已結案（未通過）")
                elif sel_res == "no_show":
                    # 沒出席就沒被評估過，不推進到「已面試」，也不自動結案——
                    # 改期再約還是直接結案是HR的判斷，程式不要幫忙決定。
                    st.success(f"✅ 記分卡已儲存！{sel_c2['name']} → 面試未到"
                               "（流程狀態不變，要改期或結案請自行操作）")
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

    # 從招募看板「→ 到職追蹤」按鈕跳轉過來時，把該候選人排到最前面並提示
    _focus_cid = st.session_state.pop('_onboard_focus_cid', None)
    if _focus_cid:
        _focus_name = next((c.get("name", "?") for c in target_cands if c["id"] == _focus_cid), None)
        if _focus_name:
            st.info(f"🔎 已定位到「{_focus_name}」")
            target_cands = (
                [c for c in target_cands if c["id"] == _focus_cid]
                + [c for c in target_cands if c["id"] != _focus_cid]
            )

    for c in target_cands:
        cid     = c["id"]              # application_id：這筆「錄取這個職缺」的應徵紀錄
        pcid    = c["candidate_id"]    # candidate_id：到職資料（06_員工主檔）是per-person，不是per-application
        name    = c.get("name", "?")
        stage   = c.get("stage", "")
        jtitle  = job_map.get(str(c.get("job_opening_id", "")), "")
        h       = hires_map.get(str(pcid), {})
        done_n  = sum(1 for key, _ in CHECKLIST if h.get(key))
        total_n = len(CHECKLIST)

        with st.container(border=True, key=f"card_hire_{cid}"):
            hc1, hc2 = st.columns([4, 2])
            hc1.markdown(
                f'<div style="font-weight:700;font-size:var(--fs-base);">{_html.escape(name)}'
                f'<span style="color:#64748b;font-size:var(--fs-sm);margin-left:8px;">{_html.escape(jtitle)}</span></div>'
                f'<div style="font-size:var(--fs-xs);margin-top:2px;">'
                + stage_badge(stage) + '</div>',
                unsafe_allow_html=True,
            )
            prog_color = "#15803d" if done_n == total_n else "#1e40af"
            hc2.markdown(
                f'<div style="text-align:right;font-weight:700;color:{prog_color};font-size:var(--fs-lg);">'
                f'{done_n}/{total_n} 完成</div>'
                f'<div style="background:#e2e8f0;border-radius:99px;height:6px;margin-top:4px;">'
                f'<div style="background:{prog_color};width:{int(done_n/total_n*100)}%;'
                f'height:6px;border-radius:99px;"></div></div>',
                unsafe_allow_html=True,
            )

            # Checklist items（P1：9個等寬欄位在標準螢幕寬度下會換行擠壓，
            # 改成每列3欄的3x3網格，checkbox跟文字不再擠在一起）
            changed = False
            new_h = dict(h)
            for row_start in range(0, total_n, 3):
                row_items = CHECKLIST[row_start:row_start + 3]
                check_cols = st.columns(3)
                for col, (key, label) in zip(check_cols, row_items):
                    current = bool(h.get(key))
                    checked = col.checkbox(label, value=current, key=f"ob_{cid}_{key}")
                    if checked != current:
                        new_h[key] = checked
                        changed = True

            if changed:
                new_h["candidate_id"] = pcid
                if save_hire(new_h):
                    # 所有勾完 → 自動升為 hired
                    all_done = all(new_h.get(k) for k, _ in CHECKLIST)
                    if all_done and stage != "hired":
                        update_stage(cid, "hired")
                        st.toast(f"🎉 {name} 所有流程完成，已標記為入職！")
                    st.rerun()

            # 已通知的人不會自動從招募看板消失（看板只知道stage，不知道人
            # 有沒有真的來上班）——這裡讓HR確認「已報到」後才把人從招募
            # 看板移除，到職追蹤這邊仍然留著繼續看。
            if stage == "hired":
                if h.get("actual_start_date"):
                    st.caption(f"✅ 已報到（{h['actual_start_date']}），已從招募看板移除")
                else:
                    if st.button("✅ 標記已報到（從招募看板移除）", key=f"ob_{cid}_actual_start"):
                        new_h2 = dict(h)
                        new_h2["candidate_id"] = pcid
                        new_h2["actual_start_date"] = date.today().isoformat()
                        if save_hire(new_h2):
                            st.toast(f"✅ {name} 已標記報到")
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
                        "candidate_id":    pcid,
                        "employment_type": emp_type,
                        "proposed_salary": salary,
                        "start_date":      start_date.isoformat(),
                    })
                    if save_hire(new_h2):
                        st.success("✅ 已儲存！")
                        st.rerun()

            # 留任 / 考核追蹤：招募→留任回饋迴路（E），日後才能回頭檢視
            # AI評分準不準、哪個評分維度真的預測留任——樣本要到職滿三個月
            # 以上才有意義，所以現在就要開始留存，即使暫時還沒有分析工具。
            with st.expander("🎯 留任 / 考核追蹤", expanded=False):
                _RETAIN_EVAL  = ["尚未到期", "通過", "不通過", "待觀察"]
                _PROBATION    = ["待定", "通過", "不通過"]
                _LEAVE_REASON = ["", "自願離職", "資遣", "試用期未過", "其他"]
                rc1, rc2 = st.columns(2)
                eval_result = rc1.selectbox(
                    "三個月考核結果", _RETAIN_EVAL,
                    index=_RETAIN_EVAL.index(h.get("三個月考核結果"))
                    if h.get("三個月考核結果") in _RETAIN_EVAL else 0,
                    key=f"ob_eval_{cid}")
                probation = rc2.selectbox(
                    "試用期通過", _PROBATION,
                    index=_PROBATION.index(h.get("試用期通過"))
                    if h.get("試用期通過") in _PROBATION else 0,
                    key=f"ob_prob_{cid}")
                rc3, rc4 = st.columns(2)
                _leave_val = None
                if h.get("離職日"):
                    try:
                        _leave_val = date.fromisoformat(str(h["離職日"])[:10])
                    except Exception:
                        pass
                leave_date = rc3.date_input("離職日（未離職留空）", value=_leave_val,
                                            key=f"ob_leave_{cid}")
                leave_reason = rc4.selectbox(
                    "離職原因類別", _LEAVE_REASON,
                    index=_LEAVE_REASON.index(h.get("離職原因類別"))
                    if h.get("離職原因類別") in _LEAVE_REASON else 0,
                    key=f"ob_leavereason_{cid}")
                if st.button("儲存留任追蹤資訊", key=f"ob_retain_save_{cid}"):
                    new_h3 = dict(h)
                    new_h3.update({
                        "candidate_id":   pcid,
                        "三個月考核結果": eval_result,
                        "試用期通過":     probation,
                        "離職日":         leave_date.isoformat() if leave_date else "",
                        "離職原因類別":   leave_reason,
                    })
                    if save_hire(new_h3):
                        st.success("✅ 已儲存！")
                        st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE 6 — 分析報表
# ══════════════════════════════════════════════════════════════
def _manager_response_stats(all_cands):
    """各主管：被推薦人數／已回應人數／平均回應天數（工作日）。

    2026-08-13 新增，抽成獨立函式方便測試——inline 在 page_analytics 裡時
    曾經真的算錯過一次：回應天數誤傳成「回應日→今天」，變成跟老化天數
    算同一件事，不是「主管花了幾天回應」，這種邏輯錯誤只靠字串比對測試
    抓不到，要能真正塞資料進去跑過一次才能守住。

    回應天數＝推薦日（recommended_at）→ 離開「已推薦主管」那一刻
    （stage_updated_at）的工作日數，不是到今天為止的天數——回應快但之後
    很久沒再往下走的人，不該被算成回應很慢。
    """
    _recommended = [c for c in all_cands if c.get("recommended_to")]
    _mgr_stats = {}
    for c in _recommended:
        mgr = c.get("recommended_to") or "(未填)"
        row = _mgr_stats.setdefault(mgr, {"推薦": 0, "回應": 0, "天數合計": 0})
        row["推薦"] += 1
        if c.get("flow_status") != "已推薦主管":
            _respond_dt = parse_dt(c.get("stage_updated_at"))
            if c.get("recommended_at") and _respond_dt:
                days = hr_schema.workdays_since(c.get("recommended_at"), _respond_dt.date())
                if days is not None:
                    row["回應"] += 1
                    row["天數合計"] += days
    rows = []
    for mgr, s in sorted(_mgr_stats.items(), key=lambda x: -x[1]["推薦"]):
        avg_days = round(s["天數合計"] / s["回應"], 1) if s["回應"] else None
        rows.append({
            "主管": mgr, "被推薦人數": s["推薦"], "已回應人數": s["回應"],
            "平均回應天數（工作日）": avg_days,
        })
    return rows, len(_recommended)


def _job_pipeline_inventory(all_cands, all_jobs, all_hires):
    """各開缺：開缺天數／管道人數，並標出管道 0 人的職缺。

    2026-08-13 新增，同樣抽成獨立函式方便測試——inline 版本第一次跑出來時
    「管道人數」把還卡在 screening（AI判不合格、HR從沒處理過）的人也算
    進去，單一職缺算出158人，但看板上同一個職缺實際只有7人在跑流程。
    """
    _reported_cids = {h.get("candidate_id") for h in all_hires if h.get("actual_start_date")}
    _pipeline_by_job = {}
    for c in all_cands:
        # 只算「已離開初篩」的人——跟 page_overview 拿掉「在途候選人」指標
        # 是同一個理由：stage=="screening" 大量是沒人會再處理的人。
        if c.get("stage") in ("screening", "rejected"):
            continue
        # 已報到的人是完成的結果，不是還在跑的流程，跟看板頁用同一個定義。
        if c.get("stage") == "hired" and str(c.get("candidate_id")) in _reported_cids:
            continue
        jid = c.get("job_opening_id", "")
        _pipeline_by_job[jid] = _pipeline_by_job.get(jid, 0) + 1

    rows = []
    for j in all_jobs:
        if j.get("status") != "open":
            continue
        jdt = parse_dt(j.get("created_at"))
        open_days = (date.today() - jdt.date()).days if jdt else None
        n_pipeline = _pipeline_by_job.get(j["id"], 0)
        rows.append({
            "職缺": j.get("title", "") or j["id"], "開缺天數": open_days,
            "管道人數": n_pipeline, "缺口": n_pipeline == 0,
        })
    rows.sort(key=lambda r: (r["管道人數"], -(r["開缺天數"] or 0)))
    return rows


def page_analytics():
    if not HAS_PLOTLY:
        st.warning("請安裝 plotly：`pip install plotly`")
        return

    all_cands = fetch_all_candidates()
    all_ivs   = fetch_all_interviews()
    all_hires = fetch_all_hires()
    all_jobs  = fetch_all_jobs()

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
    # 06_員工主檔有兩個報到日期，語意完全不同，混用一次就會像 2026-08-12 那樣
    # 顯示 0（八月真的報到2人，但他們的「預計報到日」是七月填的，不在八月）：
    #   start_date        = 預計報到日（錄取時填的計畫值，可能還沒到、也可能沒實現）
    #   actual_start_date = 實際報到日（真的來上班了才有值）
    # 「本期報到人數」問的是「這個月真的有幾個人來上班」→ 必須用 actual_start_date。
    hires_f     = [h for h in all_hires if in_range(h, "start_date")]
    onboarded_f = [h for h in all_hires
                   if h.get("actual_start_date") and in_range(h, "actual_start_date")]

    # 「曾經到達過」用累計判斷，已結案的人用「結案前階段」（prestage）回推
    # 走到哪一步——跟page_overview的_ever_reached同一套邏輯，否則已結案的
    # 人在這裡完全被排除，跟總覽頁的漏斗數字對不起來（使用者實際回報的落差）。
    _stage_idx = {sk: i for i, sk in enumerate(STAGE_KEYS)}

    def _ever_reached(c, stage_key):
        stage = c.get("stage")
        if stage == "rejected":
            stage = c.get("prestage") or "screening"
        return _stage_idx.get(stage, 0) >= _stage_idx.get(stage_key, 0)

    # 面試通過/報到看的是「這個人最終有沒有」，不是「這段期間內發生的事件」，
    # 所以join全量all_ivs/all_hires（不用ivs_f/hires_f那種依事件時間篩選的清單）。
    _pass_app_ids  = {iv.get("application_id") for iv in all_ivs
                       if iv.get("result") == "pass" and iv.get("application_id")}
    _pass_cand_ids = {iv.get("candidate_id") for iv in all_ivs
                       if iv.get("result") == "pass" and iv.get("candidate_id")}
    _onboarded_cids = {h.get("candidate_id") for h in all_hires if h.get("actual_start_date")}

    def _interview_passed(c):
        return c.get("id") in _pass_app_ids or c.get("candidate_id") in _pass_cand_ids

    def _onboarded(c):
        return c.get("candidate_id") in _onboarded_cids

    # 招募漏斗：對齊招募看板的階段語意，往前補「新進候選人」（不管AI篩過沒），
    # 往後延伸到「面試通過」「面試通過率」以前只當獨立KPI、沒串進漏斗鏈）跟
    # 「報到」（06_員工主檔實際報到日，比「已通知」更貼近真正的招募成果）。
    _FUNNEL_STEPS = [
        ("新進候選人", lambda c: True),
        ("AI初篩通過", lambda c: c.get("screening_result") == "合格"),
        ("HR推薦",     lambda c: _ever_reached(c, "recommended")),
        ("主管覆核",   lambda c: _ever_reached(c, "invited")),
        ("進行面試",   lambda c: _ever_reached(c, "interviewed")),
        ("面試通過",   _interview_passed),
        ("報到",       _onboarded),
    ]
    funnel_labels = [label for label, _ in _FUNNEL_STEPS]
    funnel_counts = [sum(1 for c in cands_f if fn(c)) for _, fn in _FUNNEL_STEPS]
    # 用名字取數字，不要用 funnel_counts[4] 這種魔術索引——_FUNNEL_STEPS 插一個
    # 階段，所有索引就靜默指到錯的指標（跟這系統踩過好幾次的欄位錯位同一種脆弱）。
    _fc = dict(zip(funnel_labels, funnel_counts))

    # ── 指標行：只放「本期實際發生」────────────────────────────
    # 2026-08-12 改版。原本這一行放的是漏斗的 cohort 數字（母體＝初次進庫日期
    # 落在區間內的人，往後看他們最終走到哪）。那個語意本身沒錯，但放在整頁最
    # 顯眼的位置很危險：以使用者的招募節奏，八月進來的人最快也要九、十月才會
    # 面試/報到，所以選「本月」時後段三格結構上註定接近 0——不是漏算，是時候
    # 未到。使用者同一天被它誤導兩次（先是面試 4→顯示2，再是報到 2→顯示0）。
    #
    # 所以 KPI 行改成用事件日期算的「這個月實際做了什麼」，cohort 那組數字只留
    # 在下面的漏斗圖（那張圖本來就是 cohort 語意，配 caption 說明即可）。選
    # 「本年度」「全部」時漏斗才真的有意義，那時本來就會往下看圖。
    st.markdown("---")
    # 面試未到不算一場面試——人沒出席，沒有任何東西被評估過
    _ivs_held = [iv for iv in ivs_f if iv.get("result") != "no_show"]
    _ivs_noshow = len(ivs_f) - len(_ivs_held)
    st.caption("**本期實際發生**（用事件日期算：面試日期／實際報到日，"
               "不論這個人哪個月進來）")
    am1, am2, am3, am4 = st.columns(4)
    am1.metric("本期新進候選人", _fc["新進候選人"],
               help="初次進庫日期落在本區間的候選人數。")
    am2.metric("本期面試場次", len(_ivs_held),
               help="05_面試主檔中面試日期落在本區間的筆數，不含「面試未到」。"
                    "面試日期空白的紀錄無法歸月，不會出現在這裡。")
    am3.metric("本期面試未到", _ivs_noshow,
               help="約了但沒出席。不算一場面試，也不進面試通過率的分母。")
    am4.metric("本期報到人數", len(onboarded_f),
               help="06_員工主檔中「實際報到日」落在本區間的人數。"
                    "只填了預計報到日、還沒真的來上班的人不算在內。")
    st.markdown("---")

    ch1, ch2 = st.columns(2)

    # ── 招募漏斗 ──────────────────────────────────────────────
    with ch1:
        st.subheader("📊 招募漏斗")
        # 這張圖是 cohort 語意，跟上面的 KPI 行不是同一種數字，一定要講清楚，
        # 否則「上面寫面試4場、這裡寫進行面試2人」看起來就像系統壞了。
        st.caption("母體＝**本期新進**的候選人，往後追他們最終走到哪一步。"
                   "區間選得短時後段會偏低（這個月剛進來的人還沒輪到面試），"
                   "**不是漏算**；要看「本期實際做了幾場」請看上面的 KPI。")
        # 2026-08-13：不砍圖，改加警語——面試/已通知這幾格常常個位數，一個人
        # 變動就能讓百分比跳一大塊（例如1人變2人＝+100%），百分比看起來精確
        # 但其實在這種樣本量下沒有統計意義，只看圖上的百分比容易誤判趨勢。
        _nonzero_counts = [c for c in funnel_counts if c > 0]
        if _nonzero_counts and min(_nonzero_counts) < 10:
            st.caption("⚠️ 後段階段人數常是個位數，圖上的百分比一個人變動就會跳一大塊，"
                       "請以「人數」判斷，不要照百分比推論轉換率高低。")
        fig_funnel = go.Figure(go.Funnel(
            y=funnel_labels, x=funnel_counts,
            textinfo="value+percent initial",
            marker={"color": ["#1e40af","#2563eb","#3b82f6","#60a5fa",
                               "#93c5fd","#0ea5e9","#0891b2"]},
        ))
        fig_funnel.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=300,
                                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_funnel, use_container_width=True)

        # 人工覆核率：不對主管揭露（推薦信裡不寫這個），只在這裡給HR自己看——
        # AI判不合格、HR仍手動從淘汰名單拉上來推薦的比例。這個比例偏高，
        # 代表AI評分Prompt或維度設計可能有問題（太嚴苛/抓錯重點），值得回頭
        # 檢視，不是候選人本身的問題（使用者2026-07-28提出的用途）。
        _override_n = sum(1 for c in cands_f if c.get("hr_override"))
        # 分母要把覆核者本人也算進去：他若之後被結案且「結案前階段」空白，
        # _ever_reached 會退回 screening、從「HR推薦」這格消失，但分子仍算他，
        # 比率就會超過100%。取兩者的聯集當分母，數學上永遠 <=100%。
        _hr_recommend_n = max(_fc["HR推薦"], _override_n)
        if _hr_recommend_n:
            _override_rate = _override_n / _hr_recommend_n * 100
            _rate_msg = f"🔼 人工覆核率：{_override_n}/{_hr_recommend_n}（{_override_rate:.0f}%）"
            if _override_rate >= 20:
                st.warning(f"{_rate_msg} ——偏高，建議檢視AI評分Prompt或評分維度是否過嚴／抓錯重點。")
            else:
                st.caption(f"{_rate_msg} ——AI判不合格、HR仍手動推薦的比例。")

    # ── 候選人來源分布 ────────────────────────────────────────
    with ch2:
        st.subheader("🔍 候選人來源")
        if cands_f:
            # 2026-08-13：不砍圖，改加警語——區間拉到七月中以前，「來源」選單
            # 那時還沒固定填，會出現一大塊「未指定」；那不是漏填，是那段時間
            # 本來就沒有記錄來源，跟其他來源類別放在同一張圓餅圖裡容易被誤讀
            # 成「主要來源不明」。另外總筆數不多時，一塊佔大部分也不代表
            # 真的只有那個管道，可能只是這段時間剛好都是同一類職缺在收履歷。
            if len(cands_f) < 30:
                st.caption(f"⚠️ 本區間只有 {len(cands_f)} 筆，佔比容易被單一批次影響"
                           "（例如同時段只收某類職缺），不代表長期來源比例。")
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
        st.subheader("📈 每月新增候選人（最近6個月）")
        # 2026-08-13：不砍圖，改加警語——每月人數常是個位數到十幾人，柱狀圖上
        # 看起來的「大幅成長/下滑」可能只是1、2個人的差距（例如0→2人視覺上
        # 是從無到有，但實際只是2個人），提醒不要照曲線形狀推論招募動能變化。
        st.caption("⚠️ 月人數常是個位數，柱狀高低差可能只是1、2人，"
                   "解讀「成長/下滑」前先看實際人數。")
        # 這張圖的目的就是看趨勢，固定看最近6個月，不跟著上面的「統計區間」
        # 選單走——選「本月」的話這張圖只會剩1個月的資料，完全看不出趨勢。
        # 用all_cands（不是cands_f）當資料源，月份範圍自己算，沒人的月份補0，
        # 不能讓沒資料的月份直接從圖上消失，不然會誤以為那個月剛好沒有候選人。
        _month_labels = []
        _cursor = date(today.year, today.month, 1)
        for _ in range(6):
            _month_labels.append(_cursor.strftime("%Y-%m"))
            _cursor = (_cursor - timedelta(days=1)).replace(day=1)
        _month_labels.reverse()

        _month_counts = {m: 0 for m in _month_labels}
        for c in all_cands:
            dt = parse_dt(c.get("created_at"))
            if dt:
                m = dt.strftime("%Y-%m")
                if m in _month_counts:
                    _month_counts[m] += 1

        fig_mo = px.bar(x=_month_labels, y=[_month_counts[m] for m in _month_labels],
                        labels={"x": "月份", "y": "人數"},
                        color_discrete_sequence=["#1e40af"])
        # 只有1個月資料時，plotly會誤把x軸判成連續時間軸，自動縮放出
        # 微秒級的亂碼刻度（"23:59:59.9996"這種）——強制設成分類軸避免。
        fig_mo.update_xaxes(type="category")
        fig_mo.update_layout(margin=dict(l=0,r=0,t=10,b=0), height=280,
                              plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_mo, use_container_width=True)

    # ── 評等分布 ─────────────────────────────────────────────
    with ch4:
        st.subheader("🏆 AI 評等分布")
        if cands_f:
            # 2026-08-13：不砍圖，改加警語——這張圖只顯示 AI 給了多少 A/B/C，
            # 不代表等第準不準。等第有沒有預測力要看下面的「AI 等第 vs 後續
            # 結果」交叉分析，那裡才是能不能信任這個等第的答案。
            st.caption("這張只顯示 AI 評等的分布，不代表評等準確——"
                       "評等跟結果的關聯請看下方交叉分析。")
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

    # ── AI 等第 vs 後續結果 交叉分析 ──────────────────────────
    st.markdown("---")
    st.subheader("🎯 AI 等第 vs 後續結果 交叉分析")
    st.info(
        "⚠️ 樣本量小、時間跨度短時，此分析僅供參考，不足以下結論；請隨資料累積持續觀察。"
        "目前系統無離職/留任追蹤資料，本分析只到「錄取」為止，不涉及留任率。"
    )

    def _result_category(stage: str) -> str:
        if stage == "hired":
            return "已錄取"
        if stage == "rejected":
            return "已結案/淘汰"
        if stage in ("interviewed", "offer_pending"):
            return "已面試"
        return "仍在流程中"

    _CAT_ORDER = ["已面試", "已錄取", "已結案/淘汰", "仍在流程中"]
    _cross = {g: {cat: 0 for cat in _CAT_ORDER} for g in ("A", "B", "C")}
    for c in cands_f:
        g = c.get("grade", "C")
        if g not in _cross:
            g = "C"
        _cross[g][_result_category(c.get("stage", ""))] += 1

    cross_df = pd.DataFrame(_cross).T[_CAT_ORDER]
    cross_df.index.name = "AI 等第"
    st.dataframe(cross_df, use_container_width=True)

    # 有結果的樣本（已面試/已錄取/已結案，排除仍在流程中）
    n_with_result = sum(
        _cross[g][cat] for g in _cross for cat in _CAT_ORDER if cat != "仍在流程中"
    )
    if n_with_result < 30:
        st.warning(f"目前樣本量過小（N={n_with_result} 筆有結果的應徵記錄），建議累積更多資料後再參考此分析。")

    st.markdown("**各等第錄取率**（該等第已錄取人數 ÷ 該等第總人數）")
    for g in ("A", "B", "C"):
        total_g = sum(_cross[g].values())
        hired_g = _cross[g]["已錄取"]
        rate = (hired_g / total_g * 100) if total_g else 0
        gm = GRADE_META.get(g, ("", "", "", ""))
        st.write(f"{gm[3]} {g} 等第：{hired_g} / {total_g} = {rate:.0f}%")
        st.progress(min(rate / 100, 1.0))

    # ── 主管回應時間表 ────────────────────────────────────────
    # 2026-08-13 新增。HR推薦46→主管推進21，55%的流失卡在主管端，是整條漏斗
    # 最大的單一斷點——這張表就是把它變成看得到、能拿去跟主管溝通的數字。
    # 用全部歷史（不跟上面的統計區間走），因為樣本本來就少，拆更短的區間
    # 只會更沒意義。
    #
    # 資料限制：「推薦主管」「推薦日」是 2026-08-13 才補上寫入路徑，之前的
    # 推薦記錄這兩欄是空的，不會被算進這張表——樣本量會隨時間才慢慢累積。
    # 「回應天數」用「人才狀態更新日」當回應時間點的近似值：如果這個人推薦後
    # 只被動過一次（推薦→下一步），這個日期就是真正的回應日；如果後來又動過
    # 幾次（例如又推進到已面試），這個日期會晚於真正回應的那一刻，天數因此
    # 是「最多不會少於」的近似值，不是精確值——樣本還小，先看得到有沒有卡住
    # 比抓到精確天數更重要。
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:var(--fs-sm);color:var(--p);'
        'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        '👔 主管回應時間表</div>',
        unsafe_allow_html=True,
    )
    _mgr_rows, _n_recommended = _manager_response_stats(all_cands)
    if not _mgr_rows:
        st.info("目前沒有帶「推薦主管」記錄的資料——這欄是 2026-08-13 才開始寫入，"
                "累積幾週後這裡才會有東西可看。")
    else:
        if _n_recommended < 20:
            st.caption(f"⚠️ 目前只有 {_n_recommended} 筆帶推薦記錄，樣本還小，"
                       "數字僅供參考、不要拿來對主管下結論。")
        _mgr_df = pd.DataFrame(_mgr_rows)
        _mgr_df["平均回應天數（工作日）"] = _mgr_df["平均回應天數（工作日）"].apply(
            lambda v: v if v is not None else "—")
        st.dataframe(_mgr_df, use_container_width=True, hide_index=True)

    # ── 開缺存量表 ────────────────────────────────────────────
    # 2026-08-13 新增。0人的缺是供給問題（沒人應徵/沒人被篩進來），跟「有人
    # 卡在流程裡」是完全不同的問題、需要不同的動作——這張表刻意把兩者分開看。
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:var(--fs-sm);color:var(--p);'
        'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        '📋 開缺存量表</div>',
        unsafe_allow_html=True,
    )
    _job_rows = _job_pipeline_inventory(all_cands, all_jobs, all_hires)
    if not _job_rows:
        st.info("目前沒有標記為「招募中」的職缺。")
    else:
        _n_zero = sum(1 for r in _job_rows if r["缺口"])
        if _n_zero:
            st.warning(f"⚠️ {_n_zero} 個開缺目前管道裡完全沒有人——這是供給不足，"
                       "不是流程卡住，補人／催辦解決不了，需要重新開拓來源或調整條件。")
        _job_df = pd.DataFrame(_job_rows)
        _job_df["狀態"] = _job_df["缺口"].apply(lambda z: "⚠️ 0人，供給問題" if z else "")
        _job_df["開缺天數"] = _job_df["開缺天數"].apply(lambda v: v if v is not None else "—")
        _job_df = _job_df.drop(columns=["缺口"])
        st.dataframe(_job_df, use_container_width=True, hide_index=True)

    # ── 匯出 Excel ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⬇ 匯出報告")
    if st.button("產生 Excel 報告", type="primary", key="ana_export"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            # 摘要
            summary = pd.DataFrame({"指標": funnel_labels, "數值": funnel_counts})
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
                    "預計報到日": h.get("start_date"),
                    "實際報到日": h.get("actual_start_date") or "",
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
    # 2026-08-14：拿掉「新增職缺」表單。這裡跟「動態篩選引擎」(app.py) 是兩個
    # 完全獨立的資料來源——app.py 建職缺時要填必備條件/加分條件/評分維度，
    # 這些是 AI 篩選履歷的必要內容，不是隨便打個名字就好；這裡的表單只收
    # 職缺名稱/部門/人數，就算存進 01_職缺主檔，動態篩選引擎也永遠讀不到、
    # 用不了。實際發生過：使用者在這裡新增「中壢長期晚班計時人員」，發現
    # 篩選引擎完全看不到，因為兩邊的職缺根本是兩份獨立資料。
    #
    # 而且這裡生成的 job_id 格式（sanitize後的名稱+時間戳後綴，見舊版
    # save_job()）跟 app.py 生成的 job_id（單純 sanitize 後的名稱，無後綴）
    # 不一致——如果之後又想用同一個職缺名稱在 app.py 建立並開始篩履歷，
    # 兩邊 job_id 對不上會產生重複的職缺紀錄，跟 08-10 那次「外貿業務助理」
    # 需要事後合併的狀況一樣。
    #
    # 正確流程：新職缺一律從 app.py 建立（同時決定篩選條件），它會自動同步
    # 進 01_職缺主檔；這裡只保留對既有職缺的狀態管理（關閉/重開）。
    st.caption("💡 新職缺請到「動態篩選引擎」(app.py) 建立——那裡會同時設定 "
               "AI 篩選條件，並自動同步到這份主檔。這裡只能管理既有職缺的狀態。")
    jobs = fetch_all_jobs()
    if jobs:
        for j in jobs:
            status = j.get("status", "open")
            sc = {"open": "#15803d", "paused": "#b45309", "closed": "#475569"}.get(status, "#64748b")
            sl = {"open": "招募中", "paused": "暫停中", "closed": "已結束"}.get(status, status)
            jc1, jc2, jc3, jc4 = st.columns([3.5, 1.2, 1, 1.2])
            jc1.markdown(
                f'<b>{_html.escape(j.get("title",""))}</b>'
                f'<span style="color:#64748b;font-size:var(--fs-sm);margin-left:8px;">'
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
        st.info("尚無職缺——請到「動態篩選引擎」建立第一個職缺。")

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
        '<div style="font-family:var(--font-ui);font-size:var(--fs-xl);font-weight:800;'
        'letter-spacing:-.03em;color:var(--sb-text);margin-bottom:2px;line-height:1.1;">'
        '🚀 HireFlow</div>'
        '<div style="font-size:var(--fs-2xs);font-weight:500;color:var(--sb-muted);'
        'letter-spacing:.08em;text-transform:uppercase;margin-bottom:18px;">'
        'ECLIFE · 招募任用儀表板</div>',
        unsafe_allow_html=True,
    )
    # session_state['nav']（radio的key）在widget實例化後就不能再改，跨頁按鈕
    # （如看板「→ 到職追蹤」）要切頁一律先寫進 _pending_nav，這裡搶在widget
    # 實例化之前把它套用回nav。
    if st.session_state.get('_pending_nav'):
        st.session_state['nav'] = st.session_state.pop('_pending_nav')
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
    if st.button("🔄 從 Google Sheets 重新載入", use_container_width=True,
                 help="清除快取並重新讀取六個主檔，這是唯一的資料更新入口"):
        _invalidate()
        st.rerun()
    if st.button("💾 備份六主檔到本機", use_container_width=True):
        with st.spinner("備份中…"):
            _ok, _msg = backup_sheets_to_local()
        if _ok:
            st.success(f"已備份六主檔到 backups/{_msg}/")
        else:
            st.error(f"備份失敗：{_msg}")
    _fetched_at = st.session_state.get("_data_fetched_at")
    if _fetched_at:
        st.caption(f"資料載入時間：{_fetched_at}")
    st.caption(f"今天：{date.today().strftime('%Y/%m/%d')}")

    _pending_syncs = _load_pending_sync()
    if _pending_syncs:
        st.error(f"⚠️ 初篩端有 {len(_pending_syncs)} 筆流程狀態同步失敗")
        for _p in _pending_syncs:
            st.caption(f"{_p['name']}（{_p['job_name']} → {_p['new_status']}）")
        if st.button("🔁 重試同步", key="dash_retry_pending_sync", use_container_width=True):
            _ok, _fail = retry_pending_syncs()
            if _ok:
                st.toast(f"✅ 已補同步 {_ok} 筆")
            if _fail:
                st.warning(f"仍有 {_fail} 筆失敗，請確認Sheets連線或改到app.py重試")
            _invalidate()
            st.rerun()

_PAGE_META = {
    "🏠 本週 + 下週總覽": ("🏠 本週 + 下週總覽", "面試行程 · 報到事件 · 待辦事項一覽"),
    "🗂️ 招募看板":        ("🗂️ 招募看板",         "拖拉式流程追蹤，快速推進候選人狀態"),
    "👤 候選人":           ("👤 候選人管理",        "查閱評分、篩選條件、推薦主管"),
    "📅 面試管理":         ("📅 面試管理",          "排程、記錄面試結果與評分"),
    "✅ 到職流程":         ("✅ 到職流程",          "錄取後 Onboarding checklist 追蹤"),
    "📈 分析報表":         ("📈 分析報表",          "漏斗轉換率 · 時效 · 趨勢圖表"),
    "📋 職缺管理":         ("📋 職缺管理",          "新增、編輯、追蹤開缺狀態"),
}

def _page_header(page_key: str):
    render_brand_header("HireFlow 招募儀表板")
    title, subtitle = _PAGE_META.get(page_key, (page_key, ""))
    st.title(title)
    if subtitle:
        st.markdown(
            f'<div style="margin-top:-12px;margin-bottom:8px;font-size:var(--fs-sm);'
            f'color:var(--muted);font-family:var(--font-b);">{subtitle}</div>',
            unsafe_allow_html=True,
        )

# Render selected page
if page == "🏠 本週 + 下週總覽":
    _page_header(page)
    page_overview()
elif page == "🗂️ 招募看板":
    _page_header(page)
    page_kanban()
elif page == "👤 候選人":
    _page_header(page)
    page_candidates()
elif page == "📅 面試管理":
    _page_header(page)
    page_interviews()
elif page == "✅ 到職流程":
    _page_header(page)
    page_onboarding()
elif page == "📈 分析報表":
    _page_header(page)
    page_analytics()
elif page == "📋 職缺管理":
    _page_header(page)
    page_jobs()
