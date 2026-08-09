# CFTC-COT 引き継ぎ仕様書（Claude Code 移行用）

作成日: 2026-07-27 / 最終更新: 2026-08-09 / 対象リポジトリ: `MFlab-inc/CFTC-COT`（Public）
本書は Claude Code セッションでの作業再開に必要な全情報をまとめたもの。
**本書に書かれていない仕様は「未確定」であり、推測で実装しないこと。**

> **2026-08-09 更新**: Claude Code へ移行。収集精度に関わる不具合1件（§6-6）を修正し、
> 「失敗が緑✅で通る」問題に機械判定を入れた（§7-3）。検証記録は `docs/SPEC.md` §10-11。

---

## 0. プロジェクト概要

CFTC公式のCOT（Commitments of Traders）レポートから対象11銘柄の建玉を
毎週自動取得し、GitHub Pages上で機械可読フィードとして公開するシステム。
**稼働中・全機能検収済み（2026-07-27時点）**。

| 項目 | 値 |
|---|---|
| リポジトリ | https://github.com/MFlab-inc/CFTC-COT （Public） |
| ダッシュボード | https://mflab-inc.github.io/CFTC-COT/ |
| 統合フィード | https://mflab-inc.github.io/CFTC-COT/data/cot-feed.json |
| 銘柄別CSV | `/data/csv/{slug}.csv`（Legacy）、`/data/csv/{slug}_tff.csv`（TFF） |
| 現行スキーマ | `schema_version: "1.2"` |
| 依存ライブラリ | **なし**（Python 3.10+ 標準ライブラリのみ） |
| ホスティング | GitHub Pages（Branch: `main` / フォルダ: `/(root)`） |

### 目的
FX市況レポート（週次）およびスイング戦略の環境認識材料として、
投機筋・機関投資家・ヘッジファンドの建玉ポジションを参照する。

---

## 1. リポジトリ構成（約2,080行 / 2026-08-09時点）

```
CFTC-COT/
├── .github/workflows/
│   ├── weekly.yml          # 週次自動更新（cron 2本 + workflow_dispatch）46行
│   └── backfill.yml        # 履歴再構築（workflow_dispatch のみ）47行
├── scripts/
│   ├── symbols.py          # 銘柄マスタ（145行）
│   ├── cot_common.py       # 共通処理（469行）★中核
│   ├── weekly_update.py    # 週次更新エントリポイント（173行）
│   └── backfill.py         # 履歴バックフィル エントリポイント（225行）
├── tests/
│   └── test_parse.py       # 検証テスト（258行・標準ライブラリのみ）
├── data/
│   ├── cot-feed.json       # ★統合フィード（自動生成・commit対象）
│   └── csv/
│       ├── {slug}.csv      # Legacy 11銘柄
│       └── {slug}_tff.csv  # TFF 8銘柄
├── index.html              # ダッシュボード（321行・単一ファイル・CSS/JS内包）
├── docs/
│   ├── SPEC.md             # データ仕様書（312行）※検証記録はここに追記する
│   └── HANDOFF.md          # 本書
├── .gitignore              # __pycache__ 等の生成物を除外
└── README.md               # セットアップ手順（85行）
```

### ローカル実行コマンド
```bash
export PYTHONPATH=scripts
python scripts/backfill.py --start-year 2005   # 履歴再構築（全銘柄・Legacy+TFF）
python scripts/weekly_update.py                # 最新週の取り込み
python tests/test_parse.py                     # 全テスト（4ブロック・全件合格が正常）
```

---

## 2. データソース（すべて検証済み・推測なし）

| 区分 | URL | 備考 |
|---|---|---|
| Legacy 週次 | `https://www.cftc.gov/dea/newcot/deafut.txt` | ヘッダなし・ISO日付・整数 |
| Legacy 履歴 | `https://www.cftc.gov/files/dea/history/deacot{YYYY}.zip` | 1986〜当年 |
| TFF 週次 | `https://www.cftc.gov/dea/newcot/FinFutWk.txt` | ヘッダなし・ISO日付・整数 |
| TFF 履歴（2006-2016） | `https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip` | **特殊形式・§6参照** |
| TFF 履歴（2017〜） | `https://www.cftc.gov/files/dea/history/fut_fin_txt_{YYYY}.zip` | ヘッダあり・ISO日付 |
| 公式ページ（照合用） | `https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm` | |

**公表タイミング**: データは火曜締め、公表は通常 米国時間 金曜 15:30 ET（＝JST土曜早朝）。
米祝日週は順延する。

### フィールド位置（0起点・ヘッダなし前提）

**Legacy Futures-Only**（実ファイルで検証済み）
| index | 内容 |
|---|---|
| 0 | Market and Exchange Names（引用符付き・内部カンマあり） |
| 2 | As of Date（YYYY-MM-DD） |
| 3 | CFTC Contract Market Code |
| 7 | Open Interest (All) |
| 8 | Noncommercial Long (All) ※スプレッド除く |
| 9 | Noncommercial Short (All) ※スプレッド除く |

検証記録: WHEAT-SRW 行で
`NC Long(115,711) + NC Spreading(117,851) + Commercial Long(184,410) = Total Long(417,972)`
の恒等式成立を確認してフィールド位置を確定した。

**TFF**（CFTC公式の列定義ページと一致確認済み）
| index | 内容 |
|---|---|
| 7 | Open Interest (All) |
| 8/9/10 | Dealer Long / Short / Spread |
| **11/12** | **Asset Manager Long / Short**（13=Spread・不使用） |
| **14/15** | **Leveraged Funds Long / Short**（16=Spread・不使用） |
| 17-19 | Other Reportables L/S/Spread |

検証記録: JAPANESE YEN 2026-07-07 行で
「Σ各区分L＋Σスプレッド＋非報告L ＝ Tot Rept L(354,660)＋非報告L(43,443) ＝ OI(398,103)」
の恒等式成立を確認。同行のOIはLegacyフィードの同週OIとも完全一致。

---

## 3. 銘柄マスタ（`scripts/symbols.py`）

| slug | 銘柄 | CFTCコード | sign_invert | tff | 取得実績（検収済み） |
|---|---|---|---|---|---|
| usdjpy | USD/JPY | 097741 | **True** | ○ | Legacy 2005-01-04〜1,125週 / TFF 2006-06-13〜1,050週 |
| gbpusd | GBP/USD | 096742 | False | ○ | 同上 |
| eurusd | EUR/USD | 099741 | False | ○ | 同上 |
| audusd | AUD/USD | 232741 | False | ○ | 同上 |
| sp500 | S&P500 | 13874+ | False | ○ | **Legacy/TFF とも 2010-06-15〜841週** |
| nikkei225 | NIKKEI225 | 240743 | False | ○ | **Legacy 1,108週**（下記注） / TFF 1,050週 |
| nydow | NYダウ | 12460+ | False | ○ | **Legacy/TFF とも 2010-06-15〜841週** |
| wti | WTI原油 | 067651 | False | × | Legacy 1,125週 |
| gold | GOLD | 088691 | False | × | Legacy 1,125週 |
| copper | 銅 | 085692 | False | × | Legacy 1,125週 |
| us10y | 米10年債 | 043602 | False | ○ | Legacy 1,125週 / TFF 1,050週 |

※ 上表の週数は 2026-07-27 時点。週次更新で毎週1週ずつ増える
（2026-08-04 週時点で Legacy 1,127 / TFF 1,052 / sp500・nydow 843 / nikkei225 Legacy 1,110）。

**欠測はすべて仕様であり不具合ではない**:
- `sp500` / `nydow`: Consolidatedコード（13874+ / 12460+）の集計開始が2010-06-15のため
- `nikkei225` Legacy が他より17週少ない件: CFTC公式ルール「報告対象トレーダーが
  20者未満の週はレポートから除外」と矛盾しない。
  **2026-08-09の実測（SPEC §10-2）**: 欠測17週は**すべて 2005-01-11〜2005-07-26 に集中**し、
  **2005-08-02以降は現在まで欠測ゼロ**。2006-06-13以降は Legacy と TFF の日付集合が完全一致
  （1,052 = 1,052・差分0件）。旧記述の「時折閾値を割る」は誤解を招くため訂正した
  （散発的に起きるのではなく、2005年前半に限られた現象）。
  ※ 除外理由そのものはCFTC公式で未確認
- `wti` / `gold` / `copper`: TFFは金融先物のみが対象のため構造的に存在しない（JSONで `tff: null`）

---

## 4. 符号規則（★最重要・変更時は必ず検証すること）

| slug | sign_convention | 規則 |
|---|---|---|
| usdjpy | `usdjpy_direction(inverted)` | `long` = 円先物の非商業**ショート**（＝USD/JPY買い方向）<br>`short` = −（円先物の非商業ロング）<br>**net プラス＝投機筋の円ショート優勢** |
| 上記以外 | `raw` | `long` = 非商業ロング、`short` = −非商業ショート |

TFF側（`am_*` / `lev_*`）も**同一の符号規則**を適用する（`to_tff_row(rec, sign_invert)`）。

**検証記録（変更時の回帰基準・tests に固定化済み）**:
- CFTC公式 2026-07-21付 JAPANESE YEN Code-097741
  （OI=423,796 / 非商業L=107,590 / 非商業S=259,715）
  → フィード出力 `all=423796, long=259715, short=-107590, net=152125` が完全一致
- TFF 2026-07-07 usdjpy → `am_net=+48,653`, `lev_net=+90,083`
- Legacy非商業とTFF(AM+LevF)は**分類体系が異なる別レポート**であり合計は一致しない
  （実測: 2026-07-07 Legacy net=+123,778 vs AM+Lev=+138,736）。併記時は出典を区別すること

---

## 5. 出力仕様

### 5-1. CSV
- Legacy: `data/csv/{slug}.csv` 列 = `date,all,long,short,net`
- TFF: `data/csv/{slug}_tff.csv` 列 = `date,all,am_long,am_short,am_net,lev_long,lev_short,lev_net`
- `date` は火曜締め日（YYYY-MM-DD）。日付昇順でソートして書き出す

### 5-2. cot-feed.json（`build_feed_json()`）
```
meta:
  schema_version "1.2" / name / generated_at (JST文字列) / report_date_latest
  source{weekly, historical, note} / schema{各列の説明} / state_thresholds / notes
symbols.{slug}:
  label / cftc_code / sign_convention / note
  coverage{first_date, last_date, weeks}
  latest / prev / change_1w{all,long,short,net}
  weeks_52[]                      # 直近52週の行
  state{...}                      # §5-3
  tff: null（対象外） | {available, source_report, coverage, latest, prev,
                        change_1w{am_net,lev_net}, weeks_52[{date,am_net,lev_net}], state{...}}
```

### 5-3. 状態表示（v1.2・**売買助言ではない**）

`STATE_THRESHOLDS`（`cot_common.py` 冒頭・**すべて仮置き**。JSONのmetaに転記され検証可能）
```python
percentile_extreme = [10, 90]   # p<=10 or p>=90 → extreme
percentile_biased  = [25, 75]   # p<=25 or p>=75 → biased
momentum_weeks = 4              # net の4週差分
levf_zerocross_weeks = 8        # LevF直近ゼロクロス判定の遡り週数
```

**Legacy `state`**（`legacy_state()`）
| キー | 定義 |
|---|---|
| percentile_all | 現在netの**全履歴**パーセンタイル（当該値以下の割合×100） |
| bias | extreme / biased / neutral（境界は外側に割当て＝保守側） |
| side | long / short / flat |
| momentum_4w / momentum_label | net の4週差分と方向ラベル（積み増し/縮小/横ばい） |

**TFF `tff.state`**（`tff_alignment()`）
| キー | 定義 |
|---|---|
| alignment | `aligned`（AM・LevF符号一致＝持続性高）/ `divergence_warning`（不一致かつLevFが直近8週内にゼロクロス＝転換警戒）/ `mixed`（不一致・直近クロスなし） |
| levf_zerocross_weeks_ago | LevF直近ゼロクロスが何週前か（8週超は null） |
| lev_percentile_all / lev_bias | LevF net の全履歴パーセンタイルと偏り度 |

---

## 6. ★既知の落とし穴（過去に実際に踏んだもの・再発防止必須）

### 6-1. TFF統合ZIP（2006-2016）だけ形式が違う
`fin_fut_txt_2006_2016.zip` のみ以下の点で他ファイルと異なる。**この対応を外すと
2006-2016のTFF履歴が丸ごと0件になる**（実際に発生し、原因特定に数往復を要した）。
- 日付が `MM/DD/YYYY HH:MM:SS AM/PM` 形式（例: `12/27/2016 12:00:00 AM`）。
  ヘッダーのラベルは他と同じ `Report_Date_as_YYYY-MM-DD` なのに**実データが一致していない**
- 数値が小数表記（例: `93212.000000`）
- ヘッダー行が存在する（週次ファイルには無い）

→ 対応: `_normalize_date()`（ISO / MM-DD-YYYY 両対応）と `_to_int()`（float フォールバック）。
`tests/test_parse.py::test_tff_legacy_bulk_format` に実データパターンを固定化済み。

### 6-2. `import io` の消し忘れ（自戒）
診断コード除去時に `backfill.py` の `import io` を巻き込み削除し、
`fetch_zip_text()` の `io.BytesIO` が `NameError` で全URL失敗した事例あり。
**エラー時は前回値を保持してスキップする設計のため、データが変わらないだけで
ワークフローは緑✅のまま**になり発見が遅れる。編集後は必ず
`python -m py_compile scripts/*.py` と実行ログの `WARN` 行を確認すること。

### 6-3. 失敗が緑✅で通る設計 → **2026-08-09に機械判定を追加（§7-3）**
（従来）バックフィルは1URLの失敗をスキップして継続する。
**実行時間が異常に短い（例: 全年で18秒）場合は取得失敗を疑う**こと。
判定はログ末尾の `=== coverage ===` / `=== tff coverage ===` の週数で行う。

（現在）上記の目視判定は残しつつ、**取得失敗・マッチ0件・週数減少があれば
ワークフローが赤くなる**ようにした。ログ末尾に `=== health ===` が出て
`RESULT: OK` / `DEGRADED` / `FAILED` を明示する。実行時間とダウンロード量も
health ブロックに出るため、「18秒で終わった」は数値で確認できる。
**ただし health を過信せず、coverage の週数は引き続き必ず目視すること。**

### 6-4. GitHub Web UIでは `.github/` がアップロードできない
ブラウザのフォルダドラッグはドット始まりディレクトリを除外する。
ワークフロー編集は「Add file → Create new file」でフルパス直接入力するか、
Claude Code なら通常の git push で解決する（**移行後はこの制約が消える**）。

### 6-5. Consolidatedコードの `+` 記号
`13874+` / `12460+` はコード文字列にプラス記号を含む。文字列比較で扱っており
数値変換してはいけない。

### 6-6. ★backfill の `start_year` がTFF履歴を消していた（2026-08-09 修正済み）
`backfill.py` にTFF側だけ「`start_year` より前の行を捨てる」処理があり、
**`backfill-history` の start_year に2005以外を入れるとTFF履歴が消える**状態だった。
Legacy側には同じ処理が無く非対称。しかもワークフローは差分を自動commit&pushするため
消失がリポジトリに確定し、run は緑✅で終わる（§6-3 と同じ形の事故）。

実測: start_year=2017 で TFF 1,052→501週（−551）、2020 で −708週、2026 で **−1,021週**。
Legacy は 1,127週のまま。ワークフロー入力の説明が「1986年まで遡及可能」なので、
別の年を入れる動機は実際にある。

→ 修正: フィルタを削除し、TFFもLegacyと同じ「**既存行は常に保持・同じ日付のみ上書き**」に統一。
`start_year`/`end_year` は「どの年のZIPを取りに行くか」だけを決める。
加えて**書き込み前に週数の減少を検査し、減る場合はCSVを一切書かずに異常終了**する。
`tests/test_parse.py::test_merge_preserves_history` で固定化済み。

### 6-7. Claude Code の実行環境から cftc.gov / github.io に出られない
組織のegressポリシーにより、Claude Codeセッションからは `www.cftc.gov` も
`mflab-inc.github.io` も **HTTP 403** で遮断される（2026-08-09確認）。
**迂回は禁止**（プロキシのREADMEに明記）。

実務上の影響は小さい: **GitHub Actions のランナーはこの制限を受けない**。
したがって公式データでの裏取りは以下で行う。

| やりたいこと | 方法 |
|---|---|
| 公式データでパーサを検証 | Actions の `backfill-history` を実行し `=== health ===` と coverage を読む |
| 最新週の取得を確認 | Actions の `weekly-cot-update` を手動実行しログを読む |
| 公開ページの表示確認 | しょうさんのブラウザで開く |

ローカル（セッション内）でできるのは `python tests/test_parse.py` と、
保存済みCSVからの `cot-feed.json` 再生成までに限られる。

---

## 7. 自動更新の仕組み

### weekly.yml
```yaml
cron: "30 0 * * 6"   # JST土曜 9:30（本命・COT公表後）
cron: "30 0 * * 2"   # JST火曜 9:30（米祝日順延の回収用）
workflow_dispatch: {}
permissions: contents: write
```
Legacy → TFF の順に取得し、変更があった場合のみ `data/` をcommit&push。
ファイル内の as-of 日付で判定する**冪等設計**のため重複実行しても安全。
TFF取得が失敗してもLegacy側は影響を受けない（try/exceptで分離済み）。

### backfill.yml
`workflow_dispatch` のみ。入力 `start_year`（既定 2005）と `allow_partial`（既定 false）。
Legacy年次ZIP → TFF統合ZIP → TFF年次ZIP の順に取得し全CSVを再構築、
末尾に `=== coverage ===` `=== tff coverage ===` `=== health ===` を出力する。
**新銘柄追加・パーサ修正後は必ずこれを再実行する。**

`start_year` は「どの年のZIPを取りに行くか」だけを決める（既存データは削られない・§6-6）。
TFF統合ZIP(2006-2016)は期間が掛かるときだけ取得する。
`allow_partial` は**公式から恒久的に削除された年がある場合にだけ** true にする。

### 7-3. 失敗検知（2026-08-09追加）
**backfill**: 取得失敗／マッチ0件／Legacy 0週／週数減少 のいずれかで **exit 1**。
python が異常終了するとワークフローの commit ステップが飛ぶため、
**取得漏れのあるデータはリポジトリに入らない**。週数減少時はCSVを一切書かない。

**weekly**: Legacy取得の失敗はその場で失敗させる。TFF失敗・鮮度異常は
**exit 0 のまま**にして（ここで落とすと取れたLegacyの最新週まで捨ててしまう）、
`GITHUB_OUTPUT` に `degraded=1` を出し、**commitを済ませた後の別ステップで** run を赤くする。
鮮度判定は「その週に居たか」ではなく「保存済みデータが14日以上古びていないか」で行う
（20者未満ルールによる1週の欠席でオオカミ少年にならないため・§3）。

詳細な条件表は `docs/SPEC.md` §11。

### リトライ
`http_get(url, timeout=180, retries=3, backoff=5)` に指数バックオフ実装済み。
ZIP取得は `fetch_zip_text()` が `timeout=300, retries=3, backoff=8` で呼ぶ。

---

## 8. ダッシュボード（`index.html`）

単一ファイル・外部依存はGoogle Fontsのみ。`data/cot-feed.json` を fetch して描画。

- **2タブ構成**: 「投機筋（Legacy）」/「AM／ヘッジファンド（TFF）」
- 折りたたみ式の**読み方ガイド**を常設（Legacy=極端度判定 / AM=中期バイアス /
  LevF=スクイーズ先行指標 / 乖離の読み方 / 「単独の売買シグナルではない」注意）
- 状態バッジ（中立・偏り・極端 / 整合・乖離・不一致）を色分け表示
- 52週推移スパークライン: Legacyは net 1本、TFFは AM(青)・LevF(橙) の2本重ね描き。
  **グレー横線は net=±0 ライン**、netバー中央の縦線も0軸
- 銘柄表示順は JS内の `ORDER` 配列でハードコード（**銘柄追加時はここへの追記が必須**）
- 免責を注記とガイドの両方に明記

---

## 9. 運用ルール（source_policy との整合・遵守必須）

1. 本フィードはCFTC公式ファイルの機械的写像だが、**レポートに数値を記載する際の
   確定ソースはCFTC公式のみ**。乖離疑義時は公式ビューアブル版を優先
2. レポート記載時は**対象週（火曜締め日）を必ず明記**
3. 「ネットロング○週連続」等の期間表現は**自前計算・記載しない**（品質基準文書 4-2 準拠）
4. 利用時は `meta.generated_at` と `report_date_latest` を確認し取得時刻を記録
5. 米祝日週は公表順延により土曜時点で前週データの場合がある
6. **状態表示は仮置き閾値による機械的な参考情報であり、売買助言として提示しない**

---

## 10. 未着手・今後の候補（未確定・実装前に要相談）

- 閾値の実測確定（現在すべて仮置き。EA-Risk-Monitor Phase 3 と同じ2段階方式を想定）
- 商品3銘柄（WTI/GOLD/銅）へのDisaggregatedレポート「Managed Money」区分の追加
  — TFFの代替として検討可能だが**未検証・未合意**
- 旧Googleスプレッドシート「CFTC」
  （`1R_v6V8aTzS9nuUjkfKNGMHJ6oUaQkinDu4PA9hij7qU`）はチャート閲覧用として併存中。
  シート側には「更新漏れ週が前週値で埋まる」問題が確認されているため、
  **データ参照には本フィードを使う**
- EA-Risk-Monitor（別リポジトリ）との連携は未着手

---

## 11. 作業分担の前提（重要）

これまでは「Claudeが全実装・検証 → しょうさんがGitHub Web UIで手動アップロード」
という分担だったため、**変更のたびにZIP納品＋手動アップロードが発生**していた。

**Claude Code移行後は git push が使えるため、この制約は解消された（2026-08-09 移行完了）。**
ただし以下は維持すること:
- コミット前に `python tests/test_parse.py` **全6ブロック合格**を確認
  （あわせて `python -m py_compile scripts/*.py tests/*.py`・§6-2の教訓）
- パーサ・符号規則の変更時は `backfill-history` を再実行し coverage で検証
- 公式データ形式に関する新しい発見は `docs/SPEC.md` に検証記録として追記
- **数値・URL・仕様は必ず公式で裏取りし、推測で埋めない**
  — ただしClaude Codeセッションから cftc.gov には出られない（§6-7）。
    裏取りは Actions 経由で行い、できなかった項目は「未確認」と明記する
- **出力パス・ファイル名・`schema_version` は変更しない**（レポート生成が参照しているため。
  変更が必要な場合は必ず事前に相談する）

---

## 12. 検証履歴（サマリー）

| 日付 | 内容 |
|---|---|
| 2026-07-27 | 初版構築・Legacy 11銘柄バックフィル成功（2005〜1,125週） |
| 2026-07-27 | v1.1: TFF追加（AM/LevF）。公式実データで恒等式検証 |
| 2026-07-27 | v1.2: Legacy/TFFタブ分離・読み方ガイド・状態表示3層を実装 |
| 2026-07-27 | TFF統合ZIPの日付形式問題を特定・修正（§6-1） |
| 2026-07-27 | `import io` 欠落を修正（§6-2）→ **TFF全期間取得成功・最終検収完了** |
| 2026-08-09 | Claude Code へ移行。`.gitignore` 追加（`__pycache__` の混入防止） |
| 2026-08-09 | **backfill の start_year がTFF履歴を削る不具合を修正（§6-6）**＋週数減少ガード追加 |
| 2026-08-09 | 失敗検知を機械判定化（§7-3）。backfillは exit 1、weeklyは commit後に run を赤く |
| 2026-08-09 | Legacyパーサも `_normalize_date()` に統一（§6-1 の再発防止）。出力不変を確認 |
| 2026-08-09 | nikkei225 の欠測17週が2005年前半に集中している事実を実測・§3を訂正 |
| 2026-08-09 | `docs/SPEC.md` 冒頭の混入行を削除、検証記録 §10・§11 を追記 |

現在のテスト構成（`tests/test_parse.py`・**全6ブロック合格が正常**）:
`main()`（Legacy符号規則）/ `test_tff()` / `test_state()` / `test_tff_legacy_bulk_format()` /
`test_legacy_date_formats()` / `test_merge_preserves_history()`

### 2026-08-09 の変更が既存データに影響しないことの確認
既存CSVから `cot-feed.json` を再生成して変更前と全文比較した結果、
**差分は `meta.generated_at` の1行のみ**。11銘柄すべての値・coverage・state が完全一致。
出力パス・ファイル名・`schema_version`（1.2）はいずれも変更していないため、
**公開URLとレポート側の参照はそのまま使える**（SPEC §10-3 / §10-5）。
