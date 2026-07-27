# -*- coding: utf-8 -*-
"""CFTC Legacy Futures-Only COT 共通処理

対象フォーマット（ヘッダなしカンマ区切り・2026-07-27 実ファイルで検証済み）:
  field[0]  Market and Exchange Names（引用符付き、内部にカンマを含み得る）
  field[1]  As of Date YYMMDD
  field[2]  As of Date YYYY-MM-DD
  field[3]  CFTC Contract Market Code
  field[7]  Open Interest (All)
  field[8]  Noncommercial Positions - Long (All)   ※スプレッド除く
  field[9]  Noncommercial Positions - Short (All)  ※スプレッド除く
検証例: WHEAT-SRW 2026-06-09 行で
  NC Long + NC Spreading + Commercial Long = Total Long が成立することを確認。

出力スキーマ（既存スプレッドシート「CFTC」-data 互換）:
  date  : 火曜締め日 YYYY-MM-DD
  all   : 総建玉（Open Interest, 全区分合計）
  long  : 非商業ポジション（符号規則は symbols.py 参照）
  short : 非商業ポジション（負値で記録）
  net   : long + short
"""

import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSV_DIR = os.path.join(DATA_DIR, "csv")
FEED_JSON = os.path.join(DATA_DIR, "cot-feed.json")

WEEKLY_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
HISTORY_ZIP_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
HISTORY_PAGE = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm"

USER_AGENT = "Mozilla/5.0 (compatible; MFLab-CFTC-COT-feed)"

CSV_HEADER = ["date", "all", "long", "short", "net"]

JST = timezone(timedelta(hours=9))


def http_get(url, timeout=180, retries=3, backoff=5):
    """HTTP GET with retry (指数バックオフ)。cftc.govの一時的な混雑・瞬断対策。"""
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            print("  http_get attempt %d/%d failed: HTTP %s %s (%s)"
                  % (attempt, retries, e.code, e.reason, url))
        except Exception as e:  # noqa: BLE001  (URLError, timeout, etc.)
            last_err = e
            print("  http_get attempt %d/%d failed: %s: %s (%s)"
                  % (attempt, retries, type(e).__name__, e, url))
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise last_err


def _to_int(s):
    s = s.strip().replace(",", "")
    if s in ("", "."):
        return None
    return int(s)


def parse_legacy_lines(text, wanted_codes):
    """Legacy Futures-Only テキストをパースし、対象コードの行だけ返す。

    戻り値: list of dict {code, date, oi, nc_long, nc_short, market_name}
    ヘッダ行（annual ファイルに存在し得る）は date 欄が ISO 形式でないため
    自動スキップされる。
    """
    out = []
    reader = csv.reader(io.StringIO(text))
    for fields in reader:
        if len(fields) < 10:
            continue
        code = fields[3].strip().strip('"')
        if code not in wanted_codes:
            continue
        date_iso = fields[2].strip().strip('"')
        if len(date_iso) != 10 or date_iso[4] != "-" or date_iso[7] != "-":
            continue  # ヘッダ行など
        try:
            oi = _to_int(fields[7])
            nc_long = _to_int(fields[8])
            nc_short = _to_int(fields[9])
        except ValueError:
            continue
        if oi is None or nc_long is None or nc_short is None:
            continue
        out.append({
            "code": code,
            "date": date_iso,
            "oi": oi,
            "nc_long": nc_long,
            "nc_short": nc_short,
            "market_name": fields[0].strip().strip('"'),
        })
    return out


def to_feed_row(rec, sign_invert):
    """公式レポートの生値 -> フィード行（既存シート互換スキーマ）"""
    if sign_invert:
        long_v = rec["nc_short"]      # 外貨先物ショート = ペア買い方向
        short_v = -rec["nc_long"]     # 外貨先物ロング  = ペア売り方向（負値）
    else:
        long_v = rec["nc_long"]
        short_v = -rec["nc_short"]
    return {
        "date": rec["date"],
        "all": rec["oi"],
        "long": long_v,
        "short": short_v,
        "net": long_v + short_v,
    }


def csv_path(slug):
    return os.path.join(CSV_DIR, "%s.csv" % slug)


def read_symbol_csv(slug):
    path = csv_path(slug)
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = {
                "date": r["date"],
                "all": int(r["all"]),
                "long": int(r["long"]),
                "short": int(r["short"]),
                "net": int(r["net"]),
            }
    return rows


def write_symbol_csv(slug, rows_by_date):
    os.makedirs(CSV_DIR, exist_ok=True)
    path = csv_path(slug)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for d in sorted(rows_by_date):
            w.writerow(rows_by_date[d])
    return path


def build_feed_json(symbols, generated_note=""):
    """全銘柄CSVから cot-feed.json を再生成する。"""
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    feed = {
        "meta": {
            "schema_version": "1.2",
            "name": "MFLab CFTC COT Feed",
            "generated_at": now_jst,
            "source": {
                "weekly": WEEKLY_URL,
                "historical": HISTORY_PAGE,
                "note": "CFTC Legacy Futures-Only（非商業・スプレッド除く）。"
                        "数値の一次ソースは CFTC 公式のみ。",
            },
            "schema": {
                "date": "COT締め日（火曜, YYYY-MM-DD）",
                "all": "総建玉（Open Interest, 全区分合計）",
                "long": "非商業ポジション（usdjpy は円先物ショートを USD/JPY 買い方向として記録）",
                "short": "非商業ポジション（負値）",
                "net": "long + short",
                "tff": "TFF(金融先物のみ): am_*=アセットマネジャー(機関投資家等), lev_*=レバレッジド・ファンド(ヘッジファンド等)。符号規則はlong/shortと同一",
            },
            "state_thresholds": STATE_THRESHOLDS,
            "notes": generated_note,
        },
        "symbols": {},
    }
    latest_dates = []
    for s in symbols:
        rows = read_symbol_csv(s["slug"])
        dates = sorted(rows)
        entry = {
            "label": s["label"],
            "cftc_code": s["code"],
            "sign_convention": "usdjpy_direction(inverted)" if s["sign_invert"] else "raw",
            "note": s.get("note", ""),
            "coverage": {
                "first_date": dates[0] if dates else None,
                "last_date": dates[-1] if dates else None,
                "weeks": len(dates),
            },
            "latest": rows[dates[-1]] if dates else None,
            "prev": rows[dates[-2]] if len(dates) >= 2 else None,
            "change_1w": None,
            "weeks_52": [rows[d] for d in dates[-52:]],
            "state": (legacy_state([rows[d]["net"] for d in dates]) if dates else None),
        }
        if entry["latest"] and entry["prev"]:
            entry["change_1w"] = {
                k: entry["latest"][k] - entry["prev"][k]
                for k in ("all", "long", "short", "net")
            }
        entry["tff"] = tff_feed_entry(s)
        if dates:
            latest_dates.append(dates[-1])
        feed["symbols"][s["slug"]] = entry
    feed["meta"]["report_date_latest"] = max(latest_dates) if latest_dates else None
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FEED_JSON, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=1)
    return FEED_JSON


# ============================================================
# TFF (Traders in Financial Futures) — v1.1 追加
# 対象フォーマット（ヘッダなしカンマ区切り・2026-07-27 実ファイルで検証済み）:
#   field[2]  As of Date YYYY-MM-DD / field[3] コード / field[7] Open Interest
#   field[8..10]  Dealer L / S / Spread
#   field[11..13] Asset Manager L / S / Spread
#   field[14..16] Leveraged Funds L / S / Spread
#   field[17..19] Other Reportables L / S / Spread
# 検証: JAPANESE YEN 2026-07-07 行で
#   ΣL(各区分)+ΣSpread+NonRept L = Tot Rept L + NonRept L = OI(398,103) が成立。
# ============================================================

TFF_WEEKLY_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
TFF_HIST_COMBINED_URL = "https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip"
TFF_HIST_YEAR_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

TFF_CSV_HEADER = ["date", "all", "am_long", "am_short", "am_net",
                  "lev_long", "lev_short", "lev_net"]


def parse_tff_lines(text, wanted_codes):
    """TFFテキストをパースし、対象コードの行だけ返す。"""
    out = []
    reader = csv.reader(io.StringIO(text))
    for fields in reader:
        if len(fields) < 20:
            continue
        code = fields[3].strip().strip('"')
        if code not in wanted_codes:
            continue
        date_iso = fields[2].strip().strip('"')
        if len(date_iso) != 10 or date_iso[4] != "-" or date_iso[7] != "-":
            continue
        try:
            oi = _to_int(fields[7])
            am_l = _to_int(fields[11])
            am_s = _to_int(fields[12])
            lev_l = _to_int(fields[14])
            lev_s = _to_int(fields[15])
        except ValueError:
            continue
        if None in (oi, am_l, am_s, lev_l, lev_s):
            continue
        out.append({"code": code, "date": date_iso, "oi": oi,
                    "am_l": am_l, "am_s": am_s,
                    "lev_l": lev_l, "lev_s": lev_s})
    return out


def to_tff_row(rec, sign_invert):
    """TFF生値 -> フィード行。符号規則はLegacy側（to_feed_row）と同一。"""
    if sign_invert:
        am_long, am_short = rec["am_s"], -rec["am_l"]
        lev_long, lev_short = rec["lev_s"], -rec["lev_l"]
    else:
        am_long, am_short = rec["am_l"], -rec["am_s"]
        lev_long, lev_short = rec["lev_l"], -rec["lev_s"]
    return {"date": rec["date"], "all": rec["oi"],
            "am_long": am_long, "am_short": am_short,
            "am_net": am_long + am_short,
            "lev_long": lev_long, "lev_short": lev_short,
            "lev_net": lev_long + lev_short}


def tff_csv_path(slug):
    return os.path.join(CSV_DIR, "%s_tff.csv" % slug)


def read_tff_csv(slug):
    path = tff_csv_path(slug)
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = {k: (r[k] if k == "date" else int(r[k]))
                               for k in TFF_CSV_HEADER}
    return rows


def write_tff_csv(slug, rows_by_date):
    os.makedirs(CSV_DIR, exist_ok=True)
    path = tff_csv_path(slug)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TFF_CSV_HEADER)
        w.writeheader()
        for d in sorted(rows_by_date):
            w.writerow(rows_by_date[d])
    return path


def tff_feed_entry(sym):
    """build_feed_json 用: 1銘柄分のTFFブロックを生成（非対象銘柄は None）。"""
    if not sym.get("tff"):
        return None
    rows = read_tff_csv(sym["slug"])
    dates = sorted(rows)
    if not dates:
        return {"available": False,
                "note": "TFF未取得（バックフィル未実行）"}
    latest, prev = rows[dates[-1]], (rows[dates[-2]] if len(dates) >= 2 else None)
    entry = {
        "available": True,
        "source_report": "Traders in Financial Futures (Futures Only)",
        "coverage": {"first_date": dates[0], "last_date": dates[-1],
                     "weeks": len(dates)},
        "latest": latest, "prev": prev,
        "change_1w": ({k: latest[k] - prev[k]
                       for k in ("am_net", "lev_net")} if prev else None),
        "weeks_52": [{"date": rows[d]["date"], "am_net": rows[d]["am_net"],
                      "lev_net": rows[d]["lev_net"]} for d in dates[-52:]],
    }
    am_nets = [rows[d]["am_net"] for d in dates]
    lev_nets = [rows[d]["lev_net"] for d in dates]
    align, cross_ago = tff_alignment(am_nets, lev_nets)
    entry["state"] = {
        "alignment": align,
        "levf_zerocross_weeks_ago": cross_ago,
        "lev_percentile_all": percentile_of_last(lev_nets),
        "lev_bias": classify_bias(percentile_of_last(lev_nets)),
    }
    return entry


# ============================================================
# 状態表示（v1.2）— 機械的基準による参考情報。売買助言ではない。
# 閾値はすべて仮置き（EA-Risk-MonitorのPhase 3方式に倣い実測で調整可能）。
# ============================================================

STATE_THRESHOLDS = {
    "percentile_extreme": [10, 90],   # p<=10 or p>=90 → extreme
    "percentile_biased":  [25, 75],   # p<=25 or p>=75 → biased
    "momentum_weeks": 4,              # 勢い判定: net の4週差分
    "levf_zerocross_weeks": 8,        # LevF直近ゼロクロス判定の遡り週数
    "note": "仮置き閾値による機械的な状態表示。売買助言ではない。実測に基づき調整可",
}


def percentile_of_last(values):
    """系列の最終値が全期間の中で何パーセンタイルか（当該値以下の割合×100）。"""
    if len(values) < 2:
        return None
    cur = values[-1]
    return round(sum(1 for v in values if v <= cur) / len(values) * 100, 1)


def classify_bias(p):
    """パーセンタイル -> neutral / biased / extreme（境界は外側に割当て=保守側）。"""
    if p is None:
        return None
    lo_e, hi_e = STATE_THRESHOLDS["percentile_extreme"]
    lo_b, hi_b = STATE_THRESHOLDS["percentile_biased"]
    if p <= lo_e or p >= hi_e:
        return "extreme"
    if p <= lo_b or p >= hi_b:
        return "biased"
    return "neutral"


def momentum_state(nets):
    """net系列 -> (4週差分, ラベル)。5週未満は (None, None)。"""
    w = STATE_THRESHOLDS["momentum_weeks"]
    if len(nets) < w + 1:
        return None, None
    delta = nets[-1] - nets[-1 - w]
    cur = nets[-1]
    if cur > 0:
        label = "ロング積み増し" if delta > 0 else ("ロング縮小" if delta < 0 else "ロング横ばい")
    elif cur < 0:
        label = "ショート積み増し" if delta < 0 else ("ショート縮小" if delta > 0 else "ショート横ばい")
    else:
        label = "ニュートラル"
    return delta, label


def _sign(x):
    return (x > 0) - (x < 0)


def tff_alignment(am_nets, lev_nets):
    """AM×LevF整合状態 -> (state, levf_cross_weeks_ago)
    aligned: 符号一致 / divergence_warning: 符号不一致かつLevFが直近K週内にゼロクロス /
    mixed: 符号不一致（直近クロスなし）"""
    if not am_nets or not lev_nets:
        return None, None
    k = STATE_THRESHOLDS["levf_zerocross_weeks"]
    cross_ago = None
    tail = lev_nets[-(k + 1):]
    for i in range(len(tail) - 1, 0, -1):
        if _sign(tail[i]) != 0 and _sign(tail[i - 1]) != 0 and _sign(tail[i]) != _sign(tail[i - 1]):
            cross_ago = len(tail) - 1 - i
            break
    if _sign(am_nets[-1]) == _sign(lev_nets[-1]) and _sign(am_nets[-1]) != 0:
        return "aligned", cross_ago
    if cross_ago is not None:
        return "divergence_warning", cross_ago
    return "mixed", cross_ago


def legacy_state(rows_sorted_nets):
    p = percentile_of_last(rows_sorted_nets)
    delta, label = momentum_state(rows_sorted_nets)
    cur = rows_sorted_nets[-1] if rows_sorted_nets else None
    return {
        "percentile_all": p,
        "bias": classify_bias(p),
        "side": ("long" if cur and cur > 0 else "short" if cur and cur < 0 else "flat"),
        "momentum_4w": delta,
        "momentum_label": label,
    }
