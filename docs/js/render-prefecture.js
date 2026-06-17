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
  const cityCouncils = activeCouncils.filter((council) => council.type === "city");

  root.appendChild(
    el("section", { class: "prefecture-map-panel" }, [
      el("div", { class: "section-heading-row" }, [
        el("div", {}, [
          el("p", { class: "eyebrow" }, prefectureCouncil?.prefecture_name || "都道府県"),
          el("h2", { class: "section-title" }, "掲載中の議会"),
        ]),
      ]),
      el("p", { class: "muted" },
        "このページは、現在このサイトに掲載している議会だけを表示しています。",
      ),
    ]),
  );

  if (prefectureCouncil) {
    root.appendChild(
      el("section", { class: "council-card-section" }, [
        el("div", { class: "section-heading-row" }, [
          el("div", {}, [
            el("p", { class: "eyebrow" }, "都道府県議会"),
            el("h2", { class: "section-title" }, `${prefectureCouncil.prefecture_name}議会`),
          ]),
        ]),
        el("div", { class: "council-grid council-grid-compact" }, [
          renderCouncilCard(prefectureCouncil, prefecture, summaryByCouncilId.get(prefectureCouncil.id), { hideTypeLabel: true }),
        ]),
      ]),
    );
  }

  if (cityCouncils.length) {
    root.appendChild(
      el("section", { class: "council-card-section" }, [
        el("div", { class: "section-heading-row" }, [
          el("div", {}, [
            el("p", { class: "eyebrow" }, "政令指定都市"),
            el("h2", { class: "section-title" }, "この県の政令市"),
          ]),
        ]),
        el("p", { class: "muted" },
          "現在は政令指定都市の市議会のみ掲載しています。県内すべての市区町村議会を網羅しているわけではありません。",
        ),
        el("div", { class: "council-grid" },
          cityCouncils.map((council) =>
            renderCouncilCard(council, prefecture, summaryByCouncilId.get(council.id)),
          ),
        ),
      ]),
    );
  }
}

function renderCouncilCard(council, prefecture, summary = null, options = {}) {
  const memberText = typeof summary?.memberCount === "number"
    ? `議員${summary.memberCount}人`
    : "議員数を確認中";
  const hideTypeLabel = options.hideTypeLabel || council.type === "prefecture";
  return el("article", { class: `council-card ${council.type === "prefecture" ? "is-prefecture" : "is-city"}` }, [
    hideTypeLabel ? null : el("div", { class: "card-eyebrow" }, councilTypeLabel(council)),
    el("h3", {}, council.name),
    el("p", { class: "muted" }, memberText),
    el("a", { class: "button-link", href: councilPath(prefecture, council.id) }, "議会ページを見る"),
  ]);
}

function councilTypeLabel(council) {
  if (council.type === "prefecture") return "県議会";
  return "市議会";
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
