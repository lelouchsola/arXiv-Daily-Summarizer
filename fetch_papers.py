import os
import smtplib
import arxiv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from openai import OpenAI
from collections import Counter, defaultdict
import re
from difflib import SequenceMatcher

# ========== Configuration ==========

# arXiv search configuration
CATEGORIES = ['math.OC', 'eess.SY']  # 你的专属研究领域
MAX_RESULTS = 10  # 每天最多推送的论文数量（过滤后都是精选，可适当调低）
MIN_PAPERS_PER_CATEGORY = 1  
MAX_AGE_HOURS = 72  # 只抓取过去 48 小时内的论文（建议 48 小时以覆盖 arXiv 周末不更新的情况）

# Language configuration
EMAIL_LANGUAGE = os.environ.get('EMAIL_LANGUAGE', 'zh')  # 默认中文摘要

# DeepSeek API configuration (已修改为 DeepSeek 官方配置)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEEPSEEK_MODEL = 'deepseek-chat' 

# Email configuration (已适配 163 邮箱默认配置)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')  # 注意：这里必须填 163 邮箱的授权码
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.163.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))

# Quality filtering thresholds
MIN_ABSTRACT_LENGTH = 100  
SIMILARITY_THRESHOLD = 0.85  

# Language text templates
TEXT_TEMPLATES = {
    'zh': {
        'title': 'arXiv 每日论文精选推送',
        'date_notice': '论文时效说明',
        'today': '今天',
        'yesterday': '昨天',
        'days_ago': '天前',
        'published_today': '<strong>{count} 篇</strong>是今天发布',
        'published_yesterday': '<strong>{count} 篇</strong>是昨天发布',
        'published_older_multi': '<strong>{count} 篇</strong>是 2 天及更早前发布',
        'notice_text': '本次推送的 {total} 篇最新论文中，{parts}。',
        'new_today': '今日首发',
        'yesterday_label': '昨日发布',
        'days_ago_label': '{days} 天前',
        'high_quality': '⭐ 高度契合',
        'authors': '作者',
        'published': '发布日期',
        'categories': '分类',
        'quality_score': '契合度评分',
        'ai_summary': 'AI 摘要',
        'view_pdf': '查看 PDF',
        'footer_auto': '本邮件由专属定制版 arXiv Daily Summarizer 自动生成',
        'footer_powered': '由 DeepSeek-V3 提供摘要服务'
    },
    'en': {
        'title': 'arXiv Daily Paper Digest',
        'date_notice': 'Date Notice',
        'today': 'today',
        'yesterday': 'yesterday',
        'days_ago': 'days ago',
        'published_today': '<strong>{count} papers</strong> published today',
        'published_yesterday': '<strong>{count} papers</strong> published yesterday',
        'published_older_multi': '<strong>{count} papers</strong> published 2+ days ago',
        'notice_text': 'Of the {total} papers in this digest, {parts}.',
        'new_today': 'NEW TODAY',
        'yesterday_label': 'YESTERDAY',
        'days_ago_label': '{days} DAYS AGO',
        'high_quality': '⭐ HIGH MATCH',
        'authors': 'Authors',
        'published': 'Published',
        'categories': 'Categories',
        'quality_score': 'Match Score',
        'ai_summary': 'AI Summary',
        'view_pdf': 'View PDF',
        'footer_auto': 'Generated automatically by Custom arXiv Daily Summarizer',
        'footer_powered': 'Powered by DeepSeek-V3'
    }
}


def calculate_paper_quality_score(paper):
    """
    为你定制的质量与契合度打分系统
    """
    score = 0.0
    
    # 维度 1: 摘要长度 (过滤水文)
    abstract_length = len(paper.get('abstract', ''))
    if abstract_length > 500:
        score += 2.0
    elif abstract_length > 300:
        score += 1.0
    elif abstract_length < MIN_ABSTRACT_LENGTH:
        score -= 2.0
    
    # 维度 2: 作者数量
    num_authors = len(paper.get('authors', '').split(','))
    if 3 <= num_authors <= 8:
        score += 1.0
    elif num_authors > 8:
        score += 0.5
    
    # 维度 3: 核心关键词 (已为你替换为电力系统与学习优化方向)
    title = paper.get('title', '').lower()
    abstract = paper.get('abstract', '').lower()
    
    important_keywords = [
        # 你的核心交叉领域
        'learn to optimize', 'decision-focused', 'predict-and-optimize', 
        'end-to-end', 'reinforcement learning', 'machine learning', 'data-driven',
        # 电力与能源系统
        'power system', 'energy system', 'smart grid', 'microgrid', 
        'hydrogen', 'power-to-gas', 'p2g', 'electrolyzer', 'fuel cell',
        'unit commitment', 'economic dispatch', 'optimal power flow', 'opf',
        # 灵活性与优化
        'flexibility', 'flexible resource', 'demand response', 'energy storage',
        'renewable', 'stochastic optimization', 'robust optimization',
        # 学术通用词汇
        'novel', 'efficient', 'framework', 'state-of-the-art'
    ]
    
    # 标题命中加分权重高
    for keyword in important_keywords:
        if keyword in title:
            score += 1.5
        # 摘要命中也给予一定加分
        elif keyword in abstract:
            score += 0.5
    
    # 惩罚过短或过长的标题
    title_words = len(title.split())
    if title_words < 5:
        score -= 0.5
    elif title_words > 25:
        score -= 0.3
        
    return score


def calculate_title_similarity(title1, title2):
    def normalize(text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text
    
    norm_title1 = normalize(title1)
    norm_title2 = normalize(title2)
    return SequenceMatcher(None, norm_title1, norm_title2).ratio()


def remove_duplicate_papers(papers):
    if not papers:
        return papers
    
    filtered_papers = []
    
    for paper in papers:
        is_duplicate = False
        for existing_paper in filtered_papers:
            similarity = calculate_title_similarity(paper['title'], existing_paper['title'])
            if similarity >= SIMILARITY_THRESHOLD:
                print(f"  🔄 发现相似论文 (相似度: {similarity:.2f}):")
                print(f"     已存在: {existing_paper['title'][:60]}...")
                print(f"     重复项: {paper['title'][:60]}...")
                
                if paper.get('quality_score', 0) > existing_paper.get('quality_score', 0):
                    filtered_papers.remove(existing_paper)
                    filtered_papers.append(paper)
                    print(f"     → 保留了高分版本")
                else:
                    print(f"     → 忽略重复项")
                
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_papers.append(paper)
    
    return filtered_papers


def get_latest_papers():
    print(f"🔍 Searching for latest papers on arXiv...")
    print(f"📚 Categories: {', '.join(CATEGORIES)}")
    print(f"⏳ Time filter: Last {MAX_AGE_HOURS} hours")
    
    client = arxiv.Client()
    papers_by_category = defaultdict(list)
    seen_ids = set()
    
    for category in CATEGORIES:
        print(f"\n🔎 Searching category: {category}")
        try:
            search = arxiv.Search(
                query=f'cat:{category}',
                max_results=MAX_RESULTS * 3,  # 多抓取一些用于时间过滤和打分筛选
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            results = list(client.results(search))
            print(f"  API 返回 {len(results)} 篇论文")
            
            valid_count = 0
            for result in results:
                if result.entry_id not in seen_ids:
                    
                    # ========== 核心时间拦截器 ==========
                    now = datetime.now(result.published.tzinfo)
                    time_diff = now - result.published
                    
                    if time_diff.total_seconds() > MAX_AGE_HOURS * 3600:
                        continue  # 超过 MAX_AGE_HOURS 小时的直接丢弃
                    # ==================================
                    
                    seen_ids.add(result.entry_id)
                    abstract_text = result.summary if hasattr(result, 'summary') else ''
                    
                    paper = {
                        'title': result.title,
                        'authors': ', '.join([author.name for author in result.authors]),
                        'abstract': abstract_text,
                        'pdf_url': result.pdf_url,
                        'published': result.published,
                        'categories': result.categories,
                        'entry_id': result.entry_id,
                        'primary_category': category
                    }
                    
                    paper['quality_score'] = calculate_paper_quality_score(paper)
                    papers_by_category[category].append(paper)
                    valid_count += 1
                    print(f"  ✓ {result.title[:50]}... (契合度: {paper['quality_score']:.1f})")
            
            papers_by_category[category].sort(key=lambda x: x['quality_score'], reverse=True)
            print(f"  在 {category} 中筛选出 {valid_count} 篇最新有效论文")
            
        except Exception as e:
            print(f"  ❌ Error searching {category}: {str(e)}")
            continue
    
    print(f"\n⚖️ 类别平衡与最终筛选...")
    selected_papers = []
    
    for category in CATEGORIES:
        category_papers = papers_by_category[category]
        if category_papers:
            num_to_take = min(MIN_PAPERS_PER_CATEGORY, len(category_papers))
            selected_papers.extend(category_papers[:num_to_take])
    
    remaining_slots = MAX_RESULTS - len(selected_papers)
    if remaining_slots > 0:
        all_remaining = []
        for category, papers in papers_by_category.items():
            for paper in papers:
                if paper not in selected_papers:
                    all_remaining.append(paper)
        
        # 按照你的专属契合度评分择优录取
        all_remaining.sort(key=lambda x: x['quality_score'], reverse=True)
        selected_papers.extend(all_remaining[:remaining_slots])
    
    print(f"\n🔍 查重检测中...")
    selected_papers = remove_duplicate_papers(selected_papers)
    selected_papers.sort(key=lambda x: x['published'], reverse=True)
    
    print(f"\n✅ 收集完毕，共提取: {len(selected_papers)} 篇论文")
    
    category_dist = Counter([p['primary_category'] for p in selected_papers])
    for cat, count in category_dist.items():
        print(f"   {cat}: {count} 篇")
    
    return selected_papers


def analyze_paper_dates(papers):
    now = datetime.now()
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()
    
    date_stats = {
        'today': 0,
        'yesterday': 0,
        'older': 0,
        'date_distribution': Counter()
    }
    
    for paper in papers:
        paper_date = paper['published'].date()
        date_stats['date_distribution'][paper_date] += 1
        
        if paper_date == today:
            date_stats['today'] += 1
        elif paper_date == yesterday:
            date_stats['yesterday'] += 1
        else:
            date_stats['older'] += 1
    
    return date_stats


def summarize_paper(paper, language='zh'):
    print(f"\n🤖 正在调用 DeepSeek 提取摘要:")
    print(f"   {paper['title'][:70]}...")
    
    summaries = {}
    
    prompts = {
        'zh': f"""请作为一名电力系统与能源优化领域的资深研究员，用中文总结以下学术论文：
1. 研究背景和核心动机（1-2句话）
2. 提出的数学模型、优化算法或主要创新点（2-3句话，如果涉及decision-focused或机器学习，请着重说明）
3. 实验验证及核心结论（1-2句话）
4. 对现实电力/能源系统的潜在应用价值（1句话）
5. 领域判定：明确说明本文是否与“电力系统优化”相关（请以【强相关】、【弱相关】或【不相关】开头，并用一句话简述理由）

论文标题：{paper['title']}

论文摘要：
{paper['abstract']}

请用简洁严谨的学术语言总结，适合快速阅读理解。""",
        'en': f"""Please act as a senior researcher in Power Systems and Energy Optimization, and summarize the following paper:
1. Research background and motivation (1-2 sentences)
2. Mathematical models, optimization algorithms, or main innovations (2-3 sentences, highlight if related to decision-focused or machine learning)
3. Experimental validation and conclusions (1-2 sentences)
4. Potential application to real-world power/energy systems (1 sentence)

Paper title: {paper['title']}

Paper abstract:
{paper['abstract']}

Please use concise and rigorous academic language."""
    }
    
    langs_to_generate = ['zh', 'en'] if language == 'both' else [language]
    
    try:
        client = OpenAI(
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
        )
        
        for lang in langs_to_generate:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {
                        'role': 'user',
                        'content': prompts[lang]
                    }
                ],
                stream=True
            )
            
            # 【修复版】安全解析流式响应，适配官方 deepseek-chat
            summary = ""
            for chunk in response:
                if getattr(chunk, 'choices', None) and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    answer_chunk = getattr(delta, 'content', '') or ''
                    if answer_chunk:
                        summary += answer_chunk
            
            summaries[lang] = summary.strip()
            print(f"   ✅ {'中文' if lang == 'zh' else '英文'} 摘要生成完毕")
        
        if language == 'both':
            return summaries
        else:
            return summaries[language]
    
    except Exception as e:
        print(f"   ❌ AI 摘要生成失败: {str(e)}")
        error_msg = {
            'zh': "摘要生成失败，请直接点击下方链接查看原文 PDF。",
            'en': "Summary generation failed. Please view the original PDF."
        }
        if language == 'both':
            return error_msg
        else:
            return error_msg.get(language, error_msg['en'])


def generate_date_notice(date_stats, papers, language='zh'):
    total = len(papers)
    today_count = date_stats['today']
    yesterday_count = date_stats['yesterday']
    older_count = date_stats['older']
    
    if older_count == 0 and today_count > 0:
        return ""
    
    txt = TEXT_TEMPLATES.get(language, TEXT_TEMPLATES['en'])
    notice_parts = []
    
    if today_count > 0:
        notice_parts.append(txt['published_today'].format(count=today_count))
    if yesterday_count > 0:
        notice_parts.append(txt['published_yesterday'].format(count=yesterday_count))
    if older_count > 0:
        notice_parts.append(txt['published_older_multi'].format(count=older_count))
    
    notice_text = ", ".join(notice_parts) if language == 'en' else "、".join(notice_parts)
    notice_message = txt['notice_text'].format(total=total, parts=notice_text)
    
    icon, bg_color, border_color, text_color = "✨", "#d4edda", "#28a745", "#155724"
    
    html = f"""
    <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 15px 20px; margin-bottom: 25px; border-radius: 5px;">
        <div style="color: {text_color}; font-size: 15px; line-height: 1.6;">
            <span style="font-size: 20px; margin-right: 8px;">{icon}</span>
            <strong>{txt['date_notice']}:</strong> {notice_message}
        </div>
    </div>
    """
    return html


def generate_email_content(papers_with_summaries, language='zh'):
    today = datetime.now().strftime('%Y-%m-%d')
    papers = [item['paper'] for item in papers_with_summaries]
    date_stats = analyze_paper_dates(papers)
    txt = TEXT_TEMPLATES.get('zh' if language == 'zh' else 'en', TEXT_TEMPLATES['en'])
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .date {{ font-size: 14px; opacity: 0.9; margin-top: 10px; }}
            .paper {{ background: white; padding: 25px; margin-bottom: 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: relative; }}
            .paper-title {{ color: #1e3c72; font-size: 20px; font-weight: bold; margin-bottom: 10px; line-height: 1.4; }}
            .quality-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; margin-left: 8px; background: #ffd700; color: #856404; }}
            .meta {{ color: #666; font-size: 14px; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 2px solid #f0f0f0; }}
            .meta-item {{ margin: 5px 0; }}
            .date-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; margin-left: 8px; }}
            .date-today {{ background: #d4edda; color: #155724; }}
            .date-yesterday {{ background: #d1ecf1; color: #0c5460; }}
            .date-older {{ background: #f8d7da; color: #721c24; }}
            .categories {{ display: inline-block; }}
            .category-tag {{ background: #e8eaf6; color: #1e3c72; padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-right: 5px; display: inline-block; }}
            .summary {{ background: #f8f9ff; padding: 15px; border-left: 4px solid #1e3c72; margin: 15px 0; border-radius: 4px; }}
            .summary-title {{ font-weight: bold; color: #1e3c72; margin-bottom: 10px; }}
            .links {{ margin-top: 15px; }}
            .link-button {{ display: inline-block; background: #1e3c72; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px; font-size: 14px; }}
            .link-button:hover {{ background: #2a5298; }}
            .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ {txt['title']}</h1>
            <div class="date">{today}</div>
        </div>
        {generate_date_notice(date_stats, papers, 'zh' if language == 'zh' else 'en')}
    """
    
    now = datetime.now()
    today_date = now.date()
    yesterday_date = (now - timedelta(days=1)).date()
    
    for i, item in enumerate(papers_with_summaries, 1):
        paper = item['paper']
        summary = item['summary']
        
        paper_date = paper['published'].date()
        if paper_date == today_date:
            date_badge = f'<span class="date-badge date-today">{txt["new_today"]}</span>'
        elif paper_date == yesterday_date:
            date_badge = f'<span class="date-badge date-yesterday">{txt["yesterday_label"]}</span>'
        else:
            days_ago = (today_date - paper_date).days
            date_badge = f'<span class="date-badge date-older">{txt["days_ago_label"].format(days=days_ago)}</span>'
        
        quality_badge = ''
        if paper.get('quality_score', 0) >= 3.0:  # 调整了展示高分徽章的阈值
            quality_badge = f'<span class="quality-badge">{txt["high_quality"]}</span>'
        
        categories_html = ''.join([
            f'<span class="category-tag">{cat}</span>' 
            for cat in paper['categories'][:3]
        ])
        
        if language == 'both' and isinstance(summary, dict):
            summary_html = f"""
                <div style="margin-bottom: 15px;">
                    <div style="font-weight: bold; color: #1e3c72; margin-bottom: 8px;">🇨🇳 中文摘要</div>
                    <div>{summary.get('zh', '').replace(chr(10), '<br>')}</div>
                </div>
                <div>
                    <div style="font-weight: bold; color: #1e3c72; margin-bottom: 8px;">🇬🇧 English Summary</div>
                    <div>{summary.get('en', '').replace(chr(10), '<br>')}</div>
                </div>
            """
        else:
            summary_text = summary if isinstance(summary, str) else summary.get(language, '')
            summary_html = summary_text.replace(chr(10), '<br>')
        
        html += f"""
        <div class="paper">
            <div class="paper-title">{i}. {paper['title']}{date_badge}{quality_badge}</div>
            <div class="meta">
                <div class="meta-item">
                    <strong>👥 {txt['authors']}:</strong> {paper['authors'][:200]}{'...' if len(paper['authors']) > 200 else ''}
                </div>
                <div class="meta-item">
                    <strong>📅 {txt['published']}:</strong> {paper['published'].strftime('%Y-%m-%d %H:%M')}
                </div>
                <div class="meta-item">
                    <strong>🏷️ {txt['categories']}:</strong>
                    <div class="categories">{categories_html}</div>
                </div>
                <div class="meta-item">
                    <strong>📊 {txt['quality_score']}:</strong> {paper.get('quality_score', 0):.1f}
                </div>
            </div>
            
            <div class="summary">
                <div class="summary-title">🤖 {txt['ai_summary']}</div>
                <div>{summary_html}</div>
            </div>
            
            <div class="links">
                <a href="{paper['pdf_url']}" class="link-button">📄 {txt['view_pdf']}</a>
            </div>
        </div>
        """
    
    html += f"""
        <div class="footer">
            <p>{txt['footer_auto']}</p>
            <p>{txt['footer_powered']}</p>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email(subject, html_content):
    """
    【修复版】兼容 163 邮箱的 465 端口直接 SSL 加密连接
    """
    print(f"\n📧 Sending email to {RECEIVER_EMAIL}...")
    
    try:
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = SENDER_EMAIL
        message['To'] = RECEIVER_EMAIL
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        message.attach(html_part)
        
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(message)
        
        print(f"✅ Email sent successfully!")
        return True
    
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        return False


def main():
    print("=" * 60)
    print("🚀 arXiv Daily Paper Digest - Starting")
    print("=" * 60)
    
    required_vars = ['DEEPSEEK_API_KEY', 'SENDER_EMAIL', 'SENDER_PASSWORD', 'RECEIVER_EMAIL']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these environment variables in GitHub Secrets")
        return
    
    try:
        papers = get_latest_papers()
        
        if not papers:
            print("\n⚠️ 过去 48 小时内没有找到相关论文。")
            return
        
        date_stats = analyze_paper_dates(papers)
        print(f"\n📊 论文时效统计:")
        print(f"   今天发布: {date_stats['today']} 篇")
        print(f"   昨天发布: {date_stats['yesterday']} 篇")
        print(f"   更早发布: {date_stats['older']} 篇")
        
        print("\n" + "=" * 60)
        print("🤖 Generating AI Summaries")
        print("=" * 60)
        
        papers_with_summaries = []
        for i, paper in enumerate(papers, 1):
            print(f"\n[{i}/{len(papers)}]")
            summary = summarize_paper(paper, EMAIL_LANGUAGE)
            papers_with_summaries.append({
                'paper': paper,
                'summary': summary
            })
        
        print("\n" + "=" * 60)
        print("📧 Generating Email Content")
        print("=" * 60)
        html_content = generate_email_content(papers_with_summaries, EMAIL_LANGUAGE)
        
        today = datetime.now().strftime('%Y-%m-%d')
        subject = f"⚡ 电力与优化 arXiv 最新推送 - {today}"
        send_email(subject, html_content)
        
        print("\n" + "=" * 60)
        print("✅ Execution completed successfully!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ Execution error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
