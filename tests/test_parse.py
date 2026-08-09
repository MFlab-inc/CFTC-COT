# -*- coding: utf-8 -*-
"""パーサ・符号規則の検証テスト（標準ライブラリのみ / python tests/test_parse.py で実行）

フィクスチャの根拠:
  - JPY行: CFTC公式 deacmesf.htm（2026-07-21付, 07/24公表）の
    JAPANESE YEN Code-097741 実数値
    OI=423,796 / NC Long=107,590 / NC Short=259,715
  - 期待値: 既存スプレッドシート USD/JPY-data の 2026/07/21 行
    all=423796, long=259715, short=-107590, net=152125（照合一致済み）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cot_common import parse_legacy_lines, to_feed_row  # noqa: E402

FIXTURE = '\n'.join([
    # ヘッダ行（annualファイル互換）はスキップされること
    '"Market and Exchange Names","As of Date in Form YYMMDD","As of Date in Form YYYY-MM-DD","CFTC Contract Market Code",x,x,x,"Open Interest (All)",x,x',
    # 引用符内カンマを含む銘柄名の行（対象外コード）
    '"FOO, BAR - SOME EXCHANGE",260721,2026-07-21,999999,XXX ,00,999 ,  100,  10,  20,  5,  1,  2,  3,  4,  5,  6',
    # JPY 実データ相当行（数値はCFTC公式 2026-07-21 と一致）
    '"JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",260721,2026-07-21,097741,CME ,00,097 ,  423796,  107590,  259715,   18031,  254110,   99212,  379731,  376958,   44065,   46838',
    # AUD 行（非反転側の検証・値はダミー）
    '"AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",260721,2026-07-21,232741,CME ,00,232 ,  225153,   66184,  103869,    6453,  115741,   99654,  188378,  209976,   36775,   15177',
])


def main():
    recs = parse_legacy_lines(FIXTURE, {"097741", "232741"})
    assert len(recs) == 2, "expected 2 rows, got %d" % len(recs)

    jpy = [r for r in recs if r["code"] == "097741"][0]
    assert jpy["date"] == "2026-07-21"
    assert jpy["oi"] == 423796
    assert jpy["nc_long"] == 107590
    assert jpy["nc_short"] == 259715

    row = to_feed_row(jpy, sign_invert=True)
    assert row == {"date": "2026-07-21", "all": 423796,
                   "long": 259715, "short": -107590, "net": 152125}, row

    aud = [r for r in recs if r["code"] == "232741"][0]
    row2 = to_feed_row(aud, sign_invert=False)
    assert row2["long"] == 66184 and row2["short"] == -103869
    assert row2["net"] == 66184 - 103869

    test_tff()
    test_state()
    test_tff_legacy_bulk_format()
    test_legacy_date_formats()
    test_merge_preserves_history()
    test_symbols_and_dashboard_in_sync()
    print("ALL TESTS PASSED")
    print("  usdjpy 2026-07-21:", row)
    print("  audusd 2026-07-21:", row2)




# ============================================================
# TFF テスト（v1.1）
# フィクスチャの根拠: CFTC公式 FinFutWk.txt 実データ（2026-07-07行、2026-07-27取得）
#   JAPANESE YEN: OI=398,103 / AM L=74,113 S=122,766 / Lev L=84,990 S=175,073
#   （恒等式 ΣL+ΣSpread+NonRept L = OI の成立を確認済みの行）
# ============================================================

TFF_FIXTURE = '\n'.join([
    '"JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",260707,2026-07-07,097741,CME ,00,097 ,  398103,  108938,   21659,    3379,   74113,  122766,   24861,   84990,  175073,    2463,   54132,    3630,    1784,  354660,  355615,   43443,   42488',
    '"AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",260707,2026-07-07,232741,CME ,00,232 ,  204837,   43854,   52266,     513,   52455,   89758,    5978,   59300,   29617,    6045,    2677,     500,       0,  170822,  184677,   34015,   20160',
])


def test_tff():
    from cot_common import parse_tff_lines, to_tff_row
    recs = parse_tff_lines(TFF_FIXTURE, {"097741", "232741"})
    assert len(recs) == 2, recs

    jpy = [r for r in recs if r["code"] == "097741"][0]
    assert jpy["oi"] == 398103
    assert jpy["am_l"] == 74113 and jpy["am_s"] == 122766
    assert jpy["lev_l"] == 84990 and jpy["lev_s"] == 175073

    row = to_tff_row(jpy, sign_invert=True)
    # USD/JPY方向: AMの円ショート122,766がam_long、円ロング74,113が負のam_short
    assert row["am_long"] == 122766 and row["am_short"] == -74113
    assert row["am_net"] == 48653
    assert row["lev_long"] == 175073 and row["lev_short"] == -84990
    assert row["lev_net"] == 90083
    assert row["all"] == 398103

    aud = [r for r in recs if r["code"] == "232741"][0]
    row2 = to_tff_row(aud, sign_invert=False)
    assert row2["am_long"] == 52455 and row2["am_short"] == -89758
    assert row2["am_net"] == 52455 - 89758
    assert row2["lev_long"] == 59300 and row2["lev_short"] == -29617
    assert row2["lev_net"] == 29683

    print("TFF TESTS PASSED")
    print("  usdjpy tff 2026-07-07:", {k: row[k] for k in ("am_net", "lev_net")})
    print("  audusd tff 2026-07-07:", {k: row2[k] for k in ("am_net", "lev_net")})




def test_state():
    """v1.2 状態判定の検証（仮置き閾値: extreme 10/90, biased 25/75, 4週勢い, LevFクロス8週）"""
    from cot_common import (percentile_of_last, classify_bias,
                            momentum_state, tff_alignment)
    assert percentile_of_last(list(range(1, 101))) == 100.0
    assert percentile_of_last(list(range(100, 0, -1))) == 1.0
    assert classify_bias(10) == "extreme" and classify_bias(90) == "extreme"
    assert classify_bias(25) == "biased" and classify_bias(75) == "biased"
    assert classify_bias(50) == "neutral" and classify_bias(10.1) == "biased"
    d, l = momentum_state([10, 20, 30, 40, 50, 60])
    assert d == 40 and l == "ロング積み増し"
    d, l = momentum_state([-60, -50, -40, -30, -20, -10])
    assert d == 40 and l == "ショート縮小"
    s, _ = tff_alignment([50] * 10, [30] * 10)
    assert s == "aligned"
    s, w = tff_alignment([50] * 10, [5, 4, 3, 2, 1, -1, -2, -3, -4, -5])
    assert s == "divergence_warning" and w is not None
    s, _ = tff_alignment([50] * 30, [-9] * 30)
    assert s == "mixed"
    print("STATE TESTS PASSED")




def test_tff_legacy_bulk_format():
    """TFF統合ZIP(2006-2016)専用の実データ形式を回帰防止として固定化。
    根拠: 2026-07-27にしょうさんが貼った実際のバックフィルログのDIAG出力
    （CANADIAN DOLLAR行, MM/DD/YYYY形式・小数表記のOI等）から採取したパターン。
    """
    from cot_common import parse_tff_lines, to_tff_row, _normalize_date, _to_int

    assert _normalize_date('"Report_Date_as_YYYY-MM-DD"') is None
    assert _normalize_date("2026-07-21") == "2026-07-21"
    assert _normalize_date("12/27/2016 12:00:00 AM") == "2016-12-27"
    assert _to_int("93212.000000") == 93212

    row = ('"JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",101019,10/19/2010 12:00:00 AM,097741,'
           'CME ,00,097 ,250000.000000,50000.000000,20000.000000,3000.000000,'
           '70000.000000,90000.000000,1000.000000,60000.000000,40000.000000,2000.000000,'
           '0,0,0,0,0,0,0,0')
    recs = parse_tff_lines(row, {"097741"})
    assert len(recs) == 1
    r = recs[0]
    assert r["date"] == "2010-10-19"
    assert r["oi"] == 250000
    assert r["am_l"] == 70000 and r["am_s"] == 90000
    assert r["lev_l"] == 60000 and r["lev_s"] == 40000

    out = to_tff_row(r, sign_invert=True)  # usdjpy相当の符号変換も一緒に確認
    assert out["am_long"] == 90000 and out["am_short"] == -70000
    assert out["lev_long"] == 40000 and out["lev_short"] == -60000

    print("TFF LEGACY BULK FORMAT TESTS PASSED")




def test_legacy_date_formats():
    """Legacyパーサも _normalize_date() を通ること（TFF側との統一・§6-1の再発防止）。

    現行のLegacyファイルは週次・年次ZIPともISO日付だが、TFF統合ZIPでは
    「ヘッダのラベルはISOなのに実データはMM/DD/YYYY」という不一致が実際に起きた。
    Legacy側でISO決め打ちのままだと、同じことが起きたとき全行スキップ＝0件になり、
    例外も出ないためワークフローは緑のまま通ってしまう。
    """
    from cot_common import parse_legacy_lines

    base = ('"JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",260721,%s,097741,'
            'CME ,00,097 ,  423796,  107590,  259715,   18031,  254110,   99212')

    # ISO（現行の実データ形式）
    recs = parse_legacy_lines(base % "2026-07-21", {"097741"})
    assert len(recs) == 1 and recs[0]["date"] == "2026-07-21", recs

    # MM/DD/YYYY（統合ZIPで実際に踏んだ形式。Legacyで出ても落とさない）
    recs = parse_legacy_lines(base % "07/21/2026 12:00:00 AM", {"097741"})
    assert len(recs) == 1 and recs[0]["date"] == "2026-07-21", recs
    assert recs[0]["oi"] == 423796 and recs[0]["nc_short"] == 259715

    # ヘッダ行は従来どおりスキップされること
    header = ('"Market and Exchange Names","As of Date in Form YYMMDD",'
              '"As of Date in Form YYYY-MM-DD","097741",x,x,x,"Open Interest (All)",x,x')
    assert parse_legacy_lines(header, {"097741"}) == []

    print("LEGACY DATE FORMAT TESTS PASSED")




def test_merge_preserves_history():
    """バックフィルのマージ規則: 既存行は必ず残り、同じ日付だけが上書きされること。

    backfill.py には以前「start_year より前のTFF行を捨てる」処理があり、
    start_year に2005以外を入れると TFF履歴が最大1,021週消える状態だった
    （Legacy側には同じ処理が無く非対称だった）。その規則を固定化する。
    """
    import shutil
    import tempfile
    import cot_common as cc
    from cot_common import (read_symbol_csv, write_symbol_csv,
                            read_tff_csv, write_tff_csv)

    tmp = tempfile.mkdtemp(prefix="cot-test-")
    orig_dir = cc.CSV_DIR
    cc.CSV_DIR = tmp
    try:
        old = {
            "2006-06-13": {"date": "2006-06-13", "all": 1, "long": 2, "short": -3, "net": -1},
            "2010-01-05": {"date": "2010-01-05", "all": 4, "long": 5, "short": -6, "net": -1},
        }
        write_symbol_csv("zz_test", dict(old))

        # backfill と同じ手順: 既存を読み → 取得分を同じ日付で上書き/追加
        rows = read_symbol_csv("zz_test")
        assert len(rows) == 2
        rows["2010-01-05"] = {"date": "2010-01-05", "all": 40, "long": 50,
                              "short": -60, "net": -10}          # 上書き
        rows["2026-08-04"] = {"date": "2026-08-04", "all": 7, "long": 8,
                              "short": -9, "net": -1}            # 追加
        write_symbol_csv("zz_test", rows)

        back = read_symbol_csv("zz_test")
        assert len(back) == 3, back
        assert back["2006-06-13"] == old["2006-06-13"], "start_year より前の行が消えた"
        assert back["2010-01-05"]["all"] == 40, "同日付が上書きされていない"

        tff_old = {"2006-06-13": {"date": "2006-06-13", "all": 1, "am_long": 2,
                                  "am_short": -3, "am_net": -1, "lev_long": 4,
                                  "lev_short": -5, "lev_net": -1}}
        write_tff_csv("zz_test", dict(tff_old))
        trows = read_tff_csv("zz_test")
        trows["2026-08-04"] = {"date": "2026-08-04", "all": 9, "am_long": 1,
                               "am_short": -1, "am_net": 0, "lev_long": 2,
                               "lev_short": -2, "lev_net": 0}
        write_tff_csv("zz_test", trows)
        tback = read_tff_csv("zz_test")
        assert len(tback) == 2, tback
        assert tback["2006-06-13"] == tff_old["2006-06-13"], "TFFの古い行が消えた"

        # 書き出しは日付昇順であること（SPEC 5-1）
        assert sorted(back) == list(back.keys()) or True
        with open(os.path.join(tmp, "zz_test.csv"), encoding="utf-8") as f:
            dates = [ln.split(",")[0] for ln in f.read().splitlines()[1:]]
        assert dates == sorted(dates), dates
    finally:
        cc.CSV_DIR = orig_dir
        shutil.rmtree(tmp, ignore_errors=True)

    print("MERGE / NO-DATA-LOSS TESTS PASSED")




def test_symbols_and_dashboard_in_sync():
    """index.html の ORDER 配列が symbols.py の SLUG_ORDER と一致していること。

    HANDOFF §8 に「銘柄追加時は ORDER への追記が必須」とあるが、従来は手作業ルール
    だったため追記漏れがあってもテストは通り、ダッシュボードにだけ出ない状態になる
    （フィードJSONには入るので気づきにくい）。ここで機械的に突き合わせる。
    """
    import re
    from symbols import SYMBOLS, SLUG_ORDER

    html_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    m = re.search(r"const ORDER = \[(.*?)\];", html, re.S)
    assert m, "index.html に ORDER 配列が見つからない"
    order = re.findall(r'"([a-z0-9_]+)"', m.group(1))

    assert order == SLUG_ORDER, (
        "index.html の ORDER と symbols.py の SLUG_ORDER が不一致。\n"
        "  index.html : %s\n  symbols.py : %s\n"
        "  ORDERにない: %s\n  SYMBOLSにない: %s"
        % (order, SLUG_ORDER,
           [s for s in SLUG_ORDER if s not in order],
           [s for s in order if s not in SLUG_ORDER]))

    # 銘柄定義の必須キーと値の妥当性もあわせて検査する
    seen_slugs, seen_codes = set(), {}
    for s in SYMBOLS:
        for key in ("slug", "label", "code", "sign_invert", "tff", "note"):
            assert key in s, "%s に %s が無い" % (s.get("slug"), key)
        assert s["slug"] not in seen_slugs, "slug重複: %s" % s["slug"]
        seen_slugs.add(s["slug"])
        assert s["code"] not in seen_codes, (
            "CFTCコード重複: %s が %s と %s に使われている"
            % (s["code"], seen_codes.get(s["code"]), s["slug"]))
        seen_codes[s["code"]] = s["slug"]
        assert isinstance(s["sign_invert"], bool)
        assert isinstance(s["tff"], bool)

    # 反転が要るのは日本円先物(097741)だけ。EUR/JPY(399741)は既にペア方向なので反転しない
    inverted = sorted(s["slug"] for s in SYMBOLS if s["sign_invert"])
    assert inverted == ["usdjpy"], "sign_invert=True は usdjpy のみのはず: %s" % inverted

    print("SYMBOLS / DASHBOARD SYNC TESTS PASSED (%d symbols)" % len(SYMBOLS))


if __name__ == "__main__":
    main()
