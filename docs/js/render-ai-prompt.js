import { el } from "./utils.js?v=20260615-no-member-photos-v1";

const AI_LINK_URL_LIMIT = 2000;
const AI_SERVICES = [
  {
    key: "chatgpt",
    label: "ChatGPT",
    icon: "GPT",
    baseUrl: "https://chatgpt.com/",
    url: (encoded) => `https://chatgpt.com/?q=${encoded}`,
    acceptsPrompt: true,
  },
  {
    key: "claude",
    label: "Claude",
    icon: "C",
    baseUrl: "https://claude.ai/new",
    url: (encoded) => `https://claude.ai/new?q=${encoded}`,
    acceptsPrompt: true,
  },
  {
    key: "gemini",
    label: "Gemini",
    icon: "G",
    baseUrl: "https://gemini.google.com/app",
    url: () => "https://gemini.google.com/app",
    acceptsPrompt: false,
  },
  {
    key: "perplexity",
    label: "Perplexity",
    icon: "P",
    baseUrl: "https://www.perplexity.ai/",
    url: (encoded) => `https://www.perplexity.ai/search?q=${encoded}`,
    acceptsPrompt: true,
  },
];

export function renderAiPromptCard({ title, lead, prompt, prompts = null, compact = false }) {
  const items = normalizePromptItems(prompt, prompts);
  let activeIndex = 0;
  const textarea = el("textarea", {
    class: "ai-prompt-text",
    readonly: "",
    rows: compact ? 3 : 5,
  }, items[activeIndex].text);
  const status = el("span", { class: "copy-status", "aria-live": "polite" }, "");
  const button = el("button", {
    type: "button",
    class: "copy-button is-primary",
    onclick: () => copyPromptText(textarea.value, textarea, button, status),
  }, "📋 この質問をコピー");
  const serviceLinks = el("div", { class: "ai-service-links" });

  const setActivePrompt = (index) => {
    activeIndex = index;
    textarea.value = items[activeIndex].text;
    tabRow.querySelectorAll(".ai-prompt-tab").forEach((tab, tabIndex) => {
      tab.classList.toggle("is-active", tabIndex === activeIndex);
      tab.setAttribute("aria-selected", tabIndex === activeIndex ? "true" : "false");
    });
    renderAiServiceButtons(serviceLinks, textarea, status);
  };
  const tabRow = renderPromptTabs(items, setActivePrompt);

  const card = el("article", { class: `ai-prompt-card${compact ? " is-compact" : ""}` }, [
    el("div", { class: "ai-prompt-head" }, [
      el("span", { class: "ai-prompt-robot", "aria-hidden": "true" }, "🤖"),
      el("div", {}, [
        el("h3", {}, title),
        lead ? el("p", {}, lead) : null,
      ]),
    ]),
    tabRow,
    textarea,
    button,
    status,
    serviceLinks,
    el("p", { class: "ai-caution" }, "※ボタンを押すと質問をコピーしてからAIが開きます。貼り付けて送信してください。AIの回答は誤ることがあります。"),
  ]);
  renderAiServiceButtons(serviceLinks, textarea, status);
  return card;
}

function normalizePromptItems(prompt, prompts) {
  const items = Array.isArray(prompts) && prompts.length
    ? prompts
    : [{ key: "default", label: "質問", text: prompt || "" }];
  const filtered = items.filter((item) => item?.label && item?.text);
  return filtered.length ? filtered : [{ key: "default", label: "質問", text: "" }];
}

function renderPromptTabs(items, onSelect) {
  if (items.length <= 1) return null;
  return el("div", { class: "ai-prompt-tabs", role: "tablist", "aria-label": "質問タイプ" },
    items.map((item, index) =>
      el("button", {
        type: "button",
        class: `ai-prompt-tab${index === 0 ? " is-active" : ""}`,
        role: "tab",
        "aria-selected": index === 0 ? "true" : "false",
        onclick: () => onSelect(index),
      }, item.label),
    ),
  );
}

function renderAiServiceButtons(container, textarea, status) {
  container.innerHTML = "";
  const links = aiServiceLinks(textarea.value);
  container.append(
    el("p", { class: "ai-link-note" }, "コピーして、そのままAIを開く（開いた画面に貼り付け）"),
    el("div", { class: "ai-service-button-row" }, links.map((link) =>
      el("button", {
        type: "button",
        class: `ai-service-link is-${link.key}`,
        title: link.note || undefined,
        onclick: () => copyAndOpenAi(textarea.value, textarea, status, link.url),
      }, [
        el("span", { class: `ai-service-icon is-${link.key}`, "aria-hidden": "true" }, link.icon),
        link.label,
      ]),
    )),
    el("p", { class: "ai-link-note is-subtle" }, "ChatGPT / Claude / Perplexityは短い質問なら入力欄に入った状態で開きます。長い質問やGeminiではコピーして貼り付けてください。"),
  );
}

export function aiServiceLinks(prompt) {
  const encoded = encodeURIComponent(prompt);
  return AI_SERVICES.map((service) => {
    const promptUrl = service.url(encoded);
    const canAttachPrompt = service.acceptsPrompt && promptUrl.length <= AI_LINK_URL_LIMIT;
    return {
      key: service.key,
      label: service.label,
      icon: service.icon,
      url: canAttachPrompt ? promptUrl : service.baseUrl,
      note: canAttachPrompt ? "" : "質問はコピー済みです。開いた画面に貼り付けてください",
    };
  });
}

async function copyPromptText(text, textarea, button, status) {
  button.disabled = true;
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = "コピーしました";
  } catch {
    textarea.focus();
    textarea.select();
    status.textContent = "コピーできない場合は、選択された本文を手動でコピーしてください";
  } finally {
    window.setTimeout(() => {
      button.disabled = false;
      if (status.textContent === "コピーしました") status.textContent = "";
    }, 1600);
  }
}

async function copyAndOpenAi(text, textarea, status, url) {
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = "コピーしました。AIサービスを開きます";
  } catch {
    textarea.focus();
    textarea.select();
    status.textContent = "コピーできない場合は、選択された本文を手動でコピーしてください";
  } finally {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

export function officialCouncilUrl(council) {
  const links = Array.isArray(council?.official_links) ? council.official_links : [];
  const official = links.find((link) => /公式|ご案内/.test(link.label || ""));
  return official?.url || links[0]?.url || "";
}

export function councilAreaName(council) {
  return (council?.name || "").replace(/議会$/, "").trim();
}
