#!/usr/bin/env python3
"""GitHub Pages 公開用の静的書き出し。

Flask の test_client でサーバーを起動せずに全ルートをレンダリングし、
docs/ に書き出す。docs/ をコミットすると GitHub Pages から公開される想定。

使い方:
  .venv/bin/python scripts/build_static.py [--out <出力先>] [--reference <基準日>]
    --out        既定: リポジトリ直下の docs/
    --reference  「今日」の基準日。既定は build（ビルド日）。
                 max とすると data/products.json 内の最新の発売日を基準にする（試作用）。
                 YYYY-MM-DD の日付を直接指定もできる。

どれか1つでも 200 以外が返ったら、出力先には触れずにエラーで終了する
（不完全な書き出しを残さないため、先に全部レンダリングしてから書き出す）。
"""
import argparse
import json
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

CNAME = "shinhatsubai.netaful.jp"


def resolve_reference(option):
    """--reference の値を REFERENCE_DATE 用の日付文字列にする。build なら None（実行日）。"""
    if option == "build":
        return None
    if option == "max":
        with open(os.path.join(BASE_DIR, "data", "products.json"), encoding="utf-8") as f:
            doc = json.load(f)
        return doc.get("date_max")
    return option


def collect_routes(appmod):
    """書き出すルートの一覧。データから導出する（ハードコードしない）。"""
    store = appmod.STORE
    routes = ["/"]
    for date_str in store.dates:
        routes.append("/date/%s/" % date_str)
    for slug, _name in appmod.GENRES:
        if store.genre_products(slug):
            routes.append("/genre/%s/" % slug)
    for key in store.chains:
        routes.append("/chain/%s/" % key)
    routes += ["/sitemap.xml", "/robots.txt", "/feed.json"]
    return routes


def dest_path(out_dir, route):
    rel = route.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return os.path.join(out_dir, rel)


def render_all(client, routes):
    pages = {}
    errors = []
    for route in routes:
        resp = client.get(route)
        if resp.status_code != 200:
            errors.append((route, resp.status_code))
        else:
            pages[route] = resp.get_data()
    return pages, errors


def build(out_dir, reference):
    if reference:
        os.environ["REFERENCE_DATE"] = reference
    import app as appmod  # noqa: E402  REFERENCE_DATE を読む前に環境変数を入れるため遅延 import

    routes = collect_routes(appmod)
    client = appmod.app.test_client()
    pages, errors = render_all(client, routes)
    if errors:
        for route, status in errors:
            print("[build_static] エラー: %s -> HTTP %s" % (route, status), file=sys.stderr)
        print("[build_static] 書き出しを中止しました（出力先には触れていません）", file=sys.stderr)
        return 1

    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    for route, data in pages.items():
        path = dest_path(out_dir, route)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    static_src = appmod.app.static_folder
    static_dst = os.path.join(out_dir, "static")
    static_files = []
    for root, _dirs, files in os.walk(static_src):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, static_src)
            dst = os.path.join(static_dst, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            static_files.append(rel)

    with open(os.path.join(out_dir, "CNAME"), "w", encoding="utf-8") as f:
        f.write(CNAME + "\n")
    open(os.path.join(out_dir, ".nojekyll"), "w").close()

    n_date = sum(1 for r in routes if r.startswith("/date/"))
    n_genre = sum(1 for r in routes if r.startswith("/genre/"))
    print("[build_static] 書き出し完了: %s" % out_dir)
    print("  基準日: %s" % (reference or "ビルド日"))
    n_chain = sum(1 for r in routes if r.startswith("/chain/"))
    print("  ページ: %d（トップ1・日付%d・ジャンル%d・チェーン%d・sitemap.xml・robots.txt）"
          % (len(pages), n_date, n_genre, n_chain))
    print("  静的ファイル: %d（%s）" % (len(static_files), "、".join(sorted(static_files))))
    print("  CNAME: %s / .nojekyll: あり" % CNAME)
    return 0


def main():
    parser = argparse.ArgumentParser(description="新発売ポチの静的書き出し（GitHub Pages用）")
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "docs"),
                        help="出力先ディレクトリ（既定: リポジトリ直下の docs/）")
    parser.add_argument("--reference", default="build",
                        help="「今日」の基準日: build（既定）/ max（データ内の最新日）/ YYYY-MM-DD")
    args = parser.parse_args()
    return build(args.out, resolve_reference(args.reference))


if __name__ == "__main__":
    sys.exit(main())
