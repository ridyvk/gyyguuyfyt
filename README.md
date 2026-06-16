# KPI Scope

日本の上場企業を対象にした、企業分析向けKPI可視化Webアプリです。株価チャートではなく、財務KPI、業種別KPI、強み、注意点、違和感をタイルUIで素早く確認するためのMVPです。

企業名、証券コード、市場区分、33業種はJPX「上場銘柄一覧」の2026年5月31日時点データを使用しています。プライム・スタンダード・グロースの国内株式3,734社が対象です。財務KPIはEDINET有価証券報告書とTDnet決算短信を統合し、企業ごとに新しい開示を優先します。

## 起動方法

Node.js 20.19以上を使用してください。

```bash
npm install
npm run dev
```

表示されたローカルURLをブラウザで開きます。

本番ビルドと静的検査:

```bash
npm run build
npm run lint
```

## GitHub Pagesで公開

このリポジトリには`.github/workflows/deploy-pages.yml`が含まれています。

1. GitHubで空のリポジトリを作成します。
2. このプロジェクト一式を`main`ブランチへpushします。
3. GitHubの`Settings > Pages > Build and deployment`で`GitHub Actions`を選択します。
4. Actionsのデプロイ完了後、表示されたURLを開きます。

画面遷移にはHash Routerを使用しているため、GitHub Pages上で詳細画面を再読み込みしても404になりません。

スマートフォンではブラウザの「ホーム画面に追加」からPWAとして利用できます。

## 主な画面

- **Dashboard**: 全企業数、ウォッチ数、注意企業数、平均スコア、業種・テーマ分布
- **Universe**: 上場企業3,734社の検索、絞り込み、並び替え、ページネーション、ウォッチ登録
- **Watchlist**: KPI、レーダー、トレンド、強み、注意点を企業カードで深掘り
- **Company Detail**: 12種のKPIタイル、3年推移、業種別KPI、自動コメント、分析メモ
- **Compare**: 最大5社の横棒・レーダー・KPIカード比較とBest表示

## データとスコア

`src/data/listedCompanies.json` にJPX企業マスターを同梱しています。
EDINET・TDnetから比較可能な財務データを取得できていない企業は「未取得」と表示し、架空のKPI・スコア・分析コメントは表示しません。
取得できた企業は実データへ自動的に差し替わり、取得元と対象期が画面に表示されます。
一覧画面では重いチャートを描画せず、画面単位の遅延読み込みで初期バンドルを抑えています。

企業マスターを最新化する場合は、Pythonで`pandas`と`xlrd`を導入後に次を実行します。

```bash
python scripts/update_jpx_companies.py
```

以下を0〜100点で算出します。

- 成長性
- 収益性
- 安全性
- キャッシュ創出力
- バリュエーション
- 総合スコア

スコアは投資判断ではなく、分析補助の目安です。

## 保存

`idb` を通じてブラウザのIndexedDBへ保存します。

- ウォッチリスト
- 比較対象
- 企業ごとの7項目の分析メモ

ブラウザのサイトデータを削除すると保存内容も消去されます。

## 技術構成

- React 18
- TypeScript
- Vite 8
- React Router
- Recharts 3
- IndexedDB (`idb`)
- Lucide React
- CSS

## ディレクトリ

```text
src/
  components/  共通UI・チャート
  context/     ウォッチリストと比較状態
  lib/         企業マスター、分析、スコア、検索、保存
  pages/       5つの画面
  types.ts     共通型
```

## EDINET自動更新

財務KPIは金融庁EDINETの有価証券報告書XBRLから取得できます。
GitHub Actionsの `Update EDINET financials` が3時間ごとに新しい開示を確認し、
更新された企業のKPI、注意フラグ、自動分析コメントを再生成します。

初回設定:

1. [EDINET API](https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1) でAPIキーを発行
2. GitHubリポジトリの `Settings > Secrets and variables > Actions` を開く
3. Repository secret `EDINET_API_KEY` に発行したキーを登録
4. `Actions > Update EDINET financials > Run workflow` を一度実行

初回は過去460日分を確認し、以後は直近7日を差分更新します。
画面には各企業のデータ取得元、対象期、開示日、実データKPI数を表示します。

制約:

- EDINETに掲載される開示単位で更新されるため、株価のリアルタイム更新ではありません。
- PER/PBRは株価データ契約が必要なため、EDINET実データ企業では判断不能表示です。
- 業種固有KPIはEDINETの標準タグで取得できない項目が多く、現時点では参考表示です。

## TDnet無料補完

TDnetの公開されている決算短信XBRLをAPIキーなしで取得し、EDINETより新しい開示の場合に財務KPIを更新します。
GitHub Actionsが3時間ごとに直近31日分を確認するため、ユーザー側の登録やSecret設定は不要です。

- EDINETとTDnetのうち、対象期と開示日時が新しいデータを優先
- 売上成長率、利益率、ROE、自己資本比率、営業CF、負債、ネットキャッシュなどを再計算
- スコア、注意フラグ、強み、自動分析コメントも更新後のKPIから再生成
- TDnet取得に一時的な障害があっても、直前の正常な財務データを保持
- 画面上に「EDINET実データ」または「TDnet決算短信」と取得元を表示

TDnetの公開閲覧期間は直近31日です。運用を継続することで決算発表企業が順次蓄積されますが、全上場企業・全KPIの取得を保証するものではありません。

## J-Quants株価自動更新

JPX公式のJ-Quants API V2から直近2取引日の日足終値と財務サマリーのEPS・BPSを取得し、最新終値、前日比、PER・PBRおよびバリュエーションスコアを自動再計算します。

初回設定:

1. [J-Quants](https://jpx-jquants.com/)でアカウントとAPIキーを発行
2. GitHubリポジトリの `Settings > Secrets and variables > Actions` を開く
3. Repository secret `JQUANTS_API_KEY` にAPIキーを登録
4. `Actions > Update EDINET financials > Run workflow` を実行

株価はリアルタイム配信ではなく日足終値です。取得可能な最新日はJ-Quantsの契約プランによって異なります。GitHub Actionsは3時間ごとに更新を確認します。
