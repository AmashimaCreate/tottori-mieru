import { prefPath } from "./router.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderTop(root, councils = []) {
  root.innerHTML = "";
  const prefectures = councils.filter((council) => council.type === "prefecture");
  const activePrefectures = prefectures.filter((council) => council.status === "active");
  const prefectureByCode = new Map(
    prefectures.map((council) => [String(Number(council.lg_code.slice(0, 2))), council]),
  );
  const mapFrame = el("div", { class: "map-frame japan-map-frame" }, [
    el("p", { class: "muted" }, "日本地図を読み込み中..."),
  ]);
  const statusMessage = el("p", { class: "map-status-message", "aria-live": "polite" }, "");

  root.appendChild(
    el("section", { class: "national-hero page-card" }, [
      el("div", { class: "national-copy" }, [
        el("p", { class: "eyebrow" }, "全国トップ"),
        el("h2", { class: "section-title" }, "対応地域から議会を見る"),
        el(
          "p",
          {},
          "対応済みの都道府県から議会ページへ進めます。準備中の地域は順次追加します。",
        ),
      ]),
      el("div", { class: "national-map-wrap" }, [
        mapFrame,
        statusMessage,
        el("section", { class: "supported-region-list", "aria-labelledby": "supported-regions-title" }, [
          el("h3", { id: "supported-regions-title" }, "対応地域"),
          el("div", { class: "supported-region-grid" }, [
            ...activePrefectures.map((council) => renderSupportedRegionCard(council, councils)),
          ]),
        ]),
      ]),
    ]),
  );

  hydrateJapanMap(mapFrame, prefectureByCode, statusMessage);
}

function renderSupportedRegionCard(prefectureCouncil, councils) {
  const count = councils.filter((council) =>
    council.prefecture === prefectureCouncil.prefecture && council.status === "active"
  ).length;
  const cityCount = councils.filter((council) =>
    council.prefecture === prefectureCouncil.prefecture
    && council.status === "active"
    && council.type === "city"
  ).length;
  const summary = cityCount
    ? `県議会と県内掲載市議会${cityCount}件を掲載`
    : "県議会の基本情報・議員名簿を掲載";
  return el("a", { class: "supported-region-card", href: prefPath(prefectureCouncil.prefecture) }, [
    el("span", { class: "region-card-status" }, "対応中"),
    el("strong", {}, prefectureCouncil.prefecture_name),
    el("span", {}, `${summary}（計${count}議会）`),
    el("small", {}, "地域ページへ"),
  ]);
}

async function hydrateJapanMap(container, prefectureByCode, statusMessage) {
  try {
    const response = await fetch("assets/maps/japan-prefectures.svg");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    container.innerHTML = await response.text();

    const svg = container.querySelector("svg");
    if (!svg) throw new Error("SVG root not found");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "日本地図。対応済みの都道府県を選択できます。");
    svg.removeAttribute("width");
    svg.removeAttribute("height");

    container.querySelectorAll("[data-code]").forEach((region) => {
      const council = prefectureByCode.get(region.dataset.code || "");
      region.classList.add("map-region", "is-disabled");
      region.setAttribute("tabindex", "0");
      if (council?.status === "active") {
        region.classList.remove("is-disabled");
        region.classList.add("is-active");
        region.setAttribute("role", "link");
        region.setAttribute("aria-label", `${council.prefecture_name}ページへ`);
        region.removeAttribute("aria-disabled");
        region.addEventListener("click", () => {
          window.location.href = prefPath(council.prefecture);
        });
        region.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          window.location.href = prefPath(council.prefecture);
        });
        return;
      }
      const label = council?.prefecture_name || "この地域";
      region.setAttribute("role", "button");
      region.setAttribute("aria-label", `${label}は準備中です`);
      region.setAttribute("aria-disabled", "true");
      const showPending = () => {
        statusMessage.textContent = `${label}は準備中です。`;
      };
      region.addEventListener("click", showPending);
      region.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        showPending();
      });
    });
  } catch (error) {
    console.warn("Failed to load Japan map", error);
    container.innerHTML = "";
    container.appendChild(
      el(
        "p",
        { class: "caution-note" },
        "地図を読み込めませんでした。対応地域一覧から選択してください。",
      ),
    );
  }
}
