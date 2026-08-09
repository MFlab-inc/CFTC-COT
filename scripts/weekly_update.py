# -*- coding: utf-8 -*-
"""週次更新: CFTC公式 deafut.txt / FinFutWk.txt（最新週）を取り込む。

冪等設計:
  - 既に保存済みの週なら「変更なし」で正常終了（exit 0）
  - 新しい週が含まれていれば各銘柄CSVに追記し cot-feed.json を再生成
実行タイミング（workflow 側）:
  COT公表は通常 米国時間 金曜 15:30 ET（= JST 土曜 4:30/5:30）。
  cron は 土曜 00:30 UTC（JST 9:30）と、祝日順延の取りこぼし用に
  火曜 00:30 UTC の週2回。ファイル内の as-of 日付で判定するため
  何度実行しても安全。

終了コードと degraded 判定:
  Legacy取得の失敗は例外／exit 1 でそのまま失敗させる（データが無いので当然）。
  一方 TFF取得の失敗や鮮度異常では **exit 0 のまま**にする。ここで異常終了すると
  ワークフローのcommitステップが飛び、せっかく取れたLegacyの最新週まで
  捨ててしまうため。代わりに GITHUB_OUTPUT に degraded=1 を書き出し、
  ワークフロー側が「commitした後で」runを赤くする（§6-2/§6-3 対策）。
"""

import os
import sys
from datetime import date

from symbols import SYMBOLS, code_map
from cot_common import (
    WEEKLY_URL, TFF_WEEKLY_URL, http_get, parse_legacy_lines, to_feed_row,
    read_symbol_csv, write_symbol_csv, build_feed_json,
    parse_tff_lines, to_tff_row, read_tff_csv, write_tff_csv,
)

# 締め日（火曜）からこの日数を超えて古いデータしか取れていない場合は鮮度異常とみなす。
# 通常は土曜run=4日・火曜run=7日。米祝日で公表が順延しても10日程度に収まるため、
# 14日を超えるのはCDNキャッシュ滞留か公表停止を疑うべき水準。
STALE_AFTER_DAYS = 14


def _emit(problems):
    """GitHub Actions のログ注釈と step output を出す。ローカル実行では無害。"""
    for p in problems:
        print("::warning title=COT feed degraded::%s" % p)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write("degraded=%d\n" % (1 if problems else 0))
            f.write("degraded_reason=%s\n" % (" / ".join(problems) if problems else ""))


def main():
    cmap = code_map()
    raw = http_get(WEEKLY_URL)
    text = raw.decode("utf-8", errors="replace")
    recs = parse_legacy_lines(text, set(cmap.keys()))
    if not recs:
        print("ERROR: no target rows found in %s" % WEEKLY_URL)
        _emit(["Legacy週次ファイルから対象銘柄が1件も取れませんでした（パーサ異常の疑い）"])
        return 1

    report_date = max(r["date"] for r in recs)
    print("weekly file as-of date: %s / matched rows: %d" % (report_date, len(recs)))

    problems = []
    changed = False
    missing_legacy = []
    for sym in SYMBOLS:
        my = [r for r in recs if cmap.get(r["code"], {}).get("slug") == sym["slug"]]
        if not my:
            print("  [%s] not present in this week's file (code %s)" % (sym["slug"], sym["code"]))
            missing_legacy.append(sym["slug"])
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

    # --- TFF（金融先物のみ: AM / Leveraged Funds） ---
    tff_syms = [x for x in SYMBOLS if x.get("tff")]
    tff_codes = {x["code"] for x in tff_syms}
    missing_tff = []
    try:
        tff_text = http_get(TFF_WEEKLY_URL).decode("utf-8", errors="replace")
        tff_recs = parse_tff_lines(tff_text, tff_codes)
        print("TFF file rows matched: %d" % len(tff_recs))
        if not tff_recs:
            problems.append("TFF週次ファイルから対象銘柄が1件も取れませんでした（パーサ異常の疑い）")
        for sym in tff_syms:
            my = [r for r in tff_recs if r["code"] == sym["code"]]
            if not my:
                print("  [%s/tff] not present this week" % sym["slug"])
                missing_tff.append(sym["slug"])
                continue
            row = to_tff_row(my[0], sym["sign_invert"])
            rows = read_tff_csv(sym["slug"])
            if rows.get(row["date"]) == row:
                print("  [%s/tff] %s already up to date (am_net=%d lev_net=%d)"
                      % (sym["slug"], row["date"], row["am_net"], row["lev_net"]))
                continue
            rows[row["date"]] = row
            write_tff_csv(sym["slug"], rows)
            changed = True
            print("  [%s/tff] %s written: am_net=%d lev_net=%d"
                  % (sym["slug"], row["date"], row["am_net"], row["lev_net"]))
    except Exception as e:  # noqa: BLE001
        print("WARN: TFF fetch failed (%s: %s) - legacy data is unaffected"
              % (type(e).__name__, e))
        problems.append("TFF取得に失敗しました（%s）。Legacyは正常に更新されています" % type(e).__name__)

    if changed:
        build_feed_json(SYMBOLS, generated_note="weekly update from %s" % WEEKLY_URL)
        print("cot-feed.json regenerated")
    else:
        print("no changes; feed json untouched")

    # --- health: 取り込み後の鮮度・整合チェック（§6-3 対策）---
    #
    # 判定は「その週に居たかどうか」ではなく「保存済みデータが古びていないか」で行う。
    # CFTCは報告トレーダーが20者未満の銘柄をその週だけ除外することがあり（§3）、
    # 1週の欠席で赤くすると毎回オオカミ少年になる。一方でコードが恒久的に
    # 廃止・変更された場合は数週で鮮度異常として必ず表面化する。
    today = date.today()

    def _stale(latest_iso):
        if latest_iso is None:
            return None
        return (today - date.fromisoformat(latest_iso)).days

    print("\n=== health ===")
    age = _stale(report_date)
    print("  legacy as-of   : %s (%d days old)" % (report_date, age))
    if age > STALE_AFTER_DAYS:
        problems.append("Legacyの最新データが%d日前です（%s）。CDNキャッシュ滞留か公表停止の疑い"
                        % (age, report_date))
    if missing_legacy:
        print("  legacy absent  : %s（今週のみなら正常。鮮度で判定する）" % missing_legacy)
    if missing_tff:
        print("  tff absent     : %s（同上）" % missing_tff)

    # 銘柄ごとに許容日数を変えられる。CFTCが報告者20者未満の週を除外するため、
    # 建玉の薄い銘柄は長期欠測が正常挙動になる（eurjpy: 在席率51%・最長61週）。
    # 一律14日で判定すると、そういう銘柄を持った瞬間に毎週赤くなってしまう。
    stale_syms = []
    for s in SYMBOLS:
        limit = s.get("max_stale_days", STALE_AFTER_DAYS)
        ds = sorted(read_symbol_csv(s["slug"]))
        d = _stale(ds[-1] if ds else None)
        if d is None or d > limit:
            stale_syms.append("%s(legacy:%s/%d日超)" % (s["slug"], ds[-1] if ds else "NO DATA", limit))
    tff_dates = []
    for s in tff_syms:
        limit = s.get("max_stale_days", STALE_AFTER_DAYS)
        ds = sorted(read_tff_csv(s["slug"]))
        tff_dates.append(ds[-1] if ds else None)
        d = _stale(ds[-1] if ds else None)
        if d is None or d > limit:
            stale_syms.append("%s(tff:%s/%d日超)" % (s["slug"], ds[-1] if ds else "NO DATA", limit))
    print("  tff as-of      : %s" % sorted(set(v for v in tff_dates if v)))
    thin = [s["slug"] for s in SYMBOLS if s.get("max_stale_days")]
    if thin:
        print("  thin symbols   : %s（長期欠測が正常。許容日数を個別設定）" % thin)
    if stale_syms:
        problems.append("許容日数を超えて更新されていない系列: %s" % ", ".join(stale_syms))

    print("  RESULT: %s" % ("DEGRADED" if problems else "OK"))
    for p in problems:
        print("    - %s" % p)
    _emit(problems)
    return 0


if __name__ == "__main__":
    sys.exit(main())
