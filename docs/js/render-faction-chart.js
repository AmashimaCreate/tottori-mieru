import { kaihaColor, memberFaction } from "./render-members.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const SVG_NS = "http://www.w3.org/2000/svg";
const CHART_WIDTH = 1000;
const CHART_HEIGHT = 54;
const BAR_Y = 12;
const BAR_HEIGHT = 28;

function svgEl(tag, attrs = {}, children = []) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== null) {
      node.setAttribute(key, value);
    }
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function groupFactions(members) {
  const map = new Map();
  for (const member of members) {
    const faction = memberFaction(member);
    map.set(faction, (map.get(faction) || 0) + 1);
  }
  return [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name, "ja"));
}

function formatPercent(count, total) {
  if (!total) return "0.0%";
  return `${((count / total) * 100).toFixed(1)}%`;
}

function requestFactionFocus(faction) {
  window.dispatchEvent(
    new CustomEvent("council:faction-focus", { detail: { faction } }),
  );
}

function addSegmentInteraction(node, faction) {
  node.addEventListener("click", () => requestFactionFocus(faction));
  node.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    requestFactionFocus(faction);
  });
}

function renderStackedBar(groups, total) {
  const svg = svgEl("svg", {
    class: "faction-chart-svg",
    viewBox: `0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`,
    role: "img",
    "aria-labelledby": "faction-chart-title faction-chart-desc",
  });

  svg.appendChild(svgEl("title", { id: "faction-chart-title" }, "会派構成チャート"));
  svg.appendChild(
    svgEl(
      "desc",
      { id: "faction-chart-desc" },
      `会派別の人数を横幅で示しています。合計${total}人です。`,
    ),
  );

  let x = 0;
  groups.forEach((group, index) => {
    const isLast = index === groups.length - 1;
    const width = isLast ? CHART_WIDTH - x : (group.count / total) * CHART_WIDTH;
    const rect = svgEl("rect", {
      class: "faction-chart-segment",
      x: String(x),
      y: String(BAR_Y),
      width: String(Math.max(width, 1)),
      height: String(BAR_HEIGHT),
      rx: "6",
      role: "button",
      tabindex: "0",
      fill: kaihaColor(group.name),
      "aria-label": `${group.name} ${group.count}人。会派ビューへ移動`,
    });
    rect.appendChild(svgEl("title", {}, `${group.name}: ${group.count}人`));
    addSegmentInteraction(rect, group.name);
    svg.appendChild(rect);

    if (width >= 84) {
      svg.appendChild(
        svgEl("text", {
          class: "faction-chart-count-label",
          x: String(x + width / 2),
          y: String(BAR_Y + BAR_HEIGHT / 2 + 5),
          "text-anchor": "middle",
        }, `${group.count}人`),
      );
    }
    x += width;
  });

  return svg;
}

function renderLegend(groups, total) {
  return el(
    "ul",
    { class: "faction-chart-legend" },
    groups.map((group) => {
      const button = el("button", {
        type: "button",
        class: "faction-chart-legend-button",
      }, [
        el("span", {
          class: "faction-chart-swatch",
          style: `--faction-color: ${kaihaColor(group.name)};`,
          "aria-hidden": "true",
        }),
        el("span", { class: "faction-chart-name" }, group.name),
        el("span", { class: "faction-chart-count" }, `${group.count}人`),
        el("span", { class: "faction-chart-percent" }, formatPercent(group.count, total)),
      ]);
      button.addEventListener("click", () => requestFactionFocus(group.name));
      return el("li", {}, button);
    }),
  );
}

export function renderFactionCompositionChart(members, membersMeta) {
  const groups = groupFactions(members || []);
  const total = groups.reduce((sum, group) => sum + group.count, 0);
  if (!total) return null;

  const source = membersMeta?.source_url
    ? el("a", { href: membersMeta.source_url, target: "_blank", rel: "noopener" }, "議員名簿")
    : "議員名簿";

  return el("section", { class: "viz-panel faction-composition-panel" }, [
    el("div", { class: "viz-heading-row" }, [
      el("div", {}, [
        el("h2", { class: "section-title" }, "会派構成"),
        el(
          "p",
          { class: "viz-lead" },
          `会派別の人数を横幅で示しています。並び順は会派名順、合計${total}人です。`,
        ),
      ]),
      el("p", { class: "viz-source" }, ["出典: ", source]),
    ]),
    el("div", { class: "faction-chart-svg-wrap" }, renderStackedBar(groups, total)),
    renderLegend(groups, total),
    el(
      "p",
      { class: "viz-note" },
      "色は会派の区別用です。",
    ),
  ]);
}
