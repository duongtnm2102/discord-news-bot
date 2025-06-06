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

# 🚀 OPTIMIZED LIBRARIES - CafeF Focus
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

# 🆕 GEMINI ONLY - Enhanced AI System
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

# User cache
user_news_cache = {}
user_last_detail_cache = {}  # New: Track last !chitiet article
MAX_CACHE_ENTRIES = 25

# 🔧 Enhanced User Agents for CafeF + Yahoo Finance
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'curl/7.68.0'
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

print("🚀 OPTIMIZED NEWS BOT - CAFEF + YAHOO FINANCE:")
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'}")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'}")
print(f"🔧 Current Vietnam time: {get_current_datetime_str()}")
print("=" * 50)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🔧 OPTIMIZED RSS FEEDS - CafeF Focus + Working Yahoo Finance URLs
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - CHỈ CAFEF ===
    'domestic': {
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        'cafef_doanhnghiep': 'https://cafef.vn/doanh-nghiep.rss'
    },
    
    # === QUỐC TẾ - YAHOO FINANCE WORKING URLs ===
    'international': {
        'yahoo_finance_news': 'https://finance.yahoo.com/news/rssindex',
        'yahoo_finance_main': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        'yahoo_finance_business': 'https://feeds.finance.yahoo.com/rss/2.0/category-business',
        'yahoo_finance_world': 'https://finance.yahoo.com/news/rss'
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

# 🔧 Enhanced headers for CafeF and Yahoo Finance
def get_enhanced_headers(url=None):
    """Enhanced headers for CafeF and Yahoo Finance"""
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'application/rss+xml, application/xml, text/xml, text/html, application/xhtml+xml, */*',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }
    
    if url:
        if 'yahoo' in url.lower():
            headers.update({
                'Referer': 'https://finance.yahoo.com/',
                'Origin': 'https://finance.yahoo.com',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty'
            })
        elif 'cafef.vn' in url.lower():
            headers.update({
                'Referer': 'https://cafef.vn/',
                'Origin': 'https://cafef.vn'
            })
    
    return headers

def add_random_delay():
    """Add random delay to avoid rate limiting"""
    delay = random.uniform(1.0, 3.0)
    time.sleep(delay)

# 🚀 ENHANCED CONTENT EXTRACTION WITH GEMINI TRANSLATION
async def extract_content_enhanced(url, source_name, news_item=None):
    """Enhanced content extraction with Gemini translation for international news"""
    
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
                        
                        # Enhanced Gemini translation for international news
                        if is_international_source(source_name):
                            translated_content = await translate_with_gemini(content, source_name)
                            return translated_content if translated_content else content
                        
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
                        content = article.text
                        
                        # Enhanced Gemini translation for international news
                        if is_international_source(source_name):
                            translated_content = await translate_with_gemini(content, source_name)
                            return translated_content if translated_content else content
                        
                        return content.strip()
                
                except Exception as e:
                    pass
            
            # Method 3: BeautifulSoup
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Enhanced selectors for both CafeF and Yahoo Finance
                    content_selectors = [
                        '[data-testid="article-content"]',  # Yahoo Finance
                        'div.caas-body',  # Yahoo Finance
                        'div.detail-content',  # CafeF
                        'div.fck_detail',  # CafeF
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
                        # Clean content
                        content = clean_content_enhanced(content)
                        
                        session.close()
                        
                        # Enhanced Gemini translation for international news
                        if is_international_source(source_name):
                            translated_content = await translate_with_gemini(content, source_name)
                            return translated_content if translated_content else content
                        
                        return content.strip()
                        
                except Exception as e:
                    pass
        
        session.close()
        return create_fallback_content(url, source_name)
        
    except Exception as e:
        return create_fallback_content(url, source_name, str(e))

def clean_content_enhanced(content):
    """Enhanced content cleaning for both CafeF and Yahoo Finance"""
    if not content:
        return content
    
    # Remove common patterns
    unwanted_patterns = [
        r'Subscribe.*?Premium.*?',
        r'Sign in.*?Account.*?',
        r'Advertisement.*?',
        r'Quảng cáo.*?',
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
    international_sources = {
        'yahoo_finance_news', 'yahoo_finance_main', 'yahoo_finance_business', 'yahoo_finance_world'
    }
    return source_name in international_sources

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

# 🆕 GEMINI TRANSLATION SYSTEM
async def translate_with_gemini(content: str, source_name: str):
    """Enhanced Gemini translation for international news"""
    try:
        if not GEMINI_API_KEY or not GEMINI_AVAILABLE:
            return None
        
        # Enhanced detection for English content
        english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 
                            'will', 'market', 'price', 'stock', 'financial', 'economic',
                            'company', 'business', 'trade', 'investment', 'percent']
        content_lower = content.lower()
        english_word_count = sum(1 for word in english_indicators if f' {word} ' in f' {content_lower} ')
        
        if english_word_count < 3:
            return None  # Not English content
        
        translation_prompt = f"""Bạn là chuyên gia dịch thuật kinh tế-tài chính. Hãy dịch bài báo tiếng Anh sau sang tiếng Việt một cách chính xác và tự nhiên.

YÊU CẦU DỊCH:
1. Giữ nguyên ý nghĩa và ngữ cảnh kinh tế
2. Sử dụng thuật ngữ kinh tế tiếng Việt chuẩn
3. Dịch tự nhiên, không máy móc
4. Giữ nguyên các con số, tỷ lệ phần trăm, tên công ty
5. KHÔNG thêm giải thích hay bình luận
6. Chỉ trả về bản dịch tiếng Việt

BÀI BÁO CẦN DỊCH:
{content[:2000]}

BẢN DỊCH TIẾNG VIỆT:"""

        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=1500,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    translation_prompt,
                    generation_config=generation_config
                ),
                timeout=20
            )
            
            translated_text = response.text.strip()
            return f"[Đã dịch từ {source_name}] {translated_text}"
            
        except Exception as e:
            return f"[Lỗi dịch từ {source_name}] {content[:1000]}..."
            
    except Exception as e:
        return None

# 🚀 ENHANCED NEWS COLLECTION
async def collect_news_enhanced(sources_dict, limit_per_source=15):
    """Enhanced news collection for CafeF and Yahoo Finance with improved error handling"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Fetching from {source_name}: {rss_url}")
            add_random_delay()
            
            session = requests.Session()
            headers = get_enhanced_headers(rss_url)
            session.headers.update(headers)
            
            # Enhanced error handling for Yahoo Finance
            feed = None
            try:
                response = session.get(rss_url, timeout=15, allow_redirects=True)
                print(f"📊 {source_name} response: {response.status_code}")
                
                if response.status_code == 403:
                    print(f"⚠️ 403 for {source_name}, trying fallback...")
                    # Try with curl user-agent for Yahoo Finance
                    headers['User-Agent'] = 'curl/7.68.0'
                    session.headers.update(headers)
                    time.sleep(random.uniform(2.0, 4.0))
                    response = session.get(rss_url, timeout=15, allow_redirects=True)
                    print(f"🔄 Fallback {source_name} response: {response.status_code}")
                
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    print(f"⚠️ {source_name} failed with {response.status_code}, trying direct parse...")
                    feed = feedparser.parse(rss_url)
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Request error for {source_name}: {e}")
                print(f"🔄 Trying direct feedparser for {source_name}...")
                feed = feedparser.parse(rss_url)
            
            session.close()
            
            if not feed or not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"❌ No entries for {source_name}")
                # For Yahoo Finance sources, try alternative approach
                if 'yahoo_finance' in source_name:
                    print(f"🔄 Trying alternative Yahoo Finance approach for {source_name}...")
                    # Skip this source but don't fail completely
                continue
                
            entries_processed = 0
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
                            all_news.append(news_item)
                            entries_processed += 1
                    
                except Exception as entry_error:
                    print(f"⚠️ Entry error for {source_name}: {entry_error}")
                    continue
                    
            print(f"✅ Processed {entries_processed} entries from {source_name}")
            
        except Exception as e:
            print(f"❌ Error for {source_name}: {e}")
            continue
    
    print(f"📊 Total news collected: {len(all_news)}")
    
    # Sort by publish time
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

def is_relevant_news(title, description, source_name):
    """Filter for relevant economic/financial news"""
    
    # For CafeF sources, all content is relevant (already filtered by RSS category)
    if 'cafef' in source_name:
        return True
    
    # For Yahoo Finance, filter for economic/financial keywords
    if 'yahoo_finance' in source_name:
        economic_keywords = [
            'economy', 'economic', 'gdp', 'inflation', 'fed', 'federal reserve',
            'market', 'stock', 'bond', 'trading', 'investment', 'investor',
            'financial', 'finance', 'bank', 'banking', 'earnings', 'revenue',
            'profit', 'loss', 'company', 'corporate', 'business', 'merger',
            'acquisition', 'ipo', 'dividend', 'interest rate', 'currency',
            'real estate', 'property', 'housing', 'mortgage', 'commodity',
            'oil', 'gold', 'bitcoin', 'crypto', 'policy', 'regulation'
        ]
        
        text_to_check = f"{title} {description}".lower()
        return any(keyword in text_to_check for keyword in economic_keywords)
    
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
    
    status_text = f"CafeF + Yahoo Finance • Gemini AI • {total_sources} sources • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )
    
    print(f"🤖 Gemini AI: {ai_status}")
    print(f"📊 News Sources: {total_sources}")
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
    """Tin tức từ CafeF và Yahoo Finance"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức...")
        
        domestic_news = await collect_news_enhanced(RSS_FEEDS['domestic'], 15)
        international_news = await collect_news_enhanced(RSS_FEEDS['international'], 12)
        
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
        
        # Source mapping
        source_names = {
            'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafef_doanhnghiep': 'CafeF DN',
            'yahoo_finance_news': 'Yahoo Finance News', 'yahoo_finance_main': 'Yahoo Finance',
            'yahoo_finance_business': 'Yahoo Finance Business', 'yahoo_finance_world': 'Yahoo Finance World'
        }
        
        emoji_map = {
            'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 
            'cafef_vimo': '📊', 'cafef_doanhnghiep': '🏭',
            'yahoo_finance_news': '💰', 'yahoo_finance_main': '💰',
            'yahoo_finance_business': '💼', 'yahoo_finance_world': '🌍'
        }
        
        # Add statistics
        stats_field = f"🇻🇳 CafeF: {domestic_count} tin\n🌍 Yahoo Finance: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin"
        fields_data.append(("📊 Thống kê", stats_field))
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"📰 Tin tức tổng hợp (Trang {page})",
            "",
            fields_data,
            0x00ff88
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"CafeF + Yahoo Finance • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_enhanced(ctx, page=1):
    """Tin tức trong nước - CafeF"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức CafeF...")
        
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

@bot.command(name='out')
async def get_international_news_enhanced(ctx, page=1):
    """Tin tức quốc tế - Yahoo Finance với Gemini dịch"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức Yahoo Finance...")
        
        news_list = await collect_news_enhanced(RSS_FEEDS['international'], 12)
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
        
        stats_field = f"📰 Tổng tin Yahoo Finance: {len(news_list)} tin\n🌐 Auto-translate: Gemini AI"
        fields_data.append(("📊 Thông tin", stats_field))
        
        source_names = {
            'yahoo_finance_main': 'Yahoo Finance', 'yahoo_finance_business': 'Yahoo Business',
            'yahoo_finance_markets': 'Yahoo Markets', 'yahoo_finance_economics': 'Yahoo Economics'
        }
        
        emoji_map = {
            'yahoo_finance_main': '💰', 'yahoo_finance_business': '💼',
            'yahoo_finance_markets': '📈', 'yahoo_finance_economics': '🌍'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '💰')
            title = news['title'][:55] + "..." if len(news['title']) > 55 else news['title']
            source_display = source_names.get(news['source'], 'Yahoo Finance')
            
            field_name = f"{i}. {emoji} {title}"
            field_value = f"🕰️ {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})"
            
            fields_data.append((field_name, field_value))
        
        # Create embeds
        embeds = create_safe_embed_with_fields(
            f"🌍 Tin kinh tế quốc tế (Trang {page})",
            "",
            fields_data,
            0x0066ff
        )
        
        save_user_news_enhanced(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        for i, embed in enumerate(embeds):
            embed.set_footer(text=f"Yahoo Finance + Gemini AI • Trang {page}/{total_pages} • !chitiet [số] • Phần {i+1}/{len(embeds)}")
        
        for embed in embeds:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail_enhanced(ctx, news_number: int):
    """Chi tiết bài viết với Gemini enhanced extraction"""
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
        
        loading_msg = await ctx.send(f"🚀 Đang trích xuất nội dung...")
        
        # Enhanced content extraction
        full_content = await extract_content_enhanced(news['link'], news['source'], news)
        
        # Get source name
        source_names = {
            'cafef_chungkhoan': 'CafeF Chứng Khoán', 'cafef_batdongsan': 'CafeF Bất Động Sản',
            'cafef_taichinh': 'CafeF Tài Chính', 'cafef_vimo': 'CafeF Vĩ Mô', 'cafef_doanhnghiep': 'CafeF Doanh Nghiệp',
            'yahoo_finance_news': 'Yahoo Finance News', 'yahoo_finance_main': 'Yahoo Finance',
            'yahoo_finance_business': 'Yahoo Finance Business', 'yahoo_finance_world': 'Yahoo Finance World'
        }
        
        source_name = source_names.get(news['source'], news['source'])
        
        await loading_msg.delete()
        
        # Determine if translated
        is_translated = "[Đã dịch từ" in full_content if full_content else False
        
        # Create content with metadata
        title_suffix = " 🌐 (Gemini dịch)" if is_translated else ""
        main_title = f"📖 Chi tiết bài viết{title_suffix}"
        
        # Enhanced metadata
        content_with_meta = f"**📰 Tiêu đề:** {news['title']}\n"
        content_with_meta += f"**🕰️ Thời gian:** {news['published_str']} ({get_current_date_str()})\n"
        content_with_meta += f"**📰 Nguồn:** {source_name}{'🌐' if is_translated else ''}\n"
        
        if is_translated:
            content_with_meta += f"**🤖 Gemini Translation:** Đã dịch tự động từ tiếng Anh\n\n"
        
        content_with_meta += f"**📄 Nội dung chi tiết:**\n{full_content}"
        
        # Create optimized embeds
        optimized_embeds = create_optimized_embeds(main_title, content_with_meta, 0x9932cc)
        
        # Add link to last embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔗 Đọc bài viết gốc",
                f"[Nhấn để đọc bài viết gốc]({news['link']})"
            )
            optimized_embeds[-1].add_field(name=safe_name, value=safe_value, inline=False)
            
            optimized_embeds[-1].set_footer(text=f"📖 Enhanced Content • Tin số {news_number} • {len(optimized_embeds)} phần")
        
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
                    context_info = f"📰 **Context:** Bài báo #{user_id} vừa xem"
        
        progress_embed = create_safe_embed(
            "💎 Gemini AI System",
            f"**Câu hỏi:** {question}\n{context_info}\n🧠 **Đang phân tích...**",
            0x9932cc
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get Gemini response
        if context:
            # Article analysis mode
            analysis_result = await gemini_engine.analyze_article(context, question)
            strategy_text = "Article Analysis"
        else:
            # General question mode
            analysis_result = await gemini_engine.ask_question(question, context)
            strategy_text = "General Knowledge"
        
        # Create optimized embeds
        title = f"💎 Gemini Analysis - {strategy_text}"
        optimized_embeds = create_optimized_embeds(title, analysis_result, 0x00ff88)
        
        # Add metadata to first embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🔍 Analysis Mode",
                f"**Strategy:** {strategy_text}\n**Context:** {'Article-based' if context else 'Knowledge-based'}\n**Model:** Gemini-2.0-Flash-Exp"
            )
            optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
            
            optimized_embeds[-1].set_footer(text=f"💎 Gemini AI • {current_datetime_str}")
        
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
            "🎭 Gemini Debate System",
            f"**Chủ đề:** {topic}\n🎪 **Đang tổ chức tranh luận 6 thân phận với đạo đức khác nhau...**",
            0xff9900
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Get debate analysis
        debate_result = await gemini_engine.debate_perspectives(topic)
        
        # Create optimized embeds
        title = f"🎭 Multi-Perspective Debate"
        optimized_embeds = create_optimized_embeds(title, debate_result, 0xff6600)
        
        # Add metadata to first embed
        if optimized_embeds:
            safe_name, safe_value = validate_embed_field(
                "🎪 Debate Info",
                f"**Topic:** {topic[:100]}...\n**Characters:** 6 thân phận với đặc điểm đạo đức riêng biệt\n**AI Engine:** Gemini Multi-Role Advanced"
            )
            optimized_embeds[0].add_field(name=safe_name, value=safe_value, inline=True)
            
            optimized_embeds[-1].set_footer(text=f"🎭 Gemini Debate • {get_current_datetime_str()}")
        
        # Send optimized embeds
        await progress_msg.edit(embed=optimized_embeds[0])
        
        for embed in optimized_embeds[1:]:
            await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống debate: {str(e)}")

@bot.command(name='menu')
async def help_command_optimized(ctx):
    """Enhanced menu guide"""
    current_datetime_str = get_current_datetime_str()
    
    main_embed = create_safe_embed(
        "🤖 Enhanced News Bot",
        f"CafeF + Yahoo Finance với Gemini AI - {current_datetime_str}",
        0xff9900
    )
    
    ai_status = f"🤖 **Gemini AI {'✅ Ready' if gemini_engine.available else '❌ Unavailable'}**"
    
    safe_name, safe_value = validate_embed_field("🤖 AI Status", ai_status)
    main_embed.add_field(name=safe_name, value=safe_value, inline=False)
    
    safe_name2, safe_value2 = validate_embed_field(
        "🤖 AI Commands",
        f"**!hoi [câu hỏi]** - Gemini AI trả lời\n**!hoi [question]** - Tự động hiểu context sau !chitiet\n**!debate [chủ đề]** - Tranh luận 6 thân phận có đặc điểm đạo đức khác nhau"
    )
    main_embed.add_field(name=safe_name2, value=safe_value2, inline=False)
    
    safe_name3, safe_value3 = validate_embed_field(
        "📰 News Commands",
        f"**!all [trang]** - CafeF + Yahoo Finance (12 tin/trang)\n**!in [trang]** - CafeF Vietnam\n**!out [trang]** - Yahoo Finance (Gemini dịch)\n**!chitiet [số]** - Chi tiết bài viết"
    )
    main_embed.add_field(name=safe_name3, value=safe_value3, inline=False)
    
    safe_name4, safe_value4 = validate_embed_field(
        "🎯 Examples",
        f"**!hoi lạm phát Việt Nam** - Gemini phân tích\n**!chitiet 1** - Xem chi tiết tin 1\n**!hoi tại sao?** - AI phân tích bài vừa xem\n**!debate lãi suất** - 6 nhân vật với đạo đức khác nhau tranh luận"
    )
    main_embed.add_field(name=safe_name4, value=safe_value4, inline=False)
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    safe_name5, safe_value5 = validate_embed_field(
        "📊 Sources", 
        f"🇻🇳 **CafeF**: {len(RSS_FEEDS['domestic'])} RSS feeds\n🌍 **Yahoo Finance**: {len(RSS_FEEDS['international'])} RSS feeds\n📊 **Tổng**: {total_sources} nguồn chọn lọc"
    )
    main_embed.add_field(name=safe_name5, value=safe_value5, inline=True)
    
    main_embed.set_footer(text=f"🤖 Enhanced News Bot • {current_datetime_str}")
    await ctx.send(embed=main_embed)

# Run the bot
if __name__ == "__main__":
    try:
        keep_alive()
        print("🌐 Keep-alive server started")
        
        print("🚀 Starting Enhanced News Bot...")
        print(f"🔧 CafeF Sources: {len(RSS_FEEDS['domestic'])}")
        print(f"🔧 Yahoo Finance Sources: {len(RSS_FEEDS['international'])}")
        print(f"🤖 Gemini AI: {'✅ Ready' if gemini_engine.available else '❌ Not Available'}")
        print(f"⚡ Boot time: {get_current_datetime_str()}")
        print("=" * 60)
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ STARTUP ERROR: {e}")
        print("🔧 Check environment variables and dependencies")
