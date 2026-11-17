# 新発売ポチ（試作）

コンビニ・ファストフード・カップ麺・カフェ・回転寿司の食ポチ5サイトが記録している新商品を、発売日で横断集約するサイト「新発売ポチ」（shinhatsubai.netaful.jp）の試作です。

- 名前とドメインは 2026-11-18 に所有者が決定（計画メモ: `~/workspace/michinoeki-pilot/release-aggregator-plan.md`）。
- この試作はローカルで静的ビルドが通るところまでです。**リポジトリ作成・DNS・公開はまだしていません。**
- デザインは兄弟サイト「道の駅ポチ」の家族デザイン（ヘッダー、カード、フッターの関連サイトチップ）を土台に、アクセント色だけ橙赤系に変えています。ロゴ・favicon・OGP画像は道の駅ポチのものを仮置きしています。

## データ源

5リポジトリ（ローカルでは `~/Desktop/Claude/` 直下、CI では `sources/` 配下）を**読み取りのみ**で使います（このプロジェクトからは一切変更しません）。

| サイト | リポジトリ | 商品総数 | 発売日あり |
|---|---|---|---|
| コンビニポチ | conbini-pochi | 1,358 | 1,302 |
| ファストフードポチ | fastfood-pochi | 793 | 86 |
| カップ麺ポチ | cupmen-pochi | 49 | 40 |
| カフェポチ | cafe-pochi | 60 | 23 |
| 回転寿司ポチ | sushi-pochi | 137 | 78 |
| 合計 | | 2,397 | **1,529** |

（2026-11-18 の集約実行時の数。詳細な棚卸しは `~/workspace/michinoeki-pilot/release-aggregator-inventory.md`）

### 注意：データの時点

ローカルクローンは本番データとずれていることがあります。`data/products.json` の `sources` に、集約時点の各リポジトリの HEAD（コミットと日付）を記録しています。更新ワークフローでは GitHub 上の最新を取り込んでから集約します。

### 集約のルール（scripts/aggregate.py）

- 掲載対象は `launch_date`（発売日）がある商品だけ。発売日がない商品は載せません。
- 価格は税込優先。税抜しかない商品（現状はカップ麺の全件）は `price_tax="excl"` として保持し、画面で「（税抜）」と明示します。推測で税込換算はしません。
  - conbini: `price_incl_tax` → 税込（float も受け付ける。213.84 のような値はそのまま持ち「213.84円（税込）」と表示、整数値は int にして「1,234円」）、なければ `price_excl_tax` → 税抜
  - cupmen: `price_excl_tax` のみ → 税抜
  - fastfood / cafe / sushi: `price` は税込（各商品の `price_note` が税込表記であることを確認済み）。cafe は `price_max` がある場合に価格帯として表示
- チェーン表示名は各サイトの `config.json` の `chains[].name` を使います。
- 商品ページURLは `https://<サイト>.netaful.jp/items/{chain}-{product_id}.html`（site_url は config.json から取得）。
- レビュー紐づけは各サイトの `data/netaful_reviews.json` の `matches`（`"chain-product_id"` → 記事ID配列）と `articles` から引きます。発売日あり商品の中で一致したのは15件（コンビニ13・ファストフード2）で、その商品にだけ「ネタフルでレビュー」リンクを出します。なお reviews の一致自体は43商品ありますが、残り28商品は発売日がないため本サイトの掲載対象外です。
- 販売地域（`region_text`）が空でなければ商品に持たせます。同じ一覧に、チェーン・名前・発売日が同じ商品が複数あるとき（地域違い）だけ、名前の横に地域ラベル（12文字超は先頭12文字＋…）を出します。
- 商品画像は5サイトともデータに無いため、カードは画像なしのテキスト中心です。

## 構成

```
app.py                  Flask アプリ（data/products.json を読んで描画）
data/products.json      集約済みデータ（aggregate.py の出力。試作のスナップショット）
scripts/aggregate.py    5サイトのデータを正規化して data/products.json を生成
scripts/build_static.py Flask の test_client で全ルートを描画し docs/ へ静的書き出し
static/style.css        道の駅ポチの CSS を土台にアクセント色を変更＋固有の追加分
static/assets/          ロゴ等（道の駅ポチから仮置き）
docs/                   静的書き出しの出力（GitHub Pages 想定）
test_app.py             unittest（21件）
.github/workflows/update.yml  更新ワークフロー（workflow_dispatch のみ）
```

### ページ

- `/` トップ：今日発売 → 今週発売（過去6日、日ごとに区切り）→ 先週発売（7〜13日前、日ごとに区切り）。基準日より後30日以内の商品があれば「近日発売」も出す
- `/date/YYYY-MM-DD/` 日付ページ（商品がある日だけ生成。58日分）
- `/genre/<site>/` ジャンル別（5サイト別、発売日の新しい順に日付で区切り）
- `/chain/<site>-<chain>/` チェーン別（発売日つき商品がある22チェーン分）
- `/sitemap.xml`、`/robots.txt`

「今日」の基準日は通常はビルド日（日本時間 +09:00。実行マシンのタイムゾーンに依存しない）です。試作ではデータ内の最新日付（2026-11-18）を基準にできるよう、`build_static.py --reference max`（または `REFERENCE_DATE` 環境変数）で上書きできます。

## ビルド方法

```bash
cd ~/Desktop/Claude/shinhatsubai-pochi
.venv/bin/python scripts/aggregate.py                 # データ集約（既定: 環境変数 POCHI_REPOS、なければ親ディレクトリ ~/Desktop/Claude）
.venv/bin/python scripts/aggregate.py --repos <dir>    # 取り込み元を明示するとき
.venv/bin/python scripts/build_static.py               # 静的書き出し → docs/（基準日は日本時間のビルド日。GA4_ID があればGA4タグも出力）
.venv/bin/python -m unittest test_app                  # テスト
.venv/bin/python app.py                                # 開発サーバー（http://localhost:8080）
```

ビルド結果の目安：93ページ前後（トップ1・日付63・ジャンル5・チェーン22・sitemap.xml・robots.txt）。

## 更新の仕組み

`.github/workflows/update.yml`（`workflow_dispatch` のみ）が、5つの公開リポジトリ（netafull/conbini-pochi ほか）を `sources/` にチェックアウトし、集約→静的書き出し→テストを実行して、`docs/` と `data/` に差分があればコミット・push します（`sources/` は git 管理外）。

- 起動は Cloud Scheduler のジョブ `shinhatsubai-pochi-update`（毎日10:00 JST、5サイトの更新 7:00〜9:00 の後）。`schedule:` を使わないのは、GitHub の cron が高負荷時にスキップされるため。
- GA4 は GitHub のリポジトリ変数 `GA4_ID` を設定すれば、ビルド時にタグが入ります（未設定なら出力なし）。
- `data/products.json` は git 管理に含めます（アプリとテストの入力で、差分履歴も残るため）。CI では毎回再生成されます。

## 本番化のときに必要な作業

1. **リポジトリ作成**：GitHub（netafull）に新規リポジトリを作り、この一式を push。docs/ を GitHub Pages の公開元にする（兄弟サイトと同じ運用）。
2. **DNS**：shinhatsubai.netaful.jp の CNAME を GitHub Pages 向けに設定し、証明書発行と HTTPS 強制を確認する。
3. **GA4 / GSC 登録**：GA4 プロパティを作成して測定IDを `GA4_ID`（リポジトリ変数）に設定する。Google Search Console にプロパティを追加し、sitemap.xml を送信する。
4. **更新の自動化**：ワークフローは作成済み。Cloud Scheduler のジョブ作成と、GitHub 側の起動権限（トークン）の設定が必要。
5. **アセット差し替え**：ロゴ・favicon・OGP画像を新発売ポチ用に作り直す（現在は道の駅ポチの仮置き）。
6. **関連サイトへの追加**：公開時に、他ポチのフッター関連サイトチップとポチ・ローテーターへ新発売ポチを追加する（道の駅ポチ公開時の手順と同じ）。
7. **文言の最終確認**：フッターの説明文とメディアポリシーまわりを所有者が確認する。

## 残る課題・分かっている制約

- **未来の発売予定が薄い**：データの性質上、発売予定は巡回で当日・直前に埋まるため、「近日発売」はほぼ空になる。先行発表を拾う仕組みは各サイト側の課題。
- **発売日つき商品が0件のチェーンが5つある**（丸亀製麺・バーガーキング・サンヨー食品・ドトールコーヒーショップ・くら寿司）。これらのチェーンはチェーンページ自体を作っていない（0件のページは作らない方針）。各サイト側で発売日が記録されれば自動で出る。
- **ジャンルページが大きい**：コンビニは1,302件を1ページに並べるため、ジャンルページのHTMLが大きめ（docs 全体で約4.3MB）。本番化のときに月別分割やページ分割を検討する。
- **レビュー紐づけが少ない**：発売日あり商品では15件のみ。カフェ・回転寿司は reviews の一致自体が0件。
- **説明文がないサイトがある**：説明の抜粋を出せるのはコンビニ（全件）とファストフード（一部）だけ。他3サイトのカードは名前・価格・カテゴリーのみになる。
