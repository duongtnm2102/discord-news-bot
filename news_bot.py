import discord
from discord.ext import commands
import feedparser
import asyncio
import os
import re
from datetime import datetime, timedelta
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

# 🚀 OPTIMIZED LIBRARIES - Enhanced for async operations
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
MAX_CACHE_ENTRIES = 25
MAX_GLOBAL_CACHE = 1000

# 🔧 Enhanced User Agents for better compatibility
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

print("🚀 News Bot:")
print(f"Token: {'✅' if TOKEN else '❌'}")
print(f"Gemini: {'✅' if GEMINI_API_KEY else '❌'}")
print("=" * 20)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🔧 FREE RSS FEEDS ONLY - Removed ALL Paywall Sources 2025
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - CHỈ CAFEF ===
    'domestic': {
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafef_doanhnghiep': 'https://cafef.vn/doanh-nghiep.rss'
    },
    
    # === QUỐC TẾ - ONLY FREE RSS SOURCES (NO PAYWALL) ===
    'international': {
        # ✅ YAHOO FINANCE RSS (100% Free)
        'yahoo_finance_main': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_headlines': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        'yahoo_finance_rss': 'https://www.yahoo.com/news/rss/finance',
        
        # ✅ FREE NEWS RSS FEEDS (NO PAYWALL - Verified 2025)
        'cnn_money': 'http://rss.cnn.com/rss/money_topstories.rss',
        'marketwatch': 'http://feeds.marketwatch.com/marketwatch/topstories/',
        'business_insider': 'http://feeds2.feedburner.com/businessinsider',
        'cnbc': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
        'investing_com': 'https://www.investing.com/rss/news.rss',
        'investopedia': 'https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline',
        'bbc_business': 'http://feeds.bbci.co.uk/news/business/rss.xml',
        'guardian_business': 'https://www.theguardian.com/business/economics/rss',
        'coindesk': 'https://feeds.feedburner.com/CoinDesk',
        'nasdaq_news': 'http://articlefeeds.nasdaq.com/nasdaq/categories?category=Investing+Ideas',
        
        # ✅ FREE ALTERNATIVE SOURCES (Removed problematic ones)
        'seeking_alpha': 'https://seekingalpha.com/feed.xml',
        'benzinga': 'https://www.benzinga.com/feed',
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
    clean_title = re.sub(r'[^\w\s]', '', title.lower().strip())
    clean_link = link.lower().strip()
    content = f"{clean_title}|{clean_link}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def clean_expired_cache():
    """Clean expired articles from global cache"""
    global global_seen_articles
    current_time = get_current_vietnam_datetime()
    expired_hashes = []
    
    for article_hash, article_data in global_seen_articles.items():
        time_diff = current_time - article_data['timestamp']
        if time_diff.total_seconds() > (CACHE_EXPIRE_HOURS * 3600):
            expired_hashes.append(article_hash)
    
    for expired_hash in expired_hashes:
        del global_seen_articles[expired_hash]
    
    if expired_hashes:
        print(f"🧹 Cleaned {len(expired_hashes)} expired articles from cache")

def normalize_title(title):
    """Normalize title for exact comparison"""
    import re
    # Convert to lowercase and remove extra spaces
    normalized = re.sub(r'\s+', ' ', title.lower().strip())
    # Remove common punctuation that might vary
    normalized = re.sub(r'[.,!?;:\-\u2013\u2014]', '', normalized)
    # Remove quotes that might vary
    normalized = re.sub(r'["\'\u201c\u201d\u2018\u2019]', '', normalized)
    return normalized

def is_duplicate_article_local(news_item, existing_articles):
    """Check duplicate within current collection - EXACT TITLE MATCH ONLY"""
    current_title = normalize_title(news_item['title'])
    current_link = news_item['link'].lower().strip()
    
    for existing in existing_articles:
        existing_title = normalize_title(existing['title'])
        existing_link = existing['link'].lower().strip()
        
        # Check exact title match OR exact link match
        if current_title == existing_title or current_link == existing_link:
            return True
    
    return False

def is_duplicate_article_global(news_item, source_name):
    """Check duplicate against global cache - EXACT TITLE MATCH ONLY"""
    global global_seen_articles
    
    try:
        # Clean expired cache first
        clean_expired_cache()
        
        current_title = normalize_title(news_item['title'])
        current_link = news_item['link'].lower().strip()
        
        # Check against global cache - EXACT matches only
        for existing_data in global_seen_articles.values():
            existing_title = normalize_title(existing_data['title'])
            existing_link = existing_data['link'].lower().strip()
            
            if current_title == existing_title or current_link == existing_link:
                return True
        
        # Add to global cache using simple key
        cache_key = f"{current_title}|{current_link}"
        
        global_seen_articles[cache_key] = {
            'title': news_item['title'],
            'link': news_item['link'],
            'source': source_name,
            'timestamp': get_current_vietnam_datetime()
        }
        
        # Limit cache size
        if len(global_seen_articles) > MAX_GLOBAL_CACHE:
            sorted_items = sorted(global_seen_articles.items(), key=lambda x: x[1]['timestamp'])
            for old_key, _ in sorted_items[:100]:
                del global_seen_articles[old_key]
        
        return False
        
    except Exception as e:
        print(f"⚠️ Global duplicate check error: {e}")
        return False

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

# 🔧 ASYNC-FIRST APPROACHES - NO MORE BLOCKING
async def async_sleep_delay():
    """FIXED: Use asyncio.sleep instead of time.sleep to prevent heartbeat blocking"""
    delay = random.uniform(0.1, 0.5)  # Much shorter delay
    await asyncio.sleep(delay)

def get_enhanced_headers(url=None):
    """Enhanced headers for better compatibility - NO BROTLI"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate',  # Removed 'br' to avoid brotli errors
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    
    if url and 'yahoo' in url.lower():
        headers.update({
            'Referer': 'https://finance.yahoo.com/',
            'Origin': 'https://finance.yahoo.com',
        })
    elif url and 'cafef.vn' in url.lower():
        headers.update({
            'Referer': 'https://cafef.vn/',
            'Origin': 'https://cafef.vn'
        })
    
    return headers

def is_international_source(source_name):
    """Check if source is international - FIXED for removed sources"""
    international_sources = [
        'yahoo_finance', 'cnn_money', 'marketwatch', 'business_insider',
        'cnbc', 'investing_com', 'investopedia', 'bbc_business',
        'guardian_business', 'coindesk', 'nasdaq_news', 'seeking_alpha', 'benzinga'
    ]
    return any(source in source_name for source in international_sources)

def create_fallback_content(url, source_name, error_msg=""):
    """Create fallback content when extraction fails"""
    try:
        article_id = url.split('/')[-1] if '/' in url else 'news-article'
        
        if is_international_source(source_name):
            source_display = "Financial News"
            if 'marketwatch' in source_name:
                source_display = "MarketWatch"
            elif 'reuters' in source_name:
                source_display = "Reuters"
            elif 'cnn' in source_name:
                source_display = "CNN Money"
            elif 'cnbc' in source_name:
                source_display = "CNBC"
            elif 'bbc' in source_name:
                source_display = "BBC Business"
            
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
        
        extraction_prompt = f"""Truy cập và trích xuất TOÀN BỘ nội dung bài báo từ: {url}

YÊU CẦU:
1. Đọc và hiểu HOÀN TOÀN bài báo
2. Trích xuất TẤT CẢ nội dung chính (loại bỏ quảng cáo, sidebar)
3. Dịch từ tiếng Anh sang tiếng Việt TỰ NHIÊN
4. Giữ nguyên số liệu, tên công ty, thuật ngữ tài chính
5. Độ dài: 500-1500 từ (toàn bộ bài viết)
6. CHỈ trả về nội dung bài báo đã dịch

**NỘI DUNG HOÀN CHỈNH:**"""

        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=3000,  # Tăng từ 2000 để lấy toàn bộ nội dung
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    extraction_prompt,
                    generation_config=generation_config
                ),
                timeout=30  # Tăng timeout từ 20s
            )
            
            extracted_content = response.text.strip()
            
            if len(extracted_content) > 300:
                error_indicators = [
                    'cannot access', 'unable to access', 'không thể truy cập',
                    'failed to retrieve', 'error occurred', 'sorry, i cannot'
                ]
                
                if not any(indicator in extracted_content.lower() for indicator in error_indicators):
                    return f"[🤖 Gemini AI - Toàn bộ nội dung từ {source_name}]\n\n{extracted_content}"
                else:
                    return create_fallback_content(url, source_name, "Gemini không thể trích xuất")
            else:
                return create_fallback_content(url, source_name, "Nội dung quá ngắn")
            
        except asyncio.TimeoutError:
            return create_fallback_content(url, source_name, "Gemini timeout")
        except Exception as e:
            return create_fallback_content(url, source_name, f"Lỗi Gemini: {str(e)}")
            
    except Exception as e:
        return create_fallback_content(url, source_name, str(e))

# 🚀 ASYNC HTTP CLIENT - NO MORE BLOCKING REQUESTS
async def fetch_with_aiohttp(url, headers=None, timeout=8):
    """FIXED: Use aiohttp instead of requests to prevent blocking"""
    try:
        if headers is None:
            headers = get_enhanced_headers(url)
        
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_config, headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return content
                else:
                    return None
    except Exception as e:
        print(f"❌ aiohttp fetch error for {url}: {e}")
        return None

# 🚀 ASYNC CONTENT EXTRACTION - Non-blocking
async def extract_content_enhanced(url, source_name, news_item=None):
    """Enhanced content extraction - Gemini for international, traditional for domestic"""
    
    # For international sources, use Gemini
    if is_international_source(source_name):
        print(f"🤖 Using Gemini for international source: {source_name}")
        return await extract_content_with_gemini(url, source_name)
    
    # For domestic (CafeF) sources, use traditional async methods
    try:
        print(f"🔧 Using async traditional methods for domestic source: {source_name}")
        await async_sleep_delay()
        
        content = await fetch_with_aiohttp(url)
        
        if content:
            # Method 1: Trafilatura with enhanced config for full content
            if TRAFILATURA_AVAILABLE:
                try:
                    result = await asyncio.to_thread(
                        trafilatura.bare_extraction,
                        content,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        include_images=False,
                        favor_precision=False,  # Changed to False for more content
                        favor_recall=True,      # Added for maximum content
                        with_metadata=True,
                        prune_xpath=[],         # Don't prune anything
                        only_with_metadata=False
                    )
                    
                    if result and result.get('text') and len(result['text']) > 200:
                        full_text = result['text']
                        
                        # Try to get more content with different settings
                        if len(full_text) < 1000:
                            result2 = await asyncio.to_thread(
                                trafilatura.extract,
                                content,
                                include_comments=True,
                                include_tables=True,
                                include_links=True,
                                favor_precision=False,
                                favor_recall=True
                            )
                            if result2 and len(result2) > len(full_text):
                                full_text = result2
                        
                        return full_text.strip()
                except Exception as e:
                    print(f"⚠️ Trafilatura failed: {e}")
            
            # Method 2: Enhanced BeautifulSoup with multiple strategies
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = await asyncio.to_thread(BeautifulSoup, content, 'html.parser')
                    
                    # Strategy 1: CafeF specific selectors
                    content_selectors = [
                        'div.detail-content',
                        'div.fck_detail', 
                        'div.content-detail',
                        'div.article-content',
                        'div.entry-content',
                        'div.post-content',
                        'article',
                        'main',
                        '.article-body',
                        '.content-body',
                        '.post-body'
                    ]
                    
                    extracted_text = ""
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            for element in elements:
                                text = element.get_text(strip=True)
                                if len(text) > len(extracted_text):
                                    extracted_text = text
                    
                    # Strategy 2: Find all paragraphs and combine
                    if len(extracted_text) < 500:
                        all_paragraphs = soup.find_all('p')
                        paragraph_texts = []
                        for p in all_paragraphs:
                            p_text = p.get_text(strip=True)
                            if len(p_text) > 50:  # Only substantial paragraphs
                                paragraph_texts.append(p_text)
                        
                        combined_text = '\n\n'.join(paragraph_texts)
                        if len(combined_text) > len(extracted_text):
                            extracted_text = combined_text
                    
                    if extracted_text and len(extracted_text) > 300:
                        cleaned_content = clean_content_enhanced(extracted_text)
                        return cleaned_content.strip()
                        
                except Exception as e:
                    print(f"⚠️ BeautifulSoup failed: {e}")
            
            # Method 3: Newspaper3k fallback
            if NEWSPAPER_AVAILABLE:
                try:
                    from newspaper import Article
                    article = Article(url)
                    article.set_config({
                        'headers': get_enhanced_headers(url),
                        'timeout': 12
                    })
                    
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 300:
                        return article.text.strip()
                
                except Exception as e:
                    print(f"⚠️ Newspaper3k failed: {e}")
        
        print(f"⚠️ All traditional methods failed for {source_name}")
        return create_fallback_content(url, source_name, "Traditional extraction methods failed")
        
    except Exception as e:
        print(f"❌ Extract content error for {source_name}: {e}")
        return create_fallback_content(url, source_name, str(e))

def clean_content_enhanced(content):
    """Enhanced content cleaning for CafeF"""
    if not content:
        return content
    
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
    
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\n\s*\n', '\n', content)
    
    return content.strip()

# 🚀 ASYNC NEWS COLLECTION - Fully non-blocking
async def collect_news_enhanced(sources_dict, limit_per_source=15, use_global_dedup=False):
    """Session-based collection with EXACT TITLE duplicate detection"""
    all_news = []
    
    print(f"🔄 Starting collection from {len(sources_dict)} sources (Global dedup: {use_global_dedup})")
    print(f"🎯 Duplicate logic: EXACT title match only")
    
    # Clean expired cache before starting
    if use_global_dedup:
        clean_expired_cache()
    
    # Create tasks for concurrent processing
    tasks = []
    for source_name, source_url in sources_dict.items():
        task = process_single_source(source_name, source_url, limit_per_source)
        tasks.append(task)
    
    # Process all sources concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Collect results with exact title duplicate detection
    total_processed = 0
    local_duplicates = 0
    global_duplicates = 0
    
    for result in results:
        if isinstance(result, Exception):
            print(f"❌ Source processing error: {result}")
        elif result:
            for news_item in result:
                total_processed += 1
                
                # Local duplicate check (exact title/link match within current collection)
                if is_duplicate_article_local(news_item, all_news):
                    local_duplicates += 1
                    print(f"🔄 Local duplicate: {news_item['title'][:50]}...")
                    continue
                
                # Global duplicate check (exact title/link match cross-session) - only if enabled
                if use_global_dedup and is_duplicate_article_global(news_item, news_item['source']):
                    global_duplicates += 1
                    print(f"🌍 Global duplicate: {news_item['title'][:50]}...")
                    continue
                
                # Add unique article
                all_news.append(news_item)
    
    unique_count = len(all_news)
    print(f"📊 Processed: {total_processed}, Local dups: {local_duplicates}, Global dups: {global_duplicates}, Unique: {unique_count}")
    
    # Sort by publish time
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

async def process_single_source(source_name, source_url, limit_per_source):
    """Process a single RSS source asynchronously"""
    try:
        print(f"🔄 Processing {source_name}: {source_url}")
        
        if source_url.endswith('.rss') or 'rss' in source_url.lower() or 'feeds.' in source_url:
            # RSS Feed processing
            return await process_rss_feed_async(source_name, source_url, limit_per_source)
        else:
            # For future expansion - direct scraping
            return []
            
    except Exception as e:
        print(f"❌ Error for {source_name}: {e}")
        return []

async def process_rss_feed_async(source_name, rss_url, limit_per_source):
    """FIXED: Async RSS feed processing to prevent blocking"""
    try:
        await async_sleep_delay()
        
        # Use aiohttp instead of requests
        content = await fetch_with_aiohttp(rss_url)
        
        if content:
            # Parse feedparser in thread to avoid blocking
            feed = await asyncio.to_thread(feedparser.parse, content)
        else:
            # Fallback to direct feedparser
            feed = await asyncio.to_thread(feedparser.parse, rss_url)
        
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
        
        print(f"✅ Processed {len(news_items)} articles from {source_name}")
        return news_items
        
    except Exception as e:
        print(f"❌ RSS processing error for {source_name}: {e}")
        return []

def is_relevant_news(title, description, source_name):
    """Filter for relevant economic/financial news - MORE RELAXED"""
    # For CafeF sources, all content is relevant
    if 'cafef' in source_name:
        return True
    
    # For international sources, use very relaxed filter
    financial_keywords = [
        'stock', 'market', 'trading', 'investment', 'economy', 'economic',
        'bitcoin', 'crypto', 'currency', 'bank', 'financial', 'finance',
        'earnings', 'revenue', 'profit', 'inflation', 'fed', 'gdp',
        'business', 'company', 'corporate', 'industry', 'sector',
        'money', 'cash', 'capital', 'fund', 'price', 'cost', 'value',
        'growth', 'analyst', 'forecast', 'report', 'data', 'sales'
    ]
    
    title_lower = title.lower()
    description_lower = description.lower() if description else ""
    
    # Check in both title and description
    for keyword in financial_keywords:
        if keyword in title_lower or keyword in description_lower:
            return True
    
    # If no keywords found, still include (very relaxed)
    return True  # Changed from False to True - accept all articles

def get_or_collect_user_news(user_id, command_type, sources_dict, limit_per_source=15):
    """Get cached news or collect new ones for consistent pagination"""
    global user_news_cache
    
    # Check if user has recent cached news for this command
    if user_id in user_news_cache:
        cached_data = user_news_cache[user_id]
        time_diff = get_current_vietnam_datetime() - cached_data['timestamp']
        
        # If cache is recent (< 10 minutes) and same command type, use it
        if time_diff.total_seconds() < 600 and cached_data['command'].startswith(command_type):
            print(f"📱 Using cached news for user {user_id}: {len(cached_data['news'])} articles")
            return cached_data['news'], True  # True = from cache
    
    print(f"🔄 Need to collect fresh news for user {user_id}")
    return [], False  # False = need to collect

async def collect_and_cache_news(user_id, command_type, sources_dict, limit_per_source=15):
    """Collect fresh news and cache for user"""
    # Collect with minimal global deduplication for fresh session
    all_news = await collect_news_enhanced(sources_dict, limit_per_source, use_global_dedup=False)
    
    # Cache for user
    save_user_news_enhanced(user_id, all_news, command_type)
    
    return all_news

def save_user_news_enhanced(user_id, news_list, command_type, current_page=1):
    """Enhanced user news saving with pagination info"""
    global user_news_cache
    
    user_news_cache[user_id] = {
        'news': news_list,  # Full news list
        'command': command_type,
        'current_page': current_page,
        'timestamp': get_current_vietnam_datetime()
    }
    
    if len(user_news_cache) > MAX_CACHE_ENTRIES:
        oldest_users = sorted(user_news_cache.items(), key=lambda x: x[1]['timestamp'])[:10]
        for user_id_to_remove, _ in oldest_users:
            del user_news_cache[user_id_to_remove]

def save_user_page_context(user_id, page_news, page_number):
    """Save current page context for !chitiet"""
    global user_news_cache
    
    if user_id in user_news_cache:
        user_news_cache[user_id]['current_page'] = page_number
        user_news_cache[user_id]['current_page_news'] = page_news  # Current page's 12 items

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
                timeout=15
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout. Vui lòng thử lại."
        except Exception as e:
            return f"⚠️ Lỗi Gemini AI: {str(e)}"
    
    async def debate_perspectives(self, topic: str):
        """Multi-perspective debate system"""
        if not self.available:
            return "⚠️ Gemini AI không khả dụng."
        
        try:
            prompt = f"""Tổ chức cuộc tranh luận về: {topic}

6 quan điểm khác nhau:
💸 **Nhà KT Tham Nhũng:** [ích kỷ, bóp méo số liệu]
👨‍🏫 **GS Chính Trực:** [học thuật, đạo đức cao]  
💼 **Nhân Viên Ham Tiền:** [chỉ quan tâm lương]
😠 **Người Nghèo:** [đổ lỗi, thiếu hiểu biết]
🤑 **Người Giàu Ích Kỷ:** [chỉ tìm lợi nhuận]
🧠 **Người Giàu Thông Thái:** [tầm nhìn xa]
🤖 **Tổng Kết:** [phân tích khách quan]

Mỗi góc nhìn 80-120 từ, thể hiện rõ tính cách:"""

            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.4,
                top_p=0.9,
                max_output_tokens=1500,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=generation_config
                ),
                timeout=20
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout."
        except Exception as e:
            return f"⚠️ Lỗi Gemini AI: {str(e)}"
    
    async def analyze_article(self, article_content: str, question: str = ""):
        """Analyze specific article with Gemini - Vietnamese response"""
        if not self.available:
            return "⚠️ Gemini AI không khả dụng cho phân tích bài báo."
        
        try:
            analysis_question = question if question else "Hãy phân tích và tóm tắt bài báo này"
            
            prompt = f"""Bạn là Gemini AI - chuyên gia kinh tế tài chính thông minh. Hãy phân tích bài báo dựa trên NỘI DUNG HOÀN CHỈNH được cung cấp.

**NỘI DUNG BÀI BÁO HOÀN CHỈNH:**
{article_content}

**YÊU CẦU PHÂN TÍCH:**
{analysis_question}

**HƯỚNG DẪN PHÂN TÍCH:**
1. Phân tích CHỦ YẾU dựa trên nội dung bài báo (85-90%)
2. Kết hợp kiến thức chuyên môn để giải thích sâu hơn (10-15%)
3. Phân tích tác động, nguyên nhân, hậu quả
4. Đưa ra nhận định và đánh giá chuyên sâu
5. Trả lời câu hỏi trực tiếp với bằng chứng từ bài báo
6. Độ dài: 600-1000 từ với cấu trúc rõ ràng
7. Tham chiếu các phần cụ thể trong bài báo
8. CHỈ phân tích bài báo được cung cấp

**QUAN TRỌNG:** Tập trung hoàn toàn vào nội dung từ bài báo đã cung cấp. Đưa ra phân tích THÔNG MINH và CHI TIẾT bằng tiếng Việt:"""

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
                timeout=20
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini AI timeout khi phân tích bài báo."
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
    
    status_text = f"News • {total_sources} sources"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )
    
    print(f"🤖 AI: {ai_status}")
    print(f"📊 Sources: {total_sources}")

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

# 🆕 ENHANCED COMMANDS - ALL ASYNC

@bot.command(name='all')
async def get_all_news_enhanced(ctx, page=1):
    """Tin tức từ CafeF và các nguồn free quốc tế"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳")
        
        # Concurrent processing
        domestic_task = collect_news_enhanced(RSS_FEEDS['domestic'], 15)
        international_task = collect_news_enhanced(RSS_FEEDS['international'], 20)
        
        domestic_news, international_news = await asyncio.gather(domestic_task, international_task)
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page if all_news else 0
            
            # If no news and cache is large, suggest clearing cache
            if len(global_seen_articles) > 200:
                await ctx.send(f"❌ Không có tin tức ở trang {page}! Cache có thể đầy. Dùng `!clear` để xóa cache hoặc `!debug` để kiểm tra.")
            else:
                await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Prepare fields data
        fields_data = []
        
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        # Enhanced source mapping for FREE sources only
        source_names = {
            # CafeF sources
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN',
            
            # FREE international sources
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_rss': 'Yahoo Finance', 'cnn_money': 'CNN Money', 
            'reuters_topnews': 'Reuters', 'reuters_business': 'Reuters Biz',
            'marketwatch': 'MarketWatch', 'business_insider': 'Business Insider',
            'cnbc': 'CNBC', 'investing_com': 'Investing.com', 
            'investopedia': 'Investopedia', 'economic_times': 'Economic Times',
            'bbc_business': 'BBC Business', 'guardian_business': 'The Guardian',
            'coindesk': 'CoinDesk', 'nasdaq_news': 'Nasdaq',
            'seeking_alpha': 'Seeking Alpha', 'benzinga': 'Benzinga'
        }
        
        emoji_map = {
            # CafeF sources
            'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 
            'cafef_vimo': '📊', 'cafef_doanhnghiep': '🏭',
            
            # FREE international sources - FIXED mapping
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_rss': '💼',
            'cnn_money': '📺', 'marketwatch': '📊', 'business_insider': '💼', 
            'cnbc': '📺', 'investing_com': '💹', 'investopedia': '📚',
            'bbc_business': '🇬🇧', 'guardian_business': '🛡️', 'coindesk': '₿',
            'nasdaq_news': '📈', 'seeking_alpha': '🔍', 'benzinga': '🚀'
        }
        
        # Statistics
        stats_field = f"🇻🇳 {domestic_count} • 🌍 {international_count} • 📊 {len(all_news)}"
        fields_data.append(("📊", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"📰 Trang {page}",
            "",
            fields_data,
            0x00ff88
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        
        # Save current page context for !chitiet (for both cached and fresh data)
        save_user_page_context(user_id, page_news, page)
        
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"{page}/{total_pages}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_enhanced(ctx, page=1):
    """Tin tức quốc tế - CONSISTENT PAGINATION"""
    try:
        page = max(1, int(page))
        user_id = ctx.author.id
        
        # Check cached news first
        cached_news, is_cached = get_or_collect_user_news(user_id, "out", RSS_FEEDS['international'])
        
        if is_cached:
            news_list = cached_news
        else:
            loading_msg = await ctx.send(f"⏳")
            
            news_list = await collect_news_enhanced(RSS_FEEDS['international'], 20, use_global_dedup=False)
            
            # Cache for consistent pagination
            save_user_news_enhanced(user_id, news_list, "out")
            
            await loading_msg.delete()
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page if news_list else 0
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Prepare fields data
        fields_data = []
        
        stats_field = f"🌍 {len(news_list)} tin"
        if is_cached:
            stats_field += " (cached)"
        fields_data.append(("📊", stats_field))
        
        # FREE source names only - FIXED
        source_names = {
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'yahoo_finance_rss': 'Yahoo Finance', 'cnn_money': 'CNN Money', 
            'marketwatch': 'MarketWatch', 'business_insider': 'Business Insider',
            'cnbc': 'CNBC', 'investing_com': 'Investing.com', 
            'investopedia': 'Investopedia', 'bbc_business': 'BBC Business', 
            'guardian_business': 'The Guardian', 'coindesk': 'CoinDesk', 
            'nasdaq_news': 'Nasdaq', 'seeking_alpha': 'Seeking Alpha', 'benzinga': 'Benzinga'
        }
        
        emoji_map = {
            'yahoo_finance_main': '💼', 'yahoo_finance_headlines': '📰', 'yahoo_finance_rss': '💼',
            'cnn_money': '📺', 'marketwatch': '📊', 'business_insider': '💼', 
            'cnbc': '📺', 'investing_com': '💹', 'investopedia': '📚',
            'bbc_business': '🇬🇧', 'guardian_business': '🛡️', 'coindesk': '₿',
            'nasdaq_news': '📈', 'seeking_alpha': '🔍', 'benzinga': '🚀'
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
            f"🌍 Trang {page}",
            "",
            fields_data,
            0x0066ff
        )
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        
        # Save current page context (for both cached and fresh data)
        save_user_page_context(user_id, page_news, page)
        
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"{page}/{total_pages}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] • FREE ONLY")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_enhanced(ctx, page=1):
    """Tin tức trong nước - CafeF"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['domestic'], 15)
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
        
        stats_field = f"🇻🇳 {len(news_list)} tin"
        fields_data.append(("📊", stats_field))
        
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
            f"🇻🇳 Trang {page}",
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
    """Chi tiết bài viết - Async extraction"""
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
        
        # Source names mapping - FIXED
        source_names = {
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN',
            'yahoo_finance_main': 'Yahoo RSS', 'yahoo_finance_headlines': 'Yahoo Headlines',
            'marketwatch': 'MarketWatch', 'cnn_money': 'CNN Money',
            'cnbc': 'CNBC', 'bbc_business': 'BBC Business', 'investing_com': 'Investing.com'
        }
        
        source_name = source_names.get(news['source'], news['source'])
        
        if is_international_source(news['source']):
            loading_msg = await ctx.send(f"⏳ Gemini...")
        else:
            loading_msg = await ctx.send(f"⏳ Loading...")
        
        # Enhanced async content extraction
        full_content = await extract_content_enhanced(news['link'], news['source'], news)
        
        await loading_msg.delete()
        
        # Create content with metadata
        main_title = f"📖 Tin {news_number}"
        
        content_with_meta = f"**{news['title']}**\n"
        content_with_meta += f"🕰️ {news['published_str']} • 📰 {source_name}\n\n"
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
            optimized_embeds[-1].set_footer(text=f"#{news_number}")
        
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

@bot.command(name='debate')
async def gemini_debate_system(ctx, *, topic=""):
    """Tranh luận đa góc nhìn"""
    try:
        if not gemini_engine.available:
            await ctx.send("❌ Gemini AI không khả dụng.")
            return
        
        if not topic:
            user_id = ctx.author.id
            if user_id in user_last_detail_cache:
                last_detail = user_last_detail_cache[user_id]
                time_diff = get_current_vietnam_datetime() - last_detail['timestamp']
                
                if time_diff.total_seconds() < 1800:
                    article = last_detail['article']
                    topic = f"Bài báo: {article['title']}"
                else:
                    await ctx.send("❌ Nhập chủ đề hoặc xem bài báo trước.")
                    return
            else:
                await ctx.send("❌ Nhập chủ đề! Ví dụ: `!debate lạm phát`")
                return
        
        loading_msg = await ctx.send(f"⏳")
        
        debate_result = await gemini_engine.debate_perspectives(topic)
        
        optimized_embeds = create_optimized_embeds(f"🎭 Debate", debate_result, 0xff6600)
        
        await loading_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
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
        
        # Check for recent !chitiet context
        user_id = ctx.author.id
        context = ""
        
        if user_id in user_last_detail_cache:
            last_detail = user_last_detail_cache[user_id]
            time_diff = get_current_vietnam_datetime() - last_detail['timestamp']
            
            if time_diff.total_seconds() < 1800:  # 30 minutes
                article = last_detail['article']
                
                # Extract content for context
                article_content = await extract_content_enhanced(article['link'], article['source'], article)
                
                if article_content:
                    context = f"BÀI BÁO LIÊN QUAN:\nTiêu đề: {article['title']}\nNguồn: {article['source']}\nNội dung: {article_content[:1500]}"
        
        progress_embed = create_safe_embed(
            "🤖 AI",
            f"⏳",
            0x9932cc
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get Gemini response
        if context:
            analysis_result = await gemini_engine.analyze_article(context, question)
        else:
            analysis_result = await gemini_engine.ask_question(question, context)
        
        # Create optimized embeds
        title = f"🤖 AI"
        optimized_embeds = create_optimized_embeds(title, analysis_result, 0x00ff88)
        
        if optimized_embeds:
            optimized_embeds[-1].set_footer(text=f"AI")
        
        # Send optimized embeds
        await progress_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Gemini: {str(e)}")

@bot.command(name='menu')
async def help_command_optimized(ctx):
    """Menu"""
    
    main_embed = create_safe_embed(
        "📰 Commands",
        "",
        0x00ff88
    )
    
    safe_name1, safe_value1 = validate_embed_field(
        "📰 News",
        "!all [page] - All\n!in [page] - Domestic\n!out [page] - International\n!chitiet [num] - Details"
    )
    main_embed.add_field(name=safe_name1, value=safe_value1, inline=False)
    
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI", 
        "!hoi [question] - Ask AI\n!debate [topic] - Debate"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=False)
    
    safe_name3, safe_value3 = validate_embed_field(
        "🔧 Debug",
        "!status - Status\n!debug - Cache info\n!clear - Clear cache\n!test_dup [title] - Test duplicate"
    )
    main_embed.add_field(name=safe_name3, value=safe_value3, inline=False)
    
    await ctx.send(embed=main_embed)

@bot.command(name='clear')
async def clear_cache_command(ctx):
    """Clear global cache"""
    global global_seen_articles
    cache_size = len(global_seen_articles)
    global_seen_articles.clear()
    await ctx.send(f"🧹 Cleared {cache_size} articles from cache")

@bot.command(name='debug')
async def debug_command(ctx):
    """Debug cache status and duplicate logic"""
    global global_seen_articles
    
    cache_size = len(global_seen_articles)
    current_time = get_current_vietnam_datetime()
    
    # Count recent vs old articles
    recent_count = 0
    old_count = 0
    
    for article_data in global_seen_articles.values():
        time_diff = current_time - article_data['timestamp']
        if time_diff.total_seconds() < (CACHE_EXPIRE_HOURS * 3600):
            recent_count += 1
        else:
            old_count += 1
    
    # Show sample of cached titles
    sample_titles = []
    for i, (key, data) in enumerate(list(global_seen_articles.items())[:3]):
        normalized = normalize_title(data['title'])
        sample_titles.append(f"• {normalized[:40]}...")
        if i >= 2:  # Only show first 3
            break
    
    embed = create_safe_embed(
        "🔧 Debug Info",
        f"**Cache:** {cache_size} articles\n**Recent:** {recent_count}\n**Old:** {old_count}\n\n**Duplicate Logic:** EXACT title match only\n\n**Sample cached titles:**\n" + "\n".join(sample_titles),
        0xff9900
    )
    
    await ctx.send(embed=embed)

@bot.command(name='test_dup')
async def test_duplicate_logic(ctx, *, test_title=""):
    """Test duplicate detection with a title"""
    if not test_title:
        await ctx.send("❌ Nhập tiêu đề để test! Ví dụ: `!test_dup Bitcoin tăng giá mạnh`")
        return
    
    normalized = normalize_title(test_title)
    
    # Check against cache
    is_duplicate = False
    matching_title = ""
    
    for article_data in global_seen_articles.values():
        existing_normalized = normalize_title(article_data['title'])
        if normalized == existing_normalized:
            is_duplicate = True
            matching_title = article_data['title']
            break
    
    embed = create_safe_embed(
        "🧪 Duplicate Test",
        f"**Input:** {test_title}\n**Normalized:** {normalized}\n\n**Result:** {'🔴 DUPLICATE' if is_duplicate else '✅ UNIQUE'}" + 
        (f"\n**Matches:** {matching_title}" if is_duplicate else ""),
        0xff0000 if is_duplicate else 0x00ff00
    )
    
    await ctx.send(embed=embed)

@bot.command(name='status')
async def status_command(ctx):
    """Status"""
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    global_cache_size = len(global_seen_articles)
    
    main_embed = create_safe_embed(
        "📊 Status",
        "",
        0x00ff88
    )
    
    safe_name1, safe_value1 = validate_embed_field(
        "📰 Sources",
        f"🇻🇳 {len(RSS_FEEDS['domestic'])}\n🌍 {len(RSS_FEEDS['international'])}\n📊 {total_sources} total"
    )
    main_embed.add_field(name=safe_name1, value=safe_value1, inline=True)
    
    gemini_status = "✅" if gemini_engine.available else "❌"
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI",
        f"Gemini: {gemini_status}\nCache: {global_cache_size}"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=True)
    
    await ctx.send(embed=main_embed)

# Run the bot
if __name__ == "__main__":
    try:
        keep_alive()
        print("🌐 Keep-alive server started")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        
        print("🚀 Enhanced News Bot...")
        print(f"🔧 FREE Sources: {total_sources}")
        print(f"🤖 Gemini: {'✅' if gemini_engine.available else '❌'}")
        print("✅ Fixed: Heartbeat, Paywall, Content")
        print("🎯 Duplicate: EXACT title match only")
        print("=" * 30)
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ STARTUP ERROR: {e}")
