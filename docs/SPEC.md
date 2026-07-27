[SPEC.md](https://github.com/user-attachments/files/30417702/SPEC.md)
# CFTC-COT フィード データ仕様書（v1.2 / 2026-07-27）

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


---

## 7. TFF拡張（v1.1 / 2026-07-27追加）

**目的**: アセットマネジャー（機関投資家等）とレバレッジド・ファンド（ヘッジファンド等）の
建玉を追加配信する。**TFF（Traders in Financial Futures）は金融先物のみが対象**のため、
対象は8銘柄（usdjpy/gbpusd/eurusd/audusd/sp500/nikkei225/nydow/us10y）。
WTI・GOLD・銅は対象外（JSONでは `tff: null`）。

### 7-1. ソース（検証済み）

| 区分 | URL |
|---|---|
| 週次 | https://www.cftc.gov/dea/newcot/FinFutWk.txt |
| 履歴 2006-06-13〜2016 | https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip |
| 履歴 2017〜 | https://www.cftc.gov/files/dea/history/fut_fin_txt_{YYYY}.zip |

フィールド位置（0起点・ヘッダなし）: [7]=OI, [11]/[12]=Asset Manager L/S,
[14]/[15]=Leveraged Funds L/S（スプレッドは[13]/[16]で不使用）。
**検証記録**: JAPANESE YEN 2026-07-07行で「Σ各区分L＋Σスプレッド＋非報告L＝
Tot Rept L(354,660)＋非報告L(43,443)＝OI(398,103)」の恒等式成立を確認。
同行のOIはLegacyフィードの同週OIとも完全一致。

### 7-2. 出力

- CSV: `data/csv/{slug}_tff.csv` 列=`date,all,am_long,am_short,am_net,lev_long,lev_short,lev_net`
- JSON: `symbols.{slug}.tff` に coverage / latest / prev / change_1w / weeks_52（am_net・lev_netのみ）
- 符号規則はLegacy側と同一（usdjpyのみUSD/JPY方向に反転。
  例: 2026-07-07 usdjpy → am_net=+48,653・lev_net=+90,083＝AM・HFとも円ショート優勢）

### 7-3. 注意（分類体系の違い）

LegacyのNon-Commercial（非商業）とTFFのAM＋Leveraged Fundsは**分類体系が異なる別レポート**であり、
合計しても一致しない（例: 2026-07-07 usdjpy Legacy net=+123,778 vs AM+Lev=+138,736）。
レポートに併記する場合は出典レポート名（Legacy／TFF）を必ず区別して明記する。
TFF履歴は2006-06-13以降（Legacyの2005年〜より短い）。


---

## 8. 状態表示（v1.2 / 2026-07-27追加）

**位置付け**: 機械的な仮置き閾値による参考表示であり、**売買助言ではない**
（フィードmeta.state_thresholds に閾値と免責を転記。閾値は運用実測で調整可能）。

### 8-1. Legacy: `symbols.{slug}.state`

| キー | 定義 |
|---|---|
| percentile_all | 現在netの全履歴パーセンタイル（当該値以下の割合×100） |
| bias | extreme（p≤10 or p≥90）/ biased（p≤25 or p≥75）/ neutral（境界は外側に割当て=保守側） |
| side | long / short / flat（netの符号） |
| momentum_4w / momentum_label | netの4週差分と方向ラベル（積み増し/縮小/横ばい） |

### 8-2. TFF: `symbols.{slug}.tff.state`

| キー | 定義 |
|---|---|
| alignment | aligned（AM・LevF符号一致=持続性高）/ divergence_warning（不一致かつLevFが直近8週内にゼロクロス=転換警戒）/ mixed（不一致・直近クロスなし） |
| levf_zerocross_weeks_ago | LevFの直近ゼロクロスが何週前か（8週超はnull） |
| lev_percentile_all / lev_bias | LevF netの全履歴パーセンタイルと偏り度（スクイーズリスクの目安） |

検証: tests/test_parse.py の test_state（境界値・勢い・整合の全パターン）＋
合成120週履歴での通しテスト（extreme/ロング積み増し/divergence_warningの再現）で確認済み。


---

## 9. TFF統合ZIP(2006-2016)の日付形式問題と修正（2026-07-27）

**症状**: 統合ZIP（fin_fut_txt_2006_2016.zip）からのマッチ件数が常に0件になっていた。

**原因（実データで特定済み）**: この統合ZIPのみ、日付列の値が
`MM/DD/YYYY HH:MM:SS AM/PM`（例: `12/27/2016 12:00:00 AM`）形式で格納されている。
ヘッダーのラベルは他ファイルと同じ「Report_Date_as_YYYY-MM-DD」だが、実データの形式が
表記と一致していない（CFTC側のエクスポート仕様の不一致、2026-07-27に実データで確認）。
また同ファイルは数値列も `93212.000000` のような小数表記になっている。
2017年以降の年次ZIP・週次ファイル・Legacy年次ZIPはいずれもISO日付・整数表記のため
影響を受けない。

**修正**: `_normalize_date()`（ISO形式とMM/DD/YYYY形式の両方に対応）と
`_to_int()`の小数フォールバックを追加。`tests/test_parse.py`の
`test_tff_legacy_bulk_format`に実データパターンを固定化し回帰を防止。
