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

    def test_genres_are_five(self):
        self.assertEqual([slug for slug, _ in appmod.GENRES],
                         ["conbini", "fastfood", "cupmen", "cafe", "sushi"])
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


class FloatPriceTest(unittest.TestCase):
    def test_float_price_kept_and_rendered(self):
        p, reason = appmod.ProductStore._validate(_product())
        self.assertIsNone(reason)
        self.assertEqual(p["price"], 213.84)
        html_text = appmod._price_html(p)
        self.assertIn("213.84円", html_text)
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
