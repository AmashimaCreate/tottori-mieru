import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderAbout(root) {
  root.innerHTML = "";
  root.append(
    el("section", { class: "info-hero page-card" }, [
      el("p", { class: "eyebrow" }, "このサイトについて"),
      el("h2", { class: "section-title" }, "公開情報へたどりやすくする入口です"),
      el("p", { class: "info-lead" }, "議員名簿、議決結果、地域データを整理し、公式情報を確認しやすくします。評価や順位づけはしません。"),
    ]),
    el("div", { class: "info-grid" }, [
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "表示の方針"),
        el("ul", { class: "info-list" }, [
          el("li", {}, "議員個人を点数化・ランキング化しません。"),
          el("li", {}, "会派や指標の色は区別のために使います。"),
          el("li", {}, "賛成・反対は記号を主にし、色は補助にします。"),
          el("li", {}, "比較や増減は事実として表示し、良し悪しは断定しません。"),
        ]),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "データと更新"),
        el("ul", { class: "info-list" }, [
          el("li", {}, "月1回の自動更新を基本にしています。"),
          el("li", {}, "議員名簿は公式ページをもとに構造化しています。"),
          el("li", {}, "議決結果は公式ページやPDFから取得できる範囲を掲載します。"),
          el("li", {}, "地域データは自治体資料、決算カード、e-Statなどを使います。"),
          el("li", {}, "生成後にスキーマ検証と個人情報チェックを行います。"),
        ]),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "出典・クレジット"),
        el("ul", { class: "info-list" }, [
          el("li", {}, "議員名簿・議決結果・会議録は、各議会と自治体の公開情報を出典にしています。"),
          el("li", {}, [
            "統計データ: ",
            el("a", {
              href: "https://www.e-stat.go.jp/",
              target: "_blank",
              rel: "noopener",
            }, "e-Stat"),
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
            "市町村地図: ",
            el("a", {
              href: "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html",
              target: "_blank",
              rel: "noopener",
            }, "国土数値情報 行政区域データ"),
            " (PDL1.0)",
          ]),
        ]),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "問い合わせ"),
        el("p", { class: "muted" }, "このサイトは非公式・個人運営です。正確な情報は公式発表を優先してください。"),
        el("p", {}, [
          el("a", {
            class: "button-link",
            href: "https://forms.gle/YiggPHVqdPViAdHRA",
            target: "_blank",
            rel: "noopener",
          }, "訂正・不具合を送る"),
        ]),
      ]),
    ]),
  );
}
