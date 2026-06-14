# KPI Scope

日本の上場企業を、財務KPI・業種別KPI・強み・注意点・違和感から直感的に分析する React + TypeScript + Vite アプリです。

- Universe: 上場企業全体から検索・絞り込み
- Watchlist: 気になる企業を保存して深掘り
- Company Detail: KPIタイル、レーダー、3年推移、メモ
- Compare: 最大5社を横棒・レーダー・比較カードで比較
- IndexedDB: ウォッチリストと企業メモをブラウザに保存
- JPX上場銘柄マスター3,734社を収録し、財務値はMVP用の合成データを使用

> スコアは投資判断ではなく、企業分析を補助する目安です。

## Links

- GitHub repository: https://github.com/ridyvk/gyyguuyfyt
- Instant preview: https://stackblitz.com/github/ridyvk/gyyguuyfyt
- GitHub Pages: https://ridyvk.github.io/gyyguuyfyt/

## GitHub Pagesの初回設定

1. https://github.com/ridyvk/gyyguuyfyt/settings/pages を開く
2. `Build and deployment` の `Source` を `GitHub Actions` にする
3. https://github.com/ridyvk/gyyguuyfyt/actions/workflows/deploy-pages.yml を開き、`Run workflow` を実行する

以後は `main` ブランチへの更新ごとに自動デプロイされます。

## Local development

```bash
npm install
npm run dev
```

本番ビルド:

```bash
npm run build
npm run preview
```

## Tech stack

React / TypeScript / Vite / React Router / Recharts / IndexedDB (idb)
