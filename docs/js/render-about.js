import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderAbout(root) {
  root.innerHTML = "";
  root.append(
    el("section", { class: "about-page page-card" }, [
      el("h2", { class: "section-title" }, "このサイトについて"),
      el("div", { class: "about-lead" }, [
        el("p", {}, "自治体や議会が公開している情報を、市民が見つけやすい形に並べ直す非公式サイトです。"),
        el("p", {}, "議員名簿、発言インデックス、議決結果、街の基礎データを、自治体をまたいで同じ形で見られるようにします。"),
        el("p", {}, "評価や順位づけではなく、一次ソースへたどる入口を増やすことを目的にしています。"),
      ]),
    ]),
    el("section", { class: "about-page page-card" }, [
      el("h2", { class: "section-title" }, "中立性の考え方"),
      el("ul", { class: "about-list" }, [
        el("li", {}, "議員個人を点数化・ランキング化しません。発言数や賛否の件数は、取得範囲内の事実として表示します。"),
        el("li", {}, "会派や指標の色は区別のために使います。特定政党のイメージカラーを再現する意図はありません。"),
        el("li", {}, "賛成・反対は記号とティール/オレンジ系で表示し、緑/赤の善悪を連想しやすい配色は使いません。"),
        el("li", {}, "平均・比較・増減は、地域の状況を知るための事実として表示します。良し悪しの断定はしません。"),
      ]),
    ]),
    el("section", { class: "about-page page-card" }, [
      el("h2", { class: "section-title" }, "データの出典・取得方法・更新頻度"),
      el("ul", { class: "about-list" }, [
        el("li", {}, "更新頻度: GitHub Actions により月1回の自動更新を基本とし、手作業確認が必要なデータは随時反映します。"),
        el("li", {}, "議員名簿: 各議会の公式名簿ページを取得し、構造化できる範囲をJSON化しています。自動取得が安定しないものは手動入力JSONを併用します。"),
        el("li", {}, "発言インデックス: 会議録検索システムから、本会議での議員発言者・会議名・日付を対象に取得しています。"),
        el("li", {}, "議決結果: 公式の議決結果ページまたはPDFから、議案名・議決日・結果・賛否を取得できる範囲で抽出しています。"),
        el("li", {}, "街の基礎データ: 自治体公式資料、決算カード、政府統計の総合窓口(e-Stat)社会・人口統計体系などから取得しています。"),
        el("li", {}, "確認処理: データ生成後にスキーマ検証、公式リンク確認、掲載対象外の個人情報検出を実行しています。"),
      ]),
    ]),
    el("section", { class: "about-page page-card" }, [
      el("h2", { class: "section-title" }, "出典・クレジット"),
      el("ul", { class: "about-list" }, [
        el("li", {}, "議員名簿・議決結果・会議録: 各議会、各自治体、会議録検索システムの公開情報を出典としています。"),
        el("li", {}, [
          "統計データ: ",
          el("a", {
            href: "https://www.e-stat.go.jp/",
            target: "_blank",
            rel: "noopener",
          }, "政府統計の総合窓口(e-Stat)"),
          " 社会・人口統計体系を利用しています。",
        ]),
        el("li", {}, [
          "日本地図: ",
          el("a", {
            href: "https://github.com/geolonia/japanese-prefectures",
            target: "_blank",
            rel: "noopener",
          }, "geolonia/japanese-prefectures"),
          " (GFDL)",
        ]),
        el("li", {}, [
          "鳥取県市町村地図: ",
          el("a", {
            href: "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html",
            target: "_blank",
            rel: "noopener",
          }, "国土数値情報 行政区域データ"),
          " (PDL1.0)",
        ]),
      ]),
    ]),
    el("section", { class: "about-page page-card" }, [
      el("h2", { class: "section-title" }, "運営者・問い合わせ"),
      el("p", { class: "muted" }, "このサイトは非公式・個人運営です。正確な情報は公式発表を優先してください。"),
      el("p", {}, [
        "内容の訂正・削除のご依頼、不具合のご報告はこちら → ",
        el("a", {
          href: "https://forms.gle/YiggPHVqdPViAdHRA",
          target: "_blank",
          rel: "noopener",
        }, "Googleフォーム"),
      ]),
    ]),
  );
}
