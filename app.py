#!/usr/bin/env python3
"""新発売ポチ: 食ポチ6サイト（コンビニ・ファストフード・カップ麺・カフェ・回転寿司・ファミレス）が
記録している新商品を、発売日で横断集約するサイト。

起動（ローカル）:
  .venv/bin/python app.py
  -> http://localhost:8080

守っている方針（詳細は README.md）
- 掲載するのは発売日（launch_date）が記録されている商品だけ。発売日がない商品は載せない。
- 商品データは scripts/aggregate.py が6サイトの data/products から正規化した
  data/products.json を読むだけ（このアプリは元データには触れない）。
- 価格は税込を優先し、税抜しかない商品は「（税抜）」と明示する。推測で換算しない。
- 商品画像は元データに無いため使わない。テキスト中心のカードにする。
- 「今日」の基準日は通常はビルド日（実行日）。環境変数 REFERENCE_DATE（YYYY-MM-DD）で
  上書きでき、試作ではデータ内の最新日付を基準にする使い方をする
  （scripts/build_static.py --reference max）。
"""
import datetime
import html
import json
import os
import re

from flask import Flask, Response, abort

from icon_guess import guess_icon

# ---------- サイト名・基本設定 ----------
SITE_NAME = "新発売ポチ"
TAGLINE = "今日発売の新商品を、まとめてチェック"
DESCRIPTION = ("コンビニ・ファストフード・カップ麺・カフェ・回転寿司・ファミレスの新商品を、発売日ごとに"
               "横断してまとめています。今日発売・今週発売の新商品が1ページで分かります。")
SITE_URL = os.environ.get("SITE_URL", "https://shinhatsubai.netaful.jp").rstrip("/")
# GA4 の測定ID（G-XXXXXXXXXX）。空ならタグを出さない。本番化のときに環境変数で渡す
GA4_ID = os.environ.get("GA4_ID", "")

# 共通ページテンプレート・文言を最後に変えた日（sitemap.xml の lastmod の下限）
PAGES_UPDATED = "2026-11-23"

# フッターの関連サイト（ポチシリーズ。新発売ポチ自身は載せない）
SERIES_SITES = (
    ("電書ポチ", "Kindle本セール", "https://book.netaful.jp/"),
    ("家電ポチ", "ガジェット・家電セール", "https://kaden.netaful.jp/"),
    ("林檎ポチ", "Apple整備済製品", "https://apple.netaful.jp/"),
    ("漫画ポチ", "Webマンガ横断検索", "https://manga.netaful.jp/"),
    ("マンガ新刊ポチ", "コミック新刊の発売日をまとめて", "https://shinkan.netaful.jp/"),
    ("コンビニポチ", "コンビニ新商品アーカイブ", "https://conbini.netaful.jp/"),
    ("ファストフードポチ", "ファストフード限定メニュー", "https://fastfood.netaful.jp/"),
    ("カフェポチ", "カフェ季節限定メニュー", "https://cafe.netaful.jp/"),
    ("ファミレスポチ", "ファミレスの期間限定フェア", "https://famires.netaful.jp/"),
    ("回転寿司ポチ", "回転寿司の期間限定ネタ", "https://sushi.netaful.jp/"),
    ("カップ麺ポチ", "カップ麺の新商品", "https://cupmen.netaful.jp/"),
    ("ホテルポチ", "空室ホテルを安い順に検索", "https://hotel.netaful.jp/"),
    ("温泉宿ポチ", "温泉地の空室を、すぐ探す", "https://onsen.netaful.jp/"),
    ("離島宿ポチ", "島の空室を、すぐ探す", "https://ritou.netaful.jp/"),
    ("道の駅ポチ", "道の駅の駐車場・設備", "https://michinoeki.netaful.jp/"),
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "products.json")

CAUTION = ("価格・発売日・販売地域などは変更される場合があります。"
           "購入前に、各チェーンの公式ページでも最新の情報をご確認ください。")

# ジャンル（=元のポチサイト）: slug -> 表示名。並びはこの順
GENRES = (
    ("conbini", "コンビニ"),
    ("fastfood", "ファストフード"),
    ("cupmen", "カップ麺"),
    ("cafe", "カフェ"),
    ("sushi", "回転寿司"),
    ("famires", "ファミレス"),
)
GENRE_NAMES = dict(GENRES)

WEEKDAYS = "月火水木金土日"


def _is_date(value):
    try:
        return isinstance(value, str) and datetime.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


# ビルドは GitHub Actions（UTC）でも回るため、「今日」は実行マシンのタイムゾーンでなく日本時間で決める
JST = datetime.timezone(datetime.timedelta(hours=9))


def reference_date():
    """「今日」の基準日。REFERENCE_DATE があればそれ、なければ日本時間（+09:00）の実行日。"""
    env = os.environ.get("REFERENCE_DATE")
    if _is_date(env or ""):
        return datetime.date.fromisoformat(env)
    return datetime.datetime.now(JST).date()


class ProductStore:
    """data/products.json（aggregate.py の出力）を読み、検証して索引を作る。

    検証に落ちた商品はその商品だけを除外して理由を標準出力に出す。
    必須: name / launch_date（実在する日付）/ url（http(s)）。
    """

    def __init__(self, path=DATA_PATH):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.generated_at = raw.get("generated_at")
        self.products = []
        for item in raw.get("products") or []:
            p, reason = self._validate(item)
            if p is None:
                print("[shinhatsubai] 商品を除外しました: %s (%s)"
                      % (item.get("name") or "?", reason))
                continue
            self.products.append(p)
        self.by_date = {}
        for p in self.products:
            self.by_date.setdefault(p["launch_date"], []).append(p)
        self.dates = sorted(self.by_date, reverse=True)
        # チェーン索引: "<site>-<chain>" -> {"site", "chain", "chain_name", "site_name"}
        self.chains = {}
        for p in self.products:
            key = "%s-%s" % (p["site"], p["chain"])
            self.chains.setdefault(key, {"site": p["site"], "chain": p["chain"],
                                         "chain_name": p["chain_name"], "site_name": p["site_name"]})

    @staticmethod
    def _validate(item):
        if not isinstance(item, dict):
            return None, "オブジェクトでない"
        if not isinstance(item.get("name"), str) or not item["name"]:
            return None, "name がない"
        if not _is_date(item.get("launch_date")):
            return None, "launch_date が実在する日付でない"
        url = item.get("url")
        if not isinstance(url, str) or not (url.startswith("https://") or url.startswith("http://")):
            return None, "url がない/URLでない"
        if item.get("site") not in GENRE_NAMES:
            return None, "site が未知"
        p = dict(item)
        for k in ("category", "price_note", "description", "review_url", "review_title"):
            if not isinstance(p.get(k), str) or not p.get(k):
                p[k] = None
        for k in ("price", "price_max"):
            v = p.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
                p[k] = None
            elif isinstance(v, float) and v.is_integer():
                p[k] = int(v)
        if not isinstance(p.get("region_text"), str) or not p["region_text"].strip():
            p["region_text"] = None
        if p.get("price_tax") not in ("incl", "excl"):
            p["price_tax"] = None
        return p, None

    def on(self, date_str):
        return self.by_date.get(date_str, [])

    def genre_products(self, site):
        return [p for p in self.products if p["site"] == site]

    def chain_products(self, key):
        info = self.chains.get(key)
        if info is None:
            return None, []
        return info, [p for p in self.products
                      if p["site"] == info["site"] and p["chain"] == info["chain"]]


STORE = ProductStore()

app = Flask(__name__, static_folder="static", static_url_path="/static")

# ---------- テンプレート ----------
# GA4 は環境変数 GA4_ID が空でないときだけ {{GA4}} の位置にタグを出す。
BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{{GA4}}<title>{{PAGE_TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<link rel="canonical" href="{{CANONICAL}}">
<link rel="icon" type="image/png" sizes="96x96" href="/static/assets/favicon.png">
<link rel="apple-touch-icon" href="/static/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:title" content="{{PAGE_TITLE}}">
<meta property="og:description" content="{{DESCRIPTION}}">
<meta property="og:url" content="{{CANONICAL}}">
<meta property="og:site_name" content="{{SITE_NAME}}">
<meta property="og:locale" content="ja_JP">
<meta property="og:image" content="{{OGP_IMAGE}}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/static/style.css">
{{JSONLD}}</head>
<body>
<header class="site-header">
{{SITE_HEAD}}
<p class="tagline">{{TAGLINE}}</p>
</header>
<main>
{{CONTENT}}</main>
<footer class="site-footer">
<p>{{SITE_NAME}}は、コンビニポチ・ファストフードポチ・カップ麺ポチ・カフェポチ・回転寿司ポチ・ファミレスポチが記録している新商品の情報を、発売日で横断してまとめています。商品の詳細（栄養成分など）は各商品のリンク先（元のポチ）でご確認ください。</p>
<p>当サイトは各チェーン・各社とは関係のない非公式サイトです。価格・発売日は、元のポチが公式の案内を確認した時点のものです。最新の情報は各チェーンの公式サイトでご確認ください。</p>
<p>Googleアナリティクス（Cookie）を利用しています。</p>
<p><a href="/">トップ</a></p>
{{SERIES_NAV}}</footer>
</body>
</html>
"""


def _series_nav():
    links = "\n".join('<a href="%s">%s<span class="lbl"> %s</span></a>'
                      % (html.escape(u, quote=True), html.escape(n), html.escape(d)) for n, d, u in SERIES_SITES)
    return ('<nav class="sites"><span class="lbl">関連サイト</span>\n%s\n</nav>\n' % links
            + '<nav class="sites"><span class="lbl">ポチシリーズ一覧：</span>\n'
            + '<a href="https://pochi.netaful.jp/">ポチフル</a>\n</nav>\n')


def _site_head(is_top):
    name = ('<a href="/"><img src="/static/assets/logo.png" alt="" width="44" height="44">%s</a>'
            % html.escape(SITE_NAME))
    return '<h1 class="site-title">%s</h1>' % name if is_top else '<div class="site-title">%s</div>' % name


def _ga4_snippet():
    """GA4 の標準 gtag.js タグ。GA4_ID が空なら空文字。"""
    if not GA4_ID:
        return ""
    gid = html.escape(GA4_ID, quote=True)
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>\n'
            '<script>\nwindow.dataLayer = window.dataLayer || [];\n'
            'function gtag(){dataLayer.push(arguments);}\n'
            "gtag('js', new Date());\n"
            "gtag('config', '%s');\n</script>\n" % (gid, gid))


def _render(title, description, canonical, content, jsonld="", is_top=False):
    vals = {"PAGE_TITLE": html.escape(title, quote=True), "DESCRIPTION": html.escape(description, quote=True),
            "CANONICAL": html.escape(canonical, quote=True), "SITE_NAME": html.escape(SITE_NAME),
            "TAGLINE": html.escape(TAGLINE), "CONTENT": content, "JSONLD": jsonld,
            "OGP_IMAGE": html.escape(SITE_URL + "/static/assets/ogp.jpg", quote=True), "SITE_HEAD": _site_head(is_top),
            "SERIES_NAV": _series_nav(), "GA4": _ga4_snippet()}
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), BASE_TEMPLATE)


def _jsonld(obj):
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return '<script type="application/ld+json">%s</script>\n' % body


def _crumbs(*items):
    rows = [(SITE_NAME, SITE_URL + "/")] + list(items)
    return _jsonld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(rows)]})


def _crumbs_nav(*items):
    e = html.escape
    rows = [(SITE_NAME, "/")] + list(items)
    parts = ['<a href="%s">%s</a>' % (e(u, True), e(n)) for n, u in rows[:-1]]
    parts.append('<span aria-current="page">%s</span>' % e(rows[-1][0]))
    return '<nav class="crumbs" aria-label="パンくずリスト">' + " &gt; ".join(parts) + "</nav>\n"


def _fmt_date(date_str, with_year=True):
    """'2026-11-18' -> '2026年11月18日（水）'"""
    d = datetime.date.fromisoformat(date_str)
    s = "%d月%d日（%s）" % (d.month, d.day, WEEKDAYS[d.weekday()])
    return "%d年%s" % (d.year, s) if with_year else s


def _fmt_price(v):
    """1,234 形式。小数（コンビニの税込 494.64 など）は切り捨てて整数にする（オーナー指示 2026-11-21）。"""
    return format(int(v), ",")


def _price_html(p):
    """価格。税込/税抜を明示し、価格帯（price_max）がある場合は 〜 でつなぐ。"""
    if p["price"] is None:
        return ""
    e = html.escape
    if p["price_max"]:
        text = "%s〜%s円" % (_fmt_price(p["price"]), _fmt_price(p["price_max"]))
    else:
        text = "%s円" % _fmt_price(p["price"])
    tax = {"incl": "（税込）", "excl": "（税抜）"}.get(p["price_tax"] or "", "")
    return ('<p class="ms-parking"><span class="ms-parking-item">'
            '<strong class="ms-parking-num">%s</strong>'
            '<span class="ms-parking-label">%s</span></span></p>' % (e(text), e(tax)))


def _excerpt(text, limit=80):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + "…" if len(text) > limit else text


def _region_label(text):
    """販売地域の短いラベル。12文字を超えたら先頭12文字＋…。"""
    text = (text or "").strip()
    return text[:12] + "…" if len(text) > 12 else text


# カテゴリ名 -> アイコン（static/icons/cat/<slug>.svg）。サイトごとに同じ語の意味が違うため (site, category) で引く。
# 未登録・カテゴリなしはアイコンを出さない（「その他」にはフォールバックしない）
def _m(slug, *cats):
    return {c: slug for c in cats}


CATEGORY_ICONS = {
    "conbini": {
        **_m("onigiri", "おにぎり", "おむすび"), **_m("bento", "お弁当"), **_m("sushi", "お寿司"),
        **_m("sandwich", "サンド", "サンドイッチ・ロールパン・バーガー"), **_m("bread", "パン"),
        **_m("noodles", "そば・うどん・中華めん", "麺"), **_m("pasta", "パスタ"),
        **_m("sozai", "チルド惣菜", "ホットスナック・惣菜"), **_m("salad", "サラダ"),
        **_m("soup", "スープ・グラタン・お好み焼き"), **_m("chukaman", "中華まん"),
        **_m("sweets", "デザート", "スイーツ", "和菓子"), **_m("ice", "アイス", "アイスクリーム"),
        **_m("snack", "お菓子"), **_m("drink", "飲料", "コーヒー・フラッペ"), **_m("alcohol", "お酒"),
    },
    "fastfood": {
        **_m("burger", "バーガー", "ハンバーガー"), **_m("sozai", "サイド", "おかず", "惣菜"),
        **_m("sweets", "デザート・シェイク", "デザート", "スイーツ＆ドリンク"),
        **_m("drink", "ドリンク", "ドリンク／スープ"), **_m("curry", "カレー"),
        **_m("donburi", "丼", "牛丼", "こだわり丼", "吉野家の丼", "定食", "盛合せ",
             "ヘビー級", "ライト級", "豚焼肉"),
    },
    "cafe": {
        **_m("drink", "ビバレッジ", "ドリンク"), **_m("bread", "フード"),
        **_m("sweets", "デザート", "スナック"),
    },
    "sushi": {**_m("sushi", "にぎり", "にぎり一貫", "ぐんかん・細巻"), **_m("sweets", "デザート")},
}


# 推定したアイコンの代替テキスト（推定はアイコンにだけ使い、カテゴリー名としては出さない）
ICON_LABELS = {
    "onigiri": "おにぎり", "bento": "弁当・ごはん", "donburi": "丼・定食", "curry": "カレー", "sushi": "寿司",
    "sandwich": "サンドイッチ", "burger": "ハンバーガー", "bread": "パン", "noodles": "麺", "pasta": "パスタ",
    "cupnoodle": "カップ麺", "sozai": "惣菜・揚げ物", "salad": "サラダ", "soup": "スープ・グラタン",
    "chukaman": "中華まん", "sweets": "スイーツ", "ice": "アイス", "snack": "お菓子", "drink": "ドリンク",
    "alcohol": "お酒", "other": "その他",
}
# 元データにカテゴリーがないとき、商品名から推定してよいサイト（セブン・ローソン・回転寿司など）
GUESS_SITES = ("conbini", "sushi", "famires")


def _category_icon(p):
    """商品のカテゴリアイコン (slug, ラベル) を返す。なければ None。カップ麺サイトは全商品が対象。

    カテゴリーがあればそれで引く。カテゴリーがない商品だけ、商品名から推定する（icon_guess.py）。
    """
    if p["site"] == "cupmen":
        return "cupnoodle", "カップ麺"
    cat = p.get("category")
    if cat:
        slug = CATEGORY_ICONS.get(p["site"], {}).get(cat)
        return (slug, cat) if slug else None
    if p["site"] in GUESS_SITES:
        slug = guess_icon(p.get("name"), p["site"])
        if p["site"] == "famires" and slug == "ice":
            slug = "sweets"  # ファミレスの「アイス添え」等はデザートとして扱う（アイス単品の商品はない）
        if slug:
            return slug, ICON_LABELS[slug]
    return None


def _product_card(p, show_date=False, show_region=False):
    """商品カード。左に名前と説明、右に価格と詳細ボタンの横並び行レイアウト。"""
    e = html.escape
    badges = '<a class="ms-pref" href="/chain/%s-%s/">%s</a>' % (e(p["site"]), e(p["chain"]), e(p["chain_name"]))
    if p["category"]:
        badges += '<span class="ms-chip">%s</span>' % e(p["category"])
    if show_date:
        badges += '<span class="ms-chip">%s発売</span>' % e(_fmt_date(p["launch_date"], with_year=False))
    out = '<li class="ms-card">'
    icon = _category_icon(p)
    if icon:
        out += ('<img class="sh-cat-icon" src="/static/icons/cat/%s.svg" width="32" height="32" alt="%s" '
                'loading="lazy" decoding="async">' % (icon[0], e(icon[1], True)))
    out += '<div class="ms-card-main">'
    region = ""
    if show_region and p.get("region_text"):
        region = ' <span class="region">%s</span>' % e(_region_label(p["region_text"]))
    out += ('<div class="ms-card-head"><h3><a href="%s" target="_blank" rel="noopener">%s</a>%s</h3>%s</div>'
            % (e(p["url"], True), e(p["name"]), region, badges))
    ex = _excerpt(p["description"])
    if ex:
        out += '<p class="sh-desc">%s</p>' % e(ex)
    out += '</div><div class="ms-card-side">'
    out += _price_html(p)
    links = ('<p class="ms-card-links"><a class="ms-official" href="%s" target="_blank" rel="noopener">詳細</a>'
             % e(p["url"], True))
    if p["review_url"]:
        links += ('<a class="ms-detail" href="%s" target="_blank" rel="noopener">ネタフルでレビュー</a>'
                  % e(p["review_url"], True))
    out += links + "</p>"
    return out + "</div></li>"


def _cards(products, show_date=False):
    # 同じ一覧に、チェーン・名前・発売日が同じ商品が複数あるもの（販売地域違い）には地域ラベルを付ける
    counts = {}
    for p in products:
        k = (p["site"], p["chain"], p["name"], p["launch_date"])
        counts[k] = counts.get(k, 0) + 1
    return '<ul class="ms-cards">%s</ul>\n' % "".join(
        _product_card(p, show_date,
                      counts[(p["site"], p["chain"], p["name"], p["launch_date"])] > 1)
        for p in products)


def _grouped_by_date(products, show_date=False, ascending=False):
    """発売日の新しい順（ascending=True なら近い順）に、日付見出し＋カード群を並べる。"""
    e = html.escape
    by_date = {}
    for p in products:
        by_date.setdefault(p["launch_date"], []).append(p)
    out = ""
    for date_str in sorted(by_date, reverse=not ascending):
        items = by_date[date_str]
        # 日付見出しをタップで折りたためるよう details/summary にする（初期は開く）。
        # 見出しをリンクにすると折りたたみと衝突するので、日付ページへのリンクは一覧の下に置く
        out += ('<section><details class="sh-day" open><summary><h2>%s発売<small class="sh-count">%d件</small></h2></summary>'
                '%s<p class="sh-day-link"><a href="/date/%s/">この日の新商品をすべて見る</a></p></details></section>\n'
                % (e(_fmt_date(date_str)), len(items), _cards(items, show_date), date_str))
    return out


def _genre_links():
    e = html.escape
    items = ""
    for slug, name in GENRES:
        n = len(STORE.genre_products(slug))
        if n == 0:
            continue
        items += '<li><a href="/genre/%s/">%s<small>%d件</small></a></li>' % (slug, e(name), n)
    return '<ul class="ms-nav-chips">%s</ul>' % items if items else ""


def _chain_links(site=None):
    e = html.escape
    items = ""
    for key in sorted(STORE.chains, key=lambda k: (GENRE_NAMES[STORE.chains[k]["site"]], STORE.chains[k]["chain_name"])):
        info = STORE.chains[key]
        if site is not None and info["site"] != site:
            continue
        items += '<li><a href="/chain/%s/">%s</a></li>' % (key, e(info["chain_name"]))
    return '<ul class="ms-nav-chips">%s</ul>' % items if items else ""


# ---------- ページ ----------
@app.route("/")
def index():
    e = html.escape
    ref = reference_date()
    ref_str = ref.isoformat()
    content = ('<section class="hero"><p class="intro">コンビニ・ファストフード・カップ麺・カフェ・'
               '回転寿司・ファミレスの新商品を発売日ごとにまとめています。今日（%s）は%d件の新商品が発売です。'
               # 当日発売の約14%は各社の朝の巡回で初めて登録されるため、更新時刻を明記して期待値を合わせる（2026-11-19 マサト判断）
               '毎日10:00に更新しています。当日発売の商品は10:00の更新で反映されます。%s</p></section>\n'
               % (e(_fmt_date(ref_str)), len(STORE.on(ref_str)), e(CAUTION)))
    def dstr(delta):
        return (ref + datetime.timedelta(days=delta)).isoformat()

    # 今日発売をいちばん上に置く（サイトの主目的。近日発売が多い日に埋もれないように）
    today = STORE.on(ref_str)
    content += '<section><h2>今日発売（%s）<small class="sh-count">%d件</small></h2>' % (e(_fmt_date(ref_str)), len(today))
    content += _cards(today) if today else '<p class="intro">今日発売の新商品は記録されていません。</p>'
    content += '</section>\n'

    # 近日発売（基準日より後、30日以内）
    upcoming = [p for p in STORE.products if ref_str < p["launch_date"] <= dstr(30)]
    if upcoming:
        content += '<section><h2>近日発売</h2></section>\n' + _grouped_by_date(upcoming, ascending=True)  # 近い日から（オーナー意向 2026-11-22）

    this_week = [p for p in STORE.products if dstr(-6) <= p["launch_date"] < ref_str]
    content += '<section><h2>今週発売</h2></section>\n'
    content += _grouped_by_date(this_week) if this_week else '<p class="intro">今週発売の新商品は記録されていません。</p>\n'

    last_week = [p for p in STORE.products if dstr(-13) <= p["launch_date"] < dstr(-6)]
    content += '<section><h2>先週発売（まだ買える新商品）</h2></section>\n'
    content += _grouped_by_date(last_week) if last_week else '<p class="intro">先週発売の新商品は記録されていません。</p>\n'
    content += '<section><h2>ジャンルから探す</h2>%s</section>\n' % _genre_links()

    # サブドメインは WebSite 構造化データが無いと検索結果のサイト名が親（ネタフル）になる（コンビニポチで実例）
    website = _jsonld({"@context": "https://schema.org", "@type": "WebSite",
                       "name": SITE_NAME, "url": SITE_URL + "/"})
    return _render(SITE_NAME, DESCRIPTION, SITE_URL + "/", content, jsonld=website, is_top=True)


@app.route("/date/<date_str>/")
def date_page(date_str):
    if not _is_date(date_str):
        abort(404)
    items = STORE.on(date_str)
    if not items:
        abort(404)
    e = html.escape
    title = "%s発売の新商品" % _fmt_date(date_str)
    desc = "%sに発売された新商品%d件の一覧です。コンビニ・ファストフード・カップ麺・カフェ・回転寿司・ファミレスの新商品をまとめました。" % (
        _fmt_date(date_str), len(items))
    canonical = "%s/date/%s/" % (SITE_URL, date_str)
    content = ('<section class="hero"><h1>%s</h1>\n%s'
               '<p class="intro">%sに発売された新商品は%d件です。%s</p></section>\n'
               % (e(title), _crumbs_nav((title, "/date/%s/" % date_str)), e(_fmt_date(date_str)),
                  len(items), e(CAUTION)))
    content += _cards(items)
    return _render("%s | %s" % (title, SITE_NAME), desc, canonical, content,
                   _crumbs((title, canonical)))


@app.route("/genre/<site>/")
def genre(site):
    if site not in GENRE_NAMES:
        abort(404)
    items = STORE.genre_products(site)
    if not items:
        abort(404)
    e = html.escape
    name = GENRE_NAMES[site]
    title = "%sの新商品" % name
    desc = "%sで記録している、発売日つきの新商品%d件の一覧です。発売日の新しい順にまとめました。" % (name, len(items))
    canonical = "%s/genre/%s/" % (SITE_URL, site)
    content = ('<section class="hero"><h1>%s</h1>\n%s'
               '<p class="intro">%sの新商品%d件を、発売日の新しい順に並べています。%s</p></section>\n'
               % (e(title), _crumbs_nav((title, "/genre/%s/" % site)), e(name), len(items), e(CAUTION)))
    cl = _chain_links(site)
    if cl:
        content += '<section><h2>チェーンから探す</h2>%s</section>\n' % cl
    content += _grouped_by_date(items)
    return _render("%s | %s" % (title, SITE_NAME), desc, canonical, content,
                   _crumbs((title, canonical)))



@app.route("/chain/<key>/")
def chain(key):
    info, items = STORE.chain_products(key)
    if info is None or not items:
        abort(404)
    e = html.escape
    title = "%sの新商品" % info["chain_name"]
    desc = "%sの新商品%d件の一覧です。発売日の新しい順にまとめました。" % (info["chain_name"], len(items))
    canonical = "%s/chain/%s/" % (SITE_URL, key)
    content = ('<section class="hero"><h1>%s</h1>\n%s'
               '<p class="intro">%s（%s）の新商品%d件を、発売日の新しい順に並べています。%s</p></section>\n'
               % (e(title), _crumbs_nav((title, "/chain/%s/" % key)), e(info["chain_name"]),
                  e(info["site_name"]), len(items), e(CAUTION)))
    content += _grouped_by_date(items, show_date=True)
    return _render("%s | %s" % (title, SITE_NAME), desc, canonical, content,
                   _crumbs((title, canonical)))


@app.route("/sitemap.xml")
def sitemap():
    gen_date = (STORE.generated_at or "")[:10]
    lastmod = max(d for d in (PAGES_UPDATED, gen_date) if _is_date(d)) if _is_date(gen_date) else PAGES_UPDATED
    urls = [(SITE_URL + "/", lastmod)]
    for date_str in STORE.dates:
        urls.append(("%s/date/%s/" % (SITE_URL, date_str), max(lastmod, date_str)))
    for slug, _name in GENRES:
        if STORE.genre_products(slug):
            urls.append(("%s/genre/%s/" % (SITE_URL, slug), lastmod))
    for key in STORE.chains:
        urls.append(("%s/chain/%s/" % (SITE_URL, key), lastmod))
    body = "".join("<url><loc>%s</loc><lastmod>%s</lastmod></url>" % (html.escape(u), m) for u, m in urls)
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % body,
                    mimetype="application/xml")


FEED_DAYS = 3
FEED_MAX = 50


def build_feed(ref=None, generated=None):
    """ポチフルのダッシュボード用 /feed.json（仕様 v1）。発売日が今日から3日前〜今日の商品を新しい順に最大50件。"""
    ref = ref or reference_date()
    oldest = (ref - datetime.timedelta(days=FEED_DAYS)).isoformat()
    newest = ref.isoformat()
    picked = [p for p in STORE.products if oldest <= p["launch_date"] <= newest]
    picked.sort(key=lambda p: p["launch_date"], reverse=True)  # sort は安定なのでデータ順は保たれる
    items = []
    for p in picked[:FEED_MAX]:
        ic = _category_icon(p)
        items.append({
            "id": "%s:%s-%s" % (p["site"], p["chain"], p["product_id"]),
            "title": p["name"],
            "url": p["url"],
            "date": p["launch_date"],
            "note": ("\u00a5" + _fmt_price(p["price"]) if p.get("price") is not None else None),
            "brand": p.get("chain_name") or None,  # チェーン名（ポチフルで価格の前に出す）
            "image": None,
            "image_link": None,
            "source": p["site"],
            "source_name": p["site_name"],
            "icon": ("%s/static/icons/cat/%s.svg" % (SITE_URL, ic[0])) if ic else None,
        })
    if generated is None:
        generated = datetime.datetime.now(JST).replace(microsecond=0).isoformat()
    return {"version": 1, "site": "shinhatsubai", "site_name": SITE_NAME, "site_url": SITE_URL + "/",
            "generated": generated, "items": items}


@app.route("/feed.json")
def feed():
    return Response(json.dumps(build_feed(), ensure_ascii=False, indent=1), mimetype="application/json")


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE_URL, mimetype="text/plain")


@app.errorhandler(404)
def not_found(_err):
    content = ('<section class="hero"><h1>ページが見つかりません</h1>'
               '<p class="intro">お探しのページは存在しないか、その日付・条件の新商品はまだ記録されていません。</p></section>\n')
    return _render("ページが見つかりません | %s" % SITE_NAME, DESCRIPTION, SITE_URL + "/", content), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))
