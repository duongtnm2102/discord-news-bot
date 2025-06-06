import discord
from discord.ext import commands
import feedparser
import requests
import asyncio
import os
import re
from datetime import datetime, timedelta
import time
import calendar
from urllib.parse import urljoin, urlparse, quote
import html
import chardet
import pytz
import json
import aiohttp
from keep_alive import keep_alive
from enum import Enum
from typing import List, Dict, Tuple, Optional
import random
import hashlib

# 🚀 OPTIMIZED LIBRARIES - Enhanced for Yahoo Finance
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    WIKIPEDIA_AVAILABLE = False

# 🆕 GEMINI ONLY - Enhanced AI System with Direct Content Access
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔒 ENVIRONMENT VARIABLES
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# 🔧 TIMEZONE - Vietnam
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# 🔧 DISCORD LIMITS
DISCORD_EMBED_FIELD_VALUE_LIMIT = 1000
DISCORD_EMBED_DESCRIPTION_LIMIT = 4000
DISCORD_EMBED_TITLE_LIMIT = 250
DISCORD_EMBED_TOTAL_EMBED_LIMIT = 5800

# User cache with deduplication
user_news_cache = {}
user_last_detail_cache = {}
global_seen_articles = {}  # Global deduplication cache
scraped_news_cache = {}    # Cache for scraped news from Yahoo Finance
MAX_CACHE_ENTRIES = 25
MAX_GLOBAL_CACHE = 1000

# 🔧 Enhanced User Agents for Yahoo Finance
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_current_vietnam_datetime():
    """Get current Vietnam date and time"""
    return datetime.now(VN_TIMEZONE)

def get_current_date_str():
    """Get current date string in Vietnam format"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%d/%m/%Y")

def get_current_time_str():
    """Get current time string in Vietnam format"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%H:%M")

def get_current_datetime_str():
    """Get current datetime string for display"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%H:%M %d/%m/%Y")

print("🚀 NEWS BOT:")
print(f"DISCORD_TOKEN: {'✅' if TOKEN else '❌'}")
print(f"GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌'}")
print("=" * 30)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🔧 MASSIVE RSS FEEDS - 20+ WORKING SOURCES from GitHub Gist 2025
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - CHỈ CAFEF ===
    'domestic': {
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafef_doanhnghiep': 'https://cafef.vn/doanh-nghiep.rss'
    },
    
    # === QUỐC TẾ - MASSIVE RSS COLLECTION from GitHub Gist 2025 ===
    'international': {
        # ✅ YAHOO FINANCE RSS (Original working feeds)
        'yahoo_finance_main': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_headlines': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        'yahoo_finance_rss': 'https://www.yahoo.com/news/rss/finance',
        
        # ✅ MAJOR FINANCIAL NEWS RSS FEEDS (Verified from GitHub)
        'cnn_money': 'http://rss.cnn.com/rss/money_topstories.rss',
        'reuters_topnews': 'http://feeds.reuters.com/reuters/topNews',
        'marketwatch': 'http://feeds.marketwatch.com/marketwatch/topstories/',
        'business_insider': 'http://feeds2.feedburner.com/businessinsider',
        'forbes': 'https://www.forbes.com/real-time/feed2/',
        'wsj': 'http://www.wsj.com/xml/rss/3_7031.xml',
        'cnbc': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
        'investing_com': 'https://www.investing.com/rss/news.rss',
        'seekingalpha': 'https://seekingalpha.com/market_currents.xml',
        'financial_times': 'https://www.ft.com/?format=rss',
        'fortune': 'http://fortune.com/feed/',
        'economist': 'http://www.economist.com/sections/economics/rss.xml',
        'nasdaq': 'http://articlefeeds.nasdaq.com/nasdaq/categories?category=Investing+Ideas',
        'washington_post_biz': 'http://feeds.washingtonpost.com/rss/business',
        'guardian_business': 'https://www.theguardian.com/business/economics/rss',
        'investopedia': 'https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline',
        'nikkei_asia': 'https://asia.nikkei.com/rss/feed/nar',
        'economic_times': 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
        'bbc_news': 'http://feeds.bbci.co.uk/news/rss.xml',
        'coindesk': 'https://feeds.feedburner.com/CoinDesk',
        
        # ✅ BACKUP WORKING URLs (if primary fail)
        'yahoo_finance_crypto': 'https://finance.yahoo.com/topic/crypto/',
        'yahoo_finance_tech': 'https://finance.yahoo.com/topic/tech/',
        'yahoo_finance_stock_market': 'https://finance.yahoo.com/topic/stock-market-news/',
    }
}

def convert_utc_to_vietnam_time(utc_time_tuple):
    """Convert UTC to Vietnam time"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        return datetime.now(VN_TIMEZONE)

# 🆕 ENHANCED DEDUPLICATION SYSTEM
def generate_article_hash(title, link, description=""):
    """Generate unique hash for article deduplication"""
    # Clean and normalize text
    clean_title = re.sub(r'[^\w\s]', '', title.lower().strip())
    clean_link = link.lower().strip()
    
    # Create content-based hash
    content = f"{clean_title}|{clean_link}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def is_duplicate_article(news_item, source_name):
    """Check if article is duplicate using multiple methods"""
    global global_seen_articles
    
    # Method 1: Hash-based deduplication
    article_hash = generate_article_hash(news_item['title'], news_item['link'], news_item.get('description', ''))
    
    if article_hash in global_seen_articles:
        return True
    
    # Method 2: Title similarity check (for same-content different URLs)
    title_words = set(news_item['title'].lower().split())
    
    for existing_hash, existing_data in global_seen_articles.items():
        existing_title_words = set(existing_data['title'].lower().split())
        
        # Check if 80% of words are similar
        if len(title_words) > 3 and len(existing_title_words) > 3:
            similarity = len(title_words.intersection(existing_title_words)) / len(title_words.union(existing_title_words))
            if similarity > 0.8:
                return True
    
    # Method 3: URL domain check (same article, different parameters)
    for existing_hash, existing_data in global_seen_articles.items():
        if clean_url_for_comparison(news_item['link']) == clean_url_for_comparison(existing_data['link']):
            return True
    
    # Not duplicate - add to cache
    global_seen_articles[article_hash] = {
        'title': news_item['title'],
        'link': news_item['link'],
        'source': source_name,
        'timestamp': get_current_vietnam_datetime()
    }
    
    # Limit cache size
    if len(global_seen_articles) > MAX_GLOBAL_CACHE:
        # Remove oldest 100 entries
        sorted_items = sorted(global_seen_articles.items(), key=lambda x: x[1]['timestamp'])
        for old_hash, _ in sorted_items[:100]:
            del global_seen_articles[old_hash]
    
    return False

def clean_url_for_comparison(url):
    """Clean URL for comparison (remove parameters, fragments)"""
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".lower()
    except:
        return url.lower()

# 🔧 CONTENT VALIDATION FOR DISCORD
def validate_and_truncate_content(content: str, limit: int, suffix: str = "...") -> str:
    """Strict validation and truncation for Discord limits"""
    if not content:
        return "Không có nội dung."
    
    content = str(content).strip()
    safe_limit = max(limit - 50, 100)
    
    if len(content) <= safe_limit:
        return content
    
    available_space = safe_limit - len(suffix)
    if available_space <= 0:
        return suffix[:safe_limit]
    
    truncated = content[:available_space].rstrip()
    last_sentence = truncated.rfind('. ')
    if last_sentence > available_space * 0.7:
        truncated = truncated[:last_sentence + 1]
    
    return truncated + suffix

def validate_embed_field(name: str, value: str) -> Tuple[str, str]:
    """Strict embed field validation for Discord limits"""
    safe_name = validate_and_truncate_content(name, DISCORD_EMBED_TITLE_LIMIT, "...")
    safe_value = validate_and_truncate_content(value, DISCORD_EMBED_FIELD_VALUE_LIMIT, "...")
    
    if not safe_value or safe_value == "...":
        safe_value = "Nội dung không khả dụng."
    
    return safe_name, safe_value

def create_safe_embed(title: str, description: str = "", color: int = 0x00ff88) -> discord.Embed:
    """Create safe embed that fits Discord limits"""
    safe_title = validate_and_truncate_content(title, DISCORD_EMBED_TITLE_LIMIT, "...")
    safe_description = validate_and_truncate_content(description, DISCORD_EMBED_DESCRIPTION_LIMIT, "...")
    
    return discord.Embed(
        title=safe_title,
        description=safe_description,
        color=color,
        timestamp=get_current_vietnam_datetime()
    )

# 🔧 Enhanced headers with retry mechanism - OPTIMIZED for 2025
def get_enhanced_headers(url=None):
    """Enhanced headers for Yahoo Finance with anti-blocking - OPTIMIZED"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document'
    }
    
    if url and 'yahoo' in url.lower():
        headers.update({
            'Referer': 'https://finance.yahoo.com/',
            'Origin': 'https://finance.yahoo.com',
            'Host': 'finance.yahoo.com' if 'finance.yahoo.com' in url else 'feeds.finance.yahoo.com'
        })
    elif url and 'cafef.vn' in url.lower():
        headers.update({
            'Referer': 'https://cafef.vn/',
            'Origin': 'https://cafef.vn'
        })
    
    return headers

def add_random_delay():
    """Add random delay to avoid rate limiting - SHORTER for optimization"""
    delay = random.uniform(0.3, 1.5)  # Reduced from 0.5-2.0
    time.sleep(delay)

def is_international_source(source_name):
    """Check if source is international - FIXED for all RSS sources"""
    international_sources = [
        'yahoo_finance', 'cnn_money', 'reuters', 'marketwatch', 'business_insider',
        'forbes', 'wsj', 'cnbc', 'investing_com', 'seekingalpha', 'financial_times',
        'fortune', 'economist', 'nasdaq', 'washington_post', 'guardian_business',
        'investopedia', 'nikkei_asia', 'economic_times', 'bbc_news', 'coindesk'
    ]
    return any(source in source_name for source in international_sources)

def create_fallback_content(url, source_name, error_msg=""):
    """Create fallback content when extraction fails - FIXED for all sources"""
    try:
        article_id = url.split('/')[-1] if '/' in url else 'news-article'
        
        if is_international_source(source_name):
            # Get actual source display name
            source_display = "Financial News"
            if 'marketwatch' in source_name:
                source_display = "MarketWatch"
            elif 'reuters' in source_name:
                source_display = "Reuters"
            elif 'cnn' in source_name:
                source_display = "CNN Money"
            elif 'forbes' in source_name:
                source_display = "Forbes"
            elif 'wsj' in source_name:
                source_display = "Wall Street Journal"
            elif 'cnbc' in source_name:
                source_display = "CNBC"
            elif 'bbc' in source_name:
                source_display = "BBC News"
            
            return f"""**{source_display} Financial News:**

📈 **Market Analysis:** This article provides financial market insights and economic analysis.

📊 **Coverage Areas:**
• Real-time market data and analysis
• Economic indicators and trends
• Corporate earnings and reports
• Investment strategies and forecasts

**Article ID:** {article_id}
**Note:** Content extraction failed. Please visit the original link for complete article.

{f'**Technical Error:** {error_msg}' if error_msg else ''}"""
        else:
            return f"""**Tin tức kinh tế CafeF:**

📰 **Thông tin kinh tế:** Bài viết cung cấp thông tin kinh tế, tài chính từ CafeF.

📊 **Nội dung chuyên sâu:**
• Phân tích thị trường chứng khoán Việt Nam
• Tin tức kinh tế vĩ mô và chính sách
• Báo cáo doanh nghiệp và tài chính
• Bất động sản và đầu tư

**Mã bài viết:** {article_id}
**Lưu ý:** Để đọc đầy đủ, vui lòng truy cập link gốc.

{f'**Lỗi:** {error_msg}' if error_msg else ''}"""
        
    except Exception as e:
        return f"Nội dung từ {source_name}. Vui lòng truy cập link gốc để đọc đầy đủ."

async def extract_content_with_gemini(url, source_name):
    """Use Gemini to extract and translate content from international news"""
    try:
        if not GEMINI_API_KEY or not GEMINI_AVAILABLE:
            return create_fallback_content(url, source_name, "Gemini không khả dụng")
        
        extraction_prompt = f"""You are a financial news content extractor and translator. Access and process this news article:

**ARTICLE URL:** {url}

**INSTRUCTIONS:**
1. Access and read the COMPLETE article content from the URL
2. Extract main content (remove ads, sidebar, footer)
3. Translate from English to Vietnamese naturally and accurately
4. Preserve all numbers, percentages, company names, financial terms
5. Use standard Vietnamese economic-financial terminology
6. Do NOT add personal commentary or explanations
7. Return translated content with clear structure
8. FOCUS ONLY on the source article content - do not reference other news sources

**IMPORTANT:** Only return the translated article content from the provided URL. Do not mention CafeF, Yahoo Finance, or other sources unless they appear in the original article.

**TRANSLATED CONTENT:**"""

        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=2500,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    extraction_prompt,
                    generation_config=generation_config
                ),
                timeout=25
            )
            
            extracted_content = response.text.strip()
            
            if len(extracted_content) > 200:
                error_indicators = [
                    'cannot access', 'unable to access', 'không thể truy cập',
                    'failed to retrieve', 'error occurred', 'sorry, i cannot'
                ]
                
                if not any(indicator in extracted_content.lower() for indicator in error_indicators):
                    return f"[🤖 Gemini AI trích xuất từ {source_name}]\n\n{extracted_content}"
                else:
                    return create_fallback_content(url, source_name, "Gemini không thể trích xuất nội dung")
            else:
                return create_fallback_content(url, source_name, "Gemini trả về nội dung quá ngắn")
            
        except asyncio.TimeoutError:
            return create_fallback_content(url, source_name, "Gemini timeout")
        except Exception as e:
            return create_fallback_content(url, source_name, f"Lỗi Gemini: {str(e)}")
            
    except Exception as e:
        return create_fallback_content(url, source_name, str(e))

# 🆕 OPTIMIZED YAHOO FINANCE NEWS SCRAPING - Fixed for 2025
def scrape_yahoo_finance_news(base_url, limit=20):  # Reduced limit from 30
    """OPTIMIZED scrape news directly from Yahoo Finance - Fixed URLs 2025"""
    try:
        print(f"🔄 Optimized scraping: {base_url}")
        add_random_delay()
        
        session = requests.Session()
        headers = get_enhanced_headers(base_url)
        session.headers.update(headers)
        
        # SHORTER timeout to prevent heartbeat blocking
        response = session.get(base_url, timeout=10, allow_redirects=True)  # Reduced from 15
        
        if response.status_code != 200:
            print(f"❌ Failed to scrape {base_url}: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # OPTIMIZED selectors for Yahoo Finance 2025
        news_articles = []
        
        # Enhanced selectors for different Yahoo Finance page types
        article_selectors = [
            # News page selectors
            'h3 > a[href*="/news/"]',
            'a[href*="/news/"][data-module]',
            'h3 a[href*="/news/"]',
            'h2 a[href*="/news/"]',
            
            # Sector page selectors
            'div[data-testid] a[href*="/quote/"]',
            '.js-content-viewer a',
            'article a[href*="/news/"]',
            
            # Video page selectors
            'a[href*="/video/"]',
            
            # General news selectors
            'h3 a',
            'h2 a',
            '.newsItem a',
            '.story a'
        ]
        
        for selector in article_selectors:
            try:
                elements = soup.select(selector)[:limit]  # Limit early
                for element in elements:
                    try:
                        # Extract title and link
                        if element.name == 'a':
                            title = element.get_text(strip=True)
                            link = element.get('href', '')
                        else:
                            # If it's h3 or other element, find the link inside
                            link_elem = element.find('a') if element.name != 'a' else element
                            if not link_elem:
                                continue
                            title = link_elem.get_text(strip=True)
                            link = link_elem.get('href', '')
                        
                        # Clean and validate
                        if not title or not link or len(title) < 10:
                            continue
                        
                        # Fix relative URLs
                        if link.startswith('/'):
                            link = f"https://finance.yahoo.com{link}"
                        elif not link.startswith('http'):
                            continue
                        
                        # Filter for financial/economic content - RELAXED filter
                        if is_relevant_financial_news_relaxed(title):
                            news_item = {
                                'title': html.unescape(title.strip()),
                                'link': link,
                                'source': f"yahoo_finance_scraped",
                                'published': get_current_vietnam_datetime(),
                                'published_str': get_current_vietnam_datetime().strftime("%H:%M %d/%m"),
                                'description': title[:200] + "..." if len(title) > 200 else title
                            }
                            
                            # Check for duplicates
                            if not is_duplicate_article(news_item, news_item['source']):
                                news_articles.append(news_item)
                        
                    except Exception as e:
                        continue
                
                if len(news_articles) >= limit:
                    break
                    
            except Exception as e:
                continue
        
        session.close()
        print(f"✅ Scraped {len(news_articles)} unique articles from {base_url}")
        return news_articles[:limit]
        
    except Exception as e:
        print(f"❌ Scraping error for {base_url}: {e}")
        return []

def is_relevant_financial_news_relaxed(title):
    """RELAXED filter for relevant financial/economic news - More inclusive"""
    financial_keywords = [
        # Core financial terms
        'stock', 'market', 'trading', 'investment', 'investor', 'wall street',
        'nasdaq', 'dow', 's&p', 'earnings', 'revenue', 'profit', 'loss',
        'financial', 'finance', 'economy', 'economic', 'fed', 'federal reserve',
        'interest rate', 'inflation', 'gdp', 'unemployment', 'jobs', 'employment',
        
        # Crypto and digital assets
        'bitcoin', 'crypto', 'cryptocurrency', 'ethereum', 'digital asset',
        
        # Banking and financial services
        'bank', 'banking', 'credit', 'loan', 'mortgage', 'debt',
        'ipo', 'merger', 'acquisition', 'dividend', 'bond', 'treasury',
        
        # Commodities and currencies
        'currency', 'dollar', 'euro', 'commodity', 'oil', 'gold', 'silver',
        
        # Real estate and housing
        'real estate', 'housing', 'property', 'reit',
        
        # Business and corporate
        'retail', 'consumer', 'spending', 'sales', 'manufacturing', 'industrial',
        'tech', 'technology', 'ai', 'artificial intelligence', 'startup',
        'venture capital', 'hedge fund', 'mutual fund', 'etf', 'pension',
        
        # Economic indicators
        'tariff', 'trade', 'export', 'import', 'growth', 'recession',
        'bull market', 'bear market', 'volatility',
        
        # Company names and sectors
        'apple', 'microsoft', 'google', 'amazon', 'tesla', 'nvidia',
        'jp morgan', 'goldman sachs', 'berkshire'
    ]
    
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in financial_keywords)

# 🚀 ENHANCED CONTENT EXTRACTION - USE GEMINI FOR ALL INTERNATIONAL SOURCES
async def extract_content_enhanced(url, source_name, news_item=None):
    """Enhanced content extraction - Gemini for ALL international sources"""
    
    # For ALL international sources, use Gemini (not just Yahoo Finance)
    if is_international_source(source_name):
        print(f"🤖 Using Gemini for international source: {source_name}")
        return await extract_content_with_gemini(url, source_name)
    
    # For domestic (CafeF) sources, use traditional methods
    try:
        print(f"🔧 Using traditional methods for domestic source: {source_name}")
        add_random_delay()
        session = requests.Session()
        headers = get_enhanced_headers(url)
        session.headers.update(headers)
        
        response = session.get(url, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            # Method 1: Trafilatura
            if TRAFILATURA_AVAILABLE:
                try:
                    result = trafilatura.bare_extraction(
                        response.content,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        favor_precision=True,
                        with_metadata=True
                    )
                    
                    if result and result.get('text') and len(result['text']) > 300:
                        content = result['text']
                        session.close()
                        return content.strip()
                except Exception as e:
                    print(f"⚠️ Trafilatura failed: {e}")
            
            # Method 2: Newspaper3k
            if NEWSPAPER_AVAILABLE:
                try:
                    session.close()
                    article = Article(url)
                    article.set_config({
                        'headers': headers,
                        'timeout': 15
                    })
                    
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 300:
                        return article.text.strip()
                
                except Exception as e:
                    print(f"⚠️ Newspaper3k failed: {e}")
            
            # Method 3: BeautifulSoup for CafeF
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # CafeF-specific selectors
                    content_selectors = [
                        'div.detail-content',
                        'div.fck_detail',
                        'div.content-detail',
                        'div.article-content',
                        'div.entry-content',
                        'div.post-content',
                        'article',
                        'main'
                    ]
                    
                    content = ""
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            for element in elements:
                                text = element.get_text(strip=True)
                                if len(text) > 500:
                                    content = text
                                    break
                            if content:
                                break
                    
                    if content and len(content) > 500:
                        content = clean_content_enhanced(content)
                        session.close()
                        return content.strip()
                        
                except Exception as e:
                    print(f"⚠️ BeautifulSoup failed: {e}")
        
        session.close()
        print(f"⚠️ All traditional methods failed for {source_name}")
        return create_fallback_content(url, source_name, "Traditional extraction methods failed")
        
    except Exception as e:
        print(f"❌ Extract content error for {source_name}: {e}")
        return create_fallback_content(url, source_name, str(e))

def clean_content_enhanced(content):
    """Enhanced content cleaning for CafeF"""
    if not content:
        return content
    
    # Remove common patterns
    unwanted_patterns = [
        r'Theo.*?CafeF.*?',
        r'Nguồn.*?:.*?',
        r'Tags:.*?$',
        r'Từ khóa:.*?$',
        r'Đăng ký.*?nhận tin.*?',
        r'Like.*?Fanpage.*?',
        r'Follow.*?us.*?'
    ]
    
    for pattern in unwanted_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\n\s*\n', '\n', content)
    
    return content.strip()

# 🚀 OPTIMIZED NEWS COLLECTION - Reduced limits to prevent timeout
async def collect_news_enhanced(sources_dict, limit_per_source=20):  # Reduced from 50
    """OPTIMIZED news collection with RSS feeds + direct scraping"""
    all_news = []
    
    for source_name, source_url in sources_dict.items():
        retry_count = 0
        max_retries = 2  # Reduced from 3
        
        while retry_count < max_retries:
            try:
                print(f"🔄 Processing {source_name} (attempt {retry_count + 1}): {source_url}")
                
                # Determine if it's RSS or direct scraping
                if source_url.endswith('.rss') or 'rss' in source_url.lower() or 'feeds.' in source_url:
                    # RSS Feed processing
                    news_items = await process_rss_feed(source_name, source_url, limit_per_source)
                else:
                    # Direct scraping for Yahoo Finance news pages
                    news_items = scrape_yahoo_finance_news(source_url, limit_per_source)
                
                if news_items:
                    duplicates_found = 0
                    for news_item in news_items:
                        if not is_duplicate_article(news_item, source_name):
                            all_news.append(news_item)
                        else:
                            duplicates_found += 1
                    
                    entries_processed = len(news_items) - duplicates_found
                    print(f"✅ Processed {entries_processed} unique entries from {source_name} (skipped {duplicates_found} duplicates)")
                    break  # Success, exit retry loop
                else:
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        print(f"🔄 Retrying {source_name}...")
                        time.sleep(1)  # Reduced sleep time
                        continue
                    else:
                        print(f"❌ No content from {source_name} after {max_retries} attempts")
                        break
                
            except Exception as e:
                print(f"❌ Error for {source_name}: {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"🔄 Retrying {source_name}...")
                    time.sleep(1)  # Reduced sleep time
                else:
                    print(f"❌ Failed to fetch from {source_name} after {max_retries} attempts")
                    break
    
    print(f"📊 Total unique news collected: {len(all_news)}")
    
    # Sort by publish time
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

async def process_rss_feed(source_name, rss_url, limit_per_source):
    """Process RSS feed with enhanced error handling"""
    try:
        add_random_delay()
        session = requests.Session()
        headers = get_enhanced_headers(rss_url)
        session.headers.update(headers)
        
        response = session.get(rss_url, timeout=10, allow_redirects=True)  # Reduced timeout
        
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
        elif response.status_code in [403, 429]:
            print(f"⚠️ Rate limited for {source_name}, waiting...")
            time.sleep(random.uniform(2.0, 4.0))  # Reduced wait time
            headers['User-Agent'] = random.choice(USER_AGENTS)
            session.headers.update(headers)
            response = session.get(rss_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(rss_url)
        else:
            feed = feedparser.parse(rss_url)
        
        session.close()
        
        if not feed or not hasattr(feed, 'entries') or len(feed.entries) == 0:
            return []
        
        news_items = []
        for entry in feed.entries[:limit_per_source]:
            try:
                vn_time = get_current_vietnam_datetime()
                
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    vn_time = convert_utc_to_vietnam_time(entry.published_parsed)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    vn_time = convert_utc_to_vietnam_time(entry.updated_parsed)
                
                description = ""
                if hasattr(entry, 'summary'):
                    description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                elif hasattr(entry, 'description'):
                    description = entry.description[:400] + "..." if len(entry.description) > 400 else entry.description
                
                if hasattr(entry, 'title') and hasattr(entry, 'link'):
                    title = entry.title.strip()
                    
                    # Filter for relevant economic/financial content
                    if is_relevant_news(title, description, source_name):
                        news_item = {
                            'title': html.unescape(title),
                            'link': entry.link,
                            'source': source_name,
                            'published': vn_time,
                            'published_str': vn_time.strftime("%H:%M %d/%m"),
                            'description': html.unescape(description) if description else ""
                        }
                        news_items.append(news_item)
                
            except Exception as entry_error:
                continue
        
        return news_items
        
    except Exception as e:
        return []

def is_relevant_news(title, description, source_name):
    """Filter for relevant economic/financial news"""
    
    # For CafeF sources, all content is relevant (already filtered by RSS category)
    if 'cafef' in source_name:
        return True
    
    # For Yahoo Finance, use relaxed filter
    if 'yahoo_finance' in source_name:
        return is_relevant_financial_news_relaxed(title)
    
    return True

def save_user_news_enhanced(user_id, news_list, command_type):
    """Enhanced user news saving"""
    global user_news_cache
    
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': get_current_vietnam_datetime()
    }
    
    if len(user_news_cache) > MAX_CACHE_ENTRIES:
        oldest_users = sorted(user_news_cache.items(), key=lambda x: x[1]['timestamp'])[:10]
        for user_id_to_remove, _ in oldest_users:
            del user_news_cache[user_id_to_remove]

def save_user_last_detail(user_id, news_item):
    """Save last article accessed via !chitiet"""
    global user_last_detail_cache
    
    user_last_detail_cache[user_id] = {
        'article': news_item,
        'timestamp': get_current_vietnam_datetime()
    }

# 🔧 DISCORD EMBED HELPERS
def split_text_for_discord(text: str, max_length: int = 950) -> List[str]:
    """Split text to fit Discord field limits"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    sentences = text.split('. ')
    
    for sentence in sentences:
        if len(current_part + sentence + '. ') <= max_length:
            current_part += sentence + '. '
        else:
            if current_part:
                parts.append(current_part.strip())
                current_part = sentence + '. '
            else:
                parts.append(sentence[:max_length])
                current_part = ""
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

def create_optimized_embeds(title: str, content: str, color: int = 0x9932cc) -> List[discord.Embed]:
    """Create optimized embeds for Discord limits"""
    embeds = []
    
    content_parts = split_text_for_discord(content, 950)
    
    for i, part in enumerate(content_parts):
        if i == 0:
            embed = discord.Embed(
                title=validate_and_truncate_content(title, DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
        else:
            embed = discord.Embed(
                title=validate_and_truncate_content(f"{title[:150]}... (Phần {i+1})", DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
        
        field_name = f"📄 Nội dung {f'(Phần {i+1})' if len(content_parts) > 1 else ''}"
        safe_field_name, safe_field_value = validate_embed_field(field_name, part)
        
        embed.add_field(
            name=safe_field_name,
            value=safe_field_value,
            inline=False
        )
        
        embeds.append(embed)
    
    return embeds

def create_safe_embed_with_fields(title: str, description: str, fields_data: List[Tuple[str, str]], color: int = 0x00ff88) -> List[discord.Embed]:
    """Create safe embeds with multiple fields"""
    embeds = []
    
    safe_title = validate_and_truncate_content(title, DISCORD_EMBED_TITLE_LIMIT, "...")
    safe_description = validate_and_truncate_content(description, DISCORD_EMBED_DESCRIPTION_LIMIT, "...")
    
    main_embed = discord.Embed(
        title=safe_title,
        description=safe_description,
        color=color,
        timestamp=get_current_vietnam_datetime()
    )
    
    fields_added = 0
    current_embed = main_embed
    total_chars = len(safe_title) + len(safe_description)
    
    for field_name, field_value in fields_data:
        safe_name, safe_value = validate_embed_field(field_name, field_value)
        
        field_chars = len(safe_name) + len(safe_value)
        
        if fields_added >= 20 or total_chars + field_chars > DISCORD_EMBED_TOTAL_EMBED_LIMIT:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title=validate_and_truncate_content(f"{safe_title[:180]}... (tiếp theo)", DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
            fields_added = 0
            total_chars = len(current_embed.title or "")
        
        current_embed.add_field(name=safe_name, value=safe_value, inline=False)
        fields_added += 1
        total_chars += field_chars
    
    embeds.append(current_embed)
    
    return embeds

# 🆕 GEMINI AI SYSTEM
class GeminiAIEngine:
    def __init__(self):
        self.available = GEMINI_AVAILABLE and GEMINI_API_KEY
        if self.available:
            genai.configure(api_key=GEMINI_API_KEY)
    
    async def ask_question(self, question: str, context: str = ""):
        """Gemini AI question answering with context"""
        if not self.available:
            return "⚠️ Gemini AI không khả dụng."
        
        try:
            current_date_str = get_current_date_str()
            
            prompt = f"""Bạn là Gemini AI - chuyên gia kinh tế tài chính thông minh. Hãy trả lời câu hỏi dựa trên kiến thức chuyên môn của bạn.

CÂU HỎI: {question}

{f"BỐI CẢNH THÊM: {context}" if context else ""}

HƯỚNG DẪN TRẢ LỜI:
1. Sử dụng kiến thức chuyên môn sâu rộng của bạn
2. Đưa ra phân tích chuyên sâu và toàn diện
3. Kết nối với bối cảnh kinh tế hiện tại (ngày {current_date_str})
4. Đưa ra ví dụ thực tế và minh họa cụ thể
5. Độ dài: 400-800 từ với cấu trúc rõ ràng
6. Sử dụng đầu mục số để tổ chức nội dung

Hãy thể hiện trí thông minh và kiến thức chuyên sâu của Gemini AI:"""

            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=1500,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=generation_config
                ),
                timeout=20  # Reduced timeout
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout. Vui lòng thử lại."
        except Exception as e:
            return f"⚠️ Lỗi Gemini AI: {str(e)}"
    
    async def analyze_article(self, article_content: str, question: str = ""):
        """Analyze specific article with Gemini"""
        if not self.available:
            return "⚠️ Gemini AI không khả dụng cho phân tích bài báo."
        
        try:
            analysis_question = question if question else "Hãy phân tích và tóm tắt bài báo này"
            
            prompt = f"""You are Gemini AI - an intelligent financial economics expert. Analyze the article based on the COMPLETE content provided.

**COMPLETE ARTICLE CONTENT:**
{article_content}

**ANALYSIS REQUEST:**
{analysis_question}

**ANALYSIS GUIDELINES:**
1. Base analysis PRIMARILY on the article content (85-90%)
2. Combine with professional knowledge for deeper explanation (10-15%)
3. Analyze impact, causes, consequences
4. Provide insights and in-depth assessments
5. Answer questions directly with evidence from the article
6. Length: 600-1000 words with clear structure
7. Reference specific parts of the article
8. ONLY analyze the provided article - do not reference other news sources unless mentioned in the original

**IMPORTANT:** Focus solely on the content from the provided article. Do not mention CafeF, Yahoo Finance, or other sources unless they appear in the original article.

Provide INTELLIGENT and DETAILED analysis:"""

            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=2000,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=generation_config
                ),
                timeout=30  # Reduced timeout
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout khi phân tích bài báo."
        except Exception as e:
            return f"⚠️ Lỗi Gemini AI: {str(e)}"
    
    async def debate_perspectives(self, topic: str):
        """Multi-perspective debate system with distinct moral characteristics"""
        if not self.available:
            return "⚠️ Gemini AI không khả dụng cho debate."
        
        try:
            prompt = f"""Bạn là Gemini AI với khả năng đóng nhiều vai trò khác nhau. Hãy tổ chức một cuộc tranh luận về chủ đề sau từ 6 góc nhìn khác nhau với tính cách đạo đức riêng biệt:

**CHỦ ĐỀ TRANH LUẬN:** {topic}

**CÁC THÂN PHẬN THAM GIA:**
1. **Nhà Kinh Tế Học Tham Nhũng** - Có đạo đức nghề nghiệp tệ hại, bóp méo số liệu, chỉ phục vụ quyền lợi cá nhân
2. **Phó Giáo Sư Tiến Sĩ Chính Trực** - Có đạo đức cao, học thuật nghiêm túc, quan tâm lợi ích chung
3. **Nhân Viên VP Ham Tiền** - Chỉ quan tâm lương thưởng, sẵn sàng vứt bỏ đạo đức vì lợi nhuận
4. **Người Nghèo Vô Học** - Tầng lớp thấp, không học thức, đạo đức tệ, hay đổ lỗi cho người khác
5. **Người Giàu Ích Kỷ** - Chỉ tìm cách bỏ tiền vào túi mình, không quan tâm hậu quả xã hội
6. **Người Giàu Thông Thái** - Có tầm nhìn xa, hiểu biết sâu rộng, quan tâm phát triển bền vững

**YÊU CẦU:**
- Mỗi thân phận đưa ra 1 đoạn tranh luận (100-150 từ)
- Thể hiện RÕ RÀNG tính cách đạo đức và động cơ của từng nhân vật
- Tạo ra mâu thuẫn và xung đột quan điểm
- Phản ánh thực tế xã hội một cách sắc bén
- Kết thúc bằng phân tích tổng hợp từ Gemini AI

**FORMAT:**
💸 **Nhà KT Học Tham Nhũng:** [quan điểm ích kỷ, bóp méo]
👨‍🏫 **PGS.TS Chính Trực:** [quan điểm học thuật, đạo đức cao]
💼 **Nhân Viên Ham Tiền:** [chỉ quan tâm lương thưởng]
😠 **Người Nghèo Vô Học:** [đổ lỗi, thiếu hiểu biết]
🤑 **Người Giàu Ích Kỷ:** [chỉ tìm lợi nhuận cá nhân]
🧠 **Người Giàu Thông Thái:** [tầm nhìn xa, phát triển bền vững]
🤖 **Gemini AI - Tổng Kết:** [phân tích khách quan các quan điểm]

Hãy tạo ra cuộc tranh luận gay gắt và phản ánh thực tế xã hội:"""

            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.4,
                top_p=0.9,
                max_output_tokens=2000,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=generation_config
                ),
                timeout=25  # Reduced timeout
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout khi tổ chức debate."
        except Exception as e:
            return f"⚠️ Lỗi Gemini AI: {str(e)}"

# Initialize Gemini Engine
gemini_engine = GeminiAIEngine()

# Bot event handlers
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    
    ai_status = "✅ Available" if gemini_engine.available else "❌ Unavailable"
    current_datetime_str = get_current_datetime_str()
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    
    status_text = f"News Bot • {total_sources} sources"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )
    
    print(f"🤖 Gemini AI: {ai_status}")
    print(f"📊 Sources: {total_sources}")
    print(f"🕰️ Started: {current_datetime_str}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu tham số! Gõ `!menu` để xem hướng dẫn.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Tham số không hợp lệ! Gõ `!menu` để xem hướng dẫn.")
    else:
        await ctx.send(f"❌ Lỗi: {str(error)}")

# 🆕 ENHANCED COMMANDS

@bot.command(name='all')
async def get_all_news_enhanced(ctx, page=1):
    """Tin tức từ CafeF và Yahoo Finance với Gemini-powered extraction"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải...")
        
        domestic_news = await collect_news_enhanced(RSS_FEEDS['domestic'], 20)  # Reduced limit
        international_news = await collect_news_enhanced(RSS_FEEDS['international'], 30)  # Reduced limit
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Prepare fields data
        fields_data = []
        
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        # MASSIVE source mapping for 20+ RSS feeds
        source_names = {
            # CafeF sources
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN',
            
            # Yahoo Finance sources
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_rss': 'Yahoo Finance', 'yahoo_finance_crypto': 'Yahoo Crypto',
            'yahoo_finance_tech': 'Yahoo Tech', 'yahoo_finance_stock_market': 'Yahoo Stocks',
            
            # Major financial news sources
            'cnn_money': 'CNN Money', 'reuters_topnews': 'Reuters', 'marketwatch': 'MarketWatch',
            'business_insider': 'Business Insider', 'forbes': 'Forbes', 'wsj': 'Wall Street Journal',
            'cnbc': 'CNBC', 'investing_com': 'Investing.com', 'seekingalpha': 'Seeking Alpha',
            'financial_times': 'Financial Times', 'fortune': 'Fortune', 'economist': 'The Economist',
            'nasdaq': 'Nasdaq', 'washington_post_biz': 'Washington Post', 'guardian_business': 'The Guardian',
            'investopedia': 'Investopedia', 'nikkei_asia': 'Nikkei Asia', 'economic_times': 'Economic Times',
            'bbc_news': 'BBC News', 'coindesk': 'CoinDesk',
            
            # Scraped sources
            'yahoo_finance_scraped': 'Yahoo Scraped'
        }
        
        emoji_map = {
            # CafeF sources
            'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 
            'cafef_vimo': '📊', 'cafef_doanhnghiep': '🏭',
            
            # Yahoo Finance sources
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_rss': '💼',
            'yahoo_finance_crypto': '💰', 'yahoo_finance_tech': '💻', 'yahoo_finance_stock_market': '📈',
            
            # Major financial news sources
            'cnn_money': '📺', 'reuters_topnews': '🌍', 'marketwatch': '📊', 'business_insider': '💼',
            'forbes': '💎', 'wsj': '📰', 'cnbc': '📺', 'investing_com': '💹', 'seekingalpha': '🔍',
            'financial_times': '📊', 'fortune': '💰', 'economist': '🎯', 'nasdaq': '📈',
            'washington_post_biz': '📰', 'guardian_business': '🛡️', 'investopedia': '📚',
            'nikkei_asia': '🌏', 'economic_times': '🇮🇳', 'bbc_news': '🇬🇧', 'coindesk': '₿',
            
            # Scraped sources
            'yahoo_finance_scraped': '🚀'
        }
        
        # Simple statistics
        stats_field = f"🇻🇳 CafeF: {domestic_count} • 🌍 International: {international_count} • 📊 Tổng: {len(all_news)}\n🔥 NEW: 20+ RSS feeds từ GitHub sources!"
        fields_data.append(("📊 Thống kê", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"📰 Tin tức (Trang {page})",
            "",
            fields_data,
            0x00ff88
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số]")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_enhanced(ctx, page=1):
    """Tin tức quốc tế - Fixed Yahoo Finance URLs 2025"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải...")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['international'], 30)  # Reduced limit
        await loading_msg.delete()
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Prepare fields data
        fields_data = []
        
        stats_field = f"📰 International News: {len(news_list)} tin\n🔥 20+ RSS sources: CNN, Reuters, WSJ, Forbes, BBC và nhiều hơn!\n✅ URLs from GitHub verified 2025"
        fields_data.append(("📊 Thông tin", stats_field))
        
        # MASSIVE source names for international sources
        source_names = {
            # Yahoo Finance sources
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_rss': 'Yahoo Finance', 'yahoo_finance_crypto': 'Yahoo Crypto',
            'yahoo_finance_tech': 'Yahoo Tech', 'yahoo_finance_stock_market': 'Yahoo Stocks',
            
            # Major financial news sources
            'cnn_money': 'CNN Money', 'reuters_topnews': 'Reuters', 'marketwatch': 'MarketWatch',
            'business_insider': 'Business Insider', 'forbes': 'Forbes', 'wsj': 'Wall Street Journal',
            'cnbc': 'CNBC', 'investing_com': 'Investing.com', 'seekingalpha': 'Seeking Alpha',
            'financial_times': 'Financial Times', 'fortune': 'Fortune', 'economist': 'The Economist',
            'nasdaq': 'Nasdaq', 'washington_post_biz': 'Washington Post', 'guardian_business': 'The Guardian',
            'investopedia': 'Investopedia', 'nikkei_asia': 'Nikkei Asia', 'economic_times': 'Economic Times',
            'bbc_news': 'BBC News', 'coindesk': 'CoinDesk',
            'yahoo_finance_scraped': 'Yahoo Scraped'
        }
        
        emoji_map = {
            # Yahoo Finance sources
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_rss': '💼',
            'yahoo_finance_crypto': '💰', 'yahoo_finance_tech': '💻', 'yahoo_finance_stock_market': '📈',
            
            # Major financial news sources
            'cnn_money': '📺', 'reuters_topnews': '🌍', 'marketwatch': '📊', 'business_insider': '💼',
            'forbes': '💎', 'wsj': '📰', 'cnbc': '📺', 'investing_com': '💹', 'seekingalpha': '🔍',
            'financial_times': '📊', 'fortune': '💰', 'economist': '🎯', 'nasdaq': '📈',
            'washington_post_biz': '📰', 'guardian_business': '🛡️', 'investopedia': '📚',
            'nikkei_asia': '🌏', 'economic_times': '🇮🇳', 'bbc_news': '🇬🇧', 'coindesk': '₿',
            'yahoo_finance_scraped': '🚀'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '💰')
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            source_display = source_names.get(news['source'], 'International Finance')
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"🌍 Tin nước ngoài (Trang {page})",
            "",
            fields_data,
            0x0066ff
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số]")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_enhanced(ctx, page=1):
    """Tin tức trong nước - CafeF với traditional extraction"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải...")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['domestic'], 20)  # Reduced limit
        await loading_msg.delete()
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Prepare fields data
        fields_data = []
        
        stats_field = f"📰 Tổng tin CafeF: {len(news_list)} tin\n🎯 Lĩnh vực: CK, BĐS, TC, VM, DN"
        fields_data.append(("📊 Thông tin", stats_field))
        
        source_names = {
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN'
        }
        
        emoji_map = {
            'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 
            'cafef_taichinh': '💰', 'cafef_vimo': '📊', 'cafef_doanhnghiep': '🏭'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"🇻🇳 Tin trong nước (Trang {page})",
            "",
            fields_data,
            0xff0000
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số]")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail_enhanced(ctx, news_number: int):
    """Chi tiết bài viết - Gemini cho tin nước ngoài, traditional cho tin trong nước"""
    try:
        user_id = ctx.author.id
        
        if user_id not in user_news_cache:
            await ctx.send("❌ Bạn chưa xem tin tức! Dùng `!all`, `!in`, hoặc `!out` trước.")
            return
        
        user_data = user_news_cache[user_id]
        news_list = user_data['news']
        
        if news_number < 1 or news_number > len(news_list):
            await ctx.send(f"❌ Số không hợp lệ! Chọn từ 1 đến {len(news_list)}")
            return
        
        news = news_list[news_number - 1]
        
        # Save as last detail for !hoi context
        save_user_last_detail(user_id, news)
        
        # Determine extraction method based on source
        if is_international_source(news['source']):
            loading_msg = await ctx.send(f"⏳ Đang tải bằng Gemini AI cho {news['source']}...")
        else:
            loading_msg = await ctx.send(f"⏳ Đang tải...")
        
        # Enhanced content extraction - NOW USES GEMINI FOR ALL INTERNATIONAL
        full_content = await extract_content_enhanced(news['link'], news['source'], news)
        
        # Enhanced source names
        source_names = {
            'cafef_chungkhoan': 'CafeF Chứng Khoán', 'cafef_batdongsan': 'CafeF Bất Động Sản',
            'cafef_taichinh': 'CafeF Tài Chính', 'cafef_vimo': 'CafeF Vĩ Mô', 'cafef_doanhnghiep': 'CafeF Doanh Nghiệp',
            'yahoo_finance_main': 'Yahoo Finance RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_scraped': 'Yahoo Finance Scraped', 'marketwatch': 'MarketWatch',
            'reuters_topnews': 'Reuters', 'cnn_money': 'CNN Money', 'forbes': 'Forbes',
            'wsj': 'Wall Street Journal', 'cnbc': 'CNBC', 'bbc_news': 'BBC News'
        }
        
        source_name = source_names.get(news['source'], news['source'])
        
        await loading_msg.delete()
        
        # Create content with metadata
        main_title = f"📖 Chi tiết tin {news_number}"
        
        # Simple metadata
        content_with_meta = f"**📰 {news['title']}**\n"
        content_with_meta += f"**🕰️ {news['published_str']}** • **📰 {source_name}**\n\n"
        content_with_meta += f"{full_content}"
        
        # Create optimized embeds
        optimized_embeds = create_optimized_embeds(main_title, content_with_meta, 0x9932cc)
        
        # Add link to last embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔗 Link gốc",
                f"[Đọc bài viết gốc]({news['link']})"
            )
            optimized_embeds[-1].add_field(name=safe_name, value=safe_value, inline=False)
            
            optimized_embeds[-1].set_footer(text=f"Tin số {news_number}")
        
        # Send all embeds
        for i, embed in enumerate(optimized_embeds, 1):
            if i == 1:
                await ctx.send(embed=embed)
            else:
                await asyncio.sleep(0.5)
                await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='hoi')
async def enhanced_gemini_question(ctx, *, question):
    """Enhanced Gemini AI với context awareness"""
    try:
        if not gemini_engine.available:
            embed = create_safe_embed(
                "⚠️ Gemini AI không khả dụng",
                "Cần Gemini API key để hoạt động.",
                0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        current_datetime_str = get_current_datetime_str()
        
        # Check if user has recent !chitiet context
        user_id = ctx.author.id
        context = ""
        context_info = ""
        
        if user_id in user_last_detail_cache:
            last_detail = user_last_detail_cache[user_id]
            # Check if accessed within last 30 minutes
            time_diff = get_current_vietnam_datetime() - last_detail['timestamp']
            
            if time_diff.total_seconds() < 1800:  # 30 minutes
                article = last_detail['article']
                
                # Extract content for context
                article_content = await extract_content_enhanced(article['link'], article['source'], article)
                
                if article_content:
                    context = f"BÀI BÁO LIÊN QUAN:\nTiêu đề: {article['title']}\nNguồn: {article['source']}\nNội dung: {article_content[:1500]}"
                    context_info = f"📰 **Context:** Bài báo vừa xem"
        
        progress_embed = create_safe_embed(
            "🤖 Gemini AI",
            f"Đang phân tích: {question[:100]}...",
            0x9932cc
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get Gemini response
        if context:
            # Article analysis mode
            analysis_result = await gemini_engine.analyze_article(context, question)
        else:
            # General question mode
            analysis_result = await gemini_engine.ask_question(question, context)
        
        # Create optimized embeds
        title = f"🤖 Gemini AI"
        optimized_embeds = create_optimized_embeds(title, analysis_result, 0x00ff88)
        
        # Simple footer
        if optimized_embeds:
            optimized_embeds[-1].set_footer(text=f"Gemini AI")
        
        # Send optimized embeds
        await progress_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Gemini: {str(e)}")

@bot.command(name='debate')
async def gemini_debate_system(ctx, *, topic=""):
    """Multi-perspective debate system với Gemini"""
    try:
        if not gemini_engine.available:
            embed = create_safe_embed(
                "⚠️ Gemini AI không khả dụng",
                "Cần Gemini API key để hoạt động.",
                0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Determine debate topic
        if not topic:
            # Use last !chitiet article if available
            user_id = ctx.author.id
            if user_id in user_last_detail_cache:
                last_detail = user_last_detail_cache[user_id]
                time_diff = get_current_vietnam_datetime() - last_detail['timestamp']
                
                if time_diff.total_seconds() < 1800:  # 30 minutes
                    article = last_detail['article']
                    topic = f"Bài báo: {article['title']}"
                else:
                    await ctx.send("❌ Vui lòng nhập chủ đề debate hoặc xem bài báo bằng !chitiet trước.")
                    return
            else:
                await ctx.send("❌ Vui lòng nhập chủ đề debate! Ví dụ: `!debate lạm phát hiện tại`")
                return
        
        progress_embed = create_safe_embed(
            "🎭 Gemini Debate",
            f"Chủ đề: {topic[:100]}...",
            0xff9900
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get debate analysis
        debate_result = await gemini_engine.debate_perspectives(topic)
        
        # Create optimized embeds
        title = f"🎭 Debate"
        optimized_embeds = create_optimized_embeds(title, debate_result, 0xff6600)
        
        # Simple footer
        if optimized_embeds:
            optimized_embeds[-1].set_footer(text=f"Gemini Debate")
        
        # Send optimized embeds
        await progress_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống debate: {str(e)}")

@bot.command(name='menu')
async def help_command_optimized(ctx):
    """Simple menu guide"""
    
    main_embed = create_safe_embed(
        "📰 News Bot - 20+ RSS Sources",
        "CafeF + CNN + Reuters + WSJ + Forbes + BBC + 15 more!",
        0x00ff88
    )
    
    safe_name1, safe_value1 = validate_embed_field(
        "📰 Lệnh tin tức",
        "**!all [trang]** - Tất cả tin tức\n**!in [trang]** - Tin trong nước\n**!out [trang]** - Tin nước ngoài\n**!chitiet [số]** - Chi tiết bài viết"
    )
    main_embed.add_field(name=safe_name1, value=safe_value1, inline=False)
    
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 Lệnh AI",
        "**!hoi [câu hỏi]** - Hỏi AI\n**!debate [chủ đề]** - Tranh luận"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=False)
    
    await ctx.send(embed=main_embed)

# 🆕 STATUS COMMAND
@bot.command(name='status')
async def status_command(ctx):
    """Hiển thị trạng thái hệ thống"""
    
    # System statistics
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    global_cache_size = len(global_seen_articles)
    
    main_embed = create_safe_embed(
        "📊 Trạng thái hệ thống - 20+ RSS Sources",
        "",
        0x00ff88
    )
    
    safe_name1, safe_value1 = validate_embed_field(
        "📰 Nguồn tin",
        f"🇻🇳 CafeF: {len(RSS_FEEDS['domestic'])}\n🌍 International: {len(RSS_FEEDS['international'])}\n📊 Tổng: {total_sources}\n🔥 20+ RSS feeds từ GitHub sources!\n✅ CNN, Reuters, WSJ, Forbes, BBC..."
    )
    main_embed.add_field(name=safe_name1, value=safe_value1, inline=True)
    
    gemini_status = "✅" if gemini_engine.available else "❌"
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI System",
        f"Gemini AI: {gemini_status}\nCache: {global_cache_size}\n⚡ Optimized timeouts"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=True)
    
    await ctx.send(embed=main_embed)

# Run the bot
if __name__ == "__main__":
    try:
        keep_alive()
        print("🌐 Keep-alive server started")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        
        print("🚀 Starting MASSIVE RSS News Bot...")
        print(f"🔧 Sources: {total_sources} (20+ RSS feeds)")
        print(f"🤖 Gemini: {'✅' if gemini_engine.available else '❌'}")
        print("🔥 MASSIVE RSS collection from GitHub sources")
        print("📰 CNN, Reuters, WSJ, Forbes, BBC, CNBC + more!")
        print("⚡ Optimized timeouts and limits")
        print("=" * 40)
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ STARTUP ERROR: {e}")
