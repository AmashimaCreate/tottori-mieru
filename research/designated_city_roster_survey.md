# 政令指定都市20市議会 名簿構造・実装前偵察

調査日: 2026-06-18

## 0. 結論

政令指定都市20市の議員名簿は、外部ベンダー名簿ではなく、全市が公式サイト内の複数ビュー型に寄っている。

分類結果:

| 型 | 市数 | 対象 |
|---|---:|---|
| (a) 公式CMS multi-view型 | 20 | 札幌、仙台、さいたま、千葉、横浜、川崎、相模原、新潟、静岡、浜松、名古屋、京都、大阪、堺、神戸、岡山、広島、北九州、福岡、熊本 |
| (b) HTML表+個別プロフィール型 | 0 | 単独主ソースとしては該当なし。多くは(a)内の個別ページとして存在 |
| (c) WYSIWYG/Word貼付型 | 0 | 単独主ソースとしては該当なし。相模原・神戸などにWYSIWYG風ページあり |
| (d) PDF型 | 0 | 補助PDFはあるが、主名簿はHTML |
| (e) gijiroku/g07等外部ASP | 0 | 千葉などで会議録/中継ASPはあるが、名簿主ソースではない |

実装方針としては、新規 `municipal_official_multiview_roster` を作り、五十音・区別・会派別・委員会別を市別設定で結合するのが第一候補。既存 `single_page_roster` の正規化・検算・出力契約は流用できるが、市議会は個人情報混在リスクが都道府県より高いため、許可リスト抽出を必須にする。

## 1. 共通観察

- 政令市20市は、行政区別/選挙区別、会派別、委員会別、50音順の複数ビューを持つ市が多い。
- 政令市では「選挙区」はほぼ行政区単位。
- 当選回数は一部市でHTML上にあるが、全市共通ではない。取れない市は `null` が妥当。
- 個別プロフィールページがある市では、住所・電話・メール・経歴・SNS等が混在する可能性がある。保存対象は氏名・ふりがな・会派・行政区/選挙区・当選回数・委員会・役職・公式URLに限定する。
- 現員は、実装時に公式名簿の実掲載数を機械カウントして最終確定する。今回の偵察では、公式ページに欠員表示が明記された相模原市・福岡市を除き、欠員表示なし=定数相当として扱う。

## 2. 市別サマリー

| 市 | 所属都道府県 | 型 | 主ソースURL | 定数・現員・欠員 | 当選回数 | 個人情報混在度 | 注意点 |
|---|---|---|---|---|---|---|---|
| 札幌市 | 北海道 | (a) | https://www.city.sapporo.jp/gikai/html/giin.html | 定数68 / 現員68相当 / 欠員表示なし | あり。区別ページに「○期」 | 中 | 区別・会派・委員会・50音。区別ページに氏名かな、会派、期数、委員会がまとまる |
| 仙台市 | 宮城県 | (a) | https://www.gikai.city.sendai.jp/list/index.html | 定数55 / 現員55相当 / 欠員表示なし | 要確認 | 中 | 区別・会派別・委員会等。区別一覧PDFもあるが主ソースはHTML |
| さいたま市 | 埼玉県 | (a) | https://www.city.saitama.lg.jp/gikai/001/002/index.html | 定数60 / 現員60 / 欠員表示なし | 要確認 | 中 | 公式ページに「60人の市議会議員」と明記。50音・選出区・委員会・会派 |
| 千葉市 | 千葉県 | (a) | https://www.city.chiba.jp/shigikai/meibo-menu.html | 定数50 / 現員50相当 / 欠員表示なし | 要確認 | 中 | 会議録/中継は `chiba-city.gijiroku.com` だが、名簿は公式HTML。選出区別・五十音・委員会・会派・議席別 |
| 横浜市 | 神奈川県 | (a) | https://www.city.yokohama.lg.jp/shikai/giin/ | 定数86 / 現員86相当 / 欠員表示なし | 要確認 | 中 | 選挙区別、会派別、委員会別、50音順。大規模で区ページ分割あり |
| 川崎市 | 神奈川県 | (a) | https://www.city.kawasaki.jp/shisei/category/40-3-0-0-0-0-0-0-0-0.html | 定数60 / 現員60相当 / 欠員表示なし | 要確認 | 中 | 議員名簿カテゴリ配下に五十音別・委員会別・会派別・各種名簿。トップ `/980/` は403になるがカテゴリ経由は取得可 |
| 相模原市 | 神奈川県 | (a) | https://www.sagamihara-shigikai.jp/doc/2013122400014/ | 定数46 / 現員45 / 欠員1（中央区） | 要確認 | 中 | 選出区別ページに「中央区（定数17）※欠員1名」。50音・選出区・委員会・会派。WYSIWYG風HTML |
| 新潟市 | 新潟県 | (a) | https://www.city.niigata.lg.jp/shigikai/index_meibo/index.html | 定数50 / 現員50相当 / 欠員表示なし | 要確認 | 中 | 定数と区別人数が本文に明記。区別・会派・常任/特別/議運等 |
| 静岡市 | 静岡県 | (a) | https://www.city.shizuoka.lg.jp/gikai/p000237.html | 定数48 / 現員48相当 / 欠員表示なし | 要確認 | 中 | 区別名簿は葵区17・駿河区15・清水区16。50音・会派・委員会 |
| 浜松市 | 静岡県 | (a) | https://www.city.hamamatsu.shizuoka.jp/gikai/mokuji/ginshokai.html | 定数46 / 現員46相当 / 欠員表示なし | 要確認 | 中 | 50音・会派・委員会・選挙区別。顔写真PDFありだが写真は方針上使わない |
| 名古屋市 | 愛知県 | (a) | https://www.city.nagoya.jp/shikai/about/1030778/index.html | 定数68 / 現員68相当 / 欠員表示なし | 要確認 | 中 | 区別・議運・常任・特別・会派・50音。会議録は別に `ssp.kaigiroku.net` |
| 京都市 | 京都府 | (a) | https://www2.city.kyoto.lg.jp/shikai/meibo/index.html | 定数67 / 現員67相当 / 欠員表示なし | 要確認 | 中 | 定数67人がページに明記。選挙区別・五十音・会派・委員会 |
| 大阪市 | 大阪府 | (a) | https://www.city.osaka.lg.jp/shikai/category/3559-2-0-0-0-0-0-0-0-0.html | 定数81 / 現員81相当 / 欠員表示なし | 要確認 | 中 | 選挙区別・会派別・役員/委員別・議席表・各派名簿。カテゴリページから細目を辿る |
| 堺市 | 大阪府 | (a) | https://www.city.sakai.lg.jp/shigikai/meibo/index.html | 定数48 / 現員48相当 / 欠員表示なし | あり。注記で美原町議時代を含む | 中 | 選出区別ページに定数48と区別定数明記。50音・委員会・会派・選出区 |
| 神戸市 | 兵庫県 | (a) | https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/index.html | 定数65 / 現員65相当 / 欠員表示なし | 要確認 | 中 | 定数65と区別定数が本文に明記。区別・50音・会派・委員会 |
| 岡山市 | 岡山県 | (a) | https://www.city.okayama.jp/gikai/0000015787.html | 定数46 / 現員46相当 / 欠員表示なし | 要確認 | 中 | 50音順ページのタイトルに条例定数46人。会派別・委員会ページあり |
| 広島市 | 広島県 | (a) | https://www.city.hiroshima.lg.jp/gikai/giin-shoukai/index.html | 定数54 / 現員54相当 / 欠員表示なし | 要確認 | 中 | 議員紹介配下。会議録/中継は `hiroshima.gijiroku.com` だが名簿は公式HTML |
| 北九州市 | 福岡県 | (a) | https://www.city.kitakyushu.lg.jp/sigikai/menu11_0002.html | 定数57 / 現員57相当 / 欠員表示なし | 要確認 | 中 | 選挙区別・議員紹介一覧・会派別・委員会別 |
| 福岡市 | 福岡県 | (a) | https://gikai.city.fukuoka.lg.jp/member | 定数62 / 現員60 / 欠員2（早良区1・西区1） | 要確認 | 中 | WordPress/TablePress風。区別・会派別・委員会別。欠員2を本文で明記 |
| 熊本市 | 熊本県 | (a) | https://kumamoto-shigikai.jp/namelist/pub/default.aspx?c_id=3 | 定数48 / 現員48相当 / 欠員表示なし | 要確認 | 中 | 市本体から議会専用サイト `kumamoto-shigikai.jp` へ遷移。会派別・委員会別・50音・選出区別 |

## 3. 実装設計への示唆

### 第1候補パーサ

`municipal_official_multiview_roster`

想定入力:

- city_id
- main_url
- views:
  - 50音/全員一覧
  - 区別/選挙区別
  - 会派別
  - 委員会別
  - 議長・副議長/役員
- join_key:
  - 個別プロフィールURLがあればURLキー
  - 無い場合は氏名正規化+区名+会派の複合キー

### 既存資産の流用

- `single_page_roster` の正規化、氏名/かな分離、JSON出力契約、件数検算は流用可能。
- `gijiroku` / `gsl` / `pdf_member_roster` は政令市第1便では主役にならない。
- 千葉・広島など会議録ASPが見える市でも、名簿は公式HTML側を読む。

### 件数検算

第1便で必ず入れるべき検算:

- 条例定数または公式ページ定数と、実掲載数の一致。
- 欠員表示がある場合のみ不足を許容。
- 欠員表示が無い不足は停止。
- 区別名簿がある市は、区別定数と区別掲載数の照合。

今回の偵察で欠員表示を確認した市:

- 相模原市: 中央区に欠員1。
- 福岡市: 早良区・西区に各1欠員、計2。

### 個人情報リスク

政令市の名簿ページでは、少なくともフッターや議会事務局連絡先として電話・FAX・住所が頻出する。個別プロフィールに議員本人の連絡先が混在する可能性も都道府県より高い。

対策:

- ページ全体から正規表現で拾わず、許可リストのセル/項目だけ読む。
- `tel`, `email`, `address`, `birth`, `birthday`, `生年月日`, `住所`, `電話`, `メール` 系キーは生成しない。
- `check_personal_info.py` は必須。

## 4. 第1便の進め方案

最初の実装対象は、構造が比較的きれいで検算アンカーが明確な市を推奨。

1. 札幌市: 区別ページに氏名かな・会派・期数・委員会がまとまっており、定数も区別に明記。
2. 静岡市または堺市: 区別定数が明確で、市区町村型の行政区検算に向く。
3. 福岡市: WordPress/TablePress風 + 欠員あり。欠員処理の実証に向く。
4. 相模原市: WYSIWYG風 + 欠員あり。やや癖があるため、基底が固まってから。

20市を一括実装する場合でも、まず上記4市で `municipal_official_multiview_roster` の型を固めるのがよい。

## 5. 確認した公式URL一覧

- 札幌市議会: https://www.city.sapporo.jp/gikai/html/giin.html
- 仙台市議会: https://www.gikai.city.sendai.jp/list/index.html
- さいたま市議会: https://www.city.saitama.lg.jp/gikai/001/002/index.html
- 千葉市議会: https://www.city.chiba.jp/shigikai/meibo-menu.html
- 横浜市会: https://www.city.yokohama.lg.jp/shikai/giin/
- 川崎市議会: https://www.city.kawasaki.jp/shisei/category/40-3-0-0-0-0-0-0-0-0.html
- 相模原市議会: https://www.sagamihara-shigikai.jp/doc/2013122400014/
- 新潟市議会: https://www.city.niigata.lg.jp/shigikai/index_meibo/index.html
- 静岡市議会: https://www.city.shizuoka.lg.jp/gikai/p000237.html
- 浜松市議会: https://www.city.hamamatsu.shizuoka.jp/gikai/mokuji/ginshokai.html
- 名古屋市会: https://www.city.nagoya.jp/shikai/about/1030778/index.html
- 京都市会: https://www2.city.kyoto.lg.jp/shikai/meibo/index.html
- 大阪市会: https://www.city.osaka.lg.jp/shikai/category/3559-2-0-0-0-0-0-0-0-0.html
- 堺市議会: https://www.city.sakai.lg.jp/shigikai/meibo/index.html
- 神戸市会: https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/index.html
- 岡山市議会: https://www.city.okayama.jp/gikai/0000015787.html
- 広島市議会: https://www.city.hiroshima.lg.jp/gikai/giin-shoukai/index.html
- 北九州市議会: https://www.city.kitakyushu.lg.jp/sigikai/menu11_0002.html
- 福岡市議会: https://gikai.city.fukuoka.lg.jp/member
- 熊本市議会: https://kumamoto-shigikai.jp/namelist/pub/default.aspx?c_id=3
