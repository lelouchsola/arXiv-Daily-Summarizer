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
    renderPaperList();
  });

  try {
    const response = await fetch("./latest.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load latest.json (${response.status})`);
    }

    state.payload = await response.json();
    renderFrame();
    renderPaperList();
  } catch (error) {
    renderErrorState(error);
  }
});

function renderFrame() {
  const { meta, papers } = state.payload;
  document.getElementById("site-title").textContent = meta.title;
  document.getElementById("site-subtitle").textContent = meta.subtitle;
  document.getElementById("target-date").textContent = `For ${meta.target_date}`;
  document.getElementById("updated-at").textContent = `Updated ${formatDateTime(meta.generated_at, meta.timezone)}`;

  const statsGrid = document.getElementById("stats-grid");
  statsGrid.innerHTML = "";
  const statCards = [
    ["Today's Picks", meta.paper_count],
    ["Sources", meta.source_count],
    ["Strong Matches", meta.strong_match_count],
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
      renderPaperList();
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
      renderPaperList();
    },
  );

  const errorBanner = document.getElementById("error-banner");
  if (meta.source_errors && meta.source_errors.length > 0) {
    errorBanner.hidden = false;
    errorBanner.textContent = `Partial source issues: ${meta.source_errors.join(" | ")}`;
  } else {
    errorBanner.hidden = true;
    errorBanner.textContent = "";
  }
}

function renderPaperList() {
  const container = document.getElementById("paper-list");
  container.innerHTML = "";

  if (!state.payload) {
    return;
  }

  const papers = getVisiblePapers();
  document.getElementById("result-count").textContent = `${papers.length} papers shown`;

  if (papers.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = "No papers match the current filters. Try switching source or relevance.";
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
    fragment.querySelector(".paper-card__title").textContent = paper.title;
    fragment.querySelector(".paper-card__meta").textContent =
      `${paper.authors.slice(0, 5).join(", ") || "Unknown authors"} · ${paper.published_date_local} ${paper.published_time_local}`;
    fragment.querySelector(".score-badge").textContent = `Score ${paper.final_score.toFixed(1)}`;
    fragment.querySelector(".label-badge").textContent = paper.relevance_label;
    fragment.querySelector(".paper-card__summary").textContent = paper.ai_summary;
    fragment.querySelector(".paper-card__value").textContent = paper.application_value;

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

function getVisiblePapers() {
  const papers = [...state.payload.papers].filter((paper) => {
    const sourceMatch = state.sourceFilter === "all" || paper.source === state.sourceFilter;
    const labelMatch = state.labelFilter === "all" || paper.relevance_label === state.labelFilter;
    return sourceMatch && labelMatch;
  });

  papers.sort((left, right) => {
    if (state.sortMode === "latest") {
      return new Date(right.published_at_local) - new Date(left.published_at_local);
    }
    if (state.sortMode === "journal") {
      return left.journal.localeCompare(right.journal);
    }
    return right.final_score - left.final_score;
  });

  return papers;
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
  document.getElementById("updated-at").textContent = "Build data unavailable";
  document.getElementById("result-count").textContent = "0 papers shown";
  const container = document.getElementById("paper-list");
  container.innerHTML = "";

  const emptyState = document.createElement("div");
  emptyState.className = "empty-state";
  emptyState.textContent = `The site build is ready, but the latest dataset could not be loaded. ${error.message}`;
  container.appendChild(emptyState);
}

function formatDateTime(isoString, timezone) {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: timezone,
  }).format(date);
}
