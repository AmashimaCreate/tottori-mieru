import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderGuide(root) {
  root.innerHTML = "";
  root.append(
    el("section", { class: "guide-page page-card" }, [
      el("p", { class: "eyebrow" }, "はじめに"),
      el("h2", { class: "section-title" }, "このサイトでできること"),
      el("div", { class: "guide-lead" }, [
        el("p", {}, "議員名簿、議決結果、自治体の基礎データをまとめて確認できます。"),
        el("p", {}, "気になった議員や議案から、公式情報や会議録検索へ進めます。"),
        el("p", {}, "数字や件数から、気になる一次ソースへ進めます。"),
      ]),
    ]),
    el("section", { class: "guide-page page-card" }, [
      el("p", { class: "eyebrow" }, "一次ソースに当たる"),
      el("h2", { class: "section-title" }, "会議録検索システムの使い方"),
      el("ol", { class: "guide-steps" }, [
        el("li", {}, "議会ページの「公式情報へのリンク」から会議録検索を開きます。"),
        el("li", {}, "議員名、会議名、日付、気になる言葉を入れて検索します。"),
        el("li", {}, "検索結果の本文を開き、前後の発言や議事の流れも一緒に確認します。"),
      ]),
    ]),
    el("section", { class: "guide-page page-card" }, [
      el("h2", { class: "section-title" }, "議決結果の探し方"),
      el("p", {}, "議会ページの「公式情報へのリンク」や「議決一覧」から、公式PDF・公式ページへ進めます。議員別賛否が公開されていない議会では、議案ごとの結果だけが確認できる場合があります。"),
    ]),
    el("section", { class: "guide-page page-card" }, [
      el("h2", { class: "section-title" }, "自治体の統計データ"),
      el("p", {}, [
        "人口や財政などの長期推移は、政府統計の総合窓口 ",
        el("a", { href: "https://www.e-stat.go.jp/", target: "_blank", rel: "noopener" }, "e-Stat"),
        " の社会・人口統計体系などで確認できます。このサイトでは、取得できる範囲をグラフとして表示しています。",
      ]),
    ]),
    el("section", { class: "guide-page page-card" }, [
      el("p", { class: "eyebrow" }, "深掘りする"),
      el("h2", { class: "section-title" }, "AIで調べるときのコツ"),
      el("p", {}, "AIに聞くときは、議会名・議員名・議案名・日付・公式URLを入れ、出典を示しながら事実を整理するよう指定すると、一次ソースを確認しやすい形で返ってきます。"),
      el("p", { class: "ai-caution" }, "AIの回答には誤りが含まれることがあります。重要な判断は一次ソースで確認してください。"),
    ]),
  );
}
