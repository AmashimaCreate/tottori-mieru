import { el } from "./utils.js?v=20260615-no-member-photos-v1";

export function acquisitionText(membersMeta) {
  const acquisition = membersMeta?.acquisition;
  if (acquisition === "scraping") {
    return "公式サイトから自動取得";
  }
  if (acquisition === "manual_transcription") {
    const date = confirmedDate(membersMeta);
    return `公式名簿を手作業で転記（確認日: ${date || "不明"}）`;
  }
  return "取得方法の記録がありません";
}

export function coverageText(speechesMeta, council = null) {
  if (!speechesMeta) {
    if (council?.minutes_system === "dbsr") {
      return "発言インデックス未取得（会議録が別システムのため）。";
    }
    return "発言インデックスはまだ取得していません。";
  }
  return "本会議での議員の発言のみ。委員会・議長の進行・市長や職員の答弁は含みません。";
}

export function voteCoverageText(votesMeta, council = null) {
  if (votesMeta) {
    if (votesMeta.granularity === "result_only" || council?.vote_granularity === "result_only") {
      return "議員ごとの賛否ではなく、議案ごとの議決結果を公式PDFから取得しています。";
    }
    return "議員別賛否PDFから取得。議案名・票・議決結果は公式PDFを確認できます。";
  }
  if (council?.vote_granularity === "result_only") {
    return "議員ごとの賛否は公開されていません。議決結果のみ公式ページで確認できます。";
  }
  if (council?.id === "tottori-city") {
    return "議決結果は機械可読でない形式のため未収録です。";
  }
  return "議決データはまだ収録していません。";
}

export function sourceLink(url, label = "公式情報を確認") {
  if (!url) return null;
  return el(
    "a",
    {
      href: url,
      target: "_blank",
      rel: "noopener",
    },
    label,
  );
}

export function dataQualityPanel({ membersMeta, speechesMeta, votesMeta, council }) {
  const rows = [
    qualityRow(
      "議員名簿",
      acquisitionText(membersMeta),
      sourceLink(membersMeta?.source_url, "名簿の出典"),
      membersMeta?.acquisition,
    ),
    qualityRow(
      "発言インデックス",
      coverageText(speechesMeta, council),
      sourceLink(firstSpeechSourceUrl(speechesMeta), "発言の確認はこちら"),
      speechesMeta ? "speaker1_only" : "not_collected",
    ),
    qualityRow(
      "議案への賛否",
      voteCoverageText(votesMeta, council),
      sourceLink(firstVoteSourceUrl(votesMeta), "賛否の出典"),
      votesMeta ? "member_votes" : "not_collected",
    ),
  ];

  return el("section", { class: "quality-panel", "aria-label": "データ品質" }, [
    el("h2", { class: "section-title" }, "データの見方"),
    el("div", { class: "quality-grid" }, rows),
  ]);
}

export function cautionNote() {
  return el("p", { class: "caution-note" },
    "発言数は取得範囲内の件数です。役職（議長等）や当選時期により差があります。",
  );
}

function qualityRow(label, text, link, rawValue) {
  return el("div", { class: "quality-row", "data-quality": rawValue || "" }, [
    el("span", { class: "quality-label" }, label),
    el("span", { class: "quality-text", title: rawValue || "" }, text),
    link ? el("span", { class: "quality-link" }, link) : null,
  ]);
}

function firstSpeechSourceUrl(speechesMeta) {
  const speeches = speechesMeta?.speeches;
  if (!Array.isArray(speeches) || speeches.length === 0) return null;
  return speeches.find((speech) => speech.source_url)?.source_url || null;
}

function firstVoteSourceUrl(votesMeta) {
  const votes = votesMeta?.votes;
  if (!Array.isArray(votes) || votes.length === 0) return null;
  return votes.find((vote) => vote.source_url)?.source_url || null;
}

function confirmedDate(membersMeta) {
  const note = membersMeta?.source_note || "";
  const match = note.match(/令和\s*(\d+)年\s*(\d+)月\s*(\d+)日/);
  if (match) {
    const year = 2018 + Number(match[1]);
    return [
      year,
      String(Number(match[2])).padStart(2, "0"),
      String(Number(match[3])).padStart(2, "0"),
    ].join("-");
  }
  if (membersMeta?.updated_at) {
    return membersMeta.updated_at.slice(0, 10);
  }
  return null;
}
