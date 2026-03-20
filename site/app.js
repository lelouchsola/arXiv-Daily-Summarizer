const state = {
  sourceFilter: "all",
  labelFilter: "all",
  sortMode: "score",
  payload: null,
};

document.addEventListener("DOMContentLoaded", async () => {
  const sortSelect = document.getElementById("sort-select");
  sortSelect.addEventListener("change", (event) => {
    state.sortMode = event.target.value;
    renderSections();
  });

  try {
    const response = await fetch("./latest.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load latest.json (${response.status})`);
    }

    state.payload = await response.json();
    renderFrame();
    renderSections();
  } catch (error) {
    renderErrorState(error);
  }
});

function renderFrame() {
  const { meta, papers } = state.payload;
  document.getElementById("site-title").textContent = meta.title;
  document.getElementById("site-subtitle").textContent = meta.subtitle;
  document.getElementById("target-date").textContent = `更新日期 ${meta.target_date}`;
  document.getElementById("updated-at").textContent = `生成时间 ${formatDateTime(meta.generated_at, meta.timezone)}`;
  document.getElementById("window-pill").textContent = `近 ${meta.lookback_days} 天窗口`;

  const statsGrid = document.getElementById("stats-grid");
  statsGrid.innerHTML = "";
  const statCards = [
    ["今日入选", meta.paper_count],
    ["来源数", meta.source_count],
    ["强相关", meta.strong_match_count],
  ];

  statCards.forEach(([label, value]) => {
    const article = document.createElement("article");
    article.className = "stat-card";
    article.innerHTML = `
      <span class="stat-card__label">${label}</span>
      <strong class="stat-card__value">${value}</strong>
    `;
    statsGrid.appendChild(article);
  });

  buildFilterChips(
    document.getElementById("source-filters"),
    ["all", ...Object.keys(meta.source_counts).sort()],
    state.sourceFilter,
    (value) => {
      state.sourceFilter = value;
      renderFrame();
      renderSections();
    },
  );

  const labels = ["all", ...new Set(papers.map((paper) => paper.relevance_label))];
  buildFilterChips(
    document.getElementById("label-filters"),
    labels,
    state.labelFilter,
    (value) => {
      state.labelFilter = value;
      renderFrame();
      renderSections();
    },
  );

  const errorBanner = document.getElementById("error-banner");
  if (meta.source_errors && meta.source_errors.length > 0) {
    errorBanner.hidden = false;
    errorBanner.textContent = `部分来源抓取异常：${meta.source_errors.join(" | ")}`;
  } else {
    errorBanner.hidden = true;
    errorBanner.textContent = "";
  }
}

function renderSections() {
  const sections = state.payload.sections;
  const discovery = getVisiblePapers(sections.discovery.papers);
  const core = getVisiblePapers(sections.core_ieee.papers);

  document.getElementById("result-count").textContent = `${discovery.length + core.length} 篇论文通过当前筛选`;
  document.getElementById("discovery-title").textContent = sections.discovery.title;
  document.getElementById("discovery-description").textContent = sections.discovery.description;
  document.getElementById("discovery-count").textContent = `${discovery.length} 篇`;
  document.getElementById("core-title").textContent = sections.core_ieee.title;
  document.getElementById("core-description").textContent = sections.core_ieee.description;
  document.getElementById("core-count").textContent = `${core.length} 篇`;

  renderPaperList(document.getElementById("discovery-list"), discovery, "当前筛选下没有跨来源发现榜论文。");
  renderPaperList(document.getElementById("core-list"), core, "当前筛选下没有核心电力期刊论文。");
}

function renderPaperList(container, papers, emptyMessage) {
  container.innerHTML = "";
  if (papers.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = emptyMessage;
    container.appendChild(emptyState);
    return;
  }

  const template = document.getElementById("paper-card-template");
  papers.forEach((paper, index) => {
    const fragment = template.content.cloneNode(true);
    const card = fragment.querySelector(".paper-card");
    card.style.animationDelay = `${Math.min(index * 40, 320)}ms`;

    fragment.querySelector(".paper-card__source").textContent = paper.source;
    fragment.querySelector(".paper-card__journal").textContent = paper.journal;
    fragment.querySelector(".paper-card__age").textContent = buildAgeLabel(paper);
    fragment.querySelector(".paper-card__title").textContent = paper.title;
    fragment.querySelector(".paper-card__meta").textContent =
      `${paper.authors.slice(0, 5).join(", ") || "Unknown authors"} · ${paper.published_date_local} ${paper.published_time_local}`;
    fragment.querySelector(".score-badge").textContent = `推荐分 ${paper.final_score.toFixed(1)} / 10`;
    fragment.querySelector(".label-badge").textContent = paper.relevance_label;
    fragment.querySelector(".paper-card__reason").textContent = paper.score_reason;
    fragment.querySelector(".paper-card__summary").innerHTML = formatStructuredText(paper.ai_summary || "");
    fragment.querySelector(".paper-card__value").textContent = paper.application_value;

    const keywordContainer = fragment.querySelector(".paper-card__keywords");
    const matchedKeywords = paper.matched_keywords && paper.matched_keywords.length > 0 ? paper.matched_keywords : ["待补关键词"];
    matchedKeywords.forEach((keyword) => {
      const chip = document.createElement("span");
      chip.className = "keyword-chip";
      chip.textContent = keyword;
      keywordContainer.appendChild(chip);
    });

    const categories = fragment.querySelector(".paper-card__categories");
    paper.categories.slice(0, 4).forEach((category) => {
      const badge = document.createElement("span");
      badge.textContent = category;
      categories.appendChild(badge);
    });

    const primaryLink = fragment.querySelector(".primary-link");
    primaryLink.href = paper.url;

    const secondaryLink = fragment.querySelector(".secondary-link");
    if (paper.pdf_url) {
      secondaryLink.href = paper.pdf_url;
      secondaryLink.hidden = false;
    }

    container.appendChild(fragment);
  });
}

function getVisiblePapers(papers) {
  const filtered = [...papers].filter((paper) => {
    const sourceMatch = state.sourceFilter === "all" || paper.source === state.sourceFilter;
    const labelMatch = state.labelFilter === "all" || paper.relevance_label === state.labelFilter;
    return sourceMatch && labelMatch;
  });

  filtered.sort((left, right) => {
    if (state.sortMode === "latest") {
      return new Date(right.published_at_local) - new Date(left.published_at_local);
    }
    if (state.sortMode === "journal") {
      return left.journal.localeCompare(right.journal);
    }
    return right.final_score - left.final_score;
  });

  return filtered;
}

function buildFilterChips(container, options, activeValue, onClick) {
  container.innerHTML = "";
  options.forEach((option) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `chip${option === activeValue ? " is-active" : ""}`;
    chip.textContent = option;
    chip.addEventListener("click", () => onClick(option));
    container.appendChild(chip);
  });
}

function renderErrorState(error) {
  document.getElementById("updated-at").textContent = "数据加载失败";
  document.getElementById("result-count").textContent = "0 篇论文通过当前筛选";

  const discoveryList = document.getElementById("discovery-list");
  const coreList = document.getElementById("core-list");
  discoveryList.innerHTML = "";
  coreList.innerHTML = "";

  const emptyState = document.createElement("div");
  emptyState.className = "empty-state";
  emptyState.textContent = `页面已经部署成功，但 latest.json 暂时无法读取：${error.message}`;
  discoveryList.appendChild(emptyState.cloneNode(true));
  coreList.appendChild(emptyState);
}

function buildAgeLabel(paper) {
  const today = new Date();
  const published = new Date(paper.published_at_local);
  const diffDays = Math.max(Math.floor((today - published) / (1000 * 60 * 60 * 24)), 0);
  if (diffDays === 0) return "今日发布";
  if (diffDays === 1) return "昨天发布";
  return `${diffDays} 天前发布`;
}

function formatStructuredText(text) {
  const escaped = escapeHtml(text || "");
  const withBold = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold.replace(/\n/g, "<br>");
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDateTime(isoString, timezone) {
  if (!isoString) return "待生成";
  const date = new Date(isoString);
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
  }).format(date);
}
