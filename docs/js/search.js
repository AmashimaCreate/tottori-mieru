import { state } from "./state.js?v=20260615-no-member-photos-v1";

export function matchesQuery(member, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  const fields = [
    member.name || "",
    member.name_kana || member.kana || "",
    member.faction || member.kaiha || "",
    ...(member.committees || []).map((c) =>
      typeof c === "string" ? c : c.name || "",
    ),
  ];
  return fields.some((f) => f.toLowerCase().includes(q));
}

export function filteredMembers() {
  const q = state.query.trim();
  if (!q) return state.members;
  return state.members.filter((m) => matchesQuery(m, q));
}
