# -*- coding: utf-8 -*-
"""一時調査スクリプト: CFTC週次ファイルにクロス円等の銘柄が単独コードで
存在するかを検索する。EUR/JPY追加要否の判断材料。用が済み次第削除する。
"""
import sys
sys.path.insert(0, "scripts")
from cot_common import http_get, WEEKLY_URL, TFF_WEEKLY_URL  # noqa: E402

KEYWORDS = ["JPY", "YEN", "EURO", "XRATE", "CROSS", "STERLING", "POUND", "AUSTRALIAN", "CANADIAN", "SWISS"]


def scan(url, label):
    text = http_get(url).decode("utf-8", errors="replace")
    print("=== %s (%s) ===" % (label, url))
    seen = {}
    for line in text.splitlines():
        upper = line.upper()
        if any(k in upper for k in KEYWORDS):
            parts = line.split('","')
            name = parts[0].strip('"') if parts else line[:80]
            code = parts[3].strip('"') if len(parts) > 3 else "?"
            seen[name] = code
    for name in sorted(seen):
        print("  %-55s code=%s" % (name, seen[name]))
    print("  (%d unique names)" % len(seen))


scan(WEEKLY_URL, "Legacy weekly (deafut.txt)")
print()
scan(TFF_WEEKLY_URL, "TFF weekly (FinFutWk.txt)")
