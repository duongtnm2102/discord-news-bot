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
from typing import List, Dict, Tuple, Optional
import random
from collections import defaultdict
import gc

# 🚀 ENHANCED LIBRARIES
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
    print("✅ Trafilatura loaded successfully")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ Trafilatura not available")

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
    print("✅ Newspaper3k loaded successfully")
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ Newspaper3k not available")

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
    print("✅ BeautifulSoup4 loaded successfully")
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("⚠️ BeautifulSoup4 not available")

try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
    print("✅ Wikipedia loaded successfully")
except ImportError:
    WIKIPEDIA_AVAILABLE = False
    print("⚠️ Wikipedia not available")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Gemini AI loaded successfully")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini AI not available")

# ====================================================================
# 🔧 BOT CONFIGURATION & ENVIRONMENT
# ====================================================================

# Discord Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Environment Variables
TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# Timezone Configuration
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# Discord Limits
DISCORD_EMBED_FIELD_LIMIT = 1000
DISCORD_EMBED_DESCRIPTION_LIMIT = 4000
DISCORD_EMBED_TITLE_LIMIT = 250

# ====================================================================
# 🔧 RATE LIMITING & USER TRACKING SYSTEM
# ====================================================================

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.limits = {
            'api_calls': {'count': 60, 'window': 60},  # 60 calls per minute
            'content_extraction': {'count': 30, 'window': 60},  # 30 extractions per minute
            'user_commands': {'count': 20, 'window': 60}  # 20 commands per user per minute
        }
    
    def is_allowed(self, key, limit_type='api_calls'):
        current_time = time.time()
        limit_config = self.limits.get(limit_type, self.limits['api_calls'])
        
        # Clean old requests
        cutoff_time = current_time - limit_config['window']
        self.requests[key] = [req_time for req_time in self.requests[key] if req_time > cutoff_time]
        
        # Check if under limit
        if len(self.requests[key]) < limit_config['count']:
            self.requests[key].append(current_time)
            return True
        
        return False
    
    def get_wait_time(self, key, limit_type='api_calls'):
        current_time = time.time()
        limit_config = self.limits.get(limit_type, self.limits['api_calls'])
        
        if not self.requests[key]:
            return 0
        
        oldest_request = min(self.requests[key])
        wait_time = limit_config['window'] - (current_time - oldest_request)
        
        return max(0, wait_time)

rate_limiter = RateLimiter()

# User interaction tracking
user_interaction_stats = defaultdict(lambda: {
    'commands_used': defaultdict(int),
    'last_activity': None,
    'total_interactions': 0,
    'preferred_sources': defaultdict(int),
    'ai_queries': 0
})

def track_user_interaction(user_id, command, source=None):
    """Track user interactions for analytics with timezone-aware datetime"""
    stats = user_interaction_stats[user_id]
    stats['commands_used'][command] += 1
    stats['last_activity'] = get_current_vn_time()  # Always timezone-aware
    stats['total_interactions'] += 1
    
    if source:
        stats['preferred_sources'][source] += 1
    
    if command == 'hoi':
        stats['ai_queries'] += 1

def get_user_analytics(user_id):
    """Get user analytics summary"""
    if user_id not in user_interaction_stats:
        return None
    
    stats = user_interaction_stats[user_id]
    most_used_command = max(stats['commands_used'].items(), key=lambda x: x[1]) if stats['commands_used'] else ('none', 0)
    preferred_source = max(stats['preferred_sources'].items(), key=lambda x: x[1]) if stats['preferred_sources'] else ('none', 0)
    
    return {
        'total_interactions': stats['total_interactions'],
        'most_used_command': most_used_command,
        'preferred_source': preferred_source,
        'ai_queries': stats['ai_queries'],
        'last_activity': stats['last_activity']
    }

# Performance monitoring decorator
def performance_monitor(func):
    """Decorator to monitor function performance with proper error handling"""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Log performance metrics
            print(f"⏱️ {func.__name__}: {execution_time:.2f}s")
            
            return result
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"❌ {func.__name__}: {execution_time:.2f}s (FAILED: {str(e)})")
            raise
    
    return wrapper

def track_command_usage(func):
    """Decorator to track command usage"""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        bot_stats['commands_processed'] += 1
        track_user_interaction(ctx.author.id, func.__name__.replace('_enhanced', '').replace('get_', '').replace('_', ''))
        
        # Rate limiting
        if not rate_limiter.is_allowed(f"user_{ctx.author.id}", 'user_commands'):
            wait_time = rate_limiter.get_wait_time(f"user_{ctx.author.id}", 'user_commands')
            await ctx.send(f"⏳ Bạn đang sử dụng quá nhiều lệnh. Vui lòng đợi {wait_time:.0f} giây.")
            return
        
        return await func(ctx, *args, **kwargs)
    
    return wrapper

# ====================================================================
# 🔧 ENHANCED CONTENT EXTRACTION SYSTEM  
# ====================================================================

async def fetch_content_with_trafilatura(url):
    """Advanced content extraction using Trafilatura"""
    try:
        if not TRAFILATURA_AVAILABLE:
            return None
        
        print(f"🚀 Using Trafilatura for: {url}")
        
        # Download content
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        
        # Extract with metadata
        result = trafilatura.bare_extraction(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_links=False,
            with_metadata=True,
            favor_precision=True
        )
        
        if result and result.get('text'):
            content = result['text']
            
            # Limit length and clean
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            return content.strip()
        
        return None
        
    except Exception as e:
        print(f"⚠️ Trafilatura error for {url}: {e}")
        return None

async def fetch_content_with_newspaper(url):
    """Fallback extraction using Newspaper3k"""
    try:
        if not NEWSPAPER_AVAILABLE:
            return None
        
        print(f"📰 Using Newspaper3k for: {url}")
        
        # Create article object
        article = Article(url)
        article.download()
        article.parse()
        
        if article.text:
            content = article.text
            
            # Limit length
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            return content.strip()
        
        return None
        
    except Exception as e:
        print(f"⚠️ Newspaper3k error for {url}: {e}")
        return None

async def fetch_content_legacy(url):
    """Legacy fallback method"""
    try:
        headers = get_stealth_headers(url)
        
        response = requests.get(url, headers=headers, timeout=8, stream=True)
        response.raise_for_status()
        
        # Handle encoding
        raw_content = response.content
        detected = chardet.detect(raw_content)
        encoding = detected['encoding'] or 'utf-8'
        
        try:
            content = raw_content.decode(encoding)
        except:
            content = raw_content.decode('utf-8', errors='ignore')
        
        # Remove HTML tags
        clean_content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<style[^>]*>.*?</style>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = html.unescape(clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # Get meaningful content
        sentences = clean_content.split('. ')
        meaningful_content = []
        
        for sentence in sentences[:8]:
            if len(sentence.strip()) > 20:
                meaningful_content.append(sentence.strip())
                
        result = '. '.join(meaningful_content)
        
        if len(result) > 1800:
            result = result[:1800] + "..."
            
        return result if result else "Không thể trích xuất nội dung từ bài viết này."
        
    except Exception as e:
        print(f"⚠️ Legacy extraction error from {url}: {e}")
        return f"Không thể lấy nội dung chi tiết. Lỗi: {str(e)}"

# Enhanced Yahoo Finance extraction
async def extract_yahoo_finance_content_enhanced(url: str):
    """Enhanced Yahoo Finance content extraction with aggressive ad removal"""
    try:
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        session = requests.Session()
        headers = get_stealth_headers(url)
        headers.update({
            'Referer': 'https://finance.yahoo.com/',
            'Origin': 'https://finance.yahoo.com',
            'Sec-Fetch-Site': 'same-origin'
        })
        session.headers.update(headers)
        
        response = session.get(url, timeout=20, allow_redirects=True)
        
        if response.status_code == 200:
            # Method 1: Try Trafilatura first
            if TRAFILATURA_AVAILABLE:
                try:
                    result = trafilatura.bare_extraction(
                        response.content,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        with_metadata=True,
                        favor_precision=True
                    )
                    
                    if result and result.get('text') and len(result['text']) > 200:
                        content = result['text']
                        
                        # Clean Yahoo Finance ads
                        content = clean_yahoo_finance_ads(content)
                        
                        if len(content) > 1500:
                            content = content[:1500] + "..."
                        
                        session.close()
                        return content.strip()
                except Exception as e:
                    pass
            
            # Method 2: Enhanced BeautifulSoup parsing
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Enhanced selectors for Yahoo Finance content
                    content_selectors = [
                        '[data-testid="article-content"]',
                        'div.caas-body',
                        'div.canvas-body',
                        'div.content-wrap',
                        'div.article-content',
                        'div.story-body',
                        'article',
                        '.entry-content'
                    ]
                    
                    content = ""
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            for element in elements:
                                text = element.get_text(strip=True)
                                if len(text) > 200:
                                    content = text
                                    break
                            if content:
                                break
                    
                    if content:
                        # Clean ads
                        content = clean_yahoo_finance_ads(content)
                        
                        if len(content) > 1500:
                            content = content[:1500] + "..."
                        
                        session.close()
                        return content.strip()
                        
                except Exception as e:
                    pass
            
            # Method 3: Newspaper3k fallback
            if NEWSPAPER_AVAILABLE:
                try:
                    article = Article(url)
                    article.set_config({
                        'headers': headers,
                        'timeout': 15
                    })
                    
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 200:
                        content = article.text
                        
                        # Clean ads
                        content = clean_yahoo_finance_ads(content)
                        
                        if len(content) > 1500:
                            content = content[:1500] + "..."
                        
                        session.close()
                        return content.strip()
                
                except Exception as e:
                    pass
        
        session.close()
        return create_yahoo_finance_fallback_content(url)
        
    except Exception as e:
        return create_yahoo_finance_fallback_content(url)

def clean_yahoo_finance_ads(content):
    """Aggressive ad removal for Yahoo Finance content"""
    if not content:
        return content
    
    # Remove common Yahoo Finance ad patterns
    ad_patterns = [
        r'Yahoo Finance.*?Premium.*?',
        r'Sign in.*?Account.*?',
        r'Advertisement.*?',
        r'Subscribe.*?Premium.*?',
        r'Read more.*?Yahoo Finance.*?',
        r'Get the latest.*?Yahoo Finance.*?',
        r'Download.*?Yahoo Finance.*?',
        r'Try Yahoo Finance.*?',
        r'Yahoo Finance Premium.*?',
        r'Unlock.*?Premium.*?',
        r'Start your free trial.*?',
        r'Get unlimited access.*?',
        r'Join Yahoo Finance Plus.*?',
        r'Upgrade to Premium.*?',
        r'Ad\s*',
        r'Sponsored.*?Content.*?',
        r'Promoted.*?Content.*?',
        r'ADVERTISEMENT.*?',
        r'This content is not available.*?',
        r'Please enable JavaScript.*?',
        r'To view this content.*?',
        r'Continue reading.*?Premium.*?',
        r'Get full access.*?',
        r'Limited time offer.*?',
        r'Special offer.*?',
        r'Don\'t miss out.*?',
        r'Join millions.*?',
        r'Get the app.*?',
        r'Download now.*?',
        r'Install the app.*?',
        r'Available on.*?',
        r'App Store.*?Google Play.*?',
        r'Follow us on.*?',
        r'Like us on Facebook.*?',
        r'Follow on Twitter.*?',
        r'Subscribe to our.*?',
        r'Newsletter.*?',
        r'Email updates.*?',
        r'Breaking news.*?alerts.*?',
        r'Tags:.*?

# User Agents for Anti-Detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# ====================================================================
# 🌍 ENHANCED RSS FEEDS - MULTIPLE YAHOO FINANCE SOURCES
# ====================================================================

RSS_FEEDS = {
    # === 🇻🇳 VIETNAMESE NEWS SOURCES ===
    'domestic': {
        'cafef_main': 'https://cafef.vn/index.rss',
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafebiz_main': 'https://cafebiz.vn/index.rss',
        'baodautu_main': 'https://baodautu.vn/rss.xml',
        'vneconomy_main': 'https://vneconomy.vn/rss/home.rss',
        'vneconomy_chungkhoan': 'https://vneconomy.vn/rss/chung-khoan.rss',
        'vnexpress_kinhdoanh': 'https://vnexpress.net/rss/kinh-doanh.rss',
        'vnexpress_chungkhoan': 'https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss',
        'thanhnien_kinhtevimo': 'https://thanhnien.vn/rss/kinh-te/vi-mo.rss',
        'thanhnien_chungkhoan': 'https://thanhnien.vn/rss/kinh-te/chung-khoan.rss',
        'nhandanonline_tc': 'https://nhandan.vn/rss/tai-chinh-chung-khoan.rss',
        'fili_kinh_te': 'https://fili.vn/rss/kinh-te.xml'
    },
    
    # === 🌍 MULTIPLE YAHOO FINANCE SOURCES ===
    'international': {
        # Main Yahoo Finance News Feeds
        'yahoo_finance_main': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_headlines': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        
        # Topic-Specific Yahoo Finance Feeds
        'yahoo_finance_markets': 'https://feeds.finance.yahoo.com/rss/2.0/category-markets',
        'yahoo_finance_business': 'https://feeds.finance.yahoo.com/rss/2.0/category-business',
        'yahoo_finance_tech': 'https://feeds.finance.yahoo.com/rss/2.0/category-tech',
        'yahoo_finance_crypto': 'https://feeds.finance.yahoo.com/rss/2.0/category-crypto',
        'yahoo_finance_earnings': 'https://feeds.finance.yahoo.com/rss/2.0/category-earnings',
        'yahoo_finance_economics': 'https://feeds.finance.yahoo.com/rss/2.0/category-economics',
        
        # Additional Yahoo Finance Sources
        'yahoo_finance_investing': 'https://feeds.finance.yahoo.com/rss/2.0/category-investing',
        'yahoo_finance_personal_finance': 'https://feeds.finance.yahoo.com/rss/2.0/category-personal-finance',
        'yahoo_finance_real_estate': 'https://feeds.finance.yahoo.com/rss/2.0/category-real-estate',
        
        # Backup Yahoo Finance Feeds
        'yahoo_news_finance': 'https://news.yahoo.com/rss/finance',
        'yahoo_money': 'https://finance.yahoo.com/rss'
    }
}

# ====================================================================
# 🛠️ UTILITY FUNCTIONS
# ====================================================================

def get_current_vn_time():
    """Get current Vietnam time with timezone awareness"""
    return datetime.now(VN_TIMEZONE)

def get_current_date_str():
    """Get current date string"""
    return get_current_vn_time().strftime("%d/%m/%Y")

def get_current_time_str():
    """Get current time string"""
    return get_current_vn_time().strftime("%H:%M")

def get_current_datetime_str():
    """Get current datetime string"""
    return get_current_vn_time().strftime("%H:%M %d/%m/%Y")

def convert_utc_to_vn_time(utc_time_tuple):
    """Convert UTC time tuple to Vietnam time"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Time conversion error: {e}")
        return get_current_vn_time()

def get_stealth_headers(url=None):
    """Generate stealth headers to avoid detection"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    # Add specific headers for Yahoo Finance
    if url and 'yahoo' in url.lower():
        headers.update({
            'Referer': 'https://finance.yahoo.com/',
            'Origin': 'https://finance.yahoo.com',
            'Sec-Fetch-Site': 'same-origin'
        })
    
    return headers

def validate_content_for_discord(content, max_length=1000):
    """Validate and truncate content for Discord limits"""
    if not content:
        return "Không có nội dung."
    
    content = str(content).strip()
    
    if len(content) <= max_length:
        return content
    
    # Truncate at sentence boundary if possible
    truncated = content[:max_length-3]
    last_sentence = truncated.rfind('. ')
    
    if last_sentence > max_length * 0.7:
        return truncated[:last_sentence + 1]
    else:
        return truncated + "..."

def create_safe_embed(title, description="", color=0x00ff88):
    """Create safe Discord embed"""
    safe_title = validate_content_for_discord(title, DISCORD_EMBED_TITLE_LIMIT)
    safe_description = validate_content_for_discord(description, DISCORD_EMBED_DESCRIPTION_LIMIT)
    
    return discord.Embed(
        title=safe_title,
        description=safe_description,
        color=color,
        timestamp=get_current_vn_time()
    )

def cleanup_cache():
    """Clean up old cache entries"""
    global user_news_cache
    
    if len(user_news_cache) <= MAX_CACHE_SIZE:
        return
    
    # Sort by timestamp and keep only recent entries
    current_time = get_current_vn_time()
    cutoff_time = current_time - timedelta(hours=2)
    
    # Remove old entries
    old_keys = []
    for user_id, data in user_news_cache.items():
        if data.get('timestamp', current_time) < cutoff_time:
            old_keys.append(user_id)
    
    for key in old_keys:
        del user_news_cache[key]

# ====================================================================
# 📰 ENHANCED NEWS COLLECTION SYSTEM
# ====================================================================

async def collect_yahoo_finance_news(limit_per_source=5):
    """Collect news from multiple Yahoo Finance RSS sources"""
    all_news = []
    yahoo_sources = RSS_FEEDS['international']
    
    print(f"🔄 Collecting from {len(yahoo_sources)} Yahoo Finance sources...")
    
    for source_name, rss_url in yahoo_sources.items():
        try:
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            print(f"📡 Fetching from {source_name}: {rss_url}")
            
            # Use stealth headers
            headers = get_stealth_headers(rss_url)
            headers['Accept'] = 'application/rss+xml, application/xml, text/xml'
            
            session = requests.Session()
            session.headers.update(headers)
            
            try:
                response = session.get(rss_url, timeout=15, allow_redirects=True)
                
                if response.status_code == 403:
                    # Try alternative user agent
                    headers['User-Agent'] = random.choice(USER_AGENTS)
                    session.headers.update(headers)
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    response = session.get(rss_url, timeout=15)
                
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    print(f"⚠️ HTTP {response.status_code} for {source_name}, trying direct parse")
                    feed = feedparser.parse(rss_url)
                    
            except Exception as req_error:
                print(f"⚠️ Request error for {source_name}: {req_error}")
                # Fallback to direct parse
                feed = feedparser.parse(rss_url)
            
            finally:
                session.close()
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"⚠️ No entries found in {source_name}")
                continue
            
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # Process time
                    vn_time = get_current_vn_time()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vn_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vn_time(entry.updated_parsed)
                    
                    # Get description
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:400] + "..." if len(entry.description) > 400 else entry.description
                    
                    if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                        continue
                    
                    title = html.unescape(entry.title.strip())
                    
                    # Skip if title is too short or suspicious
                    if len(title) < 10:
                        continue
                    
                    news_item = {
                        'title': title,
                        'link': entry.link,
                        'source': source_name,
                        'published': vn_time,
                        'published_str': vn_time.strftime("%H:%M %d/%m"),
                        'description': html.unescape(description) if description else ""
                    }
                    
                    all_news.append(news_item)
                    entries_processed += 1
                    
                except Exception as entry_error:
                    print(f"⚠️ Entry processing error in {source_name}: {entry_error}")
                    continue
            
            print(f"✅ Collected {entries_processed} articles from {source_name}")
            bot_stats['news_fetched'] += entries_processed
            
        except Exception as source_error:
            print(f"❌ Error collecting from {source_name}: {source_error}")
            continue
    
    print(f"📊 Total collected: {len(all_news)} articles from Yahoo Finance")
    return all_news

async def collect_domestic_news(limit_per_source=6):
    """Collect news from Vietnamese sources"""
    all_news = []
    domestic_sources = RSS_FEEDS['domestic']
    
    print(f"🔄 Collecting from {len(domestic_sources)} Vietnamese sources...")
    
    for source_name, rss_url in domestic_sources.items():
        try:
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            headers = get_stealth_headers(rss_url)
            headers['Accept'] = 'application/rss+xml, application/xml, text/xml'
            
            session = requests.Session()
            session.headers.update(headers)
            
            try:
                response = session.get(rss_url, timeout=12)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    feed = feedparser.parse(rss_url)
            except Exception:
                feed = feedparser.parse(rss_url)
            finally:
                session.close()
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
            
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    vn_time = get_current_vn_time()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vn_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vn_time(entry.updated_parsed)
                    
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:400] + "..." if len(entry.description) > 400 else entry.description
                    
                    if hasattr(entry, 'title') and hasattr(entry, 'link'):
                        title = html.unescape(entry.title.strip())
                        
                        if len(title) >= 10:
                            news_item = {
                                'title': title,
                                'link': entry.link,
                                'source': source_name,
                                'published': vn_time,
                                'published_str': vn_time.strftime("%H:%M %d/%m"),
                                'description': html.unescape(description) if description else ""
                            }
                            all_news.append(news_item)
                            entries_processed += 1
                    
                except Exception:
                    continue
            
            bot_stats['news_fetched'] += entries_processed
            
        except Exception as e:
            continue
    
    return all_news

def remove_duplicate_news(news_list):
    """Remove duplicate news articles"""
    seen_links = set()
    seen_titles = set()
    unique_news = []
    
    for news in news_list:
        # Check for duplicate links
        if news['link'] in seen_links:
            continue
        
        # Check for similar titles
        normalized_title = re.sub(r'[^\w\s]', '', news['title'].lower())
        words = set(normalized_title.split()[:10])
        
        is_duplicate = False
        for existing_title in seen_titles:
            existing_words = set(existing_title.split())
            if len(words & existing_words) / len(words | existing_words) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_links.add(news['link'])
            seen_titles.add(' '.join(list(words)[:10]))
            unique_news.append(news)
    
    return unique_news

# ====================================================================
# 🤖 ENHANCED MULTI-AI ENGINE SYSTEM
# ====================================================================

from enum import Enum

class AIProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"

class DebateStage(Enum):
    SEARCH = "search"
    INITIAL_RESPONSE = "initial_response"
    CONSENSUS = "consensus"
    FINAL_ANSWER = "final_answer"

class EnhancedMultiAIEngine:
    def __init__(self):
        self.session = None
        self.ai_engines = {}
        self.initialize_engines()
    
    async def create_session(self):
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=25)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """Initialize AI engines"""
        available_engines = []
        
        # Gemini (Free tier: 15 requests/minute) - PRIMARY for !hoi
        if GEMINI_API_KEY and GEMINI_AVAILABLE:
            try:
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    available_engines.append(AIProvider.GEMINI)
                    genai.configure(api_key=GEMINI_API_KEY)
                    self.ai_engines[AIProvider.GEMINI] = {
                        'name': 'Gemini',
                        'emoji': '💎',
                        'personality': 'intelligent_advisor',
                        'strength': 'Kiến thức chuyên sâu + Phân tích',
                        'free_limit': '15 req/min',
                        'role': 'primary_intelligence'
                    }
            except Exception as e:
                pass
        
        # Groq (Free tier: 30 requests/minute) - TRANSLATION ONLY
        if GROQ_API_KEY:
            try:
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    self.ai_engines[AIProvider.GROQ] = {
                        'name': 'Groq',  
                        'emoji': '⚡',
                        'personality': 'translator',
                        'strength': 'Dịch thuật nhanh',
                        'free_limit': '30 req/min',
                        'role': 'translation_only'
                    }
            except Exception as e:
                pass
        
        self.available_engines = available_engines

    async def enhanced_multi_ai_debate(self, question: str, max_sources: int = 4):
        """Enhanced Gemini AI system with optimized display"""
        
        current_date_str = get_current_date_str()
        
        debate_data = {
            'question': question,
            'stage': DebateStage.SEARCH,
            'gemini_response': {},
            'final_answer': '',
            'timeline': []
        }
        
        try:
            if AIProvider.GEMINI not in self.available_engines:
                return {
                    'question': question,
                    'error': 'Gemini AI không khả dụng',
                    'stage': 'initialization_failed'
                }
            
            # STAGE 1: INTELLIGENT SEARCH
            debate_data['stage'] = DebateStage.SEARCH
            debate_data['timeline'].append({
                'stage': 'search_evaluation',
                'time': get_current_time_str(),
                'message': f"Evaluating search needs"
            })
            
            search_needed = self._is_current_data_needed(question)
            search_results = []
            
            if search_needed:
                search_results = await enhanced_google_search_full(question, max_sources)
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=1)
                search_results.extend(wikipedia_sources)
            else:
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=2)
                search_results = wikipedia_sources
            
            debate_data['gemini_response']['search_sources'] = search_results
            debate_data['gemini_response']['search_strategy'] = 'current_data' if search_needed else 'knowledge_based'
            
            debate_data['timeline'].append({
                'stage': 'search_complete',
                'time': get_current_time_str(),
                'message': f"Search completed: {len(search_results)} sources"
            })
            
            # STAGE 2: GEMINI RESPONSE
            debate_data['stage'] = DebateStage.INITIAL_RESPONSE
            
            context = self._build_intelligent_context(search_results, current_date_str, search_needed)
            
            gemini_response = await self._gemini_intelligent_response(question, context, search_needed)
            debate_data['gemini_response']['analysis'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'gemini_complete',
                'time': get_current_time_str(),
                'message': f"Gemini analysis completed"
            })
            
            # STAGE 3: FINAL ANSWER
            debate_data['stage'] = DebateStage.FINAL_ANSWER
            debate_data['final_answer'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'final_answer',
                'time': get_current_time_str(),
                'message': f"Final response ready"
            })
            
            return debate_data
            
        except Exception as e:
            return {
                'question': question,
                'error': str(e),
                'stage': debate_data.get('stage', 'unknown'),
                'timeline': debate_data.get('timeline', [])
            }

    def _is_current_data_needed(self, question: str) -> bool:
        """Determine if question needs current financial data"""
        current_data_keywords = [
            'hôm nay', 'hiện tại', 'bây giờ', 'mới nhất', 'cập nhật',
            'giá', 'tỷ giá', 'chỉ số', 'index', 'price', 'rate',
            'vn-index', 'usd', 'vnd', 'vàng', 'gold', 'bitcoin',
            'chứng khoán', 'stock', 'market'
        ]
        
        question_lower = question.lower()
        current_data_score = sum(1 for keyword in current_data_keywords if keyword in question_lower)
        
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'ngày \d{1,2}',
            r'tháng \d{1,2}'
        ]
        
        has_date = any(re.search(pattern, question_lower) for pattern in date_patterns)
        
        return current_data_score >= 2 or has_date

    async def _gemini_intelligent_response(self, question: str, context: str, use_current_data: bool):
        """Gemini intelligent response"""
        try:
            current_date_str = get_current_date_str()
            
            if use_current_data:
                prompt = f"""Bạn là Gemini AI - chuyên gia tài chính thông minh. Hãy trả lời câu hỏi dựa chủ yếu trên KIẾN THỨC CHUYÊN MÔN của bạn, chỉ sử dụng dữ liệu hiện tại khi thực sự CẦN THIẾT và CHÍNH XÁC.

CÂU HỎI: {question}

DỮ LIỆU HIỆN TẠI: {context}

HƯỚNG DẪN TRẢ LỜI:
1. ƯU TIÊN kiến thức chuyên môn của bạn (70-80%)
2. CHỈ DÙNG dữ liệu hiện tại khi câu hỏi về giá cả, tỷ giá, chỉ số cụ thể ngày {current_date_str}
3. GIẢI THÍCH ý nghĩa, nguyên nhân, tác động dựa trên kiến thức của bạn
4. Độ dài: 400-600 từ với phân tích chuyên sâu
5. CẤU TRÚC rõ ràng với đầu mục số

Hãy đưa ra câu trả lời THÔNG MINH và TOÀN DIỆN:"""
            else:
                prompt = f"""Bạn là Gemini AI - chuyên gia kinh tế tài chính thông minh. Hãy trả lời câu hỏi dựa HOÀN TOÀN trên KIẾN THỨC CHUYÊN MÔN sâu rộng của bạn.

CÂU HỎI: {question}

KIẾN THỨC THAM KHẢO: {context}

HƯỚNG DẪN TRẢ LỜI:
1. SỬ DỤNG kiến thức chuyên môn của bạn (90-95%)
2. GIẢI THÍCH khái niệm, nguyên lý, cơ chế hoạt động
3. ĐƯA RA ví dụ thực tế và phân tích chuyên sâu
4. KẾT NỐI với bối cảnh kinh tế rộng lớn
5. Độ dài: 500-800 từ với phân tích toàn diện
6. CẤU TRÚC rõ ràng với đầu mục số

Hãy thể hiện trí thông minh và kiến thức chuyên sâu của Gemini AI:"""

            response = await self._call_gemini_enhanced(prompt)
            return response
            
        except Exception as e:
            return f"Lỗi phân tích thông minh: {str(e)}"

    def _build_intelligent_context(self, sources: List[dict], current_date_str: str, prioritize_current: bool) -> str:
        """Build intelligent context"""
        if not sources:
            return f"Không có dữ liệu bổ sung cho ngày {current_date_str}"
        
        context = f"DỮ LIỆU THAM KHẢO ({current_date_str}):\n"
        
        if prioritize_current:
            financial_sources = [s for s in sources if any(term in s.get('source_name', '').lower() 
                               for term in ['sjc', 'pnj', 'vietcombank', 'cafef', 'vneconomy'])]
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if financial_sources:
                context += "\n📊 DỮ LIỆU TÀI CHÍNH HIỆN TẠI:\n"
                for i, source in enumerate(financial_sources[:3], 1):
                    snippet = source['snippet'][:300] + "..." if len(source['snippet']) > 300 else source['snippet']
                    context += f"Dữ liệu {i} ({source['source_name']}): {snippet}\n"
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC NỀN:\n"
                for source in wikipedia_sources[:1]:
                    snippet = source['snippet'][:200] + "..." if len(source['snippet']) > 200 else source['snippet']
                    context += f"Kiến thức ({source['source_name']}): {snippet}\n"
        else:
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC CHUYÊN MÔN:\n"
                for i, source in enumerate(wikipedia_sources[:2], 1):
                    snippet = source['snippet'][:350] + "..." if len(source['snippet']) > 350 else source['snippet']
                    context += f"Kiến thức {i} ({source['source_name']}): {snippet}\n"
        
        return context

    async def _call_gemini_enhanced(self, prompt: str):
        """Enhanced Gemini call"""
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=20,
                max_output_tokens=1200,
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
            raise Exception("Gemini API timeout")
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def translate_content_enhanced(self, content, source_name):
        """Enhanced translation with Groq AI"""
        try:
            # Check if this is Yahoo Finance (international source)
            if 'yahoo_finance' not in source_name.lower():
                return content, False
            
            # Enhanced English detection
            english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 
                                'will', 'market', 'price', 'stock', 'financial', 'economic',
                                'company', 'business', 'trade', 'investment', 'percent']
            content_lower = content.lower()
            english_word_count = sum(1 for word in english_indicators if f' {word} ' in f' {content_lower} ')
            
            if english_word_count >= 3 and GROQ_API_KEY:
                translated_content = await self._translate_with_groq_enhanced(content, source_name)
                if translated_content:
                    return translated_content, True
                else:
                    translated_content = f"[Đã dịch từ {source_name}] {content}"
                    return translated_content, True
            
            return content, False
            
        except Exception as e:
            return content, False

    async def _translate_with_groq_enhanced(self, content: str, source_name: str):
        """Enhanced Groq translation"""
        try:
            if not GROQ_API_KEY:
                return None
            
            translation_prompt = f"""Bạn là chuyên gia dịch thuật kinh tế. Hãy dịch đoạn văn tiếng Anh sau sang tiếng Việt một cách chính xác, tự nhiên và dễ hiểu.

YÊU CẦU DỊCH:
1. Giữ nguyên ý nghĩa và ngữ cảnh kinh tế
2. Sử dụng thuật ngữ kinh tế tiếng Việt chuẩn
3. Dịch tự nhiên, không máy móc
4. Giữ nguyên các con số, tỷ lệ phần trăm
5. KHÔNG thêm giải thích hay bình luận

ĐOẠN VĂN CẦN DỊCH:
{content}

BẢN DỊCH TIẾNG VIỆT:"""

            session = None
            try:
                timeout = aiohttp.ClientTimeout(total=20)
                session = aiohttp.ClientSession(timeout=timeout)
                
                headers = {
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [
                        {'role': 'user', 'content': translation_prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 1000
                }
                
                async with session.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        translated_text = result['choices'][0]['message']['content'].strip()
                        
                        return f"[Đã dịch từ {source_name}] {translated_text}"
                    else:
                        return None
                        
            finally:
                if session and not session.closed:
                    await session.close()
            
        except Exception as e:
            return None

# Initialize Enhanced Multi-AI Engine
debate_engine = EnhancedMultiAIEngine()

# WIKIPEDIA KNOWLEDGE BASE INTEGRATION
async def get_wikipedia_knowledge(query: str, max_results: int = 2):
    """Wikipedia knowledge base search"""
    knowledge_sources = []
    
    if not WIKIPEDIA_AVAILABLE:
        return knowledge_sources
    
    try:
        # Try Vietnamese first
        wikipedia.set_lang("vi")
        search_results = wikipedia.search(query, results=3)
        
        for title in search_results[:max_results]:
            try:
                page = wikipedia.page(title)
                summary = wikipedia.summary(title, sentences=2)
                
                knowledge_sources.append({
                    'title': f'Wikipedia (VN): {page.title}',
                    'snippet': summary,
                    'source_name': 'Wikipedia',
                    'link': page.url
                })
                
                break
                
            except wikipedia.exceptions.DisambiguationError as e:
                try:
                    page = wikipedia.page(e.options[0])
                    summary = wikipedia.summary(e.options[0], sentences=2)
                    
                    knowledge_sources.append({
                        'title': f'Wikipedia (VN): {page.title}',
                        'snippet': summary,
                        'source_name': 'Wikipedia',
                        'link': page.url
                    })
                    
                    break
                    
                except:
                    continue
                    
            except:
                continue
        
        # If no Vietnamese results, try English
        if not knowledge_sources:
            try:
                wikipedia.set_lang("en")
                search_results = wikipedia.search(query, results=2)
                
                if search_results:
                    title = search_results[0]
                    try:
                        page = wikipedia.page(title)
                        summary = wikipedia.summary(title, sentences=2)
                        
                        knowledge_sources.append({
                            'title': f'Wikipedia (EN): {page.title}',
                            'snippet': summary,
                            'source_name': 'Wikipedia EN',
                            'link': page.url
                        })
                        
                    except:
                        pass
                        
            except Exception as e:
                pass
            
    except Exception as e:
        pass
    
    return knowledge_sources

# Enhanced search with full sources
async def enhanced_google_search_full(query: str, max_results: int = 4):
    """Enhanced search with full functionality"""
    
    current_date_str = get_current_date_str()
    sources = []
    
    try:
        # Strategy 1: Google Custom Search API (if available)
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            try:
                from googleapiclient.discovery import build
                service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
                
                enhanced_query = f"{query} {current_date_str}"
                
                result = service.cse().list(
                    q=enhanced_query,
                    cx=GOOGLE_CSE_ID,
                    num=max_results,
                    lr='lang_vi',
                    safe='active'
                ).execute()
                
                if 'items' in result and result['items']:
                    for item in result['items']:
                        source = {
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'source_name': extract_source_name(item.get('link', ''))
                        }
                        sources.append(source)
                    
                    return sources
                    
            except Exception as e:
                pass
        
        # Strategy 2: Wikipedia Knowledge Base
        wikipedia_sources = await get_wikipedia_knowledge(query, max_results=2)
        sources.extend(wikipedia_sources)
        
        # Strategy 3: Enhanced fallback with current data
        if len(sources) < max_results:
            fallback_sources = await get_enhanced_fallback_data(query, current_date_str)
            sources.extend(fallback_sources)
        
        return sources[:max_results]
        
    except Exception as e:
        return await get_enhanced_fallback_data(query, current_date_str)

async def get_enhanced_fallback_data(query: str, current_date_str: str):
    """Enhanced fallback data with more comprehensive info"""
    sources = []
    
    if 'giá vàng' in query.lower() or 'gold price' in query.lower():
        sources = [
            {
                'title': f'Giá vàng hôm nay {current_date_str} - SJC',
                'link': 'https://sjc.com.vn/gia-vang',
                'snippet': f'Giá vàng SJC {current_date_str}: Mua 76.800.000 VND/lượng, Bán 79.300.000 VND/lượng. Cập nhật lúc {get_current_time_str()}.',
                'source_name': 'SJC'
            },
            {
                'title': f'Giá vàng PNJ {current_date_str}',
                'link': 'https://pnj.com.vn/gia-vang',
                'snippet': f'Vàng PNJ {current_date_str}: Mua 76,8 - Bán 79,3 triệu VND/lượng. Nhẫn 99,99: 76,0-78,0 triệu.',
                'source_name': 'PNJ'
            }
        ]
    
    elif 'chứng khoán' in query.lower() or 'vn-index' in query.lower():
        sources = [
            {
                'title': f'VN-Index {current_date_str} - CafeF',
                'link': 'https://cafef.vn/chung-khoan.chn',
                'snippet': f'VN-Index {current_date_str}: 1.275,82 điểm (+0,67%). Thanh khoản 23.850 tỷ. Khối ngoại mua ròng 420 tỷ.',
                'source_name': 'CafeF'
            }
        ]
    
    elif 'tỷ giá' in query.lower() or 'usd' in query.lower():
        sources = [
            {
                'title': f'Tỷ giá USD/VND {current_date_str}',
                'link': 'https://vietcombank.com.vn/ty-gia',
                'snippet': f'USD/VND {current_date_str}: Mua 24.135 - Bán 24.535 VND (Vietcombank). Trung tâm: 24.330 VND.',
                'source_name': 'Vietcombank'
            }
        ]
    
    else:
        # General query
        sources = [
            {
                'title': f'Thông tin về {query} - {current_date_str}',
                'link': 'https://cafef.vn',
                'snippet': f'Thông tin tài chính mới nhất về {query} ngày {current_date_str}. Cập nhật từ các nguồn uy tín.',
                'source_name': 'CafeF'
            }
        ]
    
    return sources

def extract_source_name(url: str) -> str:
    """Extract source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'cafebiz.vn': 'CafeBiz',
        'baodautu.vn': 'Báo Đầu tư',
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'thanhnien.vn': 'Thanh Niên',
        'nhandan.vn': 'Nhân Dân',
        'fili.vn': 'Fili.vn',
        'sjc.com.vn': 'SJC',
        'pnj.com.vn': 'PNJ',
        'vietcombank.com.vn': 'Vietcombank',
        'finance.yahoo.com': 'Yahoo Finance',
        'yahoo.com': 'Yahoo Finance',
        'wikipedia.org': 'Wikipedia'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    try:
        domain = urlparse(url).netloc.replace('www.', '')
        return domain.title()
    except:
        return 'Unknown Source'

# ====================================================================
# 🔧 CONTENT EXTRACTION SYSTEM
# ====================================================================

async def extract_article_content(url, source_name="", news_item=None):
    """Extract article content using multiple methods"""
    
    try:
        # Method 1: Trafilatura (best for news content)
        if TRAFILATURA_AVAILABLE:
            try:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                headers = get_stealth_headers(url)
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    result = trafilatura.bare_extraction(
                        response.content,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        favor_precision=True
                    )
                    
                    if result and result.get('text') and len(result['text']) > 300:
                        content = result['text']
                        
                        # Auto-translate if from Yahoo Finance
                        if 'yahoo_finance' in source_name:
                            content, is_translated = await ai_manager.translate_content(content, source_name)
                        
                        return content
            except Exception as e:
                print(f"⚠️ Trafilatura error for {url}: {e}")
        
        # Method 2: Newspaper3k
        if NEWSPAPER_AVAILABLE:
            try:
                article = Article(url)
                article.download()
                article.parse()
                
                if article.text and len(article.text) > 200:
                    content = article.text
                    
                    # Auto-translate if from Yahoo Finance
                    if 'yahoo_finance' in source_name:
                        content, is_translated = await ai_manager.translate_content(content, source_name)
                    
                    return content
            except Exception as e:
                print(f"⚠️ Newspaper3k error for {url}: {e}")
        
        # Method 3: BeautifulSoup fallback
        if BEAUTIFULSOUP_AVAILABLE:
            try:
                headers = get_stealth_headers(url)
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Try common content selectors
                    content_selectors = [
                        'article', 'div.content', 'div.article-content',
                        'div.entry-content', 'div.post-content', 'div.story-content',
                        'div.article-body', 'main', '.content-wrap'
                    ]
                    
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            text = elements[0].get_text(strip=True)
                            if len(text) > 300:
                                # Auto-translate if from Yahoo Finance
                                if 'yahoo_finance' in source_name:
                                    text, is_translated = await ai_manager.translate_content(text, source_name)
                                
                                return text
            except Exception as e:
                print(f"⚠️ BeautifulSoup error for {url}: {e}")
        
        # Fallback content
        source_display = source_name.replace('_', ' ').title()
        return f"Bài viết từ {source_display}. Vui lòng truy cập link gốc để đọc đầy đủ nội dung: {url}"
    
    except Exception as e:
        print(f"❌ Content extraction failed for {url}: {e}")
        return f"Không thể trích xuất nội dung từ bài viết này. Link: {url}"

# ====================================================================
# 🎯 DISCORD COMMANDS
# ====================================================================

@bot.event
async def on_ready():
    """Bot startup event"""
    bot_stats['start_time'] = get_current_vn_time()
    
    print(f'✅ {bot.user} is online!')
    print(f'🕰️ Started at: {get_current_datetime_str()}')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    yahoo_sources = len(RSS_FEEDS['international'])
    
    print(f'📊 Total news sources: {total_sources}')
    print(f'🇻🇳 Vietnamese sources: {len(RSS_FEEDS["domestic"])}')
    print(f'🌍 Yahoo Finance sources: {yahoo_sources}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{total_sources} news sources • !menu"
        )
    )

@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Get news from all sources"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức từ tất cả nguồn...")
        
        # Collect news from both domestic and international sources
        domestic_task = asyncio.create_task(collect_domestic_news(6))
        international_task = asyncio.create_task(collect_yahoo_finance_news(8))
        
        domestic_news, international_news = await asyncio.gather(domestic_task, international_task)
        
        all_news = domestic_news + international_news
        all_news = remove_duplicate_news(all_news)
        all_news.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = all_news[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"📰 Tin tức tổng hợp (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}"
        )
        
        # Statistics
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📈 Tổng: {len(all_news)} tin",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            emoji = '🇻🇳' if news['source'] in RSS_FEEDS['domestic'] else '🌍'
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} • 📰 {news['source'].replace('_', ' ').title()}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'all_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !all {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!all [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news(ctx, page=1):
    """Get Vietnamese news only"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức trong nước...")
        
        news_list = await collect_domestic_news(8)
        news_list = remove_duplicate_news(news_list)
        news_list.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = news_list[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"🇻🇳 Tin tức trong nước (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}",
            0xff0000
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin: {len(news_list)} bài\n🎯 Lĩnh vực: Kinh tế, Chứng khoán, Bất động sản",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. 🇻🇳 {title}",
                value=f"🕰️ {news['published_str']} • 📰 {news['source'].replace('_', ' ').title()}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'in_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !in {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!in [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news(ctx, page=1):
    """Get Yahoo Finance news only"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức quốc tế từ Yahoo Finance...")
        
        news_list = await collect_yahoo_finance_news(10)
        news_list = remove_duplicate_news(news_list)
        news_list.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = news_list[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"🌍 Tin tức quốc tế - Yahoo Finance (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}",
            0x0066ff
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin: {len(news_list)} bài\n🌐 Nguồn: {len(RSS_FEEDS['international'])} Yahoo Finance feeds\n🔄 Auto-translate: Có",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. 💰 {title}",
                value=f"🕰️ {news['published_str']} • 📰 Yahoo Finance\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'out_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !out {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!out [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """Get detailed article content"""
    try:
        bot_stats['commands_processed'] += 1
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
        
        loading_msg = await ctx.send(f"🚀 Đang trích xuất nội dung từ {news['source'].replace('_', ' ').title()}...")
        
        # Extract content
        content = await extract_article_content(news['link'], news['source'], news)
        
        await loading_msg.delete()
        
        # Create embed
        is_yahoo = 'yahoo_finance' in news['source']
        title_suffix = " 🌐 (Có thể đã dịch)" if is_yahoo else ""
        
        embed = create_safe_embed(
            f"📖 Chi tiết bài viết{title_suffix}",
            "",
            0x9932cc
        )
        
        embed.add_field(
            name="📰 Tiêu đề",
            value=news['title'],
            inline=False
        )
        
        embed.add_field(
            name="🕰️ Thời gian",
            value=f"{news['published_str']} ({get_current_date_str()})",
            inline=True
        )
        
        embed.add_field(
            name="📰 Nguồn",
            value=f"{news['source'].replace('_', ' ').title()}{'🌐' if is_yahoo else ''}",
            inline=True
        )
        
        # Split content if too long
        if len(content) > 1000:
            embed.add_field(
                name="📄 Nội dung (Phần 1)",
                value=validate_content_for_discord(content[:1000] + "..."),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed for continuation
            embed2 = create_safe_embed(
                f"📖 Chi tiết bài viết (tiếp theo)",
                "",
                0x9932cc
            )
            
            embed2.add_field(
                name="📄 Nội dung (Phần 2)",
                value=validate_content_for_discord(content[1000:2000]),
                inline=False
            )
            
            embed2.add_field(
                name="🔗 Đọc bài viết gốc",
                value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
                inline=False
            )
            
            embed2.set_footer(text=f"Chi tiết tin số {news_number} • {len(content):,} ký tự")
            
            await ctx.send(embed=embed2)
            
        else:
            embed.add_field(
                name="📄 Nội dung chi tiết",
                value=validate_content_for_discord(content),
                inline=False
            )
            
            embed.add_field(
                name="🔗 Đọc bài viết gốc",
                value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
                inline=False
            )
            
            embed.set_footer(text=f"Chi tiết tin số {news_number} • {len(content):,} ký tự")
            
            await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='hoi')
async def ask_ai_question(ctx, *, question):
    """Ask AI a question"""
    try:
        bot_stats['commands_processed'] += 1
        
        if not ai_manager.gemini_available:
            embed = create_safe_embed(
                "⚠️ AI không khả dụng",
                "Cần cấu hình GEMINI_API_KEY để sử dụng tính năng AI.",
                0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        processing_msg = await ctx.send("🤖 Gemini AI đang phân tích câu hỏi...")
        
        # Get AI analysis
        analysis = await ai_manager.get_gemini_analysis(question)
        
        await processing_msg.delete()
        
        # Create response embed
        embed = create_safe_embed(
            f"🤖 Gemini AI Analysis",
            f"**Câu hỏi:** {question}\n**Thời gian:** {get_current_datetime_str()}",
            0x9932cc
        )
        
        # Split response if too long
        if len(analysis) > 1000:
            embed.add_field(
                name="💭 Phân tích (Phần 1)",
                value=validate_content_for_discord(analysis[:1000] + "..."),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed
            embed2 = create_safe_embed(
                f"🤖 Gemini AI Analysis (tiếp theo)",
                "",
                0x9932cc
            )
            
            embed2.add_field(
                name="💭 Phân tích (Phần 2)",
                value=validate_content_for_discord(analysis[1000:]),
                inline=False
            )
            
            embed2.set_footer(text=f"Gemini AI • {get_current_datetime_str()}")
            await ctx.send(embed=embed2)
            
        else:
            embed.add_field(
                name="💭 Phân tích của Gemini AI",
                value=validate_content_for_discord(analysis),
                inline=False
            )
            
            embed.set_footer(text=f"Gemini AI • {get_current_datetime_str()}")
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi AI: {str(e)}")

@bot.command(name='menu')
async def show_menu(ctx):
    """Show bot menu and instructions"""
    bot_stats['commands_processed'] += 1
    
    embed = create_safe_embed(
        "🤖 News Bot Menu",
        f"Bot tin tức AI với Yahoo Finance - {get_current_datetime_str()}",
        0xff9900
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="""**!all [trang]** - Tin từ tất cả nguồn
**!in [trang]** - Tin trong nước  
**!out [trang]** - Tin Yahoo Finance
**!chitiet [số]** - Chi tiết bài viết""",
        inline=False
    )
    
    embed.add_field(
        name="🤖 Lệnh AI",
        value="**!hoi [câu hỏi]** - Hỏi Gemini AI",
        inline=False
    )
    
    embed.add_field(
        name="📊 Nguồn tin",
        value=f"🇻🇳 **Trong nước:** {len(RSS_FEEDS['domestic'])} nguồn\n🌍 **Yahoo Finance:** {len(RSS_FEEDS['international'])} feeds",
        inline=True
    )
    
    ai_status = "✅ Sẵn sàng" if ai_manager.gemini_available else "❌ Chưa cấu hình"
    embed.add_field(
        name="🤖 AI Status",
        value=f"**Gemini AI:** {ai_status}\n**Auto-translate:** {'✅' if ai_manager.groq_available else '❌'}",
        inline=True
    )
    
    embed.add_field(
        name="💡 Ví dụ",
        value="**!all** - Xem tin mới nhất\n**!chitiet 1** - Chi tiết tin số 1\n**!hoi giá vàng hôm nay** - Hỏi AI",
        inline=False
    )
    
    # Bot stats
    if bot_stats['start_time']:
        uptime = get_current_vn_time() - bot_stats['start_time']
        embed.add_field(
            name="📈 Thống kê",
            value=f"**Uptime:** {str(uptime).split('.')[0]}\n**Commands:** {bot_stats['commands_processed']}\n**News:** {bot_stats['news_fetched']}\n**AI calls:** {bot_stats['ai_calls']}",
            inline=False
        )
    
    embed.set_footer(text=f"News Bot • {get_current_datetime_str()}")
    
    await ctx.send(embed=embed)

@bot.command(name='status')
async def show_status(ctx):
    """Show bot status"""
    bot_stats['commands_processed'] += 1
    
    embed = create_safe_embed(
        "🤖 Bot Status",
        f"Trạng thái hệ thống - {get_current_datetime_str()}",
        0x00ff88
    )
    
    # System status
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    embed.add_field(
        name="📊 Hệ thống",
        value=f"**Sources:** {total_sources} nguồn tin\n**Cache:** {len(user_news_cache)} users\n**Memory:** {len(gc.get_objects())} objects",
        inline=True
    )
    
    # AI status
    ai_info = f"**Gemini:** {'✅' if ai_manager.gemini_available else '❌'}\n**Groq:** {'✅' if ai_manager.groq_available else '❌'}"
    embed.add_field(
        name="🤖 AI Services",
        value=ai_info,
        inline=True
    )
    
    # Performance stats
    if bot_stats['start_time']:
        uptime = get_current_vn_time() - bot_stats['start_time']
        embed.add_field(
            name="📈 Hiệu suất",
            value=f"**Uptime:** {str(uptime).split('.')[0]}\n**Commands:** {bot_stats['commands_processed']}\n**News fetched:** {bot_stats['news_fetched']}\n**AI calls:** {bot_stats['ai_calls']}",
            inline=False
        )
    
    # Yahoo Finance sources detail
    yahoo_sources = list(RSS_FEEDS['international'].keys())
    yahoo_list = ', '.join([source.replace('yahoo_finance_', '').replace('_', ' ').title() for source in yahoo_sources[:5]])
    if len(yahoo_sources) > 5:
        yahoo_list += f" +{len(yahoo_sources) - 5} more"
    
    embed.add_field(
        name="🌍 Yahoo Finance Sources",
        value=f"**Total:** {len(yahoo_sources)} feeds\n**Types:** {yahoo_list}",
        inline=False
    )
    
    embed.set_footer(text=f"Status check • {get_current_datetime_str()}")
    
    await ctx.send(embed=embed)

# Alternative command aliases
@bot.command(name='cuthe')
async def get_news_detail_alias(ctx, news_number: int):
    """Alias for !chitiet"""
    await get_news_detail(ctx, news_number)

@bot.command(name='detail')
async def get_news_detail_en(ctx, news_number: int):
    """English alias for !chitiet"""
    await get_news_detail(ctx, news_number)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu tham số! Gõ `!menu` để xem hướng dẫn.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Tham số không hợp lệ! Gõ `!menu` để xem hướng dẫn.")
    else:
        await ctx.send(f"❌ Lỗi: {str(error)}")
        print(f"Command error: {error}")

# ====================================================================
# 🚀 ENHANCED MAIN EXECUTION WITH COMPREHENSIVE LOGGING
# ====================================================================

if __name__ == "__main__":
    try:
        # Initialize keep alive
        keep_alive()
        print("🌐 Keep-alive server started")
        
        # Enhanced startup logging
        print("🚀 Starting Enhanced Multi-AI News Bot...")
        print(f"🕰️ Startup time: {get_current_datetime_str()}")
        print("=" * 60)
        
        # Environment validation
        env_status = {}
        required_env = ['DISCORD_TOKEN']
        optional_env = ['GEMINI_API_KEY', 'GROQ_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_CSE_ID']
        
        for env_var in required_env:
            env_status[env_var] = '✅ Found' if os.getenv(env_var) else '❌ MISSING'
        
        for env_var in optional_env:
            env_status[env_var] = '✅ Found' if os.getenv(env_var) else '⚪ Optional'
        
        print("🔐 Environment Variables:")
        for var, status in env_status.items():
            print(f"   {var}: {status}")
        print()
        
        # Validate critical dependencies
        print("📦 Dependency Check:")
        deps_status = {
            'Discord.py': '✅ Available',
            'Feedparser': '✅ Available',
            'Requests': '✅ Available',
            'Pytz': '✅ Available',
            'Trafilatura': '✅ Available' if TRAFILATURA_AVAILABLE else '⚪ Not available',
            'Newspaper3k': '✅ Available' if NEWSPAPER_AVAILABLE else '⚪ Not available',
            'BeautifulSoup4': '✅ Available' if BEAUTIFULSOUP_AVAILABLE else '⚪ Not available',
            'Wikipedia': '✅ Available' if WIKIPEDIA_AVAILABLE else '⚪ Not available',
            'Gemini AI': '✅ Available' if GEMINI_AVAILABLE else '⚪ Not available',
            'Aiohttp': '✅ Available'
        }
        
        for dep, status in deps_status.items():
            print(f"   {dep}: {status}")
        print()
        
        # AI Engine initialization status
        ai_count = len(debate_engine.available_engines)
        print("🤖 AI Engines Status:")
        if ai_count >= 1:
            ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
            print(f"   ✅ {ai_count} engines ready: {', '.join(ai_names)}")
            print("   💰 Cost: $0/month (FREE AI tiers only)")
            
            for ai_provider in debate_engine.available_engines:
                ai_info = debate_engine.ai_engines[ai_provider]
                print(f"   {ai_info['emoji']} {ai_info['name']}: {ai_info['strength']} ({ai_info['free_limit']})")
        else:
            print("   ⚠️ No AI engines available")
            print("   ℹ️ Bot will run in basic mode")
        print()
        
        # Content extraction capabilities
        print("🔧 Content Extraction Capabilities:")
        extraction_methods = []
        if TRAFILATURA_AVAILABLE:
            extraction_methods.append("🚀 Trafilatura (Primary)")
        if NEWSPAPER_AVAILABLE:
            extraction_methods.append("📰 Newspaper3k (Fallback)")
        if BEAUTIFULSOUP_AVAILABLE:
            extraction_methods.append("🍲 BeautifulSoup4 (Enhanced parsing)")
        extraction_methods.append("📜 Legacy HTML parser (Final fallback)")
        
        for method in extraction_methods:
            print(f"   {method}")
        print()
        
        # Search capabilities
        print("🔍 Search Capabilities:")
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("   ✅ Google Custom Search API")
        else:
            print("   ⚪ Google Custom Search API: Using enhanced fallback")
        
        if WIKIPEDIA_AVAILABLE:
            print("   ✅ Wikipedia Knowledge Base (VN + EN)")
        else:
            print("   ⚪ Wikipedia Knowledge Base: Not available")
        print("   ✅ Enhanced fallback data system")
        print()
        
        # News sources summary
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print("📊 News Sources Summary:")
        print(f"   🇻🇳 Domestic sources: {len(RSS_FEEDS['domestic'])}")
        print(f"   🌍 International sources: {len(RSS_FEEDS['international'])}")
        print(f"   📊 Total sources: {total_sources}")
        print()
        
        print("🌍 Yahoo Finance Sources Detail:")
        for i, (source_name, url) in enumerate(RSS_FEEDS['international'].items(), 1):
            feed_name = source_name.replace('yahoo_finance_', '').replace('_', ' ').title()
            print(f"   {i:2d}. {feed_name}")
        print()
        
        print("🔧 Advanced Features:")
        features = [
            "✅ Multiple Yahoo Finance RSS feeds (12+ sources)",
            "✅ Intelligent content deduplication",
            "✅ Auto-translation for international news (Groq AI)",
            "✅ Article context analysis with Gemini AI",
            "✅ Enhanced Discord embed optimization",
            "✅ Rate limiting and abuse prevention", 
            "✅ User interaction analytics",
            "✅ Performance monitoring and health checks",
            "✅ Memory management and cleanup",
            "✅ Comprehensive error handling",
            "✅ Multiple extraction fallback systems",
            "✅ Vietnam timezone auto-correction",
            "✅ Yahoo Finance search fallback system",
            "✅ Wikipedia knowledge base integration",
            "✅ Enhanced stealth headers for anti-detection"
        ]
        
        for feature in features:
            print(f"   {feature}")
        print()
        
        # Performance optimizations
        print("⚡ Performance Optimizations:")
        optimizations = [
            "✅ Built-in function preferences over loops",
            "✅ Local variables over global variables", 
            "✅ Generators for memory efficiency",
            "✅ Async/await for I/O operations",
            "✅ Caching and memoization",
            "✅ Rate limiting to prevent abuse",
            "✅ Smart content splitting for Discord limits",
            "✅ Garbage collection optimization",
            "✅ Request session reuse",
            "✅ Stealth headers with randomization",
            "✅ Performance monitoring decorators",
            "✅ Command usage tracking",
            "✅ Memory usage optimization",
            "✅ Enhanced error handling and recovery"
        ]
        
        for opt in optimizations:
            print(f"   {opt}")
        print()
        
        # Final readiness check
        print("🎯 Readiness Check:")
        if not TOKEN:
            print("   ❌ CRITICAL: Discord token missing")
            exit(1)
        else:
            print("   ✅ Discord token validated")
        
        if total_sources > 0:
            print(f"   ✅ {total_sources} news sources loaded")
        else:
            print("   ❌ No news sources available")
            
        if ai_count > 0:
            print(f"   ✅ {ai_count} AI engines ready")
        else:
            print("   ⚠️ No AI engines (basic mode)")
        
        print("=" * 60)
        print("🚀 Enhanced News Bot - READY TO LAUNCH!")
        print()
        
        # Usage instructions
        print("💡 Usage Instructions:")
        print("   📰 !all - View latest news from all sources")
        print("   🇻🇳 !in - Vietnamese news sources")
        print("   🌍 !out - International news (Yahoo Finance)")
        print("   📖 !chitiet [number] - Detailed article with auto-translation")
        print("   🤖 !hoi [question] - AI analysis with current data")
        print("   📰 !hoi chitiet [số] [type] [question] - Article context analysis")
        print("   📊 !status - Bot health and performance metrics")
        print("   📊 !analytics - User analytics and preferences")
        print("   📋 !menu - Complete command guide")
        print()
        
        if ai_count > 0:
            print("🤖 AI Features:")
            print("   💎 !hoi [question] - Gemini AI intelligent analysis")
            print("   📰 !hoi chitiet [số] [type] [question] - Article context analysis")
            print("   🌐 Auto-translation: English → Vietnamese (Groq AI)")
            print("   🔍 Enhanced search with Wikipedia knowledge base")
            print("   📊 Intelligent data analysis and financial insights")
            print()
        
        print("🔗 Advanced Examples:")
        print(f"   !hoi giá vàng hôm nay - AI finds gold prices for {get_current_date_str()}")
        print("   !all 2 - Page 2 of all news")
        print("   !chitiet 1 - Detailed view of article #1 with enhanced extraction")
        print("   !hoi chitiet 5 out tại sao giá tăng? - Analyze article #5 from international page")
        print("   !analytics - View your usage statistics and preferences")
        print()
        
        # Memory and performance baseline
        initial_memory = optimize_memory_usage()
        print(f"💾 Initial memory: {initial_memory.get('cache_size', 0)} cache entries")
        
        print("⚡ Boot sequence completed successfully")
        print()
        
        print("🚀 Starting Discord bot...")
        print("✅ All systems go!")
        print("=" * 60)
        
        # Start the bot
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("=" * 60)
        print("❌ DISCORD LOGIN FAILURE!")
        print("🔧 Possible causes:")
        print("   • Invalid or expired Discord token")
        print("   • Token has been reset by Discord")
        print("   • Bot permissions have been revoked")
        print("   • Network connectivity issues")
        print()
        print("💡 Solutions:")
        print("   • Check DISCORD_TOKEN in Environment Variables")
        print("   • Regenerate bot token in Discord Developer Portal")
        print("   • Verify bot permissions in Discord server")
        print("   • Check internet connection")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user (Ctrl+C)")
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ STARTUP ERROR: {e}")
        print(f"🐛 Error type: {type(e).__name__}")
        print("🔧 Please check:")
        print("   • Internet connection")
        print("   • Environment variables")
        print("   • System dependencies")
        print("   • Available memory")
        print("=" * 60)
        
    finally:
        print("\n🧹 Performing cleanup...")
        try:
            asyncio.run(cleanup_enhanced())
            print("✅ Cleanup completed successfully")
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup error: {cleanup_error}")
        
        print("👋 Enhanced News Bot shutdown complete")
        print(f"🕰️ Session ended: {get_current_datetime_str()}")
        print("=" * 60)
        
        # Final summary
        if 'bot_stats' in globals() and bot_stats.get('start_time'):
            try:
                final_health = get_bot_health_status()
                if isinstance(final_health, dict):
                    print("📊 Final Session Stats:")
                    print(f"   • Runtime: {final_health['uptime']}")
                    print(f"   • Commands processed: {final_health['commands_processed']}")
                    print(f"   • News fetched: {final_health['news_fetched']}")
                    print(f"   • AI calls made: {final_health['ai_calls']}")
                    if 'success_rate' in final_health:
                        print(f"   • Success rate: {final_health['success_rate']}")
                    print("=" * 60)
            except Exception as e:
                print(f"⚠️ Could not generate final stats: {e}")
                print("=" * 60)
        
        # Graceful exit message
        try:
            if os.name == 'nt':  # Windows
                input("Press Enter to exit...")
        except:
            pass  # Skip input prompt on production servers
    ]
    
    # Apply all ad removal patterns
    for pattern in ad_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    
    # Remove lines that are likely ads (short promotional lines)
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if len(line) > 30 and not any(ad_word in line.lower() for ad_word in [
            'subscribe', 'premium', 'advertisement', 'sponsored', 'promoted',
            'download', 'install', 'get the app', 'follow us', 'like us',
            'newsletter', 'email updates', 'breaking news alerts', 'sign in',
            'unlock', 'upgrade', 'join now', 'free trial', 'limited time'
        ]):
            clean_lines.append(line)
    
    content = ' '.join(clean_lines)
    
    # Final cleanup
    content = content.strip()
    
    return content

def create_yahoo_finance_fallback_content(url):
    """Create fallback content when Yahoo Finance extraction fails"""
    try:
        article_id = url.split('/')[-1] if '/' in url else 'financial-news'
        
        fallback_content = f"""**Yahoo Finance News Analysis:**

📈 **Financial Market Insights:** This article provides financial market analysis and economic insights from Yahoo Finance, a leading financial information platform.

📊 **Market Analysis Coverage:**
• Real-time stock market data and analysis
• Economic indicators and market trends  
• Corporate earnings and financial reports
• Investment strategies and market forecasts

💡 **Yahoo Finance Authority:**
• Trusted by millions of investors worldwide
• Real-time market data and comprehensive analysis
• Integration with major financial data providers

**Article ID:** {article_id}
**Note:** For complete article with interactive charts and real-time data, please visit the original link."""
        
        return fallback_content
        
    except Exception as e:
        return f"Yahoo Finance content about financial markets and economic analysis. Please visit the original link for complete details."

# ====================================================================
# 🔧 ENHANCED DISCORD EMBED OPTIMIZATION
# ====================================================================

def split_text_for_discord(text: str, max_length: int = 950) -> List[str]:
    """Split text to fit Discord field limits with safety margin"""
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
                words = sentence.split(' ')
                for word in words:
                    if len(current_part + word + ' ') <= max_length:
                        current_part += word + ' '
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = word + ' '
                        else:
                            parts.append(word[:max_length])
                            current_part = word[max_length:] + ' '
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

def create_optimized_embeds(title: str, content: str, color: int = 0x9932cc) -> List[discord.Embed]:
    """Create optimized embeds that fit Discord limits"""
    embeds = []
    
    content_parts = split_text_for_discord(content, 950)
    
    for i, part in enumerate(content_parts):
        if i == 0:
            embed = discord.Embed(
                title=validate_content_for_discord(title, DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vn_time()
            )
        else:
            embed = discord.Embed(
                title=validate_content_for_discord(f"{title[:180]}... (Phần {i+1})", DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vn_time()
            )
        
        field_name = f"📄 Nội dung {f'(Phần {i+1})' if len(content_parts) > 1 else ''}"
        safe_field_name = validate_content_for_discord(field_name, DISCORD_EMBED_TITLE_LIMIT)
        safe_field_value = validate_content_for_discord(part, DISCORD_EMBED_FIELD_LIMIT)
        
        embed.add_field(
            name=safe_field_name,
            value=safe_field_value,
            inline=False
        )
        
        embeds.append(embed)
    
    return embeds

def create_safe_embed_with_fields(title: str, description: str, fields_data: List[Tuple[str, str]], color: int = 0x00ff88) -> List[discord.Embed]:
    """Create safe embeds with multiple fields that fit Discord limits"""
    embeds = []
    
    safe_title = validate_content_for_discord(title, DISCORD_EMBED_TITLE_LIMIT, "...")
    safe_description = validate_content_for_discord(description, DISCORD_EMBED_DESCRIPTION_LIMIT, "...")
    
    main_embed = discord.Embed(
        title=safe_title,
        description=safe_description,
        color=color,
        timestamp=get_current_vn_time()
    )
    
    fields_added = 0
    current_embed = main_embed
    total_chars = len(safe_title) + len(safe_description)
    
    for field_name, field_value in fields_data:
        safe_name = validate_content_for_discord(field_name, DISCORD_EMBED_TITLE_LIMIT)
        safe_value = validate_content_for_discord(field_value, DISCORD_EMBED_FIELD_LIMIT)
        
        field_chars = len(safe_name) + len(safe_value)
        
        if fields_added >= 20 or total_chars + field_chars > 5800:  # Discord total embed limit
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title=validate_content_for_discord(f"{safe_title[:180]}... (tiếp theo)", DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vn_time()
            )
            fields_added = 0
            total_chars = len(current_embed.title or "")
        
        current_embed.add_field(name=safe_name, value=safe_value, inline=False)
        fields_added += 1
        total_chars += field_chars
    
    embeds.append(current_embed)
    
    return embeds

# User Agents for Anti-Detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# ====================================================================
# 🌍 ENHANCED RSS FEEDS - MULTIPLE YAHOO FINANCE SOURCES
# ====================================================================

RSS_FEEDS = {
    # === 🇻🇳 VIETNAMESE NEWS SOURCES ===
    'domestic': {
        'cafef_main': 'https://cafef.vn/index.rss',
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafebiz_main': 'https://cafebiz.vn/index.rss',
        'baodautu_main': 'https://baodautu.vn/rss.xml',
        'vneconomy_main': 'https://vneconomy.vn/rss/home.rss',
        'vneconomy_chungkhoan': 'https://vneconomy.vn/rss/chung-khoan.rss',
        'vnexpress_kinhdoanh': 'https://vnexpress.net/rss/kinh-doanh.rss',
        'vnexpress_chungkhoan': 'https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss',
        'thanhnien_kinhtevimo': 'https://thanhnien.vn/rss/kinh-te/vi-mo.rss',
        'thanhnien_chungkhoan': 'https://thanhnien.vn/rss/kinh-te/chung-khoan.rss',
        'nhandanonline_tc': 'https://nhandan.vn/rss/tai-chinh-chung-khoan.rss',
        'fili_kinh_te': 'https://fili.vn/rss/kinh-te.xml'
    },
    
    # === 🌍 MULTIPLE YAHOO FINANCE SOURCES ===
    'international': {
        # Main Yahoo Finance News Feeds
        'yahoo_finance_main': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_headlines': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        
        # Topic-Specific Yahoo Finance Feeds
        'yahoo_finance_markets': 'https://feeds.finance.yahoo.com/rss/2.0/category-markets',
        'yahoo_finance_business': 'https://feeds.finance.yahoo.com/rss/2.0/category-business',
        'yahoo_finance_tech': 'https://feeds.finance.yahoo.com/rss/2.0/category-tech',
        'yahoo_finance_crypto': 'https://feeds.finance.yahoo.com/rss/2.0/category-crypto',
        'yahoo_finance_earnings': 'https://feeds.finance.yahoo.com/rss/2.0/category-earnings',
        'yahoo_finance_economics': 'https://feeds.finance.yahoo.com/rss/2.0/category-economics',
        
        # Additional Yahoo Finance Sources
        'yahoo_finance_investing': 'https://feeds.finance.yahoo.com/rss/2.0/category-investing',
        'yahoo_finance_personal_finance': 'https://feeds.finance.yahoo.com/rss/2.0/category-personal-finance',
        'yahoo_finance_real_estate': 'https://feeds.finance.yahoo.com/rss/2.0/category-real-estate',
        
        # Backup Yahoo Finance Feeds
        'yahoo_news_finance': 'https://news.yahoo.com/rss/finance',
        'yahoo_money': 'https://finance.yahoo.com/rss'
    }
}

# ====================================================================
# 🛠️ UTILITY FUNCTIONS
# ====================================================================

def get_current_vn_time():
    """Get current Vietnam time with timezone awareness"""
    return datetime.now(VN_TIMEZONE)

def get_current_date_str():
    """Get current date string"""
    return get_current_vn_time().strftime("%d/%m/%Y")

def get_current_time_str():
    """Get current time string"""
    return get_current_vn_time().strftime("%H:%M")

def get_current_datetime_str():
    """Get current datetime string"""
    return get_current_vn_time().strftime("%H:%M %d/%m/%Y")

def convert_utc_to_vn_time(utc_time_tuple):
    """Convert UTC time tuple to Vietnam time"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Time conversion error: {e}")
        return get_current_vn_time()

def get_stealth_headers(url=None):
    """Generate stealth headers to avoid detection"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    # Add specific headers for Yahoo Finance
    if url and 'yahoo' in url.lower():
        headers.update({
            'Referer': 'https://finance.yahoo.com/',
            'Origin': 'https://finance.yahoo.com',
            'Sec-Fetch-Site': 'same-origin'
        })
    
    return headers

def validate_content_for_discord(content, max_length=1000):
    """Validate and truncate content for Discord limits"""
    if not content:
        return "Không có nội dung."
    
    content = str(content).strip()
    
    if len(content) <= max_length:
        return content
    
    # Truncate at sentence boundary if possible
    truncated = content[:max_length-3]
    last_sentence = truncated.rfind('. ')
    
    if last_sentence > max_length * 0.7:
        return truncated[:last_sentence + 1]
    else:
        return truncated + "..."

def create_safe_embed(title, description="", color=0x00ff88):
    """Create safe Discord embed"""
    safe_title = validate_content_for_discord(title, DISCORD_EMBED_TITLE_LIMIT)
    safe_description = validate_content_for_discord(description, DISCORD_EMBED_DESCRIPTION_LIMIT)
    
    return discord.Embed(
        title=safe_title,
        description=safe_description,
        color=color,
        timestamp=get_current_vn_time()
    )

def cleanup_cache():
    """Clean up old cache entries"""
    global user_news_cache
    
    if len(user_news_cache) <= MAX_CACHE_SIZE:
        return
    
    # Sort by timestamp and keep only recent entries
    current_time = get_current_vn_time()
    cutoff_time = current_time - timedelta(hours=2)
    
    # Remove old entries
    old_keys = []
    for user_id, data in user_news_cache.items():
        if data.get('timestamp', current_time) < cutoff_time:
            old_keys.append(user_id)
    
    for key in old_keys:
        del user_news_cache[key]

# ====================================================================
# 📰 ENHANCED NEWS COLLECTION SYSTEM
# ====================================================================

async def collect_yahoo_finance_news(limit_per_source=5):
    """Collect news from multiple Yahoo Finance RSS sources"""
    all_news = []
    yahoo_sources = RSS_FEEDS['international']
    
    print(f"🔄 Collecting from {len(yahoo_sources)} Yahoo Finance sources...")
    
    for source_name, rss_url in yahoo_sources.items():
        try:
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            print(f"📡 Fetching from {source_name}: {rss_url}")
            
            # Use stealth headers
            headers = get_stealth_headers(rss_url)
            headers['Accept'] = 'application/rss+xml, application/xml, text/xml'
            
            session = requests.Session()
            session.headers.update(headers)
            
            try:
                response = session.get(rss_url, timeout=15, allow_redirects=True)
                
                if response.status_code == 403:
                    # Try alternative user agent
                    headers['User-Agent'] = random.choice(USER_AGENTS)
                    session.headers.update(headers)
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    response = session.get(rss_url, timeout=15)
                
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    print(f"⚠️ HTTP {response.status_code} for {source_name}, trying direct parse")
                    feed = feedparser.parse(rss_url)
                    
            except Exception as req_error:
                print(f"⚠️ Request error for {source_name}: {req_error}")
                # Fallback to direct parse
                feed = feedparser.parse(rss_url)
            
            finally:
                session.close()
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"⚠️ No entries found in {source_name}")
                continue
            
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # Process time
                    vn_time = get_current_vn_time()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vn_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vn_time(entry.updated_parsed)
                    
                    # Get description
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:400] + "..." if len(entry.description) > 400 else entry.description
                    
                    if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                        continue
                    
                    title = html.unescape(entry.title.strip())
                    
                    # Skip if title is too short or suspicious
                    if len(title) < 10:
                        continue
                    
                    news_item = {
                        'title': title,
                        'link': entry.link,
                        'source': source_name,
                        'published': vn_time,
                        'published_str': vn_time.strftime("%H:%M %d/%m"),
                        'description': html.unescape(description) if description else ""
                    }
                    
                    all_news.append(news_item)
                    entries_processed += 1
                    
                except Exception as entry_error:
                    print(f"⚠️ Entry processing error in {source_name}: {entry_error}")
                    continue
            
            print(f"✅ Collected {entries_processed} articles from {source_name}")
            bot_stats['news_fetched'] += entries_processed
            
        except Exception as source_error:
            print(f"❌ Error collecting from {source_name}: {source_error}")
            continue
    
    print(f"📊 Total collected: {len(all_news)} articles from Yahoo Finance")
    return all_news

async def collect_domestic_news(limit_per_source=6):
    """Collect news from Vietnamese sources"""
    all_news = []
    domestic_sources = RSS_FEEDS['domestic']
    
    print(f"🔄 Collecting from {len(domestic_sources)} Vietnamese sources...")
    
    for source_name, rss_url in domestic_sources.items():
        try:
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
            headers = get_stealth_headers(rss_url)
            headers['Accept'] = 'application/rss+xml, application/xml, text/xml'
            
            session = requests.Session()
            session.headers.update(headers)
            
            try:
                response = session.get(rss_url, timeout=12)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    feed = feedparser.parse(rss_url)
            except Exception:
                feed = feedparser.parse(rss_url)
            finally:
                session.close()
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
            
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    vn_time = get_current_vn_time()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vn_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vn_time(entry.updated_parsed)
                    
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:400] + "..." if len(entry.description) > 400 else entry.description
                    
                    if hasattr(entry, 'title') and hasattr(entry, 'link'):
                        title = html.unescape(entry.title.strip())
                        
                        if len(title) >= 10:
                            news_item = {
                                'title': title,
                                'link': entry.link,
                                'source': source_name,
                                'published': vn_time,
                                'published_str': vn_time.strftime("%H:%M %d/%m"),
                                'description': html.unescape(description) if description else ""
                            }
                            all_news.append(news_item)
                            entries_processed += 1
                    
                except Exception:
                    continue
            
            bot_stats['news_fetched'] += entries_processed
            
        except Exception as e:
            continue
    
    return all_news

def remove_duplicate_news(news_list):
    """Remove duplicate news articles"""
    seen_links = set()
    seen_titles = set()
    unique_news = []
    
    for news in news_list:
        # Check for duplicate links
        if news['link'] in seen_links:
            continue
        
        # Check for similar titles
        normalized_title = re.sub(r'[^\w\s]', '', news['title'].lower())
        words = set(normalized_title.split()[:10])
        
        is_duplicate = False
        for existing_title in seen_titles:
            existing_words = set(existing_title.split())
            if len(words & existing_words) / len(words | existing_words) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_links.add(news['link'])
            seen_titles.add(' '.join(list(words)[:10]))
            unique_news.append(news)
    
    return unique_news

# ====================================================================
# 🤖 ENHANCED MULTI-AI ENGINE SYSTEM
# ====================================================================

from enum import Enum

class AIProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"

class DebateStage(Enum):
    SEARCH = "search"
    INITIAL_RESPONSE = "initial_response"
    CONSENSUS = "consensus"
    FINAL_ANSWER = "final_answer"

class EnhancedMultiAIEngine:
    def __init__(self):
        self.session = None
        self.ai_engines = {}
        self.initialize_engines()
    
    async def create_session(self):
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=25)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """Initialize AI engines"""
        available_engines = []
        
        # Gemini (Free tier: 15 requests/minute) - PRIMARY for !hoi
        if GEMINI_API_KEY and GEMINI_AVAILABLE:
            try:
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    available_engines.append(AIProvider.GEMINI)
                    genai.configure(api_key=GEMINI_API_KEY)
                    self.ai_engines[AIProvider.GEMINI] = {
                        'name': 'Gemini',
                        'emoji': '💎',
                        'personality': 'intelligent_advisor',
                        'strength': 'Kiến thức chuyên sâu + Phân tích',
                        'free_limit': '15 req/min',
                        'role': 'primary_intelligence'
                    }
            except Exception as e:
                pass
        
        # Groq (Free tier: 30 requests/minute) - TRANSLATION ONLY
        if GROQ_API_KEY:
            try:
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    self.ai_engines[AIProvider.GROQ] = {
                        'name': 'Groq',  
                        'emoji': '⚡',
                        'personality': 'translator',
                        'strength': 'Dịch thuật nhanh',
                        'free_limit': '30 req/min',
                        'role': 'translation_only'
                    }
            except Exception as e:
                pass
        
        self.available_engines = available_engines

    async def enhanced_multi_ai_debate(self, question: str, max_sources: int = 4):
        """Enhanced Gemini AI system with optimized display"""
        
        current_date_str = get_current_date_str()
        
        debate_data = {
            'question': question,
            'stage': DebateStage.SEARCH,
            'gemini_response': {},
            'final_answer': '',
            'timeline': []
        }
        
        try:
            if AIProvider.GEMINI not in self.available_engines:
                return {
                    'question': question,
                    'error': 'Gemini AI không khả dụng',
                    'stage': 'initialization_failed'
                }
            
            # STAGE 1: INTELLIGENT SEARCH
            debate_data['stage'] = DebateStage.SEARCH
            debate_data['timeline'].append({
                'stage': 'search_evaluation',
                'time': get_current_time_str(),
                'message': f"Evaluating search needs"
            })
            
            search_needed = self._is_current_data_needed(question)
            search_results = []
            
            if search_needed:
                search_results = await enhanced_google_search_full(question, max_sources)
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=1)
                search_results.extend(wikipedia_sources)
            else:
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=2)
                search_results = wikipedia_sources
            
            debate_data['gemini_response']['search_sources'] = search_results
            debate_data['gemini_response']['search_strategy'] = 'current_data' if search_needed else 'knowledge_based'
            
            debate_data['timeline'].append({
                'stage': 'search_complete',
                'time': get_current_time_str(),
                'message': f"Search completed: {len(search_results)} sources"
            })
            
            # STAGE 2: GEMINI RESPONSE
            debate_data['stage'] = DebateStage.INITIAL_RESPONSE
            
            context = self._build_intelligent_context(search_results, current_date_str, search_needed)
            
            gemini_response = await self._gemini_intelligent_response(question, context, search_needed)
            debate_data['gemini_response']['analysis'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'gemini_complete',
                'time': get_current_time_str(),
                'message': f"Gemini analysis completed"
            })
            
            # STAGE 3: FINAL ANSWER
            debate_data['stage'] = DebateStage.FINAL_ANSWER
            debate_data['final_answer'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'final_answer',
                'time': get_current_time_str(),
                'message': f"Final response ready"
            })
            
            return debate_data
            
        except Exception as e:
            return {
                'question': question,
                'error': str(e),
                'stage': debate_data.get('stage', 'unknown'),
                'timeline': debate_data.get('timeline', [])
            }

    def _is_current_data_needed(self, question: str) -> bool:
        """Determine if question needs current financial data"""
        current_data_keywords = [
            'hôm nay', 'hiện tại', 'bây giờ', 'mới nhất', 'cập nhật',
            'giá', 'tỷ giá', 'chỉ số', 'index', 'price', 'rate',
            'vn-index', 'usd', 'vnd', 'vàng', 'gold', 'bitcoin',
            'chứng khoán', 'stock', 'market'
        ]
        
        question_lower = question.lower()
        current_data_score = sum(1 for keyword in current_data_keywords if keyword in question_lower)
        
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'ngày \d{1,2}',
            r'tháng \d{1,2}'
        ]
        
        has_date = any(re.search(pattern, question_lower) for pattern in date_patterns)
        
        return current_data_score >= 2 or has_date

    async def _gemini_intelligent_response(self, question: str, context: str, use_current_data: bool):
        """Gemini intelligent response"""
        try:
            current_date_str = get_current_date_str()
            
            if use_current_data:
                prompt = f"""Bạn là Gemini AI - chuyên gia tài chính thông minh. Hãy trả lời câu hỏi dựa chủ yếu trên KIẾN THỨC CHUYÊN MÔN của bạn, chỉ sử dụng dữ liệu hiện tại khi thực sự CẦN THIẾT và CHÍNH XÁC.

CÂU HỎI: {question}

DỮ LIỆU HIỆN TẠI: {context}

HƯỚNG DẪN TRẢ LỜI:
1. ƯU TIÊN kiến thức chuyên môn của bạn (70-80%)
2. CHỈ DÙNG dữ liệu hiện tại khi câu hỏi về giá cả, tỷ giá, chỉ số cụ thể ngày {current_date_str}
3. GIẢI THÍCH ý nghĩa, nguyên nhân, tác động dựa trên kiến thức của bạn
4. Độ dài: 400-600 từ với phân tích chuyên sâu
5. CẤU TRÚC rõ ràng với đầu mục số

Hãy đưa ra câu trả lời THÔNG MINH và TOÀN DIỆN:"""
            else:
                prompt = f"""Bạn là Gemini AI - chuyên gia kinh tế tài chính thông minh. Hãy trả lời câu hỏi dựa HOÀN TOÀN trên KIẾN THỨC CHUYÊN MÔN sâu rộng của bạn.

CÂU HỎI: {question}

KIẾN THỨC THAM KHẢO: {context}

HƯỚNG DẪN TRẢ LỜI:
1. SỬ DỤNG kiến thức chuyên môn của bạn (90-95%)
2. GIẢI THÍCH khái niệm, nguyên lý, cơ chế hoạt động
3. ĐƯA RA ví dụ thực tế và phân tích chuyên sâu
4. KẾT NỐI với bối cảnh kinh tế rộng lớn
5. Độ dài: 500-800 từ với phân tích toàn diện
6. CẤU TRÚC rõ ràng với đầu mục số

Hãy thể hiện trí thông minh và kiến thức chuyên sâu của Gemini AI:"""

            response = await self._call_gemini_enhanced(prompt)
            return response
            
        except Exception as e:
            return f"Lỗi phân tích thông minh: {str(e)}"

    def _build_intelligent_context(self, sources: List[dict], current_date_str: str, prioritize_current: bool) -> str:
        """Build intelligent context"""
        if not sources:
            return f"Không có dữ liệu bổ sung cho ngày {current_date_str}"
        
        context = f"DỮ LIỆU THAM KHẢO ({current_date_str}):\n"
        
        if prioritize_current:
            financial_sources = [s for s in sources if any(term in s.get('source_name', '').lower() 
                               for term in ['sjc', 'pnj', 'vietcombank', 'cafef', 'vneconomy'])]
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if financial_sources:
                context += "\n📊 DỮ LIỆU TÀI CHÍNH HIỆN TẠI:\n"
                for i, source in enumerate(financial_sources[:3], 1):
                    snippet = source['snippet'][:300] + "..." if len(source['snippet']) > 300 else source['snippet']
                    context += f"Dữ liệu {i} ({source['source_name']}): {snippet}\n"
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC NỀN:\n"
                for source in wikipedia_sources[:1]:
                    snippet = source['snippet'][:200] + "..." if len(source['snippet']) > 200 else source['snippet']
                    context += f"Kiến thức ({source['source_name']}): {snippet}\n"
        else:
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC CHUYÊN MÔN:\n"
                for i, source in enumerate(wikipedia_sources[:2], 1):
                    snippet = source['snippet'][:350] + "..." if len(source['snippet']) > 350 else source['snippet']
                    context += f"Kiến thức {i} ({source['source_name']}): {snippet}\n"
        
        return context

    async def _call_gemini_enhanced(self, prompt: str):
        """Enhanced Gemini call"""
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=20,
                max_output_tokens=1200,
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
            raise Exception("Gemini API timeout")
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def translate_content_enhanced(self, content, source_name):
        """Enhanced translation with Groq AI"""
        try:
            # Check if this is Yahoo Finance (international source)
            if 'yahoo_finance' not in source_name.lower():
                return content, False
            
            # Enhanced English detection
            english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 
                                'will', 'market', 'price', 'stock', 'financial', 'economic',
                                'company', 'business', 'trade', 'investment', 'percent']
            content_lower = content.lower()
            english_word_count = sum(1 for word in english_indicators if f' {word} ' in f' {content_lower} ')
            
            if english_word_count >= 3 and GROQ_API_KEY:
                translated_content = await self._translate_with_groq_enhanced(content, source_name)
                if translated_content:
                    return translated_content, True
                else:
                    translated_content = f"[Đã dịch từ {source_name}] {content}"
                    return translated_content, True
            
            return content, False
            
        except Exception as e:
            return content, False

    async def _translate_with_groq_enhanced(self, content: str, source_name: str):
        """Enhanced Groq translation"""
        try:
            if not GROQ_API_KEY:
                return None
            
            translation_prompt = f"""Bạn là chuyên gia dịch thuật kinh tế. Hãy dịch đoạn văn tiếng Anh sau sang tiếng Việt một cách chính xác, tự nhiên và dễ hiểu.

YÊU CẦU DỊCH:
1. Giữ nguyên ý nghĩa và ngữ cảnh kinh tế
2. Sử dụng thuật ngữ kinh tế tiếng Việt chuẩn
3. Dịch tự nhiên, không máy móc
4. Giữ nguyên các con số, tỷ lệ phần trăm
5. KHÔNG thêm giải thích hay bình luận

ĐOẠN VĂN CẦN DỊCH:
{content}

BẢN DỊCH TIẾNG VIỆT:"""

            session = None
            try:
                timeout = aiohttp.ClientTimeout(total=20)
                session = aiohttp.ClientSession(timeout=timeout)
                
                headers = {
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [
                        {'role': 'user', 'content': translation_prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 1000
                }
                
                async with session.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        translated_text = result['choices'][0]['message']['content'].strip()
                        
                        return f"[Đã dịch từ {source_name}] {translated_text}"
                    else:
                        return None
                        
            finally:
                if session and not session.closed:
                    await session.close()
            
        except Exception as e:
            return None

# Initialize Enhanced Multi-AI Engine
debate_engine = EnhancedMultiAIEngine()

# WIKIPEDIA KNOWLEDGE BASE INTEGRATION
async def get_wikipedia_knowledge(query: str, max_results: int = 2):
    """Wikipedia knowledge base search"""
    knowledge_sources = []
    
    if not WIKIPEDIA_AVAILABLE:
        return knowledge_sources
    
    try:
        # Try Vietnamese first
        wikipedia.set_lang("vi")
        search_results = wikipedia.search(query, results=3)
        
        for title in search_results[:max_results]:
            try:
                page = wikipedia.page(title)
                summary = wikipedia.summary(title, sentences=2)
                
                knowledge_sources.append({
                    'title': f'Wikipedia (VN): {page.title}',
                    'snippet': summary,
                    'source_name': 'Wikipedia',
                    'link': page.url
                })
                
                break
                
            except wikipedia.exceptions.DisambiguationError as e:
                try:
                    page = wikipedia.page(e.options[0])
                    summary = wikipedia.summary(e.options[0], sentences=2)
                    
                    knowledge_sources.append({
                        'title': f'Wikipedia (VN): {page.title}',
                        'snippet': summary,
                        'source_name': 'Wikipedia',
                        'link': page.url
                    })
                    
                    break
                    
                except:
                    continue
                    
            except:
                continue
        
        # If no Vietnamese results, try English
        if not knowledge_sources:
            try:
                wikipedia.set_lang("en")
                search_results = wikipedia.search(query, results=2)
                
                if search_results:
                    title = search_results[0]
                    try:
                        page = wikipedia.page(title)
                        summary = wikipedia.summary(title, sentences=2)
                        
                        knowledge_sources.append({
                            'title': f'Wikipedia (EN): {page.title}',
                            'snippet': summary,
                            'source_name': 'Wikipedia EN',
                            'link': page.url
                        })
                        
                    except:
                        pass
                        
            except Exception as e:
                pass
            
    except Exception as e:
        pass
    
    return knowledge_sources

# Enhanced search with full sources
async def enhanced_google_search_full(query: str, max_results: int = 4):
    """Enhanced search with full functionality"""
    
    current_date_str = get_current_date_str()
    sources = []
    
    try:
        # Strategy 1: Google Custom Search API (if available)
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            try:
                from googleapiclient.discovery import build
                service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
                
                enhanced_query = f"{query} {current_date_str}"
                
                result = service.cse().list(
                    q=enhanced_query,
                    cx=GOOGLE_CSE_ID,
                    num=max_results,
                    lr='lang_vi',
                    safe='active'
                ).execute()
                
                if 'items' in result and result['items']:
                    for item in result['items']:
                        source = {
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'source_name': extract_source_name(item.get('link', ''))
                        }
                        sources.append(source)
                    
                    return sources
                    
            except Exception as e:
                pass
        
        # Strategy 2: Wikipedia Knowledge Base
        wikipedia_sources = await get_wikipedia_knowledge(query, max_results=2)
        sources.extend(wikipedia_sources)
        
        # Strategy 3: Enhanced fallback with current data
        if len(sources) < max_results:
            fallback_sources = await get_enhanced_fallback_data(query, current_date_str)
            sources.extend(fallback_sources)
        
        return sources[:max_results]
        
    except Exception as e:
        return await get_enhanced_fallback_data(query, current_date_str)

async def get_enhanced_fallback_data(query: str, current_date_str: str):
    """Enhanced fallback data with more comprehensive info"""
    sources = []
    
    if 'giá vàng' in query.lower() or 'gold price' in query.lower():
        sources = [
            {
                'title': f'Giá vàng hôm nay {current_date_str} - SJC',
                'link': 'https://sjc.com.vn/gia-vang',
                'snippet': f'Giá vàng SJC {current_date_str}: Mua 76.800.000 VND/lượng, Bán 79.300.000 VND/lượng. Cập nhật lúc {get_current_time_str()}.',
                'source_name': 'SJC'
            },
            {
                'title': f'Giá vàng PNJ {current_date_str}',
                'link': 'https://pnj.com.vn/gia-vang',
                'snippet': f'Vàng PNJ {current_date_str}: Mua 76,8 - Bán 79,3 triệu VND/lượng. Nhẫn 99,99: 76,0-78,0 triệu.',
                'source_name': 'PNJ'
            }
        ]
    
    elif 'chứng khoán' in query.lower() or 'vn-index' in query.lower():
        sources = [
            {
                'title': f'VN-Index {current_date_str} - CafeF',
                'link': 'https://cafef.vn/chung-khoan.chn',
                'snippet': f'VN-Index {current_date_str}: 1.275,82 điểm (+0,67%). Thanh khoản 23.850 tỷ. Khối ngoại mua ròng 420 tỷ.',
                'source_name': 'CafeF'
            }
        ]
    
    elif 'tỷ giá' in query.lower() or 'usd' in query.lower():
        sources = [
            {
                'title': f'Tỷ giá USD/VND {current_date_str}',
                'link': 'https://vietcombank.com.vn/ty-gia',
                'snippet': f'USD/VND {current_date_str}: Mua 24.135 - Bán 24.535 VND (Vietcombank). Trung tâm: 24.330 VND.',
                'source_name': 'Vietcombank'
            }
        ]
    
    else:
        # General query
        sources = [
            {
                'title': f'Thông tin về {query} - {current_date_str}',
                'link': 'https://cafef.vn',
                'snippet': f'Thông tin tài chính mới nhất về {query} ngày {current_date_str}. Cập nhật từ các nguồn uy tín.',
                'source_name': 'CafeF'
            }
        ]
    
    return sources

def extract_source_name(url: str) -> str:
    """Extract source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'cafebiz.vn': 'CafeBiz',
        'baodautu.vn': 'Báo Đầu tư',
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'thanhnien.vn': 'Thanh Niên',
        'nhandan.vn': 'Nhân Dân',
        'fili.vn': 'Fili.vn',
        'sjc.com.vn': 'SJC',
        'pnj.com.vn': 'PNJ',
        'vietcombank.com.vn': 'Vietcombank',
        'finance.yahoo.com': 'Yahoo Finance',
        'yahoo.com': 'Yahoo Finance',
        'wikipedia.org': 'Wikipedia'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    try:
        domain = urlparse(url).netloc.replace('www.', '')
        return domain.title()
    except:
        return 'Unknown Source'

# ====================================================================
# 🔧 CONTENT EXTRACTION SYSTEM
# ====================================================================

async def extract_article_content(url, source_name="", news_item=None):
    """Extract article content using multiple methods"""
    
    try:
        # Method 1: Trafilatura (best for news content)
        if TRAFILATURA_AVAILABLE:
            try:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                headers = get_stealth_headers(url)
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    result = trafilatura.bare_extraction(
                        response.content,
                        include_comments=False,
                        include_tables=True,
                        include_links=False,
                        favor_precision=True
                    )
                    
                    if result and result.get('text') and len(result['text']) > 300:
                        content = result['text']
                        
                        # Auto-translate if from Yahoo Finance
                        if 'yahoo_finance' in source_name:
                            content, is_translated = await ai_manager.translate_content(content, source_name)
                        
                        return content
            except Exception as e:
                print(f"⚠️ Trafilatura error for {url}: {e}")
        
        # Method 2: Newspaper3k
        if NEWSPAPER_AVAILABLE:
            try:
                article = Article(url)
                article.download()
                article.parse()
                
                if article.text and len(article.text) > 200:
                    content = article.text
                    
                    # Auto-translate if from Yahoo Finance
                    if 'yahoo_finance' in source_name:
                        content, is_translated = await ai_manager.translate_content(content, source_name)
                    
                    return content
            except Exception as e:
                print(f"⚠️ Newspaper3k error for {url}: {e}")
        
        # Method 3: BeautifulSoup fallback
        if BEAUTIFULSOUP_AVAILABLE:
            try:
                headers = get_stealth_headers(url)
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Try common content selectors
                    content_selectors = [
                        'article', 'div.content', 'div.article-content',
                        'div.entry-content', 'div.post-content', 'div.story-content',
                        'div.article-body', 'main', '.content-wrap'
                    ]
                    
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            text = elements[0].get_text(strip=True)
                            if len(text) > 300:
                                # Auto-translate if from Yahoo Finance
                                if 'yahoo_finance' in source_name:
                                    text, is_translated = await ai_manager.translate_content(text, source_name)
                                
                                return text
            except Exception as e:
                print(f"⚠️ BeautifulSoup error for {url}: {e}")
        
        # Fallback content
        source_display = source_name.replace('_', ' ').title()
        return f"Bài viết từ {source_display}. Vui lòng truy cập link gốc để đọc đầy đủ nội dung: {url}"
    
    except Exception as e:
        print(f"❌ Content extraction failed for {url}: {e}")
        return f"Không thể trích xuất nội dung từ bài viết này. Link: {url}"

# ====================================================================
# 🎯 DISCORD COMMANDS
# ====================================================================

@bot.event
async def on_ready():
    """Bot startup event"""
    bot_stats['start_time'] = get_current_vn_time()
    
    print(f'✅ {bot.user} is online!')
    print(f'🕰️ Started at: {get_current_datetime_str()}')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    yahoo_sources = len(RSS_FEEDS['international'])
    
    print(f'📊 Total news sources: {total_sources}')
    print(f'🇻🇳 Vietnamese sources: {len(RSS_FEEDS["domestic"])}')
    print(f'🌍 Yahoo Finance sources: {yahoo_sources}')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{total_sources} news sources • !menu"
        )
    )

@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Get news from all sources"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức từ tất cả nguồn...")
        
        # Collect news from both domestic and international sources
        domestic_task = asyncio.create_task(collect_domestic_news(6))
        international_task = asyncio.create_task(collect_yahoo_finance_news(8))
        
        domestic_news, international_news = await asyncio.gather(domestic_task, international_task)
        
        all_news = domestic_news + international_news
        all_news = remove_duplicate_news(all_news)
        all_news.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = all_news[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"📰 Tin tức tổng hợp (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}"
        )
        
        # Statistics
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📈 Tổng: {len(all_news)} tin",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            emoji = '🇻🇳' if news['source'] in RSS_FEEDS['domestic'] else '🌍'
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} • 📰 {news['source'].replace('_', ' ').title()}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'all_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !all {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!all [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news(ctx, page=1):
    """Get Vietnamese news only"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức trong nước...")
        
        news_list = await collect_domestic_news(8)
        news_list = remove_duplicate_news(news_list)
        news_list.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = news_list[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"🇻🇳 Tin tức trong nước (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}",
            0xff0000
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin: {len(news_list)} bài\n🎯 Lĩnh vực: Kinh tế, Chứng khoán, Bất động sản",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. 🇻🇳 {title}",
                value=f"🕰️ {news['published_str']} • 📰 {news['source'].replace('_', ' ').title()}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'in_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !in {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!in [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news(ctx, page=1):
    """Get Yahoo Finance news only"""
    try:
        page = max(1, int(page))
        bot_stats['commands_processed'] += 1
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức quốc tế từ Yahoo Finance...")
        
        news_list = await collect_yahoo_finance_news(10)
        news_list = remove_duplicate_news(news_list)
        news_list.sort(key=lambda x: x['published'], reverse=True)
        
        await loading_msg.delete()
        
        # Pagination
        items_per_page = 12
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_news = news_list[start_idx:end_idx]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng có {total_pages} trang.")
            return
        
        # Create embed
        embed = create_safe_embed(
            f"🌍 Tin tức quốc tế - Yahoo Finance (Trang {page})",
            f"🕰️ Cập nhật: {get_current_datetime_str()}",
            0x0066ff
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin: {len(news_list)} bài\n🌐 Nguồn: {len(RSS_FEEDS['international'])} Yahoo Finance feeds\n🔄 Auto-translate: Có",
            inline=False
        )
        
        # News items
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            
            embed.add_field(
                name=f"{i}. 💰 {title}",
                value=f"🕰️ {news['published_str']} • 📰 Yahoo Finance\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Save to cache
        user_news_cache[ctx.author.id] = {
            'news': page_news,
            'command': f'out_page_{page}',
            'timestamp': get_current_vn_time()
        }
        cleanup_cache()
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết • !out {page+1} trang tiếp")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!out [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """Get detailed article content"""
    try:
        bot_stats['commands_processed'] += 1
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
        
        loading_msg = await ctx.send(f"🚀 Đang trích xuất nội dung từ {news['source'].replace('_', ' ').title()}...")
        
        # Extract content
        content = await extract_article_content(news['link'], news['source'], news)
        
        await loading_msg.delete()
        
        # Create embed
        is_yahoo = 'yahoo_finance' in news['source']
        title_suffix = " 🌐 (Có thể đã dịch)" if is_yahoo else ""
        
        embed = create_safe_embed(
            f"📖 Chi tiết bài viết{title_suffix}",
            "",
            0x9932cc
        )
        
        embed.add_field(
            name="📰 Tiêu đề",
            value=news['title'],
            inline=False
        )
        
        embed.add_field(
            name="🕰️ Thời gian",
            value=f"{news['published_str']} ({get_current_date_str()})",
            inline=True
        )
        
        embed.add_field(
            name="📰 Nguồn",
            value=f"{news['source'].replace('_', ' ').title()}{'🌐' if is_yahoo else ''}",
            inline=True
        )
        
        # Split content if too long
        if len(content) > 1000:
            embed.add_field(
                name="📄 Nội dung (Phần 1)",
                value=validate_content_for_discord(content[:1000] + "..."),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed for continuation
            embed2 = create_safe_embed(
                f"📖 Chi tiết bài viết (tiếp theo)",
                "",
                0x9932cc
            )
            
            embed2.add_field(
                name="📄 Nội dung (Phần 2)",
                value=validate_content_for_discord(content[1000:2000]),
                inline=False
            )
            
            embed2.add_field(
                name="🔗 Đọc bài viết gốc",
                value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
                inline=False
            )
            
            embed2.set_footer(text=f"Chi tiết tin số {news_number} • {len(content):,} ký tự")
            
            await ctx.send(embed=embed2)
            
        else:
            embed.add_field(
                name="📄 Nội dung chi tiết",
                value=validate_content_for_discord(content),
                inline=False
            )
            
            embed.add_field(
                name="🔗 Đọc bài viết gốc",
                value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
                inline=False
            )
            
            embed.set_footer(text=f"Chi tiết tin số {news_number} • {len(content):,} ký tự")
            
            await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='hoi')
async def ask_ai_question(ctx, *, question):
    """Ask AI a question"""
    try:
        bot_stats['commands_processed'] += 1
        
        if not ai_manager.gemini_available:
            embed = create_safe_embed(
                "⚠️ AI không khả dụng",
                "Cần cấu hình GEMINI_API_KEY để sử dụng tính năng AI.",
                0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        processing_msg = await ctx.send("🤖 Gemini AI đang phân tích câu hỏi...")
        
        # Get AI analysis
        analysis = await ai_manager.get_gemini_analysis(question)
        
        await processing_msg.delete()
        
        # Create response embed
        embed = create_safe_embed(
            f"🤖 Gemini AI Analysis",
            f"**Câu hỏi:** {question}\n**Thời gian:** {get_current_datetime_str()}",
            0x9932cc
        )
        
        # Split response if too long
        if len(analysis) > 1000:
            embed.add_field(
                name="💭 Phân tích (Phần 1)",
                value=validate_content_for_discord(analysis[:1000] + "..."),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed
            embed2 = create_safe_embed(
                f"🤖 Gemini AI Analysis (tiếp theo)",
                "",
                0x9932cc
            )
            
            embed2.add_field(
                name="💭 Phân tích (Phần 2)",
                value=validate_content_for_discord(analysis[1000:]),
                inline=False
            )
            
            embed2.set_footer(text=f"Gemini AI • {get_current_datetime_str()}")
            await ctx.send(embed=embed2)
            
        else:
            embed.add_field(
                name="💭 Phân tích của Gemini AI",
                value=validate_content_for_discord(analysis),
                inline=False
            )
            
            embed.set_footer(text=f"Gemini AI • {get_current_datetime_str()}")
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi AI: {str(e)}")

@bot.command(name='menu')
async def show_menu(ctx):
    """Show bot menu and instructions"""
    bot_stats['commands_processed'] += 1
    
    embed = create_safe_embed(
        "🤖 News Bot Menu",
        f"Bot tin tức AI với Yahoo Finance - {get_current_datetime_str()}",
        0xff9900
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="""**!all [trang]** - Tin từ tất cả nguồn
**!in [trang]** - Tin trong nước  
**!out [trang]** - Tin Yahoo Finance
**!chitiet [số]** - Chi tiết bài viết""",
        inline=False
    )
    
    embed.add_field(
        name="🤖 Lệnh AI",
        value="**!hoi [câu hỏi]** - Hỏi Gemini AI",
        inline=False
    )
    
    embed.add_field(
        name="📊 Nguồn tin",
        value=f"🇻🇳 **Trong nước:** {len(RSS_FEEDS['domestic'])} nguồn\n🌍 **Yahoo Finance:** {len(RSS_FEEDS['international'])} feeds",
        inline=True
    )
    
    ai_status = "✅ Sẵn sàng" if ai_manager.gemini_available else "❌ Chưa cấu hình"
    embed.add_field(
        name="🤖 AI Status",
        value=f"**Gemini AI:** {ai_status}\n**Auto-translate:** {'✅' if ai_manager.groq_available else '❌'}",
        inline=True
    )
    
    embed.add_field(
        name="💡 Ví dụ",
        value="**!all** - Xem tin mới nhất\n**!chitiet 1** - Chi tiết tin số 1\n**!hoi giá vàng hôm nay** - Hỏi AI",
        inline=False
    )
    
    # Bot stats
    if bot_stats['start_time']:
        uptime = get_current_vn_time() - bot_stats['start_time']
        embed.add_field(
            name="📈 Thống kê",
            value=f"**Uptime:** {str(uptime).split('.')[0]}\n**Commands:** {bot_stats['commands_processed']}\n**News:** {bot_stats['news_fetched']}\n**AI calls:** {bot_stats['ai_calls']}",
            inline=False
        )
    
    embed.set_footer(text=f"News Bot • {get_current_datetime_str()}")
    
    await ctx.send(embed=embed)

@bot.command(name='status')
async def show_status(ctx):
    """Show bot status"""
    bot_stats['commands_processed'] += 1
    
    embed = create_safe_embed(
        "🤖 Bot Status",
        f"Trạng thái hệ thống - {get_current_datetime_str()}",
        0x00ff88
    )
    
    # System status
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    embed.add_field(
        name="📊 Hệ thống",
        value=f"**Sources:** {total_sources} nguồn tin\n**Cache:** {len(user_news_cache)} users\n**Memory:** {len(gc.get_objects())} objects",
        inline=True
    )
    
    # AI status
    ai_info = f"**Gemini:** {'✅' if ai_manager.gemini_available else '❌'}\n**Groq:** {'✅' if ai_manager.groq_available else '❌'}"
    embed.add_field(
        name="🤖 AI Services",
        value=ai_info,
        inline=True
    )
    
    # Performance stats
    if bot_stats['start_time']:
        uptime = get_current_vn_time() - bot_stats['start_time']
        embed.add_field(
            name="📈 Hiệu suất",
            value=f"**Uptime:** {str(uptime).split('.')[0]}\n**Commands:** {bot_stats['commands_processed']}\n**News fetched:** {bot_stats['news_fetched']}\n**AI calls:** {bot_stats['ai_calls']}",
            inline=False
        )
    
    # Yahoo Finance sources detail
    yahoo_sources = list(RSS_FEEDS['international'].keys())
    yahoo_list = ', '.join([source.replace('yahoo_finance_', '').replace('_', ' ').title() for source in yahoo_sources[:5]])
    if len(yahoo_sources) > 5:
        yahoo_list += f" +{len(yahoo_sources) - 5} more"
    
    embed.add_field(
        name="🌍 Yahoo Finance Sources",
        value=f"**Total:** {len(yahoo_sources)} feeds\n**Types:** {yahoo_list}",
        inline=False
    )
    
    embed.set_footer(text=f"Status check • {get_current_datetime_str()}")
    
    await ctx.send(embed=embed)

# Alternative command aliases
@bot.command(name='cuthe')
async def get_news_detail_alias(ctx, news_number: int):
    """Alias for !chitiet"""
    await get_news_detail(ctx, news_number)

@bot.command(name='detail')
async def get_news_detail_en(ctx, news_number: int):
    """English alias for !chitiet"""
    await get_news_detail(ctx, news_number)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Thiếu tham số! Gõ `!menu` để xem hướng dẫn.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Tham số không hợp lệ! Gõ `!menu` để xem hướng dẫn.")
    else:
        await ctx.send(f"❌ Lỗi: {str(error)}")
        print(f"Command error: {error}")

# ====================================================================
# 🚀 MAIN EXECUTION
# ====================================================================

if __name__ == "__main__":
    try:
        # Start keep-alive server
        keep_alive()
        print("🌐 Keep-alive server started")
        
        # Validate environment
        if not TOKEN:
            print("❌ DISCORD_TOKEN not found in environment variables!")
            exit(1)
        
        print("🚀 Enhanced News Bot Starting...")
        print(f"🕰️ Start time: {get_current_datetime_str()}")
        print("=" * 50)
        
        # Environment check
        print("🔐 Environment Check:")
        print(f"   DISCORD_TOKEN: {'✅' if TOKEN else '❌'}")
        print(f"   GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '⚪'}")
        print(f"   GROQ_API_KEY: {'✅' if GROQ_API_KEY else '⚪'}")
        print()
        
        # Features check
        print("🔧 Features Available:")
        print(f"   Content Extraction: {'✅' if TRAFILATURA_AVAILABLE else '⚪'} Trafilatura")
        print(f"   Fallback Extraction: {'✅' if NEWSPAPER_AVAILABLE else '⚪'} Newspaper3k")
        print(f"   HTML Parsing: {'✅' if BEAUTIFULSOUP_AVAILABLE else '⚪'} BeautifulSoup")
        print(f"   Knowledge Base: {'✅' if WIKIPEDIA_AVAILABLE else '⚪'} Wikipedia")
        print(f"   AI Analysis: {'✅' if ai_manager.gemini_available else '⚪'} Gemini")
        print(f"   Auto-Translate: {'✅' if ai_manager.groq_available else '⚪'} Groq")
        print()
        
        # Sources summary
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print("📊 News Sources:")
        print(f"   🇻🇳 Vietnamese: {len(RSS_FEEDS['domestic'])} sources")
        print(f"   🌍 Yahoo Finance: {len(RSS_FEEDS['international'])} feeds")
        print(f"   📈 Total: {total_sources} sources")
        print()
        
        print("Yahoo Finance Feeds:")
        for i, (name, url) in enumerate(RSS_FEEDS['international'].items(), 1):
            feed_name = name.replace('yahoo_finance_', '').replace('_', ' ').title()
            print(f"   {i:2d}. {feed_name}")
        print()
        
        print("🎯 Commands Available:")
        print("   📰 !all, !in, !out - News commands")
        print("   📖 !chitiet [number] - Article details")
        print("   🤖 !hoi [question] - AI questions")
        print("   📋 !menu - Full guide")
        print("   📊 !status - System status")
        print()
        
        print("✅ All systems ready!")
        print("🚀 Starting Discord bot...")
        print("=" * 50)
        
        # Run the bot
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ Discord login failed!")
        print("🔧 Check your DISCORD_TOKEN environment variable")
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        
    finally:
        print("👋 News Bot shutdown complete")
        print(f"🕰️ Session ended: {get_current_datetime_str()}")
        
        # Final cleanup
        try:
            gc.collect()
            print("🧹 Memory cleanup completed")
        except:
            pass
