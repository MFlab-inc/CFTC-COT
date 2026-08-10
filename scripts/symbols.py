# -*- coding: utf-8 -*-
"""銘柄マスタ定義

CFTC Legacy Futures-Only レポートから抽出する銘柄と符号規則を定義する。

sign_invert:
  True  = 外貨先物の生値を「USD/JPY方向」に反転して記録する
          （long = 非商業ショート, short = -非商業ロング）
          対象: USD/JPY（日本円先物 097741）のみ。
          既存スプレッドシート「CFTC」の USD/JPY-data と同一規則
          （2026-07-21行でCFTC公式との照合一致を確認済み）。
  False = 生値のまま（long = 非商業ロング, short = -非商業ショート）

  なぜ USD/JPY だけ反転が要るか（EUR/JPY との違い・混同注意）:
    - 日本円先物(097741)は「1円=何ドル」建て。ロング=円買い=USD/JPY下落方向。
      よってUSD/JPY方向で読むには反転が必要 → sign_invert=True
    - ユーロ円クロス先物(399741)は「1ユーロ=何円」建て。ロング=ユーロ買い円売り
      =EUR/JPY上昇方向。既にペア表記と同じ向きなので反転不要 → sign_invert=False

fallback_codes:
  主コードがその週のレポートに存在しない場合に代替検索するコード。
  Consolidated系（13874+ / 12460+）は導入前の期間に主コードが存在しない
  ため、バックフィル時の網羅性確認用。既定では空（＝主コードのみ）。
  代替コードを有効化する場合は、CFTC公式で当該コードの実在と定義を
  確認してから追加すること（未検証コードの推測追加は禁止）。
"""

SYMBOLS = [
    {
        "slug": "usdjpy",
        "tff": True,
        "label": "USD/JPY",
        "code": "097741",
        "market_hint": "JAPANESE YEN",
        "sign_invert": True,
        "fallback_codes": [],
        "note": "円先物を USD/JPY 方向に符号変換。net プラス = 投機筋の円ショート優勢",
    },
    {
        "slug": "eurjpy",
        "tff": True,
        "label": "EUR/JPY",
        "code": "399741",
        "market_hint": "EURO FX/JAPANESE YEN XRATE",
        "sign_invert": False,
        "fallback_codes": [],
        # 実測(2026-08-09): 2017-08-01〜2026-08-04 の471週中238週しか存在せず
        # 在席率51%。最大の欠測は 2024-06-18→2025-08-26 の **434日(62週)**。
        # 既定の14日で鮮度警告すると毎週赤くなるため個別に緩める。
        # 434日を確実に上回る550日(約18ヶ月)とし、それを超える消失は
        # 「契約が実質的に無くなった」として通知させる。
        "max_stale_days": 550,
        "note": "CMEユーロ円クロスレート先物（1ユーロ=何円建て）。合成値ではなくCFTC公式の"
                "単独銘柄。建玉が小さく報告者20者未満の週は除外されるため欠測が多い"
                "（在席率約51%・最長61週連続欠測。coverage.present_ratio 参照）",
    },
    {
        "slug": "gbpusd",
        "tff": True,
        "label": "GBP/USD",
        "code": "096742",
        "market_hint": "BRITISH POUND",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "eurusd",
        "tff": True,
        "label": "EUR/USD",
        "code": "099741",
        "market_hint": "EURO FX",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "audusd",
        "tff": True,
        "label": "AUD/USD",
        "code": "232741",
        "market_hint": "AUSTRALIAN DOLLAR",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "sp500",
        "tff": True,
        "label": "S&P500",
        "code": "13874+",
        "market_hint": "S&P 500 Consolidated",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "Consolidated（大型+E-mini+Micro合算）。導入前の週は欠測になる",
    },
    {
        "slug": "nikkei225",
        "tff": True,
        "label": "NIKKEI225",
        "code": "240743",
        "market_hint": "NIKKEI STOCK AVERAGE YEN DENOM",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "円建て日経平均先物（CME）",
    },
    {
        "slug": "nydow",
        "tff": True,
        "label": "NYダウ",
        "code": "12460+",
        "market_hint": "DJIA Consolidated",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "Consolidated。導入前の週は欠測になる",
    },
    {
        "slug": "wti",
        "tff": False,
        "label": "WTI原油",
        "code": "067651",
        # 公式ファイル上の名称は "WTI-PHYSICAL"（旧称 CRUDE OIL, LIGHT SWEET）。
        # 2026-08-09の照合で判明。建玉188万枚＝主要WTI契約であることを確認済み（SPEC §12-5）
        "market_hint": "WTI-PHYSICAL",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "NYMEX WTI原油先物。公式表記は WTI-PHYSICAL（旧 Light Sweet Crude Oil）",
    },
    {
        "slug": "gold",
        "tff": False,
        "label": "GOLD",
        "code": "088691",
        "market_hint": "GOLD",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "COMEX金先物",
    },
    {
        "slug": "copper",
        "tff": False,
        "label": "銅",
        "code": "085692",
        "market_hint": "COPPER",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "COMEX銅先物",
    },
    {
        "slug": "us10y",
        "tff": True,
        "label": "米10年債",
        "code": "043602",
        "market_hint": "UST 10Y NOTE",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "CBOT米10年国債先物",
    },
]

SLUG_ORDER = [s["slug"] for s in SYMBOLS]


def code_map():
    """CFTCコード -> 銘柄定義 の辞書（フォールバックコード込み）"""
    m = {}
    for s in SYMBOLS:
        m[s["code"]] = s
        for fc in s.get("fallback_codes", []):
            m.setdefault(fc, s)
    return m
