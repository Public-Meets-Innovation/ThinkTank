# PMI ThinkTank Blog

Markdownで記事を書き、`build.py` を実行するとHTMLが生成される静的ブログです。

## サイト全体の構成

```
pmi-thinktank/                 ← リポジトリ／サイトのルート
├─ index.html                  ← トップページ（自動生成。編集は index.template.html を）
├─ index.template.html         ← トップページの雛形（ヒーロー・About・お問い合わせ）
├─ home.css                    ← トップページのデザイン
├─ requirements.txt
├─ .github/workflows/deploy.yml← push で自動ビルド＆公開
└─ blog/                       ← ブログ（/blog/ で公開）
   ├─ posts/                   ← 記事の本体（.md）。ここだけ触ればOK
   ├─ images/                  ← サムネイル・図版
   ├─ build.py                 ← 実行するとブログ＋トップページを生成
   ├─ style.css                ← ブログのデザイン
   ├─ index.html               ← 一覧（自動生成）
   └─ *.html                   ← 各記事ページ（自動生成）
```

`python blog/build.py` を実行すると、ブログの各ページに加えて
トップページ（ルート `index.html`）の「最新の記事」も自動更新されます。

## 記事を追加する手順

1. `posts/` に Markdown ファイルを1枚作る（ファイル名は自由。例: `2026-08-01-my-post.md`）
2. 先頭に frontmatter を書く：

   ```markdown
   ---
   title: 記事タイトル
   date: 2026-08-01
   category: Methodology
   thumbnail: images/xxx.svg   （任意。無ければ省略可）
   excerpt: 一覧に表示される要約。
   ---

   ここから本文をMarkdownで書く。

   ## 見出し

   - 箇条書き
   - **強調** や [リンク](https://example.com) も使える
   ```

3. ビルドを実行：

   ```bash
   python3 build.py
   ```

これで記事ページが作られ、`index.html` の一覧に **日付の新しい順** で自動的に並びます。

## カテゴリを変えたいとき

`build.py` 冒頭の `CATEGORIES` リストを編集してください。

## 記事を消したいとき

`posts/` から該当の `.md` を削除して `build.py` を再実行。
（生成済みの `*.html` は古いものが残る場合があるので、必要なら手動削除）
