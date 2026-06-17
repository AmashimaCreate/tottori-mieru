# 引き継ぎドキュメント

このリポジトリは、地方議会見える化サイトの静的フロントエンドと生成済みデータを管理する。

## 現状

- 公開先: https://seiji-mieru.com/tottori/
- ハブ統合: `seiji-mieru` リポジトリのビルドで、このリポジトリの `docs/` が `/tottori/` に配置される
- 配信元: Cloudflare Pages
- フロント: vanilla JS + CSS + 静的JSON
- データ生成: Python + requests + BeautifulSoup + 各種PDF/統計パーサ

## データモデル

- `councils.json`: 議会レジストリ。47都道府県議会 + 鳥取県内4市議会を扱う
- `docs/data/councils.json`: フロント配信用の同期データ
- `docs/data/{council_id}/members.json`: 議員名簿
- `docs/data/{council_id}/profile.json`: 基礎データ
- `docs/data/{council_id}/timeseries.json`: SSDS時系列
- `docs/data/{council_id}/votes.json`: 議決結果。議員別賛否がない議会は `result_only` または未収録
- `docs/data/{council_id}/finance.json`: 市区町村版の歳出内訳。都道府県版は未対応

## 重要な設計原則

- 議員個人を評価・序列化しない
- 政党イメージカラーを再現しない
- 賛否を緑/赤の善悪色にしない
- 住所・電話・メール・生年月日などの個人情報は、公式サイトに掲載されていても収集・掲載しない
- 個別ページのパースは許可リスト方式にする
- 議員写真は表示しない。`photo_url` は互換用に残すが、表示にも新規取得にも使わない
- 公式HTMLの表記がプレースホルダや欠員を含む場合は、議員として積まず `ketsuin` / `vacancy_details` に記録する

## 更新と検証

主な検証コマンド:

```bash
.venv/bin/python scripts/validate.py
.venv/bin/python scripts/check_personal_info.py docs/data
```

月次更新では、議員名簿・議決結果・profile/timeseriesを再生成し、変更がある場合のみコミットする。

## スクレイピング規約

- robots.txt を尊重
- User-Agent を設定
- `sleep(2)` 以上の間隔を維持
- 公式ページの連絡先・住所・生年月日等は読まない
- 件数検算アンカーを必ず持つ
- `teisu / genin / ketsuin` と `checks.vacancy_details` を整合させる

## ローカル確認

```bash
cd docs
python3 -m http.server 8765
```

ブラウザで `http://localhost:8765/` を開く。

## 代表的な作業フロー

1. 公式ページ・robots・件数アンカーを確認
2. 県別パーサまたは既存アダプタを実装
3. `members.json` を生成
4. `scripts/validate.py` と `scripts/check_personal_info.py` を通す
5. フロントで該当県ページ・議会ページ・議員ページを確認
6. 意味単位でコミット

## 参考資料

- `VISION.md`: 設計思想
- `scripts/validate.py`: データスキーマの実行可能な検証ルール
- `PROJECT_KNOWLEDGE.md`: ハブ統合を含む運用知見
- `research/`: ベンダー調査・地域別名簿調査
