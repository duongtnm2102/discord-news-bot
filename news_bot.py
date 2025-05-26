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
from urllib.parse import urljoin
import html
import chardet
import pytz
from keep_alive import keep_alive

# 🆕 THÊM CÁC THỬ VIỆN MẠNH MẼ CHO TRÍCH XUẤT NỘI DUNG
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
    print("✅ Trafilatura đã được tích hợp - Trích xuất nội dung cải tiến!")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ Trafilatura chưa cài đặt. Chạy: pip install trafilatura")

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
    print("✅ Newspaper3k đã được tích hợp - Fallback extraction!")
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ Newspaper3k chưa cài đặt. Chạy: pip install newspaper3k")

# 🤖 THÊM AI GIẢI THÍCH THÔNG MINH
try:
    import groq
    GROQ_AVAILABLE = True
    print("🚀 Groq AI đã được tích hợp - Giải thích thông minh!")
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq chưa cài đặt. Chạy: pip install groq")

try:
    from googleapiclient.discovery import build
    GOOGLE_SEARCH_AVAILABLE = True
    print("🔍 Google Search API đã được tích hợp - Tìm nguồn tin đáng tin cậy!")
except ImportError:
    GOOGLE_SEARCH_AVAILABLE = False
    print("⚠️ Google API Client chưa cài đặt. Chạy: pip install google-api-python-client")

import json

# Cấu hình bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔒 BẢO MẬT: Lấy token từ environment variable
TOKEN = os.getenv('DISCORD_TOKEN')

# 🤖 CẤU HÌNH AI APIS
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# Khởi tạo Groq client
if GROQ_AVAILABLE and GROQ_API_KEY:
    try:
        groq_client = groq.Groq(api_key=GROQ_API_KEY)
        print("🚀 Groq AI client đã sẵn sàng!")
    except Exception as e:
        print(f"⚠️ Lỗi khởi tạo Groq client: {e}")
        GROQ_AVAILABLE = False
else:
    GROQ_AVAILABLE = False

# Khởi tạo Google Search client
if GOOGLE_SEARCH_AVAILABLE and GOOGLE_API_KEY and GOOGLE_CSE_ID:
    try:
        google_search_service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        print("🔍 Google Search API đã sẵn sàng!")
    except Exception as e:
        print(f"⚠️ Lỗi khởi tạo Google Search: {e}")
        GOOGLE_SEARCH_AVAILABLE = False
else:
    GOOGLE_SEARCH_AVAILABLE = False

if not TOKEN:
    print("❌ CẢNH BÁO: Không tìm thấy DISCORD_TOKEN trong environment variables!")
    print("🔧 Vui lòng thêm DISCORD_TOKEN vào Render Environment Variables")
    exit(1)

# 🇻🇳 TIMEZONE VIỆT NAM - ĐÃ SỬA LỖI MÚI GIỜ
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# Lưu trữ tin tức theo từng user
user_news_cache = {}

# RSS feeds đã được kiểm tra và xác nhận hoạt động
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC - ĐÃ KIỂM TRA ===
    'domestic': {
        # CafeF - RSS chính hoạt động tốt
        'cafef_main': 'https://cafef.vn/index.rss',
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
        'cafef_batdongsan': 'https://cafef.vn/bat-dong-san.rss',
        'cafef_taichinh': 'https://cafef.vn/tai-chinh-ngan-hang.rss',
        'cafef_vimo': 'https://cafef.vn/vi-mo-dau-tu.rss',
        
        # CafeBiz - RSS tổng hợp
        'cafebiz_main': 'https://cafebiz.vn/index.rss',
        
        # Báo Đầu tư - RSS hoạt động
        'baodautu_main': 'https://baodautu.vn/rss.xml',
        
        # VnEconomy - RSS tin tức chính
        'vneconomy_main': 'https://vneconomy.vn/rss/home.rss',
        'vneconomy_chungkhoan': 'https://vneconomy.vn/rss/chung-khoan.rss',
        
        # VnExpress Kinh doanh 
        'vnexpress_kinhdoanh': 'https://vnexpress.net/rss/kinh-doanh.rss',
        'vnexpress_chungkhoan': 'https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss',
        
        # Thanh Niên - RSS kinh tế
        'thanhnien_kinhtevimo': 'https://thanhnien.vn/rss/kinh-te/vi-mo.rss',
        'thanhnien_chungkhoan': 'https://thanhnien.vn/rss/kinh-te/chung-khoan.rss',
        
        # Nhân Dân - RSS tài chính chứng khoán
        'nhandanonline_tc': 'https://nhandan.vn/rss/tai-chinh-chung-khoan.rss'
    },
    
    # === KINH TẾ QUỐC TẾ ===
    'international': {
        'yahoo_finance': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
        'reuters_business': 'https://feeds.reuters.com/reuters/businessNews',
        'bloomberg_markets': 'https://feeds.bloomberg.com/markets/news.rss',
        'marketwatch_latest': 'https://feeds.marketwatch.com/marketwatch/realtimeheadlines/',
        'forbes_money': 'https://www.forbes.com/money/feed/',
        'financial_times': 'https://www.ft.com/rss/home',
        'business_insider': 'https://feeds.businessinsider.com/custom/all',
        'the_economist': 'https://www.economist.com/rss'
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
        return datetime.now(VN_TIMEZONE)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} đã online!')
    print(f'📊 Kết nối với {len(bot.guilds)} server(s)')
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Sẵn sàng cung cấp tin từ {total_sources} nguồn ĐÃ KIỂM TRA')
    print(f'🇻🇳 Trong nước: {len(RSS_FEEDS["domestic"])} nguồn')
    print(f'🌍 Quốc tế: {len(RSS_FEEDS["international"])} nguồn')
    print('🎯 Lĩnh vực: Kinh tế, Chứng khoán, Vĩ mô, Bất động sản')
    
    # Kiểm tra thư viện đã cài đặt
    if TRAFILATURA_AVAILABLE:
        print('🚀 Trafilatura: Trích xuất nội dung cải tiến (94.5% độ chính xác)')
    if NEWSPAPER_AVAILABLE:
        print('📰 Newspaper3k: Fallback extraction cho tin tức')
    
    print('🕰️ Múi giờ: Đã sửa lỗi - Hiển thị chính xác giờ Việt Nam')
    print('🎯 Gõ !menu để xem hướng dẫn')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="tin tức VN chuẩn giờ | !menu"
        )
    )

async def search_reliable_sources(query, max_results=5):
    """🔍 TÌM KIẾM NGUỒN TIN ĐÁNG TIN CẬY BẰNG GOOGLE SEARCH API"""
    try:
        if not GOOGLE_SEARCH_AVAILABLE:
            return []
        
        print(f"🔍 Tìm kiếm: {query}")
        
        # Thêm từ khóa để tìm nguồn tin uy tín
        enhanced_query = f"{query} site:reuters.com OR site:bloomberg.com OR site:bbc.com OR site:vnexpress.net OR site:cafef.vn OR site:tuoitre.vn OR site:economist.com OR site:ft.com"
        
        # Gọi Google Custom Search API
        result = google_search_service.cse().list(
            q=enhanced_query,
            cx=GOOGLE_CSE_ID,
            num=max_results,
            lr='lang_vi|lang_en',  # Tiếng Việt và tiếng Anh
            safe='active'
        ).execute()
        
        sources = []
        if 'items' in result:
            for item in result['items']:
                source = {
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source_name': extract_source_name(item.get('link', ''))
                }
                sources.append(source)
        
        print(f"✅ Tìm thấy {len(sources)} nguồn tin đáng tin cậy")
        return sources
        
    except Exception as e:
        print(f"⚠️ Lỗi Google Search: {e}")
        return []

def extract_source_name(url):
    """Trích xuất tên nguồn tin từ URL"""
    domain_mapping = {
        'reuters.com': 'Reuters',
        'bloomberg.com': 'Bloomberg',
        'bbc.com': 'BBC',
        'vnexpress.net': 'VnExpress',
        'cafef.vn': 'CafeF',
        'tuoitre.vn': 'Tuổi Trẻ',
        'economist.com': 'The Economist',
        'ft.com': 'Financial Times',
        'forbes.com': 'Forbes',
        'marketwatch.com': 'MarketWatch',
        'cnbc.com': 'CNBC'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    # Fallback: extract domain name
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain.replace('www.', '').title()
    except:
        return 'Unknown Source'

async def detect_and_translate_content(content, source_name):
    """🌐 PHÁT HIỆN VÀ DỊCH NỘI DUNG TIẾNG ANH SANG TIẾNG VIỆT"""
    try:
        # Danh sách nguồn tin nước ngoài (tiếng Anh)
        international_sources = {
            'yahoo_finance', 'reuters_business', 'bloomberg_markets', 'marketwatch_latest',
            'forbes_money', 'financial_times', 'business_insider', 'the_economist'
        }
        
        # Chỉ dịch nếu là nguồn nước ngoài và có Groq AI
        if source_name not in international_sources or not GROQ_AVAILABLE:
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

        # Gọi Groq AI để dịch
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": translation_prompt
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,  # Ít creativity để dịch chính xác
            max_tokens=2000
        )
        
        translated_content = chat_completion.choices[0].message.content.strip()
        print("✅ Dịch thuật thành công")
        return translated_content, True
        
    except Exception as e:
        print(f"⚠️ Lỗi dịch thuật: {e}")
        return content, False

async def ai_explain_with_sources(question, sources):
    """🤖 SỬ DỤNG GROQ AI ĐỂ GIẢI THÍCH VỚI NGUỒN TIN"""
    try:
        if not GROQ_AVAILABLE:
            return "⚠️ Groq AI không khả dụng. Vui lòng cấu hình GROQ_API_KEY."
        
        # Tạo context từ các nguồn tin
        context = "\n".join([
            f"Nguồn {i+1} ({source['source_name']}): {source['snippet']}"
            for i, source in enumerate(sources[:3])  # Chỉ lấy 3 nguồn đầu
        ])
        
        # Tạo prompt cho AI
        prompt = f"""Bạn là chuyên gia kinh tế. Hãy giải thích thuật ngữ hoặc khái niệm sau một cách đơn giản, dễ hiểu:

Câu hỏi: {question}

Thông tin từ các nguồn tin đáng tin cậy:
{context}

Yêu cầu:
1. Giải thích đơn giản, dễ hiểu cho người bình thường
2. Sử dụng thông tin từ các nguồn đã cung cấp
3. Đưa ra ví dụ cụ thể nếu có thể
4. Giữ câu trả lời trong khoảng 300-500 từ
5. Viết bằng tiếng Việt

Câu trả lời:"""

        # Gọi Groq AI
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile",  # Model mạnh nhất của Groq
            temperature=0.3,  # Ít creativity, nhiều accuracy
            max_tokens=1000
        )
        
        explanation = chat_completion.choices[0].message.content
        print("🤖 AI đã tạo giải thích thành công")
        return explanation
        
    except Exception as e:
        print(f"⚠️ Lỗi Groq AI: {e}")
        return f"⚠️ Không thể tạo giải thích AI. Lỗi: {str(e)}"
    """🆕 TRÍCH XUẤT NỘI DUNG BẰNG TRAFILATURA - TỐT NHẤT 2024"""
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
        
async def fetch_content_with_newspaper(url):
    """📰 TRÍCH XUẤT BẰNG NEWSPAPER3K - FALLBACK"""
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
    """🔄 PHƯƠNG PHÁP CŨ - CUỐI CÙNG FALLBACK"""
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

async def fetch_full_content_improved(url):
    """🆕 TRÍCH XUẤT NỘI DUNG CẢI TIẾN - SỬ DỤNG 3 PHƯƠNG PHÁP"""
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

async def fetch_content_with_newspaper(url):
    """📰 TRÍCH XUẤT BẰNG NEWSPAPER3K - FALLBACK"""
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
    """🔄 PHƯƠNG PHÁP CŨ - CUỐI CÙNG FALLBACK"""
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

async def fetch_full_content_improved(url):
    """🆕 TRÍCH XUẤT NỘI DUNG CẢI TIẾN - SỬ DỤNG 3 PHƯƠNG PHÁP"""
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

async def collect_news_from_sources(sources_dict, limit_per_source=8):
    """Thu thập tin tức với xử lý múi giờ chính xác"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Đang lấy tin từ {source_name}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8'
            }
            
            try:
                response = requests.get(rss_url, headers=headers, timeout=10)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
            except Exception as req_error:
                print(f"⚠️ Lỗi request từ {source_name}: {req_error}")
                feed = feedparser.parse(rss_url)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"⚠️ Không có tin từ {source_name}")
                continue
                
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # 🔧 XỬ LÝ THỜI GIAN CHÍNH XÁC
                    vn_time = datetime.now(VN_TIMEZONE)  # Default fallback
                    
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.updated_parsed)
                    
                    # Lấy mô tả
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:500] + "..." if len(entry.summary) > 500 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:500] + "..." if len(entry.description) > 500 else entry.description
                    
                    if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                        continue
                    
                    title = html.unescape(entry.title.strip())
                    
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
                    print(f"⚠️ Lỗi xử lý tin từ {source_name}: {entry_error}")
                    continue
                    
            print(f"✅ Lấy được {entries_processed} tin từ {source_name}")
            
        except Exception as e:
            print(f"❌ Lỗi khi lấy tin từ {source_name}: {e}")
            continue
    
    print(f"📊 Tổng cộng lấy được {len(all_news)} tin từ tất cả nguồn")
    
    # Loại bỏ tin trùng lặp
    unique_news = remove_duplicate_news(all_news)
    print(f"🔄 Sau khi loại trùng còn {len(unique_news)} tin")
    
    # Sắp xếp theo thời gian mới nhất
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

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
    import re
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = ' '.join(title.split())
    
    words = title.split()[:10]
    return ' '.join(words)

def save_user_news(user_id, news_list, command_type):
    """Lưu tin tức của user để sử dụng cho lệnh !detail"""
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': datetime.now(VN_TIMEZONE)
    }

@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Lấy tin tức từ tất cả nguồn với múi giờ chính xác"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức từ tất cả nguồn...")
        
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 8)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 6)
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        all_news.sort(key=lambda x: x['published'], reverse=True)
        
        # Phân trang
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        # Tạo embed với thông tin múi giờ
        embed = discord.Embed(
            title=f"📰 Tin tức kinh tế tổng hợp (Trang {page})",
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Trafilatura • 📰 Từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Emoji map
        emoji_map = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️', 'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹', 
            'marketwatch_latest': '📈', 'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
        # Thống kê
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê trang này",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin",
            inline=False
        )
        
        # Hiển thị tin tức với thời gian chính xác
        source_names = {
            'cafef_main': 'CafeF', 'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafebiz_main': 'CafeBiz',
            'baodautu_main': 'Báo Đầu tư', 'vneconomy_main': 'VnEconomy', 'vneconomy_chungkhoan': 'VnEconomy CK',
            'vnexpress_kinhdoanh': 'VnExpress KD', 'vnexpress_chungkhoan': 'VnExpress CK',
            'thanhnien_kinhtevimo': 'Thanh Niên VM', 'thanhnien_chungkhoan': 'Thanh Niên CK',
            'nhandanonline_tc': 'Nhân Dân TC', 'yahoo_finance': 'Yahoo Finance', 'reuters_business': 'Reuters',
            'bloomberg_markets': 'Bloomberg', 'marketwatch_latest': 'MarketWatch', 'forbes_money': 'Forbes',
            'financial_times': 'Financial Times', 'business_insider': 'Business Insider', 'the_economist': 'The Economist'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:70] + "..." if len(news['title']) > 70 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Bot cải tiến • Trang {page}/{total_pages} • !all {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!all [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news(ctx, page=1):
    """Lấy tin tức từ các nguồn trong nước với múi giờ chính xác"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức trong nước...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['domestic'], 10)
        
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
            title=f"🇻🇳 Tin kinh tế trong nước (Trang {page})",
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Trafilatura • Từ {len(RSS_FEEDS['domestic'])} nguồn chuyên ngành",
            color=0xff0000,
            timestamp=ctx.message.created_at
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin có sẵn: {len(news_list)} tin\n🎯 Lĩnh vực: Kinh tế, Chứng khoán, Bất động sản, Vĩ mô",
            inline=False
        )
        
        # Hiển thị tin tức trong nước
        emoji_map = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️'
        }
        
        source_names = {
            'cafef_main': 'CafeF', 'cafef_chungkhoan': 'CafeF CK', 'cafef_batdongsan': 'CafeF BĐS',
            'cafef_taichinh': 'CafeF TC', 'cafef_vimo': 'CafeF VM', 'cafebiz_main': 'CafeBiz',
            'baodautu_main': 'Báo Đầu tư', 'vneconomy_main': 'VnEconomy', 'vneconomy_chungkhoan': 'VnEconomy CK',
            'vnexpress_kinhdoanh': 'VnExpress KD', 'vnexpress_chungkhoan': 'VnExpress CK',
            'thanhnien_kinhtevimo': 'Thanh Niên VM', 'thanhnien_chungkhoan': 'Thanh Niên CK',
            'nhandanonline_tc': 'Nhân Dân TC'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:70] + "..." if len(news['title']) > 70 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Bot cải tiến • Trang {page}/{total_pages} • !in {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news(ctx, page=1):
    """Lấy tin tức từ các nguồn quốc tế với múi giờ chính xác"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức quốc tế...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['international'], 8)
        
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
            title=f"🌍 Tin kinh tế quốc tế (Trang {page})",
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Trafilatura • Từ {len(RSS_FEEDS['international'])} nguồn hàng đầu",
            color=0x0066ff,
            timestamp=ctx.message.created_at
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin có sẵn: {len(news_list)} tin",
            inline=False
        )
        
        emoji_map = {
            'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹', 'marketwatch_latest': '📈',
            'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
        source_names = {
            'yahoo_finance': 'Yahoo Finance', 'reuters_business': 'Reuters', 'bloomberg_markets': 'Bloomberg', 
            'marketwatch_latest': 'MarketWatch', 'forbes_money': 'Forbes', 'financial_times': 'Financial Times', 
            'business_insider': 'Business Insider', 'the_economist': 'The Economist'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '🌍')
            title = news['title'][:70] + "..." if len(news['title']) > 70 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Bot cải tiến • Trang {page}/{total_pages} • !out {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """🆕 XEM CHI TIẾT BẰNG TRAFILATURA + NEWSPAPER3K + TỰ ĐỘNG DỊCH"""
    try:
        user_id = ctx.author.id
        
        if user_id not in user_news_cache:
            await ctx.send("❌ Bạn chưa xem tin tức nào! Hãy dùng `!all`, `!in`, hoặc `!out` trước.")
            return
        
        user_data = user_news_cache[user_id]
        news_list = user_data['news']
        
        if news_number < 1 or news_number > len(news_list):
            await ctx.send(f"❌ Số không hợp lệ! Chọn từ 1 đến {len(news_list)}")
            return
        
        news = news_list[news_number - 1]
        
        # Thông báo đang tải với thông tin công nghệ
        if TRAFILATURA_AVAILABLE and NEWSPAPER_AVAILABLE:
            loading_msg = await ctx.send("🚀 Đang trích xuất nội dung bằng Trafilatura + Newspaper3k...")
        elif TRAFILATURA_AVAILABLE:
            loading_msg = await ctx.send("🚀 Đang trích xuất nội dung bằng Trafilatura...")
        else:
            loading_msg = await ctx.send("⏳ Đang trích xuất nội dung...")
        
        # Sử dụng function cải tiến
        full_content = await fetch_full_content_improved(news['link'])
        
        # 🌐 TÍNH NĂNG MỚI: Tự động dịch nếu là tin nước ngoài
        translated_content, is_translated = await detect_and_translate_content(full_content, news['source'])
        
        await loading_msg.delete()
        
        # Tạo embed đẹp hơn
        embed = discord.Embed(
            title="📖 Chi tiết bài viết",
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        # Emoji cho nguồn
        emoji_map = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️', 'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹', 
            'marketwatch_latest': '📈', 'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
        source_names = {
            'cafef_main': 'CafeF', 'cafef_chungkhoan': 'CafeF Chứng khoán', 'cafef_batdongsan': 'CafeF Bất động sản',
            'cafef_taichinh': 'CafeF Tài chính', 'cafef_vimo': 'CafeF Vĩ mô', 'cafebiz_main': 'CafeBiz',
            'baodautu_main': 'Báo Đầu tư', 'vneconomy_main': 'VnEconomy', 'vneconomy_chungkhoan': 'VnEconomy Chứng khoán',
            'vnexpress_kinhdoanh': 'VnExpress Kinh doanh', 'vnexpress_chungkhoan': 'VnExpress Chứng khoán',
            'thanhnien_kinhtevimo': 'Thanh Niên Vĩ mô', 'thanhnien_chungkhoan': 'Thanh Niên Chứng khoán',
            'nhandanonline_tc': 'Nhân Dân Tài chính', 'yahoo_finance': 'Yahoo Finance', 'reuters_business': 'Reuters Business',
            'bloomberg_markets': 'Bloomberg Markets', 'marketwatch_latest': 'MarketWatch', 'forbes_money': 'Forbes Money',
            'financial_times': 'Financial Times', 'business_insider': 'Business Insider', 'the_economist': 'The Economist'
        }
        
        emoji = emoji_map.get(news['source'], '📰')
        source_display = source_names.get(news['source'], news['source'])
        
        # Thêm indicator dịch thuật vào tiêu đề
        title_suffix = " 🌐 (Đã dịch)" if is_translated else ""
        embed.add_field(
            name=f"{emoji} Tiêu đề{title_suffix}",
            value=news['title'],
            inline=False
        )
        
        embed.add_field(
            name="🕰️ Thời gian (VN)",
            value=news['published_str'],
            inline=True
        )
        
        embed.add_field(
            name="📰 Nguồn",
            value=source_display + (" 🌐" if is_translated else ""),
            inline=True
        )
        
        # Sử dụng nội dung đã dịch (nếu có)
        content_to_display = translated_content
        
        # Hiển thị nội dung đã được xử lý
        if len(content_to_display) > 1000:
            # Chia nội dung thành 2 phần
            content_title = "📄 Nội dung chi tiết 🌐 (Đã dịch sang tiếng Việt)" if is_translated else "📄 Nội dung chi tiết"
            
            embed.add_field(
                name=f"{content_title} (Phần 1)",
                value=content_to_display[:1000] + "...",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Tạo embed thứ 2
            embed2 = discord.Embed(
                title=f"📖 Chi tiết bài viết (tiếp theo){'🌐' if is_translated else ''}",
                color=0x9932cc
            )
            
            embed2.add_field(
                name=f"{content_title} (Phần 2)",
                value=content_to_display[1000:2000],
                inline=False
            )
            
            # Thêm thông tin về bản gốc nếu đã dịch
            if is_translated:
                embed2.add_field(
                    name="🔄 Thông tin dịch thuật",
                    value="📝 Nội dung gốc bằng tiếng Anh đã được dịch sang tiếng Việt bằng Groq AI\n💡 Để xem bản gốc, vui lòng truy cập link bài viết",
                    inline=False
                )
            
            embed2.add_field(
                name="🔗 Đọc bài viết đầy đủ",
                value=f"[Nhấn để đọc toàn bộ bài viết gốc]({news['link']})",
                inline=False
            )
            
            # Thông tin công nghệ sử dụng
            tech_info = "🚀 Trafilatura" if TRAFILATURA_AVAILABLE else "📰 Legacy"
            if NEWSPAPER_AVAILABLE:
                tech_info += " + Newspaper3k"
            if is_translated:
                tech_info += " + 🌐 Groq AI Translation"
            
            embed2.set_footer(text=f"{tech_info} • Từ lệnh: {user_data['command']} • Tin số {news_number}")
            
            await ctx.send(embed=embed2)
            return
        else:
            content_title = "📄 Nội dung chi tiết 🌐 (Đã dịch sang tiếng Việt)" if is_translated else "📄 Nội dung chi tiết"
            embed.add_field(
                name=content_title,
                value=content_to_display,
                inline=False
            )
        
        # Thêm thông tin về dịch thuật nếu có
        if is_translated:
            embed.add_field(
                name="🔄 Thông tin dịch thuật",
                value="📝 Bài viết gốc bằng tiếng Anh đã được dịch sang tiếng Việt bằng Groq AI",
                inline=False
            )
        
        embed.add_field(
            name="🔗 Đọc bài viết đầy đủ",
            value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
            inline=False
        )
        
        # Thông tin công nghệ sử dụng
        tech_info = "🚀 Trafilatura" if TRAFILATURA_AVAILABLE else "📰 Legacy"
        if NEWSPAPER_AVAILABLE:
            tech_info += " + Newspaper3k"
        if is_translated:
            tech_info += " + 🌐 Groq AI Translation"
        
        embed.set_footer(text=f"{tech_info} • Từ lệnh: {user_data['command']} • Tin số {news_number} • !menu để xem thêm lệnh")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# Alias cho lệnh chitiet
@bot.command(name='cuthe')
async def get_news_detail_alias(ctx, news_number: int):
    """Alias cho lệnh !chitiet"""
    await get_news_detail(ctx, news_number)

@bot.command(name='menu')
async def help_command(ctx):
    """Hiển thị menu lệnh - ĐÃ CẬP NHẬT VỚI AI"""
    embed = discord.Embed(
        title="🤖🚀 Menu News Bot",
        description="Bot tin tức kinh tế với AI giải thích thông minh",
        color=0xff9900
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="""
**!all [trang]** - Tin từ tất cả nguồn (12 tin/trang)
**!in [trang]** - Tin trong nước (12 tin/trang)  
**!out [trang]** - Tin quốc tế (12 tin/trang)
**!chitiet [số]** - Xem nội dung chi tiết + 🌐 Tự động dịch
        """,
        inline=False
    )
    
    embed.add_field(
        name="🤖 Lệnh AI thông minh",
        value="""
**!hoi [câu hỏi]** - AI trả lời với nguồn tin đáng tin cậy
        """,
        inline=False
    )
    
    embed.add_field(
        name="🇻🇳 Nguồn trong nước (9 nguồn)",
        value="CafeF, CafeBiz, Báo Đầu tư, VnEconomy, VnExpress KD, Thanh Niên, Nhân Dân",
        inline=True
    )
    
    embed.add_field(
        name="🌍 Nguồn quốc tế (8 nguồn)",
        value="Yahoo Finance, Reuters, Bloomberg, MarketWatch, Forbes, Financial Times, Business Insider, The Economist",
        inline=True
    )
    
    # Kiểm tra trạng thái AI services
    ai_status = ""
    if GROQ_AVAILABLE:
        ai_status += "🚀 **Groq AI** - Giải thích + Dịch thuật thông minh ✅\n"
    else:
        ai_status += "⚠️ **Groq AI** - Chưa cấu hình\n"
    
    if GOOGLE_SEARCH_AVAILABLE:
        ai_status += "🔍 **Google Search** - Tìm nguồn tin đáng tin cậy ✅\n"
    else:
        ai_status += "⚠️ **Google Search** - Chưa cấu hình\n"
    
    if TRAFILATURA_AVAILABLE:
        ai_status += "🚀 **Trafilatura** - Trích xuất nội dung 94.5% ✅\n"
    else:
        ai_status += "⚠️ **Trafilatura** - Chưa cài\n"
    
    if NEWSPAPER_AVAILABLE:
        ai_status += "📰 **Newspaper3k** - Fallback extraction ✅"
    else:
        ai_status += "⚠️ **Newspaper3k** - Chưa cài"
    
    embed.add_field(
        name="🚀 Công nghệ tích hợp",
        value=ai_status,
        inline=False
    )
    
    embed.add_field(
        name="💡 Ví dụ sử dụng AI",
        value="""
`!hoi lạm phát là gì` - Hỏi về lạm phát
`!hoi GDP nghĩa là gì` - Tìm hiểu về tổng sản phẩm quốc nội
`!hoi blockchain là gì` - Hỏi về công nghệ blockchain
`!hoi chứng khoán hoạt động như thế nào` - Hỏi về thị trường chứng khoán
        """,
        inline=False
    )
    
    embed.add_field(
        name="📋 Hướng dẫn sử dụng",
        value="""
1️⃣ **Xem tin**: Gõ **!all** để xem tin mới nhất
2️⃣ **Chi tiết**: Gõ **!chitiet [số]** - tin nước ngoài tự động dịch 🌐
3️⃣ **Hỏi AI**: Gõ **!hoi [câu hỏi]** để AI trả lời
4️⃣ **Phân trang**: Dùng **!all 2**, **!all 3** cho trang tiếp theo
        """,
        inline=False
    )
    
    if not GROQ_AVAILABLE or not GOOGLE_SEARCH_AVAILABLE:
        embed.add_field(
            name="⚙️ Cấu hình AI (cho admin)",
            value="""
Để kích hoạt AI, thêm vào Environment Variables:
• **GROQ_API_KEY** - Đăng ký miễn phí tại groq.com
• **GOOGLE_API_KEY** - Lấy từ Google Cloud Console
• **GOOGLE_CSE_ID** - Tạo Custom Search Engine
            """,
            inline=False
        )
    
    embed.set_footer(text="🤖 Bot với AI thông minh • 🌐 Tự động dịch tin nước ngoài • Múi giờ VN chính xác • Groq + Google Search")
    await ctx.send(embed=embed)

# Chạy bot với error handling tốt hơn
if __name__ == "__main__":
    try:
        print("🚀 Đang khởi động News Bot cải tiến...")
# Khởi động web server để keep alive
        keep_alive()
        print("🔑 Đang kiểm tra token từ Environment Variables...")
        
        if TOKEN:
            print("✅ Token đã được tải từ Environment Variables")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 Đã load {total_sources} nguồn RSS ĐÃ KIỂM TRA")
        print(f"🇻🇳 Trong nước: {len(RSS_FEEDS['domestic'])} nguồn")
        print(f"🌍 Quốc tế: {len(RSS_FEEDS['international'])} nguồn")
        print("🎯 Lĩnh vực: Kinh tế, Chứng khoán, Vĩ mô, Bất động sản")
        print("🕰️ Múi giờ: Đã sửa lỗi - Hiển thị chính xác giờ Việt Nam")
        
        if TRAFILATURA_AVAILABLE:
            print("🚀 Trafilatura: Sẵn sàng - Trích xuất nội dung 94.5% độ chính xác")
        else:
            print("⚠️ Trafilatura: Chưa cài đặt - Sẽ sử dụng phương pháp cũ")
            
        if NEWSPAPER_AVAILABLE:
            print("📰 Newspaper3k: Sẵn sàng - Fallback extraction")
        else:
            print("⚠️ Newspaper3k: Chưa cài đặt - Chỉ dùng Trafilatura")
        
        # Thông tin AI Services
        if GROQ_AVAILABLE:
            print("🤖 Groq AI: Sẵn sàng - AI giải thích + dịch thuật thông minh (1000 calls/ngày)")
        else:
            print("⚠️ Groq AI: Chưa cấu hình - Thiếu GROQ_API_KEY")
            
        if GOOGLE_SEARCH_AVAILABLE:
            print("🔍 Google Search: Sẵn sàng - Tìm nguồn tin đáng tin cậy (100 queries/ngày)")
        else:
            print("⚠️ Google Search: Chưa cấu hình - Thiếu GOOGLE_API_KEY hoặc GOOGLE_CSE_ID")
        
        print("✅ Bot sẵn sàng nhận lệnh!")
        print("💡 Lệnh AI: !hoi [câu hỏi] - AI trả lời với nguồn tin đáng tin cậy")
        print("🌐 Tính năng mới: !chitiet tự động dịch tin nước ngoài sang tiếng Việt")
        
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ Lỗi đăng nhập Discord!")
        print("🔧 Token có thể không hợp lệ hoặc đã bị reset")
        print("🔧 Kiểm tra DISCORD_TOKEN trong Environment Variables")
        
    except Exception as e:
        print(f"❌ Lỗi khi chạy bot: {e}")
        print("🔧 Kiểm tra kết nối internet và Environment Variables")
        
    input("Nhấn Enter để thoát...")
