# PMI ThinkTank サイト

**サイトの文章はすべて Markdown（`.md`）で編集できます。** HTML や Python を触る必要はありません。

## どこを直せばいいか

| 直したいもの | 開くファイル |
|---|---|
| トップページ（見出し・説明文・ボタン） | `content/index.md` |
| 私たちについて（About / ミッション / メッセージ） | `content/about.md` |
| プロジェクト | `content/projects.md` |
| お問い合わせ | `content/contact.md` |
| メンバー（1人1ファイル） | `content/members/*.md` |
| サイト名・メニュー名・フッターのリンク | `content/site.md` |
| ブログ記事 | `blog/posts/*.md` |

`index.html` や `about/index.html` などの HTML は**自動生成されるファイル**です。直接編集してもビルド時に上書きされます。

## 反映のしかた

```bash
python3 blog/build.py
```

を実行してコミットするだけです。`main` にマージすると GitHub Actions が自動でビルドして公開します。

## ファイルの書き方

`---` で囲まれた部分が設定、その下が本文（Markdown）です。

```markdown
---
title: お問い合わせ
eyebrow: Contact
heading: お問い合わせ
---

ここに本文を書くと、見出しの下に表示されます。
**強調** や [リンク](https://example.com) も使えます。
```

`#` で始まる行はメモ書きで、サイトには表示されません。

### ブログ記事を追加する

`blog/posts/` に `.md` を1枚置くだけです。

```markdown
---
title: 記事タイトル
date: 2026-08-01
category: 論考
excerpt: 一覧に出る要約。
thumbnail: images/xxx.png
---

本文をMarkdownで書く。
```

`category` は `content/site.md` の `blog_categories` にある名前を使ってください。

### メンバーを追加する

`content/members/` に `.md` を置きます。**ファイル名がそのままURL**になります
（`ueno.md` → `/members/ueno/`）。

```markdown
---
name: 山田 太郎
role: Researcher
group: staff        # leadership または staff
order: 3            # 並び順（小さいほど先）
field: 専門領域      # 任意
twitter: account    # 任意。@は不要。書くとアイコンが出ます
website: https://example.com   # 任意。個人サイト。書くとアイコンが出ます
photo: assets/yamada.jpg   # 任意
---

紹介文をここに書くと、個人ページの本文になります。
```

## フォルダ構成

```
pmi-thinktank/
├─ content/          ← ★ここを編集する
│  ├─ site.md
│  ├─ index.md / about.md / projects.md / contact.md
│  └─ members/*.md
├─ blog/
│  ├─ posts/*.md     ← ★ブログ記事
│  ├─ build.py       ← ビルドスクリプト
│  ├─ style.css      ← ブログのデザイン
│  └─ images/
├─ home.css          ← サイトのデザイン
├─ logo.png / favicon.png / ogp.png
└─ *.html            ← 自動生成（編集しない）
```

デザイン（色・文字サイズ・余白）を変えたい場合は `home.css` と `blog/style.css` を編集します。
