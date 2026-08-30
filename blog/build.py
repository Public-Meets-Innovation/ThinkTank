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
import yaml

ROOT = Path(__file__).parent          # blog/ ディレクトリ
POSTS_DIR = ROOT / "posts"
SITE_ROOT = ROOT.parent               # リポジトリのルート（トップページを置く場所）
CONTENT_DIR = SITE_ROOT / "content"   # ページ本文の Markdown 置き場

# ---- content/ の Markdown を読む -------------------------------------------

def load_md(path):
    """--- で囲んだ YAML（frontmatter）と、その下の Markdown 本文を返す。
    サイトの文言は全部 content/*.md にあり、HTML や Python を触らずに編集できる。"""
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not m:
        return {}, raw
    meta = yaml.safe_load(m.group(1)) or {}
    return meta, m.group(2)

def md_to_html(text):
    """Markdown を HTML に。空なら空文字。"""
    text = (text or "").strip()
    if not text:
        return ""
    return markdown.markdown(text, extensions=["extra", "sane_lists"])

def inline_md(text):
    """1行ぶんの Markdown（**強調** など）。<p> で包まない。"""
    out = md_to_html(text)
    return re.sub(r"^<p>(.*)</p>$", r"\1", out, flags=re.DOTALL).strip()

def clause_spans(text):
    """読点で区切って <span> に包む。inline-block と組み合わせることで、
    折り返しが語句の途中ではなく意味の切れ目で起きるようにする。"""
    parts = [p for p in re.split(r"(?<=、)", text) if p]
    return "".join(f"<span>{inline_md(p)}</span>" for p in parts)

SITE, _ = load_md(CONTENT_DIR / "site.md")

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
SITE_BASE_URL = SITE["base_url"]
DEFAULT_DESCRIPTION = SITE["description"]

# 生成物であることを明示するバナー。生成HTMLを直接編集してもビルド時に
# 上書きされてしまうため、編集すべき元ファイルの場所をここで案内する。
GENERATED_BANNER = """<!--
  ============================================================
  このファイルは build.py が自動生成しています。直接編集しないでください。
  （編集してもビルド時に上書きされ、公開サイトには反映されません）

  編集する場所（すべて Markdown です）:
    ・トップ/私たちについて/プロジェクト/お問い合わせ
        → content/index.md, about.md, projects.md, contact.md
    ・メンバー（1人1ファイル。ファイル名がURLになります）
        → content/members/*.md
    ・サイト名・メニュー名・フッターのリンクなど
        → content/site.md
    ・ブログ記事
        → blog/posts/*.md

  反映方法: python blog/build.py を実行してコミット
           （main にマージすると GitHub Actions が自動ビルドします）
  ============================================================
-->"""

# 全ページ共通フォント（英数字: Helvetica Neue / 日本語: Noto Sans JP）
FONT_LINKS = """  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet" />"""

# 一覧上部のカテゴリナビ（表示順）。content/site.md の blog_categories で変える。
CATEGORIES = SITE["blog_categories"]

# 記事に thumbnail を書かなかったときの既定画像（サイトルートからのパス）。
DEFAULT_THUMBNAIL = SITE.get("default_thumbnail", "ogp.png")

def thumb_src(post, blog_prefix, root_prefix):
    """カードに出すサムネイルのパス。
    記事の thumbnail は blog/ を基準に書かれ、既定画像はサイトルート基準なので、
    どちらを使うかで基準が変わる。呼び出し側のページ位置に合わせて解決する。"""
    if post["thumbnail"]:
        return blog_prefix + post["thumbnail"]
    return root_prefix + DEFAULT_THUMBNAIL

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
  <meta property="og:site_name" content="{html.escape(SITE["site_name"])}" />
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

def header_html(root_prefix, blog_prefix):
    """root_prefix: サイトルートまでの相対パス。blog_prefix: blog/ までの相対パス。
    一覧は blog/ 直下、記事は blog/<slug>/ と深さが違うため両方を受け取る。"""
    blog_home = blog_prefix or "./"
    return f"""  <header class="site-header">
    <div class="site-header__inner">
      <div class="site-header__left">
        <a href="{root_prefix}" class="site-home">← {html.escape(SITE["site_name"])}</a>
        <a href="{blog_home}" class="logo">
          <img class="logo__light" src="{root_prefix}logo.png" alt="{html.escape(SITE["site_name"])}" />
          <img class="logo__dark" src="{root_prefix}logo-reverse.png" alt="{html.escape(SITE["site_name"])}" />
        </a>
      </div>
      <button class="theme-toggle" type="button" role="switch" aria-label="ライト/ダーク切り替え"><span class="tt-opt" data-mode="L">L</span><span class="tt-opt" data-mode="D">D</span></button>
    </div>
  </header>"""

def footer_html():
    # フッターの文言・リンクは content/site.md から。トップ側と二重管理しない。
    links = "\n".join(
        f'        <a href="{html.escape(s["href"])}" target="_blank" rel="noopener">'
        f'{html.escape(s["label"])}</a>'
        for s in SITE["social"])
    return ('  <footer class="site-footer">\n'
            '    <div class="site-footer__inner">\n'
            f'      <span>{html.escape(SITE["copyright"])}</span>\n'
            '      <div class="social">\n' + links + '\n'
            '      </div>\n'
            '    </div>\n'
            '  </footer>')

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

def page(title, body, canonical_path="blog/", description="", image_path="ogp.png",
         blog_prefix=""):
    """blog_prefix は blog/ ディレクトリまでの相対パス。
    一覧（blog/index.html）は ""、記事（blog/<slug>/index.html）は "../"。"""
    root_prefix = "../" + blog_prefix
    social = social_meta_head(root_prefix, title, canonical_path, description, image_path)
    return f"""<!DOCTYPE html>
{GENERATED_BANNER}
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
{social}
{FONT_LINKS}
{THEME_HEAD_JS}
  <link rel="stylesheet" href="{blog_prefix}style.css?v={BLOG_CSS_VER}" />
</head>
<body>
{header_html(root_prefix, blog_prefix)}
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
    # 記事は blog/<slug>/index.html に置き、URLから .html を無くす。
    # blog/ 直下より1段深くなるので、本文中の images/... や pdf/... も1段ぶん持ち上げる。
    blog_prefix = "../"
    body_html = re.sub(r'(src|href)="(images|pdf)/', rf'\1="{blog_prefix}\2/',
                       p["body_html"])
    # 記事上部のヒーロー画像は本文先頭画像（＝サムネイル）と重複するため出力しない。
    # thumbnail は一覧カードのサムネイルとしてのみ使用する。
    body = f"""  <article class="article">
    <a href="{blog_prefix}" class="article__back">← ブログ一覧へ戻る</a>
    <h1 class="article__title">{html.escape(p["title"])}</h1>
    <div class="article__meta">{html.escape(p["category"])} ・ {date_ja(p["date"])}</div>
    <div class="article__body">
{body_html}
    </div>
  </article>"""
    # OGP画像は記事のサムネイルを優先。無ければ共通ロゴにフォールバック。
    image_path = f'blog/{p["thumbnail"]}' if p["thumbnail"] else DEFAULT_THUMBNAIL
    out = ROOT / p["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        page(f'{p["title"]} | {SITE["site_name"]} Blog', body,
             canonical_path=f'blog/{p["slug"]}/', description=p["excerpt"],
             image_path=image_path, blog_prefix=blog_prefix),
        encoding="utf-8")
    return f'{p["slug"]}/'

# ---- 一覧ページ生成 ---------------------------------------------------------

def render_legacy_redirects(posts):
    """記事URLを blog/<slug>.html から blog/<slug>/ に変えたため、
    旧URLが 404 にならないよう転送用のページを残す。GitHub Pages には
    サーバー側のリダイレクト設定が無いので、meta refresh + canonical で行う。
    旧URLが参照されなくなったら、この関数ごと消してよい。"""
    for p in posts:
        target = f'{p["slug"]}/'
        (ROOT / f'{p["slug"]}.html').write_text(
            f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8" />
<meta http-equiv="refresh" content="0; url={target}" />
<link rel="canonical" href="{SITE_BASE_URL}blog/{target}" />
<meta name="robots" content="noindex" />
<title>移動しました</title>
</head>
<body><p><a href="{target}">このページは移動しました</a></p></body>
</html>
""", encoding="utf-8")
    print(f"  旧URLからの転送ページ: {len(posts)}件")

def render_index(posts):
    cards = []
    for p in posts:
        link = f'{p["slug"]}/'
        # 一覧は blog/ 直下。thumbnail 未指定なら既定画像（サイトルート基準）を使う。
        thumb = (f'      <a href="{link}" class="post__thumb">'
                 f'<img src="{html.escape(thumb_src(p, "", "../"))}" alt="" /></a>\n')
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

def site_nav(active, prefix):
    """prefix はサイトルートまでの相対パス（ルート="" / サブページ="../"）。"""
    links = []
    for item in SITE["nav"]:
        cls = ' class="is-active"' if item["key"] == active else ''
        links.append(f'        <a href="{prefix}{item["key"]}/"{cls}>'
                     f'{html.escape(item["label"])}</a>')
    home = prefix if prefix else './'
    return ('  <nav class="nav">\n'
            '    <div class="nav__inner">\n'
            f'      <a href="{home}" class="nav__logo">'
            f'<img src="{prefix}logo.png" alt="{html.escape(SITE["site_name"])}" /></a>\n'
            '      <div class="nav__links">\n' + "\n".join(links) + "\n"
            '      </div>\n'
            '    </div>\n'
            '  </nav>')

def about_subnav(active, prefix):
    items = []
    for item in SITE["subnav"]:
        cls = ' class="is-active"' if item["key"] == active else ''
        items.append(f'        <a href="{prefix}{item["key"]}/"{cls}>'
                     f'{html.escape(item["label"])}</a>')
    return '      <div class="subnav">\n' + "\n".join(items) + "\n      </div>"

# Twitter のロゴ（鳥）
TWITTER_ICON = ('<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" '
          'aria-hidden="true"><path d="M23.953 4.57a10 10 0 0 1-2.825.775 4.958 4.958 0 0 0 '
          '2.163-2.723 9.99 9.99 0 0 1-3.127 1.195 4.92 4.92 0 0 0-8.384 4.482'
          'C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 0 0-.666 2.475c0 1.71.87 3.213 '
          '2.188 4.096a4.904 4.904 0 0 1-2.228-.616v.06a4.923 4.923 0 0 0 3.946 4.827 '
          '4.996 4.996 0 0 1-2.212.085 4.936 4.936 0 0 0 4.604 3.417 9.867 9.867 0 0 1'
          '-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 0 0 7.557 2.209c9.053 0 '
          '13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0 0 24 4.59z"/></svg>')

# 個人サイト用のアイコン（地球儀）
WEBSITE_ICON = ('<svg viewBox="0 0 24 24" width="16" height="16" fill="none" '
                'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
                'aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
                '<path d="M3 12h18"/>'
                '<path d="M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9"/>'
                '<path d="M12 3C9.5 5.7 8.2 8.7 8.2 12s1.3 6.3 3.8 9"/></svg>')

def load_members():
    """content/members/*.md を読む。ファイル名がそのまま個人ページのURLになる。
    group（leadership / staff）で分け、order の小さい順に並べる。"""
    members = []
    for path in sorted((CONTENT_DIR / "members").glob("*.md")):
        meta, body = load_md(path)
        meta = dict(meta or {})
        meta["slug"] = path.stem
        meta["bio_html"] = md_to_html(body)
        members.append(meta)
    members.sort(key=lambda m: (m.get("order", 999), m["slug"]))
    leadership = [m for m in members if m.get("group") == "leadership"]
    staff = [m for m in members if m.get("group") == "staff"]
    return leadership, staff, members

def member_cards(members, prefix="../"):
    cards = []
    for m in members:
        name, role = m["name"], m["role"]
        field, photo = m.get("field", ""), m.get("photo", "")
        twitter, website = m.get("twitter", ""), m.get("website", "")

        media = (f'<img src="{prefix}{html.escape(photo)}" alt="" />'
                 if photo else html.escape(name.strip()[0]))
        field_html = (f'\n            <div class="member-card__field">{html.escape(field)}</div>'
                      if field else "")

        actions = []
        if twitter:
            actions.append(
                f'<a class="member-card__icon" href="https://x.com/{html.escape(twitter)}" '
                f'target="_blank" rel="noopener" '
                f'aria-label="{html.escape(name)}のTwitter">{TWITTER_ICON}</a>')
        if website:
            actions.append(
                f'<a class="member-card__icon" href="{html.escape(website)}" '
                f'target="_blank" rel="noopener" '
                f'aria-label="{html.escape(name)}の個人サイト">{WEBSITE_ICON}</a>')
        # 個人ページは全員分を生成しているので View Bio は常に出す
        actions.append(
            f'<a class="member-card__bio" href="{prefix}members/'
            f'{html.escape(m["slug"])}/">View Bio</a>')
        actions_html = ('\n            <div class="member-card__actions">'
                        + "".join(actions) + '</div>') if actions else ""

        cards.append(f"""        <div class="member-card">
          <div class="member-card__photo" aria-hidden="true">{media}</div>
          <div class="member-card__body">
            <div class="member-card__name">{html.escape(name)}</div>
            <div class="member-card__role">{html.escape(role)}</div>{field_html}{actions_html}
          </div>
        </div>""")
    return "\n".join(cards)

def site_footer():
    links = "\n".join(
        f'        <a href="{html.escape(s["href"])}" target="_blank" rel="noopener">'
        f'{html.escape(s["label"])}</a>'
        for s in SITE["social"])
    return ('  <footer class="site-foot">\n'
            '    <div class="wrap site-foot__inner">\n'
            f'      <span>{html.escape(SITE["copyright"])}</span>\n'
            '      <div class="site-foot__social">\n' + links + '\n'
            '      </div>\n'
            '    </div>\n'
            '  </footer>')

def site_shell(title, active, body_html, prefix, canonical_path, description=""):
    desc = (f'\n  <meta name="description" content="{html.escape(description)}" />'
            if description else "")
    social = social_meta_head(prefix, title, canonical_path, description)
    return f"""<!DOCTYPE html>
{GENERATED_BANNER}
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
        link = f'blog/{p["slug"]}/'
        # トップはサイトルート。thumbnail 未指定なら既定画像にフォールバックする。
        thumb = (f'<a href="{link}" class="home-card__thumb">'
                 f'<img src="{html.escape(thumb_src(p, "blog/", ""))}" alt="" /></a>')
        cards.append(f"""      <article class="home-card">
        {thumb}
        <div class="home-card__body">
          <div class="home-card__meta"><span class="home-card__cat">{html.escape(p["category"])}</span><span>{date_ja(p["date"])}</span></div>
          <a href="{link}"><h3 class="home-card__title">{html.escape(p["title"])}</h3></a>
        </div>
      </article>""")
    return "\n".join(cards)

def section_open(sec):
    """セクションの外枠と見出し（eyebrow / heading）。"""
    cls = "section section--alt" if sec.get("alt") else "section"
    sid = f' id="{html.escape(sec["id"])}"' if sec.get("id") else ""
    head = ""
    if sec.get("eyebrow") or sec.get("heading"):
        head = ('      <div class="section__head">\n'
                + (f'        <div class="section__eyebrow">{html.escape(sec["eyebrow"])}</div>\n'
                   if sec.get("eyebrow") else "")
                + (f'        <h2 class="section__title">{html.escape(sec["heading"])}</h2>\n'
                   if sec.get("heading") else "")
                + '      </div>\n')
    return f'  <section class="{cls}"{sid}>\n    <div class="wrap">\n' + head

def render_index_page(page, posts):
    hero, latest = page["hero"], page["latest"]
    cards = home_cards(posts, latest.get("count", 3))
    return f"""  <header class="hero">
    <div class="wrap">
      <h1>{clause_spans(hero["heading"])}</h1>
      <p>{clause_spans(hero["body"])}</p>
      <a href="{html.escape(hero["cta_href"])}" class="hero__cta">{html.escape(hero["cta_label"])}</a>
    </div>
  </header>

  <section class="section" id="blog">
    <div class="wrap">
      <div class="section__head">
        <div class="section__eyebrow">{html.escape(latest["eyebrow"])}</div>
        <h2 class="section__title">{html.escape(latest["heading"])}</h2>
      </div>
      <div class="home-cards">
{cards}
      </div>
      <a href="blog/" class="more-link">{html.escape(latest["more_label"])}</a>
    </div>
  </section>"""

def render_about_page(page, prefix):
    out = []
    for i, sec in enumerate(page["sections"]):
        s = section_open(sec)
        # サブナビは最初のセクションの見出し直後に置く
        if i == 0:
            s += about_subnav("about", prefix) + "\n"
        if sec.get("lead"):
            s += f'      <p class="about__lead">{inline_md(sec["lead"])}</p>\n'
        if sec.get("cards"):
            s += '      <div class="about__grid">\n'
            for c in sec["cards"]:
                s += ('        <div class="about__item">\n'
                      f'          <h3>{html.escape(c["heading"])}</h3>\n'
                      f'          <p>{inline_md(c["body"])}</p>\n'
                      '        </div>\n')
            s += '      </div>\n'
        if sec.get("body"):
            s += f'      <div class="message__body">\n{md_to_html(sec["body"])}\n      </div>\n'
        if sec.get("sign"):
            s += ('      <div class="message__sign">\n'
                  f'        <div class="role">{html.escape(sec["sign"]["role"])}</div>\n'
                  f'        <div class="name">{html.escape(sec["sign"]["name"])}</div>\n'
                  '      </div>\n')
        out.append(s + '    </div>\n  </section>')
    return "\n\n".join(out)

def render_projects_page(page):
    items = []
    for p in page["projects"]:
        s = ('        <article class="project">\n'
             f'          <div class="project__eyebrow">{html.escape(p["eyebrow"])}</div>\n'
             f'          <h3 class="project__name">{html.escape(p["name"])}</h3>\n'
             f'          <p class="project__desc">{inline_md(p["body"])}</p>\n')
        if p.get("bullets"):
            s += '          <ul>\n'
            s += "".join(f'            <li>{inline_md(b)}</li>\n' for b in p["bullets"])
            s += '          </ul>\n'
        if p.get("note"):
            s += f'          <p class="project__note">{inline_md(p["note"])}</p>\n'
        if p.get("link_label"):
            ext = ' target="_blank" rel="noopener"' if p.get("link_external") else ""
            s += (f'          <a href="{html.escape(p["link_href"])}"{ext} '
                  f'class="project__link">{html.escape(p["link_label"])}</a>\n')
        items.append(s + '        </article>')
    return (section_open({"id": "projects", "eyebrow": page["eyebrow"],
                          "heading": page["heading"]})
            + f'      <p class="about__lead">{inline_md(page["lead"])}</p>\n\n'
            + '      <div class="projects">\n\n'
            + "\n\n".join(items)
            + '\n\n      </div>\n    </div>\n  </section>')

def render_simple_page(page, body_md, active, prefix):
    s = section_open({"id": active, "eyebrow": page.get("eyebrow"),
                      "heading": page.get("heading")})
    s += about_subnav(active, prefix) + "\n"
    body = md_to_html(body_md)
    if body:
        s += f'      <div class="message__body">\n{body}\n      </div>\n'
    return s + '    </div>\n  </section>'

def render_members_page(page, leadership, staff, prefix):
    s = section_open({"id": "members", "eyebrow": page.get("eyebrow", "Members"),
                      "heading": page.get("heading", "メンバー")})
    s += about_subnav("members", prefix) + "\n\n"
    for label, group in (("Leadership", leadership), ("Staff", staff)):
        if not group:
            continue
        s += (f'      <h3 class="members__group">{html.escape(label)}</h3>\n'
              '      <div class="members-grid">\n'
              + member_cards(group, prefix) + '\n      </div>\n\n')
    return s + '    </div>\n  </section>'

def render_toplevel(posts, leadership, staff):
    prefix = "../"
    index_page, _ = load_md(CONTENT_DIR / "index.md")
    about_page, _ = load_md(CONTENT_DIR / "about.md")
    projects_page, _ = load_md(CONTENT_DIR / "projects.md")
    contact_page, contact_body = load_md(CONTENT_DIR / "contact.md")
    members_page, _ = load_md(CONTENT_DIR / "members.md") \
        if (CONTENT_DIR / "members.md").exists() else ({}, "")

    site_name = SITE["site_name"]
    pages = [
        ("index.html", "index", "", "",
         index_page.get("title", site_name), DEFAULT_DESCRIPTION,
         render_index_page(index_page, posts)),
        ("about/index.html", "about", prefix, "about/",
         f'{about_page["title"]} | {site_name}', "",
         render_about_page(about_page, prefix)),
        ("members/index.html", "members", prefix, "members/",
         f'{members_page.get("title", "メンバー")} | {site_name}', "",
         render_members_page(members_page, leadership, staff, prefix)),
        ("projects/index.html", "projects", prefix, "projects/",
         f'{projects_page["title"]} | {site_name}', "",
         render_projects_page(projects_page)),
        ("contact/index.html", "contact", prefix, "contact/",
         f'{contact_page["title"]} | {site_name}', "",
         render_simple_page(contact_page, contact_body, "contact", prefix)),
    ]
    for out, active, pfx, canonical, title, desc, body in pages:
        out_path = SITE_ROOT / out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            site_shell(title, active, body, pfx, canonical, desc), encoding="utf-8")
    print("  トップレベル生成: / /about/ /members/ /projects/ /contact/")

def render_member_pages(members):
    """メンバー個人ページ（/members/<slug>/）。本文は content/members/*.md の
    frontmatter より下に書いた Markdown がそのまま入る。"""
    prefix = "../../"     # /members/<slug>/ からサイトルートまで
    for m in members:
        photo = m.get("photo", "")
        media = (f'<img src="{prefix}{html.escape(photo)}" alt="" />'
                 if photo else html.escape(m["name"].strip()[0]))
        field = (f'\n          <div class="member-detail__field">{html.escape(m["field"])}</div>'
                 if m.get("field") else "")
        # Twitter と個人サイトのリンク。設定した人にだけ出る。
        links = []
        if m.get("twitter"):
            links.append(
                f'<a class="member-detail__link" '
                f'href="https://x.com/{html.escape(m["twitter"])}" '
                f'target="_blank" rel="noopener">{TWITTER_ICON}'
                f'<span>@{html.escape(m["twitter"])}</span></a>')
        if m.get("website"):
            label = re.sub(r'^https?://', '', m["website"]).rstrip('/')
            links.append(
                f'<a class="member-detail__link" '
                f'href="{html.escape(m["website"])}" '
                f'target="_blank" rel="noopener">{WEBSITE_ICON}'
                f'<span>{html.escape(label)}</span></a>')
        twitter = ('\n          <div class="member-detail__links">'
                   + "".join(links) + '</div>') if links else ""
        body = f"""  <section class="section" id="member-detail">
    <div class="wrap">
      <a href="{prefix}members/" class="member-detail__back">← メンバー一覧へ戻る</a>
      <div class="member-detail__head">
        <div class="member-detail__photo" aria-hidden="true">{media}</div>
        <div>
          <h1 class="member-detail__name">{html.escape(m["name"])}</h1>
          <div class="member-detail__role">{html.escape(m["role"])}</div>{field}{twitter}
        </div>
      </div>
      <div class="member-detail__bio">
{m["bio_html"]}
      </div>
    </div>
  </section>"""
        out_path = SITE_ROOT / "members" / m["slug"] / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            site_shell(f'{m["name"]} | {SITE["site_name"]}', "members", body,
                       prefix, f'members/{m["slug"]}/'),
            encoding="utf-8")
    # content/members/ から消した（またはファイル名を変えた）人のページが
    # 古い内容のまま残らないよう、対応する .md が無いものを片付ける。
    current = {m["slug"] for m in members}
    for d in sorted((SITE_ROOT / "members").iterdir()):
        if d.is_dir() and d.name not in current:
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink()
            d.rmdir()
            print(f"  不要になったメンバーページを削除: members/{d.name}/")
    print(f"  メンバー個人ページ生成: {len(members)}名分")

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
    render_legacy_redirects(posts)
    render_index(posts)
    leadership, staff, all_members = load_members()
    render_toplevel(posts, leadership, staff)
    render_member_pages(all_members)
    print(f"\n✅ 完了: {len(posts)}件の記事 + ブログ一覧 + トップレベル4ページを生成しました。")

if __name__ == "__main__":
    main()
