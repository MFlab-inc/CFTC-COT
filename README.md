# CFTC-COT — 自社CFTC建玉フィード

CFTC公式のCOT（Commitments of Traders）レポートから、対象11銘柄の
**非商業（投機筋）・先物限定・スプレッド除く**ポジションを毎週自動取得し、
GitHub Pages上で機械可読フィードとして公開するリポジトリです。

- データの一次ソースは **CFTC公式のみ**（週次: `dea/newcot/deafut.txt`、履歴: 公式年次ZIP）
- 既存Googleスプレッドシート「CFTC」の `-data` シートと**同一スキーマ・同一符号規則**
  （USD/JPYは2026-07-21行でCFTC公式との照合一致を確認済み）

## 公開URL（GitHub Pages有効化後）

| 用途 | URL |
|---|---|
| ダッシュボード | `https://<org>.github.io/CFTC-COT/` |
| 統合フィード（JSON） | `https://<org>.github.io/CFTC-COT/data/cot-feed.json` |
| 銘柄別CSV | `https://<org>.github.io/CFTC-COT/data/csv/usdjpy.csv` 等 |

銘柄slug: `usdjpy` `gbpusd` `eurusd` `audusd` `sp500` `nikkei225` `nydow` `wti` `gold` `copper` `us10y`

## 初回セットアップ手順

1. **リポジトリ作成**：GitHubで新規リポジトリ `CFTC-COT` を作成（Public推奨。
   Pages公開するため実質公開データになる点に留意）し、本フォルダの内容をpush
2. **Actions権限**：Settings → Actions → General → Workflow permissions を
   **Read and write permissions** に設定（ワークフローがdata/をcommitするため）
3. **履歴バックフィル**：Actionsタブ → `backfill-history` → Run workflow
   （start_year 既定 2005。公式ZIPは1986年まで遡及可能）
   実行ログ末尾の coverage で各銘柄の開始週を確認する
4. **Pages有効化**：Settings → Pages → Source: Deploy from a branch →
   `main` / `/ (root)` を選択
5. 翌週以降は `weekly-cot-update` が自動実行（下記スケジュール）

## 更新スケジュール

COT公表は通常 **米国時間 金曜 15:30 ET**（データは同週火曜締め）＝ JST土曜早朝。

- cron `30 0 * * 6`（JST 土曜 9:30）… 本命
- cron `30 0 * * 2`（JST 火曜 9:30）… 米祝日で公表が順延した週の回収用

スクリプトはファイル内の as-of 日付で判定する冪等設計のため、
重複実行しても二重登録は発生しません。手動実行はActionsタブから可能です。

## データ仕様

詳細は [docs/SPEC.md](docs/SPEC.md) を参照。要点:

- CSV列: `date,all,long,short,net`（既存シート `-data` 互換。`price` 列は廃止）
- `date` は火曜締め日（YYYY-MM-DD）
- **USD/JPYのみ符号変換あり**：円先物ショート＝`long`（USD/JPY買い方向）、
  net プラス＝投機筋の円ショート優勢
- その他銘柄は生値（`long`=非商業ロング、`short`=−非商業ショート）

## source_policy との関係

1. 本フィードは**参照・集計用**。レポートに数値を記載する場合の確定ソースは
   従来どおり **CFTC公式（cftc.gov）のみ**（本フィードは公式ファイルの機械的
   写像だが、乖離が疑われる場合は公式ビューアブル版を優先）
2. レポート記載時は**対象週（火曜締め日）を必ず明記**
3. 「ネットロング○週連続」等の期間表現の自前計算禁止ルールは従来どおり適用

## 既知の制約

- `sp500`（13874+）と `nydow`（12460+）はConsolidatedコードのため、
  コード導入前の期間は欠測になる（バックフィルのcoverage出力で確認可能）
- 週次ファイル `deafut.txt` はCDNキャッシュで稀に旧週が返ることがある。
  その場合も火曜cronで自動回収される
- 公式FAQのとおり、報告対象トレーダーが20者未満になった銘柄はその週の
  レポートから除外される（欠測週が生じ得る）

## ローカル実行

```bash
export PYTHONPATH=scripts
python scripts/backfill.py --start-year 2005   # 履歴再構築
python scripts/weekly_update.py                # 最新週の取り込み
python tests/test_parse.py                     # パーサ・符号規則テスト
```

依存ライブラリなし（Python 3.10+ 標準ライブラリのみ）。
