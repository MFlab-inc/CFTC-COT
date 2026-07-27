# -*- coding: utf-8 -*-
"""履歴バックフィル: CFTC公式の年次ZIP（Legacy Futures-Only）から全履歴を再構築する。

  URL形式: https://www.cftc.gov/files/dea/history/deacot{YYYY}.zip
  （HistoricalCompressed 公式ページで 1986〜2026 の全年リンクを確認済み。
    404 になった年は公式ページで最新のリンクを確認すること。）

使い方:
  python scripts/backfill.py --start-year 2005            # 2005〜今年
  python scripts/backfill.py --start-year 2005 --end-year 2010

注意:
  - 既存CSVは同日付の行を上書きする（公式値で常に置き換え）
  - Consolidated系（13874+ / 12460+）はコード導入前の週が欠測になる。
    実行後に出力される coverage レポートで各銘柄の開始日を確認すること。
"""

import argparse
import io
import sys
import zipfile
from datetime import date

from symbols import SYMBOLS, code_map
from cot_common import (
    HISTORY_ZIP_URL, http_get, parse_legacy_lines, to_feed_row,
    read_symbol_csv, write_symbol_csv, build_feed_json,
)


def fetch_year_text(year):
    url = HISTORY_ZIP_URL.format(year=year)
    raw = http_get(url)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    # ZIP内のテキストファイル（通常1本: annual.txt）を全て連結
    texts = []
    for n in names:
        if n.lower().endswith(".txt"):
            texts.append(zf.read(n).decode("utf-8", errors="replace"))
    if not texts:
        raise RuntimeError("no .txt in %s (contains: %s)" % (url, names))
    return "\n".join(texts), url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=2005)
    ap.add_argument("--end-year", type=int, default=date.today().year)
    args = ap.parse_args()

    cmap = code_map()
    wanted = set(cmap.keys())

    per_symbol = {s["slug"]: read_symbol_csv(s["slug"]) for s in SYMBOLS}

    for year in range(args.start_year, args.end_year + 1):
        try:
            text, url = fetch_year_text(year)
        except Exception as e:  # noqa: BLE001
            print("WARN %d: fetch failed (%s) - skip. check %s manually" % (year, e, HISTORY_ZIP_URL.format(year=year)))
            continue
        recs = parse_legacy_lines(text, wanted)
        n = 0
        for rec in recs:
            sym = cmap[rec["code"]]
            row = to_feed_row(rec, sym["sign_invert"])
            per_symbol[sym["slug"]][row["date"]] = row
            n += 1
        print("%d: %s -> %d rows" % (year, url, n))

    print("\n=== coverage ===")
    for s in SYMBOLS:
        rows = per_symbol[s["slug"]]
        write_symbol_csv(s["slug"], rows)
        ds = sorted(rows)
        if ds:
            print("  %-10s code=%-7s %s .. %s (%d weeks)"
                  % (s["slug"], s["code"], ds[0], ds[-1], len(ds)))
        else:
            print("  %-10s code=%-7s NO DATA" % (s["slug"], s["code"]))

    build_feed_json(SYMBOLS, generated_note="backfill %d-%d from official annual zips"
                    % (args.start_year, args.end_year))
    print("cot-feed.json regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
