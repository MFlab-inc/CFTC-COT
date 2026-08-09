# -*- coding: utf-8 -*-
"""履歴バックフィル: CFTC公式の年次ZIP（Legacy Futures-Only / TFF）から全履歴を再構築する。

  Legacy: https://www.cftc.gov/files/dea/history/deacot{YYYY}.zip
  TFF   : https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip（2006-2016）
          https://www.cftc.gov/files/dea/history/fut_fin_txt_{YYYY}.zip（2017〜）
  （HistoricalCompressed 公式ページで 1986〜2026 の全年リンクを確認済み。
    404 になった年は公式ページで最新のリンクを確認すること。）

使い方:
  python scripts/backfill.py --start-year 2005            # 2005〜今年
  python scripts/backfill.py --start-year 2005 --end-year 2010
  python scripts/backfill.py --start-year 2005 --allow-partial   # 取得失敗を許容（下記）

マージ規則（Legacy・TFF共通）:
  - 既存CSVの行は**常に保持**する。取得できた週だけを同じ日付で上書きする
  - したがって start_year / end_year は「**どの年のZIPを取りに行くか**」だけを
    決める。範囲外の既存データが削られることはない
  - 週数が減る結果になった場合はバグとみなし、**書き込みを中止して異常終了**する

終了コード:
  0 = 全URL取得成功・週数の減少なし
  1 = 取得失敗あり（--allow-partial 指定時を除く）／週数が減少（常に異常）
  ※ ワークフローは python が異常終了すると commit ステップを飛ばすため、
    中途半端なデータがリポジトリに入らない。

注意:
  - Consolidated系（13874+ / 12460+）はコード導入前の週が欠測になる。
    実行後に出力される coverage レポートで各銘柄の開始日を確認すること。
"""

import argparse
import io
import sys
import time
import zipfile
from datetime import date

from symbols import SYMBOLS, code_map
from cot_common import (
    HISTORY_ZIP_URL, TFF_HIST_COMBINED_URL, TFF_HIST_YEAR_URL,
    http_get, parse_legacy_lines, to_feed_row,
    read_symbol_csv, write_symbol_csv, build_feed_json,
    parse_tff_lines, to_tff_row, read_tff_csv, write_tff_csv,
)

# TFF統合ZIPが収録する期間。start/end がこの範囲に掛かるときだけ取得する
# （掛からないのに毎回ダウンロードすると、大きいファイルを取って捨てるだけになる）
TFF_COMBINED_FIRST_YEAR = 2006
TFF_COMBINED_LAST_YEAR = 2016


def fetch_zip_text(url):
    # 統合ZIP(2006-2016)は年次ZIPよりサイズが大きいためタイムアウトを長めに設定
    raw = http_get(url, timeout=300, retries=3, backoff=8)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    texts = []
    for n in names:
        if n.lower().endswith(".txt"):
            texts.append(zf.read(n).decode("utf-8", errors="replace"))
    if not texts:
        raise RuntimeError("no .txt in %s (contains: %s)" % (url, names))
    return "\n".join(texts), url


def fetch_year_text(year):
    return fetch_zip_text(HISTORY_ZIP_URL.format(year=year))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=2005)
    ap.add_argument("--end-year", type=int, default=date.today().year)
    ap.add_argument("--allow-partial", action="store_true",
                    help="一部URLの取得に失敗しても正常終了する（既定は異常終了）。"
                         "公式から恒久的に削除された年がある場合のみ使う")
    args = ap.parse_args()

    t0 = time.monotonic()
    failures = []       # [(区分, URL, エラー文字列)]
    total_bytes = 0

    cmap = code_map()
    wanted = set(cmap.keys())

    per_symbol = {s["slug"]: read_symbol_csv(s["slug"]) for s in SYMBOLS}
    before_legacy = {k: len(v) for k, v in per_symbol.items()}

    for year in range(args.start_year, args.end_year + 1):
        try:
            text, url = fetch_year_text(year)
        except Exception as e:  # noqa: BLE001
            url = HISTORY_ZIP_URL.format(year=year)
            print("WARN %d: fetch failed (%s: %s) - skip. check %s manually"
                  % (year, type(e).__name__, e, url))
            failures.append(("legacy", url, "%s: %s" % (type(e).__name__, e)))
            continue
        total_bytes += len(text)
        recs = parse_legacy_lines(text, wanted)
        n = 0
        for rec in recs:
            sym = cmap[rec["code"]]
            row = to_feed_row(rec, sym["sign_invert"])
            per_symbol[sym["slug"]][row["date"]] = row
            n += 1
        print("%d: %s -> %d rows (%d bytes)" % (year, url, n, len(text)))
        if n == 0:
            # 取得は成功したのにマッチ0件 = パーサ側の異常（§6-1と同じ症状）
            failures.append(("legacy", url, "fetched OK but matched 0 rows"))
            print("WARN %d: fetched OK but matched 0 target rows - parser issue?" % year)

    # --- TFF履歴（2006-06-13〜: 統合ZIP + 2017年以降の年次ZIP） ---
    tff_syms = [s for s in SYMBOLS if s.get("tff")]
    tff_by_code = {s["code"]: s for s in tff_syms}
    tff_codes = set(tff_by_code)
    tff_rows = {s["slug"]: read_tff_csv(s["slug"]) for s in tff_syms}
    before_tff = {k: len(v) for k, v in tff_rows.items()}

    tff_urls = []
    if (args.start_year <= TFF_COMBINED_LAST_YEAR
            and args.end_year >= TFF_COMBINED_FIRST_YEAR):
        tff_urls.append(TFF_HIST_COMBINED_URL)
    tff_urls += [TFF_HIST_YEAR_URL.format(year=y)
                 for y in range(max(2017, args.start_year), args.end_year + 1)]

    for url in tff_urls:
        try:
            text, _ = fetch_zip_text(url)
        except Exception as e:  # noqa: BLE001
            print("WARN tff: fetch failed %s (%s: %s) - skip"
                  % (url, type(e).__name__, e))
            failures.append(("tff", url, "%s: %s" % (type(e).__name__, e)))
            continue
        total_bytes += len(text)
        recs = parse_tff_lines(text, tff_codes)
        n = 0
        for rec in recs:
            sym = tff_by_code.get(rec["code"])
            if sym is None:
                continue
            tff_rows[sym["slug"]][rec["date"]] = to_tff_row(rec, sym["sign_invert"])
            n += 1
        print("tff: %s -> %d rows (%d bytes)" % (url, n, len(text)))
        if n == 0:
            failures.append(("tff", url, "fetched OK but matched 0 rows"))
            print("WARN tff: fetched OK but matched 0 target rows - parser issue? (%s)" % url)

    # --- 書き込み前のガード: 週数が減る結果は常にバグとして扱う ---
    shrunk = []
    for s in SYMBOLS:
        n_before, n_after = before_legacy[s["slug"]], len(per_symbol[s["slug"]])
        if n_after < n_before:
            shrunk.append(("legacy", s["slug"], n_before, n_after))
    for s in tff_syms:
        n_before, n_after = before_tff[s["slug"]], len(tff_rows[s["slug"]])
        if n_after < n_before:
            shrunk.append(("tff", s["slug"], n_before, n_after))
    if shrunk:
        print("\n=== health ===")
        print("  FATAL: 週数が減少しました。データ消失を防ぐため書き込みを中止します。")
        for kind, slug, b, a in shrunk:
            print("    %-6s %-10s %d -> %d weeks (-%d)" % (kind, slug, b, a, b - a))
        print("  CSVは一切変更していません。マージ処理を確認してください。")
        return 1

    for s in tff_syms:
        write_tff_csv(s["slug"], tff_rows[s["slug"]])

    print("\n=== coverage ===")
    for s in SYMBOLS:
        rows = per_symbol[s["slug"]]
        write_symbol_csv(s["slug"], rows)
        ds = sorted(rows)
        if ds:
            print("  %-10s code=%-7s %s .. %s (%d weeks, %+d)"
                  % (s["slug"], s["code"], ds[0], ds[-1], len(ds),
                     len(ds) - before_legacy[s["slug"]]))
        else:
            print("  %-10s code=%-7s NO DATA" % (s["slug"], s["code"]))
    print("=== tff coverage ===")
    for s in tff_syms:
        ds = sorted(tff_rows[s["slug"]])
        if ds:
            print("  %-10s tff %s .. %s (%d weeks, %+d)"
                  % (s["slug"], ds[0], ds[-1], len(ds),
                     len(ds) - before_tff[s["slug"]]))
        else:
            print("  %-10s tff NO DATA" % s["slug"])

    build_feed_json(SYMBOLS, generated_note="backfill %d-%d from official annual zips"
                    % (args.start_year, args.end_year))
    print("cot-feed.json regenerated")

    # --- health: 「失敗が緑✅で通る」を防ぐための最終判定（§6-2 / §6-3）---
    elapsed = time.monotonic() - t0
    empty_legacy = [s["slug"] for s in SYMBOLS if not per_symbol[s["slug"]]]
    empty_tff = [s["slug"] for s in tff_syms if not tff_rows[s["slug"]]]
    print("\n=== health ===")
    print("  urls attempted : %d (legacy %d + tff %d)"
          % (args.end_year - args.start_year + 1 + len(tff_urls),
             args.end_year - args.start_year + 1, len(tff_urls)))
    print("  fetch failures : %d" % len(failures))
    print("  downloaded     : %.1f MB" % (total_bytes / 1024 / 1024))
    print("  elapsed        : %.1f sec" % elapsed)
    print("  empty symbols  : legacy=%s tff=%s"
          % (empty_legacy or "none", empty_tff or "none"))
    for kind, url, err in failures:
        print("    FAIL %-6s %s  (%s)" % (kind, url, err))
    if empty_legacy:
        print("  FATAL: Legacy側に0週の銘柄があります: %s" % empty_legacy)
    if failures or empty_legacy:
        if args.allow_partial and not empty_legacy:
            print("  RESULT: DEGRADED (--allow-partial のため正常終了扱い)")
            return 0
        print("  RESULT: FAILED - このrunは失敗として扱われ、data/ はcommitされません。")
        print("          原因を解消してから backfill-history を再実行してください。")
        print("          公式から恒久的に消えた年が原因の場合のみ allow_partial を有効にします。")
        return 1
    print("  RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
