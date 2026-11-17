#!/usr/bin/env python3
"""食ポチ5サイトの商品データを読み、正規化した1本の JSON（data/products.json）を生成する。

使い方:
  .venv/bin/python scripts/aggregate.py [--repos <リポジトリ群の親ディレクトリ>]
  （既定: 環境変数 POCHI_REPOS があればそれ、なければこのプロジェクトの親ディレクトリ。
   ローカルでは ~/Desktop/Claude 直下に5リポジトリが並んでいる）

データ源（読み取りのみ。書き換えはしない）:
  conbini-pochi / fastfood-pochi / cupmen-pochi / cafe-pochi / sushi-pochi の
  data/products/<chain>/<product_id>.json、config.json、data/netaful_reviews.json

正規化の方針:
- launch_date（発売日）がある商品だけを対象にする。発売日がない商品は載せない。
- 価格は税込を優先する。税抜しかない商品は price_tax="excl" として、表示側で
  「（税抜）」と分かるようにする（推測で税込換算はしない）。
  - conbini: price_incl_tax → 税込（float のことがある。例 213.84。整数値なら int にし、
    それ以外は float のまま持つ）。なければ price_excl_tax → 税抜
  - cupmen:  price_excl_tax のみ → 税抜
  - fastfood / cafe / sushi: price は税込（各商品の price_note が税込表記であることを確認済み）。
    cafe は price_max がある場合は価格帯として持つ。
- チェーン表示名は各サイトの config.json の chains[].name を使う。
- 商品ページURLは https://<サイト>.netaful.jp/items/{chain}-{product_id}.html で組み立てる
  （site_url は config.json の site_url を使う）。
- netaful_reviews.json の matches（"chain-product_id" -> 記事ID配列）と articles から、
  レビュー記事の URL とタイトルを引いて付ける。複数ある場合は最新の記事を1本だけ付ける。
- region_text（販売地域。主にコンビニ）が空でない文字列なら商品に持たせる。
  同名・同発売日で地域違いの商品を、表示側で見分けるために使う。
- 出力の sources に、各リポジトリの HEAD のコミットハッシュと日付を記録する（git が失敗したら null）。
"""
import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 既定の取り込み元: 環境変数 POCHI_REPOS、なければこのプロジェクトの親ディレクトリ
DEFAULT_REPOS = os.environ.get("POCHI_REPOS") or os.path.dirname(BASE_DIR)

# サイト定義: リポジトリ名 -> (サイトslug, 表示名)
SITES = (
    ("conbini-pochi", "conbini", "コンビニポチ"),
    ("fastfood-pochi", "fastfood", "ファストフードポチ"),
    ("cupmen-pochi", "cupmen", "カップ麺ポチ"),
    ("cafe-pochi", "cafe", "カフェポチ"),
    ("sushi-pochi", "sushi", "回転寿司ポチ"),
)


def _is_date(value):
    try:
        return isinstance(value, str) and datetime.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _num(value):
    """価格として使える数値（int / float。bool は不可）なら、整数値は int にして返す。それ以外は None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        if value.is_integer():
            return int(value)
    return value


def _price_of(site_slug, raw):
    """サイト別の価格フィールドを (price, price_max, price_tax) に読み替える。"""
    if site_slug == "conbini":
        incl = _num(raw.get("price_incl_tax"))
        if incl is not None:
            return incl, None, "incl"
        if isinstance(raw.get("price_excl_tax"), int):
            return raw["price_excl_tax"], None, "excl"
        return None, None, None
    if site_slug == "cupmen":
        if isinstance(raw.get("price_excl_tax"), int):
            return raw["price_excl_tax"], None, "excl"
        return None, None, None
    # fastfood / cafe / sushi: price は税込
    price = raw.get("price") if isinstance(raw.get("price"), int) else None
    price_max = raw.get("price_max") if isinstance(raw.get("price_max"), int) else None
    if price is not None and price_max is not None and price_max <= price:
        price_max = None
    return price, price_max, ("incl" if price is not None else None)


def _review_map(repo_dir, chain_slugs):
    """netaful_reviews.json から "chain-product_id" -> (記事URL, 記事タイトル) を作る。

    product_id 自体に "-" を含む商品（回転寿司の hz-... 等）があるため、チェーンは
    キーの末尾からではなく、既知のチェーン slug の前方一致で切り分ける。"""
    path = os.path.join(repo_dir, "data", "netaful_reviews.json")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    articles = {}
    for chain, items in (data.get("articles") or {}).items():
        for art in items or []:
            if isinstance(art, dict) and art.get("id") is not None:
                articles[(chain, art["id"])] = art
    for key, ids in (data.get("matches") or {}).items():
        chain = next((c for c in chain_slugs if key.startswith(c + "-")), "")
        cands = [articles[(chain, i)] for i in (ids or []) if (chain, i) in articles]
        if not cands:
            continue
        latest = max(cands, key=lambda a: a.get("date") or "")
        if latest.get("link"):
            out[key] = (latest["link"], latest.get("title") or "")
    return out


def _git_head(repo_dir):
    """リポジトリの HEAD の {"commit": 短縮ハッシュ, "date": コミット日時} を返す。失敗したら None。"""
    try:
        out = subprocess.run(["git", "-C", repo_dir, "log", "-1", "--format=%h %cI"],
                             capture_output=True, text=True, timeout=30, check=True).stdout.strip()
        commit, date = out.split(" ", 1)
        return {"commit": commit, "date": date}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def aggregate(repos_dir):
    products = []
    stats = {}
    for repo_name, site_slug, site_name in SITES:
        repo_dir = os.path.join(repos_dir, repo_name)
        with open(os.path.join(repo_dir, "config.json"), encoding="utf-8") as f:
            config = json.load(f)
        site_url = (config.get("site_url") or "").rstrip("/")
        chain_names = {c["slug"]: c["name"] for c in config.get("chains") or []}
        reviews = _review_map(repo_dir, list(chain_names))
        total = 0
        dated = 0
        files = sorted(glob.glob(os.path.join(repo_dir, "data", "products", "*", "*.json")))
        for path in files:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            total += 1
            launch = raw.get("launch_date")
            if not _is_date(launch):
                continue
            chain = raw.get("chain")
            product_id = raw.get("product_id")
            name = raw.get("name")
            if not chain or not product_id or not name:
                print("[aggregate] 必須項目が欠けた商品を除外: %s" % path, file=sys.stderr)
                continue
            dated += 1
            price, price_max, price_tax = _price_of(site_slug, raw)
            review = reviews.get("%s-%s" % (chain, product_id))
            products.append({
                "site": site_slug,
                "site_name": site_name,
                "site_url": site_url,
                "chain": chain,
                "chain_name": chain_names.get(chain) or chain,
                "product_id": str(product_id),
                "name": name,
                "category": raw.get("category") if isinstance(raw.get("category"), str) and raw.get("category") else None,
                "price": price,
                "price_max": price_max,
                "price_tax": price_tax,
                "price_note": raw.get("price_note") if isinstance(raw.get("price_note"), str) and raw.get("price_note") else None,
                "description": raw.get("description") if isinstance(raw.get("description"), str) and raw.get("description") else None,
                "region_text": raw.get("region_text") if isinstance(raw.get("region_text"), str) and raw.get("region_text").strip() else None,
                "launch_date": launch,
                "url": "%s/items/%s-%s.html" % (site_url, chain, product_id),
                "review_url": review[0] if review else None,
                "review_title": review[1] if review else None,
            })
        stats[site_slug] = {"site_name": site_name, "total": total, "dated": dated}
    products.sort(key=lambda p: (p["launch_date"], p["site"], p["chain"], p["name"]))
    return products, stats


def main():
    parser = argparse.ArgumentParser(description="食ポチ5サイトの商品データを data/products.json に集約する")
    parser.add_argument("--repos", default=DEFAULT_REPOS,
                        help="5リポジトリが並ぶ親ディレクトリ"
                             "（既定: 環境変数 POCHI_REPOS、なければこのプロジェクトの親ディレクトリ）")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "data", "products.json"),
                        help="出力先（既定: data/products.json）")
    args = parser.parse_args()

    products, stats = aggregate(args.repos)
    dates = [p["launch_date"] for p in products]
    doc = {
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"),
        "note": ("データ源は %s 配下の5リポジトリ（読み取りのみ）。"
                 "取り込み時点のコミットは sources を参照。" % args.repos),
        "sources": {name: _git_head(os.path.join(args.repos, name)) for name, _slug, _label in SITES},
        "stats": stats,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "products": products,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("[aggregate] 書き出し完了: %s" % args.out)
    for slug, s in stats.items():
        print("  %s（%s）: 全%d件中、発売日あり %d件" % (slug, s["site_name"], s["total"], s["dated"]))
    print("  合計: 発売日あり %d件（%s 〜 %s）" % (len(products), doc["date_min"], doc["date_max"]))
    for slug, s_ in stats.items():
        ps = [p for p in products if p["site"] == slug]
        print("  税込/税抜 %s: 税込 %d件・税抜 %d件・価格なし %d件" % (
            slug, sum(1 for p in ps if p["price_tax"] == "incl"),
            sum(1 for p in ps if p["price_tax"] == "excl"), sum(1 for p in ps if p["price_tax"] is None)))
    print("  レビュー紐づけあり: %d件" % sum(1 for p in products if p["review_url"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
