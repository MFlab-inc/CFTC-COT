# -*- coding: utf-8 -*-
"""週次更新: CFTC公式 deafut.txt（最新週・Legacy Futures-Only）を取り込む。

冪等設計:
  - 既に保存済みの週なら「変更なし」で正常終了（exit 0）
  - 新しい週が含まれていれば各銘柄CSVに追記し cot-feed.json を再生成
実行タイミング（workflow 側）:
  COT公表は通常 米国時間 金曜 15:30 ET（= JST 土曜 4:30/5:30）。
  cron は 土曜 00:30 UTC（JST 9:30）と、祝日順延の取りこぼし用に
  火曜 00:30 UTC の週2回。ファイル内の as-of 日付で判定するため
  何度実行しても安全。
"""

import sys

from symbols import SYMBOLS, code_map
from cot_common import (
    WEEKLY_URL, http_get, parse_legacy_lines, to_feed_row,
    read_symbol_csv, write_symbol_csv, build_feed_json,
)


def main():
    cmap = code_map()
    raw = http_get(WEEKLY_URL)
    text = raw.decode("utf-8", errors="replace")
    recs = parse_legacy_lines(text, set(cmap.keys()))
    if not recs:
        print("ERROR: no target rows found in %s" % WEEKLY_URL)
        return 1

    report_date = max(r["date"] for r in recs)
    print("weekly file as-of date: %s / matched rows: %d" % (report_date, len(recs)))

    changed = False
    for sym in SYMBOLS:
        my = [r for r in recs if cmap.get(r["code"], {}).get("slug") == sym["slug"]]
        if not my:
            print("  [%s] not present in this week's file (code %s)" % (sym["slug"], sym["code"]))
            continue
        # 同一銘柄に複数行は想定しないが、あれば主コード優先
        rec = sorted(my, key=lambda r: 0 if r["code"] == sym["code"] else 1)[0]
        row = to_feed_row(rec, sym["sign_invert"])
        rows = read_symbol_csv(sym["slug"])
        prev = rows.get(row["date"])
        if prev == row:
            print("  [%s] %s already up to date (net=%d)" % (sym["slug"], row["date"], row["net"]))
            continue
        rows[row["date"]] = row
        write_symbol_csv(sym["slug"], rows)
        changed = True
        print("  [%s] %s written: all=%d long=%d short=%d net=%d"
              % (sym["slug"], row["date"], row["all"], row["long"], row["short"], row["net"]))

    if changed:
        build_feed_json(SYMBOLS, generated_note="weekly update from %s" % WEEKLY_URL)
        print("cot-feed.json regenerated")
    else:
        print("no changes; feed json untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
