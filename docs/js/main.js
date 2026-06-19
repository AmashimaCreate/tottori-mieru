import { loadCouncilBundle, loadCouncils, loadCouncilSummaries } from "./data-loader.js?v=20260615-no-member-photos-v1";
import { renderAbout } from "./render-about.js?v=20260620-blue-home-v1";
import { renderCouncilPage } from "./render-council.js?v=20260618-gemini-open-v1";
import { renderGuide } from "./render-guide.js?v=20260615-no-member-photos-v1";
import { renderMemberPage } from "./render-member.js?v=20260618-gemini-open-v1";
import { renderPrefecturePage } from "./render-prefecture.js?v=20260620-blue-pref-v1";
import { renderPrefectureComparisonPage } from "./render-prefecture-comparison.js?v=20260615-no-member-photos-v1";
import { renderProfile } from "./render-profile.js?v=20260615-no-member-photos-v1";
import { renderTop } from "./render-top.js?v=20260620-blue-home-v1";
import {
  councilPath,
  parseRoute,
  prefPath,
  topPath,
} from "./router.js?v=20260615-no-member-photos-v1";
import { filteredMembers } from "./search.js?v=20260615-no-member-photos-v1";
import { state } from "./state.js?v=20260615-no-member-photos-v1";
import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const COUNCILS_WITH_SPEECHES = new Set([
  "yonago-city",
  "kurayoshi-city",
  "sakaiminato-city",
]);

function titleNode() {
  return document.getElementById("page-title");
}

function leadNode() {
  return document.getElementById("page-lead");
}

function metaNode() {
  return document.getElementById("meta");
}

function routeNavNode() {
  return document.getElementById("route-nav");
}

function mainNode() {
  return document.getElementById("main");
}

function setHeader({ title, lead, meta = "" }) {
  document.title = title.endsWith("議会見える化")
    ? title
    : `${title} | 議会見える化`;
  titleNode().textContent = title;
  const leadElement = leadNode();
  leadElement.textContent = lead || "";
  leadElement.hidden = !lead;
  metaNode().textContent = meta;
}

function setRouteNav({ back = null, crumbs = [] } = {}) {
  const node = routeNavNode();
  if (!node) return;
  node.innerHTML = "";
  if (!back && !crumbs.length) {
    node.hidden = true;
    return;
  }

  if (back) {
    node.appendChild(
      el("a", {
        class: "route-back",
        href: back.href,
        "aria-label": `${back.label}へ戻る`,
        title: `${back.label}へ戻る`,
      }, [
        el("span", { class: "route-back-icon", "aria-hidden": "true" }, "←"),
        el("span", {}, back.displayLabel || "戻る"),
      ]),
    );
  }

  if (crumbs.length) {
    node.appendChild(
      el("ol", { class: "breadcrumbs" }, crumbs.map((crumb, index) =>
        el("li", {}, [
          crumb.href
            ? el("a", { href: crumb.href }, crumb.label)
            : el("span", { "aria-current": index === crumbs.length - 1 ? "page" : undefined }, crumb.label),
        ]),
      )),
    );
  }
  node.hidden = false;
}

function resetRouteNav() {
  setRouteNav();
}

function prefectureLabel(prefecture) {
  const council = state.councils.find((item) =>
    item.type === "prefecture" && item.prefecture === prefecture
  );
  return council?.prefecture_name || prefecture;
}

function showCouncilNav(show) {
  const nav = document.getElementById("view-nav");
  if (nav) nav.hidden = !show;
  const profile = document.getElementById("profile");
  if (profile && !show) {
    profile.hidden = true;
    profile.innerHTML = "";
  }
}

function renderMeta() {
  const node = metaNode();
  const meta = state.membersMeta;
  const members = state.members;
  if (!meta) {
    node.textContent = "";
    return;
  }
  const fetched = meta.updated_at
    ? new Date(meta.updated_at).toLocaleString("ja-JP")
    : "?";
  const type = councilTypeLabel(state.currentCouncil);
  node.textContent = `${type} / 現在 ${members.length}人 / 最終更新 ${fetched}`;
}

function activePrefectureSlugs() {
  return new Set(
    state.councils
      .filter((council) => council.type === "prefecture" && council.status === "active")
      .map((council) => council.prefecture),
  );
}

function councilsWithVotes() {
  return new Set(
    state.councils
      .filter((council) => council.vote_granularity === "member" || council.vote_granularity === "result_only")
      .map((council) => council.id),
  );
}

function updateMatchCount(filteredCount) {
  const node = document.getElementById("match-count");
  if (!node) return;
  const total = state.members.length;
  if (state.query.trim()) {
    node.textContent = `${total}人中 ${filteredCount}人を表示`;
  } else {
    node.textContent = "";
  }
}

function updateSearchPlaceholder() {
  const input = document.getElementById("search");
  if (!input) return;
  input.placeholder = `${state.currentCouncil?.name || "議員"}を検索`;
}

function syncSearchInput() {
  const input = document.getElementById("search");
  const clearBtn = document.getElementById("search-clear");
  if (!input) return;
  input.value = state.query;
  if (clearBtn) clearBtn.hidden = state.query.length === 0;
}

function syncSearchVisibility() {
  const row = document.querySelector(".search-row");
  if (row) row.hidden = state.view === "votes";
}

function updateActiveTab() {
  const tabs = document.querySelectorAll(".view-tab");
  tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.view === state.view);
  });
}

function renderCouncilRoute() {
  const isRedesignedCouncil = state.currentCouncil?.status === "active";
  const prefecture = state.currentCouncil?.prefecture || "tottori";
  const prefectureName = prefectureLabel(prefecture);
  setRouteNav({
    back: { label: `${prefectureName}ページ`, href: prefPath(prefecture) },
    crumbs: [
      { label: "全国トップ", href: topPath() },
      { label: prefectureName, href: prefPath(prefecture) },
      { label: state.currentCouncil.name },
    ],
  });
  setHeader({
    title: state.currentCouncil.name,
    lead: isRedesignedCouncil
      ? "この地域の今と、最近決まったことを見ます。"
      : "議員名簿、自治体基礎データ、発言インデックスを同じ画面で確認します。",
  });
  showCouncilNav(!isRedesignedCouncil);
  updateActiveTab();
  updateSearchPlaceholder();
  syncSearchInput();
  syncSearchVisibility();
  const profileNode = document.getElementById("profile");
  if (isRedesignedCouncil) {
    profileNode.hidden = true;
    profileNode.innerHTML = "";
  } else {
    renderProfile(
      profileNode,
      state.profile,
      state.members.length,
      state.membersMeta,
    );
  }
  renderMeta();

  const filtered = filteredMembers();
  updateMatchCount(filtered.length);
  renderCouncilPage(mainNode(), state, filtered);
}

function renderMemberRoute(memberId) {
  const member = state.members.find((item) => item.id === memberId);
  const prefecture = state.currentCouncil?.prefecture || "tottori";
  const prefectureName = prefectureLabel(prefecture);
  setRouteNav({
    back: {
      label: state.currentCouncil.name,
      href: councilPath(prefecture, state.currentCouncil.id),
    },
    crumbs: [
      { label: "全国トップ", href: topPath() },
      { label: prefectureName, href: prefPath(prefecture) },
      {
        label: state.currentCouncil.name,
        href: councilPath(prefecture, state.currentCouncil.id),
      },
      { label: member ? member.name : "議員ページ" },
    ],
  });
  setHeader({
    title: member ? member.name : "議員ページ",
    lead: state.currentCouncil.name,
  });
  showCouncilNav(false);
  renderMeta();
  renderMemberPage(mainNode(), state, memberId);
}

function renderNotFound() {
  setRouteNav({
    back: { label: "全国トップ", href: topPath() },
    crumbs: [
      { label: "全国トップ", href: topPath() },
      { label: "ページが見つかりません" },
    ],
  });
  setHeader({
    title: "ページが見つかりません",
    lead: "URLを確認してください。",
  });
  showCouncilNav(false);
  mainNode().innerHTML = "";
  mainNode().appendChild(
    el("p", { class: "empty-message" }, [
      "ページが見つかりません。 ",
      el("a", { href: "#/" }, "トップへ戻る"),
    ]),
  );
}

async function applyRoute() {
  const route = parseRoute();
  state.route = route;

  if (route.name === "redirect") {
    window.location.replace(route.to);
    return;
  }

  state.councils = await loadCouncils();

  if (route.name === "about") {
    state.currentCouncil = null;
    state.members = [];
    state.membersMeta = null;
    state.profile = null;
    state.timeseries = null;
    state.councilSummaries = [];
    state.speeches = [];
    state.speechesMeta = null;
    state.votes = [];
    state.votesMeta = null;
    state.view = "kaiha";
    state.query = "";
    setHeader({
      title: "このサイトについて",
      lead: "目的、出典、更新方法、地図クレジットをまとめています。",
    });
    setRouteNav({
      back: { label: "全国トップ", href: topPath() },
      crumbs: [
        { label: "全国トップ", href: topPath() },
        { label: "このサイトについて" },
      ],
    });
    showCouncilNav(false);
    renderAbout(mainNode());
    return;
  }

  if (route.name === "guide") {
    state.currentCouncil = null;
    state.members = [];
    state.membersMeta = null;
    state.profile = null;
    state.timeseries = null;
    state.councilSummaries = [];
    state.speeches = [];
    state.speechesMeta = null;
    state.votes = [];
    state.votesMeta = null;
    state.view = "kaiha";
    state.query = "";
    setHeader({
      title: "調べ方ガイド",
      lead: "このサイトを入口に、一次ソースへたどるための簡単な案内です。",
    });
    setRouteNav({
      back: { label: "全国トップ", href: topPath() },
      crumbs: [
        { label: "全国トップ", href: topPath() },
        { label: "調べ方ガイド" },
      ],
    });
    showCouncilNav(false);
    renderGuide(mainNode());
    return;
  }

  if (route.name === "national") {
    state.currentCouncil = null;
    state.members = [];
    state.membersMeta = null;
    state.profile = null;
    state.timeseries = null;
    state.councilSummaries = [];
    state.speeches = [];
    state.speechesMeta = null;
    state.votes = [];
    state.votesMeta = null;
    state.view = "kaiha";
    state.query = "";
    setHeader({
      title: "全国 議会見える化",
      lead: "対応地域を地図と一覧から選び、議会ごとの公開データを確認できます。",
    });
    resetRouteNav();
    showCouncilNav(false);
    renderTop(mainNode(), state.councils);
    return;
  }

  if (route.name === "prefecture" || route.name === "prefecture-compare") {
    state.currentCouncil = null;
    state.members = [];
    state.membersMeta = null;
    state.profile = null;
    state.timeseries = null;
    state.councilSummaries = [];
    state.speeches = [];
    state.speechesMeta = null;
    state.votes = [];
    state.votesMeta = null;
    state.view = "kaiha";
    state.query = "";
    if (!activePrefectureSlugs().has(route.prefecture)) {
      renderNotFound();
      return;
    }
    const prefectureName = prefectureLabel(route.prefecture);
    setHeader(route.name === "prefecture-compare"
      ? {
          title: `${prefectureName} 掲載議会くらべ`,
          lead: `${prefectureName}内の掲載議会の基本データを同じ尺度で見ます。`,
        }
      : {
          title: `${prefectureName} 議会見える化`,
          lead: "",
        });
    setRouteNav(route.name === "prefecture-compare"
      ? {
          back: { label: `${prefectureName}ページ`, href: prefPath(route.prefecture) },
          crumbs: [
            { label: "全国トップ", href: topPath() },
            { label: prefectureName, href: prefPath(route.prefecture) },
            { label: "5議会くらべ" },
          ],
        }
      : {
          back: { label: "全国トップ", href: topPath() },
          crumbs: [
            { label: "全国トップ", href: topPath() },
            { label: prefectureName },
          ],
        });
    showCouncilNav(false);
    state.councilSummaries = await loadCouncilSummaries(
      state.councils.filter((council) => council.prefecture === route.prefecture),
    );
    if (route.name === "prefecture-compare") {
      renderPrefectureComparisonPage(mainNode(), state.councilSummaries, route.prefecture);
    } else {
      renderPrefecturePage(
        mainNode(),
        state.councils,
        route.prefecture,
        state.councilSummaries,
      );
    }
    return;
  }

  if (route.name === "council" || route.name === "member") {
    if (!activePrefectureSlugs().has(route.prefecture)) {
      renderNotFound();
      return;
    }
    const previousCouncilId = state.currentCouncil?.id;
    if (previousCouncilId && previousCouncilId !== route.councilId) {
      state.councilSection = "area";
      state.view = "kaiha";
      state.query = "";
    }
    if (!previousCouncilId && route.name === "council") {
      state.councilSection = "area";
      state.view = "kaiha";
    }

    const bundle = await loadCouncilBundle(route.councilId, {
      includeSpeeches: COUNCILS_WITH_SPEECHES.has(route.councilId),
      includeVotes: councilsWithVotes().has(route.councilId),
    });
    state.currentCouncil = bundle.council;
    state.members = bundle.members;
    state.membersMeta = bundle.membersMeta;
    state.profile = bundle.profile;
    state.timeseries = bundle.timeseries;
    state.finance = bundle.finance;
    state.councilSummaries = await loadCouncilSummaries(
      state.councils.filter((council) => council.prefecture === route.prefecture),
    );
    state.speeches = bundle.speeches;
    state.speechesMeta = bundle.speechesMeta;
    state.votes = bundle.votes;
    state.votesMeta = bundle.votesMeta;

    if (route.name === "member") {
      renderMemberRoute(route.memberId);
    } else {
      renderCouncilRoute();
    }
    return;
  }

  renderNotFound();
}

function renderWithErrorBoundary() {
  applyRoute().then(() => {
    window.scrollTo({ top: 0, left: 0 });
  }).catch((err) => {
    if (err instanceof Error && err.message.includes("議会が見つかりません")) {
      renderNotFound();
      return;
    }
    console.error(err);
    showCouncilNav(false);
    setHeader({
      title: "読み込みエラー",
      lead: "データの読み込みに失敗しました。",
    });
    mainNode().innerHTML = "";
    mainNode().appendChild(
      el("p", { class: "empty-message" }, [
        `読み込みに失敗しました: ${err.message} `,
        el("a", { href: "#/" }, "トップへ戻る"),
      ]),
    );
  });
}

function setupTabs() {
  const tabs = document.querySelectorAll(".view-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.dataset.view;
      if (!view || view === state.view) return;
      state.view = view;
      if (view === "votes") state.query = "";
      renderCouncilRoute();
    });
  });
}

function setupStageControls() {
  window.addEventListener("council:section-change", (event) => {
    const section = event.detail?.section;
    if (!section || section === state.councilSection) return;
    state.councilSection = section;
    if (section === "area") {
      state.query = "";
    }
    renderCouncilRoute();
    window.scrollTo({ top: 0, left: 0 });
  });

  window.addEventListener("council:view-change", (event) => {
    const view = event.detail?.view;
    if (!view || view === state.view) return;
    state.view = view;
    if (view === "votes") state.query = "";
    renderCouncilRoute();
  });

  window.addEventListener("council:show-votes", () => {
    state.councilSection = "members";
    state.view = "votes";
    state.query = "";
    renderCouncilRoute();
    requestAnimationFrame(() => {
      const target = document.querySelector(".stage-tab-content") || mainNode();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  window.addEventListener("council:query-change", (event) => {
    state.query = event.detail?.query || "";
    renderCouncilRoute();
  });
}

function setupSearch() {
  const input = document.getElementById("search");
  const clearBtn = document.getElementById("search-clear");
  if (!input) return;

  input.addEventListener("input", () => {
    state.query = input.value;
    if (clearBtn) clearBtn.hidden = state.query.length === 0;
    renderCouncilRoute();
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      input.value = "";
      state.query = "";
      clearBtn.hidden = true;
      input.focus();
      renderCouncilRoute();
    });
  }
}

function setupCouncilVizEvents() {
  window.addEventListener("council:faction-focus", (event) => {
    const faction = event.detail?.faction;
    if (!faction || !state.currentCouncil) return;

    state.view = "kaiha";
    state.query = "";
    renderCouncilRoute();

    window.requestAnimationFrame(() => {
      const target = [...document.querySelectorAll(".kaiha-group")]
        .find((node) => node.dataset.faction === faction);
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      target.classList.add("is-highlighted");
      window.setTimeout(() => target.classList.remove("is-highlighted"), 1200);
    });
  });
}

function councilTypeLabel(council) {
  if (council?.type === "prefecture") return "県議会";
  if (council?.name?.includes("区議会")) return "区議会";
  return "市議会";
}

setupTabs();
setupStageControls();
setupSearch();
setupCouncilVizEvents();
window.addEventListener("hashchange", renderWithErrorBoundary);
renderWithErrorBoundary();
