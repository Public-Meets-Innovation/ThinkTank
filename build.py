#!/usr/bin/env python3
"""
PMI ThinkTank Blog ビルドスクリプト

使い方:
    python3 build.py

posts/ 内の *.md を読み込み、記事ページと index.html を生成する。
記事の追加は「posts/ に .md を1枚置いて、このスクリプトを実行する」だけ。
"""

import re
import html
from pathlib import Path
import markdown

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"

# 一覧上部のカテゴリナビ（表示順）
CATEGORIES = [
    "All", "調査レポート", "政策提言", "解説", "お知らせ",
]

# ---- 共通パーツ -------------------------------------------------------------

def header_html():
    return """  <header class="site-header">
    <div class="site-header__inner">
      <a href="index.html" class="logo">
        pmi<span class="dot">.</span>thinktank
      </a>
    </div>
  </header>"""

def footer_html():
    return """  <footer class="site-footer">
    <div class="site-footer__inner">
      <span>© 2026 PMI ThinkTank</span>
      <div class="social">
        <a href="#">LinkedIn</a>
        <a href="#">X (Twitter)</a>
        <a href="#">note</a>
      </div>
    </div>
  </footer>"""

def nav_html():
    items = []
    for i, c in enumerate(CATEGORIES):
        cls = ' class="is-active"' if i == 0 else ""
        items.append(f'    <a href="#"{cls}>{html.escape(c)}</a>')
    return '  <nav class="category-nav">\n' + "\n".join(items) + "\n  </nav>"

def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
{header_html()}
{body}
{footer_html()}
</body>
</html>
"""

# ---- frontmatter パーサ -----------------------------------------------------

def parse_post(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
    if not m:
        raise ValueError(f"frontmatter がありません: {path.name}")
    meta_block, body_md = m.group(1), m.group(2)

    meta = {}
    for line in meta_block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip()
        # 前後の対になるクオートを除去
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        meta[key.strip()] = val

    for req in ("title", "date", "category"):
        if req not in meta:
            raise ValueError(f"{path.name}: '{req}' が frontmatter にありません")

    meta["slug"] = path.stem                 # 出力ファイル名に使用
    meta["body_html"] = markdown.markdown(
        body_md, extensions=["extra", "sane_lists"]
    )
    meta.setdefault("excerpt", "")
    meta.setdefault("thumbnail", "")
    return meta

def date_ja(iso):
    y, mth, d = iso.split("-")
    return f"{int(y)}年{int(mth)}月{int(d)}日"

# ---- 記事ページ生成 ---------------------------------------------------------

def render_article(p):
    thumb = ""
    if p["thumbnail"]:
        thumb = (f'    <div class="article__hero">'
                 f'<img src="{html.escape(p["thumbnail"])}" alt="" /></div>\n')
    body = f"""  <article class="article">
    <a href="index.html" class="article__back">← ブログ一覧へ戻る</a>
    <h1 class="article__title">{html.escape(p["title"])}</h1>
    <div class="article__meta">{html.escape(p["category"])} ・ {date_ja(p["date"])}</div>
{thumb}    <div class="article__body">
{p["body_html"]}
    </div>
  </article>"""
    out = ROOT / f'{p["slug"]}.html'
    out.write_text(page(f'{p["title"]} | PMI ThinkTank Blog', body), encoding="utf-8")
    return out.name

# ---- 一覧ページ生成 ---------------------------------------------------------

def render_index(posts):
    cards = []
    for p in posts:
        link = f'{p["slug"]}.html'
        thumb = ""
        if p["thumbnail"]:
            thumb = (f'      <a href="{link}" class="post__thumb">'
                     f'<img src="{html.escape(p["thumbnail"])}" alt="" /></a>\n')
        excerpt = ""
        if p["excerpt"]:
            excerpt = f'      <p class="post__excerpt">{html.escape(p["excerpt"])}</p>\n'
        cards.append(f"""    <article class="post">
      <a href="{link}"><h2 class="post__title">{html.escape(p["title"])}</h2></a>
      <div class="post__meta">
        <span class="post__cat">{html.escape(p["category"])}</span>
        <span>{date_ja(p["date"])}</span>
      </div>
{thumb}{excerpt}      <a href="{link}" class="post__more">read more</a>
    </article>""")

    body = nav_html() + '\n\n  <main class="post-list">\n' + \
        "\n\n".join(cards) + "\n  </main>"
    (ROOT / "index.html").write_text(
        page("PMI ThinkTank Blog", body), encoding="utf-8")

# ---- main -------------------------------------------------------------------

def main():
    md_files = sorted(POSTS_DIR.glob("*.md"))
    if not md_files:
        print("posts/ に .md がありません。")
        return
    posts = [parse_post(f) for f in md_files]
    posts.sort(key=lambda p: p["date"], reverse=True)   # 新しい順

    for p in posts:
        name = render_article(p)
        print(f"  記事生成: {name}")
    render_index(posts)
    print(f"\n✅ 完了: {len(posts)}件の記事と index.html を生成しました。")

if __name__ == "__main__":
    main()
