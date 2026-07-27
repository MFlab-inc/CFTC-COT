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


def http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


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
            "schema_version": "1.0",
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
            },
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
        }
        if entry["latest"] and entry["prev"]:
            entry["change_1w"] = {
                k: entry["latest"][k] - entry["prev"][k]
                for k in ("all", "long", "short", "net")
            }
        if dates:
            latest_dates.append(dates[-1])
        feed["symbols"][s["slug"]] = entry
    feed["meta"]["report_date_latest"] = max(latest_dates) if latest_dates else None
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FEED_JSON, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=1)
    return FEED_JSON
