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
