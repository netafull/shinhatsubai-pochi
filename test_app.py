"""新発売ポチのテスト。ネットワーク不要。実データ（data/products.json）で確認する。

実行: .venv/bin/python -m unittest test_app
"""
import datetime
import os
import unittest

os.environ.setdefault("REFERENCE_DATE", "2026-11-18")  # データ内の最新日を「今日」にする

import app as appmod  # noqa: E402


class StoreTest(unittest.TestCase):
    def test_products_loaded(self):
        self.assertGreater(len(appmod.STORE.products), 0)

    def test_all_products_have_launch_date(self):
        for p in appmod.STORE.products:
            self.assertTrue(appmod._is_date(p["launch_date"]))

    def test_genres_are_six(self):
        self.assertEqual([slug for slug, _ in appmod.GENRES],
                         ["conbini", "fastfood", "cupmen", "cafe", "sushi", "famires"])
        for slug, _name in appmod.GENRES:
            self.assertGreater(len(appmod.STORE.genre_products(slug)), 0)

    def test_reference_date_from_env(self):
        self.assertEqual(appmod.reference_date(), datetime.date(2026, 11, 18))


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = appmod.app.test_client()

    def test_top(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        text = r.get_data(as_text=True)
        self.assertIn("今日発売", text)
        self.assertIn("今週発売", text)
        self.assertIn("先週発売", text)

    def test_date_page(self):
        newest = appmod.STORE.dates[0]
        r = self.client.get("/date/%s/" % newest)
        self.assertEqual(r.status_code, 200)

    def test_date_page_404_for_empty_date(self):
        r = self.client.get("/date/2020-01-01/")
        self.assertEqual(r.status_code, 404)

    def test_genre_page(self):
        self.assertEqual(self.client.get("/genre/conbini/").status_code, 200)
        key = next(iter(appmod.STORE.chains))
        self.assertEqual(self.client.get("/chain/%s/" % key).status_code, 200)

    def test_unknown_pages_404(self):
        self.assertEqual(self.client.get("/genre/nope/").status_code, 404)
        self.assertEqual(self.client.get("/chain/nope-nope/").status_code, 404)

    def test_tax_label_shown(self):
        text = self.client.get("/genre/cupmen/").get_data(as_text=True)
        self.assertIn("（税抜）", text)  # カップ麺は税抜のみのデータ
        text = self.client.get("/genre/conbini/").get_data(as_text=True)
        self.assertIn("（税込）", text)

    def test_sitemap_and_robots(self):
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)
        self.assertEqual(self.client.get("/robots.txt").status_code, 200)


def _product(**kw):
    """テスト用の最小の商品データ。"""
    base = {"site": "conbini", "site_name": "コンビニポチ", "site_url": "https://conbini.netaful.jp",
            "chain": "seven", "chain_name": "セブン-イレブン", "product_id": "1", "name": "テスト弁当",
            "category": None, "price": 213.84, "price_max": None, "price_tax": "incl", "price_note": None,
            "description": None, "region_text": None, "launch_date": "2026-11-18",
            "url": "https://conbini.netaful.jp/items/seven-1.html", "review_url": None, "review_title": None}
    base.update(kw)
    return base


class CategoryIconTest(unittest.TestCase):
    def _sample(self, site):
        return dict(next(p for p in appmod.STORE.products if p["site"] == site))

    def test_conbini_onigiri_icon(self):
        p = self._sample("conbini")
        p["category"] = "おにぎり"
        text = appmod._product_card(p)
        self.assertIn("/static/icons/cat/onigiri.svg", text)
        self.assertIn('class="sh-cat-icon"', text)
        self.assertTrue(text.startswith('<li class="ms-card"><img class="sh-cat-icon"'))

    def test_cupmen_icon_regardless_of_category(self):
        p = self._sample("cupmen")
        p["category"] = None
        self.assertIn("/static/icons/cat/cupnoodle.svg", appmod._product_card(p))

    def test_no_icon_without_category(self):
        p = self._sample("conbini")
        p["category"] = None
        p["name"] = "ロングタオル　ブラック"  # 名前から推定できない商品
        self.assertNotIn("sh-cat-icon", appmod._product_card(p))
        p["category"] = "未登録カテゴリ"
        p["name"] = "手巻おにぎり　鮭"  # カテゴリーがある商品は名前で推定しない
        self.assertNotIn("sh-cat-icon", appmod._product_card(p))

    def test_guess_icon_from_name_when_no_category(self):
        p = self._sample("conbini")
        p["category"] = None
        p["name"] = "手巻おにぎり　炭火焼紅しゃけ"
        text = appmod._product_card(p)
        self.assertIn("/static/icons/cat/onigiri.svg", text)
        self.assertIn('alt="おにぎり"', text)
        self.assertNotIn('<span class="ms-chip">おにぎり</span>', text)  # 推定はカテゴリー名として出さない

    def test_guess_rules(self):
        cases = [
            ("手巻寿司　まぐろたたき巻", "conbini", "sushi"),
            ("焼きさば御飯（もち麦）", "conbini", "bento"),
            ("町中華の鉄鍋炒めチャーハン", "conbini", "bento"),
            ("焼きそばパン　マヨネーズ入", "conbini", "bread"),
            ("ボルドー産赤ワイン仕立てのデミソースハンバーグ弁当", "conbini", "bento"),
            ("おにぎり浅草宿六監修　こだわり味噌の豚汁", "conbini", "soup"),
            ("広島県産牡蠣のカキフライ3個（タルタルソース）", "sushi", "sozai"),
            ("サラダ軍艦", "sushi", "sushi"),
            ("炙り牛タン", "sushi", "sushi"),
            ("横浜家系ラーメン", "sushi", "noodles"),
            ("森永製菓　パキパリおっとっと　サワークリームオニオン味", "conbini", "snack"),
            ("純米酒 晴雲", "sushi", "alcohol"),
            ("松茸あんかけ茶碗蒸し", "sushi", "soup"),
            ("えびブロッコリーサラダ", "sushi", "salad"),
            ("サラダ軍艦", "sushi", "sushi"),
            ("紫キャベツの酢漬け", "sushi", "salad"),
            ("辛ラーメン専用 追いシャリ", "sushi", "sushi"),
            ("つぶあんぱん", "conbini", "bread"),
            ("ロールキャベツ", "conbini", "sozai"),
            ("蜜芋オレ ～種子島産安納芋使用～", "cafe", "drink"),
        ]
        for name, site, want in cases:
            self.assertEqual(appmod.guess_icon(name, site), want, name)

    def test_famires_loaded_with_tax_included_price(self):
        fam = [p for p in appmod.STORE.products if p["site"] == "famires"]
        self.assertGreater(len(fam), 0)
        for p in fam:
            self.assertEqual(p["site_name"], "ファミレスポチ")
            self.assertEqual(p["price_tax"], "incl")
            self.assertIsInstance(p["price"], int)
            self.assertTrue(p["url"].startswith("https://famires.netaful.jp/items/"))
        self.assertEqual({p["chain"] for p in fam} - {"dennys"}, set())  # ジョナサンは発売日なしで載らない
        self.assertEqual(appmod.GENRE_NAMES["famires"], "ファミレス")

    def test_famires_icon_guess(self):
        cases = [("味噌らぁ麺・改～五重の味噌", "noodles"), ("おいもプリン", "sweets"),
                 ("蜜いものブリュレパンケーキ（パンケーキ4枚）", "sweets"), ("蜜いものキャラメリゼ～バニラアイス添え", "sweets"),
                 ("さつまいもアイスとあずきの白蜜ゼリー", "sweets")]
        for name, want in cases:
            p = self._sample("famires")
            p["category"] = None
            p["name"] = name
            self.assertEqual(appmod._category_icon(p)[0], want, name)
        p = self._sample("famires")
        p["category"] = None
        p["name"] = "ニラともやしのシャキシャキ焼き"
        self.assertIsNone(appmod._category_icon(p))  # 決まらないものは出さない
        for name in ("蜜いものパルフェ", "蜜いものザ・サンデー～紅天使使用"):  # 2026-11-23 規則に追加（オーナー判断）
            p["name"] = name
            self.assertEqual(appmod._category_icon(p)[0], "sweets", name)

    def test_famires_in_feed(self):
        f = appmod.build_feed(datetime.date(2026, 10, 28), generated="2026-10-28T10:00:00+09:00")
        fam = [i for i in f["items"] if i["source"] == "famires"]
        self.assertGreater(len(fam), 0)
        for i in fam:
            self.assertEqual(i["source_name"], "ファミレスポチ")
            self.assertEqual(i["brand"], "デニーズ")
            self.assertTrue(i["id"].startswith("famires:dennys-"))
            if i["icon"]:
                self.assertTrue(i["icon"].startswith("https://shinhatsubai.netaful.jp/static/icons/cat/"))
        self.assertTrue(any(i["icon"] for i in fam))

    def test_guess_labels_cover_all_slugs(self):
        base = os.path.join(os.path.dirname(appmod.__file__), "static", "icons", "cat")
        for slug in appmod.ICON_LABELS:
            self.assertTrue(os.path.isfile(os.path.join(base, slug + ".svg")), slug)

    def test_mapped_icon_files_exist(self):
        slugs = {s for m in appmod.CATEGORY_ICONS.values() for s in m.values()} | {"cupnoodle"}
        base = os.path.join(os.path.dirname(appmod.__file__), "static", "icons", "cat")
        for slug in slugs:
            self.assertTrue(os.path.isfile(os.path.join(base, slug + ".svg")), slug)


class FloatPriceTest(unittest.TestCase):
    def test_float_price_kept_and_rendered(self):
        p, reason = appmod.ProductStore._validate(_product())
        self.assertIsNone(reason)
        self.assertEqual(p["price"], 213.84)
        html_text = appmod._price_html(p)
        self.assertIn("213円", html_text)  # 表示は切り捨て（データは 213.84 のまま）
        self.assertIn("（税込）", html_text)

    def test_integral_float_becomes_int_with_separator(self):
        p, _ = appmod.ProductStore._validate(_product(price=1234.0))
        self.assertEqual(p["price"], 1234)
        self.assertIsInstance(p["price"], int)
        self.assertIn("1,234円", appmod._price_html(p))

    def test_bool_price_rejected(self):
        p, _ = appmod.ProductStore._validate(_product(price=True))
        self.assertIsNone(p["price"])

    def test_real_data_has_float_incl_price(self):
        self.assertTrue(any(isinstance(p["price"], float) and p["price_tax"] == "incl"
                            for p in appmod.STORE.products))


class RegionLabelTest(unittest.TestCase):
    def test_label_only_for_duplicated_groups(self):
        a = _product(product_id="1", region_text="中国")
        b = _product(product_id="2", region_text="四国")
        c = _product(product_id="3", name="別の弁当", region_text="北海道")
        out = appmod._cards([a, b, c])
        self.assertIn('<span class="region">中国</span>', out)
        self.assertIn('<span class="region">四国</span>', out)
        self.assertNotIn("北海道", out)  # 重複していない商品には付けない

    def test_long_region_truncated(self):
        a = _product(product_id="1", region_text="あ" * 20)
        b = _product(product_id="2", region_text="い")
        out = appmod._cards([a, b])
        self.assertIn("あ" * 12 + "…", out)
        self.assertNotIn("あ" * 13, out)

    def test_empty_region_shows_nothing(self):
        a = _product(product_id="1", region_text=None)
        b = _product(product_id="2", region_text="四国")
        out = appmod._cards([a, b])
        self.assertEqual(out.count('class="region"'), 1)


class FeedTest(unittest.TestCase):
    def test_feed_shape_and_window(self):
        ref = datetime.date(2026, 11, 18)
        f = appmod.build_feed(ref, generated="2026-11-18T10:00:00+09:00")
        self.assertEqual(f["version"], 1)
        self.assertEqual(f["site"], "shinhatsubai")
        self.assertGreater(len(f["items"]), 0)
        self.assertLessEqual(len(f["items"]), 50)
        dates = [i["date"] for i in f["items"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertTrue(all("2026-11-15" <= d <= "2026-11-18" for d in dates))
        self.assertEqual(len({i["id"] for i in f["items"]}), len(f["items"]))
        for i in f["items"]:
            self.assertIn(i["source"], ("conbini", "fastfood", "cafe", "sushi", "cupmen", "famires"))
            self.assertTrue(i["url"].startswith("https://"))
            self.assertIsNone(i["image"])
            self.assertTrue(i["brand"])  # チェーン名（例「スターバックス」）
            if i["icon"]:
                self.assertTrue(i["icon"].startswith("https://shinhatsubai.netaful.jp/static/icons/cat/"))

    def test_future_excluded(self):
        f = appmod.build_feed(datetime.date(2026, 1, 1))
        self.assertTrue(all(i["date"] <= "2026-01-01" for i in f["items"]))

    def test_route(self):
        r = appmod.app.test_client().get("/feed.json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["version"], 1)


class ReferenceDateTest(unittest.TestCase):
    def test_default_is_jst_date(self):
        saved = os.environ.pop("REFERENCE_DATE", None)
        try:
            expected = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()
            self.assertEqual(appmod.reference_date(), expected)
        finally:
            if saved is not None:
                os.environ["REFERENCE_DATE"] = saved


class Ga4Test(unittest.TestCase):
    def test_absent_when_empty(self):
        saved = appmod.GA4_ID
        appmod.GA4_ID = ""
        try:
            text = appmod.app.test_client().get("/").get_data(as_text=True)
        finally:
            appmod.GA4_ID = saved
        self.assertNotIn("googletagmanager", text)
        self.assertNotIn("{{GA4}}", text)

    def test_present_when_set(self):
        saved = appmod.GA4_ID
        appmod.GA4_ID = "G-TEST123456"
        try:
            text = appmod.app.test_client().get("/").get_data(as_text=True)
        finally:
            appmod.GA4_ID = saved
        self.assertIn("googletagmanager.com/gtag/js?id=G-TEST123456", text)


if __name__ == "__main__":
    unittest.main()


class PriceFormatTest(unittest.TestCase):
    def test_decimal_floored(self):
        self.assertEqual(appmod._fmt_price(494.64), "494")
        self.assertEqual(appmod._fmt_price(1234), "1,234")
        self.assertEqual(appmod._fmt_price(1234.9), "1,234")


class GroupedOrderTest(unittest.TestCase):
    def test_upcoming_ascending_and_default_descending(self):
        ps = [_product(product_id=str(i), launch_date=d) for i, d in enumerate(["2026-11-30", "2026-11-23", "2026-11-25"])]
        asc = appmod._grouped_by_date(ps, ascending=True)
        self.assertLess(asc.index("/date/2026-11-23/"), asc.index("/date/2026-11-25/"))
        self.assertLess(asc.index("/date/2026-11-25/"), asc.index("/date/2026-11-30/"))
        desc = appmod._grouped_by_date(ps)
        self.assertLess(desc.index("/date/2026-11-30/"), desc.index("/date/2026-11-23/"))
