import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderGuide(root) {
  root.innerHTML = "";
  root.append(
    el("section", { class: "info-hero page-card" }, [
      el("p", { class: "eyebrow" }, "調べ方ガイド"),
      el("h2", { class: "section-title" }, "気になった情報から公式資料へ進む"),
      el("p", { class: "info-lead" }, "このサイトは入口です。議員、議案、地域データを見て、必要なところだけ一次ソースで確認できます。"),
    ]),
    el("section", { class: "guide-flow page-card" }, [
      el("p", { class: "eyebrow" }, "基本の流れ"),
      el("h3", {}, "3ステップで確認する"),
      el("ol", { class: "guide-step-cards" }, [
        renderStep("1", "見る", "議員名簿、議決、地域データから気になる項目を探す。"),
        renderStep("2", "開く", "公式プロフィール、議決PDF、会議録検索へ進む。"),
        renderStep("3", "確かめる", "本文や前後の議事を読み、一次ソースで確認する。"),
      ]),
    ]),
    el("div", { class: "info-grid" }, [
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "会議録を探す"),
        el("ol", { class: "guide-steps" }, [
          el("li", {}, "議会ページの公式リンクから会議録検索を開く。"),
          el("li", {}, "議員名、会議名、日付、気になる言葉で検索する。"),
          el("li", {}, "本文を開き、前後の発言も確認する。"),
        ]),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "議決結果を見る"),
        el("p", {}, "議会ページの議決一覧や公式リンクから、公式PDF・公式ページへ進めます。"),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "統計データを見る"),
        el("p", {}, [
          "人口や財政などの長期推移は ",
          el("a", { href: "https://www.e-stat.go.jp/", target: "_blank", rel: "noopener" }, "e-Stat"),
          " などの公的統計で確認できます。",
        ]),
      ]),
      el("section", { class: "info-card page-card" }, [
        el("h3", {}, "AIで深掘りする"),
        el("p", {}, "議員名、議案名、日付、公式URLを入れて、出典つきで整理するよう頼むと確認しやすくなります。"),
        el("p", { class: "ai-caution" }, "AIの回答には誤りが含まれることがあります。重要な判断は一次ソースで確認してください。"),
      ]),
    ]),
  );
}

function renderStep(number, title, body) {
  return el("li", {}, [
    el("span", { class: "guide-step-number" }, number),
    el("strong", {}, title),
    el("span", {}, body),
  ]);
}
