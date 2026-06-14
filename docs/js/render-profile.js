import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function formatNumber(value) {
  if (typeof value !== "number") return null;
  return value.toLocaleString("ja-JP");
}

export function formatPeople(value) {
  const formatted = formatNumber(value);
  return formatted ? `${formatted}人` : null;
}

export function formatHouseholds(value) {
  const formatted = formatNumber(value);
  return formatted ? `${formatted}世帯` : null;
}

export function formatYen(value) {
  if (typeof value !== "number") return null;
  if (value >= 100000000) {
    const oku = value / 100000000;
    const formatted = oku.toLocaleString("ja-JP", {
      maximumFractionDigits: Number.isInteger(oku) ? 0 : 1,
    });
    return `${formatted}億円`;
  }
  if (value >= 10000) {
    const man = value / 10000;
    const formatted = man.toLocaleString("ja-JP", {
      maximumFractionDigits: Number.isInteger(man) ? 0 : 1,
    });
    return `${formatted}万円`;
  }
  return `${value.toLocaleString("ja-JP")}円`;
}

export function formatDecimal(value) {
  if (typeof value !== "number") return null;
  return value.toLocaleString("ja-JP", { maximumFractionDigits: 2 });
}

export function sourceLink(url, label = "出典") {
  if (!url) return null;
  return el(
    "a",
    {
      class: "profile-source",
      href: url,
      target: "_blank",
      rel: "noopener",
    },
    label,
  );
}

function profileItem(label, value, sources = []) {
  if (!value) return null;
  const sourceNodes = sources.filter(Boolean);
  return el("div", { class: "profile-item" }, [
    el("span", { class: "profile-label" }, label),
    el("span", { class: "profile-value" }, value),
    sourceNodes.length
      ? el("span", { class: "profile-sources" }, sourceNodes)
      : null,
  ]);
}

export function renderProfile(root, profile, memberCount, membersMeta) {
  if (!root) return;
  root.innerHTML = "";
  if (!profile) {
    root.hidden = true;
    return;
  }

  const population = profile.population;
  const households = profile.households;
  const budget = profile.budget_general_yen;
  const fiscalIndex = profile.fiscal_index;
  const perCapita = profile.per_capita || {};
  const memberSourceUrl = membersMeta?.source_url;

  const items = [
    profileItem(
      "人口",
      formatPeople(population?.value),
      [sourceLink(population?.source_url)],
    ),
    profileItem(
      "世帯数",
      formatHouseholds(households?.value),
      [sourceLink(households?.source_url)],
    ),
    profileItem(
      "一般会計予算",
      formatYen(budget?.value),
      [sourceLink(budget?.source_url)],
    ),
    profileItem(
      "財政力指数",
      formatDecimal(fiscalIndex?.value),
      [sourceLink(fiscalIndex?.source_url)],
    ),
    profileItem(
      "議員数",
      memberCount ? formatPeople(memberCount) : null,
      [sourceLink(memberSourceUrl)],
    ),
    profileItem(
      "議員1人あたり住民数",
      formatPeople(perCapita.population_per_member),
      [
        sourceLink(population?.source_url, "人口"),
        sourceLink(memberSourceUrl, "議員"),
      ],
    ),
  ].filter(Boolean);

  if (items.length === 0) {
    root.hidden = true;
    return;
  }

  root.hidden = false;
  root.appendChild(el("div", { class: "profile-grid" }, items));
}
