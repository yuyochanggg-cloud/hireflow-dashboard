# -*- coding: utf-8 -*-
"""
一次性比對腳本：同一批已篩過的履歷，分別用 gemini-3.5-flash（現行主力）
與 gemini-3.6-flash（候選新版）重新跑一次評分，比對「初篩判定」「等第」是否一致。

不寫回任何正式資料（cache_db / resume_library / Sheets 全部不動），
純粹讀取既有 resume_library 的履歷原文與 jd_profiles.json 的職缺條件，
呼叫 Gemini API 後印出比對結果到終端機。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JD_NAME = "三創晚班計時員"
SAMPLE_SIZE = 20
MODELS = ["gemini-3.5-flash", "gemini-3.6-flash"]

GSHEET_ID_FILE = os.path.join(BASE_DIR, "gsheet_config.json")


def compute_weighted_grade(data, active_dims):
    weight_map = {
        d.get('dimension'): float(d.get('weight') or 0)
        for d in (active_dims or [])
        if d.get('dimension')
    }
    dyn = data.get('dynamic_scores') or []
    wsum = sum(weight_map.values())
    if not dyn or wsum <= 0:
        return data
    total = 0.0
    matched_w = 0.0
    for d in dyn:
        dim = d.get('dimension', '')
        if dim not in weight_map:
            continue
        try:
            sc = float(str(d.get('score', 0)).strip())
        except (ValueError, TypeError):
            sc = 0.0
        total += sc * weight_map[dim]
        matched_w += weight_map[dim]
    if matched_w <= 0:
        return data
    total = total / matched_w
    if str(data.get('初篩判定', '')).strip() == '不合格':
        grade = 'C'
    elif total >= 8:
        grade = 'A'
    elif total >= 6:
        grade = 'B'
    else:
        grade = 'C'
    data['加權總分'] = round(total, 2)
    data['綜合推薦度'] = grade
    if grade == 'C':
        data['初篩判定'] = '不合格'
    return data


def extract_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        decoder = json.JSONDecoder()
        start = text.find('{')
        if start != -1:
            obj, _ = decoder.raw_decode(text, start)
            return obj
    except Exception:
        pass
    return None


def get_client():
    gcp_project = ''
    if os.path.exists(GSHEET_ID_FILE):
        try:
            with open(GSHEET_ID_FILE, 'r', encoding='utf-8') as f:
                gcp_project = json.load(f).get('gcp_project_id', '')
        except Exception:
            pass
    return genai.Client(enterprise=True, project=gcp_project, location='global')


def ask_gemini_json(client, model, prompt, retries=3):
    for attempt in range(retries):
        try:
            cfg = types.GenerateContentConfig(response_mime_type="application/json")
            if model.startswith("gemini-3"):
                cfg.thinking_config = types.ThinkingConfig(thinking_level="low")
            resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
            return resp.text
        except Exception as e:
            msg = str(e)
            if ("429" in msg or "503" in msg) and attempt < retries - 1:
                time.sleep(8)
                continue
            return f"FATAL_API_ERROR: {msg}"
    return "FATAL_API_ERROR: 重試耗盡"


def main():
    with open(os.path.join(BASE_DIR, "jd_profiles.json"), encoding="utf-8") as f:
        jd = json.load(f)[JD_NAME]

    with open(os.path.join(BASE_DIR, "prompts", "scoring.txt"), encoding="utf-8") as f:
        template = f.read()

    with open(os.path.join(BASE_DIR, "resume_library", f"{JD_NAME}.json"), encoding="utf-8") as f:
        lib = json.load(f)

    candidates = [c for c in lib["candidates"] if c.get("履歷原文")][:SAMPLE_SIZE]
    print(f"抽樣 {len(candidates)} 位候選人（職缺：{JD_NAME}）")

    client = get_client()
    dim_names = [d["dimension"] for d in jd["dimensions"]]

    rows = []
    for i, cand in enumerate(candidates):
        prompt = template.format(
            today=time.strftime('%Y/%m/%d'),
            active_must=jd["must"], active_nice=jd["nice"], dim_names=dim_names,
            safe_res=cand.get("居住地", "未知"), active_loc=jd["location"],
            safe_resume=cand["履歷原文"],
        )
        row = {"姓名": cand.get("真實姓名", f"候選人{i+1}"),
               "現行(3.5)判定": cand.get("初篩判定"), "現行(3.5)等第": cand.get("綜合推薦度")}
        for model in MODELS:
            res = ask_gemini_json(client, model, prompt)
            if "FATAL_API_ERROR" in res:
                row[f"{model}_判定"] = "ERROR"
                row[f"{model}_等第"] = res[:80]
                continue
            data = extract_json(res) or {}
            compute_weighted_grade(data, jd["dimensions"])
            row[f"{model}_判定"] = data.get("初篩判定", "解析失敗")
            row[f"{model}_等第"] = data.get("綜合推薦度", "?")
            row[f"{model}_分數"] = data.get("加權總分", "?")
        rows.append(row)
        print(f"[{i+1}/{len(candidates)}] {row}")

    out_path = os.path.join(BASE_DIR, "scripts", "model_compare_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n完整結果已存到 {out_path}")

    # 摘要：跟現行 3.5-flash 判定不一致的筆數
    mismatch = [r for r in rows if r.get("gemini-3.6-flash_判定") not in (r["現行(3.5)判定"], "ERROR")]
    print(f"\n=== 摘要 ===\n總數：{len(rows)}，與現行3.5判定不一致：{len(mismatch)}")
    for r in mismatch:
        print(f"  - {r['姓名']}：現行={r['現行(3.5)判定']} → 3.6={r.get('gemini-3.6-flash_判定')}")


if __name__ == "__main__":
    main()
