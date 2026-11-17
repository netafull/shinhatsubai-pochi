# 食ポチ5サイト データ棚卸し（「今日の発売速報（仮）」集約サイト計画用）

調査日：2026-11-18。対象はローカルクローン `~/workspace/repos/` 配下の5リポジトリ（読み取りのみ）。外部サイトにはアクセスしていない。

- 数値の基準日は 2026-11-18。「直近30日」は 2026-10-19〜2026-11-17、「未来」は 2026-11-18 以降として数えた。
- ローカルクローンの最終コミットは conbini / fastfood / cafe / sushi が 2026-11-13、cupmen が 2026-11-14。数値はその時点のデータに基づく（本番は日次更新されているため、実数とは数日分ずれる可能性がある）。
- 商品数は `data/products/<chain>/<product_id>.json` のファイル数を数えたもの。全ファイルが JSON オブジェクトとして読み込めた。

## 全体サマリー

| サイト | 商品総数 | launch_date あり | 割合 | 発売日の範囲 | 直近30日 | 未来（11/18以降） |
|---|---|---|---|---|---|---|
| コンビニポチ | 1,358 | 1,302 | 95.9% | 2026-09-01〜2026-11-18 | 648 | 8（すべて 11/18） |
| ファストフードポチ | 793 | 86 | 10.8% | 2026-05-20〜2026-11-11 | 20 | 0 |
| カップ麺ポチ | 49 | 40 | 81.6% | 2026-08-03〜2026-11-09 | 23 | 0 |
| カフェポチ | 60 | 23 | 38.3% | 2026-09-28〜2026-11-18 | 15 | 1（11/18） |
| 回転寿司ポチ | 137 | 78 | 56.9% | 2026-08-20〜2026-11-12 | 71 | 0 |
| 合計 | 2,397 | 1,529 | 63.8% | — | 777 | 9 |

未来の発売予定は、基準日当日（11/18）の9件だけで、11/19 以降の日付は5サイトともゼロだった。「発売予定」欄は各サイトの日次巡回で当日・直前に埋まる性質で、先々の予定が貯まっている状態ではない。

---

## 1. コンビニポチ（conbini-pochi）

- 本番：https://conbini.netaful.jp/（`config.json` の `site_url`、`docs/CNAME` で確認）
- データ：`data/products/<chain>/<product_id>.json`、1商品1ファイル。全商品が同じ20キーを持つ。
  - フィールド：`chain, product_id, name, category, price_excl_tax, price_incl_tax, launch_date, launch_text, regions, region_text, description, nutrition, allergens, spec, variants, official_url, first_seen_at, fetched_at, source_list, image`。一部商品に `official_urls`（383件）、`list_week_start`（348件）が付く。
  - `launch_date` は文字列 1,302件 / null 56件。`launch_text`（発売表記の原文）は全件にある。
- 発売日：範囲 2026-09-01〜2026-11-18。直近30日 648件。未来は 11/18 の8件のみ。
- 商品ページURL：`https://conbini.netaful.jp/items/{chain}-{product_id}.html`（`scripts/generate_site.py` の `item_url`）。
- 画像：`image` キーは全件にあるが全件 null。URLが入っている商品は0件。
- チェーン（`config.json` の `chains`、slug→表示名）：seven=セブンイレブン（383件）、familymart=ファミリーマート（428件）、lawson=ローソン（371件）、dailyyamazaki=デイリーヤマザキ（121件）、ministop=ミニストップ（55件）。
- 生成・更新：`scripts/generate_site.py` が `docs/` へ静的生成（GitHub Pages）。`.github/workflows/update.yml` は `workflow_dispatch` のみで、コメントに発火元は Cloud Scheduler ジョブ `conbini-pochi-update`（GCPプロジェクト manga-rss、毎朝7時 JST、1日1回）と明記されている。ワークフローは巡回→レビュー照合→生成→コミット・push→通知の順。

## 2. ファストフードポチ（fastfood-pochi）

- 本番：https://fastfood.netaful.jp/
- データ：`data/products/<chain>/<product_id>.json`、1商品1ファイル。
  - 全商品共通のフィールド：`chain, product_id, name, category, price, price_note, launch_date, planned_end_text, description, description_full_len, nutrition, allergens, origin, limited_kind, official_url, first_seen_at, last_seen_at, status, ended_observed_at, missed_runs, price_history, source_list, image`。
  - 任意フィールドが多い：`is_regular`（564件）、`price_variants`（541件）、`launch_date_source`（541件）、`news_url / news_title / news_date`（各496件）、`badges`（474件）、`announced_at`（395件）、アレルゲン・栄養のPDF系URLなど。チェーン固有のキー（`slug`、`category_id`、`current_slug` 等）もある。
  - 価格は `price`（税込、全件 int）で、コンビニのような税抜・税込の分離はない。
- 発売日：`launch_date` は 86件（10.8%）のみ、707件が null。範囲 2026-05-20〜2026-11-11。直近30日 20件、未来 0件。
  - 理由として確認できたこと：全793件中 `limited_kind` が「定番」564件で、`is_regular=true` も564件。定番メニューを含むアーカイブのため、発売日が埋まるのは主にニュース記事等から日付が取れた商品。`launch_date_source` の内訳は not_found 496件、news_headline 20件、news_article_body 20件、news_article 5件、キー自体がないもの 252件。
- 商品ページURL：`https://fastfood.netaful.jp/items/{chain}-{product_id}.html`（他サイトと同形式）。
- 画像：`image` キーは全件にあるが全件 null。URLが入っている商品は0件。
- チェーン：mcdonalds=マクドナルド（134件）、mos=モスバーガー（118件）、matsuya=松屋（17件）、matsunoya=松のや（33件）、yoshinoya=吉野家（96件）、sukiya=すき家（139件）、katsuya=かつや（109件）、karayama=からやま（85件）、marugame=丸亀製麺（45件）、burgerking=バーガーキング（17件）。表示名は `config.json` の `chains[].name`。
- 生成・更新：静的生成（`docs/`、GitHub Pages）。ワークフローは `workflow_dispatch` のみで、コメントでは Cloud Scheduler ジョブ（`fastfood-pochi-update`、毎朝1回想定）は「運営者の確認後に作成する予定」と書かれている。README には「1日1回巡回」とある。吉野家・すき家の栄養は公式PDF読み取り（pdfminer.six）のステップがある。

## 3. カップ麺ポチ（cupmen-pochi）

- 本番：https://cupmen.netaful.jp/
- データ：`data/products/<chain>/<product_id>.json`、1商品1ファイル。全商品が同じ19キーで、5サイト中いちばんスキーマが均一。
  - フィールド：`chain, product_id, name, price_excl_tax, price_label, launch_date, launch_month, net_amount, net_label, sales_area, ec_only, jan, nutrition, nutrition_label, allergens, discontinued, official_url, first_seen_at, detail_checked_at`。
  - カテゴリー相当のキーはない。価格は税抜のみ（`price_excl_tax`、全件 int）。
- 発売日：`launch_date` は 40件（81.6%）。残り9件は null だが全件 `launch_month`（例：2026-09）を持ち、月単位では全商品に発売時期がある。範囲 2026-08-03〜2026-11-09。直近30日 23件、未来 0件。記録開始は `config.json` の `record_from=2026-08-01`。
- 商品ページURL：`https://cupmen.netaful.jp/items/{chain}-{product_id}.html`。
- 画像：`image` キー自体が存在しない（0件）。
- チェーン：nissin=日清食品（11件）、myojo=明星食品（18件）、sanyo=サンヨー食品（9件）、acecook=エースコック（11件）。表示名は `config.json` の `chains[].name`。チェーン一覧ページのパスは他サイトの `chains/` ではなく `companies/`。
- 生成・更新：静的生成（`docs/`、GitHub Pages、README に「公開済み・運用中。定期実行で毎朝更新」と明記）。ワークフローは `workflow_dispatch` のみで、コメントでは Cloud Scheduler ジョブ（`cupmen-pochi-update`、毎朝9:00 JST想定）は作成予定と書かれている。

## 4. カフェポチ（cafe-pochi）

- 本番：https://cafe.netaful.jp/
- データ：`data/products/<chain>/<product_id>.json`、1商品1ファイル。回転寿司ポチとほぼ同系のスキーマ。
  - 全商品共通のフィールド：`chain, product_id, name, category, price, price_max, price_note, price_variants, launch_date, launch_date_source, news_title, news_url, news_date, listed_at, planned_end_text, nutrition, nutrition_variants, nutrition_note, nutrition_source, allergens, allergen_source, allergen_note, limited_kind, stores_note, official_url, first_seen_at, last_seen_at, status, ended_observed_at, missed_runs, price_history, launch_search_runs, source_list`。一部に `nutrition_label`（58件）、`detail_checked_at`（24件）等。
  - 価格は `price`（int、全件）＋ `price_max`（19件）。
- 発売日：`launch_date` は 23件（38.3%）、37件が null。範囲 2026-09-28〜2026-11-18。直近30日 15件、未来は 11/18 の1件。`launch_date_source` の内訳は press_release_body 11件、official_news_body 9件、press_release 3件。発売日がなくても `listed_at`（公式一覧への掲載日）を持つ商品が7件ある。
- 商品ページURL：`https://cafe.netaful.jp/items/{chain}-{product_id}.html`。
- 画像：`image` キー自体が存在しない（0件）。
- チェーン：starbucks=スターバックス（36件）、tullys=タリーズ（8件）、komeda=コメダ珈琲店（10件）、doutor=ドトールコーヒーショップ（6件）。表示名は `config.json` の `chains[].name`。
- 生成・更新：静的生成（`docs/`、GitHub Pages）。ワークフローは `workflow_dispatch` のみで、コメントでは Cloud Scheduler ジョブ（`cafe-pochi-update`、毎朝1回想定）は作成予定と書かれている。

## 5. 回転寿司ポチ（sushi-pochi）

- 本番：https://sushi.netaful.jp/
- データ：`data/products/<chain>/<product_id>.json`、1商品1ファイル。カフェポチとほぼ同系のスキーマに、寿司固有の `period`（99件、`{start, end, quantity, sellout}` の辞書。ただし start/end が null のものも含む）と `limited_by`（38件）が加わる。
- 発売日：`launch_date` は 78件（56.9%）、59件が null。範囲 2026-08-20〜2026-11-12。直近30日 71件、未来 0件。`launch_date_source` の内訳は official_json 36件、official_news_body 29件、menu_period 13件。
- 商品ページURL：`https://sushi.netaful.jp/items/{chain}-{product_id}.html`。
- 画像：`image` キー自体が存在しない（0件）。
- チェーン：sushiro=スシロー（13件）、kurasushi=くら寿司（38件）、hamazushi=はま寿司（50件）、kappasushi=かっぱ寿司（36件）。表示名は `config.json` の `chains[].name`。
- 生成・更新：静的生成（`docs/`、GitHub Pages）。ワークフローは `workflow_dispatch` のみで、コメントでは Cloud Scheduler ジョブ（`sushi-pochi-update`、毎朝1回想定）は作成予定と書かれている。アレルゲン等は公式PDF読み取りのステップがある。

---

## netaful_reviews.json（5サイト共通の形式）

全サイトとも `data/netaful_reviews.json` が同じ4キー構成だった。

```json
{
  "articles": { "<chain>": [ { "id": 記事ID, "date": "公開日時", "link": "https://netaful.jp/...",
                               "title": "記事タイトル", "product_name": "記事から抽出した商品名",
                               "thumb": { "url": "サムネイルURL", "width": 485, "height": 364 } } ] },
  "matches":  { "<chain>-<product_id>": [記事ID, ...] },
  "errors":   [],
  "fetched_at": "最終取得日時"
}
```

- 紐づけのキーは `matches` の `"chain-product_id"`（商品ページURLのファイル名部分と同一）で、値はネタフル記事IDの配列。記事の詳細（タイトル・URL・サムネイル）は `articles` 側を記事IDで引く形。
- 件数：

| サイト | articles 合計 | matches（レビューが付いた商品） |
|---|---|---|
| コンビニポチ | 1,009（seven 541 / lawson 235 / familymart 231 / ministop 2） | 15商品 |
| ファストフードポチ | 867（matsuya 254 / mcdonalds 209 ほか） | 27商品 |
| カップ麺ポチ | 274（nissin 198 ほか） | 1商品 |
| カフェポチ | 94 | 0商品 |
| 回転寿司ポチ | 34 | 0商品 |

- `articles` は候補記事の蓄積で、`matches` が実際に商品と結び付いたもの。カフェ・回転寿司は候補記事はあるが一致は0件だった。
- 各サイトの商品ページでは、この `thumb.url` がレビュー記事のサムネイル表示に使われている（`generate_site.py` で確認）。商品画像の供給源は現状これだけ。

## 横断まとめ（集約サイトを作る観点）

### 揃っているもの

- データ形式：全サイト `data/products/<chain>/<product_id>.json` の1商品1ファイル。`chain` / `product_id` / `name` / `official_url` / `first_seen_at` は全サイト・全商品にある。
- 商品ページURL：全サイト共通で `https://<サイト>.netaful.jp/items/{chain}-{product_id}.html`。集約側は `site_url + items/{chain}-{product_id}.html` で機械的にリンクを組み立てられる。
- チェーン表示名：全サイト `config.json` の `chains[].slug / name` にある。集約側はこれを読めば日本語名を統一できる。全27チェーン（5+10+4+4+4）。
- レビュー紐づけ：`netaful_reviews.json` の形式（articles / matches / errors / fetched_at）が5サイト完全共通。matches のキーはURLのファイル名部と一致する。
- 生成・更新：全サイトとも Python スクリプトで `docs/` へ静的生成し GitHub Pages で公開、更新ワークフロー（巡回→レビュー照合→生成→push）は同構成。集約サイトも同じ型（各サイトの data を読んで静的生成）に乗せられる。

### サイトごとに違うもの

- 発売日の充足率が大きく違う：コンビニ 95.9% に対しファストフード 10.8%、カフェ 38.3%、回転寿司 56.9%、カップ麺 81.6%。ファストフードは定番メニュー（564件）が母数に入っているためで、発売日ベースの集約では「日付なし商品をどう扱うか」がサイトごとに問題になる。
- 発売日の代替情報の持ち方：コンビニは `launch_text`（原文、全件）、カップ麺は `launch_month`（月単位、全件）、回転寿司は `period.start`（99件、null 含む）、カフェは `listed_at`（掲載日、発売日なしでも7件）、ファストフードは `announced_at`（395件がキーを持つが値があるのは19件）など、揃っていない。
- 価格フィールド：コンビニは `price_excl_tax / price_incl_tax`、カップ麺は `price_excl_tax` のみ、他3サイトは `price`（＋ `price_max`、`price_variants`）。表示用の価格を統一するにはサイト別の読み替えが要る。
- カテゴリー：コンビニ・ファストフード・カフェ・回転寿司には `category` があるが、カップ麺にはない。値の体系もチェーンごとに別。
- スキーマの均一さ：コンビニとカップ麺は全商品同一キー。ファストフード・カフェ・回転寿司は任意キーが多く、特にファストフードはチェーン固有キーが混ざる。
- 更新スケジュールの確定度：ワークフロー自体は全サイト `workflow_dispatch` のみ。コンビニだけがコメントに Cloud Scheduler ジョブ（毎朝7時）の存在を明記し、他4サイトはコメント上「作成予定・想定」の書き方。README の記述（「1日1回巡回」「毎朝更新」）とは温度差がある。

### 欠けているもの

- 商品画像：5サイトとも商品データに画像URLがない。コンビニとファストフードは `image` キーがあるが全件 null、他3サイトはキー自体がない。集約サイトで画像付きカードにするには、レビュー記事のサムネイル（matches がある商品のみ：15+27+1+0+0=43商品）しか現状の供給源がない。
- 未来の発売予定：基準日（11/18）当日分9件のみで、それより先の予定は全サイトゼロ。「今日発売」は成立しても「来週の発売予定」を厚くするには、各サイトの巡回で先行発表を拾う仕組みが別途要る。
- ファストフードの発売日：86件しかなく、直近30日も20件。コンビニ中心の集約にならないよう、日付なし商品の見せ方（初掲載日 `first_seen_at` で代替する等）の設計が要る。
- レビューの一致：カフェ・回転寿司は matches が0件で、集約側でレビューリンクを出せるのは実質コンビニとファストフードの一部だけ。
