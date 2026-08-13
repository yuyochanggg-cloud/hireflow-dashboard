# -*- coding: utf-8 -*-
"""HireFlow smoke tests — 守住歷史重大 bug 的最小安全網。

跑法（repo 根目錄）：python -m pytest tests/test_smoke.py -q
全部離線，不連 Google Sheets、不讀 config/secrets。
每個測試對應一個真實踩過的坑或核心契約，改壞會立刻紅。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hr_schema
from hr_schema import (
    S2_COLS, S3_COLS, S4_COLS, S3_PROTECT_ON_UPDATE,
    FLOW_TO_STAGE, STAGE_KEYS, grade_badge_html,
)
import app  # module-level 有 st.set_page_config，bare mode 下是 no-op
import dashboard as dashboard_module  # 同上；只用來對原始碼做語意斷言


# ── 1. Schema 契約（守 2026-07-09 的 13欄/19欄錯位 bug）─────────────

def test_s3_二十一欄且key是application_id():
    # 19 欄 + 「結案前階段」(2026-07-15) + 「結案原因」(2026-07-23) = 21
    assert len(S3_COLS) == 21, "03_應徵主檔欄數變了，_build_master_rows 會寫錯位"
    assert S3_COLS[0] == "application_id"
    assert S2_COLS[0] == "candidate_id"


def test_保護欄位必須真的存在於S3():
    # 若保護欄名打錯字，_upsert_rows 的 header.index() 找不到 → 保護「靜默失效」
    missing = set(S3_PROTECT_ON_UPDATE) - set(S3_COLS)
    assert not missing, f"這些保護欄不在 S3_COLS，HR 手填資料會被洗掉：{missing}"


def test_舊資料流程狀態相容():
    # 守「已約面試」（舊寫法）→ interview_scheduled 的向下相容
    assert FLOW_TO_STAGE["已約面試"] == "interview_scheduled"
    # 所有流程狀態都必須映到合法 stage，否則看板該卡片會消失
    assert set(FLOW_TO_STAGE.values()) <= set(STAGE_KEYS)


def test_未知評級不會crash():
    html = grade_badge_html("不存在的等級")
    assert isinstance(html, str) and html


# ── 2. _upsert_rows（守「批次同步洗掉 HR 手填欄位」bug）─────────────

class FakeWS:
    """假 worksheet：記錄 _upsert_rows 實際送出什麼，不碰網路。"""
    def __init__(self, header, rows):
        self._values = [header] + rows
        self.updated_cells = []
        self.appended = []

    def get_all_values(self):
        return self._values

    def update_cells(self, cells, value_input_option=None):
        self.updated_cells = cells

    def append_rows(self, rows, value_input_option=None, insert_data_option=None):
        self.appended = rows


def test_更新既有列時不覆蓋HR手填欄位():
    header = list(S3_COLS)
    備註_idx = header.index("備註")
    流程_idx = header.index("流程狀態")
    existing = ["APP-123-測試職缺"] + [""] * 19
    existing[備註_idx] = "HR 手打的重要備註"
    existing[流程_idx] = "已約面試"
    ws = FakeWS(header, [existing])

    new_row = ["APP-123-測試職缺"] + ["新值"] * 19  # 同 key，全部欄位帶新值
    app._upsert_rows(ws, [new_row], key_cols=[0],
                     protect_cols=S3_PROTECT_ON_UPDATE)

    touched_cols = {c.col - 1 for c in ws.updated_cells}  # Cell.col 是 1-based
    protected = {header.index(c) for c in S3_PROTECT_ON_UPDATE}
    assert not (touched_cols & protected), \
        "受保護欄位被寫入了——HR 手填資料會被批次同步洗掉"
    assert touched_cols, "非保護欄位應該要被更新"
    assert not ws.appended, "同 key 應走更新而非新增"


def test_新候選人照常整列新增():
    ws = FakeWS(list(S3_COLS), [])
    new_row = ["APP-999-新職缺"] + ["x"] * 19
    app._upsert_rows(ws, [new_row], key_cols=[0],
                     protect_cols=S3_PROTECT_ON_UPDATE)
    assert len(ws.appended) == 1 and ws.appended[0][0] == "APP-999-新職缺"
    assert not ws.updated_cells


# ── 3. ID 產生契約（守 candidate_id/application_id 混用 bug）────────

def test_id產生公式契約():
    cand = {"104代碼": "12345", "真實姓名": "王小明"}
    jd = "門市儲備幹部 (台北-中山店)超長職缺名稱測試用"
    s2, s3, s4 = app._build_master_rows(jd, [cand])

    import re
    job_safe = re.sub(r"[^\w\-]", "_", jd)[:20]  # 與程式內公式一致（契約）
    assert s2[0][0] == "CAND-12345"
    assert s3[0][0] == f"APP-12345-{job_safe}"
    assert s3[0][2] == "CAND-12345", "s3 的 candidate_id 欄要對回 02 主檔"
    assert s4[0][0] == f"SCR-12345-{job_safe}"
    # 兩種 id 絕不可互換：application_id 必含職缺、candidate_id 必不含
    assert job_safe in s3[0][0] and job_safe not in s2[0][0]


def test_master_rows寬度與schema一致():
    # 守欄位錯位：產出的 row 寬度必須等於 schema 欄數
    cand = {"104代碼": "1", "真實姓名": "測"}
    s2, s3, s4 = app._build_master_rows("職缺A", [cand])
    assert len(s2[0]) == len(S2_COLS)
    assert len(s3[0]) == len(S3_COLS)
    assert len(s4[0]) == len(S4_COLS)


def test_job_row寬度與S1一致():
    # 2026-08-04 新增 01_職缺主檔同步時，S1 沒有像 S2/S3/S4 一樣被寬度測試守住，
    # 正是 2026-07-27「S3 少一欄」事故的同一個缺口。
    row = app._build_job_row("職缺A")
    assert len(row) == len(hr_schema.S1_COLS), "01_職缺主檔 row 寬度跟 S1_COLS 對不上"
    assert hr_schema.S1_COLS[0] == "job_id"
    missing = set(hr_schema.S1_PROTECT_ON_UPDATE) - set(hr_schema.S1_COLS)
    assert not missing, f"這些保護欄不在 S1_COLS，保護會靜默失效：{missing}"


# ── 3.5 識別碼唯一性（守 2026-08-05 的 APP-- 撞號事故）──────────────

def test_無104代碼時app_id不會互相撞號():
    """生產資料曾出現 8 列共用 3 個 application_id（AI短影音企劃專員有 4 位真實
    A/B 級候選人被合併成 1 列）。104代碼 空白時必須還能產生互不相同的 ID。"""
    a = {"104代碼": "", "真實姓名": "", "履歷原文": "甲的履歷內容" * 30}
    b = {"104代碼": None, "真實姓名": None, "履歷原文": "乙的履歷內容" * 30}
    _, app_a, _, _ = app.make_master_ids(a, "職缺A")
    _, app_b, _, _ = app.make_master_ids(b, "職缺A")
    assert app_a != app_b, "兩個無代碼候選人拼出同一個 application_id"
    assert app_a != "APP--職缺A" and "APP--" not in app_a


def test_無代碼者的ID不能被104樣板文字綁在一起():
    """104 履歷的前 300 字是「履歷使用規範」法律樣板、人人相同。若拿前 300 字做
    hash（_render_results 算 cache_key 就是那樣寫的），所有無代碼者會 hash 到同一
    個值、再次全部撞號。這條守住「必須用全文」。"""
    boiler = "EcLife良興_良興股份有限公司從事徵才目的使用。履歷使用規範" * 12  # >300字
    a = {"104代碼": None, "履歷原文": boiler + "甲的工作經歷"}
    b = {"104代碼": None, "履歷原文": boiler + "乙的工作經歷"}
    assert app.resolve_candidate_code(a) != app.resolve_candidate_code(b)


def test_同一份履歷每次都得到同一個ID():
    # 不可重現的 ID（例如摻進時間戳）會讓 upsert 每次同步都新增一列
    cand = {"104代碼": "", "履歷原文": "某人的履歷全文" * 20}
    assert app.resolve_candidate_code(cand) == app.resolve_candidate_code(dict(cand))


def test_有104代碼時ID完全不變():
    # 這是遷移安全的關鍵：既有 838 列的 ID 一個都不能變，否則同步會全部變成新增列
    cand = {"104代碼": "1872572026871", "真實姓名": "翁志魁"}
    cand_id, app_id, scr_id, job_safe = app.make_master_ids(cand, "視覺設計師")
    assert cand_id == "CAND-1872572026871"
    assert app_id == "APP-1872572026871-視覺設計師"
    assert scr_id == "SCR-1872572026871-視覺設計師"


# ── 4. 評分與解析（守 LLM 輸出不可信原則）──────────────────────────

def test_加權評分_C級同步標記不合格():
    dims = [{"dimension": "技能", "weight": 1.0}]
    data = {"dynamic_scores": [{"dimension": "技能", "score": 3}]}
    out = app.compute_weighted_grade(data, dims)
    assert out["綜合推薦度"] == "C"
    assert out["初篩判定"] == "不合格", "C 級必須同步標不合格，否則看板與評級矛盾"


def test_加權評分_維度對不上不強算():
    # AI 回的維度名跟 JD 完全對不上 → 不能全算 0 分變 C（誤殺）
    dims = [{"dimension": "技能", "weight": 1.0}]
    data = {"dynamic_scores": [{"dimension": "AI自己發明的維度", "score": 9}],
            "綜合推薦度": "待確認"}
    out = app.compute_weighted_grade(data, dims)
    assert out["綜合推薦度"] == "待確認", "維度對不上時應維持原值，不得強算誤殺"


def test_extract_json_能解析markdown包裹的輸出():
    text = '好的，以下是結果：\n```json\n{"初篩判定": "合格", "分數": 8}\n```'
    obj = app.extract_json(text)
    assert obj and obj["初篩判定"] == "合格"
    assert app.extract_json("完全沒有 JSON 的回覆") is None


def test_個資遮蔽():
    masked = app.mask_personal_info(
        "聯絡 test@example.com 或 0912-345-678，35歲", "王小明")
    assert "test@example.com" not in masked
    assert "0912" not in masked
    assert "35歲" not in masked


# ── 5. 健檢護欄（守 2026-08-06 遷移腳本用 today 蓋掉歷史日期的坑）──────

def _hc_rows(s3_pairs, s2_pairs):
    """組出 check_10 需要的 (03, 02) 兩張表最小資料。"""
    h3 = list(S3_COLS)
    h2 = ['candidate_id', '真實姓名', '104代碼', 'Email', '電話（遮蔽）', '居住地',
          '最近應徵職缺', '初次進庫日期', '最後更新日期', '來源檔案', '備註']
    t3 = [h3]
    for cid, batch in s3_pairs:
        r = [''] * len(h3)
        r[h3.index('candidate_id')] = cid
        r[h3.index('應徵批次日期')] = batch
        t3.append(r)
    t2 = [h2]
    for cid, first in s2_pairs:
        r = [''] * len(h2)
        r[0] = cid
        r[h2.index('初次進庫日期')] = first
        t2.append(r)
    return t3, t2


def test_健檢抓得到初次進庫日期被蓋成執行當天():
    # 2026-08-06 撞號修復腳本替 11 人新開 02 列時把初次進庫寫成執行當天，
    # 導致 6/7 月的人被算進 8 月的新進候選人。這條護欄就是為了讓下次當天就發現。
    import daily_health_check as hc
    t3, t2 = _hc_rows([('CAND-Ha', '2026-06-24')], [('CAND-Ha', '2026-08-06')])
    issue = hc.check_10_first_entry_date(t3, t2)
    assert issue is not None, "初次進庫晚於應徵日期必須被抓到"
    assert '2026-06-24' in issue.lines[0]


def test_健檢不誤報進庫早於應徵的正常情形():
    # 人才庫舊人之後才投新職缺是正常的；會誤報的健檢等於沒有健檢
    import daily_health_check as hc
    t3, t2 = _hc_rows([('CAND-X', '2026-07-01')], [('CAND-X', '2026-05-01')])
    assert hc.check_10_first_entry_date(t3, t2) is None
    # 同日、空值、短列都不能報也不能炸
    t3, t2 = _hc_rows([('CAND-Y', '2026-08-10')], [('CAND-Y', '2026-08-10')])
    assert hc.check_10_first_entry_date(t3, t2) is None
    t3, t2 = _hc_rows([('CAND-W', '')], [('CAND-W', '2026-08-06')])
    assert hc.check_10_first_entry_date(t3, t2) is None
    assert hc.check_10_first_entry_date([list(S3_COLS), ['CAND-S']],
                                        [['candidate_id'], ['CAND-S']]) is None


def test_健檢報告編號總數與檢查數一致():
    # 以前 [n/9] 寫死在四處，加檢查時漏改就會出現「[10/9]」
    import daily_health_check as hc
    import inspect
    n = len([x for x in dir(hc) if x.startswith('check_') and callable(getattr(hc, x))])
    assert hc.TOTAL_CHECKS == n, f"TOTAL_CHECKS={hc.TOTAL_CHECKS} 但實際有 {n} 個 check_ 函式"
    assert 'TOTAL_CHECKS' in inspect.getsource(hc.format_report), "報告編號必須讀 TOTAL_CHECKS"


# ── 6. 面試未到（no_show）獨立類別（2026-08-12）────────────────────

def test_面試未到不是未通過():
    # 沒出席的人沒被評估過，不該進面試通過率的分母。以前兩者都寫「未通過」。
    from hr_schema import RESULT_MAP, CLOSE_REASON_TO_INTERVIEW
    assert RESULT_MAP["面試未到"] == "no_show"
    assert RESULT_MAP["未通過"] == "fail", "未通過不能被連坐改掉"
    assert CLOSE_REASON_TO_INTERVIEW["面試未到"][0] == "面試未到"
    assert CLOSE_REASON_TO_INTERVIEW["面試未通過"][0] == "未通過"
    # 結案原因清單裡兩個選項都還在，沒被合併
    assert "面試未到" in hr_schema.CLOSE_REASONS
    assert "面試未通過" in hr_schema.CLOSE_REASONS


def test_健檢抓得到有面試紀錄但階段沒推進():
    # 葉宇騫案例的反向：05 有「未通過」記分卡，但 03 還停在約定面試 → 漏斗少算他
    import daily_health_check as hc
    h3 = list(S3_COLS)
    h5 = ['interview_id', 'application_id', 'candidate_id', 'job_id', '職缺名稱',
          '姓名', '面試日期', '面試時間', '面試官', '面試類型', '面試結果']

    def mk3(app_id, flow, pre=''):
        r = [''] * len(h3)
        r[h3.index('application_id')] = app_id
        r[h3.index('流程狀態')] = flow
        r[h3.index('結案前階段')] = pre
        r[h3.index('姓名')] = '測試'
        return r

    def mk5(app_id, result):
        r = [''] * len(h5)
        r[1] = app_id
        r[5] = '測試'
        r[6] = '2026-06-25'
        r[10] = result
        return r

    # 有「未通過」記分卡但階段停在約定面試 → 該報
    issue = hc.check_11_interview_ahead_of_stage(
        [h3, mk3('APP-1', '已結案', '約定面試')], [h5, mk5('APP-1', '未通過')])
    assert issue is not None

    # 同一筆改成「面試未到」→ 階段停在約定面試是正確的，不該報
    assert hc.check_11_interview_ahead_of_stage(
        [h3, mk3('APP-1', '已結案', '約定面試')], [h5, mk5('APP-1', '面試未到')]) is None

    # 「待定」是排了還沒填結果，也不該報
    assert hc.check_11_interview_ahead_of_stage(
        [h3, mk3('APP-1', '已結案', '約定面試')], [h5, mk5('APP-1', '待定')]) is None

    # 階段已到已面試 → 正常，不該報
    assert hc.check_11_interview_ahead_of_stage(
        [h3, mk3('APP-1', '已面試')], [h5, mk5('APP-1', '未通過')]) is None

    # 孤兒紀錄（03 找不到對應 app_id）是 check_7 的守備範圍，這裡不重複報
    assert hc.check_11_interview_ahead_of_stage(
        [h3, mk3('APP-1', '已面試')], [h5, mk5('APP-不存在', '未通過')]) is None


def test_本期報到人數要用實際報到日不是預計報到日():
    # 2026-08-12 實跑抓到的 bug：八月真的報到2人，指標卻顯示0，因為沿用了既有的
    # hires_f（依「預計報到日」篩，那兩人的預計報到日是七月填的）。
    # 06_員工主檔的 start_date=預計報到日、actual_start_date=實際報到日，
    # 名字很像但語意完全不同，混用不會報錯、只會靜默算錯。
    import inspect
    src = inspect.getsource(dashboard_module.page_analytics)
    assert 'onboarded_f' in src, "本期報到人數必須用依 actual_start_date 篩的清單"
    # 找到那一行 metric，確認它吃的是 onboarded_f
    line = next(l for l in src.splitlines() if '"本期報到人數"' in l)
    assert 'onboarded_f' in line, f"本期報到人數吃錯清單了：{line.strip()}"
    assert 'actual_start_date' in src


# ── 7. 待催辦天數（2026-08-12）──────────────────────────────────────

def test_工作日計算不含週末():
    import daily_health_check as hc
    import datetime as _dt
    # 2026-08-07 是週五，2026-08-12 是週三 → 中間工作日：10(一)11(二)12(三) = 3
    assert hc._workdays_since('2026-08-07', _dt.date(2026, 8, 12)) == 3
    # 週五 → 下週一 = 1 個工作日（週末不算）
    assert hc._workdays_since('2026-08-07', _dt.date(2026, 8, 10)) == 1
    # 同一天 = 0
    assert hc._workdays_since('2026-08-12', _dt.date(2026, 8, 12)) == 0
    # 未來日期、空值、爛格式都回 None，不能當成 0（0 會被當成「今天剛推薦」而漏催）
    assert hc._workdays_since('2026-09-01', _dt.date(2026, 8, 12)) is None
    assert hc._workdays_since('', _dt.date(2026, 8, 12)) is None
    assert hc._workdays_since('不是日期', _dt.date(2026, 8, 12)) is None


def test_待催辦以推薦日優先且無日期不誤報():
    import daily_health_check as hc
    import datetime as _dt
    h = list(S3_COLS)

    def mk(flow, rec_date='', upd_date='', rec='', name='測試'):
        r = [''] * len(h)
        r[h.index('流程狀態')] = flow
        r[h.index('推薦日')] = rec_date
        r[h.index('人才狀態更新日')] = upd_date
        r[h.index('推薦主管')] = rec
        r[h.index('姓名')] = name
        r[h.index('職缺名稱')] = '某職缺'
        return r

    today = _dt.date(2026, 8, 12)

    # 已推薦主管：推薦日優先（比人才狀態更新日更精準地代表「推薦發生在哪天」）
    lines, n, no_date = hc.build_followup_lines(
        [h, mk('已推薦主管', rec_date='2026-08-03', upd_date='2026-08-11', rec='設計部 許媚喬')], today)
    assert n == 1 and '設計部 許媚喬' in lines[0]
    assert '個工作日' in lines[0]

    # 沒有任何日期 → 算進 no_date，不算逾期（不能憑空當成很久沒動）
    lines, n, no_date = hc.build_followup_lines([h, mk('已推薦主管')], today)
    assert (n, no_date) == (0, 1)

    # 未達門檻不報（3 個工作日才算逾期）
    lines, n, _ = hc.build_followup_lines([h, mk('已推薦主管', rec_date='2026-08-11')], today)
    assert n == 0

    # 不在規則裡的階段不管（初篩完成的 644 人不該每天被催）
    lines, n, no_date = hc.build_followup_lines(
        [h, mk('初篩完成', upd_date='2026-01-01')], today)
    assert (n, no_date) == (0, 0)
    lines, n, no_date = hc.build_followup_lines(
        [h, mk('已結案', upd_date='2026-01-01')], today)
    assert (n, no_date) == (0, 0)


def test_寄信路徑會寫推薦主管與推薦日():
    # 2026-08-12：寄推薦信那條路徑原本只寫「流程狀態」，而 dashboard 的 update_stage
    # 會寫「人才狀態更新日」——兩條路徑做同一件事、缺的那條躲了幾個月，導致
    # 「推薦後幾天沒回」完全算不出來。這條測試鎖住三個欄位都要寫。
    import inspect
    src = inspect.getsource(app.update_application_statuses_batch)
    for col in ['人才狀態更新日', '推薦主管', '推薦日']:
        assert col in src, f"寄信路徑沒有寫入「{col}」，待催辦會算不出來"
    assert 'recommended_to' in src


# ── 8. 推薦信改走 GAS 郵件轉發（2026-08-13）──────────────────────────

def test_推薦信不再依賴smtp帳密():
    # 2026-08-13：從 smtplib+app_password 改成呼叫 GAS Web App，因為
    # (1) 明文 SMTP 密碼有外洩風險（本專案就真的中過一次，見 .gitignore 的
    #     email_config.json* 規則），(2) 使用者想用公司信箱寄信但良興
    # Workspace 是否開放應用程式密碼不確定，GAS 端用 MailApp 不需要密碼。
    # 檢查真正的呼叫（不是字面文字）——函式的 docstring 本身會提到
    # smtplib（解釋改動歷史），字串比對會被自己的說明文字誤判。
    assert not hasattr(app, 'smtplib'), "app.py 不該再 import smtplib"
    import inspect
    src = inspect.getsource(app.send_recommendation_email)
    assert 'smtplib.SMTP' not in src, "推薦信不該再依賴 SMTP 帳密"
    assert 'relay_url' in src and 'relay_secret' in src
    assert 'requests.post' in src


def test_推薦信會帶密鑰白名單與附件base64():
    # 鎖住轉發服務的請求格式：少了任何一個欄位，GAS 端的驗證/白名單/附件
    # 邏輯就會對不上（見 outputs/scripts/lx-hireflow-mail-relay/Code.gs）。
    import inspect
    src = inspect.getsource(app.send_recommendation_email)
    for key in ['"secret"', '"to"', '"subject"', '"body"', '"cc"', '"attachments"']:
        assert key in src, f"payload 缺少 {key}，GAS 端會收不到或驗證失敗"
    assert 'base64.b64encode' in src
    assert "result.get('ok')" in src, "沒檢查 GAS 回應的 ok 欄位，寄信失敗會被當成成功"
