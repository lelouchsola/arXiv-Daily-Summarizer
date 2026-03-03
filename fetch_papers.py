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
MAX_RESULTS = 10  # 每天最多推送的论文数量
MIN_PAPERS_PER_CATEGORY = 1  

# 历史记录文件路径（用于跨天去重）
HISTORY_FILE = 'sent_papers_history.txt'

# Language configuration
EMAIL_LANGUAGE = os.environ.get('EMAIL_LANGUAGE', 'zh')  

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
DEEPSEEK_MODEL = 'deepseek-chat' 

# Email configuration (163 邮箱配置)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')  # 163 邮箱授权码
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL')    # 支持逗号分隔的多个邮箱，例如 "A@163.com, B@qq.com"
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.163.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))

# Quality filtering thresholds
MIN_ABSTRACT_LENGTH = 100  
SIMILARITY_THRESHOLD = 0.85  

# Language text templates
TEXT_TEMPLATES = {
    'zh': {
        'title': 'arXiv 每日论文精选推送 - 大湾区大学 IDEA (Intelligent Decision & Energy Analytics) Lab',
        'date_notice': '论文时效说明',
        'today': '今天',
        'yesterday': '昨天',
        'days_ago': '天前',
        'published_today': '<strong>{count} 篇</strong>是今天发布',
        'published_yesterday': '<strong>{count} 篇</strong>是昨天发布',
        'published_older_multi': '<strong>{count} 篇</strong>是 2 天及更早前发布',
        'notice_text': '本次推送的 {total} 篇全新论文中，{parts}。',
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
        'title': 'arXiv Daily Paper Digest - Smart Energy Group, Great Bay University',
        'date_notice': 'Date Notice',
        'today': 'today',
        'yesterday': 'yesterday',
        'days_ago': 'days ago',
        'published_today': '<strong>{count} papers</strong> published today',
        'published_yesterday': '<strong>{count} papers</strong> published yesterday',
        'published_older_multi': '<strong>{count} papers</strong> published 2+ days ago',
        'notice_text': 'Of the {total} new papers in this digest, {parts}.',
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

# ========== Helper Functions for History Memory ==========

def load_sent_history():
    """加载已经推送过的论文 ID，实现跨天去重"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_history(paper_ids):
    """把今天新推送的论文 ID 追加保存到历史记录中"""
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for pid in paper_ids:
            f.write(f"{pid}\n")

# ========== Core Logic ==========

def calculate_paper_quality_score(paper):
    """定制的质量与契合度打分系统"""
    score = 0.0
    
    abstract_length = len(paper.get('abstract', ''))
    if abstract_length > 500:
        score += 2.0
    elif abstract_length > 300:
        score += 1.0
    elif abstract_length < MIN_ABSTRACT_LENGTH:
        score -= 2.0
    
    num_authors = len(paper.get('authors', '').split(','))
    if 3 <= num_authors <= 8:
        score += 1.0
    elif num_authors > 8:
        score += 0.5
    
    title = paper.get('title', '').lower()
    abstract = paper.get('abstract', '').lower()
    
    important_keywords = [
        'learn to optimize', 'decision-focused', 'predict-and-optimize', 
        'end-to-end', 'reinforcement learning', 'machine learning', 'data-driven',
        'power system', 'energy system', 'smart grid', 'microgrid', 
        'hydrogen', 'power-to-gas', 'p2g', 'electrolyzer', 'fuel cell',
        'unit commitment', 'economic dispatch', 'optimal power flow', 'opf',
        'flexibility', 'flexible resource', 'demand response', 'energy storage',
        'renewable', 'stochastic optimization', 'robust optimization', 'resilience', 'typhoon', 'der',
        'novel', 'efficient', 'framework', 'state-of-the-art'
    ]
    
    for keyword in important_keywords:
        if keyword in title:
            score += 1.5
        elif keyword in abstract:
            score += 0.5
    
    title_words = len(title.split())
    if title_words < 5:
        score -= 0.5
    elif title_words > 25:
        score -= 0.3
        
    return score

def calculate_title_similarity(title1, title2):
    def normalize(text):
        return re.sub(r'[^\w\s]', '', text.lower())
    return SequenceMatcher(None, normalize(title1), normalize(title2)).ratio()

def remove_duplicate_papers(papers):
    if not papers: return papers
    filtered_papers = []
    
    for paper in papers:
        is_duplicate = False
        for existing_paper in filtered_papers:
            similarity = calculate_title_similarity(paper['title'], existing_paper['title'])
            if similarity >= SIMILARITY_THRESHOLD:
                if paper.get('quality_score', 0) > existing_paper.get('quality_score', 0):
                    filtered_papers.remove(existing_paper)
                    filtered_papers.append(paper)
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_papers.append(paper)
            
    return filtered_papers

def get_latest_papers():
    print(f"🔍 Searching for latest papers on arXiv...")
    
    # 1. 加载历史记录，避免重复推送
    sent_history = load_sent_history()
    print(f"📚 已加载 {len(sent_history)} 篇历史推送记录")
    
    client = arxiv.Client()
    papers_by_category = defaultdict(list)
    seen_ids = set()
    
    for category in CATEGORIES:
        print(f"\n🔎 Searching category: {category}")
        try:
            # 扩大初筛池容量
            search = arxiv.Search(
                query=f'cat:{category}',
                max_results=MAX_RESULTS * 10,  
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            results = list(client.results(search))
            print(f"  API 返回 {len(results)} 篇论文")
            
            valid_count = 0
            for result in results:
                # 核心拦截 1：如果已经在历史记录中，直接跳过
                if result.entry_id in sent_history:
                    continue
                    
                if result.entry_id not in seen_ids:
                    # 核心拦截 2：智能时间窗口 (解决周末断更问题)
                    now = datetime.now(result.published.tzinfo)
                    current_weekday = now.weekday()
                    
                    lookback_days = 5 if current_weekday in [0, 1] else 3
                    time_diff = now - result.published
                    
                    if time_diff.days > lookback_days:
                        continue  
                    
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
            
            papers_by_category[category].sort(key=lambda x: x['quality_score'], reverse=True)
            print(f"  在 {category} 中筛选出 {valid_count} 篇全新有效论文")
            
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
        
        all_remaining.sort(key=lambda x: x['quality_score'], reverse=True)
        selected_papers.extend(all_remaining[:remaining_slots])
    
    selected_papers = remove_duplicate_papers(selected_papers)
    selected_papers.sort(key=lambda x: x['published'], reverse=True)
    
    print(f"\n✅ 收集完毕，共提取: {len(selected_papers)} 篇全新论文")
    return selected_papers

def analyze_paper_dates(papers):
    now = datetime.now()
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()
    
    date_stats = {'today': 0, 'yesterday': 0, 'older': 0, 'date_distribution': Counter()}
    for paper in papers:
        paper_date = paper['published'].date()
        date_stats['date_distribution'][paper_date] += 1
        if paper_date == today: date_stats['today'] += 1
        elif paper_date == yesterday: date_stats['yesterday'] += 1
        else: date_stats['older'] += 1
    return date_stats

def summarize_paper(paper, language='zh'):
    print(f"\n🤖 正在调用 DeepSeek 提取摘要:")
    print(f"   {paper['title'][:70]}...")
    
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
请用简洁严谨的学术语言总结，适合快速阅读理解。"""
    }
    
    try:
        client = OpenAI(base_url=DEEPSEEK_BASE_URL, api_key=DEEPSEEK_API_KEY)
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{'role': 'user', 'content': prompts.get(language, prompts['zh'])}],
            stream=True
        )
        
        summary = ""
        for chunk in response:
            if getattr(chunk, 'choices', None) and len(chunk.choices) > 0:
                answer_chunk = getattr(chunk.choices[0].delta, 'content', '') or ''
                summary += answer_chunk
                
        print(f"   ✅ 摘要生成完毕")
        return summary.strip()
    except Exception as e:
        print(f"   ❌ AI 摘要生成失败: {str(e)}")
        return "摘要生成失败，请直接点击下方链接查看原文 PDF。"

def generate_date_notice(date_stats, papers, language='zh'):
    total = len(papers)
    if date_stats['older'] == 0 and date_stats['today'] > 0: return ""
    
    txt = TEXT_TEMPLATES.get(language, TEXT_TEMPLATES['zh'])
    parts = []
    if date_stats['today'] > 0: parts.append(txt['published_today'].format(count=date_stats['today']))
    if date_stats['yesterday'] > 0: parts.append(txt['published_yesterday'].format(count=date_stats['yesterday']))
    if date_stats['older'] > 0: parts.append(txt['published_older_multi'].format(count=date_stats['older']))
    
    notice_message = txt['notice_text'].format(total=total, parts="、".join(parts))
    return f"""
    <div style="background: #d4edda; border-left: 4px solid #28a745; padding: 15px 20px; margin-bottom: 25px; border-radius: 5px;">
        <div style="color: #155724; font-size: 15px; line-height: 1.6;">
            <span style="font-size: 20px; margin-right: 8px;">✨</span>
            <strong>{txt['date_notice']}:</strong> {notice_message}
        </div>
    </div>
    """

def generate_email_content(papers_with_summaries, language='zh'):
    today = datetime.now().strftime('%Y-%m-%d')
    papers = [item['paper'] for item in papers_with_summaries]
    date_stats = analyze_paper_dates(papers)
    txt = TEXT_TEMPLATES.get(language, TEXT_TEMPLATES['zh'])
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
            .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .date {{ font-size: 14px; opacity: 0.9; margin-top: 10px; }}
            .paper {{ background: white; padding: 25px; margin-bottom: 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .paper-title {{ color: #1e3c72; font-size: 18px; font-weight: bold; margin-bottom: 10px; line-height: 1.4; }}
            .quality-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; margin-left: 8px; background: #ffd700; color: #856404; }}
            .meta {{ color: #666; font-size: 14px; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 2px solid #f0f0f0; }}
            .date-badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; margin-left: 8px; }}
            .date-today {{ background: #d4edda; color: #155724; }}
            .date-yesterday {{ background: #d1ecf1; color: #0c5460; }}
            .date-older {{ background: #f8d7da; color: #721c24; }}
            .category-tag {{ background: #e8eaf6; color: #1e3c72; padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-right: 5px; display: inline-block; }}
            .summary {{ background: #f8f9ff; padding: 15px; border-left: 4px solid #1e3c72; margin: 15px 0; border-radius: 4px; }}
            .summary-title {{ font-weight: bold; color: #1e3c72; margin-bottom: 10px; }}
            .link-button {{ display: inline-block; background: #1e3c72; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; font-size: 14px; }}
            .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ {txt['title']}</h1>
            <div class="date">{today}</div>
        </div>
        {generate_date_notice(date_stats, papers, language)}
    """
    
    today_date = datetime.now().date()
    yesterday_date = today_date - timedelta(days=1)
    
    for i, item in enumerate(papers_with_summaries, 1):
        paper = item['paper']
        paper_date = paper['published'].date()
        
        if paper_date == today_date: date_badge = f'<span class="date-badge date-today">{txt["new_today"]}</span>'
        elif paper_date == yesterday_date: date_badge = f'<span class="date-badge date-yesterday">{txt["yesterday_label"]}</span>'
        else: date_badge = f'<span class="date-badge date-older">{txt["days_ago_label"].format(days=(today_date - paper_date).days)}</span>'
        
        quality_badge = f'<span class="quality-badge">{txt["high_quality"]}</span>' if paper.get('quality_score', 0) >= 3.0 else ''
        categories_html = ''.join([f'<span class="category-tag">{cat}</span>' for cat in paper['categories'][:3]])


        html += f"""
        <div class="paper">
            <div class="paper-title">{i}. {paper['title']}{date_badge}{quality_badge}</div>
            <div class="meta">
                <div style="margin: 5px 0;"><strong>👥 {txt['authors']}:</strong> {paper['authors'][:200]}</div>
                <div style="margin: 5px 0;"><strong>📅 {txt['published']}:</strong> {paper['published'].strftime('%Y-%m-%d %H:%M')}</div>
                <div style="margin: 5px 0;"><strong>🏷️ {txt['categories']}:</strong> {categories_html}</div>
                <div style="margin: 5px 0;"><strong>📊 {txt['quality_score']}:</strong> {paper.get('quality_score', 0):.1f}</div>
            </div>
            <div class="summary">
                <div class="summary-title">🤖 {txt['ai_summary']}</div>
                <div>{item['summary'].replace(chr(10), '<br>')}</div>
            </div>
            <div style="margin-top: 15px;">
                <a href="{paper['pdf_url']}" class="link-button">📄 {txt['view_pdf']}</a>
            </div>
        </div>
        """
    
    html += f'<div class="footer"><p>{txt["footer_auto"]}</p><p>{txt["footer_powered"]}</p></div></body></html>'
    return html

def send_email(subject, html_content):
    """支持多收件人密送 (BCC)，保护隐私"""
    print(f"\n📧 Sending email to recipients...")
    try:
        receivers = [email.strip() for email in RECEIVER_EMAIL.split(',') if email.strip()]
        
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = SENDER_EMAIL
        # 表面收件人设为自己，实现密送效果
        message['To'] = SENDER_EMAIL 
        
        message.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                # 实际发送给所有人
                server.sendmail(SENDER_EMAIL, receivers, message.as_string())
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, receivers, message.as_string())
                
        print(f"✅ Email sent successfully to {len(receivers)} recipients (via BCC)!")
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
        return
    
    try:
        papers = get_latest_papers()
        if not papers:
            print("\n⚠️ 当前时间窗口内没有发现未推送过的新论文。")
            return
            
        print("\n" + "=" * 60)
        print("🤖 Generating AI Summaries")
        print("=" * 60)
        
        papers_with_summaries = []
        for i, paper in enumerate(papers, 1):
            print(f"\n[{i}/{len(papers)}]")
            summary = summarize_paper(paper, EMAIL_LANGUAGE)
            papers_with_summaries.append({'paper': paper, 'summary': summary})
        
        print("\n" + "=" * 60)
        print("📧 Generating Email Content")
        print("=" * 60)
        
        html_content = generate_email_content(papers_with_summaries, EMAIL_LANGUAGE)
        today = datetime.now().strftime('%Y-%m-%d')
        subject = f"⚡ 电力与优化 arXiv 最新推送 - {today}"
        
        # 发送邮件并记录历史
        if send_email(subject, html_content):
            new_sent_ids = [p['paper']['entry_id'] for p in papers_with_summaries]
            save_sent_history(new_sent_ids)
            print(f"💾 已将 {len(new_sent_ids)} 篇论文 ID 存入历史记录，防止未来重复推送。")
        
        print("\n✅ Execution completed successfully!")
    
    except Exception as e:
        print(f"\n❌ Execution error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
