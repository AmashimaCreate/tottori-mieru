# Data Schema

このディレクトリ配下のデータは、掲載議会を同じ形で扱うための共通スキーマに従う。

## 共通更新時刻

- `updated_at` は、データの実体が最後に変化した日時を表す。取得・生成ジョブを実行した日時そのものではない。
- 生成スクリプトは `updated_at` や `retrieved_at` などの時刻系フィールドを除いた実体を既存JSONと比較し、実体が同一ならファイルを書き換えない。
- SSDS時系列の `source.retrieved_at` も、ファイル内の実体が最後に変化した取得日時として扱う。取得ジョブが成功してもSSDS値が変わらない場合は据え置く。

## councils.json

リポジトリ直下の `councils.json` は、対応対象の議会レジストリである。

必須キー:

- `id`: `yonago-city` のような一意なID
- `name`: 表示名
- `type`: `prefecture` または `city`
- `prefecture`: URL階層用の都道府県slug。例: `tottori`
- `prefecture_name`: 都道府県の表示名。例: `鳥取県`
- `lg_code`: 総務省「全国地方公共団体コード」の6桁文字列
- `minutes_system`: `dbsr` / `kensakusystem` / `kensakusystem_legacy` / `unknown`
- `vote_granularity`: `member` / `faction` / `result_only` / `unknown`
- `status`: `active` / `planned`

任意キー:

- `minutes_base_url`: 会議録検索システムの議会別トップURL。
- `votes_official_url`: 議決結果または議員別賛否を確認できる公式ページURL。`vote_granularity` が `result_only` または `unknown` の議会では、フロントの縮退表示から公式確認へ誘導する。
- `official_links`: 公式情報への導線。`{"label": "...", "url": "https://..."}` の配列。議会公式サイト、政務活動費、議会日程、傍聴案内、会議録検索など、公式HTMLまたは調査済みのURLのみを載せる。不明な項目は推測で補わない。
- `notes`: 自動取得や公式導線に関する補足。

ルール:

- `lg_code` は議会固有のコードではなく、議会が属する自治体の全国地方公共団体コードを記録する。
- `lg_code` は e-Stat、総務省決算カード、自治体基礎データとの機械的JOINキーとして使う。
- コード確認元: 総務省「全国地方公共団体コード」 https://www.soumu.go.jp/denshijiti/code.html

## members.json

配置: `docs/data/{council_id}/members.json`

```json
{
  "council_id": "yonago-city",
  "updated_at": "2026-06-11T00:00:00+00:00",
  "source_url": "https://www.city.yonago.lg.jp/2919.htm",
  "acquisition": "scraping",
  "source_basis_date": "公式基準日記載なし",
  "last_verified": "2026-06-15",
  "teisu": 26,
  "genin": 26,
  "ketsuin": 0,
  "checks": {
    "anchor_type": "official_roster_count",
    "anchor_source_url": "https://www.city.yonago.lg.jp/2919.htm",
    "teisu": 26,
    "genin": 26,
    "ketsuin": 0,
    "vacancy_details": []
  },
  "members": [
    {
      "id": "yonago-city--adachi-takashi",
      "council_id": "yonago-city",
      "name": "安達 卓是",
      "name_kana": "あだち たかし",
      "district": "米子市",
      "faction": "信風",
      "elected_count": 3,
      "positions": ["総務政策副委員長"],
      "committees": ["総務政策", "基地問題等調査特別"],
      "photo_url": null,
      "official_profile_url": "https://... or null"
    }
  ]
}
```

必須キー:

- ルート: `council_id`, `updated_at`, `source_url`, `acquisition`, `source_basis_date`, `last_verified`, `teisu`, `genin`, `ketsuin`, `checks`, `members`
- 各議員: `id`, `council_id`, `name`, `name_kana`, `faction`, `elected_count`, `positions`, `committees`, `photo_url`

ルール:

- `acquisition` は `scraping` / `manual_transcription`。
- `id` は `{council_id}--{slug}` 形式。
- `positions` と `committees` は文字列配列。
- `source_basis_date`: 公式ページが掲げる基準日・任期。取得できない場合は `"公式基準日記載なし"` とし、推測で補わない。
- `last_verified`: 月次ジョブまたは手動確認で、件数検算に最後に成功した日付（`YYYY-MM-DD`）。
- `teisu`: 件数検算アンカーとして使う定数または公式名簿掲載現員数。
- `genin`: 公開 `members` 件数。
- `ketsuin`: `teisu - genin`。欠員位置を公式ページから識別できる場合は `checks.vacancy_details` に選挙区名・議席番号等を保持する。
- `checks.anchor_type`: 件数検算アンカーの種別。例: `official_district_capacity`, `official_roster_count`, `manual_official_roster_count`。
- `photo_url` は全議会で `null`。議員写真は表示・保存・ホットリンクしない。互換キーとして残すが、新規スクレイパーは写真URLを取得しない。
- 議員個別ページのパースは許可リスト方式とし、取得する項目を明示列挙する。
- 許可リスト外の項目は読まない。特に電話番号、メールアドレス、自宅住所、生年月日等の個人情報は、公式サイトに掲載されていても公開データへ取り込まない。

任意キー:

- `official_profile_url`: 議員本人の公式プロフィールページURL。URL文字列または `null`。値がある場合は、利用者が公式情報を自分で確認する動線としてフロントに表示する。
- `district`: 県議会など選挙区が公式名簿で公開されている場合の選挙区名。文字列または `null`。市議会など選挙区を持たない議会では省略可。

## manual members source

配置: `data_sources/members_manual/{council_id}.json`

robots.txt 等により自動取得しない議会の、人間転記用入力ファイル。

```json
{
  "council_id": "sakaiminato-city",
  "source_url": "https://...",
  "source_note": "KT が公式サイトの議員名簿ページを確認して転記",
  "members": [
    {
      "id": "sakaiminato-city--sample-taro",
      "council_id": "sakaiminato-city",
      "name": "境港 太郎",
      "name_kana": "さかいみなと たろう",
      "faction": null,
      "elected_count": null,
      "positions": [],
      "committees": [],
      "photo_url": null,
      "source_url": "https://..."
    }
  ]
}
```

ルール:

- ルートの `source_url` は転記元の議員名簿ページ。
- 各議員にも `source_url` を持たせる。個別ページがない場合はルートと同じ議員名簿ページURLを入れる。
- 生成される `docs/data/{council_id}/members.json` では、ルートに `acquisition: "manual_transcription"` を付与し、各議員の `source_url` は公開スキーマからは落とす。

## votes.json

配置: `docs/data/{council_id}/votes.json`

このフェーズでは定義のみ。データ生成は次フェーズ以降。

```json
{
  "council_id": "yonago-city",
  "updated_at": "2026-06-11T00:00:00+00:00",
  "acquisition": "scraping",
  "votes": [
    {
      "id": "yonago-city--令和8年3月定例会--bill-slug",
      "council_id": "yonago-city",
      "session": "令和8年3月定例会",
      "bill_no": "議案第1号",
      "bill_title": "議案第1号 ...",
      "date": "2026-03-25",
      "result": "可決",
      "committee_report": null,
      "granularity": "member",
      "votes_by_member": [
        {"member_id": "yonago-city--adachi-takashi", "vote": "賛成"}
      ],
      "votes_by_faction": null,
      "source_url": "https://..."
    }
  ]
}
```

必須キー:

- ルート: `council_id`, `updated_at`, `votes`
- 各議決: `id`, `council_id`, `session`, `bill_title`, `date`, `result`, `granularity`, `votes_by_member`, `votes_by_faction`, `source_url`

ルール:

- `acquisition` は `scraping` / `manual_transcription` / `manual_download`。未付与の既存データも当面は許容するが、新規生成では来歴を明示する。
- `granularity` は `member` / `faction` / `result_only`。
- `granularity` が `member` 以外の場合、`votes_by_member` は `null`。
- `granularity: result_only` は米子市議会や鳥取市議会のように、議員別賛否を安定して機械抽出できない議会向け。各議決は `bill_no`, `bill_title`, `date`, `result`, `source_url` を持ち、`votes_by_member` と `votes_by_faction` は `null` とする。
- `date` は `YYYY-MM-DD` または `null`。
- `committee_report` は任意。請願・陳情で委員長報告（採択 / 不採択 / 研究留保 等）がPDFにある場合のみ文字列で保持する。`bill_title` は件名セルのみとし、陳情事項本文や委員長報告を連結しない。
- `votes_by_member[].vote` は `賛成` / `反対` / `退席` / `欠席` / `議長` / `除斥` / `継続審査` のいずれか。
- `議長` は慣例により採決に加わらない議長席を表す。賛否の意思表示として扱わない。
- `除斥` は地方自治法上の利害関係等により議事から除かれた状態を表す。フロントでは「利害関係があるため採決から外れた状態」のように平易な注記を添える。
- `継続審査` はPDF上の `△` 等、議員セルに継続審査として記録された値を表す。結果欄の文言を議員セルへ混入させない。
- `votes_by_member[].member_name` は、`member_id` が `null` の場合もPDF上の投票者名を保持するためのフィールド。`speeches.json` の `speaker_label` と同じく、現名簿外の人物や表記揺れを後から確認できるように残す。

## profile source input

配置: `data_sources/profiles/{council_id}.json`

自治体基礎データの一次入力ファイル。人間が公式サイト、e-Stat、総務省決算カード等の一次ソースから確認・転記した値を正とし、ビルダーが検証と派生値計算を行う。

```json
{
  "council_id": "yonago-city",
  "population": {
    "value": 142472,
    "as_of": "2026-05-31",
    "source_name": "米子市 人口と世帯数（住民基本台帳）",
    "source_url": "https://www.city.yonago.lg.jp/9498.htm"
  },
  "households": null,
  "budget_general_yen": null,
  "fiscal_index": null,
  "aging_rate_pct": null,
  "local_debt_yen": null,
  "member_salary_monthly_yen": null
}
```

必須キー:

- ルート: `council_id`, `population`, `households`, `budget_general_yen`, `fiscal_index`, `aging_rate_pct`, `local_debt_yen`, `member_salary_monthly_yen`

ルール:

- 未調査・取得不能の項目は `null`。
- 値がある項目はオブジェクトとし、`value` と `source_url` を必須とする。
- `source_url` は `https://` で始まるURL。
- `population`, `households`, `budget_general_yen`, `local_debt_yen`, `member_salary_monthly_yen` は整数値。
- `fiscal_index`, `aging_rate_pct` は数値。
- `population` は `0` より大きい値。
- 時点を持つ項目は `as_of`、会計年度を持つ項目は `fiscal_year` を付ける。

## profile.json

配置: `docs/data/{council_id}/profile.json`

`data_sources/profiles/{council_id}.json` から生成される公開用データ。入力ファイルの内容に `per_capita` と `updated_at` を加える。`updated_at` は実体が変わった場合のみ更新する。

```json
{
  "council_id": "yonago-city",
  "population": {"value": 142472, "as_of": "2026-05-31", "source_url": "https://..."},
  "households": null,
  "budget_general_yen": null,
  "fiscal_index": null,
  "aging_rate_pct": null,
  "local_debt_yen": null,
  "member_salary_monthly_yen": null,
  "per_capita": {
    "population_per_member": 5479.7,
    "budget_per_capita_yen": 620894,
    "debt_per_capita_yen": 404290
  },
  "updated_at": "2026-06-11T00:00:00+00:00"
}
```

必須キー:

- ルート: `council_id`, `population`, `households`, `budget_general_yen`, `fiscal_index`, `aging_rate_pct`, `local_debt_yen`, `member_salary_monthly_yen`, `per_capita`, `updated_at`
- `per_capita`: `population_per_member`, `budget_per_capita_yen`, `debt_per_capita_yen`

派生値:

- `population_per_member`: 人口 ÷ 議員数。議員数は `docs/data/{council_id}/members.json` の `members` 件数から算出し、ファイルがない場合は `null`。
- `budget_per_capita_yen`: 一般会計予算 ÷ 人口。
- `debt_per_capita_yen`: 地方債残高 ÷ 人口。
- 必要な入力が `null` の場合、派生値は `null`。

## timeseries.json

配置: `docs/data/{council_id}/timeseries.json`

SSDS（e-Stat 社会・人口統計体系）から生成する、自治体ごとの過去時系列データ。profileは最新公表値のスナップショット、timeseriesは確定統計に基づく履歴系列として分けて扱う。

必須キー:

- ルート: `council_id`, `updated_at`, `source`, `indicators`
- `source`: `provider`, `api`, `retrieved_at`, `area_code`, `statsDataIds`, `note`
- 各指標: `label`, `unit`, `ssds_item`, `year_start`, `year_end`, `first`, `latest`, `delta`, `delta_pct`, `values`
- `values[]`: `year`, `value`

指標:

- `population_total`: 住民基本台帳人口（総数）
- `aging_rate`: 高齢化率。`elderly_population / population_total * 100`。表用に `young_population`, `working_age_population`, `elderly_population` も保持する。
- `births`: 出生数
- `social_change`: 社会増減。`in_migration - out_migration`。表用に `in_migration`, `out_migration` も保持する。
- `expenditure_total`: 歳出決算総額。SSDSの千円単位値を円に換算して保持する。
- `fiscal_index`: 財政力指数
- `pref_assembly_turnout`: 都道府県議会議員選挙投票率。都道府県表のみの任意指標で、県議会ページにだけ保持する。
- `pref_governor_turnout`: 都道府県知事選挙投票率。都道府県表のみの任意指標で、県議会ページにだけ保持する。

ルール:

- `population_total` は SSDS `A2301_住民基本台帳人口（総数）`。
- `aging_rate` は SSDS `A1301_年少人口`, `A1302_生産年齢人口`, `A1303_老年人口` から算出する。国勢調査年のみの系列は補間しない。
- `births` は SSDS `A4101_出生数`。
- `social_change` は SSDS `A5103_転入者数` と `A5104_転出者数` から算出する。
- `expenditure_total` は都道府県が `D3103_歳出決算総額（都道府県財政）`、市区町村が `D3203_歳出決算総額（市町村財政）`。SSDSの千円単位値を円に換算して保持する。
- `fiscal_index` は都道府県が `D2101_財政力指数（都道府県財政）`、市区町村が `D2201_財政力指数（市町村財政）`。
- `pref_assembly_turnout` は都道府県表 SSDS `G6305_都道府県議会議員選挙投票率`。市区町村別投票率ではないため4市には出力しない。
- `pref_governor_turnout` は都道府県表 SSDS `G6306_都道府県知事選挙投票率`。市区町村別投票率ではないため4市には出力しない。
- 各指標は5議会で揃う直近最大10点を採用する。SSDSの収録最新年は指標ごとに異なるため、指標間で `year_start` / `year_end` が異なってよい。
- 県限定の任意指標は、対象範囲内で取得できる直近最大10点を採用する。選挙年のみ値があるため、年が連続しなくてよい。
- `values` は2〜10点。年齢3区分のように毎年値がない系列は、取得できた年のみを保持する。
- `first` / `latest` は表示対象期間の先頭・末尾の `year` と `value` を保持する。`latest.year` はフロントで各指標カードの基準年として明示する。
- 投票率など選挙年のみ値が存在する指標は、毎年値があるように見せない。無投票区がある場合は区ごとの投票率が存在しないため、フロントで基準年と注意書きを併記する。
- `delta` は `latest.value - first.value`。増減の事実表示に使う派生値で、良し悪しの評価ではない。
- `delta_pct` は `delta / first.value * 100` を小数第2位で丸めた値。先頭値が0の場合は `null`。
- `value` は数値型。人口総数と出生数は整数、財政力指数は小数を許容する。
- `source.statsDataIds` には、各指標で実際に問い合わせたSSDS表IDを保持する。
- appIdは実行環境の `.env` または環境変数でのみ扱い、`timeseries.json` には保存しない。

注記:

- SSDSは確定統計のため、最新公表値より1〜3年遅れることがある。
- `profile.json` は自治体公式ページや決算カード等の最新公表値を優先するため、`timeseries.json` と出典・年次が異なる。
- フロントで両者を併用する場合、`profile.json` は現在値、`timeseries.json` は履歴推移として表示する。

## finance.json

配置: `docs/data/{council_id}/finance.json`

デジタル庁/総務省の地方財政データから生成する、市区町村の決算歳出内訳データ。鳥取県議会は都道府県版データ未公開のため、このフェーズでは4市のみ保持する。

```json
{
  "council_id": "yonago-city",
  "updated_at": "2026-04-24T00:00:00+09:00",
  "fiscal_year": 2024,
  "municipal_code": "31202",
  "lg_code": "312029",
  "municipality_name": "米子市",
  "similar_group": "一般市Ⅲ－３",
  "population": {"value": 144056, "source": "finance_data_table_master.csv 人口数_人"},
  "source": {
    "name": "総務省「地方財政状況調査」/ デジタル庁 地方財政データ",
    "dataset": "20260424_resources_municipal-finance",
    "fiscal_year": 2024,
    "license": "CC BY 4.0相当",
    "note": "手元の配布ZIPから生成。金額の生値は千円。"
  },
  "expenditure": {
    "purpose": {
      "classification": "歳出 (目的)",
      "total_thousand_yen": 87579776,
      "total_yen": 87579776000,
      "items": [
        {
          "label": "民生費",
          "amount_thousand_yen": 32057600,
          "amount_yen": 32057600000,
          "amount_oku_yen": 320.576,
          "share_pct": 36.604,
          "per_capita_yen": 222536,
          "similar_group_average_per_capita_yen": 215096,
          "similar_group_average_n": 62
        }
      ]
    },
    "nature": {
      "classification": "歳出 (性質)",
      "total_thousand_yen": 71209232,
      "total_yen": 71209232000,
      "items": []
    }
  }
}
```

必須キー:

- ルート: `council_id`, `updated_at`, `fiscal_year`, `municipal_code`, `lg_code`, `municipality_name`, `similar_group`, `population`, `source`, `checks`, `similar_group_indicators`, `expenditure`
- `source`: `name`, `dataset`, `fiscal_year`, `license`, `note`, `files`
- `expenditure`: `purpose`, `nature`
- `expenditure.{purpose,nature}`: `classification`, `total_thousand_yen`, `total_yen`, `items`
- `items[]`: `label`, `amount_thousand_yen`, `amount_yen`, `amount_oku_yen`, `share_pct`, `per_capita_yen`, `similar_group_average_per_capita_yen`, `similar_group_average_n`

ルール:

- `municipal_code` は地方財政データ側の5桁市区町村コード。例: 鳥取市 `31201`。
- `lg_code` は `councils.json` の6桁全国地方公共団体コード。例: 鳥取市 `312011`。
- ビルダーは `lg_code` の先頭5桁が `municipal_code` と一致することを検証する。6桁目はチェックディジットのため、地方財政データ側の5桁コードとは桁数が異なる。
- CSVの生値は `値_千円`。`amount_yen` と `total_yen` は `千円 * 1000`、`amount_oku_yen` は `千円 / 100000` で算出する。
- `purpose` は `分類: 歳出 (目的)` を `大項目` ごとに合算する。表示の主役として使う。
- `nature` は `分類: 歳出 (性質)` を `大項目` ごとに合算する。補助情報として折りたたみ表示に使う。
- `share_pct` は各分類内の構成比。丸め後の合計は概ね100%。
- `per_capita_yen` は `amount_yen / finance.population.value`。市民の負担額ではなく、歳出を人口で割った参考値。
- `similar_group_average_per_capita_yen` は同一配布データ内の `master` で同じ `similar_group` に属する自治体について、同一費目の1人あたり歳出を平均した参考値。配布 `groups.csv` に費目別平均がないため、費目別比較は `flow + master` から算出する。
- `similar_group_average_n` はその費目の類似団体平均の算出に使った自治体数。表示では「N市平均」として併記し、母集団の大きさを利用者に示す。
- `source.license` は配布元の表記に従い、フロントでは出典とともに表示する。

注記:

- `profile.json` の `budget_general_yen` は予算（計画）、`finance.json` は決算（実際に使われたお金）であり、同じ金額にはならない。
- `timeseries.json` の `expenditure_total` はSSDSの過去年次系列であり、`finance.json` の2024年度決算とは年次が異なる場合がある。

## speeches.json

配置: `docs/data/{council_id}/speeches.json`

このフェーズでは定義のみ。データ生成は次フェーズ以降。

```json
{
  "council_id": "yonago-city",
  "updated_at": "2026-06-11T00:00:00+00:00",
  "coverage": {
    "scope": "本会議・議員発言者(speaker1)のみ",
    "excluded": ["議長の議事進行発言", "市長・執行部の発言(member_id: null扱い)"],
    "note": "議長は慣例により一般質問を行わないため発言数が少なく/ゼロに見える場合がある",
    "source_url_note": "個別発言への直接リンクは本システムの仕様上提供不可。source_url は会議録検索入口。"
  },
  "speeches": [
    {
      "id": "yonago-city--2026-03-10--0001",
      "member_id": "yonago-city--adachi-takashi",
      "speaker_label": "安達議員",
      "meeting_name": "令和8年3月定例会 本会議",
      "date": "2026-03-10",
      "kind": "一般質問",
      "summary": null,
      "source_url": "https://..."
    }
  ]
}
```

必須キー:

- ルート: `council_id`, `updated_at`, `coverage`, `speeches`
- `coverage`: `scope`, `excluded`, `note`, `source_url_note`
- 各発言: `id`, `member_id`, `speaker_label`, `meeting_name`, `date`, `kind`, `summary`, `source_url`

ルール:

- `member_id` は `{council_id}--{slug}`、または議員特定不能時は `null`。
- `speaker_label` は会議録検索システム上の発言者表記。`member_id` が `null` の場合も表記揺れや過去議員の検出に使うため保持する。
- `summary` はAI要約が未生成の場合 `null`。
- `coverage` は取得範囲と構造的な欠落を説明する。フロントエンドでは、議長や執行部の発言が対象外であることを表示に利用する。
- `source_url` は永続性を優先し、会議録検索入口URLを保存する。旧系統の `Code` 付き検索URLや `ResultFrame.exe` URLは直接リンクとして永続利用しない。
