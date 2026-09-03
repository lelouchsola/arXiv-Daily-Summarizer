# Daily Paper Briefing

This repository builds a daily research briefing website for power systems, optimization, and sustainable energy.

Instead of sending an email, the pipeline now:

1. Runs once per day with GitHub Actions.
2. Collects papers released on the same day from arXiv and selected journals.
3. Scores and ranks the papers.
4. Generates short Chinese summaries.
5. Publishes the result to GitHub Pages.

## Current status

The project now ships a GitHub Pages workflow and a static front end in [site/index.html](/C:/codex_workspace/dailyPaper/site/index.html).

Implemented pieces:

1. Daily static site build pipeline.
2. arXiv collector.
3. Crossref-based journal metadata collector for:
   - Nature Energy
   - Nature Communications
   - Joule
   - IEEE Transactions on Smart Grid
   - IEEE Transactions on Power Systems
   - IEEE Transactions on Sustainable Energy
4. Rule-based scoring, batch deduplication, and optional DeepSeek summaries.

Notes:

1. Journal collection is intentionally non-blocking. If one source fails, the site still publishes.
2. The site only shows the current day's build. No cross-day history is stored.
3. DeepSeek is optional. Without `DEEPSEEK_API_KEY`, the site still builds with fallback summaries.

## Repository layout

```text
.github/workflows/build_daily_site.yml
collectors/
pipeline/
scripts/build_daily_site.py
site/
IMPLEMENTATION_DESIGN.md
```

## Required secrets and settings

Open your repository settings and configure:

### GitHub Actions secrets

1. `DEEPSEEK_API_KEY`
   Optional. Enables AI summaries and model-assisted relevance scoring.
2. `CROSSREF_MAILTO`
   Optional but recommended. A contact email sent with Crossref requests.
3. `OPENALEX_API_KEY`
   Optional. Improves the reliability of missing-abstract enrichment; the site still builds without it.

### Repository Pages settings

1. Enable GitHub Pages for the repository.
2. Set the source to GitHub Actions.

The workflow uses the default `GITHUB_TOKEN`, so a personal access token is not required for normal Pages deployment.

## Environment variables

See [.env.example](/C:/codex_workspace/dailyPaper/.env.example).

Main variables:

1. `TARGET_TIMEZONE`
2. `SITE_TITLE`
3. `SITE_SUBTITLE`
4. `MAX_RESULTS`
5. `SUMMARY_COUNT`
6. `ARXIV_CATEGORIES`
7. `ENABLED_SOURCES`

## Local usage

```bash
pip install -r requirements.txt
python -m scripts.build_daily_site
```

The build writes:

1. [site/latest.json](/C:/codex_workspace/dailyPaper/site/latest.json)
2. [site/index.html](/C:/codex_workspace/dailyPaper/site/index.html)

Open the generated site locally with any static server if you want to preview the full experience.

## Scheduled publishing

The workflow in [.github/workflows/build_daily_site.yml](/C:/codex_workspace/dailyPaper/.github/workflows/build_daily_site.yml) runs once per day and deploys the `site/` directory to GitHub Pages.

Default schedule:

1. `30 0 * * *` UTC
2. Equivalent to `08:30` in `Asia/Shanghai`

## Next steps

The repository now has the first full GitHub Pages version in place. The next likely improvements are:

1. Improve journal-specific abstract retrieval for IEEE and Joule.
2. Tune the ranking weights.
3. Add richer source-specific tags and filters in the front end.
