import glob
import json
import re

RE_YYYYMMDD = re.compile(r'(20\d{2})(\d{2})(\d{2})')
RE_MMDD = re.compile(r'(?<!\d)(\d{2})(\d{2})(?!\d)')
RE_FOLDER_DOT = re.compile(r'(20\d{2})\.(\d{2})')
RE_FOLDER_PLAIN = re.compile(r'(20\d{2})(\d{2})(?!\d)')


def extract_date(src_path):
    if not src_path:
        return None
    basename = src_path.replace('\\', '/').split('/')[-1]
    if RE_YYYYMMDD.search(basename):
        return 'day'
    if RE_MMDD.search(basename):
        return 'day'
    for part in src_path.replace('\\', '/').split('/')[:-1]:
        if RE_FOLDER_DOT.search(part) or RE_FOLDER_PLAIN.search(part):
            return 'month'
    if RE_FOLDER_DOT.search(basename) or RE_FOLDER_PLAIN.search(basename):
        return 'month'
    return None


nomatch = []
for fp in glob.glob('resume_library/*.json'):
    if fp.endswith('.bak'):
        continue
    d = json.load(open(fp, encoding='utf-8'))
    for c in d.get('candidates', []):
        src = c.get('來源檔案', '')
        code = c.get('104代碼', '')
        if extract_date(src) is None:
            nomatch.append((code, src))

print('抓不到日期:', len(nomatch))
for code, src in nomatch[:25]:
    print(code, '|', src)
