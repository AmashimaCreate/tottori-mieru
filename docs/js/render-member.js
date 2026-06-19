import { externalLinkIcon, sourceLink } from "./data-quality.js?v=20260615-external-icons-v2";
import { councilAreaName, officialCouncilUrl, renderAiPromptCard } from "./render-ai-prompt.js?v=20260618-gemini-open-v1";
import { renderMemberVoteSection } from "./render-votes.js?v=20260618-gemini-open-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function renderMemberPage(root, state, memberId) {
  const member = state.members.find((item) => item.id === memberId);
  root.innerHTML = "";

  if (!member) {
    root.appendChild(el("p", { class: "empty-message" }, "議員データが見つかりません。"));
    return;
  }

  root.appendChild(renderMemberProfile(member, state.membersMeta, state.currentCouncil));
  const voteSection = renderMemberVoteSection(
    state.votes,
    state.votesMeta,
    member,
    state.currentCouncil,
    state.route,
  );
  if (voteSection) root.appendChild(voteSection);
  root.appendChild(renderMemberResearchSection(member, state));
}

function renderMemberProfile(member, membersMeta, council) {
  return el("section", { class: "member-detail member-profile-hero" }, [
    el("div", { class: "member-profile-heading" }, [
      el("p", { class: "eyebrow" }, "人物プロフィール"),
    ]),
    el("div", { class: "member-detail-main" }, [
      el("div", { class: "member-profile-body" }, [
        el("div", { class: "member-profile-facts" }, [
          member.district ? detailRow("選挙区", member.district) : null,
          detailRow("会派", member.faction || "データなし"),
          detailRow("当選回数", typeof member.elected_count === "number" ? `${member.elected_count}回` : "データなし"),
          detailRow("役職", listText(member.positions)),
          detailRow("委員会", listText(member.committees)),
        ]),
        el("div", { class: "member-profile-links" }, [
        member.official_profile_url
          ? el("p", { class: "official-profile-link member-link-line" }, [
              sourceLink(member.official_profile_url, "公式プロフィールを見る"),
            ])
          : null,
        renderMemberSearchLink(member, council),
        ]),
        sourceLink(membersMeta?.source_url, "議員名簿の出典"),
      ]),
    ]),
  ]);
}

function renderMemberSearchLink(member, council) {
  const areaName = councilAreaName(council);
  const query = [member.name, areaName, "議員"].filter(Boolean).join(" ");
  const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
  return el("p", { class: "member-search-link member-link-line" }, [
    el("a", { class: "external-link", href: url, target: "_blank", rel: "noopener" }, [
      "この議員について検索",
      externalLinkIcon(),
    ]),
  ]);
}

function renderMemberResearchSection(member, state) {
  const council = state.currentCouncil;
  return el("details", { class: "research-section member-research-details page-card" }, [
    el("summary", {}, [
      el("span", { class: "eyebrow" }, "もっと調べる"),
      el("strong", {}, "AIに聞いてみる"),
      el("small", {}, "質問の雛形を開く"),
    ]),
    renderAiPromptCard({
      title: "AIに聞いてみる",
      lead: "目的に合わせた質問の雛形を用意しました",
      prompts: memberPromptItems(member, state),
    }),
  ]);
}

function memberPromptItems(member, state) {
  const council = state.currentCouncil;
  return [
    {
      key: "activity",
      label: "活動テーマ",
      text: activityPrompt(member, council),
    },
    {
      key: "profile",
      label: "経歴・基本情報",
      text: profilePrompt(member, council),
    },
  ];
}

function activityPrompt(member, council) {
  const councilName = council?.name || "議会";
  const factionText = member.faction ? `、会派: ${promptFaction(member.faction)}` : "";
  const officialSources = officialSourceText(member, council);
  return [
    `対象: ${member.name}（${councilName}）`,
    "",
    "# お願い",
    `${member.name}議員（${councilName}${factionText}）が、議会でどんなテーマに取り組んでいるかを、公開情報の範囲で整理してください。`,
    "",
    "# 前提（重要）",
    `- 出典（公式）: ${officialSources}`,
    `- 同姓同名の別人と取り違えないよう、${councilName}議員本人であることを確認してください。`,
    "- 議員の発言や活動について、良し悪しの評価・採点・他議員との優劣づけはしないでください。事実（どのテーマを、いつ、どの場で取り上げたか）を中立に整理してください。",
    "- 確認できないこと・情報が少ないことは、断定せず正直に述べてください。",
    "- できる限り出典（会議録のURL等）を併記してください。",
    "",
    "# 聞きたいこと",
    "- どんな政策テーマ・発言・質問が公開記録にあるか（公式の会議録などの範囲で）",
    "- そのテーマについて、自分でさらに調べるにはどの会議録・資料を見ればよいか",
  ].join("\n");
}

function profilePrompt(member, council) {
  const councilName = council?.name || "議会";
  const factionText = member.faction ? `、会派: ${promptFaction(member.faction)}` : "";
  const siteFacts = memberSiteFacts(member);
  const officialUrl = member.official_profile_url || officialCouncilUrl(council) || "公式ページ";
  return [
    `対象: ${member.name}（${councilName}）`,
    "",
    "# お願い",
    `${member.name}議員（${councilName}${factionText}）について、公開されている経歴や活動の基本情報を整理してください。`,
    "",
    "# 前提（重要）",
    "- 以下は当サイト「政治見える化」の記載です。正しい前提とせず、必ず公式の一次情報で確認したうえで使ってください。",
    ...siteFacts.map((fact) => `  - ${fact}`),
    `  - 出典（公式）: ${officialUrl}`,
    `- 同姓同名の別人（他自治体の議員、国会議員、一般の方など）と取り違えないよう、${councilName}議員の本人であることを確認してから答えてください。`,
    "- 確実でない点や、情報が古い可能性がある点は、断定せず「確認できない」と述べてください。公開情報が少ない場合は、無理に埋めず「公開されている情報が少ない」と述べて構いません。",
    "- できる限り、述べた内容の出典（URL）を併記してください。",
    "- 専門用語（委員会名・役職など）には、ひとこと説明を添えてください。",
    "",
    "# 聞きたいこと",
    "- どんな経歴の人物か（前職・当選回数など、公開情報の範囲で）",
    "- 所属会派と、議会で担っている役割",
    "- この議員について、次に自分で確認するなら何を見ればよいか（公式ページ・会議録など）",
  ].join("\n");
}

function officialSourceText(member, council) {
  const sources = [];
  const profileUrl = member.official_profile_url || officialCouncilUrl(council);
  if (profileUrl) sources.push(profileUrl);
  if (council?.minutes_base_url) {
    sources.push(`${council.name || "議会"}の会議録検索システム: ${council.minutes_base_url}`);
  } else {
    sources.push(`${council?.name || "議会"}の会議録`);
  }
  return sources.join(" および ");
}

function memberSiteFacts(member) {
  const facts = [];
  if (member.district) facts.push(`選挙区: ${member.district}`);
  if (member.faction) facts.push(`会派: ${promptFaction(member.faction)}`);
  if (typeof member.elected_count === "number") facts.push(`当選回数: ${member.elected_count}回`);
  if (Array.isArray(member.positions) && member.positions.length) facts.push(`役職: ${member.positions.join(" / ")}`);
  if (Array.isArray(member.committees) && member.committees.length) facts.push(`担当委員会: ${member.committees.join(" / ")}`);
  if (!facts.length) facts.push("当サイト側の補足データ: データなし");
  return facts;
}

function promptFaction(value) {
  return String(value).replace(/[（(]([^（）()]+)[）)]/g, "〔$1〕");
}

function detailRow(label, value) {
  return el("p", { class: "detail-row" }, [
    el("span", { class: "detail-label" }, label),
    el("span", { class: "detail-value" }, value),
  ]);
}

function listText(values) {
  if (!Array.isArray(values) || values.length === 0) return "データなし";
  return values.join(" / ");
}
