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
        "label": "USD/JPY",
        "code": "097741",
        "market_hint": "JAPANESE YEN",
        "sign_invert": True,
        "fallback_codes": [],
        "note": "円先物を USD/JPY 方向に符号変換。net プラス = 投機筋の円ショート優勢",
    },
    {
        "slug": "gbpusd",
        "label": "GBP/USD",
        "code": "096742",
        "market_hint": "BRITISH POUND",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "eurusd",
        "label": "EUR/USD",
        "code": "099741",
        "market_hint": "EURO FX",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "audusd",
        "label": "AUD/USD",
        "code": "232741",
        "market_hint": "AUSTRALIAN DOLLAR",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "",
    },
    {
        "slug": "sp500",
        "label": "S&P500",
        "code": "13874+",
        "market_hint": "S&P 500 Consolidated",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "Consolidated（大型+E-mini+Micro合算）。導入前の週は欠測になる",
    },
    {
        "slug": "nikkei225",
        "label": "NIKKEI225",
        "code": "240743",
        "market_hint": "NIKKEI STOCK AVERAGE YEN DENOM",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "円建て日経平均先物（CME）",
    },
    {
        "slug": "nydow",
        "label": "NYダウ",
        "code": "12460+",
        "market_hint": "DJIA Consolidated",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "Consolidated。導入前の週は欠測になる",
    },
    {
        "slug": "wti",
        "label": "WTI原油",
        "code": "067651",
        "market_hint": "CRUDE OIL",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "NYMEX WTI（Light Sweet Crude Oil）",
    },
    {
        "slug": "gold",
        "label": "GOLD",
        "code": "088691",
        "market_hint": "GOLD",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "COMEX金先物",
    },
    {
        "slug": "copper",
        "label": "銅",
        "code": "085692",
        "market_hint": "COPPER",
        "sign_invert": False,
        "fallback_codes": [],
        "note": "COMEX銅先物",
    },
    {
        "slug": "us10y",
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
