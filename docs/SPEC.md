# CFTC-COT フィード データ仕様書（v1.2 / 2026-07-27・2026-08-09追記）

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

`coverage` の各キー（2026-08-09にフィールド追加）:

| キー | 定義 |
|---|---|
| first_date / last_date | 保存されている最初と最後の締め日 |
| weeks | **保存されている行数**（連続週数ではない点に注意） |
| span_weeks | first_date〜last_date の暦の週数 |
| present_ratio | weeks ÷ span_weeks。1.0 なら欠測なし |
| max_gap_days | 隣接する2週の最大間隔（日）。通常7、祝日ずれで6/8 |
| contiguous | `max_gap_days <= 10` なら true。**false の銘柄を連続系列として扱わないこと**<br>※在席率ではなく**最大の穴**で判定する（1箇所に大穴があっても比率は高く出るため） |

`weeks` と `span_weeks` が食い違うのは、CFTCが報告者20者未満の週を除外するため
（§12-2 の eurjpy が典型で present_ratio ≈ 0.51）。

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
| eurjpy | EUR/JPY | 399741 | ユーロ円クロスレート先物（CME）。**欠測多・§12参照** |
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
対象は9銘柄（usdjpy/eurjpy/gbpusd/eurusd/audusd/sp500/nikkei225/nydow/us10y）。
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
| momentum_4w / momentum_label | netの4週差分と方向ラベル（積み増し/縮小/横ばい）。**暦で4週ちょうどの窓でなければ null**（§12-3） |
| percentile_all / bias | サンプルが `min_samples_for_bias`(26週) 未満なら **null**（2件で「極端」と出るのを防ぐ） |

### 8-2. TFF: `symbols.{slug}.tff.state`

| キー | 定義 |
|---|---|
| alignment | aligned（AM・LevF符号一致=持続性高）/ divergence_warning（不一致かつLevFが直近8週内にゼロクロス=転換警戒）/ mixed（不一致・直近クロスなし） |
| levf_zerocross_weeks_ago | LevFの直近ゼロクロスが何週前か（8週超はnull）。**暦の週数**で数え、クロスを挟む2点が2週以上離れて時期を特定できない場合もnull（§12-3） |
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

**2026-08-09 追記**: 同種の再発を防ぐため、Legacy側（`parse_legacy_lines`）も
ISO決め打ちをやめ `_normalize_date()` に統一した。現行のLegacyファイルは週次・年次ZIPとも
ISO日付のため出力は変わらないが（下記10-3で確認）、将来Legacy側で同じ不一致が起きても
「0件なのに緑✅」にはならない。`test_legacy_date_formats` で固定化。


---

## 10. 収集精度の検証記録（2026-08-09）

Claude Code への移行に伴い、リポジトリ全体をコードとデータの両面から照合した記録。

### 10-1. バックフィルの `start_year` がTFF履歴を削っていた問題（修正済み）

**症状（潜在）**: `backfill.py` にTFF側だけ「`start_year` より前の行を捨てる」処理があり、
`backfill-history` の `start_year` に2005以外を入れるとTFF履歴が消える状態だった。
Legacy側には同じ処理が無く**非対称**。ワークフローは差分を自動commit&pushするため、
消失がリポジトリに確定し、しかも run は緑✅で終わる。

**実測（2026-08-09・シミュレーション、書き込みなし）**:

| 入力 start_year | TFF履歴 | Legacy履歴 |
|---|---|---|
| 2005（既定） | 1,052 → 1,052週 | 1,127週のまま |
| 2017 | 1,052 → **501週（−551）** | 1,127週のまま |
| 2020 | 1,052 → **344週（−708）** | 1,127週のまま |
| 2026 | 1,052 → **31週（−1,021）** | 1,127週のまま |

ワークフロー入力の説明文が「1986年まで遡及可能」であり、実際に別の年を入れる動機がある。

**修正**: 当該フィルタを削除し、TFFもLegacyと同じ「**既存行は常に保持・同じ日付のみ上書き**」に
統一した。`start_year` / `end_year` は「どの年のZIPを取りに行くか」だけを決める。
あわせて、書き込み前に**週数が減っていないか検査し、減る場合はCSVを一切書かずに異常終了**する
ガードを追加（減少は常にバグとみなす）。`test_merge_preserves_history` で固定化。

**副次的修正**: TFF統合ZIP（2006-2016）は `start_year`/`end_year` がその期間に掛かるときだけ
取得するようにした。従来は `start_year` に関係なく毎回ダウンロードし、その後フィルタで
捨てていた。

### 10-2. 銘柄別の欠測週の実測（nikkei225）

Legacy `nikkei225` が他銘柄より17週少ない件を実データで特定した。

- 欠測17週は**すべて 2005-01-11〜2005-07-26 に集中**しており、
  **2005-08-02以降は現在（2026-08-04）まで欠測ゼロ**
- 2006-06-13以降で Legacy と TFF の日付集合は**完全一致**（1,052 = 1,052、差分0件）
- 該当17週: 2005-01-11/01-18/01-25/02-01/02-08/02-15/02-22/03-01/03-15/03-22/
  04-05/04-12/06-14/06-21/06-28/07-12/07-26

CFTC公式FAQの「報告対象トレーダーが20者未満の銘柄はその週のレポートから除外」と
矛盾しない分布だが、**除外理由そのものは公式で未確認**。数値をレポートに記載する際は
この期間の欠測を前提にすること。

その他の銘柄の日付間隔はすべて7日、または年末年始・独立記念日前後の6日/8日のシフトのみで、
異常な欠落は無い（sp500 / nydow は 2010-06-15 開始で12件、他は22件のシフト）。

※ この調査は11銘柄時点のもの。**2026-08-09に追加した eurjpy はこの記述の対象外**で、
在席率51%・最大434日の欠測がある（§12-2）。現在の各銘柄の状態は
フィードの `coverage.max_gap_days` / `coverage.contiguous` で確認すること
（nikkei225 も 2005年前半の欠測により contiguous=false）。

### 10-3. パーサ変更が既存データに影響しないことの確認

`parse_legacy_lines` の日付処理を `_normalize_date()` に統一したうえで、
既存CSVから `cot-feed.json` を再生成し変更前と全文比較した。
**差分は `meta.generated_at`（生成時刻）の1行のみ**で、11銘柄すべての
値・coverage・state ブロックは完全一致した。

### 10-4. HANDOFF.md 記載値の再現確認

| 検証項目 | 結果 |
|---|---|
| usdjpy 2026-07-21 → `all=423796, long=259715, short=-107590, net=152125` | 一致 |
| usdjpy TFF 2026-07-07 → `am_net=+48,653 / lev_net=+90,083` | 一致 |
| 同週 Legacy `net=+123,778` vs AM+Lev `=+138,736`（一致しないこと） | 一致 |

### 10-5. フルバックフィルによる実データ検証（2026-08-09・run 31322502500）

上記の修正後、作業ブランチ上で `backfill-history`（start_year=2005）を実行し、
CFTC公式ZIPから全履歴を取り直した結果:

| 項目 | 結果 |
|---|---|
| 取得URL | 33本（Legacy年次22 + TFF統合1 + TFF年次10）**全成功・失敗0** |
| ダウンロード量 | 293.4 MB |
| 実行時間 | 6.1 秒 |
| TFF統合ZIP(2006-2016) | **3,990行**マッチ（§9修正前は0行だった箇所） |
| Legacy coverage | 全11銘柄 **±0週**（usdjpy 1,127 / nikkei225 1,110 / sp500・nydow 843） |
| TFF coverage | 全8銘柄 **±0週**（1,052 / sp500・nydow 843） |
| **CSVの実差分** | **19ファイルすべて byte-identical（差分ゼロ）** |
| commitされた変更 | `cot-feed.json` の `generated_at` と `notes` の2行のみ |

**21年分をCFTC公式から取り直して全CSVが1バイトも変わらなかった**ことから、
(a) 保存済みデータは現在の公式公表値と完全に一致している、
(b) パーサ統一（§9追記）は実データに対しても出力を変えない、
(c) TFF履歴の消失は起きていない、の3点が同時に確認された。

### 10-6. 失敗検知が実際に働くことの確認（2026-08-09）

ネットワークから cftc.gov に到達できない環境（§10-7）で
`backfill.py --start-year 2024` を実行し、失敗経路を実測した。

```
=== health ===
  urls attempted : 6 (legacy 3 + tff 3)
  fetch failures : 6
  downloaded     : 0.0 MB
  elapsed        : 149.8 sec
  empty symbols  : legacy=none tff=none
    FAIL legacy .../deacot2024.zip  (URLError: ... 403 Forbidden)
    ...
  RESULT: FAILED - このrunは失敗として扱われ、data/ はcommitされません。
### EXIT CODE = 1
```

同時に、**`--start-year 2024` を指定してもTFF coverage は 1,052週のまま（±0）**で
あることを確認した（修正前の実装なら約950週が削られていた）。

この実行は**修正前なら exit 0 = 緑✅で通り、しかもTFF履歴を削って
commitしていた**ケースにあたる。

**副次的な発見（重要）**: 成功時 293.4MB/6.1秒 に対し、全失敗時は 0.0MB/149.8秒
（リトライのバックオフで長くなる）。つまり**実行時間は成否の判定に使えない**。
従来 HANDOFF に記載されていた「実行時間が18秒より短ければ失敗を疑う」という
判定基準は、成功を失敗と誤判定するため撤回した。判定は
`fetch failures` と `downloaded (MB)` で行う。

### 10-7. 公開URLは不変

`data/cot-feed.json` と `index.html` はGit履歴上（改名追跡 `--follow`）一度も
移動・改名されていない。以下のURLは初版から不変であり、今後も変更しない。

- `https://mflab-inc.github.io/CFTC-COT/`
- `https://mflab-inc.github.io/CFTC-COT/data/cot-feed.json`
- `https://mflab-inc.github.io/CFTC-COT/data/csv/{slug}.csv` / `{slug}_tff.csv`


---

## 11. 失敗検知（2026-08-09追加）

本リポジトリで繰り返し発生した事故は、いずれも「**取得に失敗しているのに
ワークフローが緑✅で終わる**」形だった（`import io` 欠落によるTFF全滅、
統合ZIPの日付形式によるマッチ0件）。人間がログを読んで気づく運用に依存していたため、
機械判定に置き換えた。

### 11-1. backfill.py

ログ末尾に `=== health ===` を出力し、以下のいずれかで**異常終了（exit 1）**する。
ワークフローは python が異常終了すると commit ステップを飛ばすため、
**取得漏れのあるデータはリポジトリに入らない**。

| 条件 | 扱い |
|---|---|
| いずれかのURLの取得に失敗 | exit 1（`allow_partial` で回避可） |
| 取得は成功したがマッチ0件 | exit 1（§9と同じ症状の検出） |
| Legacy側に0週の銘柄がある | exit 1（`allow_partial` でも回避不可） |
| 週数が減少する結果になった | **CSVを書かずに** exit 1（常に回避不可） |

health ブロックには取得URL数・失敗数・ダウンロード量(MB)・**実行時間(秒)**・
0週の銘柄を出力する。coverage 行には前回比（`+12` 等）も併記する。
「実行時間が異常に短い場合は取得失敗を疑う」という従来の目視判定を数値で確認できる。

`allow_partial` は、公式から**恒久的に削除された年**がある場合にだけ使う
（ワークフロー入力、既定 false）。

### 11-2. weekly_update.py

Legacy取得の失敗は従来どおりその場で失敗させる。一方、**TFF取得の失敗や鮮度異常では
exit 0 のままにする** — ここで異常終了するとcommitステップが飛び、取得できたLegacyの
最新週まで捨ててしまうため。代わりに `GITHUB_OUTPUT` に `degraded=1` を書き出し、
ワークフローが**commitを済ませた後で** run を赤くする。

鮮度判定は「その週にその銘柄が居たか」ではなく「**保存済みデータが古びていないか**」で行う
（`STALE_AFTER_DAYS = 14`）。CFTCは20者未満の銘柄をその週だけ除外することがあるため、
1週の欠席で赤くするとオオカミ少年になる。一方でコードが恒久的に廃止・変更された場合は
2週で必ず表面化する。

| 検出内容 | 扱い |
|---|---|
| Legacy週次から対象銘柄が0件 | exit 1 |
| TFF取得失敗 / TFFマッチ0件 | degraded（commit後にrunを赤く） |
| 最新データが14日以上古い | degraded（CDNキャッシュ滞留・公表停止の疑い） |
| 14日以上更新されていない系列がある | degraded（コード廃止・変更の疑い） |


---

## 12. EUR/JPY 追加の検証記録（2026-08-09）

### 12-1. 単独銘柄としての実在確認

当初「CFTCにEUR/JPY単独銘柄は存在せず、EUR先物とJPY先物からの合成が必要」と
判断しかけたが、**これは誤り**だった。CFTC公式の週次ファイルを実際に検索して
確認した結果（run 31323904219・読み取り専用の調査）:

```
EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE   code=399741
```

- **Legacy（deafut.txt）・TFF（FinFutWk.txt）の両方に存在**する
- したがって合成値ではなく、**CFTC公式の実データをそのまま配信できる**
- 同じ仕組みの `EURO FX/BRITISH POUND XRATE` = **299741**（EUR/GBP）も併せて確認。
  将来の追加候補（未検証・未合意）

同一週の Open Interest が Legacy 側と TFF 側で完全一致することも確認した
（2026-08-04: いずれも 20,895）。同じ契約を両レポートから読めている裏付けとなる。

### 12-2. 欠測の実測（★利用上の最重要注意）

`eurjpy` は他の11銘柄と**データの性質が根本的に異なる**。

| 指標 | eurjpy | 参考: usdjpy |
|---|---|---|
| 期間 | 2017-08-01 〜 2026-08-04 | 2005-01-04 〜 2026-08-04 |
| 期間内の暦週数 | 471週 | 1,127週 |
| 実際に存在する週 | **Legacy 238週 / TFF 240週** | 1,127週 |
| 在席率 | **約51%** | 100% |
| 最長の連続欠測 | **61週** | 0 |
| 3週以上の連続欠測 | 13回 | 0 |
| 直近1年 | 53週中47週（6週欠測） | 欠測なし |
| Open Interest（2026-08-04） | 20,895 | 419,393 |

建玉がUSD/JPYの約5%しかなく、CFTC公式ルール「報告対象トレーダーが20者未満の週は
除外」に頻繁に該当するため。**不具合ではなく仕様**だが、以下の帰結がある。

1. **連続系列として扱ってはいけない**。「○週連続」等の期間表現は
   §6-3 の運用ルール（自前計算・記載しない）に照らしても行わないこと
2. JSONの `coverage.present_ratio`（0.505）と `coverage.contiguous`（false）で
   機械的に判定できるようにした。連続系列の銘柄は present_ratio=1.0 / contiguous=true
3. TFF が Legacy より2週多い（240 vs 238）。2018-01-16 と 2018-02-06 は
   TFF にあり Legacy に無い。分類体系が異なる別レポートのため起こり得る

### 12-3. 欠測系列に対応するための実装変更

`eurjpy` を追加したことで、既存ロジックに以下の不具合が顕在化したため修正した。
いずれも**連続系列の11銘柄には影響しない**（state ブロックの全文比較で差分0件を確認）。

| 症状 | 修正 |
|---|---|
| `momentum_4w` が「4**件**前」との差分だった。欠測銘柄では暦で20週前などになり、「4週差分」として誤った数値を出す | `momentum_state(nets, dates)` が暦の週数を検査し、欠測をまたぐ場合は **null を返す**（誤った数値を出すより出さない） |
| `levf_zerocross_weeks_ago` も件数ベースで、暦とずれる | 暦の週数で算出。さらに**クロスを挟む2点が2週以上離れている場合は反転時期を特定できない**ため null（＝`mixed` 扱い）とする |
| 週次の鮮度チェック（14日）が、長期欠測する銘柄で**毎週DEGRADED＝runが赤**になる | `symbols.py` に `max_stale_days` を追加。eurjpy は 365日（実測最長61週=434日に基づく）。他銘柄は従来どおり14日でコード廃止を2週で検知 |

**オオカミ少年テスト（実測パターンを適用）**:

| 欠測パターン | 赤くなる銘柄 |
|---|---|
| 1週欠測 | なし |
| 3週連続欠測 | eurjpy 以外の11銘柄（＝eurjpyは誤発火しない） |
| 11週連続欠測 | 同上 |
| 61週連続欠測（実測最長） | eurjpy も含む全銘柄（1年超の消失は通知されるべき） |

### 12-4. 符号規則（USD/JPY との違い）

`sign_invert=False`。**USD/JPY と扱いが逆になる点に注意**。

| 先物 | 建て方 | ロングの意味 | sign_invert |
|---|---|---|---|
| 日本円先物 097741 | 1円 = 何ドル | 円買い ＝ USD/JPY **下落**方向 | True（反転が必要） |
| ユーロ円クロス 399741 | 1ユーロ = 何円 | ユーロ買い円売り ＝ EUR/JPY **上昇**方向 | False（既にペア方向） |

契約名 `EURO FX/JAPANESE YEN` はFXの慣行どおり「基軸通貨/決済通貨」＝
JPY per EUR を意味し、CFTC公式ファイル上の表記自体がこの向きを示している。
したがって `net` プラス＝**投機筋のユーロロング／円ショート優勢**で、
ペア表記とそのまま同じ向きになる。

**★未確認事項（レポート記載前に要確認）**: 上記は契約の建て方（CME仕様）と
CFTCの契約名表記からの帰結であり、**CFTC公式ビューアブル版の表示との目視照合は未実施**。
USD/JPY のように「公式値と完全一致」を確認した銘柄とは検証レベルが異なる。

参考として EUR/USD・USD/JPY のネットとの相関を238週で測ったが、
**符号の裏取りにはならなかった**（記録として残す）:

| 対象 | 相関係数 |
|---|---|
| EUR/JPY net vs EUR/USD net | +0.138 |
| EUR/JPY net vs USD/JPY net | +0.018 |
| EUR/JPY net vs (EUR/USD + USD/JPY) | +0.135 |

符号が逆なら負に出るはずなので向きとしては矛盾しないが、値が小さすぎて
証拠能力はない（参加者層も契約サイズも異なる別市場のため当然）。
**数値をレポートに記載する前に、公式版で符号の向きを一度確認すること**（§6-1）。

**2026-08-04 週の出力**（照合用）:
- Legacy: `all=20895, long=6183, short=-3883, net=+2300`（非商業は小幅ネットロング）
- TFF: `am_net=-3363`（AMはネットショート）, `lev_net=+578`（LevFはネットロング）


---

## 13. 契約名の照合（2026-08-09追加）

### 13-1. 背景

`symbols.py` は各銘柄に `market_hint`（この契約はこういう名前のはず）を持っていたが、
**どこからも参照されていなかった**。そのため CFTC がコードを別契約に振り替えても
検知できず、「銘柄ラベルは正しいまま中身だけ別商品になる」という気づきにくい
壊れ方をし得た。

`backfill.py` が公式ファイル上の契約名を収集し、`=== contract names (official) ===`
として必ずログに出力するようにした。`market_hint` と一致しない場合は health に
WARN を出す（表記ゆれで誤検知し得るため run は落とさない）。

### 13-2. 全12銘柄の公式契約名（run 31325767237 で取得）

| slug | code | 公式ファイル上の契約名 |
|---|---|---|
| usdjpy | 097741 | JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE |
| eurjpy | 399741 | EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE |
| gbpusd | 096742 | BRITISH POUND - CHICAGO MERCANTILE EXCHANGE |
| eurusd | 099741 | EURO FX - CHICAGO MERCANTILE EXCHANGE |
| audusd | 232741 | AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE |
| sp500 | 13874+ | S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE |
| nikkei225 | 240743 | NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE |
| nydow | 12460+ | DJIA Consolidated - **CHICAGO BOARD OF TRADE** |
| wti | 067651 | **WTI-PHYSICAL** - NEW YORK MERCANTILE EXCHANGE |
| gold | 088691 | GOLD - COMMODITY EXCHANGE INC. |
| copper | 085692 | COPPER- #1 - COMMODITY EXCHANGE INC. |
| us10y | 043602 | UST 10Y NOTE - CHICAGO BOARD OF TRADE |

### 13-3. WTI の名称不一致（調査済み・データは正しい）

初回実行で `wti` のみ WARN が出た（hint=`CRUDE OIL` / 実際=`WTI-PHYSICAL`）。

**調査結果: コードの振り替えではなく、CFTC側の表示名変更**。以下の根拠で
067651 が主要WTI原油先物であることを確認した。

| 締め日 | Open Interest |
|---|---|
| 2005-01-04 | 683,120 |
| 2010-01-05 | 1,231,436 |
| 2015-01-06 | 1,505,101 |
| 2020-01-07 | 2,244,930 |
| 2026-08-04 | 1,886,816 |

建玉188万枚規模かつ2005年から1,127週連続（最大間隔8日＝祝日ずれのみ）であり、
ニッチな契約ではあり得ない。`market_hint` を実際の名称 `WTI-PHYSICAL` に更新した。

※ 旧称 "CRUDE OIL, LIGHT SWEET" から現行表記への変更時期は未調査（未確認）。
レポートで銘柄名を書く際は「WTI原油」表記のままで問題ないが、公式ファイルを
直接参照する場合は現行名が `WTI-PHYSICAL` である点に注意。
