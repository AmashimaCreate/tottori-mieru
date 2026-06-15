import { externalLinkIcon, sourceLink } from "./data-quality.js?v=20260615-external-icons-v2";
import { councilAreaName, officialCouncilUrl, renderAiPromptCard } from "./render-ai-prompt.js?v=20260615-ai-links-anchor-v1";
import { renderMemberVoteSection } from "./render-votes.js?v=20260615-ai-links-anchor-v1";
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
  const prompts = [
    {
      key: "activity",
      label: "活動テーマ",
      text: structuredPrompt(member.name, council, activityInstruction(member, council)),
    },
  ];
  prompts.push({
    key: "profile",
    label: "経歴・基本情報",
    text: structuredPrompt(member.name, council, profileInstruction(member, council)),
  });
  return prompts;
}

function structuredPrompt(target, council, instruction) {
  return [
    `対象: ${target}(${council?.name || "議会"})`,
    "# お願い",
    `- ${instruction}`,
    "- 専門用語にはひとこと説明を添えてください",
    "- 確実でない点や古い可能性のある点は「分からない」と述べ、できれば出典を示してください",
    "- 評価や良し悪しの断定ではなく、事実の整理をお願いします",
  ].join("\n");
}

function activityInstruction(member, council) {
  const prefectureName = council?.prefecture_name || "鳥取県";
  const councilName = council?.name || "議会";
  const minutesUrl = council?.minutes_base_url;
  if (minutesUrl) {
    return `${prefectureName}の${councilName}議員・${member.name}さんについて、${councilName}の会議録検索システム(${minutesUrl})で最近の発言を検索し、どんなテーマについて発言しているか事実ベースで整理してください`;
  }
  const officialUrl = officialCouncilUrl(council);
  return `${prefectureName}の${councilName}議員・${member.name}さんについて、${councilName}の公式サイト(${officialUrl})で公開情報を確認し、最近どんなテーマに関わっているか事実ベースで整理してください`;
}

function profileInstruction(member, council) {
  const faction = member.faction || "会派データなし";
  const committees = Array.isArray(member.committees) && member.committees.length
    ? `担当委員会: ${member.committees.join(" / ")}。`
    : "";
  const profileUrl = member.official_profile_url || officialCouncilUrl(council);
  return `${member.name}議員(${council?.name || "議会"}、${faction})の経歴や担当委員会など公開されている基本情報を、出典(${profileUrl})を示しながら整理してください。${committees}`;
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
