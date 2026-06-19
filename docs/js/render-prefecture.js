import { councilPath, prefComparePath } from "./router.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderPrefecturePage(root, councils, prefecture = "tottori", summaries = []) {
  root.innerHTML = "";
  const prefectureCouncils = councils.filter((council) => council.prefecture === prefecture);
  const prefectureCouncil = prefectureCouncils.find((council) => council.type === "prefecture");
  if (prefecture !== "tottori") {
    renderGenericPrefecturePage(root, prefectureCouncils, prefectureCouncil, prefecture, summaries);
    return;
  }
  const summaryByCouncilId = new Map(
    summaries.map((summary) => [summary.council.id, summary]),
  );
  const mapFrame = el("div", { class: "map-frame municipality-map-frame" }, [
    el("p", { class: "muted" }, "鳥取県の市町村地図を読み込み中..."),
  ]);
  root.appendChild(
    el("section", { class: "prefecture-map-panel" }, [
      el("div", { class: "prefecture-map-layout" }, [
        prefectureCouncil
          ? el("div", { class: "prefecture-assembly-wrap" }, [
              el("p", { class: "map-caption" }, "県全体を扱う議会"),
              renderCouncilCard(
                prefectureCouncil,
                prefecture,
                summaryByCouncilId.get(prefectureCouncil.id),
                { hideTypeLabel: true },
              ),
            ])
          : null,
        el("div", {}, [
          mapFrame,
          el("div", { class: "map-legend", "aria-label": "地図の凡例" }, [
            el("span", {}, [
              el("span", { class: "legend-swatch is-supported" }),
              "対応済み",
            ]),
            el("span", {}, [
              el("span", { class: "legend-swatch is-unsupported" }),
              "未対応",
            ]),
          ]),
          el(
            "p",
            { class: "muted" },
            "鳥取県内19市町村(4市+15町村、14町1村)のうち、色付きの4市は議会ページへ進めます。グレーの15町村は未対応です。",
          ),
        ]),
      ]),
    ]),
  );

  root.appendChild(
    el("section", { class: "council-card-section" }, [
      el("div", { class: "section-heading-row" }, [
        el("div", {}, [
          el("p", { class: "eyebrow" }, "対応中の議会"),
          el("h2", { class: "section-title" }, "議会カードから選ぶ"),
        ]),
      ]),
      el(
        "div",
        { class: "council-grid" },
        prefectureCouncils.map((council) =>
          renderCouncilCard(council, prefecture, summaryByCouncilId.get(council.id)),
        ),
      ),
    ]),
  );

  root.appendChild(
    el("p", { class: "prefecture-compare-link" }, [
      el("a", { href: prefComparePath(prefecture) }, "5議会をくらべる →"),
    ]),
  );

  hydrateMunicipalityMap(mapFrame, prefecture);
}

function renderGenericPrefecturePage(root, prefectureCouncils, prefectureCouncil, prefecture, summaries) {
  const summaryByCouncilId = new Map(
    summaries.map((summary) => [summary.council.id, summary]),
  );
  const activeCouncils = prefectureCouncils.filter((council) => council.status === "active");
  const wardCouncils = activeCouncils.filter((council) => isTokyoWardCouncil(council));
  const cityCouncils = activeCouncils.filter((council) => council.type === "city" && !isTokyoWardCouncil(council));
  const totalMembers = activeCouncils.reduce((sum, council) => {
    const count = summaryByCouncilId.get(council.id)?.memberCount;
    return sum + (typeof count === "number" ? count : 0);
  }, 0);
  const groups = [
    cityCouncils.length
      ? renderCouncilGroup("政令指定都市", cityCouncils, prefecture, summaryByCouncilId)
      : null,
    wardCouncils.length
      ? renderCouncilGroup("特別区議会", wardCouncils, prefecture, summaryByCouncilId, { compact: true })
      : null,
  ].filter(Boolean);

  root.appendChild(
    el("section", { class: "prefecture-landing page-card" }, [
      el("div", { class: "prefecture-landing-hero" }, [
        el("div", {}, [
          el("p", { class: "eyebrow" }, prefectureCouncil?.prefecture_name || "地域ページ"),
          el("h2", { class: "section-title" }, "掲載中の議会を見る"),
          el("div", { class: "prefecture-summary-pills", "aria-label": "掲載データ数" }, [
            renderSummaryPill("掲載議会", `${activeCouncils.length}議会`),
            renderSummaryPill("掲載議員", totalMembers ? `${formatNumber(totalMembers)}人` : "確認中"),
          ]),
        ]),
        prefectureCouncil
          ? renderCouncilCard(prefectureCouncil, prefecture, summaryByCouncilId.get(prefectureCouncil.id), { hideTypeLabel: true, featured: true })
          : null,
      ]),
      groups.length ? el("div", { class: "prefecture-council-groups" }, groups) : null,
    ]),
  );
}

function renderCouncilGroup(label, councils, prefecture, summaryByCouncilId, options = {}) {
  return el("section", { class: "prefecture-council-group" }, [
    el("div", { class: "prefecture-group-heading" }, [
      el("h3", {}, label),
      el("span", {}, `${councils.length}議会`),
    ]),
    el(
      "div",
      { class: `council-grid ${options.compact ? "council-grid-compact" : ""}` },
      councils.map((council) =>
        renderCouncilCard(council, prefecture, summaryByCouncilId.get(council.id), options),
      ),
    ),
  ]);
}

function renderSummaryPill(label, value) {
  return el("span", { class: "prefecture-summary-pill" }, [
    el("span", {}, label),
    el("strong", {}, value),
  ]);
}

function renderCouncilCard(council, prefecture, summary = null, options = {}) {
  const memberText = typeof summary?.memberCount === "number"
    ? `議員${summary.memberCount}人`
    : "議員数を確認中";
  const hideTypeLabel = options.hideTypeLabel || council.type === "prefecture";
  const classes = [
    "council-card",
    council.type === "prefecture" ? "is-prefecture" : "is-city",
    options.featured ? "is-featured" : "",
  ].filter(Boolean).join(" ");
  return el("article", { class: classes }, [
    hideTypeLabel ? null : el("div", { class: "card-eyebrow" }, councilTypeLabel(council)),
    el("h3", {}, council.name),
    el("p", { class: "muted" }, memberText),
    el("a", { class: "button-link", href: councilPath(prefecture, council.id) }, "議会ページを見る"),
  ]);
}

function councilTypeLabel(council) {
  if (council.type === "prefecture") return "県議会";
  if (isTokyoWardCouncil(council)) return "区議会";
  return "市議会";
}

function isTokyoWardCouncil(council) {
  return council?.prefecture === "tokyo" && council?.name?.includes("区議会");
}

function formatNumber(value) {
  return Number(value).toLocaleString("ja-JP");
}

async function hydrateMunicipalityMap(container, prefecture) {
  try {
    const response = await fetch("assets/maps/tottori-municipalities.svg");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    container.innerHTML = await response.text();

    const svg = container.querySelector("svg");
    if (!svg) throw new Error("SVG root not found");
    svg.removeAttribute("width");
    svg.removeAttribute("height");

    container.querySelectorAll(".municipality").forEach((region) => {
      const name = region.dataset.name || "市町村";
      const councilId = region.dataset.councilId;
      if (!councilId) {
        region.setAttribute("aria-label", `${name}（未対応）`);
        region.setAttribute("aria-disabled", "true");
        return;
      }
      region.setAttribute("role", "link");
      region.setAttribute("tabindex", "0");
      region.setAttribute("aria-label", `${name}議会ページへ`);
      region.addEventListener("click", () => {
        window.location.href = councilPath(prefecture, councilId);
      });
      region.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        window.location.href = councilPath(prefecture, councilId);
      });
    });
  } catch (error) {
    console.warn("Failed to load Tottori municipality map", error);
    container.innerHTML = "";
    container.appendChild(
      el(
        "p",
        { class: "caution-note" },
        "市町村地図を読み込めませんでした。議会カード一覧から選択してください。",
      ),
    );
  }
}
