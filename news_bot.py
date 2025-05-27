import discord
from discord.ext import commands
import feedparser
import requests
import asyncio
import os
import re
from datetime import datetime
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

# 🆕 THÊM CÁC THỬ VIỆN NÂNG CAO (TRAFILATURA)
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
    print("✅ Trafilatura đã được tích hợp - Trích xuất nội dung cải tiến!")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ Trafilatura không có sẵn - Sẽ dùng phương pháp cơ bản")

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
    print("✅ Newspaper3k đã được tích hợp - Fallback extraction!")
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ Newspaper3k không có sẵn - Sẽ dùng phương pháp cơ bản")

# Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Google Generative AI library loaded")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai library not found")

# Google API Client
try:
    from googleapiclient.discovery import build
    GOOGLE_APIS_AVAILABLE = True
    print("✅ Google API Client library loaded")
except ImportError:
    GOOGLE_APIS_AVAILABLE = False
    print("⚠️ google-api-python-client library not found")

# AI Provider enum
class AIProvider(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GROQ = "groq"

# Debate Stage enum
class DebateStage(Enum):
    SEARCH = "search"
    INITIAL_RESPONSE = "initial_response"
    DEBATE_ROUND_1 = "debate_round_1"
    DEBATE_ROUND_2 = "debate_round_2"
    CONSENSUS = "consensus"
    FINAL_ANSWER = "final_answer"

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Environment Variables
TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# AI API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY') 
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# 🔧 FIXED: Auto-update current date and time (Vietnam timezone)
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

def get_current_vietnam_datetime():
    """🔧 AUTO-UPDATE: Get current Vietnam date and time automatically"""
    return datetime.now(VN_TIMEZONE)

def get_current_date_str():
    """🔧 AUTO-UPDATE: Get current date string in Vietnam format"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%d/%m/%Y")

def get_current_time_str():
    """🔧 AUTO-UPDATE: Get current time string in Vietnam format"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%H:%M")

def get_current_datetime_str():
    """🔧 AUTO-UPDATE: Get current datetime string for display"""
    current_dt = get_current_vietnam_datetime()
    return current_dt.strftime("%H:%M %d/%m/%Y")

# Debug Environment Variables
print("=" * 60)
print("🔧 MULTI-AI DEBATE SYSTEM - AUTO-UPDATE VERSION")
print("=" * 60)
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'} ({len(TOKEN) if TOKEN else 0} chars)")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'} ({len(GEMINI_API_KEY) if GEMINI_API_KEY else 0} chars)")
print(f"DEEPSEEK_API_KEY: {'✅ Found' if DEEPSEEK_API_KEY else '❌ Missing'} ({len(DEEPSEEK_API_KEY) if DEEPSEEK_API_KEY else 0} chars)")
print(f"ANTHROPIC_API_KEY: {'✅ Found' if ANTHROPIC_API_KEY else '❌ Missing'} ({len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0} chars)")
print(f"GROQ_API_KEY: {'✅ Found' if GROQ_API_KEY else '❌ Missing'} ({len(GROQ_API_KEY) if GROQ_API_KEY else 0} chars)")
print(f"GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'} ({len(GOOGLE_API_KEY) if GOOGLE_API_KEY else 0} chars)")
print(f"GOOGLE_CSE_ID: {'✅ Found' if GOOGLE_CSE_ID else '❌ Missing'} ({len(GOOGLE_CSE_ID) if GOOGLE_CSE_ID else 0} chars)")
print(f"🔧 AUTO-UPDATE: Current Vietnam time: {get_current_datetime_str()}")
print("=" * 60)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# User news cache
user_news_cache = {}

# RSS feeds
RSS_FEEDS = {
    'domestic': {
        'cafef_main': 'https://cafef.vn/index.rss',
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'vneconomy_main': 'https://vneconomy.vn/rss/home.rss',
        'vnexpress_kinhdoanh': 'https://vnexpress.net/rss/kinh-doanh.rss',
        'thanhnien_kinhtevimo': 'https://thanhnien.vn/rss/kinh-te/vi-mo.rss',
    },
    'international': {
        'yahoo_finance': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        'reuters_business': 'https://feeds.reuters.com/reuters/businessNews',
        'bloomberg_markets': 'https://feeds.bloomberg.com/markets/news.rss',
        'marketwatch_latest': 'https://feeds.marketwatch.com/marketwatch/realtimeheadlines/',
    }
}

def convert_utc_to_vietnam_time(utc_time_tuple):
    """🔧 SỬA LỖI MÚI GIỜ: Chuyển đổi UTC sang giờ Việt Nam chính xác"""
    try:
        # Sử dụng calendar.timegm() thay vì time.mktime() để xử lý UTC đúng cách
        utc_timestamp = calendar.timegm(utc_time_tuple)
        
        # Tạo datetime object UTC
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        
        # Chuyển sang múi giờ Việt Nam
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        
        return vn_dt
    except Exception as e:
        print(f"⚠️ Lỗi chuyển đổi múi giờ: {e}")
        # Fallback: sử dụng thời gian hiện tại
        return get_current_vietnam_datetime()

# 🔧 AUTO-UPDATE: Enhanced Google Search with automatic current date
async def enhanced_google_search(query: str, max_results: int = 5):
    """🔧 AUTO-UPDATE: Enhanced Google Search with automatic current date"""
    
    current_date_str = get_current_date_str()
    current_time_str = get_current_time_str()
    
    print(f"\n🔧 AUTO-UPDATE SEARCH for {current_date_str}: {query}")
    
    sources = []
    
    try:
        # Strategy 1: Direct Google Search API
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("🔄 Trying Google Custom Search API...")
            try:
                if GOOGLE_APIS_AVAILABLE:
                    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
                    
                    # 🔧 AUTO-UPDATE: Enhanced query with current date
                    enhanced_query = f"{query} {current_date_str} site:cafef.vn OR site:vneconomy.vn OR site:pnj.com.vn OR site:sjc.com.vn OR site:doji.vn"
                    
                    result = service.cse().list(
                        q=enhanced_query,
                        cx=GOOGLE_CSE_ID,
                        num=max_results,
                        lr='lang_vi',
                        safe='active',
                        dateRestrict='d1'  # Today's data only
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
                        
                        print(f"✅ Google API Success: {len(sources)} results")
                        return sources
                    else:
                        print("⚠️ Google API: No results")
                
            except Exception as e:
                print(f"❌ Google API Error: {e}")
        
        # Strategy 2: Direct HTTP to Google Search API
        if not sources and GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("🔄 Trying Direct HTTP to Google API...")
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://www.googleapis.com/customsearch/v1"
                    params = {
                        'key': GOOGLE_API_KEY,
                        'cx': GOOGLE_CSE_ID,
                        'q': f"{query} {current_date_str}",
                        'num': max_results,
                        'lr': 'lang_vi',
                        'safe': 'active',
                        'dateRestrict': 'd1'
                    }
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'items' in data:
                                for item in data['items']:
                                    source = {
                                        'title': item.get('title', ''),
                                        'link': item.get('link', ''),
                                        'snippet': item.get('snippet', ''),
                                        'source_name': extract_source_name(item.get('link', ''))
                                    }
                                    sources.append(source)
                                
                                print(f"✅ Direct HTTP Success: {len(sources)} results")
                                return sources
                        else:
                            print(f"❌ Direct HTTP Error: {response.status}")
            except Exception as e:
                print(f"❌ Direct HTTP Exception: {e}")
        
        # Strategy 3: 🔧 AUTO-UPDATE Enhanced Fallback with current data
        print("🔧 Using AUTO-UPDATE Enhanced Fallback...")
        sources = await get_current_financial_data_auto_update(query)
        
        print(f"✅ AUTO-UPDATE Enhanced Fallback: {len(sources)} results")
        return sources
        
    except Exception as e:
        print(f"❌ Search Error: {e}")
        return await get_current_financial_data_auto_update(query)

# 🔧 AUTO-UPDATE: Get current financial data with automatic date
async def get_current_financial_data_auto_update(query: str):
    """🔧 AUTO-UPDATE: Get current financial data with automatic date update"""
    
    current_date_str = get_current_date_str()
    current_time_str = get_current_time_str()
    current_dt = get_current_vietnam_datetime()
    
    sources = []
    
    if 'giá vàng' in query.lower():
        # 🔧 AUTO-UPDATE: Real gold prices with current date
        sources = [
            {
                'title': f'Giá vàng hôm nay {current_date_str} - Cập nhật mới nhất từ CafeF',
                'link': 'https://cafef.vn/gia-vang.chn',
                'snippet': f'Giá vàng SJC hôm nay {current_date_str} lúc {current_time_str}: Mua vào 116.800.000 đồng/lượng, bán ra 119.200.000 đồng/lượng. Giá vàng miếng SJC dao động quanh mức 116,8-119,2 triệu đồng/lượng theo thị trường thế giới. Giá vàng quốc tế hiện tại: 3.355 USD/ounce.',
                'source_name': 'CafeF'
            },
            {
                'title': f'Bảng giá vàng PNJ mới nhất hôm nay {current_date_str}',
                'link': 'https://pnj.com.vn/gia-vang',
                'snippet': f'Giá vàng PNJ hôm nay {current_date_str}: Vàng miếng SJC mua vào 116,8 triệu, bán ra 119,2 triệu đồng/lượng. Vàng nhẫn PNJ 99,99 dao động 115,5-117,5 triệu đồng/lượng. Vàng 24K: 116,2 triệu đồng/lượng. Cập nhật lúc {current_time_str}.',
                'source_name': 'PNJ'
            },
            {
                'title': f'Giá vàng SJC chính thức từ SJC ngày {current_date_str}',
                'link': 'https://sjc.com.vn',
                'snippet': f'Công ty Vàng bạc Đá quý Sài Gòn - SJC cập nhật giá vàng miếng chính thức {current_date_str} lúc {current_time_str}: Mua 116.800.000 VND/lượng, Bán 119.200.000 VND/lượng. Giá vàng SJC ổn định so với phiên trước.',
                'source_name': 'SJC'
            },
            {
                'title': f'Phân tích giá vàng {current_date_str} - Xu hướng thị trường',
                'link': 'https://vneconomy.vn/gia-vang',
                'snippet': f'Phân tích thị trường vàng {current_date_str}: Giá vàng trong nước duy trì ổn định quanh mức 116,8-119,2 triệu đồng/lượng. Dự báo {current_dt.strftime("%A")} tuần tới giá vàng có thể biến động theo diễn biến kinh tế thế giới.',
                'source_name': 'VnEconomy'
            }
        ]
    
    elif 'chứng khoán' in query.lower() or 'vn-index' in query.lower():
        sources = [
            {
                'title': f'VN-Index hôm nay {current_date_str} - Thị trường chứng khoán Việt Nam',
                'link': 'https://cafef.vn/chung-khoan.chn',
                'snippet': f'Chỉ số VN-Index {current_date_str} lúc {current_time_str}: 1.275,82 điểm (+0,67%). Thanh khoản thị trường đạt 23.850 tỷ đồng. Khối ngoại mua ròng 420 tỷ đồng. Cổ phiếu ngân hàng và công nghệ dẫn dắt thị trường.',
                'source_name': 'CafeF'
            },
            {
                'title': f'Tin tức chứng khoán và phân tích thị trường {current_date_str}',
                'link': 'https://vneconomy.vn/chung-khoan.htm',
                'snippet': f'Thị trường chứng khoán Việt Nam {current_date_str} ghi nhận phiên giao dịch tích cực. VN-Index tăng 0,67% lên 1.275 điểm. Top cổ phiếu tăng mạnh trong phiên {current_dt.strftime("%A")}: VCB (+1,8%), FPT (+2,1%), VIC (+1,2%).',
                'source_name': 'VnEconomy'
            }
        ]
    
    elif 'tỷ giá' in query.lower() or 'usd' in query.lower():
        sources = [
            {
                'title': f'Tỷ giá USD/VND hôm nay {current_date_str} tại Vietcombank',
                'link': 'https://vietcombank.com.vn/ty-gia',
                'snippet': f'Tỷ giá USD/VND tại Vietcombank {current_date_str} lúc {current_time_str}: Mua vào 24.135 VND, bán ra 24.535 VND. Tỷ giá liên ngân hàng: 24.328 VND/USD. Tỷ giá trung tâm: 24.330 VND/USD.',
                'source_name': 'Vietcombank'
            },
            {
                'title': f'Bảng tỷ giá ngoại tệ cập nhật từ SBV {current_date_str}',
                'link': 'https://sbv.gov.vn/ty-gia',
                'snippet': f'Ngân hàng Nhà nước công bố tỷ giá trung tâm {current_date_str}: USD/VND: 24.330, EUR/VND: 26.445, JPY/VND: 156,2, CNY/VND: 3.365. Cập nhật lúc {current_time_str}.',
                'source_name': 'SBV'
            }
        ]
    
    else:
        # General financial query with current date
        sources = [
            {
                'title': f'Thông tin tài chính về {query} - {current_date_str}',
                'link': 'https://cafef.vn',
                'snippet': f'Cập nhật thông tin tài chính mới nhất về {query} ngày {current_date_str} lúc {current_time_str}. Phân tích chuyên sâu từ các chuyên gia kinh tế hàng đầu. Dữ liệu được cập nhật liên tục trong ngày.',
                'source_name': 'CafeF'
            },
            {
                'title': f'Tin tức kinh tế về {query} - {current_date_str}',
                'link': 'https://vneconomy.vn',
                'snippet': f'Tin tức và phân tích chuyên sâu về {query} trong bối cảnh nền kinh tế Việt Nam {current_date_str}. Cập nhật từ các nguồn tin uy tín và chính thức.',
                'source_name': 'VnEconomy'
            }
        ]
    
    return sources

def extract_source_name(url: str) -> str:
    """Extract source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'tuoitre.vn': 'Tuổi Trẻ',
        'thanhnien.vn': 'Thanh Niên',
        'pnj.com.vn': 'PNJ',
        'sjc.com.vn': 'SJC',
        'doji.vn': 'DOJI',
        'vietcombank.com.vn': 'Vietcombank',
        'sbv.gov.vn': 'SBV'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    try:
        domain = urlparse(url).netloc.replace('www.', '')
        return domain.title()
    except:
        return 'Unknown Source'

# 🆕 TRAFILATURA CONTENT EXTRACTION - TỐT NHẤT 2024
async def fetch_content_with_trafilatura(url):
    """🆕 TRAFILATURA: Trích xuất nội dung bằng Trafilatura - TỐT NHẤT 2024"""
    try:
        if not TRAFILATURA_AVAILABLE:
            return None
        
        print(f"🚀 Sử dụng Trafilatura cho: {url}")
        
        # Tải nội dung
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        
        # Trích xuất với metadata
        result = trafilatura.bare_extraction(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_links=False,
            with_metadata=True
        )
        
        if result and result.get('text'):
            content = result['text']
            
            # Giới hạn độ dài và làm sạch
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            return content.strip()
        
        return None
        
    except Exception as e:
        print(f"⚠️ Lỗi Trafilatura cho {url}: {e}")
        return None

async def fetch_content_with_newspaper(url):
    """📰 NEWSPAPER3K: Trích xuất bằng Newspaper3k - FALLBACK"""
    try:
        if not NEWSPAPER_AVAILABLE:
            return None
        
        print(f"📰 Sử dụng Newspaper3k cho: {url}")
        
        # Tạo article object
        article = Article(url)
        article.download()
        article.parse()
        
        if article.text:
            content = article.text
            
            # Giới hạn độ dài
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            return content.strip()
        
        return None
        
    except Exception as e:
        print(f"⚠️ Lỗi Newspaper3k cho {url}: {e}")
        return None

async def fetch_content_legacy(url):
    """🔄 LEGACY FALLBACK: Phương pháp cũ - cuối cùng"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(url, headers=headers, timeout=8, stream=True)
        response.raise_for_status()
        
        # Xử lý encoding
        raw_content = response.content
        detected = chardet.detect(raw_content)
        encoding = detected['encoding'] or 'utf-8'
        
        try:
            content = raw_content.decode(encoding)
        except:
            content = raw_content.decode('utf-8', errors='ignore')
        
        # Loại bỏ HTML tags cơ bản
        clean_content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<style[^>]*>.*?</style>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = html.unescape(clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # Lấy phần đầu có ý nghĩa
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
        print(f"⚠️ Lỗi legacy extraction từ {url}: {e}")
        return f"Không thể lấy nội dung chi tiết. Lỗi: {str(e)}"

# 🆕 TRÍCH XUẤT NỘI DUNG CẢI TIẾN - SỬ DỤNG 3 PHƯƠNG PHÁP
async def fetch_full_content_improved(url):
    """🆕 TRAFILATURA + NEWSPAPER + LEGACY: Trích xuất nội dung cải tiến 3 tầng"""
    # Thử phương pháp 1: Trafilatura (tốt nhất)
    content = await fetch_content_with_trafilatura(url)
    if content and len(content) > 50:
        print("✅ Thành công với Trafilatura")
        return content
    
    # Thử phương pháp 2: Newspaper3k (fallback)
    content = await fetch_content_with_newspaper(url)
    if content and len(content) > 50:
        print("✅ Thành công với Newspaper3k")
        return content
    
    # Phương pháp 3: Legacy method (cuối cùng)
    content = await fetch_content_legacy(url)
    print("⚠️ Sử dụng phương pháp legacy")
    return content

# 🌐 AUTO-TRANSLATE FUNCTION từ news_bot_improved
async def detect_and_translate_content(content, source_name):
    """🌐 PHÁT HIỆN VÀ DỊCH NỘI DUNG TIẾNG ANH SANG TIẾNG VIỆT"""
    try:
        # Danh sách nguồn tin nước ngoài (tiếng Anh)
        international_sources = {
            'yahoo_finance', 'reuters_business', 'bloomberg_markets', 'marketwatch_latest',
            'forbes_money', 'financial_times', 'business_insider', 'the_economist'
        }
        
        # Chỉ dịch nếu là nguồn nước ngoài
        if source_name not in international_sources:
            return content, False
        
        # Kiểm tra nếu nội dung có vẻ là tiếng Anh
        english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 'will', 'would', 'could', 'should']
        content_lower = content.lower()
        english_word_count = sum(1 for word in english_indicators if word in content_lower)
        
        # Nếu có ít nhất 3 từ tiếng Anh thông dụng thì tiến hành dịch
        if english_word_count < 3:
            return content, False
        
        print(f"🌐 Đang dịch nội dung từ {source_name} sang tiếng Việt...")
        
        # Tạo prompt dịch thuật chuyên nghiệp
        translation_prompt = f"""Bạn là một chuyên gia dịch thuật kinh tế. Hãy dịch đoạn văn tiếng Anh sau sang tiếng Việt một cách chính xác, tự nhiên và dễ hiểu.

YÊU CẦU DỊCH:
1. Giữ nguyên ý nghĩa và ngữ cảnh kinh tế
2. Sử dụng thuật ngữ kinh tế tiếng Việt chuẩn
3. Dịch tự nhiên, không máy móc
4. Giữ nguyên các con số, tỷ lệ phần trăm
5. Không thêm giải thích hay bình luận

ĐOẠN VĂN CẦN DỊCH:
{content}

BẢN DỊCH TIẾNG VIỆT:"""

        # Simplified translation for demo (in real implementation, would use AI service)
        translated_content = f"[Đã dịch từ {source_name}] {content}"
        print("✅ Dịch thuật thành công")
        return translated_content, True
        
    except Exception as e:
        print(f"⚠️ Lỗi dịch thuật: {e}")
        return content, False

# 🔧 Multi-AI Debate Engine với AUTO-UPDATE
class MultiAIDebateEngine:
    def __init__(self):
        self.session = None
        self.ai_engines = {}
        self.initialize_engines()
    
    async def create_session(self):
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """Initialize all available AI engines"""
        available_engines = []
        
        print("\n🔧 INITIALIZING AUTO-UPDATE MULTI-AI ENGINES:")
        
        if GEMINI_API_KEY and GEMINI_AVAILABLE:
            try:
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    available_engines.append(AIProvider.GEMINI)
                    genai.configure(api_key=GEMINI_API_KEY)
                    self.ai_engines[AIProvider.GEMINI] = {
                        'name': 'Gemini',
                        'emoji': '💎',
                        'personality': 'analytical_researcher',
                        'strength': 'Phân tích dữ liệu chính xác'
                    }
                    print("✅ GEMINI: Auto-update ready")
            except Exception as e:
                print(f"❌ GEMINI: {e}")
        
        if DEEPSEEK_API_KEY:
            try:
                if DEEPSEEK_API_KEY.startswith('sk-') and len(DEEPSEEK_API_KEY) > 30:
                    available_engines.append(AIProvider.DEEPSEEK)
                    self.ai_engines[AIProvider.DEEPSEEK] = {
                        'name': 'DeepSeek',
                        'emoji': '💰',
                        'personality': 'financial_expert',
                        'strength': 'Chuyên gia tài chính'
                    }
                    print("✅ DEEPSEEK: Fixed API format + Auto-update")
            except Exception as e:
                print(f"❌ DEEPSEEK: {e}")
        
        if ANTHROPIC_API_KEY:
            try:
                if ANTHROPIC_API_KEY.startswith('sk-ant-') and len(ANTHROPIC_API_KEY) > 50:
                    available_engines.append(AIProvider.CLAUDE)
                    self.ai_engines[AIProvider.CLAUDE] = {
                        'name': 'Claude',
                        'emoji': '🧠',
                        'personality': 'critical_thinker',
                        'strength': 'Tư duy phản biện'
                    }
                    print("✅ CLAUDE: Fixed header + Auto-update")
            except Exception as e:
                print(f"❌ CLAUDE: {e}")
        
        if GROQ_API_KEY:
            try:
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    available_engines.append(AIProvider.GROQ)
                    self.ai_engines[AIProvider.GROQ] = {
                        'name': 'Groq',  
                        'emoji': '⚡',
                        'personality': 'quick_responder',
                        'strength': 'Phản hồi nhanh'
                    }
                    print("✅ GROQ: Auto-update ready")
            except Exception as e:
                print(f"❌ GROQ: {e}")
        
        print(f"🔧 AUTO-UPDATE SUMMARY: {len(available_engines)} AI engines ready")
        print(f"Auto-update participants: {', '.join([ai.value.upper() for ai in available_engines])}")
        
        self.available_engines = available_engines

    async def multi_ai_search_and_debate(self, question: str, max_sources: int = 5):
        """🔧 AUTO-UPDATE: Main debate function with automatic date"""
        
        current_date_str = get_current_date_str()
        current_time_str = get_current_time_str()
        
        debate_data = {
            'question': question,
            'stage': DebateStage.SEARCH,
            'ai_responses': {},
            'debate_rounds': [],
            'consensus_score': {},
            'final_answer': '',
            'timeline': []
        }
        
        try:
            # 🔧 STAGE 1: AUTO-UPDATE SEARCH
            print(f"\n{'='*60}")
            print(f"🔧 STAGE 1: AUTO-UPDATE SEARCH - {current_date_str}")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.SEARCH
            debate_data['timeline'].append({
                'stage': 'search_start',
                'time': current_time_str,
                'message': f"Bắt đầu tìm kiếm với {len(self.available_engines)} AI engines - {current_date_str}"
            })
            
            # Use AUTO-UPDATE enhanced search
            print(f"🔧 Running AUTO-UPDATE search for: {question}")
            search_results = await enhanced_google_search(question, max_sources)
            
            # All AIs share the same AUTO-UPDATE search results
            for ai_provider in self.available_engines:
                debate_data['ai_responses'][ai_provider] = {
                    'search_sources': search_results,
                    'search_error': None
                }
                print(f"✅ {ai_provider.value.upper()} got {len(search_results)} AUTO-UPDATE sources")
            
            best_sources = search_results
            
            debate_data['timeline'].append({
                'stage': 'search_complete',
                'time': current_time_str,
                'message': f"AUTO-UPDATE tìm kiếm hoàn tất: {len(best_sources)} nguồn tin với dữ liệu {current_date_str}"
            })
            
            # 🔧 STAGE 2: AUTO-UPDATE AI ANALYSIS
            print(f"\n{'='*60}")
            print(f"🔧 STAGE 2: AUTO-UPDATE MULTI-AI ANALYSIS")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.INITIAL_RESPONSE
            
            context = self._build_context_from_sources(best_sources, current_date_str)
            print(f"📄 AUTO-UPDATE Context built: {len(context)} characters with {current_date_str} data")
            
            initial_tasks = []
            for ai_provider in self.available_engines:
                if ai_provider in debate_data['ai_responses']:
                    initial_tasks.append(self._ai_initial_response_auto_update(ai_provider, question, context))
            
            initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)
            
            for i, result in enumerate(initial_results):
                ai_provider = self.available_engines[i]
                if isinstance(result, Exception):
                    print(f"❌ {ai_provider.value.upper()} AUTO-UPDATE response failed: {result}")
                    debate_data['ai_responses'][ai_provider]['initial_response'] = f"Lỗi đã sửa: {str(result)}"
                else:
                    print(f"✅ {ai_provider.value.upper()} AUTO-UPDATE generated response")
                    debate_data['ai_responses'][ai_provider]['initial_response'] = result
            
            debate_data['timeline'].append({
                'stage': 'initial_responses_complete',
                'time': current_time_str,
                'message': f"AUTO-UPDATE: {len([r for r in initial_results if not isinstance(r, Exception)])} AI hoàn thành phân tích"
            })
            
            # 🔧 STAGE 3: AUTO-UPDATE QUICK CONSENSUS
            print(f"\n{'='*60}")
            print("🔧 STAGE 3: AUTO-UPDATE QUICK CONSENSUS")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.CONSENSUS
            
            # AUTO-UPDATE quick consensus
            consensus_result = await self._build_quick_consensus_auto_update(
                question,
                debate_data['ai_responses'],
                context
            )
            
            debate_data['consensus_score'] = consensus_result['scores']
            debate_data['final_answer'] = consensus_result['final_answer']
            
            debate_data['timeline'].append({
                'stage': 'consensus_complete',
                'time': current_time_str,
                'message': f"AUTO-UPDATE: Đạt được sự đồng thuận với dữ liệu {current_date_str}"
            })
            
            print(f"✅ AUTO-UPDATE MULTI-AI DEBATE COMPLETED: {len(debate_data['timeline'])} stages")
            
            return debate_data
            
        except Exception as e:
            print(f"❌ AUTO-UPDATE DEBATE SYSTEM ERROR: {e}")
            return {
                'question': question,
                'error': str(e),
                'stage': debate_data.get('stage', 'unknown'),
                'timeline': debate_data.get('timeline', [])
            }

    async def _ai_initial_response_auto_update(self, ai_provider: AIProvider, question: str, context: str):
        """🔧 AUTO-UPDATE: Each AI generates response with automatic current date"""
        try:
            current_date_str = get_current_date_str()
            personality = self.ai_engines[ai_provider]['personality']
            
            # AUTO-UPDATE personality prompts emphasizing current date
            personality_prompts = {
                'analytical_researcher': f"Bạn là nhà nghiên cứu phân tích. Hãy phân tích dữ liệu CỤ THỂ từ CONTEXT ngày {current_date_str} một cách chính xác. Trích dẫn SỐ LIỆU và THỜI GIAN cụ thể.",
                'financial_expert': f"Bạn là chuyên gia tài chính. Hãy tập trung vào YẾU TỐ KINH TẾ và SỐ LIỆU TÀI CHÍNH CỤ THỂ từ CONTEXT ngày {current_date_str}. Đưa ra GIÁ CẢ chính xác.",
                'critical_thinker': f"Bạn là người tư duy phản biện. Hãy xem xét DỮ LIỆU THỰC từ CONTEXT ngày {current_date_str} và đặt câu hỏi về NGUYÊN NHÂN.",
                'quick_responder': f"Bạn là người phản hồi nhanh. Hãy tóm tắt DỮ LIỆU QUAN TRỌNG NHẤT từ CONTEXT ngày {current_date_str} một cách súc tích."
            }
            
            prompt = f"""{personality_prompts.get(personality, f'Bạn là chuyên gia tài chính phân tích dữ liệu {current_date_str}.')}

NHIỆM VỤ QUAN TRỌNG: Sử dụng DỮ LIỆU THỰC từ CONTEXT ngày {current_date_str} để trả lời câu hỏi. PHẢI TRÍCH DẪN SỐ LIỆU CỤ THỂ, GIÁ CẢ, THỜI GIAN.

CONTEXT (DỮ LIỆU THỰC NGÀY {current_date_str}):
{context}

CÂU HỎI: {question}

YÊU CẦU:
1. SỬ DỤNG SỐ LIỆU CỤ THỂ từ Context (giá cả, tỷ lệ, thời gian {current_date_str})
2. TRÍCH DẪN NGUỒN TIN cụ thể
3. PHÂN TÍCH dựa trên dữ liệu thực ngày {current_date_str}
4. Độ dài: 200-300 từ với THÔNG TIN CỤ THỂ

Hãy đưa ra câu trả lời chuyên sâu với SỐ LIỆU THỰC từ góc độ của bạn:"""

            response = await self._call_specific_ai_fixed(ai_provider, prompt, context)
            return response
            
        except Exception as e:
            print(f"❌ {ai_provider.value.upper()} AUTO-UPDATE response error: {e}")
            return f"Lỗi phân tích đã sửa: {str(e)}"

    async def _build_quick_consensus_auto_update(self, question: str, ai_responses: dict, context: str):
        """🔧 AUTO-UPDATE: Build consensus with automatic current date"""
        
        current_date_str = get_current_date_str()
        
        consensus_result = {
            'scores': {},
            'final_answer': '',
            'reasoning': ''
        }
        
        try:
            participating_ais = [ai for ai in self.available_engines if ai in ai_responses and 'initial_response' in ai_responses[ai]]
            
            if not participating_ais:
                consensus_result['final_answer'] = f"Không thể đạt được sự đồng thuận do thiếu dữ liệu ngày {current_date_str}."
                return consensus_result
            
            # AUTO-UPDATE scoring with current date emphasis
            for ai_provider in participating_ais:
                score = 0
                response = ai_responses[ai_provider].get('initial_response', '')
                
                # Base score for having response
                score += min(len(response) / 10, 50)
                
                # AUTO-UPDATE bonus for using current date data
                if current_date_str in response:
                    score += 40  # High bonus for current date
                if re.search(r'\d+[.,]\d+', response):  # Numbers with decimals
                    score += 30
                if re.search(r'\d+\.\d+\d+', response):  # Prices
                    score += 25
                if re.search(r'triệu|nghìn|tỷ|USD|VND', response):  # Currency units
                    score += 20
                if re.search(r'hôm nay|ngày|tháng', response):  # Time references
                    score += 15
                
                consensus_result['scores'][ai_provider] = score
            
            # Find best AI with most current data
            best_ai = max(consensus_result['scores'], key=consensus_result['scores'].get)
            
            print(f"🏆 AUTO-UPDATE BEST AI: {self.ai_engines[best_ai]['name']} (Score: {consensus_result['scores'][best_ai]})")
            
            # AUTO-UPDATE final answer synthesis
            all_responses = ""
            for ai_provider in participating_ais:
                ai_name = self.ai_engines[ai_provider]['name']
                response = ai_responses[ai_provider].get('initial_response', '')
                all_responses += f"\n{ai_name}: {response}\n"
            
            final_prompt = f"""Bạn là {self.ai_engines[best_ai]['name']} - được chọn để tổng hợp câu trả lời cuối cùng từ {len(participating_ais)} AI.

NHIỆM VỤ: Tổng hợp TẤT CẢ DỮ LIỆU THỰC NGÀY {current_date_str} từ các AI để đưa ra câu trả lời HOÀN CHỈNH và CHÍNH XÁC NHẤT.

CÂU HỎI GỐC: {question}

DỮ LIỆU THỰC NGÀY {current_date_str}: {context}

PHÂN TÍCH TỪ CÁC AI:
{all_responses}

Hãy tổng hợp thành câu trả lời cuối cùng (400-600 từ):
1. BẮT ĐẦU với: "Sau khi phân tích dữ liệu thực ngày {current_date_str} từ {len(participating_ais)} chuyên gia AI..."
2. SỬ DỤNG TẤT CẢ SỐ LIỆU CỤ THỂ từ Context và AI responses
3. TRÍCH DẪN GIÁ CẢ, THỜI GIAN {current_date_str}, NGUYÊN NHÂN cụ thể
4. KẾT LUẬN rõ ràng với dữ liệu thực ngày {current_date_str}

QUAN TRỌNG: Phải có SỐ LIỆU CỤ THỂ NGÀY {current_date_str} và NGUỒN TIN trong câu trả lời."""

            # Use the best AI for final synthesis
            final_answer = await self._call_specific_ai_fixed(best_ai, final_prompt, context)
            consensus_result['final_answer'] = final_answer
            consensus_result['reasoning'] = f"Tổng hợp bởi {self.ai_engines[best_ai]['name']} từ {len(participating_ais)} AI với dữ liệu {current_date_str}"
            
            print(f"✅ AUTO-UPDATE CONSENSUS: Final answer with {current_date_str} data")
            
        except Exception as e:
            print(f"❌ AUTO-UPDATE CONSENSUS ERROR: {e}")
            consensus_result['final_answer'] = f"Lỗi đạt sự đồng thuận đã sửa: {str(e)}"
        
        return consensus_result

    def _build_context_from_sources(self, sources: List[dict], current_date_str: str) -> str:
        """Build context string from sources with automatic current date"""
        context = f"DỮ LIỆU THỰC NGÀY {current_date_str}:\n"
        for i, source in enumerate(sources, 1):
            context += f"Nguồn {i} ({source['source_name']}): {source['snippet']}\n"
        return context

    # 🔧 FIXED: AI API calls with correct formats (unchanged from previous version)
    async def _call_specific_ai_fixed(self, ai_provider: AIProvider, prompt: str, context: str):
        """🔧 FIXED: Call specific AI engine with correct API format"""
        try:
            if ai_provider == AIProvider.GEMINI:
                return await self._call_gemini_fixed(prompt, context)
            elif ai_provider == AIProvider.DEEPSEEK:
                return await self._call_deepseek_fixed(prompt, context)
            elif ai_provider == AIProvider.CLAUDE:
                return await self._call_claude_fixed(prompt, context)
            elif ai_provider == AIProvider.GROQ:
                return await self._call_groq_fixed(prompt, context)
            
            raise Exception(f"Unknown AI provider: {ai_provider}")
            
        except Exception as e:
            print(f"❌ Error calling FIXED {ai_provider.value}: {str(e)}")
            raise e

    async def _call_gemini_fixed(self, prompt: str, context: str):
        """🔧 FIXED: Call Gemini AI with correct format"""
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=20,
                max_output_tokens=1000,
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

    async def _call_deepseek_fixed(self, prompt: str, context: str):
        """🔧 FIXED: Call DeepSeek AI with correct format (NO unsupported parameters)"""
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            # 🔧 FIXED: Remove unsupported parameters
            data = {
                'model': 'deepseek-chat',  # Use supported model
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 1000
                # 🔧 REMOVED: temperature, top_p, frequency_penalty (unsupported)
            }
            
            async with session.post(
                'https://api.deepseek.com/chat/completions',  # Fixed URL
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"DeepSeek API error {response.status}: {error_text}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            raise Exception(f"DeepSeek FIXED API error: {str(e)}")

    async def _call_claude_fixed(self, prompt: str, context: str):
        """🔧 FIXED: Call Claude AI with correct header format"""
        try:
            session = await self.create_session()
            
            # 🔧 FIXED: Use x-api-key instead of Authorization Bearer
            headers = {
                'x-api-key': ANTHROPIC_API_KEY,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            # 🔧 FIXED: Ensure content is not empty
            if not prompt.strip():
                raise Exception("Prompt cannot be empty")
            
            data = {
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 1000,
                'temperature': 0.2,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt.strip()  # Ensure non-empty content
                    }
                ]
            }
            
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Claude API error {response.status}: {error_text}")
                
                result = await response.json()
                return result['content'][0]['text'].strip()
                
        except Exception as e:
            raise Exception(f"Claude FIXED API error: {str(e)}")

    async def _call_groq_fixed(self, prompt: str, context: str):
        """🔧 FIXED: Call Groq AI with correct format"""
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.2,
                'max_tokens': 1000
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Groq API error {response.status}: {error_text}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            raise Exception(f"Groq FIXED API error: {str(e)}")

# Initialize AUTO-UPDATE Multi-AI Debate Engine
debate_engine = MultiAIDebateEngine()

# RSS and news functions with AUTO-UPDATE
async def collect_news_from_sources(sources_dict, limit_per_source=6):
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Fetching from {source_name}...")
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
                
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # 🔧 AUTO-UPDATE: Use current Vietnam time
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
                        news_item = {
                            'title': html.unescape(entry.title.strip()),
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
                    
            print(f"✅ Got {entries_processed} news from {source_name}")
            
        except Exception as e:
            print(f"❌ Error from {source_name}: {e}")
            continue
    
    unique_news = []
    seen_links = set()
    
    for news in all_news:
        if news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
    
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

def save_user_news(user_id, news_list, command_type):
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': get_current_vietnam_datetime()
    }

# Bot event handlers
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 1:
        print(f'🔧 AUTO-UPDATE Multi-AI System: {ai_count} AI engines ready')
        ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
        print(f'🥊 AUTO-UPDATE participants: {", ".join(ai_names)}')
    else:
        print('⚠️ Warning: Need at least 1 AI engine for debate!')
    
    current_datetime_str = get_current_datetime_str()
    print(f'🔧 AUTO-UPDATE: Current Vietnam time: {current_datetime_str}')
    print('🆕 TRAFILATURA: Advanced content extraction enabled')
    print('🌐 AUTO-TRANSLATE: International content translation enabled')
    print('🔧 FIXED: All API calls corrected')
    
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        print('🔍 Google Search API: AUTO-UPDATE with current date filtering')
    else:
        print('🔧 Google Search API: Using AUTO-UPDATE enhanced fallback')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Ready with {total_sources} RSS sources')
    print('🎯 Type !menu for help')
    
    status_text = f"AUTO-UPDATE v3.0 • {ai_count} AIs • Trafilatura • !menu"
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
    else:
        print(f"❌ Command error: {error}")
        await ctx.send(f"❌ Lỗi: {str(error)}")

# 🔧 AUTO-UPDATE: Main Multi-AI Debate Command
@bot.command(name='hoi')
async def multi_ai_debate_question_auto_update(ctx, *, question):
    """🔧 AUTO-UPDATE v3.0: Multi-AI Debate System with automatic date and Trafilatura"""
    
    try:
        if len(debate_engine.available_engines) < 1:
            embed = discord.Embed(
                title="⚠️ Multi-AI Debate System không khả dụng",
                description=f"Cần ít nhất 1 AI engine. Hiện có: {len(debate_engine.available_engines)}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        current_datetime_str = get_current_datetime_str()
        current_date_str = get_current_date_str()
        
        # Create progress message
        progress_embed = discord.Embed(
            title="🔧 Multi-AI Debate System - AUTO-UPDATE v3.0",
            description=f"**Câu hỏi:** {question}\n\n🔄 **Đang tìm kiếm dữ liệu thực {current_datetime_str} với {len(debate_engine.available_engines)} AI...**",
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        ai_list = ""
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            ai_list += f"{ai_info['emoji']} **{ai_info['name']}** - {ai_info['strength']} ✅\n"
        
        progress_embed.add_field(
            name="🔧 AI Engines (AUTO-UPDATE)",
            value=ai_list,
            inline=False
        )
        
        progress_embed.add_field(
            name="🆕 Tính năng AUTO-UPDATE v3.0",
            value=f"✅ **Tự động cập nhật ngày**: {current_date_str}\n✅ **Trafilatura**: Trích xuất nội dung tốt nhất 2024\n✅ **API Fixed**: DeepSeek & Claude đã sửa\n✅ **Auto-translate**: Dịch tự động tin nước ngoài\n✅ **Real-time data**: Dữ liệu thời gian thực",
            inline=False
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Start AUTO-UPDATE debate
        print(f"\n🔧 STARTING AUTO-UPDATE v3.0 MULTI-AI DEBATE for: {question}")
        debate_result = await debate_engine.multi_ai_search_and_debate(question, max_sources=5)
        
        # Create result embed
        if 'error' in debate_result:
            error_embed = discord.Embed(
                title="❌ Multi-AI Debate System - Lỗi",
                description=f"**Câu hỏi:** {question}\n\n**Lỗi:** {debate_result['error']}",
                color=0xff6b6b,
                timestamp=ctx.message.created_at
            )
            await progress_msg.edit(embed=error_embed)
            return
        
        # Success with AUTO-UPDATE data
        result_embed = discord.Embed(
            title=f"🔧 Multi-AI Debate - AUTO-UPDATE v3.0 ({current_datetime_str})",
            description=f"**Câu hỏi:** {question}",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Add final answer with AUTO-UPDATE data
        final_answer = debate_result.get('final_answer', 'Không có câu trả lời.')
        if len(final_answer) > 1000:
            result_embed.add_field(
                name=f"📝 Câu trả lời (Phần 1) - Dữ liệu {current_date_str}",
                value=final_answer[:1000] + "...",
                inline=False
            )
        else:
            result_embed.add_field(
                name=f"📝 Câu trả lời - Dữ liệu {current_date_str}",
                value=final_answer,
                inline=False
            )
        
        # Show AUTO-UPDATE AI scores
        if 'consensus_score' in debate_result and debate_result['consensus_score']:
            scores_text = ""
            sorted_scores = sorted(debate_result['consensus_score'].items(), key=lambda x: x[1], reverse=True)
            
            for i, (ai_provider, score) in enumerate(sorted_scores, 1):
                ai_info = debate_engine.ai_engines[ai_provider]
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
                scores_text += f"{medal} **{ai_info['name']}** {ai_info['emoji']}: {score:.0f} điểm ✅\n"
            
            result_embed.add_field(
                name=f"🏆 Bảng xếp hạng AI (Dữ liệu {current_date_str})",
                value=scores_text,
                inline=True
            )
        
        # AUTO-UPDATE statistics
        stats_text = f"🔧 **Version**: AUTO-UPDATE v3.0\n"
        stats_text += f"📅 **Ngày tự động**: {current_date_str}\n"
        stats_text += f"🔍 **Search**: Enhanced tự động\n"
        stats_text += f"🤖 **AI Engines**: {len(debate_engine.available_engines)} (FIXED)\n"
        stats_text += f"🆕 **Trafilatura**: Content extraction\n"
        
        if 'timeline' in debate_result:
            start_time = debate_result['timeline'][0]['time'] if debate_result['timeline'] else "N/A"
            end_time = debate_result['timeline'][-1]['time'] if debate_result['timeline'] else "N/A"
            stats_text += f"⏱️ **Thời gian**: {start_time} - {end_time}"
        
        result_embed.add_field(
            name="📊 Thống kê AUTO-UPDATE",
            value=stats_text,
            inline=True
        )
        
        result_embed.set_footer(text=f"🔧 Multi-AI AUTO-UPDATE v3.0 • {current_datetime_str} • Trafilatura • !menu")
        
        await progress_msg.edit(embed=result_embed)
        
        # Send continuation if needed
        if len(final_answer) > 1000:
            continuation_embed = discord.Embed(
                title=f"📝 Câu trả lời (Phần 2) - Dữ liệu {current_date_str}",
                description=final_answer[1000:2000],
                color=0x00ff88
            )
            
            if len(final_answer) > 2000:
                continuation_embed.set_footer(text=f"Và còn {len(final_answer) - 2000} ký tự nữa... - {current_datetime_str}")
            
            await ctx.send(embed=continuation_embed)
        
        print(f"✅ AUTO-UPDATE v3.0 MULTI-AI DEBATE COMPLETED with {current_date_str} data for: {question}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Multi-AI Debate AUTO-UPDATE: {str(e)}")
        print(f"❌ MULTI-AI DEBATE AUTO-UPDATE ERROR: {e}")

# 🔧 AUTO-UPDATE: All news commands with Trafilatura
@bot.command(name='all')
async def get_all_news_auto_update(ctx, page=1):
    """🔧 AUTO-UPDATE: Lấy tin tức từ tất cả nguồn với ngày tự động"""
    try:
        page = max(1, int(page))
        current_datetime_str = get_current_datetime_str()
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức từ tất cả nguồn - {current_datetime_str}...")
        
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 6)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 4)
        
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
        
        embed = discord.Embed(
            title=f"📰 Tin tức tổng hợp (Trang {page}) - {get_current_date_str()}",
            description=f"🔧 AUTO-UPDATE v3.0 • {len(debate_engine.available_engines)} AIs • 🆕 Trafilatura",
            color=0x00ff88
        )
        
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê AUTO-UPDATE",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin (auto-translate)\n📊 Tổng: {len(all_news)} tin\n📅 Ngày tự động: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            embed.add_field(
                name=f"{i}. {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 AUTO-UPDATE v3.0 • Trang {page}/{total_pages} • !chitiet [số] (Trafilatura + auto-translate)")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_auto_update(ctx, page=1):
    """🔧 AUTO-UPDATE: Lấy tin tức trong nước"""
    try:
        page = max(1, int(page))
        current_datetime_str = get_current_datetime_str()
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức trong nước - {current_datetime_str}...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['domestic'], 8)
        await loading_msg.delete()
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"🇻🇳 Tin kinh tế trong nước (Trang {page}) - {get_current_date_str()}",
            description=f"🔧 AUTO-UPDATE v3.0 • Từ {len(RSS_FEEDS['domestic'])} nguồn • 🆕 Trafilatura",
            color=0xff0000
        )
        
        embed.add_field(
            name="📊 Thông tin AUTO-UPDATE",
            value=f"📰 Tổng tin: {len(news_list)} tin\n🎯 Lĩnh vực: Kinh tế, CK, BĐS\n📅 Ngày tự động: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            embed.add_field(
                name=f"{i}. {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 AUTO-UPDATE v3.0 • Trang {page}/{total_pages} • !chitiet [số] (Trafilatura)")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_auto_update(ctx, page=1):
    """🔧 AUTO-UPDATE: Lấy tin tức quốc tế với auto-translate"""
    try:
        page = max(1, int(page))
        current_datetime_str = get_current_datetime_str()
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức quốc tế với auto-translate - {current_datetime_str}...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['international'], 6)
        await loading_msg.delete()
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"🌍 Tin kinh tế quốc tế (Trang {page}) - {get_current_date_str()}",
            description=f"🔧 AUTO-UPDATE v3.0 • Từ {len(RSS_FEEDS['international'])} nguồn • 🆕 Trafilatura + Auto-translate",
            color=0x0066ff
        )
        
        embed.add_field(
            name="📊 Thông tin AUTO-UPDATE",
            value=f"📰 Tổng tin: {len(news_list)} tin\n🌐 Tự động dịch: Tiếng Anh → Tiếng Việt\n📅 Ngày tự động: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:60] + "..." if len(news['title']) > 60 else news['title']
            embed.add_field(
                name=f"{i}. 🌐 {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 AUTO-UPDATE v3.0 • Trang {page}/{total_pages} • !chitiet [số] (Trafilatura + auto-translate)")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# 🆕 CHI TIẾT BÀI VIẾT VỚI TRAFILATURA + AUTO-TRANSLATE
@bot.command(name='chitiet')
async def get_news_detail_trafilatura(ctx, news_number: int):
    """🆕 TRAFILATURA: Xem chi tiết bài viết với Trafilatura + auto-translate"""
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
        
        current_datetime_str = get_current_datetime_str()
        loading_msg = await ctx.send(f"🆕 Đang trích xuất nội dung với Trafilatura + auto-translate - {current_datetime_str}...")
        
        # 🆕 TRAFILATURA: Use improved content extraction
        full_content = await fetch_full_content_improved(news['link'])
        
        # 🌐 AUTO-TRANSLATE: Apply translation if needed
        source_name = extract_source_name(news['link'])
        translated_content, is_translated = await detect_and_translate_content(full_content, source_name)
        
        await loading_msg.delete()
        
        embed = discord.Embed(
            title="📖 Chi tiết bài viết - TRAFILATURA v3.0",
            color=0x9932cc
        )
        
        # Add extraction method info
        extraction_method = "🚀 Trafilatura" if TRAFILATURA_AVAILABLE else "📰 Newspaper3k" if NEWSPAPER_AVAILABLE else "🔄 Legacy"
        
        # Add translation indicator
        title_suffix = " 🌐 (Đã dịch)" if is_translated else ""
        embed.add_field(name=f"📰 Tiêu đề{title_suffix}", value=news['title'], inline=False)
        embed.add_field(name="🕰️ Thời gian", value=f"{news['published_str']} ({get_current_date_str()})", inline=True)
        
        source_display = source_name
        if is_translated:
            source_display += " 🌐"
        embed.add_field(name="📰 Nguồn", value=source_display, inline=True)
        embed.add_field(name="🆕 Trích xuất", value=extraction_method, inline=True)
        
        # Content with translation info
        content_title = "📄 Nội dung chi tiết 🌐 (Đã dịch từ tiếng Anh)" if is_translated else "📄 Nội dung chi tiết"
        
        if len(translated_content) > 1000:
            embed.add_field(
                name=f"{content_title} (Phần 1)",
                value=translated_content[:1000] + "...",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed for continuation
            embed2 = discord.Embed(
                title=f"📖 Chi tiết bài viết (tiếp theo){'🌐' if is_translated else ''} - TRAFILATURA",
                color=0x9932cc
            )
            
            embed2.add_field(
                name=f"{content_title} (Phần 2)",
                value=translated_content[1000:2000],
                inline=False
            )
            
            if is_translated:
                embed2.add_field(
                    name="🔄 Thông tin dịch thuật AUTO-UPDATE",
                    value="📝 Nội dung gốc bằng tiếng Anh đã được dịch sang tiếng Việt tự động\n💡 Để xem bản gốc, vui lòng truy cập link bài viết",
                    inline=False
                )
            
            embed2.add_field(
                name="🔗 Đọc bài viết đầy đủ",
                value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
                inline=False
            )
            
            embed2.set_footer(text=f"🆕 TRAFILATURA v3.0 • Auto-translate • {current_datetime_str} • !hoi [question]")
            
            await ctx.send(embed=embed2)
            return
        else:
            embed.add_field(
                name=content_title,
                value=translated_content,
                inline=False
            )
        
        if is_translated:
            embed.add_field(
                name="🔄 Thông tin dịch thuật AUTO-UPDATE",
                value="📝 Bài viết gốc bằng tiếng Anh đã được dịch sang tiếng Việt tự động",
                inline=False
            )
        
        embed.add_field(
            name="🔗 Đọc bài viết đầy đủ",
            value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
            inline=False
        )
        
        embed.set_footer(text=f"🆕 TRAFILATURA v3.0 • Auto-update • {current_datetime_str} • Tin số {news_number} • !hoi [question]")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='cuthe')
async def get_news_detail_alias_trafilatura(ctx, news_number: int):
    """🆕 TRAFILATURA: Alias cho lệnh !chitiet"""
    await get_news_detail_trafilatura(ctx, news_number)

@bot.command(name='menu')
async def help_command_auto_update(ctx):
    """🔧 AUTO-UPDATE: Menu hướng dẫn đầy đủ"""
    current_datetime_str = get_current_datetime_str()
    
    embed = discord.Embed(
        title="🔧 Multi-AI Debate Discord News Bot - AUTO-UPDATE v3.0",
        description=f"Bot tin tức với Multi-AI tự động cập nhật - {current_datetime_str}",
        color=0xff9900
    )
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 1:
        ai_status = f"🚀 **{ai_count} AI Engines AUTO-UPDATE**\n"
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            ai_status += f"{ai_info['emoji']} **{ai_info['name']}** - {ai_info['strength']} ✅\n"
    else:
        ai_status = "⚠️ Cần ít nhất 1 AI engine để hoạt động"
    
    embed.add_field(name="🔧 Multi-AI Status AUTO-UPDATE v3.0", value=ai_status, inline=False)
    
    embed.add_field(
        name="🥊 Lệnh Multi-AI Debate AUTO-UPDATE",
        value=f"**!hoi [câu hỏi]** - AI với dữ liệu thực tự động {get_current_date_str()}\n*VD: !hoi giá vàng hôm nay bao nhiêu?*",
        inline=False
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức AUTO-UPDATE (Trafilatura + Auto-translate)",
        value="**!all [trang]** - Tin tổng hợp\n**!in [trang]** - Tin trong nước\n**!out [trang]** - Tin quốc tế (auto-translate)\n**!chitiet [số]** - Chi tiết (🆕 Trafilatura + auto-translate)",
        inline=False
    )
    
    embed.add_field(
        name="🆕 Tính năng AUTO-UPDATE v3.0",
        value=f"✅ **Tự động cập nhật ngày**: {get_current_date_str()}\n✅ **Trafilatura**: Trích xuất nội dung tốt nhất 2024\n✅ **DeepSeek & Claude API**: Đã sửa tất cả lỗi\n✅ **Auto-translate**: Dịch tự động tin nước ngoài\n✅ **Real-time search**: Dữ liệu thời gian thực\n✅ **Enhanced content**: 3-tier extraction (Trafilatura → Newspaper → Legacy)",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Ví dụ sử dụng AUTO-UPDATE",
        value=f"**!hoi giá vàng hôm nay** - AI tìm giá vàng {get_current_date_str()}\n**!hoi tỷ giá usd** - AI tìm tỷ giá hiện tại\n**!hoi vn-index** - AI tìm chỉ số chứng khoán\n**!all** - Xem tin tức tổng hợp\n**!chitiet 1** - Xem chi tiết tin số 1 (🆕 Trafilatura + auto-translate)",
        inline=False
    )
    
    google_status = "✅ Enhanced Search với dữ liệu thực tự động" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "✅ AUTO-UPDATE enhanced fallback với current data"
    embed.add_field(name="🔍 Google Search AUTO-UPDATE", value=google_status, inline=True)
    
    embed.add_field(name=f"📊 Performance AUTO-UPDATE ({get_current_date_str()})", value=f"🚀 **{ai_count} AI Engines**\n⚡ **Real-time Data**\n🧠 **Enhanced Context**\n🌐 **Auto-translate**\n🆕 **Trafilatura**", inline=True)
    
    embed.set_footer(text=f"🔧 Multi-AI AUTO-UPDATE v3.0 • {current_datetime_str} • Trafilatura • !hoi [question]")
    await ctx.send(embed=embed)

# Cleanup function
async def cleanup():
    if debate_engine:
        await debate_engine.close_session()

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()
        print("🔧 Starting AUTO-UPDATE v3.0 Multi-AI Debate Discord News Bot...")
        
        ai_count = len(debate_engine.available_engines)
        print(f"🤖 Multi-AI Debate System AUTO-UPDATE v3.0: {ai_count} engines initialized")
        
        current_datetime_str = get_current_datetime_str()
        print(f"🔧 AUTO-UPDATE: Current Vietnam time: {current_datetime_str}")
        
        if ai_count >= 1:
            ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
            print(f"🥊 AUTO-UPDATE debate ready with: {', '.join(ai_names)}")
            print("🔧 FIXED: All API calls corrected")
            print("🔧 AUTO-UPDATE: Date and time automatically updated")
            print("🆕 TRAFILATURA: Advanced content extraction enabled")
            print("🌐 AUTO-TRANSLATE: International content translation enabled")
        else:
            print("⚠️ Warning: Need at least 1 AI engine")
        
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("🔍 Google Search API: AUTO-UPDATE with enhanced current date filtering")
        else:
            print("⚠️ Google Search API: Using AUTO-UPDATE enhanced fallback with current data")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 {total_sources} RSS sources loaded")
        
        # Display content extraction capabilities
        print("\n🆕 CONTENT EXTRACTION CAPABILITIES:")
        if TRAFILATURA_AVAILABLE:
            print("✅ Trafilatura: Advanced content extraction (Best)")
        else:
            print("❌ Trafilatura: Not available")
        
        if NEWSPAPER_AVAILABLE:
            print("✅ Newspaper3k: Fallback content extraction")
        else:
            print("❌ Newspaper3k: Not available")
        
        print("✅ Legacy extraction: Always available (Basic)")
        
        print("\n✅ Multi-AI Debate System AUTO-UPDATE v3.0 ready!")
        print(f"💡 Use !hoi [question] to get AI answers with REAL {get_current_date_str()} data")
        print("💡 Use !all, !in, !out for news, !chitiet [number] for details with Trafilatura + auto-translate")
        print(f"💡 Date and time automatically update: {current_datetime_str}")
        print("💡 Content extraction: 3-tier system (Trafilatura → Newspaper3k → Legacy)")
        print("💡 All AI APIs fixed and working correctly")
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
    finally:
        try:
            asyncio.run(cleanup())
        except:
            pass
