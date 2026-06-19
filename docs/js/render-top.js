import { prefPath } from "./router.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderTop(root, councils = []) {
  root.innerHTML = "";
  const prefectures = councils.filter((council) => council.type === "prefecture");
  const activePrefectures = prefectures.filter((council) => council.status === "active");
  const activeCouncils = councils.filter((council) => council.status === "active");
  const prefectureByCode = new Map(
    prefectures.map((council) => [String(Number(council.lg_code.slice(0, 2))), council]),
  );
  const memberCountNode = el("strong", { class: "national-stat-value" }, "集計中");
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
        el("section", { class: "national-stats", "aria-label": "掲載データ数" }, [
          el("h3", {}, "掲載データ"),
          el("div", { class: "national-stat-grid" }, [
            renderNationalStat("対応地域", `${formatNumber(activePrefectures.length)}都道府県`),
            renderNationalStat("掲載議会", `${formatNumber(activeCouncils.length)}議会`),
            renderNationalStat("掲載議員", memberCountNode),
          ]),
        ]),
        el("section", { class: "supported-region-list", "aria-labelledby": "supported-regions-title" }, [
          el("h3", { id: "supported-regions-title" }, "対応地域"),
          el("div", { class: "supported-region-grid" }, [
            ...activePrefectures.map((council) => renderSupportedRegionCard(council)),
          ]),
        ]),
      ]),
    ]),
  );

  hydrateJapanMap(mapFrame, prefectureByCode, statusMessage);
  hydrateMemberCount(memberCountNode, activeCouncils);
}

function renderSupportedRegionCard(prefectureCouncil) {
  return el("a", { class: "supported-region-card", href: prefPath(prefectureCouncil.prefecture) }, [
    el("strong", {}, prefectureCouncil.prefecture_name),
  ]);
}

function renderNationalStat(label, value) {
  return el("div", { class: "national-stat-card" }, [
    el("span", { class: "national-stat-label" }, label),
    typeof value === "string" ? el("strong", { class: "national-stat-value" }, value) : value,
  ]);
}

function formatNumber(value) {
  return new Intl.NumberFormat("ja-JP").format(value);
}

async function hydrateMemberCount(node, activeCouncils) {
  try {
    const counts = await Promise.all(
      activeCouncils.map(async (council) => {
        const response = await fetch(`./data/${council.id}/members.json`, { cache: "no-cache" });
        if (!response.ok) return 0;
        const data = await response.json();
        return Array.isArray(data.members) ? data.members.length : 0;
      }),
    );
    const total = counts.reduce((sum, count) => sum + count, 0);
    node.textContent = `${formatNumber(total)}人`;
  } catch (error) {
    console.warn("Failed to count members", error);
    node.textContent = "確認中";
  }
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
        if (council.prefecture === "okinawa") {
          addOkinawaHitArea(region);
        }
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

function addOkinawaHitArea(region) {
  if (region.querySelector(".okinawa-hit-area")) return;
  const hitArea = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  hitArea.setAttribute("class", "okinawa-hit-area");
  hitArea.setAttribute("x", "-16");
  hitArea.setAttribute("y", "-16");
  hitArea.setAttribute("width", "348");
  hitArea.setAttribute("height", "166");
  hitArea.setAttribute("fill", "transparent");
  hitArea.setAttribute("pointer-events", "all");
  region.insertBefore(hitArea, region.firstChild);
}
