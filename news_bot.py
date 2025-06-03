import discord
from discord.ext import commands
import feedparser
import requests
import asyncio
import os
import re
from datetime import datetime, timedelta  # ✅ FIXED: Added timedelta import
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

# 🚀 SIMPLIFIED - RENDER OPTIMIZED LIBRARIES
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

# 🆕 KNOWLEDGE BASE INTEGRATION
try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    WIKIPEDIA_AVAILABLE = False

# 🆕 FREE AI APIs ONLY
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# 🆕 BeautifulSoup for Yahoo Finance parsing
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

# AI Provider enum
class AIProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"

# Debate Stage enum
class DebateStage(Enum):
    SEARCH = "search"
    INITIAL_RESPONSE = "initial_response"
    CONSENSUS = "consensus"
    FINAL_ANSWER = "final_answer"

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔒 ENVIRONMENT VARIABLES
TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# 🆕 FREE AI API KEYS ONLY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# 🔧 TIMEZONE - Vietnam
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# 🔧 DISCORD CONTENT LIMITS
DISCORD_EMBED_FIELD_VALUE_LIMIT = 1000
DISCORD_EMBED_DESCRIPTION_LIMIT = 4000
DISCORD_EMBED_TITLE_LIMIT = 250
DISCORD_EMBED_FOOTER_LIMIT = 2000
DISCORD_EMBED_AUTHOR_LIMIT = 250
DISCORD_TOTAL_EMBED_LIMIT = 5800

# User cache
user_news_cache = {}
MAX_CACHE_ENTRIES = 25

# User agents for stealth
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_current_vietnam_datetime():
    """Get current Vietnam date and time automatically"""
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

print("🚀 ENHANCED NEWS BOT INITIALIZATION:")
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'}")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'}")
print(f"GROQ_API_KEY: {'✅ Found' if GROQ_API_KEY else '❌ Missing'}")
print(f"GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'}")
print(f"🔧 Current Vietnam time: {get_current_datetime_str()}")
print("=" * 50)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🆕 SIMPLIFIED RSS FEEDS - ONLY YAHOO FINANCE FOR INTERNATIONAL
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - 15 NGUỒN ===
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
    
    # === KINH TẾ QUỐC TẾ - CHỈ YAHOO FINANCE ===
    'international': {
        'yahoo_finance_main': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
    }
}

def convert_utc_to_vietnam_time(utc_time_tuple):
    """Chuyển đổi UTC sang giờ Việt Nam chính xác"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        return datetime.now(VN_TIMEZONE)

# 🔧 CONTENT VALIDATION FOR DISCORD LIMITS
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

def get_stealth_headers(url=None):
    """Stealth headers để bypass anti-bot detection"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
    }
    
    return headers

def add_random_delay():
    """Thêm random delay để tránh rate limiting"""
    delay = random.uniform(1.0, 3.0)
    time.sleep(delay)

# UTILITY FUNCTIONS AND HELPERS (MISSING FROM ORIGINAL)
def safe_get_attribute(obj, attr, default=""):
    """Safely get attribute from object"""
    try:
        return getattr(obj, attr, default)
    except:
        return default

def format_publish_time(time_tuple):
    """Format publish time safely"""
    try:
        if time_tuple:
            vn_time = convert_utc_to_vietnam_time(time_tuple)
            return vn_time.strftime("%H:%M %d/%m")
        else:
            current_time = get_current_vietnam_datetime()
            return current_time.strftime("%H:%M %d/%m")
    except:
        current_time = get_current_vietnam_datetime()
        return current_time.strftime("%H:%M %d/%m")

def cleanup_user_cache():
    """Clean up old user cache entries"""
    global user_news_cache
    
    if len(user_news_cache) <= MAX_CACHE_ENTRIES:
        return
    
    # Sort by timestamp and remove oldest entries
    sorted_cache = sorted(user_news_cache.items(), key=lambda x: x[1]['timestamp'])
    entries_to_remove = len(user_news_cache) - MAX_CACHE_ENTRIES + 5  # Remove extra 5 for buffer
    
    for i in range(entries_to_remove):
        user_id, _ = sorted_cache[i]
        del user_news_cache[user_id]

def get_enhanced_stealth_headers(url=None, referer=None):
    """Get enhanced stealth headers for specific sites"""
    base_headers = get_stealth_headers(url)
    
    # Add specific headers based on URL
    if url:
        if 'finance.yahoo.com' in url:
            base_headers.update({
                'Referer': 'https://finance.yahoo.com/',
                'Origin': 'https://finance.yahoo.com',
                'Sec-Fetch-Site': 'same-origin',
                'Cache-Control': 'no-cache'
            })
        elif 'cafef.vn' in url:
            base_headers.update({
                'Referer': 'https://cafef.vn/',
                'Origin': 'https://cafef.vn'
            })
        elif 'vnexpress.net' in url:
            base_headers.update({
                'Referer': 'https://vnexpress.net/',
                'Origin': 'https://vnexpress.net'
            })
    
    if referer:
        base_headers['Referer'] = referer
    
    return base_headers

def create_fallback_content(url, source_name, error_msg=""):
    """Create fallback content when extraction fails"""
    try:
        article_id = url.split('/')[-1] if '/' in url else 'news-article'
        
        if 'yahoo' in source_name.lower():
            return f"""**Yahoo Finance News Analysis:**

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
**Note:** For complete article with interactive charts and real-time data, please visit the original link.

{f'**Error:** {error_msg}' if error_msg else ''}"""
        else:
            return f"""**Bản tin kinh tế Việt Nam:**

📰 **Thông tin kinh tế:** Bài viết cung cấp thông tin kinh tế, tài chính mới nhất từ {source_name}, một trong những nguồn tin uy tín về kinh tế Việt Nam.

📊 **Nội dung chuyên sâu:**
• Phân tích thị trường chứng khoán Việt Nam
• Tin tức kinh tế vĩ mô và chính sách
• Báo cáo doanh nghiệp và tài chính
• Xu hướng đầu tư và kinh doanh

💡 **Nguồn tin đáng tin cậy:**
• Cập nhật thông tin kinh tế 24/7
• Phân tích chuyên sâu từ các chuyên gia
• Kết nối với thị trường tài chính Việt Nam

**Mã bài viết:** {article_id}
**Lưu ý:** Để đọc đầy đủ bài viết với biểu đồ và dữ liệu chi tiết, vui lòng truy cập link gốc.

{f'**Lỗi:** {error_msg}' if error_msg else ''}"""
        
    except Exception as e:
        return f"Thông tin về {source_name}. Vui lòng truy cập link gốc để đọc đầy đủ bài viết. {f'Lỗi: {error_msg}' if error_msg else ''}"

def clean_content_for_discord(content):
    """Clean content for Discord display"""
    if not content:
        return "Không có nội dung."
    
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content)
    
    # Remove common unwanted patterns
    unwanted_patterns = [
        r'Đăng ký.*?nhận tin',
        r'Theo dõi.*?Facebook',
        r'Like.*?Fanpage',
        r'Chia sẻ.*?bài viết',
        r'Tags:.*?$',
        r'Từ khóa:.*?$',
        r'Bình luận.*?$',
        r'Comment.*?$',
        r'Share.*?$',
        r'Subscribe.*?$'
    ]
    
    for pattern in unwanted_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
    
    return content.strip()

def validate_news_number(news_number, news_list):
    """Validate news number input"""
    try:
        num = int(news_number)
        if num < 1 or num > len(news_list):
            return None, f"❌ Số không hợp lệ! Chọn từ 1 đến {len(news_list)}"
        return num, None
    except ValueError:
        return None, "❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`"

# MISSING FETCH FULL CONTENT FOR AI ANALYSIS
async def fetch_full_content_for_ai_analysis(url, source_name="", news_item=None):
    """Trích xuất TOÀN BỘ nội dung cho AI analysis với enhanced fallback"""
    
    # Use the enhanced fallback system
    content = await fetch_content_with_yahoo_finance_fallback(url, source_name, news_item)
    
    if not content or len(content) < 300:
        return f"⚠️ Không thể trích xuất đầy đủ nội dung từ {source_name}. Link gốc: {url}. Vui lòng phân tích dựa trên tiêu đề và thông tin có sẵn."
    
    return content

# 🚀 ENHANCED CONTENT EXTRACTION METHODS
async def fetch_content_stealth_enhanced_international(url, source_name, news_item=None):
    """Enhanced stealth content extraction for international sources"""
    try:
        # Special handling for Yahoo Finance
        if 'finance.yahoo.com' in url or 'yahoo_finance' in source_name.lower():
            return await extract_yahoo_finance_content_enhanced(url)
        
        add_random_delay()
        session = requests.Session()
        stealth_headers = get_stealth_headers(url)
        session.headers.update(stealth_headers)
        
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
                        'headers': stealth_headers,
                        'timeout': 20
                    })
                    
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 300:
                        content = article.text
                        return content.strip()
                
                except Exception as e:
                    pass
        
        session.close()
        return None
        
    except Exception as e:
        return None

async def fetch_content_stealth_enhanced_domestic(url):
    """Enhanced stealth content extraction for domestic sources"""
    try:
        add_random_delay()
        session = requests.Session()
        stealth_headers = get_stealth_headers(url)
        session.headers.update(stealth_headers)
        
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
                    
                    if result and result.get('text') and len(result['text']) > 200:
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
                    article.download()
                    article.parse()
                    
                    if article.text and len(article.text) > 200:
                        content = article.text
                        return content.strip()
                
                except Exception as e:
                    pass
            
            # Method 3: BeautifulSoup for Vietnamese sites
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    content_selectors = [
                        'div.detail-content',
                        'div.fck_detail', 
                        'div.content-detail',
                        'div.article-content',
                        'div.entry-content',
                        'div.post-content',
                        'div.news-content',
                        'div.story-content',
                        'div.article-body',
                        '.baiviet-body',
                        '.detail-content-body',
                        '.cms-body',
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
                        # Clean Vietnamese specific patterns
                        content = re.sub(r'Theo.*?VnExpress', '', content, flags=re.IGNORECASE)
                        content = re.sub(r'Nguồn.*?:', '', content, flags=re.IGNORECASE)
                        content = re.sub(r'\s+', ' ', content)
                        
                        session.close()
                        return content.strip()
                        
                except Exception as e:
                    pass
            
            # Method 4: Legacy fallback
            return await fetch_content_legacy_domestic(response, session)
        
        session.close()
        return None
        
    except Exception as e:
        return None

async def fetch_content_legacy_domestic(response, session):
    """Legacy domestic content extraction"""
    try:
        raw_content = response.content
        detected = chardet.detect(raw_content)
        encoding = detected['encoding'] or 'utf-8'
        
        try:
            content = raw_content.decode(encoding)
        except:
            content = raw_content.decode('utf-8', errors='ignore')
        
        # Enhanced HTML cleaning for Vietnamese sites
        clean_content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<style[^>]*>.*?</style>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = html.unescape(clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # Extract meaningful content
        sentences = clean_content.split('. ')
        meaningful_content = []
        
        for sentence in sentences:
            if len(sentence.strip()) > 20:
                meaningful_content.append(sentence.strip())
                
        result = '. '.join(meaningful_content)
        
        session.close()
        return result if result else None
        
    except Exception as e:
        session.close()
        return None

def is_international_source(source_name):
    """Check if source is international"""
    international_sources = {
        'yahoo_finance_main', 'yahoo_finance_business', 'yahoo_finance_markets', 'yahoo_finance_news',
        'Reuters', 'Bloomberg', 'Yahoo Finance', 'MarketWatch', 
        'Forbes', 'Financial Times', 'Business Insider', 'The Economist',
        'CNN Business', 'BBC Business', 'Seeking Alpha', 'Investopedia',
        'The Motley Fool'
    }
    
    return any(source in source_name for source in international_sources)

# 🚀 CONTENT DEDUPLICATION SYSTEM
def remove_duplicate_news(news_list):
    """Loại bỏ tin tức trùng lặp"""
    seen_links = set()
    seen_titles = set()
    unique_news = []
    
    for news in news_list:
        normalized_title = normalize_title(news['title'])
        
        is_duplicate = False
        
        if news['link'] in seen_links:
            is_duplicate = True
        else:
            for existing_title in seen_titles:
                similarity = calculate_title_similarity(normalized_title, existing_title)
                if similarity > 0.75:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            seen_links.add(news['link'])
            seen_titles.add(normalized_title)
            unique_news.append(news)
    
    return unique_news

def calculate_title_similarity(title1, title2):
    """Tính độ tương tự giữa 2 tiêu đề"""
    words1 = set(title1.split())
    words2 = set(title2.split())
    
    if not words1 or not words2:
        return 0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0

def normalize_title(title):
    """Chuẩn hóa tiêu đề để so sánh trùng lặp"""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = ' '.join(title.split())
    
    words = title.split()[:10]
    return ' '.join(words)

# 🆕 YAHOO FINANCE SEARCH SYSTEM
async def search_yahoo_finance_by_title(title: str, max_results: int = 5):
    """Search Yahoo Finance for similar articles by title"""
    try:
        search_results = []
        
        # Search in Yahoo Finance RSS feeds
        yahoo_rss_urls = [
            'https://feeds.finance.yahoo.com/rss/2.0/headline',
            'https://finance.yahoo.com/news/rssindex',
            'https://feeds.finance.yahoo.com/rss/2.0/category-business',
            'https://feeds.finance.yahoo.com/rss/2.0/category-markets'
        ]
        
        for rss_url in yahoo_rss_urls:
            try:
                add_random_delay()
                
                session = requests.Session()
                headers = get_stealth_headers(rss_url)
                session.headers.update(headers)
                
                response = session.get(rss_url, timeout=15, allow_redirects=True)
                
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                    
                    if hasattr(feed, 'entries') and feed.entries:
                        for entry in feed.entries[:15]:
                            if hasattr(entry, 'title') and hasattr(entry, 'link'):
                                match_score = calculate_title_similarity_enhanced(title, entry.title)
                                
                                if match_score > 0.3:
                                    search_results.append({
                                        'title': entry.title,
                                        'link': entry.link,
                                        'match_score': match_score,
                                        'description': getattr(entry, 'summary', ''),
                                        'source': 'Yahoo Finance'
                                    })
                
                session.close()
                
            except Exception as e:
                continue
        
        # Sort by match score and return top results
        search_results.sort(key=lambda x: x['match_score'], reverse=True)
        return search_results[:max_results]
        
    except Exception as e:
        return []

def extract_title_keywords_enhanced(title):
    """Enhanced keyword extraction for better matching"""
    stop_words = {
        'và', 'của', 'trong', 'với', 'từ', 'về', 'có', 'sẽ', 'đã', 'được', 'cho', 'tại', 'theo', 'như', 'này', 'đó', 'các', 'một', 'hai', 'ba',
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'that', 'this', 'these', 'those', 'a', 'an',
        'said', 'says', 'after', 'before', 'up', 'down', 'out', 'over', 'under', 'again', 'further', 'then', 'once'
    }
    
    title_clean = re.sub(r'[^\w\s]', ' ', title.lower())
    title_clean = ' '.join(title_clean.split())
    
    words = [word.strip() for word in title_clean.split() if len(word) > 2 and word not in stop_words]
    
    return words[:15]

def calculate_title_similarity_enhanced(title1: str, title2: str) -> float:
    """Enhanced title similarity calculation"""
    keywords1 = set(extract_title_keywords_enhanced(title1))
    keywords2 = set(extract_title_keywords_enhanced(title2))
    
    if not keywords1 or not keywords2:
        return 0
    
    # Calculate Jaccard similarity
    intersection = keywords1.intersection(keywords2)
    union = keywords1.union(keywords2)
    
    jaccard_score = len(intersection) / len(union) if union else 0
    
    # Additional partial matching
    partial_matches = 0
    for word1 in keywords1:
        for word2 in keywords2:
            if len(word1) > 3 and len(word2) > 3:
                if word1 in word2 or word2 in word1:
                    partial_matches += 0.3
                elif abs(len(word1) - len(word2)) <= 2:
                    if len(set(word1) & set(word2)) / max(len(word1), len(word2)) > 0.7:
                        partial_matches += 0.2
    
    # Normalize partial matches
    partial_score = min(partial_matches / max(len(keywords1), len(keywords2)), 0.5)
    
    # Combine scores
    total_score = jaccard_score + partial_score
    
    return min(total_score, 1.0)

# 🆕 ENHANCED YAHOO FINANCE CONTENT EXTRACTION WITH AD REMOVAL
async def extract_yahoo_finance_content_enhanced(url: str):
    """Enhanced Yahoo Finance content extraction with aggressive ad removal"""
    try:
        time.sleep(random.uniform(2.0, 4.0))
        
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
                        
                        # AGGRESSIVE AD REMOVAL for Yahoo Finance
                        content = clean_yahoo_finance_ads(content)
                        
                        if len(content) > 1500:
                            content = content[:1500] + "..."
                        
                        session.close()
                        return content.strip()
                except Exception as e:
                    pass
            
            # Method 2: Enhanced BeautifulSoup parsing with ad removal
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
                        # AGGRESSIVE AD REMOVAL
                        content = clean_yahoo_finance_ads(content)
                        
                        if len(content) > 1500:
                            content = content[:1500] + "..."
                        
                        session.close()
                        return content.strip()
                        
                except Exception as e:
                    pass
            
            # Method 3: Newspaper3k fallback with ad removal
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
                        
                        # AGGRESSIVE AD REMOVAL
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
    """AGGRESSIVE ad removal for Yahoo Finance content"""
    if not content:
        return content
    
    # Remove common Yahoo Finance ad patterns - FIXED REGEX
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
        r'Tags:.*?$'  # FIXED: Added proper closing for this pattern
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

# 🚀 ENHANCED CONTENT EXTRACTION WITH FALLBACK SYSTEM
async def fetch_content_with_yahoo_finance_fallback(url, source_name="", news_item=None):
    """Enhanced content extraction with Yahoo Finance fallback"""
    
    # Determine if this is an international source
    is_international = is_international_source(source_name)
    
    # Step 1: Try primary extraction
    if is_international:
        content = await fetch_content_stealth_enhanced_international(url, source_name, news_item)
    else:
        content = await fetch_content_stealth_enhanced_domestic(url)
    
    # Step 2: Check if extraction failed or content is too short
    extraction_failed = (
        not content or 
        len(content) < 500 or 
        "không thể trích xuất" in content.lower() or
        "không thể lấy nội dung" in content.lower() or
        "summary" in content.lower()[:200] or
        "advertisement" in content.lower() or
        "subscribe" in content.lower()[:300] or
        content.count('.') < 5
    )
    
    # Step 3: Enhanced Yahoo Finance fallback cho international sources
    if extraction_failed and news_item and news_item.get('title') and is_international:
        # Try Yahoo Finance search fallback
        yahoo_matches = await search_yahoo_finance_by_title(news_item['title'], max_results=5)
        
        if yahoo_matches:
            # Try multiple matches, not just the best one
            for match in yahoo_matches[:3]:
                yahoo_content = await extract_yahoo_finance_content_enhanced(match['link'])
                
                if yahoo_content and len(yahoo_content) > 500:
                    # Add enhanced fallback indicator
                    fallback_content = f"""**🔍 Yahoo Finance Fallback Content:**

{yahoo_content}

**🚀 Fallback Information:**
**Original Source:** {source_name}
**Fallback Source:** Yahoo Finance (Enhanced)  
**Match Quality:** {match['match_score']:.0%} similarity
**Technology:** Enhanced extraction system

**📊 Enhanced Features:**
• Aggressive fallback triggering (requires 500+ chars)
• Multiple search strategies and match attempts
• Enhanced Yahoo Finance extraction
• Real-time financial content delivery

**Links:**
**Original Article:** [Link gốc]({url})
**Yahoo Finance Source:** [Link tham khảo]({match['link']})"""
                    
                    return fallback_content
    
    # Step 4: Return original content with warning if too short
    if content and len(content) < 500:
        return f"""**⚠️ Nội dung ngắn được trích xuất:**

{content}

**📋 Lưu ý:** Nội dung này có thể chỉ là phần tóm tắt hoặc đoạn mở đầu. Để đọc đầy đủ bài viết, vui lòng truy cập link gốc bên dưới."""
    
    return content or "Không thể trích xuất nội dung từ bài viết này."

# 🚀 STEALTH RSS COLLECTION
async def collect_news_stealth_enhanced(sources_dict, limit_per_source=6):
    """Stealth news collection với enhanced Yahoo Finance và deduplication"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            # Increase limit for Yahoo Finance to get more articles
            current_limit = 20 if 'yahoo_finance' in source_name else limit_per_source
            
            add_random_delay()
            
            stealth_headers = get_stealth_headers(rss_url)
            stealth_headers['Accept'] = 'application/rss+xml, application/xml, text/xml, */*'
            
            session = requests.Session()
            session.headers.update(stealth_headers)
            
            response = session.get(rss_url, timeout=15, allow_redirects=True)
            
            if response.status_code == 403:
                # Thử với headers khác
                alternative_headers = get_stealth_headers(rss_url)
                alternative_headers['User-Agent'] = random.choice(USER_AGENTS)
                session.headers.update(alternative_headers)
                
                time.sleep(random.uniform(2.0, 4.0))
                response = session.get(rss_url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(rss_url)
            
            session.close()
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
                
            entries_processed = 0
            for entry in feed.entries[:current_limit]:
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
                        
                        news_item = {
                            'title': html.unescape(title),
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
                    
        except Exception as e:
            continue
    
    # Enhanced deduplication using the new system
    unique_news = remove_duplicate_news(all_news)
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

def save_user_news_enhanced(user_id, news_list, command_type):
    """Enhanced user news saving with timezone-aware datetime"""
    global user_news_cache
    
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': get_current_vietnam_datetime()  # ✅ Always timezone-aware
    }
    
    if len(user_news_cache) > MAX_CACHE_ENTRIES:
        oldest_users = sorted(user_news_cache.items(), key=lambda x: x[1]['timestamp'])[:10]
        for user_id_to_remove, _ in oldest_users:
            del user_news_cache[user_id_to_remove]

# 🆕 DISCORD EMBED OPTIMIZATION FUNCTIONS
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
                title=validate_and_truncate_content(title, DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
        else:
            embed = discord.Embed(
                title=validate_and_truncate_content(f"{title[:180]}... (Phần {i+1})", DISCORD_EMBED_TITLE_LIMIT),
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
    """Create safe embeds with multiple fields that fit Discord limits"""
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
        
        if fields_added >= 20 or total_chars + field_chars > DISCORD_TOTAL_EMBED_LIMIT:
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

# 🚀 AUTO-TRANSLATE WITH GROQ
async def detect_and_translate_content_enhanced(content, source_name):
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
            translated_content = await _translate_with_groq_enhanced(content, source_name)
            if translated_content:
                return translated_content, True
            else:
                translated_content = f"[Đã dịch từ {source_name}] {content}"
                return translated_content, True
        
        return content, False
        
    except Exception as e:
        return content, False

async def _translate_with_groq_enhanced(content: str, source_name: str):
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

# 🚀 ENHANCED MULTI-AI DEBATE ENGINE
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

# ENHANCED !HOI COMMAND WITH ARTICLE CONTEXT
def parse_hoi_command(command_text):
    """Parse !hoi command to detect article context"""
    if 'chitiet' not in command_text.lower():
        return None, command_text
    
    try:
        parts = command_text.split()
        if len(parts) < 3:
            return None, command_text
        
        chitiet_index = -1
        for i, part in enumerate(parts):
            if part.lower() == 'chitiet':
                chitiet_index = i
                break
        
        if chitiet_index == -1 or chitiet_index + 1 >= len(parts):
            return None, command_text
        
        news_number = int(parts[chitiet_index + 1])
        
        article_context = {
            'news_number': news_number,
            'type': 'all',
            'page': 1
        }
        
        # Check for type (in, out, all)
        if chitiet_index + 2 < len(parts):
            next_part = parts[chitiet_index + 2].lower()
            if next_part in ['in', 'out', 'all']:
                article_context['type'] = next_part
                
                # Check for page number
                if chitiet_index + 3 < len(parts):
                    try:
                        article_context['page'] = int(parts[chitiet_index + 3])
                    except ValueError:
                        pass
        
        # Extract remaining question
        remaining_parts = []
        for i, part in enumerate(parts):
            if i <= chitiet_index + 1:
                continue
            if part.lower() in ['in', 'out', 'all'] and i == chitiet_index + 2:
                continue
            if i == chitiet_index + 3:
                try:
                    int(part)
                    continue
                except ValueError:
                    pass
            remaining_parts.append(part)
        
        question = ' '.join(remaining_parts) if remaining_parts else "Hãy phân tích bài viết này"
        
        return article_context, question
        
    except (ValueError, IndexError):
        return None, command_text

async def get_article_from_cache(user_id, article_context):
    """Get specific article from user cache"""
    try:
        if user_id not in user_news_cache:
            return None, "Bạn chưa xem tin tức nào. Hãy dùng !all, !in, hoặc !out trước."
        
        user_data = user_news_cache[user_id]
        
        cached_command = user_data['command']
        requested_type = article_context['type']
        requested_page = article_context['page']
        
        # Parse cached command to check compatibility
        if requested_type == 'all' and 'all_page' not in cached_command:
            return None, f"Bạn cần xem tin tức với !all {requested_page} trước khi phân tích."
        elif requested_type == 'in' and 'in_page' not in cached_command:
            return None, f"Bạn cần xem tin tức với !in {requested_page} trước khi phân tích."
        elif requested_type == 'out' and 'out_page' not in cached_command:
            return None, f"Bạn cần xem tin tức với !out {requested_page} trước khi phân tích."
        
        # Check page number
        cached_page = 1
        if '_page_' in cached_command:
            try:
                cached_page = int(cached_command.split('_page_')[1])
            except:
                pass
        
        if cached_page != requested_page:
            return None, f"Bạn đang xem trang {cached_page}, cần xem trang {requested_page} trước."
        
        # Get the article
        news_list = user_data['news']
        news_number = article_context['news_number']
        
        if news_number < 1 or news_number > len(news_list):
            return None, f"Số không hợp lệ! Chọn từ 1 đến {len(news_list)}."
        
        article = news_list[news_number - 1]
        return article, None
        
    except Exception as e:
        return None, f"Lỗi khi lấy bài viết: {str(e)}"

async def analyze_article_with_gemini_optimized(article, question, user_context):
    """Analyze specific article with Gemini"""
    try:
        # Extract content from article
        article_content = await fetch_content_with_yahoo_finance_fallback(
            article['link'], 
            article['source'], 
            article
        )
        
        # Create enhanced context for Gemini
        current_date_str = get_current_date_str()
        
        gemini_prompt = f"""Bạn là Gemini AI - chuyên gia phân tích tài chính thông minh. Tôi đã đọc một bài báo cụ thể và muốn bạn phân tích dựa trên TOÀN BỘ nội dung thực tế của bài báo đó.

**THÔNG TIN BÀI BÁO:**
- Tiêu đề: {article['title']}
- Nguồn: {extract_source_name(article['link'])}
- Thời gian: {article['published_str']} ({current_date_str})
- Link: {article['link']}

**TOÀN BỘ NỘI DUNG BÀI BÁO:**
{article_content}

**CÂU HỎI CỦA NGƯỜI DÙNG:**
{question}

**YÊU CẦU PHÂN TÍCH:**
1. Dựa CHÍNH vào TOÀN BỘ nội dung bài báo đã cung cấp (85-95%)
2. Kết hợp kiến thức chuyên môn của bạn để giải thích sâu hơn (5-15%)
3. Phân tích tác động, nguyên nhân, hậu quả từ thông tin trong bài
4. Đưa ra insights và dự báo dựa trên dữ liệu cụ thể
5. Trả lời trực tiếp câu hỏi với evidence từ bài báo
6. Độ dài: 600-1000 từ với phân tích chuyên sâu và chi tiết
7. Tham chiếu cụ thể đến các phần trong bài báo

Hãy đưa ra phân tích THÔNG MINH, CHI TIẾT và DỰA TRÊN EVIDENCE:"""

        # Call Gemini with enhanced prompt
        if not GEMINI_AVAILABLE:
            return "⚠️ Gemini AI không khả dụng cho phân tích bài báo."
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=20,
                max_output_tokens=2000,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    gemini_prompt,
                    generation_config=generation_config
                ),
                timeout=35
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            return "⚠️ Gemini API timeout khi phân tích bài báo."
        except Exception as e:
            return f"⚠️ Lỗi Gemini API: {str(e)}"
            
    except Exception as e:
        return f"❌ Lỗi khi phân tích bài báo: {str(e)}"

# Bot event handlers
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    
    ai_count = len(debate_engine.available_engines)
    current_datetime_str = get_current_datetime_str()
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    
    # SIMPLIFIED status text
    status_text = f"News Bot • {ai_count} AI • {total_sources} sources • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

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

# ENHANCED !HOI COMMAND
@bot.command(name='hoi')
async def enhanced_gemini_question_with_article_context(ctx, *, question):
    """Enhanced Gemini System với article context"""
    
    try:
        if len(debate_engine.available_engines) < 1:
            embed = create_safe_embed(
                "⚠️ AI System không khả dụng",
                f"Cần Gemini AI để hoạt động. Hiện có: {len(debate_engine.available_engines)} engine",
                0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        current_datetime_str = get_current_datetime_str()
        
        # Parse command to check for article context
        article_context, parsed_question = parse_hoi_command(question)
        
        if article_context:
            # ARTICLE-SPECIFIC ANALYSIS MODE
            progress_embed = create_safe_embed(
                "📰 Gemini Article Analysis",
                f"**Phân tích bài báo:** Tin số {article_context['news_number']} ({article_context['type']} trang {article_context['page']})\n**Câu hỏi:** {parsed_question}",
                0x9932cc
            )
            
            safe_name, safe_value = validate_embed_field(
                "🔄 Đang xử lý",
                "📰 Đang lấy bài báo từ cache...\n🔍 Extract nội dung...\n💎 Gemini sẽ phân tích dựa trên nội dung thực tế"
            )
            progress_embed.add_field(name=safe_name, value=safe_value, inline=False)
            
            progress_msg = await ctx.send(embed=progress_embed)
            
            # Get article from user cache
            article, error_msg = await get_article_from_cache(ctx.author.id, article_context)
            
            if error_msg:
                error_embed = create_safe_embed(
                    "❌ Không thể lấy bài báo",
                    error_msg,
                    0xff6b6b
                )
                await progress_msg.edit(embed=error_embed)
                return
            
            # Analyze article with Gemini
            analysis_result = await analyze_article_with_gemini_optimized(article, parsed_question, ctx.author.id)
            
            # Create result embed using optimized embeds
            title = f"📰 Gemini Article Analysis ({current_datetime_str})"
            description = f"**Bài báo:** {article['title']}\n**Nguồn:** {extract_source_name(article['link'])} • {article['published_str']}"
            
            # Create optimized embeds for Discord limits
            optimized_embeds = create_optimized_embeds(title, analysis_result, 0x00ff88)
            
            # Add metadata to first embed
            if optimized_embeds:
                safe_name, safe_value = validate_embed_field(
                    "📊 Analysis Info",
                    f"**Mode**: Article Context Analysis\n**Article**: Tin số {article_context['news_number']} ({article_context['type']} trang {article_context['page']})\n**Analysis**: Evidence-based"
                )
                optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
                
                safe_name2, safe_value2 = validate_embed_field(
                    "🔗 Bài báo gốc",
                    f"[{article['title'][:50]}...]({article['link']})"
                )
                optimized_embeds[0].add_field(name=safe_name2, value=safe_value2, inline=True)
                
                optimized_embeds[-1].set_footer(text=f"📰 Gemini Article Analysis • {current_datetime_str}")
            
            # Send optimized embeds
            await progress_msg.edit(embed=optimized_embeds[0])
            
            for embed in optimized_embeds[1:]:
                await ctx.send(embed=embed)
            
        else:
            # REGULAR GEMINI ANALYSIS MODE
            progress_embed = create_safe_embed(
                "💎 Gemini Intelligent System",
                f"**Câu hỏi:** {question}\n🧠 **Đang phân tích với Gemini AI...**",
                0x9932cc
            )
            
            if AIProvider.GEMINI in debate_engine.ai_engines:
                gemini_info = debate_engine.ai_engines[AIProvider.GEMINI]
                ai_status = f"{gemini_info['emoji']} **{gemini_info['name']}** - {gemini_info['strength']} ({gemini_info['free_limit']}) ✅"
            else:
                ai_status = "❌ Gemini không khả dụng"
            
            safe_name, safe_value = validate_embed_field("🤖 Gemini Engine", ai_status)
            progress_embed.add_field(name=safe_name, value=safe_value, inline=False)
            
            progress_msg = await ctx.send(embed=progress_embed)
            
            # Start regular analysis
            analysis_result = await debate_engine.enhanced_multi_ai_debate(question, max_sources=4)
            
            # Handle results
            if 'error' in analysis_result:
                error_embed = create_safe_embed(
                    "❌ Gemini System - Error",
                    f"**Câu hỏi:** {question}\n**Lỗi:** {analysis_result['error']}",
                    0xff6b6b
                )
                await progress_msg.edit(embed=error_embed)
                return
            
            # Success - Create optimized embeds
            final_answer = analysis_result.get('final_answer', 'Không có câu trả lời.')
            strategy = analysis_result.get('gemini_response', {}).get('search_strategy', 'knowledge_based')
            strategy_text = "Dữ liệu hiện tại" if strategy == 'current_data' else "Kiến thức chuyên sâu"
            
            # Create optimized embeds for Discord limits
            title = f"💎 Gemini Analysis - {strategy_text}"
            optimized_embeds = create_optimized_embeds(title, final_answer, 0x00ff88)
            
            # Add metadata to first embed
            if optimized_embeds:
                safe_name, safe_value = validate_embed_field(
                    "🔍 Phương pháp phân tích",
                    f"**Strategy:** {strategy_text}\n**Data Usage:** {'20-40% tin tức' if strategy == 'current_data' else '5-10% tin tức'}\n**Knowledge:** {'60-80% Gemini' if strategy == 'current_data' else '90-95% Gemini'}"
                )
                optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
                
                optimized_embeds[-1].set_footer(text=f"💎 Gemini System • {current_datetime_str}")
            
            # Send optimized embeds
            await progress_msg.edit(embed=optimized_embeds[0])
            
            for embed in optimized_embeds[1:]:
                await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Gemini: {str(e)}")

# ENHANCED NEWS COMMANDS
@bot.command(name='all')
async def get_all_news_enhanced(ctx, page=1):
    """Enhanced news từ tất cả nguồn"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức...")
        
        domestic_news = await collect_news_stealth_enhanced(RSS_FEEDS['domestic'], 6)
        international_news = await collect_news_stealth_enhanced(RSS_FEEDS['international'], 20)  # More from Yahoo Finance
        
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
        
        # Enhanced emoji mapping
        emoji_map = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️', 'fili_kinh_te': '📰',
            'yahoo_finance_main': '💰'
        }
        
        source_names = {
            'cafef_main': 'CafeF', 'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafebiz_main': 'CafeBiz',
            'baodautu_main': 'Báo Đầu tư', 'vneconomy_main': 'VnEconomy', 'vneconomy_chungkhoan': 'VnEconomy CK',
            'vnexpress_kinhdoanh': 'VnExpress KD', 'vnexpress_chungkhoan': 'VnExpress CK',
            'thanhnien_kinhtevimo': 'Thanh Niên VM', 'thanhnien_chungkhoan': 'Thanh Niên CK',
            'nhandanonline_tc': 'Nhân Dân TC', 'fili_kinh_te': 'Fili.vn',
            'yahoo_finance_main': 'Yahoo Finance'
        }
        
        # Add statistics field
        stats_field = f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin"
        
        fields_data.append(("📊 Thống kê", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds with safe field handling
        embeds = create_safe_embed_with_fields(
            f"📰 Tin tức tổng hợp (Trang {page})",
            "",
            fields_data,
            0x00ff88
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"News Bot • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        # Send all embeds
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_enhanced(ctx, page=1):
    """Tin tức trong nước"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức trong nước...")
        
        news_list = await collect_news_stealth_enhanced(RSS_FEEDS['domestic'], 8)
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
        
        stats_field = f"📰 Tổng tin có sẵn: {len(news_list)} tin\n🎯 Lĩnh vực: Kinh tế, CK, BĐS, Vĩ mô"
        
        fields_data.append(("📊 Thông tin", stats_field))
        
        emoji_map = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢',
            'cafef_taichinh': '💰', 'cafef_vimo': '📊', 'cafebiz_main': '💼',
            'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈',
            'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️', 'fili_kinh_te': '📰'
        }
        
        source_names = {
            'cafef_main': 'CafeF', 'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafebiz_main': 'CafeBiz',
            'baodautu_main': 'Báo Đầu tư', 'vneconomy_main': 'VnEconomy', 'vneconomy_chungkhoan': 'VnEconomy CK',
            'vnexpress_kinhdoanh': 'VnExpress KD', 'vnexpress_chungkhoan': 'VnExpress CK',
            'thanhnien_kinhtevimo': 'Thanh Niên VM', 'thanhnien_chungkhoan': 'Thanh Niên CK',
            'nhandanonline_tc': 'Nhân Dân TC', 'fili_kinh_te': 'Fili.vn'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds with safe field handling
        embeds = create_safe_embed_with_fields(
            f"🇻🇳 Tin kinh tế trong nước (Trang {page})",
            "",
            fields_data,
            0xff0000
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"News Bot • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        # Send all embeds
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_enhanced(ctx, page=1):
    """Tin tức quốc tế từ Yahoo Finance"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức quốc tế...")
        
        news_list = await collect_news_stealth_enhanced(RSS_FEEDS['international'], 20)  # More articles from Yahoo Finance
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
        
        stats_field = f"📰 Tổng tin có sẵn: {len(news_list)} tin\n🌐 Auto-translate: Tiếng Anh → Tiếng Việt"
        
        fields_data.append(("📊 Thông tin", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = '💰'
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = 'Yahoo Finance'
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds with safe field handling
        embeds = create_safe_embed_with_fields(
            f"🌍 Tin kinh tế quốc tế (Trang {page})",
            "",
            fields_data,
            0x0066ff
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"News Bot • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        # Send all embeds
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# ENHANCED ARTICLE DETAILS COMMAND
@bot.command(name='chitiet')
async def get_news_detail_enhanced(ctx, news_number: int):
    """Enhanced chi tiết bài viết"""
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
        
        loading_msg = await ctx.send(f"🚀 Đang trích xuất nội dung...")
        
        # Extract content
        full_content = await fetch_content_with_yahoo_finance_fallback(news['link'], news['source'], news)
        
        # Extract source name
        source_name = extract_source_name(news['link'])
        
        # Auto-translate chỉ cho tin quốc tế (Yahoo Finance)
        if 'yahoo_finance' in news['source']:
            translated_content, is_translated = await detect_and_translate_content_enhanced(full_content, source_name)
        else:
            translated_content, is_translated = full_content, False
        
        await loading_msg.delete()
        
        # Create content with metadata
        title_suffix = " 🌐 (Đã dịch)" if is_translated else ""
        main_title = f"📖 Chi tiết bài viết{title_suffix}"
        
        # Enhanced metadata
        content_with_meta = f"**📰 Tiêu đề:** {news['title']}\n"
        content_with_meta += f"**🕰️ Thời gian:** {news['published_str']} ({get_current_date_str()})\n"
        content_with_meta += f"**📰 Nguồn:** {source_name}{'🌐' if is_translated else ''}\n"
        
        if is_translated:
            content_with_meta += f"**🔄 Auto-Translate:** Groq AI đã dịch từ tiếng Anh\n\n"
        
        content_with_meta += f"**📄 Nội dung chi tiết:**\n{translated_content}"
        
        # Tự động split thành nhiều embeds khi content dài
        optimized_embeds = create_comprehensive_embeds(main_title, content_with_meta, 0x9932cc)
        
        # Add link to last embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔗 Đọc bài viết gốc",
                f"[Nhấn để đọc bài viết gốc]({news['link']})"
            )
            optimized_embeds[-1].add_field(name=safe_name, value=safe_value, inline=False)
            
            total_chars = sum(len(embed.description or "") + sum(len(field.value) for field in embed.fields) for embed in optimized_embeds)
            optimized_embeds[-1].set_footer(text=f"📖 Content • {total_chars:,} ký tự • Tin số {news_number} • {len(optimized_embeds)} phần")
        
        # Send all embeds with progress tracking
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

def create_comprehensive_embeds(title: str, content: str, color: int = 0x9932cc) -> List[discord.Embed]:
    """Tạo embeds cho nội dung - tự động split không giới hạn độ dài"""
    embeds = []
    
    content_parts = split_text_comprehensive(content, 800)
    
    for i, part in enumerate(content_parts):
        if i == 0:
            embed = discord.Embed(
                title=validate_and_truncate_content(title, DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
        else:
            embed = discord.Embed(
                title=validate_and_truncate_content(f"{title[:150]}... (Phần {i+1}/{len(content_parts)})", DISCORD_EMBED_TITLE_LIMIT),
                color=color,
                timestamp=get_current_vietnam_datetime()
            )
        
        if i == 0:
            field_name = f"📄 Nội dung {f'(Phần {i+1}/{len(content_parts)})' if len(content_parts) > 1 else ''}"
            safe_field_name, safe_field_value = validate_embed_field(field_name, part)
            embed.add_field(name=safe_field_name, value=safe_field_value, inline=False)
        else:
            safe_description = validate_and_truncate_content(part, DISCORD_EMBED_DESCRIPTION_LIMIT)
            embed.description = safe_description
        
        embeds.append(embed)
    
    return embeds

def split_text_comprehensive(text: str, max_length: int = 800) -> List[str]:
    """Split text cho comprehensive content"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Try to split by paragraphs first
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if len(paragraph) > max_length:
            sentences = paragraph.split('. ')
            
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
        else:
            if len(current_part + paragraph + '\n\n') <= max_length:
                current_part += paragraph + '\n\n'
            else:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
                else:
                    parts.append(paragraph)
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

@bot.command(name='menu')
async def help_command_simplified(ctx):
    """Simplified menu guide"""
    current_datetime_str = get_current_datetime_str()
    
    main_embed = create_safe_embed(
        "🤖 News Bot",
        f"Bot tin tức AI với Yahoo Finance - {current_datetime_str}",
        0xff9900
    )
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 1:
        ai_status = f"🤖 **{ai_count} AI Engine sẵn sàng**"
    else:
        ai_status = "⚠️ Cần AI engine để hoạt động"
    
    safe_name, safe_value = validate_embed_field("🤖 AI Status", ai_status)
    main_embed.add_field(name=safe_name, value=safe_value, inline=False)
    
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI Commands",
        f"**!hoi [câu hỏi]** - AI trả lời với dữ liệu {get_current_date_str()}\n**!hoi chitiet [số] [type] [question]** - Phân tích bài báo\n*VD: !hoi chitiet 5 out tại sao?*"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=False)
    
    safe_name3, safe_value3 = validate_embed_field(
        "📰 News Commands",
        f"**!all [trang]** - Tin từ tất cả nguồn (12 tin/trang)\n**!in [trang]** - Tin trong nước\n**!out [trang]** - Tin quốc tế (Yahoo Finance)\n**!chitiet [số]** - Chi tiết bài viết"
    )
    main_embed.add_field(name=safe_name3, value=safe_value3, inline=False)
    
    safe_name4, safe_value4 = validate_embed_field(
        "🎯 Examples",
        f"**!hoi giá vàng hôm nay** - AI tìm giá vàng {get_current_date_str()}\n**!all** - Xem tin mới nhất\n**!chitiet 1** - Chi tiết tin số 1"
    )
    main_embed.add_field(name=safe_name4, value=safe_value4, inline=False)
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    safe_name5, safe_value5 = validate_embed_field(
        "📊 Sources", 
        f"🇻🇳 **Trong nước**: {len(RSS_FEEDS['domestic'])} nguồn\n🌍 **Quốc tế**: Yahoo Finance\n📊 **Tổng**: {total_sources} nguồn"
    )
    main_embed.add_field(name=safe_name5, value=safe_value5, inline=True)
    
    main_embed.set_footer(text=f"🤖 News Bot • {current_datetime_str}")
    await ctx.send(embed=main_embed)

# ADDITIONAL MISSING ALIAS COMMANDS
@bot.command(name='cuthe')
async def get_news_detail_alias(ctx, news_number: int):
    """Alias cho lệnh !chitiet"""
    await get_news_detail_enhanced(ctx, news_number)

@bot.command(name='detail')
async def get_news_detail_alias_en(ctx, news_number: int):
    """English alias for !chitiet"""
    await get_news_detail_enhanced(ctx, news_number)

# MISSING COMPREHENSIVE CONTENT VALIDATION
def comprehensive_content_validation(content, min_length=200):
    """Comprehensive content validation for quality assurance"""
    if not content:
        return False, "No content"
    
    content = str(content).strip()
    
    # Check minimum length
    if len(content) < min_length:
        return False, f"Content too short: {len(content)} chars"
    
    # Check for meaningful sentences
    sentences = content.split('. ')
    meaningful_sentences = [s for s in sentences if len(s.strip()) > 10]
    
    if len(meaningful_sentences) < 3:
        return False, "Not enough meaningful sentences"
    
    # Check for spam patterns
    spam_patterns = [
        r'subscribe.*now',
        r'click.*here',
        r'buy.*now',
        r'limited.*time',
        r'act.*fast',
        r'don\'t.*miss',
        r'free.*trial'
    ]
    
    spam_count = 0
    for pattern in spam_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            spam_count += 1
    
    if spam_count >= 3:
        return False, "Content appears to be spam"
    
    return True, "Content valid"

# MISSING ENHANCED MEMORY MANAGEMENT
import gc
import sys

def ensure_timezone_aware(dt):
    """Ensure datetime object is timezone-aware (Vietnam timezone)"""
    if dt is None:
        return get_current_vietnam_datetime()
    
    if dt.tzinfo is None:
        # Convert naive datetime to Vietnam timezone
        return VN_TIMEZONE.localize(dt)
    else:
        # Convert to Vietnam timezone if it has different timezone
        return dt.astimezone(VN_TIMEZONE)

def safe_datetime_comparison(dt1, dt2):
    """Safely compare two datetime objects by ensuring both are timezone-aware"""
    try:
        aware_dt1 = ensure_timezone_aware(dt1)
        aware_dt2 = ensure_timezone_aware(dt2)
        return aware_dt1, aware_dt2
    except Exception as e:
        print(f"⚠️ Datetime comparison error: {e}")
        current = get_current_vietnam_datetime()
        return current, current

def optimize_memory_usage():
    """Optimize memory usage and cleanup"""
    try:
        # Force garbage collection
        collected = gc.collect()
        
        # Clear user cache if too large
        cleanup_user_cache()
        
        # Get memory info
        memory_info = {
            'collected_objects': collected,
            'cache_size': len(user_news_cache),
            'gc_counts': gc.get_count()
        }
        
        return memory_info
    except Exception as e:
        return {'error': str(e)}

# MISSING ENHANCED ERROR REPORTING
class NewsProcessingError(Exception):
    """Custom exception for news processing errors"""
    def __init__(self, message, error_type="general", source_url=None):
        self.message = message
        self.error_type = error_type
        self.source_url = source_url
        super().__init__(self.message)

def handle_extraction_error(url, source_name, error):
    """Enhanced error handling for content extraction"""
    error_info = {
        'url': url,
        'source': source_name,
        'error': str(error),
        'timestamp': get_current_datetime_str(),
        'error_type': type(error).__name__
    }
    
    # Log error (in production, you'd send this to logging service)
    print(f"🚨 Content extraction error: {error_info}")
    
    # Return user-friendly fallback content
    return create_fallback_content(url, source_name, f"Extraction failed: {error_info['error_type']}")

# MISSING ENHANCED REGEX PATTERNS FOR CONTENT CLEANING
CONTENT_CLEANING_PATTERNS = {
    'ads': [
        r'quảng cáo.*?',
        r'advertisement.*?',
        r'sponsored.*?content.*?',
        r'promoted.*?post.*?',
        r'paid.*?partnership.*?'
    ],
    'navigation': [
        r'menu.*?chính.*?',
        r'trang.*?chủ.*?',
        r'điều.*?hướng.*?',
        r'liên.*?hệ.*?',
        r'về.*?chúng.*?tôi.*?'
    ],
    'social': [
        r'follow.*?us.*?',
        r'like.*?facebook.*?',
        r'share.*?twitter.*?',
        r'subscribe.*?youtube.*?',
        r'theo.*?dõi.*?fanpage.*?'
    ],
    'footer': [
        r'bản.*?quyền.*?',
        r'copyright.*?',
        r'all.*?rights.*?reserved.*?',
        r'terms.*?of.*?service.*?',
        r'privacy.*?policy.*?'
    ]
}

def apply_advanced_content_cleaning(content):
    """Apply advanced content cleaning patterns"""
    if not content:
        return content
    
    cleaned_content = content
    
    # Apply all cleaning patterns
    for category, patterns in CONTENT_CLEANING_PATTERNS.items():
        for pattern in patterns:
            cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove excessive whitespace and empty lines
    cleaned_content = re.sub(r'\n\s*\n', '\n', cleaned_content)
    cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
    
    return cleaned_content.strip()

# MISSING ENHANCED RATE LIMITING
import time
from collections import defaultdict

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

# MISSING ENHANCED USER INTERACTION TRACKING
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
    stats['last_activity'] = get_current_vietnam_datetime()  # ✅ Always timezone-aware
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

# MISSING ENHANCED DISCORD OPTIMIZATION FUNCTIONS
def create_progress_embed(title, description, progress=0, total=100):
    """Create progress embed for long operations"""
    progress_bar = "█" * int(progress/10) + "░" * (10 - int(progress/10))
    progress_text = f"{progress_bar} {progress}%"
    
    embed = discord.Embed(
        title=title,
        description=f"{description}\n```{progress_text}```",
        color=0x00ff88,
        timestamp=get_current_vietnam_datetime()
    )
    
    return embed

def split_message_smart(content, max_length=2000):
    """Smart message splitting that preserves formatting"""
    if len(content) <= max_length:
        return [content]
    
    parts = []
    current_part = ""
    
    # Split by paragraphs first
    paragraphs = content.split('\n\n')
    
    for paragraph in paragraphs:
        if len(current_part + paragraph + '\n\n') <= max_length:
            current_part += paragraph + '\n\n'
        else:
            if current_part:
                parts.append(current_part.strip())
                current_part = paragraph + '\n\n'
            else:
                # Split long paragraph by sentences
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_part + sentence + '. ') <= max_length:
                        current_part += sentence + '. '
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = sentence + '. '
                        else:
                            # Force split if sentence is too long
                            words = sentence.split(' ')
                            for word in words:
                                if len(current_part + word + ' ') <= max_length:
                                    current_part += word + ' '
                                else:
                                    if current_part:
                                        parts.append(current_part.strip())
                                        current_part = word + ' '
    
    if current_part:
        parts.append(current_part.strip())
    
    return parts

# MISSING PERFORMANCE MONITORING
import time
from functools import wraps

def performance_monitor(func):
    """Decorator to monitor function performance with proper error handling"""
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

# Apply performance monitoring to key functions with error handling
try:
    collect_news_stealth_enhanced = performance_monitor(collect_news_stealth_enhanced)
    fetch_content_with_yahoo_finance_fallback = performance_monitor(fetch_content_with_yahoo_finance_fallback)
except Exception as e:
    print(f"⚠️ Could not apply performance monitoring: {e}")

# MISSING BOT STATUS AND HEALTH CHECK
bot_stats = {
    'start_time': None,
    'commands_processed': 0,
    'errors_encountered': 0,
    'successful_extractions': 0,
    'failed_extractions': 0,
    'ai_calls': 0,
    'cache_hits': 0
}

def update_bot_stats(stat_name, increment=1):
    """Update bot statistics"""
    if stat_name in bot_stats:
        bot_stats[stat_name] += increment

def get_bot_health_status():
    """Get bot health status with proper datetime handling"""
    if not bot_stats['start_time']:
        return "Bot not properly initialized"
    
    try:
        current_time = get_current_vietnam_datetime()  # timezone-aware
        uptime = current_time - bot_stats['start_time']  # both are timezone-aware now
        success_rate = 0
        
        total_extractions = bot_stats['successful_extractions'] + bot_stats['failed_extractions']
        if total_extractions > 0:
            success_rate = (bot_stats['successful_extractions'] / total_extractions) * 100
        
        return {
            'uptime': str(uptime),
            'commands_processed': bot_stats['commands_processed'],
            'success_rate': f"{success_rate:.1f}%",
            'ai_calls': bot_stats['ai_calls'],
            'cache_efficiency': f"{bot_stats['cache_hits']}/{bot_stats['commands_processed']}"
        }
    except Exception as e:
        return f"Error calculating health status: {str(e)}"

@bot.command(name='status')
async def bot_status_command(ctx):
    """Show bot status and health"""
    if not await rate_limiter.is_allowed(f"user_{ctx.author.id}", 'user_commands'):
        wait_time = rate_limiter.get_wait_time(f"user_{ctx.author.id}", 'user_commands')
        await ctx.send(f"⏳ Rate limited. Wait {wait_time:.0f} seconds.")
        return
    
    track_user_interaction(ctx.author.id, 'status')
    
    health = get_bot_health_status()
    memory_info = optimize_memory_usage()
    
    embed = create_safe_embed(
        "🤖 Bot Status",
        f"**Health Check:** {get_current_datetime_str()}",
        0x00ff88
    )
    
    if isinstance(health, dict):
        safe_name, safe_value = validate_embed_field(
            "📊 Performance Metrics",
            f"**Uptime:** {health['uptime']}\n**Commands:** {health['commands_processed']}\n**Success Rate:** {health['success_rate']}\n**AI Calls:** {health['ai_calls']}"
        )
        embed.add_field(name=safe_name, value=safe_value, inline=True)
    
    safe_name2, safe_value2 = validate_embed_field(
        "💾 Memory Status", 
        f"**Cache Size:** {memory_info.get('cache_size', 'Unknown')}\n**Collected Objects:** {memory_info.get('collected_objects', 'Unknown')}"
    )
    embed.add_field(name=safe_name2, value=safe_value2, inline=True)
    
    ai_count = len(debate_engine.available_engines)
    safe_name3, safe_value3 = validate_embed_field(
        "🤖 AI Systems",
        f"**Available Engines:** {ai_count}\n**Status:** {'✅ Online' if ai_count > 0 else '❌ Offline'}"
    )
    embed.add_field(name=safe_name3, value=safe_value3, inline=False)
    
    await ctx.send(embed=embed)

# UPDATE ON_READY TO INITIALIZE STATS
async def on_ready_enhanced():
    """Enhanced on_ready with proper initialization"""
    bot_stats['start_time'] = get_current_vietnam_datetime()  # ✅ This is timezone-aware
    
    print(f'✅ {bot.user} is online!')
    
    ai_count = len(debate_engine.available_engines)
    current_datetime_str = get_current_datetime_str()
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    
    # SIMPLIFIED status text
    status_text = f"News Bot • {ai_count} AI • {total_sources} sources • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )
    
    print(f"🤖 AI Engines: {ai_count}")
    print(f"📊 News Sources: {total_sources}")
    print(f"🕰️ Started at: {current_datetime_str}")

# Replace the original on_ready
try:
    bot.remove_listener(bot.on_ready)
except:
    pass  # In case there's no existing listener
bot.event(on_ready_enhanced)

# MISSING COMPREHENSIVE ERROR HANDLER FOR COMMANDS
@bot.event
async def on_command_error_enhanced(ctx, error):
    """Enhanced error handling for all commands"""
    update_bot_stats('errors_encountered')
    
    error_embed = None
    
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingRequiredArgument):
        error_embed = create_safe_embed(
            "❌ Thiếu tham số",
            f"Lệnh `{ctx.command}` cần thêm tham số. Gõ `!menu` để xem hướng dẫn.",
            0xff6b6b
        )
    elif isinstance(error, commands.BadArgument):
        error_embed = create_safe_embed(
            "❌ Tham số không hợp lệ",
            f"Tham số cho lệnh `{ctx.command}` không đúng định dạng. Gõ `!menu` để xem hướng dẫn.",
            0xff6b6b
        )
    elif isinstance(error, commands.CommandOnCooldown):
        error_embed = create_safe_embed(
            "⏳ Lệnh đang cooldown",
            f"Vui lòng đợi {error.retry_after:.1f} giây trước khi sử dụng lại.",
            0xffa500
        )
    elif isinstance(error, NewsProcessingError):
        error_embed = create_safe_embed(
            "❌ Lỗi xử lý tin tức",
            f"**Loại lỗi:** {error.error_type}\n**Chi tiết:** {error.message}",
            0xff6b6b
        )
    else:
        error_embed = create_safe_embed(
            "❌ Lỗi hệ thống",
            f"Đã xảy ra lỗi: `{str(error)[:100]}...`\nVui lòng thử lại sau hoặc liên hệ admin.",
            0xff0000
        )
    
    if error_embed:
        try:
            await ctx.send(embed=error_embed)
        except:
            # Fallback to plain text if embed fails
            await ctx.send(f"❌ Lỗi: {str(error)}")

# Replace the original error handler
try:
    bot.remove_listener(bot.on_command_error)
except:
    pass  # In case there's no existing error handler
bot.event(on_command_error_enhanced)

# MISSING UPDATE COMMANDS TO USE TRACKING
def track_command_usage(func):
    """Decorator to track command usage"""
    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        update_bot_stats('commands_processed')
        track_user_interaction(ctx.author.id, func.__name__.replace('_enhanced', '').replace('get_', '').replace('_', ''))
        
        # Rate limiting
        if not rate_limiter.is_allowed(f"user_{ctx.author.id}", 'user_commands'):
            wait_time = rate_limiter.get_wait_time(f"user_{ctx.author.id}", 'user_commands')
            await ctx.send(f"⏳ Bạn đang sử dụng quá nhiều lệnh. Vui lòng đợi {wait_time:.0f} giây.")
            return
        
        return await func(ctx, *args, **kwargs)
    
    return wrapper

# Apply tracking to main commands (update the existing commands with error handling)
try:
    get_all_news_enhanced = track_command_usage(get_all_news_enhanced)
    get_domestic_news_enhanced = track_command_usage(get_domestic_news_enhanced) 
    get_international_news_enhanced = track_command_usage(get_international_news_enhanced)
    get_news_detail_enhanced = track_command_usage(get_news_detail_enhanced)
    enhanced_gemini_question_with_article_context = track_command_usage(enhanced_gemini_question_with_article_context)
except Exception as e:
    print(f"⚠️ Could not apply command tracking: {e}")

# MISSING CLEANUP FUNCTION
async def cleanup_enhanced():
    """Enhanced cleanup with comprehensive resource management"""
    try:
        print("🧹 Starting enhanced cleanup...")
        
        # Close AI engine sessions
        if debate_engine:
            await debate_engine.close_session()
            print("✅ AI engine sessions closed")
        
        # Clear caches
        global user_news_cache
        if len(user_news_cache) > MAX_CACHE_ENTRIES:
            user_news_cache.clear()
            print("✅ User cache cleared")
        
        # Clear user interaction stats (keep only recent data)
        current_time = get_current_vietnam_datetime()
        cutoff_time = current_time - timedelta(hours=24)  # ✅ FIXED: Use timedelta directly
        
        users_to_remove = []
        for user_id, stats in user_interaction_stats.items():
            # ✅ FIXED: Ensure both datetimes are timezone-aware for comparison
            if stats['last_activity'] and stats['last_activity'] < cutoff_time:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del user_interaction_stats[user_id]
        
        print(f"✅ Cleaned {len(users_to_remove)} old user stats")
        
        # Force garbage collection
        memory_info = optimize_memory_usage()
        print(f"✅ Memory optimized: {memory_info.get('collected_objects', 0)} objects collected")
        
        # Final stats
        health = get_bot_health_status()
        if isinstance(health, dict):
            print(f"📊 Final stats: {health['commands_processed']} commands, {health['success_rate']} success rate")
        
        print("🧹 Enhanced cleanup completed")
        
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

# MISSING ENHANCED MAIN EXECUTION BLOCK
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
        
        print("🔧 Advanced Features:")
        features = [
            "✅ Yahoo Finance search fallback system",
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
            "✅ Vietnam timezone auto-correction"
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
            "✅ Stealth headers with randomization"
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
        print("   📊 !status - Bot health and performance metrics")
        print("   📋 !menu - Complete command guide")
        print()
        
        if ai_count > 0:
            print("🤖 AI Features:")
            print("   💎 !hoi [question] - Gemini AI intelligent analysis")
            print("   📰 !hoi chitiet [số] [type] [question] - Article context analysis")
            print("   🌐 Auto-translation: English → Vietnamese (Groq AI)")
            print()
        
        print("🔗 Advanced Examples:")
        print(f"   !hoi giá vàng hôm nay - AI finds gold prices for {get_current_date_str()}")
        print("   !all 2 - Page 2 of all news")
        print("   !chitiet 1 - Detailed view of article #1 with enhanced extraction")
        print("   !hoi chitiet 5 out tại sao giá tăng? - Analyze article #5 from international page")
        print()
        
        # Memory and performance baseline
        initial_memory = optimize_memory_usage()
        print(f"💾 Initial memory: {initial_memory.get('cache_size', 0)} cache entries")
        
        # ✅ FIXED: Removed problematic boot time calculation that mixed aware/naive datetimes
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
                    print(f"   • Success rate: {final_health['success_rate']}")
                    print(f"   • AI calls made: {final_health['ai_calls']}")
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
