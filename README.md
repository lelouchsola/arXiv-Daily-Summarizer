# Daily Paper 网页日报

这个仓库现在已经从“每日邮件推送”改造成“每日静态网页发布”。

系统会通过 GitHub Actions 每天运行一次，完成以下工作：

1. 抓取近期发布的论文、期刊文章与公开数据论文。
2. 按研究相关性和来源质量进行打分排序。
3. 生成中文摘要和简短点评。
4. 输出静态网页。
5. 部署到 GitHub Pages。

## 当前版本包含什么

当前页面分为四条独立阅读线：

1. arXiv 精选榜。
2. Nature / Joule 发现榜。
3. IEEE Transactions、Applied Energy 等核心电力期刊榜。
4. 最新公开数据集：Scientific Data、IEEE Data Descriptions、Data in Brief、Earth System Science Data。

当前特性：

1. 每天只展示最新一次构建结果，不保存历史。
2. 普通论文按原有窗口与排序逻辑处理；公开数据集使用最近 14 天窗口，每天最多展示 5 条，不足时不补齐。
3. 数据集必须同时具备明确的电力/能源领域信号，材料、生物和纯气象数据不会仅凭来源入选。
4. 单个来源失败不会阻塞整站发布。
5. 支持规则打分、批次内去重、摘要生成。
6. 如果没有配置 `DEEPSEEK_API_KEY`，仍然可以构建网页，只是会使用回退摘要。

## 仓库结构

```text
.github/workflows/build_daily_site.yml
collectors/
pipeline/
scripts/build_daily_site.py
site/
IMPLEMENTATION_DESIGN.md
```

## 需要的 GitHub 配置

### 1. GitHub Actions

需要启用仓库的 GitHub Actions。

### 2. GitHub Pages

需要在仓库设置里启用 GitHub Pages，并把发布来源设置为 GitHub Actions。

### 3. Secrets

建议配置以下 secrets：

1. `DEEPSEEK_API_KEY`
   可选。用于生成 AI 摘要和模型辅助评分。
2. `CROSSREF_MAILTO`
   可选但推荐。用于 Crossref 请求中的联系邮箱。
3. `OPENALEX_API_KEY`
   可选。用于提高缺失摘要补全请求的稳定性；不配置也可以正常构建。

说明：

1. 正常的 Pages 部署不需要你额外创建个人访问令牌。
2. workflow 会使用 GitHub 自动提供的 `GITHUB_TOKEN`。

## 环境变量

参考 [.env.example](/C:/codex_workspace/dailyPaper/.env.example)。

主要变量：

1. `TARGET_TIMEZONE`
2. `SITE_TITLE`
3. `SITE_SUBTITLE`
4. `MAX_RESULTS`
5. `SUMMARY_COUNT`
6. `ARXIV_CATEGORIES`
7. `ENABLED_SOURCES`
8. `MAX_DATASET_RESULTS`
9. `DATASET_LOOKBACK_DAYS`

## 本地运行

```bash
pip install -r requirements.txt
python -m scripts.build_daily_site
```

构建结果会写到：

1. [site/latest.json](/C:/codex_workspace/dailyPaper/site/latest.json)
2. [site/index.html](/C:/codex_workspace/dailyPaper/site/index.html)

## 默认定时

workflow 文件在 [.github/workflows/build_daily_site.yml](/C:/codex_workspace/dailyPaper/.github/workflows/build_daily_site.yml)。

默认 cron：

1. `17 1 * * *` UTC
2. 对应北京时间 `09:17`

## 设计文档

详细设计见 [IMPLEMENTATION_DESIGN.md](/C:/codex_workspace/dailyPaper/IMPLEMENTATION_DESIGN.md)。
