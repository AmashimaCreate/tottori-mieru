import {
  formatDecimal,
  formatPeople,
  sourceLink,
} from "./render-profile.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const SVG_NS = "http://www.w3.org/2000/svg";
const COUNCIL_ORDER = [
  "tottori-pref",
  "tottori-city",
  "yonago-city",
  "kurayoshi-city",
  "sakaiminato-city",
];

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

function orderedSummaries(summaries) {
  const byId = new Map((summaries || []).map((summary) => [summary.council.id, summary]));
  return COUNCIL_ORDER.map((id) => byId.get(id)).filter(Boolean);
}

function valueFrom(summary, metric) {
  if (metric.key === "member_count") return summary.memberCount || null;
  if (metric.key === "population_per_member") {
    const value = summary.profile?.per_capita?.population_per_member;
    return typeof value === "number" ? value : null;
  }
  const value = summary.profile?.[metric.profileKey]?.value;
  return typeof value === "number" ? value : null;
}

function maxMetricValue(summaries, metric) {
  if (metric.domain) return metric.domain;
  const values = summaries
    .map((summary) => valueFrom(summary, metric))
    .filter((value) => typeof value === "number");
  return values.length ? Math.max(...values) : null;
}

function clampPercent(value, domain) {
  if (typeof value !== "number" || !domain) return 0;
  return Math.max(0, Math.min(100, (value / domain) * 100));
}

function barSvg(percent, label, metricKey) {
  return svgEl("svg", {
    class: `comparison-bar-svg comparison-bar-${metricKey}`,
    viewBox: "0 0 100 12",
    preserveAspectRatio: "none",
    role: "img",
    "aria-label": label,
  }, [
    svgEl("rect", {
      class: "comparison-bar-track",
      x: "0",
      y: "2",
      width: "100",
      height: "8",
      rx: "4",
    }),
    svgEl("rect", {
      class: "comparison-bar-fill",
      x: "0",
      y: "2",
      width: percent.toFixed(1),
      height: "8",
      rx: "4",
    }),
  ]);
}

function sourceNodes(summary, metric) {
  if (metric.key === "member_count") {
    return [sourceLink(summary.membersMeta?.source_url, "名簿")].filter(Boolean);
  }
  if (metric.key === "population_per_member") {
    return [
      sourceLink(summary.profile?.population?.source_url, "人口"),
      sourceLink(summary.membersMeta?.source_url, "議員"),
    ].filter(Boolean);
  }
  return [sourceLink(summary.profile?.[metric.profileKey]?.source_url)].filter(Boolean);
}

function metricSourceNode(summaries, metric) {
  for (const summary of summaries) {
    const source = sourceNodes(summary, metric)[0];
    if (source) return sourceLink(source.href, "出典");
  }
  return null;
}

function cityAverage(summaries, metric) {
  const values = summaries
    .filter((summary) => summary.council.type === "city")
    .map((summary) => valueFrom(summary, metric))
    .filter((value) => typeof value === "number");
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatMetricDiff(metric, diff) {
  if (typeof diff !== "number") return null;
  if (Math.abs(diff) < 0.000001) {
    if (metric.key === "fiscal_index") return "±0";
    return metric.format(0).replace(/^0/, "±0");
  }
  const sign = diff < 0 ? "−" : "+";
  const abs = Math.abs(diff);
  if (metric.key === "fiscal_index") {
    return `${sign}${abs.toLocaleString("ja-JP", { maximumFractionDigits: 3 })}`;
  }
  return `${sign}${metric.format(Math.round(abs))}`;
}

function renderComparisonRow(summary, metric, domain, average) {
  const value = valueFrom(summary, metric);
  const formatted = typeof value === "number" ? metric.format(value) : null;
  const percent = clampPercent(value, domain);
  const diff = summary.council.type === "city" && typeof value === "number" && typeof average === "number"
    ? formatMetricDiff(metric, value - average)
    : null;

  return el("div", { class: "comparison-row" }, [
    el("div", { class: "comparison-council" }, [
      el("span", {}, summary.council.name),
      el("span", { class: "comparison-type" }, councilTypeLabel(summary.council)),
    ]),
    el("div", { class: "comparison-value" }, [
      formatted
        ? el("strong", {}, formatted)
        : el("span", { class: "missing-value" }, "データ未入力"),
      diff ? el("span", { class: "comparison-diff" }, `市平均との差 ${diff}`) : null,
    ]),
    el("div", { class: "comparison-bar-cell" }, [
      typeof value === "number"
        ? barSvg(percent, `${summary.council.name} ${metric.label}: ${formatted}`, metric.key)
        : el("span", { class: "comparison-missing-bar" }),
    ]),
  ]);
}

function councilTypeLabel(council) {
  if (council.type === "prefecture") return "県議会";
  if (council.name?.includes("区議会")) return "区議会";
  return "市議会";
}

export function renderPrefectureComparison(summaries, prefecture = "tottori") {
  const ordered = orderedSummaries(summaries);
  if (!ordered.length) return null;

  const metrics = [
    {
      key: "member_count",
      label: "議員数",
      format: formatPeople,
      note: "議員名簿の掲載人数",
    },
    {
      key: "population",
      profileKey: "population",
      label: "人口",
      format: formatPeople,
      note: "profile入力済みの人口",
    },
    {
      key: "population_per_member",
      label: "議員1人あたり住民数",
      format: formatPeople,
      note: "人口 ÷ 議員数",
    },
    {
      key: "fiscal_index",
      profileKey: "fiscal_index",
      label: "財政力指数",
      format: formatDecimal,
      domain: 1,
      note: "1.0を目安として表示",
    },
  ];

  return el("section", { class: "viz-panel comparison-panel" }, [
    el("div", { class: "viz-heading-row" }, [
      el("div", {}, [
        el("h2", { class: "section-title" }, "5議会くらべ"),
        el(
          "p",
          { class: "viz-lead" },
          "棒は各指標の大きさを見比べるための目安です。並び順は県→市の固定順です。",
        ),
      ]),
    ]),
    el("div", { class: "comparison-metrics" }, metrics.map((metric) => {
      const domain = maxMetricValue(ordered, metric);
      const average = cityAverage(ordered, metric);
      return el("section", { class: "comparison-metric" }, [
        el("div", { class: "comparison-metric-head" }, [
          el("h3", {}, metric.label),
          el("span", { class: "comparison-note" }, metric.note),
        ]),
        el("div", { class: "comparison-rows" },
          ordered.map((summary) => renderComparisonRow(summary, metric, domain, average)),
        ),
        el("p", { class: "comparison-source-link" }, metricSourceNode(ordered, metric)),
      ]);
    })),
  ]);
}

export function renderPrefectureComparisonPage(root, summaries, prefecture = "tottori") {
  root.innerHTML = "";
  root.appendChild(
    renderPrefectureComparison(summaries, prefecture)
      || el("p", { class: "empty-message" }, "比較に使うデータを読み込めませんでした。"),
  );
}
