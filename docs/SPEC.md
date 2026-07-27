# CFTC-COT フィード データ仕様書（v1.0 / 2026-07-27）

## 1. ソース

| 区分 | URL | 備考 |
|---|---|---|
| 週次（最新週） | https://www.cftc.gov/dea/newcot/deafut.txt | Legacy Futures-Only 長形式・カンマ区切り・ヘッダなし |
| 履歴（年次） | https://www.cftc.gov/files/dea/history/deacot{YYYY}.zip | 1986〜当年。公式Historical Compressedページで全年リンク確認済み（2026-07-27） |
| 公表スケジュール | 通常 金曜 15:30 ET（火曜締めデータ）。祝日週は順延 | CFTC公式FAQ記載 |

## 2. ソースファイルのフィールド位置（検証済み）

Legacy Futures-Only カンマ区切りファイルにはヘッダ行がない。
使用するフィールド（0起点）:

| index | 内容 |
|---|---|
| 0 | Market and Exchange Names（引用符付き・内部カンマあり得る） |
| 2 | As of Date（YYYY-MM-DD） |
| 3 | CFTC Contract Market Code |
| 7 | Open Interest (All) |
| 8 | Noncommercial Positions - Long (All) ※スプレッド除く |
| 9 | Noncommercial Positions - Short (All) ※スプレッド除く |

**検証記録（2026-07-27）**: deafut.txt 実データの WHEAT-SRW 行で
`NC Long(115,711) + NC Spreading(117,851) + Commercial Long(184,410) = Total Long(417,972)`
の恒等式が成立することを確認し、フィールド位置を確定した。

## 3. 出力スキーマ

### 3-1. 銘柄別CSV（`data/csv/{slug}.csv`）

```
date,all,long,short,net
2026-07-21,423796,259715,-107590,152125
```

| 列 | 定義 |
|---|---|
| date | COT締め日（火曜、YYYY-MM-DD） |
| all | 総建玉（Open Interest、全区分合計） |
| long | 非商業ポジション（符号規則は §4） |
| short | 非商業ポジション（負値で記録） |
| net | long + short |

既存Googleスプレッドシート「CFTC」の `-data` シートと互換
（`price` 列のみ廃止。日付は `YYYY/MM/DD` → `YYYY-MM-DD` に統一）。

### 3-2. 統合JSON（`data/cot-feed.json`）

- `meta`: schema_version / generated_at（JST）/ source / report_date_latest
- `symbols.{slug}`: label / cftc_code / sign_convention / coverage /
  latest / prev / change_1w / weeks_52（直近52週の行配列）

## 4. 符号規則

| 銘柄 | sign_convention | 規則 |
|---|---|---|
| usdjpy | `usdjpy_direction(inverted)` | `long`=円先物の非商業**ショート**（=USD/JPY買い方向）、`short`=−円先物の非商業ロング。**net プラス＝投機筋の円ショート優勢** |
| 上記以外 | `raw` | `long`=非商業ロング、`short`=−非商業ショート |

**検証記録（2026-07-27）**: CFTC公式 deacmesf.htm（2026-07-21付・07-24公表）
JAPANESE YEN Code-097741（OI=423,796 / NC Long=107,590 / NC Short=259,715）に
本規則を適用した結果が、既存スプレッドシート USD/JPY-data の同日行
（all=423796, long=259715, short=−107590, net=152125）と完全一致。
前週 2026-07-14 行も公式の前週比から逆算した値と一致。
`tests/test_parse.py` に同値検証を固定化済み。

## 5. 対象銘柄・CFTCコード

| slug | 銘柄 | コード | 備考 |
|---|---|---|---|
| usdjpy | USD/JPY | 097741 | 日本円先物（符号変換あり） |
| gbpusd | GBP/USD | 096742 | 英ポンド先物 |
| eurusd | EUR/USD | 099741 | ユーロFX先物 |
| audusd | AUD/USD | 232741 | 豪ドル先物 |
| sp500 | S&P500 | 13874+ | Consolidated（導入前は欠測） |
| nikkei225 | NIKKEI225 | 240743 | 円建て日経平均（CME） |
| nydow | NYダウ | 12460+ | Consolidated（導入前は欠測） |
| wti | WTI原油 | 067651 | NYMEX |
| gold | GOLD | 088691 | COMEX |
| copper | 銅 | 085692 | COMEX |
| us10y | 米10年債 | 043602 | CBOT |

コードは既存スプレッドシート「シート一覧」記載値を採用し、
097741・096742・099741・232741・13874+・240743 は 2026-07-21 付の
公式週次レポート実物で実在を確認済み。067651・088691・085692・043602・12460+ は
NYMEX/COMEX/CBOT掲載のため同一ファイル内の該当取引所セクションに存在する
（初回バックフィル後の coverage 出力で全銘柄の取得実績を必ず確認すること）。

## 6. 運用ルール（source_policy 整合）

1. レポート数値の確定ソースは CFTC 公式のみ。本フィードは機械的写像であり、
   乖離疑義時は公式ビューアブル版（deacmesf.htm 等）を優先する
2. レポート記載時は対象週（火曜締め日）を明記する
3. 期間表現（「○週連続」等）の自前計算・記載は品質基準文書 4-2 に従い行わない
4. フィード利用時は `meta.generated_at` と `report_date_latest` を確認し、
   取得時刻を記録する
