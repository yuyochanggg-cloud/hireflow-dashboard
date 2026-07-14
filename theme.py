"""
theme.py — app.py 與 dashboard.py 共用的視覺 design tokens 單一來源。

背景（2026-07-14 Fable設計審查）：兩個app原本各自宣告一整套獨立CSS變數，
主色（app.py藍 #1e40af / dashboard.py靛紫 #4f46e5）、字體（Plus Jakarta Sans
/ Outfit+DM Sans）互不相同，讓使用者感覺是兩個不同品牌的產品。
統一後主色採app.py的藍（原因：.streamlit/config.toml的primaryColor本來就是
這個值，Streamlit原生元件吃這個色，跟它同色最省事）；字體統一為
Plus Jakarta Sans（標題與內文同一套，內部工具不需要雙字型系統）。

兩個app各自的版面/元件CSS（候選人卡片、看板欄位等）維持在各自檔案裡，
這裡只放「顏色/字體/圓角/陰影/字級」這類跨檔共用的token。
"""
import streamlit as st

TOKENS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --c-primary:      #1e40af;
  --c-primary-dark: #1e3a8a;
  --c-primary-lite: #dbeafe;
  --c-accent:       #3b82f6;
  --c-accent-dark:  #1d4ed8;

  /* Grade 徽章顏色權威來源在 hr_schema.py 的 GRADE_META，這裡不重複定義 */

  --c-ok:  #15803d; --c-ok-bg:  #f0fdf4; --c-ok-border:  #86efac;
  --c-warn:#b45309; --c-warn-bg:#fffbeb; --c-warn-border:#fcd34d;
  --c-err: #b91c1c; --c-err-bg: #fef2f2; --c-err-border: #fca5a5;

  --c-text:       #0f172a;
  --c-text-muted: #64748b;
  --c-border:     #e2e8f0;
  --c-surface:    #f8fafc;
  --c-surface-2:  #f1f5f9;
  --c-card-bg:    #ffffff;

  /* Sidebar 深色系（兩app共用） */
  --sb-bg:       #0f172a;
  --sb-surface:  #1e293b;
  --sb-surface2: #273447;
  --sb-border:   #334155;
  --sb-text:     #e2e8f0;
  --sb-muted:    #94a3b8;

  --shadow-sm:   0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
  --shadow-md:   0 4px 14px rgba(0,0,0,.09), 0 2px 4px rgba(0,0,0,.05);
  --shadow-card: 0 0 0 1px rgba(15,23,42,.05), 0 2px 8px rgba(15,23,42,.07);
  --shadow-btn:  0 4px 14px rgba(30,64,175,.30);

  --radius:    9px;
  --radius-lg: 14px;

  --font-ui:   "Plus Jakarta Sans", "Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --font-data: "JetBrains Mono", "SF Mono", ui-monospace, monospace;

  /* Type scale：新寫的CSS請用這幾級，不要再現場發明px/rem值。
     --fs-2xs 僅限高密度圖表內部標籤（週曆/月曆/甘特），一般UI禁用。
     按鈕文字用 --fs-sm，不是 --fs-base（0.875rem跟0.85rem的差人眼分不出來，
     不留特例）。 */
  --fs-2xs:  0.65rem;
  --fs-xs:   0.75rem;
  --fs-sm:   0.85rem;
  --fs-base: 1rem;
  --fs-lg:   1.15rem;
  --fs-xl:   1.4rem;
  --fs-2xl:  1.75rem;
  /* KPI大數字專用：例外於type scale的等比級距，但仍是單一權威token，
     不得在呼叫端另外寫死數字。搭配 --font-data 使用。 */
  --fs-data: 2rem;
}

/* 標題階層：app.py跟dashboard.py共用，不再各自宣告一套不同大小 */
h1 { font-size: var(--fs-2xl) !important; }
h2 { font-size: var(--fs-xl) !important; }
h3 { font-size: var(--fs-lg) !important; }

/* 按鈕文字統一走 --fs-sm */
[data-testid="stButton"] button { font-size: var(--fs-sm) !important; }
</style>
"""

_BRAND_HEADER_TEMPLATE = """
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:10px 4px 14px;margin-bottom:6px;border-bottom:1px solid var(--c-border);">
  <div style="display:flex;align-items:baseline;gap:8px;">
    <span style="font-family:var(--font-ui);font-weight:800;font-size:var(--fs-lg);
                 color:var(--c-primary);letter-spacing:-.02em;">EcLife HR</span>
    <span style="font-family:var(--font-ui);font-weight:600;font-size:var(--fs-sm);
                 color:var(--c-text-muted);">{app_name}</span>
  </div>
</div>
"""


def inject_theme():
    """兩個app開頭都呼叫這個，注入共用的顏色/字體/圓角/陰影/字級token。"""
    st.markdown(TOKENS_CSS, unsafe_allow_html=True)


def render_brand_header(app_name: str):
    """兩app共用的品牌抬頭，讓使用者感覺這是同一套系統。"""
    st.markdown(_BRAND_HEADER_TEMPLATE.format(app_name=app_name), unsafe_allow_html=True)
