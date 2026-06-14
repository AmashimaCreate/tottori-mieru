import { state } from "./state.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";
import { memberPath } from "./router.js?v=20260615-no-member-photos-v1";

const IDENTIFICATION_COLORS = [
  "#0072b2", // blue
  "#e69f00", // orange
  "#009e73", // bluish green
  "#cc79a7", // reddish purple
  "#56b4e9", // sky blue
  "#d55e00", // vermillion
  "#f0e442", // yellow
  "#6b5b95", // purple
];

// 役職の並び順(同役職内は kana 五十音順)
const ROLE_ORDER = { "委員長": 0, "副委員長": 1, "委員": 2 };

// 当選回数ビューの表示範囲(空のバケットも表示する)
const TERM_RANGE = [1, 2, 3, 4, 5, 6];

export function kaihaColor(kaiha) {
  return identificationColor(kaiha || "");
}

function committeeColor(type) {
  return identificationColor(type || "");
}

function identificationColor(value) {
  let hash = 0;
  for (const ch of value) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return IDENTIFICATION_COLORS[hash % IDENTIFICATION_COLORS.length];
}

function memberKana(member) {
  return member.name_kana || member.kana || "";
}

export function memberFaction(member) {
  return member.faction || member.kaiha || "(未分類)";
}

function memberElectedCount(member) {
  return member.elected_count ?? member.term_count ?? null;
}

function committeeType(name) {
  if (name && name.includes("議会運営")) return "議会運営";
  if (name && name.includes("特別")) return "特別";
  return "常任";
}

function committeeRole(member, name) {
  const positions = (member.positions || []).map(normalizeRoleText);
  const normalizedName = normalizeRoleText(name);
  if (positions.includes(`${normalizedName}委員長`)) return "委員長";
  if (positions.includes(`${normalizedName}副委員長`)) return "副委員長";
  return "委員";
}

function normalizeRoleText(value) {
  return String(value || "").replace(/\s+/g, "");
}

function committeeEntries(member) {
  return (member.committees || []).map((c) => {
    if (typeof c === "string") {
      return {
        name: c,
        role: committeeRole(member, c),
        type: committeeType(c),
      };
    }
    return {
      name: c.name,
      role: c.role || committeeRole(member, c.name),
      type: c.type || committeeType(c.name),
    };
  });
}

function groupByKaiha(members) {
  const map = new Map();
  for (const m of members) {
    const key = memberFaction(m);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(m);
  }
  const ordered = [];
  for (const [k, v] of map.entries()) {
    ordered.push([k, v]);
  }
  return ordered.sort((a, b) => a[0].localeCompare(b[0], "ja"));
}

function groupByCommittee(members) {
  const map = new Map();
  for (const m of members) {
    for (const c of committeeEntries(m)) {
      if (!map.has(c.name)) {
        map.set(c.name, { type: c.type, entries: [] });
      }
      map.get(c.name).entries.push({ member: m, role: c.role });
    }
  }
  for (const group of map.values()) {
    group.entries.sort((a, b) => {
      const ra = ROLE_ORDER[a.role] ?? 99;
      const rb = ROLE_ORDER[b.role] ?? 99;
      if (ra !== rb) return ra - rb;
      return memberKana(a.member).localeCompare(memberKana(b.member), "ja");
    });
  }
  const ordered = [];
  for (const [name, group] of map.entries()) {
    ordered.push([name, group]);
  }
  return ordered.sort((a, b) => a[0].localeCompare(b[0], "ja"));
}

function groupByTermCount(members) {
  const map = new Map();
  for (const t of TERM_RANGE) map.set(t, []);
  for (const m of members) {
    const t = memberElectedCount(m);
    if (typeof t !== "number") continue;
    if (!map.has(t)) map.set(t, []);
    map.get(t).push(m);
  }
  for (const list of map.values()) {
    list.sort((a, b) =>
      memberKana(a).localeCompare(memberKana(b), "ja"),
    );
  }
  return [...map.entries()].sort((a, b) => a[0] - b[0]);
}

function renderMemberCard(m) {
  const faction = memberFaction(m);
  const colorStyle = `--kaiha-color: ${kaihaColor(faction)};`;

  // 役職バッジ(議長・副議長 + 委員長・副委員長)
  const positionBadges = [];
  for (const p of m.positions || []) {
    positionBadges.push(el("span", { class: "badge is-position" }, p));
  }

  // 委員会リスト(委員のみ。委員長/副委員長はバッジ側に出している)
  const committeeItems = committeeEntries(m)
    .filter((c) => c.role === "委員")
    .map((c) => el("li", {}, `${c.name}委員（${c.type}）`));

  return el("article", { class: "member-card", style: colorStyle }, [
    el("div", { class: "member-head" }, [
      el("div", { class: "member-name-block" }, [
        el("p", { class: "member-name" }, m.name),
        el("p", { class: "member-kana" }, memberKana(m)),
        m.district ? el("p", { class: "member-district" }, m.district) : null,
        el("p", { class: "member-card-faction" }, faction),
        el(
          "p",
          { class: "member-term" },
          memberElectedCount(m) === null
            ? "当選回数: データなし"
            : `当選 ${memberElectedCount(m)} 回`,
        ),
      ]),
    ]),
    positionBadges.length
      ? el("div", { class: "member-positions" }, positionBadges)
      : null,
    committeeItems.length
      ? el("ul", { class: "member-committees" }, committeeItems)
      : null,
    el("p", { class: "member-detail-link-wrap" }, [
      el(
        "a",
        {
          class: "member-detail-link",
          href: memberPath(
            state.currentCouncil.prefecture || state.route.prefecture || "tottori",
            state.currentCouncil.id,
            m.id,
          ),
        },
        "議員ページを見る",
      ),
    ]),
  ]);
}

export function renderKaihaView(root, members) {
  root.innerHTML = "";
  const grouped = groupByKaiha(members);
  for (const [kaiha, list] of grouped) {
    const headerStyle = `--kaiha-color: ${kaihaColor(kaiha)};`;
    const group = el("section", {
      class: "kaiha-group",
      "data-faction": kaiha,
      tabindex: "-1",
    }, [
      el("div", { class: "kaiha-header", style: headerStyle }, [
        el("h2", { class: "kaiha-name" }, kaiha),
        el("span", { class: "kaiha-count" }, `${list.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        list.map(renderMemberCard),
      ),
    ]);
    root.appendChild(group);
  }
}

export function renderCommitteeView(root, members) {
  root.innerHTML = "";
  const grouped = groupByCommittee(members);
  for (const [name, group] of grouped) {
    const headerStyle = `--committee-color: ${committeeColor(group.type)};`;
    const note = name === "予算決算"
      ? el(
          "p",
          { class: "committee-note" },
          "※全議員が所属。正副委員長のみ表示しています。",
        )
      : null;
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, name),
        el("span", { class: "committee-type-badge" }, group.type),
        el("span", { class: "committee-count" }, `${group.entries.length}人`),
      ]),
      note,
      el(
        "div",
        { class: "member-grid" },
        group.entries.map(({ member }) => renderMemberCard(member)),
      ),
    ]);
    root.appendChild(section);
  }
}

export function renderRoleView(root, members) {
  root.innerHTML = "";
  let renderedSections = 0;

  // 第1セクション: 議長・副議長
  const heads = members
    .filter((m) =>
      (m.positions || []).some((p) => p === "議長" || p === "副議長"),
    )
    .sort((a, b) => {
      const ra = (a.positions || []).includes("議長") ? 0 : 1;
      const rb = (b.positions || []).includes("議長") ? 0 : 1;
      return ra - rb;
    });

  if (heads.length > 0) {
    const headerStyle = "--committee-color: var(--position-accent);";
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, "議長・副議長"),
        el("span", { class: "committee-count" }, `${heads.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        heads.map(renderMemberCard),
      ),
    ]);
    root.appendChild(section);
    renderedSections += 1;
  }

  // 第2〜N セクション: 各委員会の委員長/副委員長(委員会ビューと同じ並び)
  const grouped = groupByCommittee(members);
  for (const [name, group] of grouped) {
    const leaders = group.entries.filter(
      (e) => e.role === "委員長" || e.role === "副委員長",
    );
    if (leaders.length === 0) continue;
    const headerStyle = `--committee-color: ${committeeColor(group.type)};`;
    const section = el("section", { class: "committee-group" }, [
      el("div", { class: "committee-header", style: headerStyle }, [
        el("h2", { class: "committee-name" }, name),
        el("span", { class: "committee-type-badge" }, group.type),
        el("span", { class: "committee-count" }, `${leaders.length}人`),
      ]),
      el(
        "div",
        { class: "member-grid" },
        leaders.map(({ member }) => renderMemberCard(member)),
      ),
    ]);
    root.appendChild(section);
    renderedSections += 1;
  }

  if (renderedSections === 0) {
    root.appendChild(
      el("p", { class: "empty-message" }, "この議会の役職データはまだ取得できていません。"),
    );
  }
}

export function renderTermView(root, members) {
  root.innerHTML = "";
  const knownMembers = members.filter((member) =>
    typeof memberElectedCount(member) === "number",
  );
  if (knownMembers.length === 0) {
    root.appendChild(
      el("p", { class: "empty-message" }, "この議会の当選回数データはまだ取得できていません。"),
    );
    return;
  }

  const grouped = groupByTermCount(members);
  const total = members.length;
  const isFiltered = state.query.trim().length > 0;

  for (const [term, list] of grouped) {
    const count = list.length;
    // 検索中は空バケットを非表示(分布のギャップは検索なし時のみ表示)
    if (isFiltered && count === 0) continue;
    const pctOfTotal =
      total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";

    const section = el("section", { class: "term-group" }, [
      el("div", { class: "term-header" }, [
        el("span", { class: "term-label" }, `${term}回`),
        el(
          "span",
          { class: "term-count" },
          count > 0 ? `${count}人 (${pctOfTotal}%)` : "該当なし",
        ),
      ]),
      count > 0
        ? el(
            "div",
            { class: "member-grid" },
            list.map(renderMemberCard),
          )
        : null,
    ]);
    root.appendChild(section);
  }
}
