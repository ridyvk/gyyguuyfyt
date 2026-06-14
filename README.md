# KPI Scope

日本の上場企業を対象にした、企業分析向けKPI可視化Webアプリです。株価チャートではなく、財務KPI、業種別KPI、強み、注意点、違和感をタイルUIで素早く確認するためのMVPです。

企業名、証券コード、市場区分、33業種はJPX「上場銘柄一覧」の2026年5月31日時点データを使用しています。プライム・スタンダード・グロースの国内株式3,734社が対象です。財務KPIはEDINET設定後に実データへ自動差し替えされ、未取得企業のみモック表示になります。

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
EDINETの設定前、またはEDINETデータがまだない企業は、`src/lib/mockGenerator.ts`
が証券コードを固定シードとして生成するモックKPIを表示します。
EDINETから取得できた企業は実データへ自動的に差し替わり、取得元と対象期が画面に表示されます。
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
  lib/         モック生成、分析、スコア、検索、保存
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
