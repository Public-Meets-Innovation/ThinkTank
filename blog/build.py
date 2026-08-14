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
import hashlib
from pathlib import Path
import markdown

ROOT = Path(__file__).parent          # blog/ ディレクトリ
POSTS_DIR = ROOT / "posts"
SITE_ROOT = ROOT.parent               # リポジトリのルート（トップページを置く場所）

def _asset_ver(path):
    """CSSファイルの中身のハッシュをキャッシュバスターにする。
    手動でバージョン番号を上げ忘れて古いCSSがキャッシュされ続ける事故を防ぐため、
    内容が変われば自動的にクエリ文字列も変わる仕組みにしている。"""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()[:8]
    except FileNotFoundError:
        return "0"

HOME_CSS_VER = _asset_ver(SITE_ROOT / "home.css")
BLOG_CSS_VER = _asset_ver(ROOT / "style.css")

# 本番公開URL（OGPの絶対URL生成に使用）。ogp.png / logo.png / favicon.png はリポジトリルート直下。
# ogp.png = SNSシェア用（1200x630）、logo.png = ヘッダー表示用、favicon.png = タブアイコン。
SITE_BASE_URL = "https://thinktank.pmi.or.jp/"
DEFAULT_DESCRIPTION = "PMI ThinkTank（Public Meets Innovation）— 事実とデータ、人文・社会科学の知に基づく政治・政策のシンクタンク。"

# 全ページ共通フォント（英数字: Helvetica Neue / 日本語: Noto Sans JP）
FONT_LINKS = """  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet" />"""

# 一覧上部のカテゴリナビ（表示順）
CATEGORIES = [
    "All", "調査レポート", "論考", "解説", "プレスリリース",
]

# ---- 共通パーツ -------------------------------------------------------------

def image_size(path):
    """PNG / JPEG の寸法を外部ライブラリなしで読む。取得できなければ None。
    og:image:width / height を宣言しておくと、SNS側が画像を落とす前にカードを
    描画できるため、初回シェア時に画像が出ないケースを減らせる。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    # PNG: 8バイトのシグネチャ + IHDR（長さ4 + "IHDR"4 + 幅4 + 高さ4）
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return (int.from_bytes(data[16:20], "big"),
                int.from_bytes(data[20:24], "big"))
    # JPEG: SOFn マーカーを走査して寸法を取る
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            # SOF0-SOF15（DHT/JPG/DAC のような非SOFは除外）
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return (int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            seg_len = int.from_bytes(data[i + 2:i + 4], "big")
            if seg_len <= 0:
                break
            i += 2 + seg_len
    return None

def social_meta_head(prefix, title, canonical_path, description="", image_path="ogp.png"):
    """favicon と OGP / Twitter Card のメタタグ。
    prefix: サイトルートまでの相対パス（例 "" / "../"）。favicon はここから解決。
    canonical_path: サイトルートからの絶対パス（例 "" / "about/" / "blog/xxx.html"）。og:url に使用。
    image_path: サイトルートからの相対パス（例 "ogp.png" / "blog/images/xxx.jpg"）。og:image に使用。
    """
    desc = description or DEFAULT_DESCRIPTION
    image_url = SITE_BASE_URL + image_path
    page_url = SITE_BASE_URL + canonical_path
    size = image_size(SITE_ROOT / image_path)
    dims = ""
    if size:
        dims = (f'\n  <meta property="og:image:width" content="{size[0]}" />'
                f'\n  <meta property="og:image:height" content="{size[1]}" />')
    return f"""  <link rel="icon" type="image/png" href="{prefix}favicon.png" />
  <link rel="canonical" href="{page_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:locale" content="ja_JP" />
  <meta property="og:site_name" content="PMI ThinkTank" />
  <meta property="og:title" content="{html.escape(title)}" />
  <meta property="og:description" content="{html.escape(desc)}" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:image:secure_url" content="{image_url}" />{dims}
  <meta property="og:image:alt" content="{html.escape(title)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{html.escape(title)}" />
  <meta name="twitter:description" content="{html.escape(desc)}" />
  <meta name="twitter:image" content="{image_url}" />
  <meta name="twitter:image:alt" content="{html.escape(title)}" />"""

def header_html():
    return """  <header class="site-header">
    <div class="site-header__inner">
      <div class="site-header__left">
        <a href="../" class="site-home">← PMI ThinkTank</a>
        <a href="index.html" class="logo">
          <img src="../logo.png" alt="PMI ThinkTank" />
        </a>
      </div>
      <button class="theme-toggle" type="button" role="switch" aria-label="ライト/ダーク切り替え"><span class="tt-opt" data-mode="L">L</span><span class="tt-opt" data-mode="D">D</span></button>
    </div>
  </header>"""

def footer_html():
    return """  <footer class="site-footer">
    <div class="site-footer__inner">
      <span>© 2026 PMI ThinkTank</span>
      <div class="social">
        <a href="https://x.com/PMI__official" target="_blank" rel="noopener">Twitter</a>
        <a href="https://note.com/pmi_thinktank" target="_blank" rel="noopener">note</a>
      </div>
    </div>
  </footer>"""

# テーマ（ライト/ダーク）の適用スクリプト
THEME_HEAD_JS = """  <script>
  (function(){try{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
  </script>"""

THEME_TOGGLE_JS = """  <script>
  (function(){
    var btn=document.querySelector('.theme-toggle');
    if(!btn)return;
    function cur(){return document.documentElement.getAttribute('data-theme')||'light';}
    function render(){
      var d=cur()==='dark';
      var L=btn.querySelector('[data-mode=\\"L\\"]'), D=btn.querySelector('[data-mode=\\"D\\"]');
      if(L)L.classList.toggle('is-active',!d);
      if(D)D.classList.toggle('is-active',d);
    }
    render();
    btn.addEventListener('click',function(e){
      var opt=e.target.closest('[data-mode]');
      var next = opt ? (opt.getAttribute('data-mode')==='D'?'dark':'light')
                     : (cur()==='dark'?'light':'dark');
      document.documentElement.setAttribute('data-theme',next);
      try{localStorage.setItem('theme',next);}catch(e){}
      render();
    });
  })();
  </script>"""

def nav_html():
    items = []
    for i, c in enumerate(CATEGORIES):
        cls = ' class="is-active"' if i == 0 else ""
        cat_val = "all" if i == 0 else html.escape(c)
        items.append(
            f'    <a href="#"{cls} data-cat="{cat_val}">{html.escape(c)}</a>')
    return '  <nav class="category-nav">\n' + "\n".join(items) + "\n  </nav>"

def page(title, body, canonical_path="blog/", description="", image_path="ogp.png"):
    # ブログページはすべて blog/ 直下（記事も一覧も）なのでサイトルートまでは常に "../"
    social = social_meta_head("../", title, canonical_path, description, image_path)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
{social}
{FONT_LINKS}
{THEME_HEAD_JS}
  <link rel="stylesheet" href="style.css?v={BLOG_CSS_VER}" />
</head>
<body>
{header_html()}
{body}
{footer_html()}
{THEME_TOGGLE_JS}
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
    # 記事上部のヒーロー画像は本文先頭画像（＝サムネイル）と重複するため出力しない。
    # thumbnail は一覧カードのサムネイルとしてのみ使用する。
    body = f"""  <article class="article">
    <a href="index.html" class="article__back">← ブログ一覧へ戻る</a>
    <h1 class="article__title">{html.escape(p["title"])}</h1>
    <div class="article__meta">{html.escape(p["category"])} ・ {date_ja(p["date"])}</div>
    <div class="article__body">
{p["body_html"]}
    </div>
  </article>"""
    # OGP画像は記事のサムネイルを優先。無ければ共通ロゴにフォールバック。
    image_path = f'blog/{p["thumbnail"]}' if p["thumbnail"] else "ogp.png"
    out = ROOT / f'{p["slug"]}.html'
    out.write_text(
        page(f'{p["title"]} | PMI ThinkTank Blog', body,
             canonical_path=f'blog/{p["slug"]}.html', description=p["excerpt"],
             image_path=image_path),
        encoding="utf-8")
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
        cards.append(f"""    <article class="post" data-category="{html.escape(p["category"])}">
      <a href="{link}"><h2 class="post__title">{html.escape(p["title"])}</h2></a>
      <div class="post__meta">
        <span class="post__cat">{html.escape(p["category"])}</span>
        <span>{date_ja(p["date"])}</span>
      </div>
{thumb}{excerpt}      <a href="{link}" class="post__more">read more</a>
    </article>""")

    empty = '    <p class="post-empty" hidden>このカテゴリの記事はまだありません。</p>'
    body = nav_html() + '\n\n  <main class="post-list">\n' + \
        "\n\n".join(cards) + "\n" + empty + "\n  </main>\n" + FILTER_JS
    (ROOT / "index.html").write_text(
        page("PMI ThinkTank Blog", body, canonical_path="blog/"), encoding="utf-8")

# 一覧のカテゴリ絞り込み（クリックで表示/非表示を切り替え）
FILTER_JS = """  <script>
  (function () {
    var nav = document.querySelector(".category-nav");
    var posts = Array.prototype.slice.call(document.querySelectorAll(".post"));
    var empty = document.querySelector(".post-empty");
    if (!nav) return;

    function apply(cat) {
      var shown = 0;
      posts.forEach(function (el) {
        var match = cat === "all" || el.getAttribute("data-category") === cat;
        el.hidden = !match;
        if (match) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    }

    nav.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-cat]");
      if (!a) return;
      e.preventDefault();
      nav.querySelectorAll("a").forEach(function (x) {
        x.classList.remove("is-active");
      });
      a.classList.add("is-active");
      apply(a.getAttribute("data-cat"));
    });
  })();
  </script>"""

# ---- トップレベルの各ページ（トップ/私たちについて/プロジェクト/お問い合わせ）----

# ヘッダーナビ（全トップレベルページ共通）。key は clean URL のディレクトリ名。
SITE_NAV = [
    ("about", "私たちについて"),
    ("projects", "プロジェクト"),
    ("blog", "ブログ"),
    ("contact", "お問い合わせ"),
]

def site_nav(active, prefix):
    """prefix はサイトルートまでの相対パス（ルート="" / サブページ="../"）。"""
    links = []
    for key, label in SITE_NAV:
        cls = ' class="is-active"' if key == active else ''
        links.append(f'        <a href="{prefix}{key}/"{cls}>{html.escape(label)}</a>')
    home = prefix if prefix else './'
    return ('  <nav class="nav">\n'
            '    <div class="nav__inner">\n'
            f'      <a href="{home}" class="nav__logo"><img src="{prefix}logo.png" alt="PMI ThinkTank" /></a>\n'
            '      <div class="nav__links">\n' + "\n".join(links) + "\n"
            '      </div>\n'
            '    </div>\n'
            '  </nav>')

# 「私たちについて」クラスタ内のサブナビ（私たちについて/メンバー/お問い合わせ）
ABOUT_SUBNAV = [
    ("about", "私たちについて"),
    ("members", "メンバー"),
    ("contact", "お問い合わせ"),
]

def about_subnav(active, prefix):
    items = []
    for key, label in ABOUT_SUBNAV:
        cls = ' class="is-active"' if key == active else ''
        items.append(f'        <a href="{prefix}{key}/"{cls}>{html.escape(label)}</a>')
    return '      <div class="subnav">\n' + "\n".join(items) + "\n      </div>"

# メンバー一覧（写真は未着手のためイニシャルのプレースホルダー表示）
MEMBERS_LEADERSHIP = [
    ("石山 アンジュ", "Chair"),
    ("田中 佑典", "Executive Director"),
]
MEMBERS_STAFF = [
    ("上野 裕太郎", "Head of Research"),
    ("小林 駿斗", "Visiting Researcher"),
]

def member_cards(members):
    cards = []
    for name, role in members:
        initial = name.strip()[0]
        cards.append(f"""        <div class="member-card">
          <div class="member-card__avatar" aria-hidden="true">{html.escape(initial)}</div>
          <div class="member-card__body">
            <div class="member-card__name">{html.escape(name)}</div>
            <div class="member-card__role">{html.escape(role)}</div>
          </div>
        </div>""")
    return "\n".join(cards)

def site_footer():
    return ('  <footer class="site-foot">\n'
            '    <div class="wrap site-foot__inner">\n'
            '      <span>© 2026 PMI ThinkTank (Public Meets Innovation)</span>\n'
            '      <div class="site-foot__social">\n'
            '        <a href="https://x.com/PMI__official" target="_blank" rel="noopener">Twitter</a>\n'
            '        <a href="https://note.com/pmi_thinktank" target="_blank" rel="noopener">note</a>\n'
            '      </div>\n'
            '    </div>\n'
            '  </footer>')

def site_shell(title, active, body_html, prefix, canonical_path, description=""):
    desc = (f'\n  <meta name="description" content="{html.escape(description)}" />'
            if description else "")
    social = social_meta_head(prefix, title, canonical_path, description)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>{desc}
{social}
{FONT_LINKS}
  <link rel="stylesheet" href="{prefix}home.css?v={HOME_CSS_VER}" />
</head>
<body>
{site_nav(active, prefix)}
{body_html}
{site_footer()}
</body>
</html>
"""

def home_cards(posts, n=3):
    cards = []
    for p in posts[:n]:
        link = f'blog/{p["slug"]}.html'
        thumb = ""
        if p["thumbnail"]:
            thumb = (f'<a href="{link}" class="home-card__thumb">'
                     f'<img src="blog/{html.escape(p["thumbnail"])}" alt="" /></a>')
        cards.append(f"""      <article class="home-card">
        {thumb}
        <div class="home-card__body">
          <div class="home-card__meta"><span class="home-card__cat">{html.escape(p["category"])}</span><span>{date_ja(p["date"])}</span></div>
          <a href="{link}"><h3 class="home-card__title">{html.escape(p["title"])}</h3></a>
        </div>
      </article>""")
    return "\n".join(cards)

def render_toplevel(posts, n=3):
    partials = SITE_ROOT / "partials"
    # (partial, out_path, active_key, prefix, canonical_path, title, description)
    pages = [
        ("index.body.html", "index.html", "index", "", "",
         "PMI ThinkTank", DEFAULT_DESCRIPTION),
        ("about.body.html", "about/index.html", "about", "../", "about/",
         "私たちについて | PMI ThinkTank", ""),
        ("members.body.html", "members/index.html", "members", "../", "members/",
         "メンバー | PMI ThinkTank", ""),
        ("projects.body.html", "projects/index.html", "projects", "../", "projects/",
         "プロジェクト | PMI ThinkTank", ""),
        ("contact.body.html", "contact/index.html", "contact", "../", "contact/",
         "お問い合わせ | PMI ThinkTank", ""),
    ]
    # サブナビを持つページ（私たちについてクラスタ）
    subnav_pages = {"about", "members", "contact"}
    for partial, out, active, prefix, canonical, title, desc in pages:
        body = (partials / partial).read_text(encoding="utf-8")
        if active == "index":
            body = body.replace("<!--LATEST_POSTS-->", home_cards(posts, n))
        if active in subnav_pages:
            body = body.replace("<!--SUBNAV-->", about_subnav(active, prefix))
        if active == "members":
            body = body.replace("<!--LEADERSHIP-->", member_cards(MEMBERS_LEADERSHIP))
            body = body.replace("<!--STAFF-->", member_cards(MEMBERS_STAFF))
        out_path = SITE_ROOT / out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            site_shell(title, active, body, prefix, canonical, desc), encoding="utf-8")
    print(f"  トップレベル生成: / /about/ /members/ /projects/ /contact/（最新{min(n, len(posts))}件掲載）")

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
    render_toplevel(posts)
    print(f"\n✅ 完了: {len(posts)}件の記事 + ブログ一覧 + トップレベル4ページを生成しました。")

if __name__ == "__main__":
    main()
