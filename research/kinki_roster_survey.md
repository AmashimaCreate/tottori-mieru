# 近畿7府県 県議会議員名簿 様式調査

調査日: 2026-06-16  
対象: 三重県・滋賀県・京都府・大阪府・兵庫県・奈良県・和歌山県  
目的: 全国展開に向け、県議会議員名簿の様式と既存アダプタ流用可否を実装前に確認する。

## 前提

この調査では近畿を広めに取り、三重県も含めた。将来の地方区分表示で三重県を東海側に寄せる場合でも、データ実装上の調査結果はそのまま使える。

議員写真は全議会で表示・取得しない方針が確定済みのため、各公式ページに写真が存在しても `photo_url` は取得対象外とする。調査の中心は、氏名・ふりがな・会派・選挙区・当選回数・公式プロフィールURLの取得可否である。

## 結論

近畿7府県は、既存の1型だけでは吸収できない。ただし、完全にバラバラでもなく、次の5系統に整理できる。

| 系統 | 県府 | 見立て |
| --- | --- | --- |
| g07系名簿システム | 滋賀 | 既存 `gijiroku_member_roster.py` 系を流用しやすい。CP932/連絡先混在に注意。 |
| 単一HTML表型 | 兵庫・奈良 | 1ページの表だけで主要項目が揃う。`single_page_roster.py` 系の拡張候補。 |
| 静的一覧 + 個別プロフィール型 | 京都 | 50音順一覧から個別プロフィールへ。既存 `static_member_profile.py` に近い。 |
| 連絡先混在の1ページ/地区別表型 | 三重・和歌山 | 住所・電話が同じ表に混在。許可リスト方式の専用寄りパースが安全。 |
| 大阪すがたみ型 | 大阪 | `すがたみ` の選挙区/50音表と会派別ページを使う。大阪固有パーサが必要。 |

実装順のおすすめは、まず **兵庫・奈良**。どちらも1ページ表から主要項目が取れ、欠員/現員の検算もしやすい。次に **京都**、その後に **滋賀**。三重・和歌山・大阪は連絡先混在や表構造の癖が強いので、やや後回しが安全。

## サマリーマトリクス

| 府県 | 名簿URL | 様式分類 | 取得可能項目 | robots / 制約 | 既存アダプタ流用 |
| --- | --- | --- | --- | --- | --- |
| 三重 | https://www.pref.mie.lg.jp/KENGIKAI/08096011310.htm | 選挙区別ページ集約型。各選挙区ページ内に複数議員の表。 | 氏名、ふりがな、会派、委員会、選挙区、公式プロフィールURL相当(議員サイト欄)。当選回数は見当たらず。 | robots.txt あり。名簿配下は禁止なし。表に住所・電話が混在。 | そのまま流用は難しい。`district_aggregate_profile` 派生または三重専用。 |
| 滋賀 | https://www.shigaken-gikai.jp/g07_giinlistP.asp | g07系名簿システム。五十音順/選挙区別HTML表 + 個別ページ。 | 氏名、ふりがな、会派、選挙区、当選回数、公式プロフィールURL。 | robots.txt は `gikai/cgi` 等をDisallow。`g07_...` 名簿は明示禁止外。表に住所・電話等の行があるため許可リスト必須。 | 既存 `gijiroku_member_roster.py` 系の有力候補。 |
| 京都 | https://www.pref.kyoto.jp/gikai/shokai/50on.html | 静的50音一覧 + 個別プロフィール。選挙区ページにも一覧あり。 | 氏名、ふりがな、会派、選挙区、当選回数、委員会、公式プロフィールURL。 | robots.txt は404。明示禁止なし扱い。個別ページに住所・生年月日が混在するため許可リスト必須。 | `static_member_profile.py` に近い。 |
| 大阪 | https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index50.html | `第20期大阪府議会議員すがたみ` 型。50音/選挙区表 + 会派別ページ。 | 氏名、ふりがな、会派、選挙区、公式プロフィールURL。個別ページ追跡で追加項目の余地あり。当選回数は一覧表では見当たらず。 | robots.txt は404。明示禁止なし扱い。連絡先一覧ページは使わない。 | 新規の大阪専用に近いパーサが安全。 |
| 兵庫 | https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/50on/50on_ichiran23.html | 単一HTML表型 + 個別プロフィール。 | 氏名、ふりがな、会派、選挙区、当選回数、公式プロフィールURL。 | robots.txt は404。公式トップで旧 `hyogokengikai.jp` は無関係サイト化している注意喚起あり。個別ページには住所欄あり。 | `single_page_roster.py` 系の拡張候補。 |
| 奈良 | https://www.pref.nara.lg.jp/n161/52534.html | 単一HTML表型。五十音順表で主要項目が揃う。 | 氏名、ふりがな、会派、選挙区、当選回数、公式プロフィールURL。 | robots.txt は `Disallow: /documents/22137/*` のみ。名簿HTMLは禁止外。異体字は別ページで注意書きあり。 | `single_page_roster.py` 系の拡張候補。 |
| 和歌山 | https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213187.html | 1ページWYSIWYG表型。選挙区別/50音順/会派別。 | 氏名、会派、選挙区、当選回数、公式プロフィールURL。ふりがなは名前セル内から一部取得可能。 | robots.txt は404。表に住所・電話が混在。写真・連絡先は取得対象外。 | 佐賀型に近いが表構造は別。和歌山専用寄りが安全。 |

## 県府別詳細

### 三重県議会

- 公式入口: https://www.pref.mie.lg.jp/KENGIKAI/
- 議員紹介: https://www.pref.mie.lg.jp/KENGIKAI/89263000001_00001.htm
- 選挙区別名簿: https://www.pref.mie.lg.jp/KENGIKAI/08096011310.htm
- 選挙区ページ例(津市): https://www.pref.mie.lg.jp/KENGIKAI/08109011323.htm
- 様式:
  - 選挙区別名簿から15選挙区ページへ遷移。
  - 選挙区ページ内に複数議員の表が並ぶ。
  - 例: 津市ページは「津市（定数7） 50音順（令和8年5月19日現在）」。
- 取得可能:
  - 氏名、ふりがな、会派、所属委員会、選挙区。
  - 議員個人サイトURLの欄があるが、公式プロフィールURLではなく外部サイトの場合がある。
  - 当選回数は確認できず。
- 注意:
  - 同じ表内に連絡先住所・電話番号が混在。取得は許可リスト方式必須。
  - 写真は名簿表には確認できず、写真全廃方針とも整合。
- robots:
  - `https://www.pref.mie.lg.jp/robots.txt` は200。
  - `User-agent: *` では特定PDFのみDisallow。名簿HTMLは禁止外。
- アダプタ見立て:
  - `district_aggregate_profile` に近いが、住所・電話混在と外部URL欄の扱いが癖。
  - まず三重専用で書き、他県に同型が出たら抽象化が安全。

### 滋賀県議会

- 公式入口: https://www.shigaken-gikai.jp/
- 五十音順名簿: https://www.shigaken-gikai.jp/g07_giinlistP.asp
- 選挙区別名簿: https://www.shigaken-gikai.jp/g07_giinlist_senkyoku.asp
- 個別プロフィール例: https://www.shigaken-gikai.jp/g07_giinlistS.asp?SrchID=188
- 様式:
  - g07系の議員名簿ページ。
  - 五十音順ページは2行構成の表で、写真リンク、氏名、かな、当選回数、会派、選挙区がまとまる。
  - 2行目に住所・電話・FAX等がある。
- 取得可能:
  - 氏名、ふりがな、会派、選挙区、当選回数、公式プロフィールURL。
  - 写真URLは存在するが取得しない。
- 件数:
  - 五十音順名簿のプロフィールリンクは41件。
  - 実装時は公式定数との差を欠員として扱う検算が必要。
- robots:
  - `https://www.shigaken-gikai.jp/robots.txt` は200。
  - 一部Bot禁止と、`/voices/cgi/`, `/voices2/cgi/`, `/gikai/cgi/`, `g07_Video_View.asp` がDisallow。
  - 名簿HTML `g07_giinlistP.asp` / `g07_giinlistS.asp` は明示禁止外。
- アダプタ見立て:
  - 既存 `gijiroku_member_roster.py` 系を拡張して流用できる可能性が高い。
  - CP932デコードと住所・電話の除外を確認する。

### 京都府議会

- 公式入口: https://www.pref.kyoto.jp/gikai/
- 議員紹介: https://www.pref.kyoto.jp/gikai/shokai/index.html
- 50音順名簿: https://www.pref.kyoto.jp/gikai/shokai/50on.html
- 選挙区別名簿: https://www.pref.kyoto.jp/gikai/shokai/senkyoku/index.html
- 個別プロフィール例: https://www.pref.kyoto.jp/gikai/shokai/senkyoku/kita/02.html
- 様式:
  - 50音順一覧から個別プロフィールへ直接リンク。
  - 選挙区ページにも議員リストがある。
  - 個別プロフィールはHTML表。
- 取得可能:
  - 氏名、ふりがな、選挙区、当選回数、会派、委員会、公式プロフィールURL。
  - 写真URLは存在するが取得しない。
- 件数:
  - 50音順名簿の議員リンクは59件。
- 注意:
  - 個別ページに住所・生年月日がある。許可リスト方式必須。
- robots:
  - `https://www.pref.kyoto.jp/robots.txt` は404。明示禁止なし扱い。
- アダプタ見立て:
  - `static_member_profile.py` に近い。
  - 個別ページ追跡が必要だが、県固有設定で吸収できる範囲に見える。

### 大阪府議会

- 公式入口: https://www.pref.osaka.lg.jp/gikai/
- 議員情報: https://www.pref.osaka.lg.jp/gikai/giinjouhou/index.html
- すがたみ入口: https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index.html
- すがたみ50音順: https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index50.html
- すがたみ選挙区別: https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index_senkyoku.html
- 最新会派別ページ例: https://www.pref.osaka.lg.jp/o170010/gikai_giji/giininfo/0806giin.html
- 様式:
  - `第20期大阪府議会議員すがたみ` 配下に50音順/選挙区別/個別ページ。
  - 会派別ページは会期ごとに別URLで、最新は令和8年6月定例会。
  - 50音順表は氏名・かな・会派略称・選挙区が取れる。
- 取得可能:
  - 氏名、ふりがな、会派、選挙区、公式プロフィールURL。
  - 当選回数は一覧表では確認できず。個別ページ追跡で取れるかは追加確認が必要。
- 件数:
  - すがたみ50音順の議員リンクは79件。
- robots:
  - `https://www.pref.osaka.lg.jp/robots.txt` は404。明示禁止なし扱い。
- 注意:
  - 議員連絡先一覧は住所・電話主体なので使わない。
  - 会派略称と正式会派名の対応が必要。
- アダプタ見立て:
  - 大阪専用パーサが安全。
  - `index50.html` を主、必要なら最新会派別ページを補助データとしてJOINする。

### 兵庫県議会

- 公式入口: https://web.pref.hyogo.lg.jp/gikai/
- 議員紹介: https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/index.html
- 五十音別一覧表: https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/50on/50on_ichiran23.html
- 選挙区別一覧表: https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/senkyokubetsu/senkyo_ichiran.html
- 個別プロフィール例: https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/50on/a/aoyama.html
- 様式:
  - 五十音別一覧表が1ページのHTML表。
  - 氏名リンク、よみがな、選挙区名、当選回数、会派が揃う。
  - 個別プロフィールには選挙区、当選回数、会派、略歴、住所等がある。
- 取得可能:
  - 一覧だけで氏名、ふりがな、選挙区、当選回数、会派、公式プロフィールURL。
  - 委員会は別ページ追跡が必要なため初回は不要。
- 件数:
  - 議員紹介ページに「議員定数86人（現員82人、欠員4人）」と明記。
  - 五十音別一覧表の議員リンクも82件。
- robots:
  - `https://web.pref.hyogo.lg.jp/robots.txt` は404。明示禁止なし扱い。
- 注意:
  - 古い `hyogokengikai.jp` / `www.hyogokengikai.jp` は無関係サイト化している。必ず `web.pref.hyogo.lg.jp/gikai/` を使う。
- アダプタ見立て:
  - `single_page_roster.py` 系を拡張すれば対応しやすい。

### 奈良県議会

- 公式入口: https://www.pref.nara.lg.jp/n161/1690.html
- 五十音順名簿: https://www.pref.nara.lg.jp/n161/52534.html
- 選挙区別名簿: https://www.pref.nara.lg.jp/n161/18534.html
- 会派別名簿: https://www.pref.nara.lg.jp/n161/52790.html
- 議員氏名等の正確な表記: https://www.pref.nara.lg.jp/n161/p114004.html
- 様式:
  - 五十音順名簿が1ページのHTML表。
  - 氏名リンク、ふりがな、選挙区、当選回数、会派が揃う。
  - 選挙区別名簿には欠員行と定数/現員の記載がある。
- 取得可能:
  - 氏名、ふりがな、選挙区、当選回数、会派、公式プロフィールURL。
- 件数:
  - 選挙区別名簿に「定数43名（現員40名）」と明記。
  - 名簿PDFは令和8年4月24日現在。
- robots:
  - `https://www.pref.nara.lg.jp/robots.txt` は200。
  - `Disallow: /documents/22137/*` のみ。名簿HTMLは禁止外。
- 注意:
  - 旧 `https://www.pref.nara.jp/dd_aspx_menuid-1690.htm` は `https://www.pref.nara.lg.jp/` トップへ301される。使わない。
  - 「議員氏名等の正確な表記」ページで、西川均・芦高清友の正確な表記は画像提示。HTML上は代替表記なので、実装時はそのまま文字列を採用し、必要なら注記。
- アダプタ見立て:
  - `single_page_roster.py` 系の有力候補。
  - 欠員検算がしやすい。

### 和歌山県議会

- 公式入口: https://www.pref.wakayama.lg.jp/prefg/200100/cms/www/index.html
- 議員紹介入口: https://www.pref.wakayama.lg.jp/prefg/200100/cms/koumoku/d00155189.html
- 選挙区別名簿: https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213187.html
- 50音順名簿: https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213193.html
- 会派別名簿: https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00154525.html
- 様式:
  - 1ページWYSIWYG表型。
  - 選挙区別名簿に、写真、名前、住所、電話番号、会派、当選回数が同居。
  - 議員名リンクから個別紹介ページへ移動できる。
- 取得可能:
  - 氏名、会派、選挙区、当選回数、公式プロフィールURL。
  - ふりがなは名前セル内にある場合があるが、行によって揺れがあるため要検証。
- 件数:
  - 50音順名簿に「議員定数42人（任期は令和5年4月30日から令和9年4月29日まで）」。
  - 令和8年5月13日現在。
  - 選挙区別名簿には欠員行あり。
- robots:
  - `https://www.pref.wakayama.lg.jp/robots.txt` は404。明示禁止なし扱い。
- 注意:
  - 表に住所・電話番号が強く混在するため、許可リスト方式必須。
  - 旧 `https://www.pref.wakayama.lg.jp/prefg/200100/www/html/index.html` は404。現行は `/prefg/200100/cms/www/index.html`。
- アダプタ見立て:
  - 佐賀のWYSIWYG表型に近いが列構造は別。
  - 和歌山専用寄りの単一ページ表パーサが安全。

## 実装優先度案

1. 兵庫・奈良
   - 1ページ表で主要項目が取れる。
   - 欠員/現員の検算が明確。
   - 写真全廃方針とも相性がよい。
2. 京都
   - 既存 `static_member_profile.py` と近い。
   - 個別ページに住所・生年月日があるため、許可リスト方式を再確認。
3. 滋賀
   - g07系で既存資産を使えそう。
   - CP932と連絡先混在の除外を丁寧に見る。
4. 三重・和歌山・大阪
   - いずれも表構造や補助ページJOINがやや面倒。
   - 三重・和歌山は連絡先混在、大阪は会派略称/正式名の対応が要点。

## 実装時の共通注意

- 写真は取得しない。既存方針どおり `photo_url: null`。
- 住所・電話・FAX・メール・生年月日は、公式ページにあっても取得しない。
- 表パースは列名・見出しを基準にした許可リスト方式にする。
- 欠員が明記されている県府は、定数と現員の二段検算を行う。
- 古いドメイン/旧CMS URLが検索結果に残っている県があるため、実装時も公式トップからの導線を優先する。
