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

print("🚀 GEMINI-POWERED YAHOO FINANCE BOT:")
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'}")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'}")
print(f"🔧 Current Vietnam time: {get_current_datetime_str()}")
print("=" * 50)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🔧 ENHANCED FEEDS - RSS + Direct Scraping
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - CHỈ CAFEF ===
    'domestic': {
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafef_doanhnghiep': 'https://cafef.vn/doanh-nghiep.rss'
    },
    
    # === QUỐC TẾ - Enhanced Yahoo Finance RSS + Direct Scraping ===
    'international': {
        # Working RSS Feeds
        'yahoo_finance_main': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_headlines': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        
        # Direct Scraping Sources
        'yahoo_finance_direct': 'https://finance.yahoo.com/news/',
        'yahoo_finance_latest': 'https://finance.yahoo.com/topic/latest-news/',
        'yahoo_finance_markets': 'https://finance.yahoo.com/topic/stock-market-news/',
        'yahoo_finance_crypto_news': 'https://finance.yahoo.com/topic/crypto/',
        'yahoo_finance_economy_news': 'https://finance.yahoo.com/topic/economic-news/'
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

# 🔧 Enhanced headers with retry mechanism
def get_enhanced_headers(url=None):
    """Enhanced headers for Yahoo Finance with anti-blocking"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Site': 'none',
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
    """Add random delay to avoid rate limiting"""
    delay = random.uniform(0.5, 2.0)
    time.sleep(delay)

# 🆕 DIRECT YAHOO FINANCE NEWS SCRAPING
def scrape_yahoo_finance_news(base_url, limit=30):
    """Scrape news directly from Yahoo Finance news pages"""
    try:
        print(f"🔄 Direct scraping: {base_url}")
        add_random_delay()
        
        session = requests.Session()
        headers = get_enhanced_headers(base_url)
        session.headers.update(headers)
        
        response = session.get(base_url, timeout=15, allow_redirects=True)
        
        if response.status_code != 200:
            print(f"❌ Failed to scrape {base_url}: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Enhanced selectors for Yahoo Finance news articles
        news_articles = []
        
        # Method 1: Look for news article containers
        article_selectors = [
            'h3 > a[href*="/news/"]',          # News article links in h3
            'a[href*="/news/"][data-module]',   # Links with data-module
            'h3 a',                             # All h3 links
            'div[data-testid] a[href*="/news/"]', # Test ID containers
            '.js-content-viewer',               # Content viewer links
            '[href*="/news/"] h3',              # News links with h3
            'h2 a[href*="/news/"]'              # H2 news links
        ]
        
        for selector in article_selectors:
            try:
                elements = soup.select(selector)
                for element in elements[:limit]:
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
                        
                        # Filter for financial/economic content
                        if is_relevant_financial_news(title):
                            # Clean selector name for source
                            clean_selector = selector.replace(' ', '_').replace('[', '').replace(']', '').replace('*', '').replace('=', '').replace('"', '').replace('/', '')
                            
                            news_item = {
                                'title': html.unescape(title.strip()),
                                'link': link,
                                'source': f"yahoo_finance_scraped_{clean_selector}",
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

def is_relevant_financial_news(title):
    """Filter for relevant financial/economic news based on title"""
    financial_keywords = [
        'stock', 'market', 'trading', 'investment', 'investor', 'wall street',
        'nasdaq', 'dow', 's&p', 'earnings', 'revenue', 'profit', 'loss',
        'financial', 'finance', 'economy', 'economic', 'fed', 'federal reserve',
        'interest rate', 'inflation', 'gdp', 'unemployment', 'jobs report',
        'bitcoin', 'crypto', 'cryptocurrency', 'ethereum', 'bank', 'banking',
        'ipo', 'merger', 'acquisition', 'dividend', 'bond', 'treasury',
        'currency', 'dollar', 'euro', 'commodity', 'oil', 'gold', 'silver',
        'real estate', 'housing', 'mortgage', 'credit', 'debt', 'loan',
        'retail', 'consumer', 'spending', 'sales', 'manufacturing', 'industrial',
        'tech', 'technology', 'ai', 'artificial intelligence', 'startup',
        'venture capital', 'hedge fund', 'mutual fund', 'etf', 'pension'
    ]
    
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in financial_keywords)

# 🚀 ENHANCED CONTENT EXTRACTION - CafeF uses traditional, Yahoo Finance uses Gemini
async def extract_content_enhanced(url, source_name, news_item=None):
    """Enhanced content extraction - Gemini for international, traditional for domestic"""
    
    # For international (Yahoo Finance) sources, use Gemini
    if is_international_source(source_name):
        return await extract_content_with_gemini(url, source_name)
    
    # For domestic (CafeF) sources, use traditional methods
    try:
        add_random_delay()
        session = requests.Session()
        headers = get_enhanced_headers(url)
        session.headers.update(headers)
        
        response = session.get(url, timeout=20, allow_redirects=True)
        
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
                    pass
            
            # Method 2: Newspaper3k
            if NEWSPAPER_AVAILABLE:
                try:
                    session.close()
                    article = Article(url)
                    article.set_config({
                        'headers': headers,
                        'timeout': 20
                    })
                    
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 300:
                        return article.text.strip()
                
                except Exception as e:
                    pass
            
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
                    pass
        
        session.close()
        return create_fallback_content(url, source_name)
        
    except Exception as e:
        return create_fallback_content(url, source_name, str(e))

# 🆕 GEMINI CONTENT EXTRACTION FOR INTERNATIONAL NEWS
async def extract_content_with_gemini(url, source_name):
    """Use Gemini to extract and translate content from international news"""
    try:
        if not GEMINI_API_KEY or not GEMINI_AVAILABLE:
            return create_fallback_content(url, source_name, "Gemini không khả dụng")
        
        extraction_prompt = f"""Bạn là chuyên gia trích xuất và dịch thuật tin tức tài chính. Hãy truy cập link bài báo sau và thực hiện:

**LINK BÀI BÁO:** {url}

**YÊU CẦU:**
1. Truy cập và đọc TOÀN BỘ nội dung bài báo từ link
2. Trích xuất nội dung chính (bỏ quảng cáo, sidebar, footer)
3. Dịch từ tiếng Anh sang tiếng Việt một cách tự nhiên và chính xác
4. Giữ nguyên các con số, phần trăm, tên công ty, thuật ngữ tài chính
5. Sử dụng thuật ngữ kinh tế-tài chính tiếng Việt chuẩn
6. KHÔNG thêm giải thích hay bình luận cá nhân
7. Trả về nội dung đã dịch với cấu trúc rõ ràng

**GHI CHÚ:** Chỉ trả về nội dung bài báo đã được dịch, không cần giải thích quá trình.

**NỘI DUNG ĐÃ DỊCH:**"""

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
                timeout=30
            )
            
            extracted_content = response.text.strip()
            
            # Validate content quality
            if len(extracted_content) > 200 and 'không thể truy cập' not in extracted_content.lower():
                return f"[🤖 Gemini đã trích xuất và dịch] {extracted_content}"
            else:
                return create_fallback_content(url, source_name, "Gemini không thể trích xuất nội dung")
            
        except asyncio.TimeoutError:
            return create_fallback_content(url, source_name, "Gemini timeout")
        except Exception as e:
            return create_fallback_content(url, source_name, f"Lỗi Gemini: {str(e)}")
            
    except Exception as e:
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

def is_international_source(source_name):
    """Check if source is international (Yahoo Finance)"""
    return 'yahoo_finance' in source_name

def create_fallback_content(url, source_name, error_msg=""):
    """Create fallback content when extraction fails"""
    try:
        article_id = url.split('/')[-1] if '/' in url else 'news-article'
        
        if is_international_source(source_name):
            return f"""**Yahoo Finance News Analysis:**

📈 **Financial Market Insights:** This article provides financial market analysis and economic insights from Yahoo Finance.

📊 **Market Coverage:**
• Real-time stock market data and analysis
• Economic indicators and market trends
• Corporate earnings and financial reports
• Investment strategies and forecasts

**Article ID:** {article_id}
**Note:** For complete article, please visit the original link.

{f'**Error:** {error_msg}' if error_msg else ''}"""
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

# 🚀 ENHANCED NEWS COLLECTION WITH RSS + SCRAPING
async def collect_news_enhanced(sources_dict, limit_per_source=25):
    """Enhanced news collection with RSS feeds + direct scraping"""
    all_news = []
    
    for source_name, source_url in sources_dict.items():
        retry_count = 0
        max_retries = 3
        
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
                        time.sleep(2)
                        continue
                    else:
                        print(f"❌ No content from {source_name} after {max_retries} attempts")
                        break
                
            except Exception as e:
                print(f"❌ Error for {source_name}: {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"🔄 Retrying {source_name}...")
                    time.sleep(2)
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
        
        response = session.get(rss_url, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
        elif response.status_code in [403, 429]:
            print(f"⚠️ Rate limited for {source_name}, waiting...")
            time.sleep(random.uniform(3.0, 6.0))
            headers['User-Agent'] = random.choice(USER_AGENTS)
            session.headers.update(headers)
            response = session.get(rss_url, timeout=15, allow_redirects=True)
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
    
    # For Yahoo Finance, filter for economic/financial keywords
    if 'yahoo_finance' in source_name:
        return is_relevant_financial_news(title)
    
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
                timeout=25
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
            
            prompt = f"""Bạn là Gemini AI - chuyên gia phân tích tài chính thông minh. Hãy phân tích bài báo dựa trên TOÀN BỘ nội dung được cung cấp.

**TOÀN BỘ NỘI DUNG BÀI BÁO:**
{article_content}

**YÊU CẦU PHÂN TÍCH:**
{analysis_question}

**HƯỚNG DẪN PHÂN TÍCH:**
1. Dựa CHÍNH vào nội dung bài báo (85-90%)
2. Kết hợp kiến thức chuyên môn để giải thích sâu hơn (10-15%)
3. Phân tích tác động, nguyên nhân, hậu quả
4. Đưa ra insights và nhận định chuyên sâu
5. Trả lời trực tiếp câu hỏi với evidence từ bài báo
6. Độ dài: 600-1000 từ với cấu trúc rõ ràng
7. Tham chiếu cụ thể đến các phần trong bài

Hãy đưa ra phân tích THÔNG MINH và CHI TIẾT:"""

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
                timeout=35
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
                timeout=30
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
    
    status_text = f"Gemini-Powered Yahoo Finance • {total_sources} sources • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )
    
    print(f"🤖 Gemini AI: {ai_status}")
    print(f"📊 News Sources: {total_sources} (CafeF: {len(RSS_FEEDS['domestic'])}, Yahoo Finance: {len(RSS_FEEDS['international'])})")
    print(f"🔄 Deduplication: Active")
    print(f"🤖 Gemini Content Extraction: {'✅ Active' if gemini_engine.available else '❌ Inactive'}")
    print(f"🕰️ Started at: {current_datetime_str}")

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
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn (RSS + Direct scraping)...")
        
        domestic_news = await collect_news_enhanced(RSS_FEEDS['domestic'], 25)
        international_news = await collect_news_enhanced(RSS_FEEDS['international'], 30)
        
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
        
        # Enhanced source mapping
        source_names = {
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN',
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_direct': 'Yahoo Direct', 'yahoo_finance_latest': 'Yahoo Latest',
            'yahoo_finance_markets': 'Yahoo Markets', 'yahoo_finance_crypto_news': 'Yahoo Crypto',
            'yahoo_finance_economy_news': 'Yahoo Economy'
        }
        
        emoji_map = {
            'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 
            'cafef_vimo': '📊', 'cafef_doanhnghiep': '🏭',
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_direct': '🔍',
            'yahoo_finance_latest': '🆕', 'yahoo_finance_markets': '📊', 'yahoo_finance_crypto_news': '₿',
            'yahoo_finance_economy_news': '🌍'
        }
        
        # Fallback for scraped sources
        for news in page_news:
            if news['source'] not in source_names:
                if 'yahoo_finance_scraped' in news['source']:
                    source_names[news['source']] = 'Yahoo Scraped'
                    emoji_map[news['source']] = '🚀'
        
        # Add enhanced statistics
        stats_field = f"🇻🇳 CafeF: {domestic_count} tin\n🌍 Yahoo Finance: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin\n🤖 Gemini Extraction: {'✅ Active' if gemini_engine.available else '❌ Inactive'}"
        fields_data.append(("📊 Thống kê Gemini-Powered", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"📰 Tin tức tổng hợp Gemini-Powered (Trang {page})",
            "",
            fields_data,
            0x00ff88
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"🤖 Gemini-Powered Bot • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_enhanced(ctx, page=1):
    """Tin tức quốc tế - Gemini-Powered Yahoo Finance với RSS + Direct Scraping"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức từ {len(RSS_FEEDS['international'])} nguồn Yahoo Finance (RSS + Scraping + Gemini)...")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['international'], 30)
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
        
        # Count by method
        rss_count = sum(1 for news in page_news if 'scraped' not in news['source'])
        scraped_count = len(page_news) - rss_count
        
        stats_field = f"📰 Tổng tin Yahoo Finance: {len(news_list)} tin\n🤖 Gemini Content Extraction: {'✅ Active' if gemini_engine.available else '❌ Inactive'}\n📊 RSS: {rss_count} tin • 🔍 Scraped: {scraped_count} tin\n🌐 Auto-translate: Gemini AI"
        fields_data.append(("📊 Thông tin Gemini-Powered", stats_field))
        
        # Enhanced source names
        source_names = {
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_direct': 'Yahoo Direct', 'yahoo_finance_latest': 'Yahoo Latest',
            'yahoo_finance_markets': 'Yahoo Markets', 'yahoo_finance_crypto_news': 'Yahoo Crypto',
            'yahoo_finance_economy_news': 'Yahoo Economy'
        }
        
        emoji_map = {
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_direct': '🔍',
            'yahoo_finance_latest': '🆕', 'yahoo_finance_markets': '📊', 'yahoo_finance_crypto_news': '₿',
            'yahoo_finance_economy_news': '🌍'
        }
        
        # Handle scraped sources
        for news in page_news:
            if news['source'] not in source_names:
                if 'yahoo_finance_scraped' in news['source']:
                    source_names[news['source']] = 'Yahoo Scraped'
                    emoji_map[news['source']] = '🚀'
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '💰')
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            source_display = source_names.get(news['source'], 'Yahoo Finance')
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"🌍 Tin kinh tế quốc tế Gemini-Powered (Trang {page})",
            "",
            fields_data,
            0x0066ff
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"🤖 Gemini-Powered Yahoo Finance • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_enhanced(ctx, page=1):
    """Tin tức trong nước - CafeF với traditional extraction"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức CafeF...")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['domestic'], 25)
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
        
        stats_field = f"📰 Tổng tin CafeF: {len(news_list)} tin\n🎯 Lĩnh vực: CK, BĐS, TC, VM, DN\n🔧 Extraction: Traditional methods (Trafilatura, Newspaper3k, BeautifulSoup)"
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
            f"🇻🇳 Tin kinh tế CafeF (Trang {page})",
            "",
            fields_data,
            0xff0000
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"CafeF Vietnam • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
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
            loading_msg = await ctx.send(f"🤖 Đang trích xuất nội dung với Gemini AI...")
        else:
            loading_msg = await ctx.send(f"🔧 Đang trích xuất nội dung với traditional methods...")
        
        # Enhanced content extraction
        full_content = await extract_content_enhanced(news['link'], news['source'], news)
        
        # Enhanced source names
        source_names = {
            'cafef_chungkhoan': 'CafeF Chứng Khoán', 'cafef_batdongsan': 'CafeF Bất Động Sản',
            'cafef_taichinh': 'CafeF Tài Chính', 'cafef_vimo': 'CafeF Vĩ Mô', 'cafef_doanhnghiep': 'CafeF Doanh Nghiệp',
            'yahoo_finance_main': 'Yahoo Finance RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_direct': 'Yahoo Direct Scraping', 'yahoo_finance_latest': 'Yahoo Latest News',
            'yahoo_finance_markets': 'Yahoo Markets', 'yahoo_finance_crypto_news': 'Yahoo Crypto',
            'yahoo_finance_economy_news': 'Yahoo Economy'
        }
        
        # Handle scraped sources
        if news['source'] not in source_names and 'yahoo_finance_scraped' in news['source']:
            source_names[news['source']] = 'Yahoo Finance Scraped'
        
        source_name = source_names.get(news['source'], news['source'])
        
        await loading_msg.delete()
        
        # Determine extraction method used
        is_gemini_extracted = "[🤖 Gemini đã trích xuất" in full_content if full_content else False
        extraction_method = "🤖 Gemini AI" if is_gemini_extracted else "🔧 Traditional Methods"
        
        # Create content with metadata
        main_title = f"📖 Chi tiết bài viết - {extraction_method}"
        
        # Enhanced metadata
        content_with_meta = f"**📰 Tiêu đề:** {news['title']}\n"
        content_with_meta += f"**🕰️ Thời gian:** {news['published_str']} ({get_current_date_str()})\n"
        content_with_meta += f"**📰 Nguồn:** {source_name}\n"
        content_with_meta += f"**🔧 Extraction Method:** {extraction_method}\n"
        
        if is_gemini_extracted:
            content_with_meta += f"**🌐 Gemini Translation:** Đã trích xuất và dịch tự động\n"
        
        content_with_meta += f"\n**📄 Nội dung chi tiết:**\n{full_content}"
        
        # Create optimized embeds
        optimized_embeds = create_optimized_embeds(main_title, content_with_meta, 0x9932cc)
        
        # Add link to last embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔗 Đọc bài viết gốc",
                f"[Nhấn để đọc bài viết gốc]({news['link']})"
            )
            optimized_embeds[-1].add_field(name=safe_name, value=safe_value, inline=False)
            
            optimized_embeds[-1].set_footer(text=f"🤖 Gemini-Powered Content System • Tin số {news_number} • {len(optimized_embeds)} phần")
        
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
                    context_info = f"📰 **Context:** Bài báo vừa xem với Gemini-Powered extraction"
        
        progress_embed = create_safe_embed(
            "💎 Gemini AI Powered System",
            f"**Câu hỏi:** {question}\n{context_info}\n🧠 **Đang phân tích với Gemini AI...**",
            0x9932cc
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get Gemini response
        if context:
            # Article analysis mode
            analysis_result = await gemini_engine.analyze_article(context, question)
            strategy_text = "Gemini Article Analysis"
        else:
            # General question mode
            analysis_result = await gemini_engine.ask_question(question, context)
            strategy_text = "Gemini Knowledge Base"
        
        # Create optimized embeds
        title = f"💎 Gemini Analysis - {strategy_text}"
        optimized_embeds = create_optimized_embeds(title, analysis_result, 0x00ff88)
        
        # Add metadata to first embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔍 Gemini Analysis Mode",
                f"**Strategy:** {strategy_text}\n**Context:** {'Article-based' if context else 'Knowledge-based'}\n**Model:** Gemini-2.0-Flash-Exp\n**System:** Gemini-Powered Content Extraction"
            )
            optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
            
            optimized_embeds[-1].set_footer(text=f"💎 Gemini AI Powered • {current_datetime_str}")
        
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
            "🎭 Gemini Debate Powered System",
            f"**Chủ đề:** {topic}\n🎪 **Đang tổ chức tranh luận với 6 thân phận có đạo đức khác nhau...**",
            0xff9900
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get debate analysis
        debate_result = await gemini_engine.debate_perspectives(topic)
        
        # Create optimized embeds
        title = f"🎭 Multi-Perspective Debate Powered"
        optimized_embeds = create_optimized_embeds(title, debate_result, 0xff6600)
        
        # Add metadata to first embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🎪 Gemini Debate Info",
                f"**Topic:** {topic[:80]}...\n**Characters:** 6 thân phận với đặc điểm đạo đức riêng biệt\n**AI Engine:** Gemini Multi-Role Advanced\n**System:** Gemini-Powered moral diversity analysis"
            )
            optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
            
            optimized_embeds[-1].set_footer(text=f"🎭 Gemini Debate Powered • {get_current_datetime_str()}")
        
        # Send optimized embeds
        await progress_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống debate: {str(e)}")

@bot.command(name='menu')
async def help_command_optimized(ctx):
    """Gemini-Powered menu guide với thống kê chi tiết"""
    current_datetime_str = get_current_datetime_str()
    
    main_embed = create_safe_embed(
        "🤖 Gemini-Powered News Bot - Yahoo Finance Enhanced",
        f"CafeF + Gemini-Enhanced Yahoo Finance với Direct Content Extraction - {current_datetime_str}",
        0xff9900
    )
    
    ai_status = f"🤖 **Gemini AI {'✅ Ready' if gemini_engine.available else '❌ Unavailable'}**"
    extraction_status = f"🔧 **Content Extraction: {'🤖 Gemini (International) + 🔧 Traditional (Domestic)' if gemini_engine.available else '🔧 Traditional Only'}**"
    
    safe_name, safe_value = validate_embed_field("🤖 Gemini-Powered Status", f"{ai_status}\n{extraction_status}")
    main_embed.add_field(name=safe_name, value=safe_value, inline=False)
    
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI Commands Powered",
        f"**!hoi [câu hỏi]** - Gemini AI với context awareness\n**!hoi [question]** - Tự động hiểu context từ !chitiet\n**!debate [chủ đề]** - Gemini tranh luận 6 thân phận có đạo đức khác nhau"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=False)
    
    safe_name3, safe_value3 = validate_embed_field(
        "📰 News Commands Enhanced",
        f"**!all [trang]** - CafeF + Yahoo Finance (RSS + Scraping)\n**!in [trang]** - CafeF Vietnam (Traditional extraction)\n**!out [trang]** - Yahoo Finance (Gemini-powered extraction)\n**!chitiet [số]** - Chi tiết: 🤖 Gemini (nước ngoài) + 🔧 Traditional (trong nước)"
    )
    main_embed.add_field(name=safe_name3, value=safe_value3, inline=False)
    
    safe_name4, safe_value4 = validate_embed_field(
        "🎯 Examples Powered",
        f"**!out** - Xem tin Yahoo Finance với Gemini extraction\n**!chitiet 1** - Gemini trích xuất nội dung nước ngoài\n**!hoi tại sao?** - Gemini phân tích bài vừa xem\n**!debate bitcoin** - Gemini tổ chức tranh luận"
    )
    main_embed.add_field(name=safe_name4, value=safe_value4, inline=False)
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    safe_name5, safe_value5 = validate_embed_field(
        "📊 Gemini-Enhanced Sources", 
        f"🇻🇳 **CafeF**: {len(RSS_FEEDS['domestic'])} RSS feeds (Traditional extraction)\n🌍 **Yahoo Finance**: {len(RSS_FEEDS['international'])} sources (RSS + Direct scraping)\n🤖 **Gemini Content**: Direct link access + translation\n📊 **Tổng**: {total_sources} nguồn với dual extraction methods"
    )
    main_embed.add_field(name=safe_name5, value=safe_value5, inline=True)
    
    # Add Gemini features
    safe_name6, safe_value6 = validate_embed_field(
        "🚀 Gemini-Powered Features",
        f"✅ **Gemini Content Extraction**: Trực tiếp truy cập link bài báo\n✅ **Smart Translation**: Gemini tự động dịch tiếng Anh → Việt\n✅ **Dual Extraction**: Gemini (nước ngoài) + Traditional (trong nước)\n✅ **RSS + Scraping**: Multiple Yahoo Finance sources\n✅ **Context Awareness**: Gemini hiểu context từ !chitiet"
    )
    main_embed.add_field(name=safe_name6, value=safe_value6, inline=True)
    
    main_embed.set_footer(text=f"🤖 Gemini-Powered News Bot • {current_datetime_str}")
    await ctx.send(embed=main_embed)

# 🆕 STATUS COMMAND
@bot.command(name='status')
async def status_command(ctx):
    """Hiển thị trạng thái hệ thống Gemini-Powered"""
    current_datetime_str = get_current_datetime_str()
    
    # System statistics
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    global_cache_size = len(global_seen_articles)
    user_cache_size = len(user_news_cache)
    
    main_embed = create_safe_embed(
        "📊 Gemini-Powered System Status",
        f"Trạng thái hệ thống lúc {current_datetime_str}",
        0x00ff88
    )
    
    # RSS Sources Status
    safe_name1, safe_value1 = validate_embed_field(
        "📰 News Sources Enhanced",
        f"🇻🇳 **CafeF Sources**: {len(RSS_FEEDS['domestic'])} RSS feeds\n🌍 **Yahoo Finance Sources**: {len(RSS_FEEDS['international'])} (RSS + Direct scraping)\n📊 **Total Active Sources**: {total_sources}\n🔧 **Methods**: RSS parsing + Direct HTML scraping"
    )
    main_embed.add_field(name=safe_name1, value=safe_value1, inline=True)
    
    # Gemini Status
    gemini_status = "✅ Ready" if gemini_engine.available else "❌ Unavailable"
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 Gemini AI System",
        f"🧠 **Gemini AI**: {gemini_status}\n🔧 **Content Extraction**: {'🤖 Gemini (International) + 🔧 Traditional (Domestic)' if gemini_engine.available else '🔧 Traditional Only'}\n🌐 **Auto Translation**: {'✅ Active' if gemini_engine.available else '❌ Inactive'}\n📊 **Context Awareness**: {'✅ Active' if gemini_engine.available else '❌ Inactive'}"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=True)
    
    # Deduplication Status
    safe_name3, safe_value3 = validate_embed_field(
        "🔄 Enhanced Systems",
        f"📦 **Global Cache**: {global_cache_size}/{MAX_GLOBAL_CACHE} articles\n👥 **User Cache**: {user_cache_size}/{MAX_CACHE_ENTRIES} users\n✅ **Deduplication**: Hash + Similarity + URL comparison\n🚀 **Performance**: Multi-source scraping optimized"
    )
    main_embed.add_field(name=safe_name3, value=safe_value3, inline=True)
    
    # Yahoo Finance Methods
    safe_name4, safe_value4 = validate_embed_field(
        "🌍 Yahoo Finance Enhanced Methods",
        f"📋 **RSS Feeds**: Working Yahoo Finance RSS endpoints\n🔍 **Direct Scraping**: finance.yahoo.com/news/ + topic pages\n🤖 **Gemini Extraction**: Direct link access for full content\n🚀 **Performance**: Multiple fallback methods for reliability"
    )
    main_embed.add_field(name=safe_name4, value=safe_value4, inline=False)
    
    main_embed.set_footer(text=f"📊 Gemini-Powered System Status • Updated: {current_datetime_str}")
    await ctx.send(embed=main_embed)

# Run the bot
if __name__ == "__main__":
    try:
        keep_alive()
        print("🌐 Keep-alive server started")
        
        print("🚀 Starting Gemini-Powered Yahoo Finance News Bot...")
        print(f"🔧 CafeF Sources: {len(RSS_FEEDS['domestic'])} (Traditional extraction)")
        print(f"🔧 Yahoo Finance Sources: {len(RSS_FEEDS['international'])} (RSS + Direct scraping)")
        print(f"🤖 Gemini AI: {'✅ Ready' if gemini_engine.available else '❌ Not Available'}")
        print(f"🔧 Content Extraction: {'🤖 Gemini (International) + 🔧 Traditional (Domestic)' if gemini_engine.available else '🔧 Traditional Only'}")
        print(f"🔄 Deduplication System: ✅ Active")
        print(f"⚡ Enhanced Features: RSS + Scraping, Gemini extraction, Context awareness")
        print(f"⚡ Boot time: {get_current_datetime_str()}")
        print("=" * 80)
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ STARTUP ERROR: {e}")
        print("🔧 Check environment variables and dependencies")
