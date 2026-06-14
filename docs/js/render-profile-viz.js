import {
  formatDecimal,
  formatPeople,
  formatYen,
  sourceLink,
} from "./render-profile.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}, children = []) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== null) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function metricValue(profile, key) {
  const value = profile?.[key]?.value;
  return typeof value === "number" ? value : null;
}

function maxProfileValue(summaries, key) {
  const values = (summaries || [])
    .map((summary) => metricValue(summary.profile, key))
    .filter((value) => typeof value === "number");
  return values.length ? Math.max(...values) : null;
}

function clampPercent(value, domain) {
  if (typeof value !== "number" || !domain) return 0;
  return Math.max(0, Math.min(100, (value / domain) * 100));
}

function miniBar(percent, label) {
  return svgEl("svg", {
    class: "mini-bar-svg",
    viewBox: "0 0 100 10",
    preserveAspectRatio: "none",
    role: "img",
    "aria-label": label,
  }, [
    svgEl("rect", {
      class: "mini-bar-track",
      x: "0",
      y: "1",
      width: "100",
      height: "8",
      rx: "4",
    }),
    svgEl("rect", {
      class: "mini-bar-fill",
      x: "0",
      y: "1",
      width: percent.toFixed(1),
      height: "8",
      rx: "4",
    }),
  ]);
}

function profileMetric({ label, value, formatted, sourceUrl, percent, note }) {
  if (typeof value !== "number") return null;
  return el("article", { class: "profile-viz-item" }, [
    el("div", { class: "profile-viz-meta" }, [
      el("span", { class: "profile-viz-label" }, label),
      el("strong", { class: "profile-viz-value" }, formatted),
      sourceLink(sourceUrl),
    ]),
    miniBar(percent, `${label}: ${formatted}`),
    note ? el("p", { class: "profile-viz-note" }, note) : null,
  ]);
}

export function renderProfileVisualization(profile, summaries) {
  if (!profile) return null;

  const population = metricValue(profile, "population");
  const budget = metricValue(profile, "budget_general_yen");
  const fiscalIndex = metricValue(profile, "fiscal_index");

  const populationMax = maxProfileValue(summaries, "population");
  const budgetMax = maxProfileValue(summaries, "budget_general_yen");
  const metrics = [
    profileMetric({
      label: "人口",
      value: population,
      formatted: formatPeople(population),
      sourceUrl: profile.population?.source_url,
      percent: clampPercent(population, populationMax),
      note: "入力済み議会の最大値を100%として表示",
    }),
    profileMetric({
      label: "一般会計予算",
      value: budget,
      formatted: formatYen(budget),
      sourceUrl: profile.budget_general_yen?.source_url,
      percent: clampPercent(budget, budgetMax),
      note: "入力済み議会の最大値を100%として表示",
    }),
    profileMetric({
      label: "財政力指数",
      value: fiscalIndex,
      formatted: formatDecimal(fiscalIndex),
      sourceUrl: profile.fiscal_index?.source_url,
      percent: clampPercent(fiscalIndex, 1),
      note: "1.0を目安として表示",
    }),
  ].filter(Boolean);

  if (!metrics.length) return null;

  return el("section", { class: "viz-panel profile-viz-panel" }, [
    el("div", { class: "viz-heading-row" }, [
      el("div", {}, [
        el("h2", { class: "section-title" }, "基礎データの図解"),
        el(
          "p",
          { class: "viz-lead" },
          "人口・予算・財政力指数を、数字とミニバーで確認できます。",
        ),
      ]),
    ]),
    el("div", { class: "profile-viz-grid" }, metrics),
  ]);
}
