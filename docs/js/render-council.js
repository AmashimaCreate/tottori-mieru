import { dataQualityPanel } from "./data-quality.js?v=20260615-external-icons-v2";
import { renderFinanceSection } from "./render-finance.js?v=20260615-no-member-photos-v1";
import { renderFactionCompositionChart } from "./render-faction-chart.js?v=20260615-no-member-photos-v1";
import { formatDecimal, formatPeople, formatYen } from "./render-profile.js?v=20260615-no-member-photos-v1";
import { renderProfileVisualization } from "./render-profile-viz.js?v=20260615-no-member-photos-v1";
import {
  hasMemberVoteLayer,
  hasResultOnlyVoteLayer,
  renderCouncilVoteSection,
  renderResultOnlyVoteCard,
  renderVoteAvailabilityNotice,
  sortedVotesByDate,
} from "./render-votes.js?v=20260615-ai-links-anchor-v1";
import {
  renderCommitteeView,
  renderKaihaView,
  kaihaColor,
  memberFaction,
  renderRoleView,
  renderTermView,
} from "./render-members.js?v=20260615-no-member-photos-v1";
import { memberPath } from "./router.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderCouncilPage(root, state, filteredMembers) {
  root.innerHTML = "";
  if (isStageOneCouncil(state)) {
    renderStageOneCouncilPage(root, state, filteredMembers);
    return;
  }

  root.appendChild(dataQualityPanel({
    membersMeta: state.membersMeta,
    speechesMeta: state.speechesMeta,
    votesMeta: state.votesMeta,
    council: state.currentCouncil,
  }));

  if (state.view === "votes") {
    root.appendChild(renderCouncilVoteSection(
      state.votes,
      state.votesMeta,
      state.currentCouncil,
      state.members,
      state.route,
    ));
    return;
  }

  const factionChart = renderFactionCompositionChart(state.members, state.membersMeta);
  if (factionChart) root.appendChild(factionChart);

  const profileViz = renderProfileVisualization(state.profile, state.councilSummaries);
  if (profileViz) root.appendChild(profileViz);

  const former = groupFormerSpeeches(state.speeches);
  if (former.length) {
    root.appendChild(renderFormerSpeeches(former));
  }

  const listRoot = el("div", { class: "member-list-root" });
  root.appendChild(listRoot);

  if (state.query.trim() && filteredMembers.length === 0) {
    listRoot.appendChild(
      el("p", { class: "empty-message" }, "該当する議員はいません。"),
    );
    return;
  }

  if (state.view === "kaiha") renderKaihaView(listRoot, filteredMembers);
  else if (state.view === "committee") renderCommitteeView(listRoot, filteredMembers);
  else if (state.view === "role") renderRoleView(listRoot, filteredMembers);
  else if (state.view === "term") renderTermView(listRoot, filteredMembers);
}

function isStageOneCouncil(state) {
  return state.currentCouncil?.status === "active";
}

function renderStageOneCouncilPage(root, state, filteredMembers) {
  root.appendChild(renderCouncilSectionTabs(state));

  if (state.councilSection === "members") {
    root.appendChild(renderRecentVoteHighlights(state));
    if (state.view === "votes") {
      root.appendChild(renderStageTabContent(state, filteredMembers));
      return;
    }

    root.appendChild(renderFaceLineupSection(filteredMembers, state));

    const pastRecords = renderPastRecordsDetails(state);
    if (pastRecords) root.appendChild(pastRecords);
    return;
  }

  root.appendChild(renderAreaOverview(state));

  const timeseriesSection = renderTimeseriesSection(state);
  if (timeseriesSection) root.appendChild(timeseriesSection);

  const officialLinks = renderOfficialLinksSection(state.currentCouncil);
  if (officialLinks) root.appendChild(officialLinks);
}

function renderAreaOverview(state) {
  const children = [renderCouncilHero(state)];
  const financeSection = renderFinanceSection(state.finance);
  if (financeSection) children.push(financeSection);
  return el("section", { class: "area-overview-card page-card" }, children);
}

function renderCouncilSectionTabs(state) {
  const tabs = [
    ["area", state.currentCouncil?.type === "prefecture" ? "県のデータ" : "地域データ"],
    ["members", "議員データ"],
  ];
  const current = state.councilSection || "area";
  return el("nav", { class: "council-section-tabs page-card", "aria-label": "議会ページの大きな切り替え" }, [
    el("div", { class: "council-section-tab-list", role: "tablist" }, tabs.map(([section, label]) =>
      el("button", {
        type: "button",
        class: `council-section-tab ${current === section ? "is-active" : ""}`,
        role: "tab",
        "aria-selected": current === section ? "true" : "false",
        onclick: () => {
          window.dispatchEvent(
            new CustomEvent("council:section-change", { detail: { section } }),
          );
        },
      }, label),
    )),
    el("p", { class: "council-section-help" },
      current === "members"
        ? "議員の顔ぶれ、会派、議決の記録を見ます。"
        : "人口・予算・統計の変化など、この地域の基本データを見ます。",
    ),
  ]);
}

function renderCouncilHero(state) {
  const profile = state.profile || {};
  const population = profile.population;
  const budget = profile.budget_general_yen;
  const fiscalIndex = profile.fiscal_index;
  const perCapita = profile.per_capita || {};
  const areaName = areaNameForCouncil(state.currentCouncil);
  const areaType = areaTypeLabel(state.currentCouncil);

  return el("div", { class: "council-hero" }, [
    el("div", { class: "hero-copy" }, [
      el("p", { class: "eyebrow" }, state.currentCouncil.type === "prefecture" ? "この県の今" : "この街の今"),
      el("h2", {}, `${areaName}の今`),
      el("p", {}, `${areaName}の規模と議会の形を見ます。`),
    ]),
    el("div", { class: "hero-metrics" }, [
      heroMetric("人口", formatPeople(population?.value), `${areaType}の規模`),
      heroMetric("一般会計予算", formatYen(budget?.value), "年間のお金の大きさ"),
      heroMetric("議員数", formatPeople(state.members.length), "現在の名簿"),
    ]),
    el("details", { class: "profile-details" }, [
      el("summary", {}, "基礎データをもう少し見る"),
      el("dl", { class: "profile-detail-list" }, [
        detailPair("世帯数", formatPeople(profile.households?.value)?.replace("人", "世帯")),
        detailPair("財政力指数", formatDecimal(fiscalIndex?.value), "1.0以上なら国からの仕送りなしでやっていける目安"),
        detailPair("議員1人あたり住民数", formatPeople(perCapita.population_per_member)),
        detailPair(`${areaType}債残高(1人あたり)`, formatYen(perCapita.debt_per_capita_yen)),
      ].filter(Boolean).flat()),
      sourceLine("基礎データ", [
        profileSource(population, "人口"),
        profileSource(budget, "予算"),
        state.membersMeta?.source_url
          ? { label: "議員名簿", url: state.membersMeta.source_url }
          : null,
      ]),
    ]),
  ]);
}

function heroMetric(label, value, note) {
  if (!value) return null;
  return el("article", { class: "hero-metric" }, [
    el("span", { class: "hero-metric-label" }, label),
    el("strong", { class: "hero-metric-value" }, value),
    el("span", { class: "hero-metric-note" }, note),
  ]);
}

const TIMESERIES_CHARTS = [
  ["population_total", "人口", "人口総数"],
  ["aging_rate", "高齢化率", "高齢化率"],
  ["births", "出生数", "出生数"],
  ["social_change", "社会増減", "社会増減"],
  ["expenditure_total", "歳出決算", "歳出決算総額"],
  ["fiscal_index", "財政力指数", "財政力指数"],
  ["pref_assembly_turnout", "投票率(県議選)", "投票率(県議選)"],
];

function renderTimeseriesSection(state) {
  const timeseries = state.timeseries;
  if (!timeseries?.indicators) return null;
  const areaName = areaNameForCouncil(state.currentCouncil);
  const cards = TIMESERIES_CHARTS
    .map(([key, shortLabel, title]) =>
      renderTimeseriesCard(key, shortLabel, title, timeseries.indicators[key]),
    )
    .filter(Boolean);
  if (!cards.length) return null;

  const eyebrow = state.currentCouncil?.type === "prefecture"
    ? "この県の変化"
    : "この街の変化";

  return el("section", { class: "timeseries-section page-card" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, eyebrow),
        el("h2", { class: "section-title" }, `${areaName}の変化`),
      ]),
    ]),
    el("p", { class: "timeseries-note" }, "今=自治体の最新公表値 / 変化=国の確定統計。年次が異なるため、同じ値にはなりません。"),
    el("div", { class: "timeseries-grid" }, cards),
    el("p", { class: "section-source timeseries-source" }, "出典: 政府統計の総合窓口(e-Stat)社会・人口統計体系。確定統計のため最新年は1〜3年前です。"),
  ]);
}

function renderTimeseriesCard(key, shortLabel, title, indicator) {
  const values = cleanTimeseriesValues(indicator?.values);
  if (values.length < 2) return null;
  const summary = timeseriesSummary(indicator, values);
  const trend = trendClass(summary.delta);
  const periodLabel = `${summary.first.year}〜${summary.latest.year}年`;
  const headline = `${shortLabel} ${formatTimeseriesValue(key, summary.latest.value)}(${summary.latest.year})`;

  return el("article", { class: "timeseries-chart-card" }, [
    el("div", { class: "timeseries-chart-head" }, [
      el("h3", {}, title),
      el("p", {}, headline),
      el("span", { class: `timeseries-delta-chip ${trend}` }, `${periodLabel}で ${formatTimeseriesDelta(key, summary.delta)}`),
    ]),
    isSparseElectionSeries(key)
      ? renderSparsePointChartSvg(key, title, values, trend)
      : renderLineChartSvg(key, title, values, trend),
    isSparseElectionSeries(key)
      ? el("p", { class: "timeseries-sparse-note" }, "選挙年のみを点と破線で表示しています。")
      : null,
    renderTimeseriesTable(key, title, values),
  ]);
}

function timeseriesSummary(indicator, values) {
  const fallbackFirst = values[0];
  const fallbackLatest = values[values.length - 1];
  const first = validSummaryPoint(indicator?.first) || {
    year: fallbackFirst.year,
    value: fallbackFirst.value,
  };
  const latest = validSummaryPoint(indicator?.latest) || {
    year: fallbackLatest.year,
    value: fallbackLatest.value,
  };
  const delta = typeof indicator?.delta === "number"
    ? indicator.delta
    : latest.value - first.value;
  const deltaPct = typeof indicator?.delta_pct === "number" ? indicator.delta_pct : null;
  return { first, latest, delta, deltaPct };
}

function validSummaryPoint(point) {
  if (!point || !Number.isInteger(point.year) || typeof point.value !== "number") return null;
  return { year: point.year, value: point.value };
}

function trendClass(delta) {
  if (typeof delta !== "number" || delta === 0) return "is-flat";
  return delta > 0 ? "is-increase" : "is-decrease";
}

function cleanTimeseriesValues(values) {
  if (!Array.isArray(values)) return [];
  return values
    .filter((item) => Number.isInteger(item?.year) && typeof item?.value === "number")
    .sort((a, b) => a.year - b.year);
}

function renderLineChartSvg(key, title, values, trend = "is-flat") {
  const width = 320;
  const height = 170;
  const pad = { top: 18, right: 12, bottom: 30, left: 42 };
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const years = values.map((item) => item.year);
  const domain = chartYDomain(key, values);
  const x = (index) => pad.left + (innerWidth * index) / Math.max(1, values.length - 1);
  const y = (value) => pad.top + ((domain.max - value) / (domain.max - domain.min)) * innerHeight;
  const points = values.map((item, index) => `${x(index).toFixed(1)},${y(item.value).toFixed(1)}`).join(" ");
  const svg = svgEl("svg", {
    class: "timeseries-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${title}の${values[0].year}年から${values[values.length - 1].year}年までの推移`,
  });

  svg.appendChild(svgEl("line", {
    class: "timeseries-axis",
    x1: pad.left,
    y1: pad.top + innerHeight,
    x2: pad.left + innerWidth,
    y2: pad.top + innerHeight,
  }));
  svg.appendChild(svgEl("line", {
    class: "timeseries-axis",
    x1: pad.left,
    y1: pad.top,
    x2: pad.left,
    y2: pad.top + innerHeight,
  }));
  svg.appendChild(svgEl("line", {
    class: "timeseries-grid-line",
    x1: pad.left,
    y1: pad.top,
    x2: pad.left + innerWidth,
    y2: pad.top,
  }));
  if (key === "fiscal_index") {
    svg.appendChild(svgEl("line", {
      class: "timeseries-basis-line",
      x1: pad.left,
      y1: y(1),
      x2: pad.left + innerWidth,
      y2: y(1),
    }));
    svg.appendChild(svgEl("text", {
      class: "timeseries-basis-label",
      x: pad.left + innerWidth - 2,
      y: Math.max(12, y(1) - 4),
      "text-anchor": "end",
    }, "1.0"));
  }
  svg.appendChild(svgEl("text", {
    class: "timeseries-y-label",
    x: pad.left - 8,
    y: pad.top + 4,
    "text-anchor": "end",
  }, formatAxisValue(key, domain.max)));
  svg.appendChild(svgEl("text", {
    class: "timeseries-y-label",
    x: pad.left - 8,
    y: pad.top + innerHeight,
    "text-anchor": "end",
  }, formatAxisValue(key, domain.min)));
  svg.appendChild(svgEl("polyline", {
    class: `timeseries-line ${trend}`,
    points,
  }));
  values.forEach((item, index) => {
    const circle = svgEl("circle", {
      class: `timeseries-point ${trend}`,
      cx: x(index),
      cy: y(item.value),
      r: 3.5,
      tabindex: "0",
    });
    circle.appendChild(svgEl("title", {}, `${item.year}: ${formatTimeseriesValue(key, item.value)}`));
    svg.appendChild(circle);
  });
  svg.appendChild(svgEl("text", {
    class: "timeseries-x-label",
    x: pad.left,
    y: height - 8,
    "text-anchor": "start",
  }, String(years[0])));
  svg.appendChild(svgEl("text", {
    class: "timeseries-x-label",
    x: pad.left + innerWidth,
    y: height - 8,
    "text-anchor": "end",
  }, String(years[years.length - 1])));

  return svg;
}

function renderSparsePointChartSvg(key, title, values, trend = "is-flat") {
  const width = 320;
  const height = 170;
  const pad = { top: 18, right: 12, bottom: 30, left: 42 };
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const years = values.map((item) => item.year);
  const minYear = years[0];
  const maxYear = years[years.length - 1];
  const domain = chartYDomain(key, values);
  const yearSpan = Math.max(1, maxYear - minYear);
  const x = (year) => pad.left + (innerWidth * (year - minYear)) / yearSpan;
  const y = (value) => pad.top + ((domain.max - value) / (domain.max - domain.min)) * innerHeight;
  const points = values.map((item) => `${x(item.year).toFixed(1)},${y(item.value).toFixed(1)}`).join(" ");
  const svg = svgEl("svg", {
    class: "timeseries-chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${title}の${values[0].year}年から${values[values.length - 1].year}年までの選挙年ごとの推移`,
  });

  svg.appendChild(svgEl("line", {
    class: "timeseries-axis",
    x1: pad.left,
    y1: pad.top + innerHeight,
    x2: pad.left + innerWidth,
    y2: pad.top + innerHeight,
  }));
  svg.appendChild(svgEl("line", {
    class: "timeseries-axis",
    x1: pad.left,
    y1: pad.top,
    x2: pad.left,
    y2: pad.top + innerHeight,
  }));
  svg.appendChild(svgEl("line", {
    class: "timeseries-grid-line",
    x1: pad.left,
    y1: pad.top,
    x2: pad.left + innerWidth,
    y2: pad.top,
  }));
  svg.appendChild(svgEl("line", {
    class: "timeseries-grid-line",
    x1: pad.left,
    y1: pad.top + innerHeight / 2,
    x2: pad.left + innerWidth,
    y2: pad.top + innerHeight / 2,
  }));
  svg.appendChild(svgEl("polyline", {
    class: `timeseries-sparse-line ${trend}`,
    points,
  }));
  values.forEach((item) => {
    const circle = svgEl("circle", {
      class: `timeseries-point is-sparse ${trend}`,
      cx: x(item.year),
      cy: y(item.value),
      r: 4.2,
      tabindex: "0",
    });
    circle.appendChild(svgEl("title", {}, `${item.year}: ${formatTimeseriesValue(key, item.value)}`));
    svg.appendChild(circle);
  });
  svg.appendChild(svgEl("text", {
    class: "timeseries-y-label",
    x: pad.left - 8,
    y: pad.top + 4,
    "text-anchor": "end",
  }, formatAxisValue(key, domain.max)));
  svg.appendChild(svgEl("text", {
    class: "timeseries-y-label",
    x: pad.left - 8,
    y: pad.top + innerHeight,
    "text-anchor": "end",
  }, formatAxisValue(key, domain.min)));
  svg.appendChild(svgEl("text", {
    class: "timeseries-x-label",
    x: pad.left,
    y: height - 8,
    "text-anchor": "start",
  }, String(minYear)));
  svg.appendChild(svgEl("text", {
    class: "timeseries-x-label",
    x: pad.left + innerWidth,
    y: height - 8,
    "text-anchor": "end",
  }, String(maxYear)));

  return svg;
}

function isSparseElectionSeries(key) {
  return key === "pref_assembly_turnout";
}

function chartYDomain(key, values) {
  if (key === "fiscal_index") return { min: 0, max: 1 };
  if (isTurnoutSeries(key)) return { min: 0, max: 100 };
  const numbers = values.map((item) => item.value);
  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  const first = numbers[0];
  const last = numbers[numbers.length - 1];
  const spread = Math.max(1, max - min);
  const change = Math.abs(last - first);
  const pad = Math.max(spread * 0.3, change * 0.5, Math.abs(first) * 0.03, key === "aging_rate" ? 0.5 : 1);
  if (key === "social_change") {
    const edge = Math.max(Math.abs(min), Math.abs(max), 1) * 1.2;
    return { min: Math.floor(-edge), max: Math.ceil(edge) };
  }
  return {
    min: Math.max(0, Math.floor(min - pad)),
    max: Math.ceil(max + pad),
  };
}

function renderTimeseriesTable(key, title, values) {
  const columns = timeseriesTableColumns(key);
  return el("details", { class: "timeseries-values" }, [
    el("summary", {}, `${title}の値を見る`),
    el("table", {}, [
      el("thead", {}, el("tr", {}, [
        ...columns.map((column) => el("th", { scope: "col" }, column.label)),
      ])),
      el("tbody", {}, values.map((item) =>
        el("tr", {}, columns.map((column) =>
          el("td", {}, column.value(item)),
        )),
      )),
    ]),
  ]);
}

function timeseriesTableColumns(key) {
  const base = [
    { label: "年", value: (item) => String(item.year) },
    { label: "値", value: (item) => formatTimeseriesValue(key, item.value) },
  ];
  if (key === "aging_rate") {
    return [
      ...base,
      { label: "年少", value: (item) => formatPeople(item.young_population) || "" },
      { label: "生産年齢", value: (item) => formatPeople(item.working_age_population) || "" },
      { label: "老年", value: (item) => formatPeople(item.elderly_population) || "" },
    ];
  }
  if (key === "social_change") {
    return [
      ...base,
      { label: "転入", value: (item) => formatPeople(item.in_migration) || "" },
      { label: "転出", value: (item) => formatPeople(item.out_migration) || "" },
    ];
  }
  return base;
}

function formatTimeseriesValue(key, value) {
  if (typeof value !== "number") return "";
  if (key === "fiscal_index") {
    return value.toLocaleString("ja-JP", { maximumFractionDigits: 3 });
  }
  if (key === "aging_rate" || isTurnoutSeries(key)) {
    return `${value.toLocaleString("ja-JP", { maximumFractionDigits: 1 })}%`;
  }
  if (key === "expenditure_total") {
    return formatOkuYen(value);
  }
  return `${value.toLocaleString("ja-JP")}人`;
}

function formatTimeseriesDelta(key, value) {
  if (typeof value !== "number") return "";
  if (value === 0) {
    if (key === "fiscal_index") return "0";
    if (key === "aging_rate" || isTurnoutSeries(key)) return "0ポイント";
    if (key === "expenditure_total") return "0億円";
    return "0人";
  }
  const sign = value < 0 ? "−" : "+";
  const abs = Math.abs(value);
  if (key === "fiscal_index") {
    return `${sign}${abs.toLocaleString("ja-JP", { maximumFractionDigits: 3 })}`;
  }
  if (key === "aging_rate" || isTurnoutSeries(key)) {
    return `${sign}${abs.toLocaleString("ja-JP", { maximumFractionDigits: 1 })}ポイント`;
  }
  if (key === "expenditure_total") {
    return `${sign}${formatOkuYen(abs)}`;
  }
  return `${sign}${Math.round(abs).toLocaleString("ja-JP")}人`;
}

function formatAxisValue(key, value) {
  if (key === "fiscal_index") {
    return value.toLocaleString("ja-JP", { maximumFractionDigits: 1 });
  }
  if (key === "aging_rate" || isTurnoutSeries(key)) {
    return `${value.toLocaleString("ja-JP", { maximumFractionDigits: 0 })}%`;
  }
  if (key === "expenditure_total") {
    return `${Math.round(value / 100000000).toLocaleString("ja-JP")}億`;
  }
  if (Math.abs(value) >= 10000) {
    return `${Math.round(value / 10000).toLocaleString("ja-JP")}万`;
  }
  return Math.round(value).toLocaleString("ja-JP");
}

function formatOkuYen(value) {
  if (typeof value !== "number") return "";
  return `${Math.round(value / 100000000).toLocaleString("ja-JP")}億円`;
}

function isTurnoutSeries(key) {
  return key === "pref_assembly_turnout" || key === "pref_governor_turnout";
}

function svgEl(tag, attrs = {}, children = []) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.setAttribute("class", value);
    else if (value !== undefined && value !== null) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function detailPair(label, value, note = null) {
  if (!value) return null;
  return [
    el("dt", {}, label),
    el("dd", {}, [
      el("span", {}, value),
      note ? el("small", {}, note) : null,
    ]),
  ];
}

function profileSource(item, fallbackLabel) {
  if (!item?.source_url) return null;
  return {
    label: item.source_name || fallbackLabel,
    url: item.source_url,
  };
}

function renderFaceLineupSection(members, state) {
  const isFiltered = state.query.trim().length > 0;
  const body = renderMemberViewBody(members, state, isFiltered);
  return el("section", { class: "face-lineup-section" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "決めている人たち"),
        el("h2", { class: "section-title" }, isFiltered ? "検索結果" : "現在の議員"),
      ]),
      el("p", { class: "section-count" }, `${members.length}人`),
    ]),
    renderCompactFactionChart(state.members),
    renderMemberViewSwitcher(state),
    body,
    sourceLine("議員名簿", [
      state.membersMeta?.source_url
        ? { label: state.membersMeta.source_name || "公式名簿", url: state.membersMeta.source_url }
        : null,
    ]),
  ]);
}

function renderMemberViewBody(members, state, isFiltered) {
  if (isFiltered && members.length === 0) {
    return el("p", { class: "empty-message" }, "該当する議員はいません。");
  }

  if (state.view === "committee" || state.view === "role" || state.view === "term") {
    const listRoot = el("div", { class: "member-list-root redesigned-tab-panel inline-member-tab-panel" });
    if (state.view === "committee") renderCommitteeView(listRoot, members);
    else if (state.view === "role") renderRoleView(listRoot, members);
    else renderTermView(listRoot, members);
    return listRoot;
  }

  const groups = groupMembersByFaction(members);
  return el("div", { class: "face-lineup-groups" }, groups.map(([faction, list]) =>
    renderFactionFaceGroup(faction, list, state),
  ));
}

function renderMemberViewSwitcher(state) {
  const tabs = [
    ["kaiha", "会派"],
    ["committee", "委員会"],
    ["role", "役職"],
    ["term", "当選回数"],
  ];
  return el("div", { class: "member-view-switcher" }, [
    el("div", { class: "stage-tabs member-view-tabs", role: "tablist", "aria-label": "議員データの表示切り替え" },
      tabs.map(([view, label]) =>
        el("button", {
          type: "button",
          class: `view-tab ${state.view === view ? "is-active" : ""}`,
          "data-view": view,
          role: "tab",
          "aria-selected": state.view === view ? "true" : "false",
          onclick: () => {
            window.dispatchEvent(
              new CustomEvent("council:view-change", { detail: { view } }),
            );
          },
        }, label),
      ),
    ),
    renderInlineMemberSearch(state),
  ]);
}

function renderInlineMemberSearch(state) {
  const clearButton = el("button", {
    type: "button",
    class: "search-clear",
    hidden: state.query.length === 0 ? "" : null,
    "aria-label": "検索をクリア",
    onclick: () => {
      window.dispatchEvent(
        new CustomEvent("council:query-change", { detail: { query: "" } }),
      );
    },
  }, "×");

  return el("div", { class: "search-row stage-search-row inline-member-search" }, [
    el("input", {
      type: "search",
      class: "search-input",
      placeholder: `${state.currentCouncil?.name || "議員"}を検索`,
      autocomplete: "off",
      value: state.query,
      oninput: (event) => {
        window.dispatchEvent(
          new CustomEvent("council:query-change", {
            detail: { query: event.target.value },
          }),
        );
      },
    }),
    clearButton,
    el("span", { class: "match-count" }, state.query.trim()
      ? `${state.members.length}人中 ${filteredMemberCount(state)}人を表示`
      : ""),
  ]);
}

function renderCompactFactionChart(members) {
  const groups = groupMembersByFaction(members);
  const total = groups.reduce((sum, [, list]) => sum + list.length, 0);
  if (!total) return null;

  return el("div", { class: "compact-faction-chart" }, [
    el("div", { class: "compact-faction-head" }, [
      el("h3", {}, "会派構成"),
      el("p", {}, `合計${total}人。色は識別用です。`),
    ]),
    el("div", { class: "compact-faction-bar", role: "img", "aria-label": `会派別人数。合計${total}人。` },
      groups.map(([faction, list]) =>
        el("button", {
          type: "button",
          class: "compact-faction-segment",
          style: `--kaiha-color: ${kaihaColor(faction)}; --segment-width: ${(list.length / total) * 100}%;`,
          "aria-label": `${faction} ${list.length}人。顔ぶれへ移動`,
          onclick: () => requestFactionFocus(faction),
        }, `${list.length}人`),
      ),
    ),
    el("div", { class: "compact-faction-legend" }, groups.map(([faction, list]) =>
      el("button", {
        type: "button",
        style: `--kaiha-color: ${kaihaColor(faction)}; --faction-color: ${kaihaColor(faction)};`,
        onclick: () => requestFactionFocus(faction),
      }, [
        el("span", { class: "faction-chart-swatch", "aria-hidden": "true" }),
        el("span", {}, faction),
        el("strong", {}, `${list.length}人`),
      ]),
    )),
  ]);
}

function requestFactionFocus(faction) {
  window.dispatchEvent(
    new CustomEvent("council:faction-focus", { detail: { faction } }),
  );
}

function groupMembersByFaction(members) {
  const map = new Map();
  for (const member of members || []) {
    const faction = memberFaction(member);
    if (!map.has(faction)) map.set(faction, []);
    map.get(faction).push(member);
  }
  return [...map.entries()];
}

function renderFactionFaceGroup(faction, members, state) {
  return el("section", {
    class: "kaiha-group ux-kaiha-face-group",
    "data-faction": faction,
    tabindex: "-1",
    style: `--kaiha-color: ${kaihaColor(faction)};`,
  }, [
    el("div", { class: "kaiha-header compact" }, [
      el("h3", { class: "kaiha-name" }, faction),
      el("span", { class: "kaiha-count" }, `${members.length}人`),
    ]),
    el("div", { class: "face-grid" }, members.map((member) =>
      renderFaceCard(member, state),
    )),
  ]);
}

function renderFaceCard(member, state) {
  const faction = memberFaction(member);
  const term = typeof member.elected_count === "number"
    ? `当選 ${member.elected_count} 回`
    : "当選回数: データなし";
  const district = member.district
    ? el("span", { class: "face-district" }, member.district)
    : null;
  return el("a", {
    class: "face-card",
    href: memberPath(
      state.currentCouncil.prefecture || state.route.prefecture || "tottori",
      state.currentCouncil.id,
      member.id,
    ),
    style: `--kaiha-color: ${kaihaColor(faction)};`,
  }, [
    el("strong", { class: "face-name" }, member.name),
    district,
    el("span", { class: "face-faction" }, faction),
    el("span", { class: "face-term" }, term),
  ]);
}

function renderRecentVoteHighlights(state) {
  if (hasResultOnlyVoteLayer(state.currentCouncil, state.votesMeta, state.votes)) {
    const highlighted = sortedVotesByDate(state.votes).slice(0, 3);
    const tabButton = renderVotesTabButton("議決一覧へ");
    return el("section", { class: "recent-votes page-card" }, [
      el("div", { class: "section-heading-row" }, [
        el("div", {}, [
          el("p", { class: "eyebrow" }, "最近決まったこと"),
          el("h2", { class: "section-title" }, "直近の議決結果"),
        ]),
        el("span", { class: "stage-link-wrap" }, [tabButton]),
      ]),
      el("p", { class: "muted" }, "議員ごとの賛否ではなく、議案ごとの議決結果を表示しています。"),
      el("div", { class: "vote-highlight-grid result-only-highlight-grid" },
        highlighted.map(renderResultOnlyVoteCard),
      ),
      sourceLine("議決", [
        highlighted.find((vote) => vote.source_url)
          ? { label: "議決結果PDF", url: highlighted.find((vote) => vote.source_url).source_url }
          : null,
      ]),
    ]);
  }

  if (!hasMemberVoteLayer(state.currentCouncil, state.votesMeta, state.votes)) {
    return el("section", { class: "recent-votes page-card is-compact" }, [
      el("div", { class: "section-heading-row" }, [
        el("div", {}, [
          el("p", { class: "eyebrow" }, "最近決まったこと"),
          el("h2", { class: "section-title" }, "議決結果"),
        ]),
      ]),
      renderVoteAvailabilityNotice(state.currentCouncil),
    ]);
  }

  const votes = [...(state.votes || [])].sort((a, b) => {
    const dateCompare = (b.date || "").localeCompare(a.date || "");
    if (dateCompare) return dateCompare;
    return (a.bill_title || "").localeCompare(b.bill_title || "", "ja");
  });
  const latestDate = votes[0].date;
  const latestVotes = votes.filter((vote) => vote.date === latestDate);
  const divided = latestVotes.filter(isDividedVote);
  const highlighted = (divided.length ? divided : latestVotes).slice(0, 3);

  const tabButton = renderVotesTabButton("議決一覧へ");

  return el("section", { class: "recent-votes page-card" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "最近決まったこと"),
        el("h2", { class: "section-title" }, "直近の議決ハイライト"),
      ]),
      el("span", { class: "stage-link-wrap" }, [tabButton]),
    ]),
    el("p", { class: "muted" }, divided.length
      ? "賛否が分かれた議決を優先表示しています。"
      : "直近の議決を表示しています。"),
    el("div", { class: "vote-highlight-grid" }, highlighted.map(renderVoteHighlightCard)),
    sourceLine("議決", [
      highlighted.find((vote) => vote.source_url)
        ? { label: "議員別賛否PDF", url: highlighted.find((vote) => vote.source_url).source_url }
        : null,
    ]),
  ]);
}

function renderVotesTabButton(label) {
  const tabButton = el("button", { type: "button", class: "text-button" }, label);
  tabButton.addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("council:show-votes"));
  });
  return tabButton;
}

function renderOfficialLinksSection(council) {
  const links = Array.isArray(council?.official_links)
    ? council.official_links.filter((link) => link?.label && link?.url)
    : [];
  if (!links.length) return null;
  return el("section", { class: "official-links-section page-card" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "公式情報"),
        el("h2", { class: "section-title" }, "公式情報へのリンク"),
      ]),
    ]),
    el("div", { class: "official-link-grid" }, links.map((link) =>
      el("a", {
        class: "official-link-card",
        href: link.url,
        target: "_blank",
        rel: "noopener",
      }, [
        el("span", {}, link.label),
        el("small", {}, "公式サイトで確認"),
      ]),
    )),
  ]);
}

function filteredMemberCount(state) {
  const query = state.query.trim().toLowerCase();
  if (!query) return state.members.length;
  return state.members.filter((member) => {
    const haystack = [
      member.name,
      member.name_kana,
      member.faction,
      ...(member.committees || []),
      ...(member.positions || []),
    ].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(query);
  }).length;
}

function renderStageTabContent(state, filteredMembers) {
  const section = el("section", { class: "stage-tab-content" });
  if (state.view === "votes") {
    section.appendChild(renderCouncilVoteSection(
      state.votes,
      state.votesMeta,
      state.currentCouncil,
      state.members,
      state.route,
    ));
    return section;
  }

  const listRoot = el("div", { class: "member-list-root redesigned-tab-panel" });
  section.appendChild(listRoot);
  if (state.query.trim() && filteredMembers.length === 0) {
    listRoot.appendChild(
      el("p", { class: "empty-message" }, "該当する議員はいません。"),
    );
    return section;
  }
  if (state.view === "committee") renderCommitteeView(listRoot, filteredMembers);
  else if (state.view === "role") renderRoleView(listRoot, filteredMembers);
  else if (state.view === "term") renderTermView(listRoot, filteredMembers);
  return section;
}

function renderVoteHighlightCard(vote) {
  const counts = voteCounts(vote);
  return el("article", { class: "vote-highlight-card" }, [
    el("span", { class: "vote-date" }, vote.date || "日付なし"),
    el("h3", {}, vote.bill_title || "議案名なし"),
    el("div", { class: "vote-highlight-counts" }, [
      el("span", { class: "vote-badge is-yes" }, `○ 賛成 ${counts["賛成"] || 0}`),
      el("span", { class: "vote-badge is-no" }, `× 反対 ${counts["反対"] || 0}`),
    ]),
    el("p", { class: "vote-result" }, `結果: ${vote.result || "結果なし"}`),
  ]);
}

function renderPastRecordsDetails(state) {
  const formerSpeeches = groupFormerSpeeches(state.speeches)
    .map(([label, items]) => ({ label, count: items.length, type: "発言" }));
  const formerVotes = groupFormerVotes(state.votes)
    .map(([label, count]) => ({ label, count, type: "議決" }));
  const records = [...formerSpeeches, ...formerVotes]
    .sort((a, b) => a.label.localeCompare(b.label, "ja"));
  const total = records.reduce((sum, record) => sum + record.count, 0);
  if (!total) return null;

  return el("details", { class: "past-records page-card" }, [
    el("summary", {}, `過去の議員の記録 ${total}件`),
    el("p", { class: "muted" }, "現在の議員名簿と照合できない発言・票です。過去議員や表記揺れの可能性があるため、現職議員ページには混ぜていません。"),
    el("ul", { class: "past-record-list" }, records.map((record) =>
      el("li", {}, `${record.label}: ${record.type} ${record.count}件`),
    )),
  ]);
}

function groupFormerVotes(votes) {
  const map = new Map();
  for (const vote of votes || []) {
    for (const entry of vote.votes_by_member || []) {
      if (entry.member_id) continue;
      const label = entry.member_name || "投票者名不明";
      map.set(label, (map.get(label) || 0) + 1);
    }
  }
  return [...map.entries()];
}

function sourceLine(label, sources) {
  const unique = [];
  const seen = new Set();
  for (const source of sources.filter(Boolean)) {
    const key = source.url || source.label;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(source);
  }
  if (!unique.length) return null;
  const children = [`出典: ${label}（`];
  unique.forEach((source, index) => {
    if (index) children.push(" / ");
    children.push(
      source.url
        ? el("a", { href: source.url, target: "_blank", rel: "noopener" }, source.label)
        : source.label,
    );
  });
  children.push("）");
  return el("p", { class: "section-source" }, children);
}

function voteCounts(vote) {
  const counts = {};
  for (const entry of vote.votes_by_member || []) {
    const value = entry.vote || "不明";
    counts[value] = (counts[value] || 0) + 1;
  }
  return counts;
}

function isDividedVote(vote) {
  const counts = voteCounts(vote);
  return (counts["賛成"] || 0) > 0 && (counts["反対"] || 0) > 0;
}

function groupFormerSpeeches(speeches) {
  const map = new Map();
  for (const speech of speeches || []) {
    if (speech.member_id) continue;
    const label = speech.speaker_label || "発言者名不明";
    if (!map.has(label)) map.set(label, []);
    map.get(label).push(speech);
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], "ja"));
}

function areaNameForCouncil(council) {
  if (!council?.name) return "この地域";
  return council.name
    .replace(/議会$/, "")
    .replace(/市$/, "市")
    .replace(/県$/, "県");
}

function areaTypeLabel(council) {
  if (council?.type === "prefecture") return "県";
  const name = council?.name || "";
  if (name.includes("町議会")) return "町";
  if (name.includes("村議会")) return "村";
  return "市";
}

function renderFormerSpeeches(groups) {
  return el("section", { class: "former-speeches" }, [
    el("h2", { class: "section-title" }, "現名簿外の発言"),
    el("p", { class: "muted" }, "現在の議員名簿と照合できない発言です。過去議員や表記揺れの可能性があるため、現職議員ページには混ぜていません。"),
    el(
      "ul",
      { class: "former-list" },
      groups.map(([label, items]) =>
        el("li", {}, `${label}: ${items.length}件`),
      ),
    ),
  ]);
}
