const state = {
  sourceFilter: "all",
  labelFilter: "all",
  keywordGroupFilter: "all",
  sortMode: "score",
  payload: null,
};

const SECTION_CONFIGS = [
  {
    key: "arxiv",
    titleId: "arxiv-title",
    descriptionId: "arxiv-description",
    countId: "arxiv-count",
    listId: "arxiv-list",
    emptyMessage: "当前筛选下没有 arXiv 论文。",
  },
  {
    key: "discovery",
    titleId: "discovery-title",
    descriptionId: "discovery-description",
    countId: "discovery-count",
    listId: "discovery-list",
    emptyMessage: "当前筛选下没有 Nature / Joule 发现榜论文。",
  },
  {
    key: "core_ieee",
    titleId: "core-title",
    descriptionId: "core-description",
    countId: "core-count",
    listId: "core-list",
    emptyMessage: "当前筛选下没有核心电力期刊论文。",
  },
];

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
  document.getElementById("target-date").textContent = `Date ${meta.target_date}`;
  document.getElementById("updated-at").textContent = `Generated ${formatDateTime(meta.generated_at, meta.timezone)}`;
  document.getElementById("window-pill").textContent = `${meta.lookback_days}-day window`;

  const rssLink = document.getElementById("rss-link");
  if (rssLink) {
    rssLink.href = meta.feed_url || "./feed.xml";
  }

  const subscriptionNote = document.getElementById("subscription-note");
  if (subscriptionNote) {
    subscriptionNote.textContent = "Add this RSS feed to Feedly, Inoreader, or any RSS reader to follow daily updates.";
  }

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
    [{ value: "all", label: "全部" }, ...Object.keys(meta.source_counts).sort().map((source) => ({ value: source, label: source }))],
    state.sourceFilter,
    (value) => {
      state.sourceFilter = value;
      renderFrame();
      renderSections();
    },
  );

  const labels = [...new Set(papers.map((paper) => paper.relevance_label))];
  buildFilterChips(
    document.getElementById("label-filters"),
    [{ value: "all", label: "全部" }, ...labels.map((label) => ({ value: label, label }))],
    state.labelFilter,
    (value) => {
      state.labelFilter = value;
      renderFrame();
      renderSections();
    },
  );

  const keywordGroupCounts = buildKeywordGroupCounts(getBaseFilteredPapers(papers));
  const keywordGroupOptions = [
    { value: "all", label: "全部" },
    ...Array.from(keywordGroupCounts.entries()).map(([groupName, count]) => ({
      value: groupName,
      label: `${groupName} (${count})`,
    })),
  ];
  const keywordGroupValues = new Set(keywordGroupOptions.map((option) => option.value));
  if (!keywordGroupValues.has(state.keywordGroupFilter)) {
    state.keywordGroupFilter = "all";
  }

  buildFilterChips(
    document.getElementById("keyword-filters"),
    keywordGroupOptions,
    state.keywordGroupFilter,
    (value) => {
      state.keywordGroupFilter = value;
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
  let totalVisible = 0;

  SECTION_CONFIGS.forEach((config) => {
    const section = sections[config.key];
    const visiblePapers = getVisiblePapers(section.papers);
    totalVisible += visiblePapers.length;

    document.getElementById(config.titleId).textContent = section.title;
    document.getElementById(config.descriptionId).textContent = section.description;
    document.getElementById(config.countId).textContent = `${visiblePapers.length} 篇`;
    renderPaperList(document.getElementById(config.listId), visiblePapers, config.emptyMessage);
  });

  document.getElementById("result-count").textContent = `${totalVisible} 篇论文通过当前筛选`;
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
    const summaryElement = fragment.querySelector(".paper-card__summary");
    if (paper.abstract_raw && paper.abstract_raw.trim()) {
      summaryElement.innerHTML = formatStructuredText(paper.ai_summary || "");
    } else {
      summaryElement.textContent = "摘要不可用";
      summaryElement.classList.add("paper-card__summary--unavailable");
    }
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
    const keywordGroups = paper.matched_keyword_groups || [];
    keywordGroups.slice(0, 3).forEach((groupName) => {
      const badge = document.createElement("span");
      badge.textContent = groupName;
      categories.appendChild(badge);
    });
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

function getBaseFilteredPapers(papers) {
  return [...papers].filter((paper) => {
    const sourceMatch = state.sourceFilter === "all" || paper.source === state.sourceFilter;
    const labelMatch = state.labelFilter === "all" || paper.relevance_label === state.labelFilter;
    return sourceMatch && labelMatch;
  });
}

function getVisiblePapers(papers) {
  const filtered = getBaseFilteredPapers(papers).filter((paper) => {
    if (state.keywordGroupFilter === "all") {
      return true;
    }
    return Array.isArray(paper.matched_keyword_groups) && paper.matched_keyword_groups.includes(state.keywordGroupFilter);
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

function buildKeywordGroupCounts(papers) {
  const counts = new Map();
  papers.forEach((paper) => {
    (paper.matched_keyword_groups || []).forEach((groupName) => {
      counts.set(groupName, (counts.get(groupName) || 0) + 1);
    });
  });

  return new Map(
    Array.from(counts.entries()).sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    }),
  );
}

function buildFilterChips(container, options, activeValue, onClick) {
  container.innerHTML = "";
  options.forEach((option) => {
    const normalized = typeof option === "string" ? { value: option, label: option } : option;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `chip${normalized.value === activeValue ? " is-active" : ""}`;
    chip.textContent = normalized.label;
    chip.addEventListener("click", () => onClick(normalized.value));
    container.appendChild(chip);
  });
}

function renderErrorState(error) {
  document.getElementById("updated-at").textContent = "数据加载失败";
  document.getElementById("result-count").textContent = "0 篇论文通过当前筛选";

  SECTION_CONFIGS.forEach((config) => {
    const container = document.getElementById(config.listId);
    container.innerHTML = "";
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = `页面已经部署成功，但 latest.json 暂时无法读取：${error.message}`;
    container.appendChild(emptyState);
  });
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
