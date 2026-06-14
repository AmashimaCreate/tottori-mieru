import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const PURPOSE_COLORS = [
  "#0072b2",
  "#e69f00",
  "#009e73",
  "#cc79a7",
  "#56b4e9",
  "#d55e00",
  "#785ef0",
  "#999999",
  "#117733",
  "#882255",
];

export function renderFinanceSection(finance) {
  if (!finance?.expenditure?.purpose?.items?.length) return null;

  const purpose = finance.expenditure.purpose;
  const nature = finance.expenditure.nature;

  return el("section", { class: "finance-section" }, [
    el("div", { class: "section-heading-row finance-heading" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "このまちのお金の使いみち"),
        el("h2", { class: "section-title" }, "決算で見る歳出内訳"),
      ]),
      el("span", { class: "finance-badge" }, `決算 / ${finance.fiscal_year}年度`),
    ]),
    el("p", { class: "finance-lead" }, [
      "予算は計画、決算は実際に使われたお金です。ここでは目的別の歳出を大きい順に並べています。",
    ]),
    finance.similar_group
      ? el("p", { class: "finance-peer-note" }, `類似団体平均との比較: ${finance.similar_group}`)
      : null,
    el("div", { class: "finance-total-row" }, [
      el("span", {}, "歳出合計"),
      el("strong", {}, formatOkuYen(purpose.total_thousand_yen)),
      el("small", {}, `1人あたり ${formatYenPerPerson(totalPerCapita(purpose, finance.population?.value))}/人`),
    ]),
    renderFinanceOverview(purpose, "目的別歳出の構成"),
    el("details", { class: "finance-detail-block finance-purpose-detail" }, [
      el("summary", {}, "費目ごとの内訳を見る"),
      renderFinanceBarList(purpose),
    ]),
    el("p", { class: "finance-note" },
      "1人あたり額は歳出を人口で割った参考値です。国や県からのお金も含むため、市民の負担額ではありません。",
    ),
    el("p", { class: "finance-source finance-source-minimal" },
      `出典: ${finance.source?.name || "総務省「地方財政状況調査」/デジタル庁"}（${finance.fiscal_year}年度決算）`,
    ),
    nature?.items?.length
      ? el("details", { class: "finance-detail-block finance-nature-details" }, [
          el("summary", {}, "性質別歳出（人件費・扶助費など）を見る"),
          renderNatureExplanation(),
          renderFinanceOverview(nature, "性質別歳出の構成", true),
          renderFinanceBarList(nature, true),
          renderFullSource(finance),
        ])
      : null,
  ]);
}

function renderNatureExplanation() {
  return el("div", { class: "finance-nature-explain" }, [
    el("h3", {}, "性質別歳出とは"),
    el("p", {}, "目的別が「何のために」使ったか(福祉・教育など)を表すのに対し、性質別は「どんな形で」使ったかを表します。"),
    el("ul", {}, [
      el("li", {}, [el("strong", {}, "人件費: "), "職員の給料など、人に関わる費用"]),
      el("li", {}, [el("strong", {}, "扶助費: "), "生活保護や児童手当など、暮らしを支えるために直接支払うお金"]),
      el("li", {}, [el("strong", {}, "普通建設事業費: "), "道路や学校など、ものを作るための費用"]),
      el("li", {}, [el("strong", {}, "物件費: "), "物の購入や委託、光熱費など、運営にかかる費用"]),
      el("li", {}, [el("strong", {}, "補助費等: "), "団体や他の組織への補助・負担金"]),
      el("li", {}, [el("strong", {}, "公債費: "), "借金(地方債)の返済"]),
    ]),
  ]);
}

function renderFullSource(finance) {
  return el("p", { class: "finance-source finance-source-full" }, [
    `出典: ${finance.source?.name || "地方財政データ"}（${finance.fiscal_year}年度決算）。`,
    `ライセンス: ${finance.source?.license || "出典表記が必要なオープンデータ"}。`,
    "予算は計画、決算は実績です。",
  ]);
}

function renderFinanceOverview(section, title, isSecondary = false) {
  const total = section.total_thousand_yen || 0;
  if (!total) return null;
  return el("div", { class: `finance-stack-card${isSecondary ? " is-secondary" : ""}` }, [
    el("div", { class: "finance-stack-head" }, [
      el("h3", {}, title),
      el("p", {}, `${section.items.length}費目 / 構成比`),
    ]),
    el("div", { class: "finance-stack-bar", "aria-label": `${title}を構成比で示す積み上げバー` },
      section.items.map((item, index) => {
        const width = Math.max(1.5, (item.amount_thousand_yen / total) * 100);
        return el("span", {
          class: "finance-stack-segment",
          style: `--segment-width: ${width}%; --finance-color: ${financeColor(index, isSecondary)};`,
          title: `${item.label} ${formatPercent(item.share_pct)}`,
        }, formatSegmentLabel(item.share_pct));
      }),
    ),
    el("ul", { class: "finance-stack-legend" },
      section.items.map((item, index) => el("li", {}, [
        el("span", {
          class: "finance-stack-swatch",
          style: `--finance-color: ${financeColor(index, isSecondary)};`,
          "aria-hidden": "true",
        }),
        el("span", {}, item.label),
        el("strong", {}, formatPercent(item.share_pct)),
      ])),
    ),
  ]);
}

function renderFinanceBarList(section, isSecondary = false) {
  const maxAmount = Math.max(...section.items.map((entry) => entry.amount_thousand_yen || 0));
  return el("div", { class: `finance-bars${isSecondary ? " is-secondary" : ""}` },
    section.items.map((item, index) => renderFinanceBar(item, maxAmount, index, isSecondary)),
  );
}

function renderFinanceBar(item, maxAmount, index, isSecondary = false) {
  const width = maxAmount > 0
    ? Math.max(2, (item.amount_thousand_yen / maxAmount) * 100)
    : 0;
  const color = financeColor(index, isSecondary);
  const peer = item.similar_group_average_per_capita_yen;
  const peerN = item.similar_group_average_n;
  return el("article", { class: "finance-bar-row", style: `--bar-width: ${width}%; --bar-color: ${color};` }, [
    el("div", { class: "finance-bar-label" }, [
      el("strong", {}, item.label),
      el("span", {}, `${formatOkuYen(item.amount_thousand_yen)} / ${formatPercent(item.share_pct)}`),
    ]),
    el("div", { class: "finance-bar-track", "aria-hidden": "true" }, [
      el("span", { class: "finance-bar-fill" }),
    ]),
    el("div", { class: "finance-bar-meta" }, [
      el("span", {}, `1人あたり ${formatYenPerPerson(item.per_capita_yen)}`),
      peer != null
        ? el("span", {}, `類似団体平均 ${formatYenPerPerson(peer)}/人${formatPeerN(peerN)}`)
        : el("span", {}, "類似団体平均: データなし"),
    ]),
  ]);
}

function financeColor(index, isSecondary = false) {
  const color = PURPOSE_COLORS[index % PURPOSE_COLORS.length];
  return isSecondary ? `${color}cc` : color;
}

function formatSegmentLabel(sharePct) {
  return typeof sharePct === "number" && sharePct >= 8 ? `${Math.round(sharePct)}%` : "";
}

function totalPerCapita(section, population) {
  if (!section?.total_yen || !population) return null;
  return Math.round(section.total_yen / population);
}

function formatPeerN(value) {
  return typeof value === "number" ? `(${value}市平均)` : "";
}

function formatOkuYen(thousandYen) {
  if (typeof thousandYen !== "number") return "データなし";
  const oku = thousandYen / 100000;
  return `${oku.toLocaleString("ja-JP", {
    maximumFractionDigits: oku >= 100 ? 0 : 1,
  })}億円`;
}

function formatPercent(value) {
  if (typeof value !== "number") return "0%";
  return `${value.toLocaleString("ja-JP", { maximumFractionDigits: 1 })}%`;
}

function formatYenPerPerson(value) {
  if (typeof value !== "number") return "データなし";
  if (value >= 10000) {
    return `${(value / 10000).toLocaleString("ja-JP", { maximumFractionDigits: 1 })}万円`;
  }
  return `${Math.round(value).toLocaleString("ja-JP")}円`;
}
