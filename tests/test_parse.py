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

    print("ALL TESTS PASSED")
    print("  usdjpy 2026-07-21:", row)
    print("  audusd 2026-07-21:", row2)


if __name__ == "__main__":
    main()
