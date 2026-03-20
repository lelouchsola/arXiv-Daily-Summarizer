# Daily Paper 网页日报

这个仓库现在已经从“每日邮件推送”改造成“每日静态网页发布”。

系统会通过 GitHub Actions 每天运行一次，完成以下工作：

1. 抓取当天发布的论文或期刊文章。
2. 按研究相关性和来源质量进行打分排序。
3. 生成中文摘要和简短点评。
4. 输出静态网页。
5. 部署到 GitHub Pages。

## 当前版本包含什么

当前已经接入或预留了这些来源：

1. arXiv
2. Nature Energy
3. Nature Communications
4. Joule
5. IEEE Transactions on Smart Grid
6. IEEE Transactions on Power Systems
7. IEEE Transactions on Sustainable Energy

当前特性：

1. 每天只展示当天结果，不保存历史。
2. 单个来源失败不会阻塞整站发布。
3. 支持规则打分、批次内去重、摘要生成。
4. 如果没有配置 `DEEPSEEK_API_KEY`，仍然可以构建网页，只是会使用回退摘要。

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

1. `30 0 * * *` UTC
2. 对应北京时间 `08:30`

## 设计文档

详细设计见 [IMPLEMENTATION_DESIGN.md](/C:/codex_workspace/dailyPaper/IMPLEMENTATION_DESIGN.md)。
