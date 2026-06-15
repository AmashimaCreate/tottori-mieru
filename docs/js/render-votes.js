import { sourceLink } from "./data-quality.js?v=20260615-external-icons-v2";
import { councilAreaName, renderAiPromptCard } from "./render-ai-prompt.js?v=20260615-ai-links-anchor-v1";
import { memberPath } from "./router.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const VOTE_ORDER = ["賛成", "反対", "退席", "欠席", "議長", "除斥", "継続審査"];

export function votesEnabledForCouncil(council) {
  return council?.vote_granularity === "member";
}

export function hasMemberVoteLayer(council, votesMeta, votes) {
  return votesEnabledForCouncil(council) && votesMeta && Array.isArray(votes) && votes.length > 0;
}

export function hasResultOnlyVoteLayer(council, votesMeta, votes) {
  return council?.vote_granularity === "result_only"
    && votesMeta
    && Array.isArray(votes)
    && votes.length > 0;
}

export function renderMemberVoteSection(votes, votesMeta, member, council, route) {
  if (!hasMemberVoteLayer(council, votesMeta, votes)) {
    return renderMemberVoteMissingSection(council);
  }

  const memberVotes = (votes || [])
    .map((vote) => {
      const item = (vote.votes_by_member || [])
        .find((entry) => entry.member_id === member.id);
      return item ? { vote, item } : null;
    })
    .filter(Boolean)
    .sort((a, b) => (b.vote.date || "").localeCompare(a.vote.date || ""));

  const groups = groupVotesBySession(memberVotes);

  return el("section", { class: "vote-section member-vote-section" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "この議員の判断"),
        el("h2", { class: "section-title" }, "賛成・反対の記録"),
      ]),
    ]),
    renderAllVoteGroups(groups, memberVotes.length),
    renderVoteSourceSummary(memberVotes),
  ]);
}

function renderMemberVoteMissingSection(council) {
  return el("section", { class: "vote-section member-vote-section" }, [
    el("div", { class: "section-heading-row" }, [
      el("div", {}, [
        el("p", { class: "eyebrow" }, "この議員の判断"),
        el("h2", { class: "section-title" }, "賛否の記録"),
      ]),
    ]),
    renderVoteAvailabilityNotice(council),
  ]);
}

export function sortedVotesByDate(votes) {
  return [...(votes || [])].sort((a, b) => {
    const dateCompare = (b.date || "").localeCompare(a.date || "");
    if (dateCompare) return dateCompare;
    return (a.bill_title || "").localeCompare(b.bill_title || "", "ja");
  });
}

export function renderCouncilVoteSection(votes, votesMeta, council, members, route) {
  if (hasResultOnlyVoteLayer(council, votesMeta, votes)) {
    return renderResultOnlyVoteSection(votes, council);
  }

  if (!hasMemberVoteLayer(council, votesMeta, votes)) {
    return el("section", { class: "vote-section" }, [
      el("h2", { class: "section-title" }, "議決一覧"),
      renderVoteAvailabilityNotice(council),
    ]);
  }

  const memberMap = new Map((members || []).map((member) => [member.id, member]));
  const sortedVotes = sortedVotesByDate(votes);

  return el("section", { class: "vote-section" }, [
    el("h2", { class: "section-title" }, `議決一覧（${sortedVotes.length}件）`),
    el("p", { class: "muted" }, "議案ごとの賛成・反対の人数を表示します。展開すると各議員の票を確認できます。"),
    el("div", { class: "vote-detail-list" },
      sortedVotes.map((vote) => renderCouncilVoteDetail(vote, council, route, memberMap)),
    ),
  ]);
}

function renderResultOnlyVoteSection(votes, council) {
  const sortedVotes = sortedVotesByDate(votes);
  return el("section", { class: "vote-section" }, [
    el("h2", { class: "section-title" }, `議決一覧（${sortedVotes.length}件）`),
    el("p", { class: "muted" }, "議員ごとの賛否ではなく、公式PDFに掲載された議案ごとの議決結果を表示します。"),
    el("div", { class: "result-only-vote-list" },
      sortedVotes.map((vote) => renderResultOnlyVoteCard(vote, council)),
    ),
    renderResultOnlyVoteSourceSummary(sortedVotes),
  ]);
}

export function renderResultOnlyVoteCard(vote) {
  return el("article", { class: "result-only-vote-card" }, [
    el("div", { class: "result-only-vote-head" }, [
      el("span", { class: "vote-date" }, vote.date || "日付なし"),
      vote.bill_no ? el("span", { class: "bill-no" }, vote.bill_no) : null,
    ]),
    el("h3", {}, vote.bill_title || "議案名なし"),
    el("p", { class: "vote-result" }, `結果: ${vote.result || "結果なし"}`),
  ]);
}

function renderResultOnlyVoteSourceSummary(votes) {
  const sources = [];
  const seen = new Set();
  for (const vote of votes || []) {
    if (!vote.source_url || seen.has(vote.source_url)) continue;
    seen.add(vote.source_url);
    sources.push(vote.source_url);
  }
  if (!sources.length) return null;
  return el("p", { class: "section-source" }, [
    "出典: ",
    sourceLink(sources[0], "議決結果PDF"),
    sources.length > 1 ? `（ほか${sources.length - 1}件）` : "",
  ]);
}

function renderAllVoteGroups(groups, total) {
  if (!total) {
    return el("p", { class: "empty-message is-compact" }, "この議員に紐付いた賛否記録はありません。");
  }
  return el("section", { class: "all-vote-records" }, [
    el("h3", {}, `全議案（${total}件）`),
    el("div", { class: "member-vote-session-list" },
      groups.map((group, index) => renderVoteSessionGroup(group, index === 0)),
    ),
  ]);
}

function renderVoteSessionGroup(group, isOpen = false) {
  return el("details", { class: "member-vote-session", open: isOpen ? "" : null }, [
    el("summary", {}, `${group.label}（${group.items.length}件）`),
    el("div", { class: "member-vote-table" },
      group.items.map(renderCompactMemberVoteRow),
    ),
  ]);
}

function renderCompactMemberVoteRow({ vote, item }) {
  return el("div", { class: "member-vote-row" }, [
    el("span", { class: "vote-date" }, vote.date || "日付なし"),
    el("span", { class: "vote-title" }, vote.bill_title || "議案名なし"),
    renderVoteBadge(item.vote),
    el("span", { class: "vote-summary-result" }, vote.result || "結果なし"),
  ]);
}

function renderVoteSourceSummary(memberVotes) {
  const sources = uniqueSourceUrls(memberVotes);
  if (!sources.length) return null;
  const first = sources[0];
  return el("p", { class: "section-source" }, [
    "出典: ",
    el("a", { href: first, target: "_blank", rel: "noopener" }, "議員別賛否PDF"),
    sources.length > 1 ? `（ほか${sources.length - 1}件）` : "",
  ]);
}

function renderCouncilVoteDetail(vote, council, route, memberMap) {
  const counts = voteCounts(vote);
  const details = el("details", { class: "vote-detail" }, [
    el("summary", { class: "vote-summary" }, [
      el("span", { class: "vote-summary-date" }, vote.date || "日付なし"),
      el("span", { class: "vote-summary-title" }, vote.bill_title || "議案名なし"),
      el("span", { class: "vote-summary-counts" }, [
        `賛成 ${counts["賛成"] || 0} / 反対 ${counts["反対"] || 0}`,
      ]),
      el("span", { class: "vote-summary-result" }, vote.result || "結果なし"),
    ]),
    el("div", { class: "vote-detail-body" }, [
      el("p", { class: "vote-source" }, sourceLink(vote.source_url, "公式PDFで確認")),
      renderVoteResearchPrompt(vote, council),
      el("div", { class: "vote-member-grid" },
        (vote.votes_by_member || []).map((entry) =>
          renderVoteMemberCell(entry, council, route, memberMap),
        ),
      ),
    ]),
  ]);
  return details;
}

function renderVoteResearchPrompt(vote, council) {
  return renderAiPromptCard({
    title: "AIに聞いてみる",
    lead: "目的に合わせた質問の雛形を用意しました",
    prompts: votePromptItems(vote, council),
    compact: true,
  });
}

function votePromptItems(vote, council) {
  const prompts = [
    {
      key: "summary",
      label: "要約して",
      text: structuredVotePrompt(vote, council, "この議案が何のためのものか、政治にくわしくない人にも分かるように3〜4行で説明してください"),
    },
  ];
  if (hasSplitVote(vote)) {
    prompts.push({
      key: "pros-cons",
      label: "賛成と反対",
      text: structuredVotePrompt(vote, council, "この議決について、賛成側と反対側でどんな立場の違いがあり得るか、公的情報を優先して整理してください"),
    }, {
      key: "pro-detail",
      label: "賛成側を詳しく",
      text: structuredVotePrompt(vote, council, "この議決について、賛成側が重視している可能性のある理由や根拠を、公的情報を優先して整理してください"),
    }, {
      key: "con-detail",
      label: "反対側を詳しく",
      text: structuredVotePrompt(vote, council, "この議決について、反対側が重視している可能性のある理由や懸念を、公的情報を優先して整理してください"),
    });
  }
  prompts.push({
    key: "background",
    label: "経緯・背景",
    text: structuredVotePrompt(vote, council, "この議案が出てきた背景や、関連する制度を整理してください"),
  });
  return prompts;
}

function structuredVotePrompt(vote, council, instruction) {
  return [
    `対象: ${vote.bill_title || "議案名不明"}(${council?.name || "議会"})`,
    "# お願い",
    `- ${councilAreaName(council) || council?.name || "この自治体"}議会で${vote.date || "日付不明"}に議決されたこの議案について、${instruction}`,
    "- 専門用語にはひとこと説明を添えてください",
    "- 確実でない点や古い可能性のある点は「分からない」と述べ、できれば出典を示してください",
    "- 評価や良し悪しの断定ではなく、事実の整理をお願いします",
  ].join("\n");
}

function hasSplitVote(vote) {
  const counts = voteCounts(vote);
  return (counts["賛成"] || 0) > 0 && (counts["反対"] || 0) > 0;
}

function renderVoteMemberCell(entry, council, route, memberMap) {
  const member = entry.member_id ? memberMap.get(entry.member_id) : null;
  const label = member?.name || entry.member_name || "名前不明";
  const nameNode = member
    ? el("a", {
        href: memberPath(
          council.prefecture || route.prefecture || "tottori",
          council.id,
          member.id,
        ),
      }, label)
    : el("span", {}, label);
  return el("div", { class: "vote-member-cell" }, [
    el("span", { class: "vote-member-name" }, nameNode),
    renderVoteBadge(entry.vote),
    entry.member_id ? null : el("span", { class: "vote-former-note" }, "現在の議員名簿にいません"),
  ]);
}

function renderVoteBadge(value) {
  return el("span", {
    class: `vote-badge ${voteClass(value)}`,
    title: voteHelpText(value),
  }, voteDisplayText(value));
}

function voteCounts(vote) {
  const counts = {};
  for (const entry of vote.votes_by_member || []) {
    const value = entry.vote || "不明";
    counts[value] = (counts[value] || 0) + 1;
  }
  return counts;
}

function formatVoteCounts(counts) {
  const ordered = [
    ...VOTE_ORDER.filter((key) => counts[key]),
    ...Object.keys(counts).filter((key) => !VOTE_ORDER.includes(key)).sort((a, b) => a.localeCompare(b, "ja")),
  ];
  return ordered.length
    ? ordered.map((key) => `${key}${counts[key]}`).join(" / ")
    : "記録なし";
}

function groupVotesBySession(memberVotes) {
  const groups = new Map();
  for (const item of memberVotes || []) {
    const label = sessionLabel(item.vote);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(item);
  }
  return [...groups.entries()].map(([label, items]) => ({ label, items }));
}

function sessionLabel(vote) {
  if (vote?.session) return vote.session;
  const dateValue = vote?.date;
  const match = String(dateValue || "").match(/^(\d{4})-(\d{2})-/);
  if (!match) return "日付なし";
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!year || !month) return "日付なし";
  if (year >= 2019) return `令和${year - 2018}年${month}月定例会`;
  return `${year}年${month}月定例会`;
}

function uniqueSourceUrls(memberVotes) {
  const urls = [];
  const seen = new Set();
  for (const { vote } of memberVotes || []) {
    const url = vote.source_url;
    if (!url || seen.has(url)) continue;
    seen.add(url);
    urls.push(url);
  }
  return urls;
}

function voteDisplayText(value) {
  if (value === "議長") return "議長（採決に加わらず）";
  if (value === "除斥") return "除斥";
  return value || "不明";
}

function voteHelpText(value) {
  if (value === "議長") return "議長は慣例により採決に加わりません。";
  if (value === "除斥") return "利害関係があるため採決から外れた状態です。";
  return value || "";
}

function voteClass(value) {
  if (value === "賛成") return "is-yes";
  if (value === "反対") return "is-no";
  if (value === "議長") return "is-chair";
  if (value === "除斥") return "is-recusal";
  if (value === "継続審査") return "is-continued";
  return "is-other";
}

export function renderVoteAvailabilityNotice(council) {
  const availability = voteAvailability(council);
  const children = [availability.text];
  if (availability.url) {
    children.push(
      " ",
      el("a", {
        href: availability.url,
        target: "_blank",
        rel: "noopener",
      }, availability.linkText),
    );
  }
  return el("p", { class: "vote-availability-note" }, children);
}

function voteAvailability(council) {
  if (council?.id === "tottori-city") {
    return {
      text: "鳥取市議会の議決結果は機械可読でない形式のため未収録です。",
      linkText: "公式ページへ →",
      url: council.votes_official_url || null,
    };
  }
  if (council?.vote_granularity === "result_only") {
    return {
      text: `${council.name}は議員ごとの賛否を公開していません。`,
      linkText: "議決結果は公式ページへ →",
      url: council.votes_official_url || null,
    };
  }
  if (council?.votes_official_url) {
    return {
      text: `${council.name}の議決結果は未収録です。`,
      linkText: "公式ページへ →",
      url: council.votes_official_url,
    };
  }
  return {
    text: `${council?.name || "この議会"}の議決結果は未収録です。`,
    linkText: "公式ページへ →",
    url: null,
  };
}
