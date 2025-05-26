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
import json
import aiohttp
from keep_alive import keep_alive
import google.generativeai as genai
from enum import Enum

# 🆕 THÊM CÁC THỬ VIỆN NÂNG CAO (OPTIONAL)
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

# 🆕 MULTI-AI ENGINE ARCHITECTURE
class AIProvider(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GROQ = "groq"  # Fallback

# 🤖 AI CONFIGURATION
AI_CONFIGS = {
    AIProvider.GEMINI: {
        'api_key_env': 'GEMINI_API_KEY',
        'model': 'gemini-2.0-flash-exp',
        'endpoint': 'google_ai_studio',
        'free_tier': 'unlimited',
        'strengths': ['search_integration', 'instruction_following', 'multimodal']
    },
    AIProvider.DEEPSEEK: {
        'api_key_env': 'DEEPSEEK_API_KEY',
        'model': 'deepseek-v3',
        'endpoint': 'https://api.deepseek.com/v1/chat/completions',
        'free_tier': 'generous',
        'strengths': ['reasoning', 'cost_effective', 'math']
    },
    AIProvider.CLAUDE: {
        'api_key_env': 'ANTHROPIC_API_KEY',
        'model': 'claude-3-5-sonnet-20241022',
        'endpoint': 'https://api.anthropic.com/v1/messages',
        'free_tier': 'limited',
        'strengths': ['safety', 'analysis', 'structured_output']
    },
    AIProvider.GROQ: {
        'api_key_env': 'GROQ_API_KEY',
        'model': 'llama-3.3-70b-versatile',
        'endpoint': 'https://api.groq.com/openai/v1/chat/completions',
        'free_tier': 'rate_limited',
        'strengths': ['speed', 'compatibility']
    }
}

# Cấu hình bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔒 BẢO MẬT: Environment Variables
TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

# AI API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

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

# 🆕 AI ENGINE MANAGER
class AIEngineManager:
    def __init__(self):
        self.primary_ai = None
        self.fallback_ais = []
        self.initialize_engines()
    
    def initialize_engines(self):
        """Khởi tạo các AI engines theo thứ tự ưu tiên"""
        available_engines = []
        
        # Gemini - Highest priority
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                available_engines.append(AIProvider.GEMINI)
                print("✅ Gemini AI initialized - PRIMARY ENGINE")
            except Exception as e:
                print(f"⚠️ Gemini initialization failed: {e}")
        
        # DeepSeek - Second priority  
        if DEEPSEEK_API_KEY:
            available_engines.append(AIProvider.DEEPSEEK)
            print("✅ DeepSeek AI available - FALLBACK 1")
            
        # Claude - Third priority
        if ANTHROPIC_API_KEY:
            available_engines.append(AIProvider.CLAUDE)
            print("✅ Claude AI available - FALLBACK 2")
            
        # Groq - Last fallback
        if GROQ_API_KEY:
            available_engines.append(AIProvider.GROQ)
            print("✅ Groq AI available - LAST FALLBACK")
        
        if available_engines:
            self.primary_ai = available_engines[0]
            self.fallback_ais = available_engines[1:]
            print(f"🚀 Primary AI: {self.primary_ai.value}")
            print(f"🛡️ Fallback AIs: {[ai.value for ai in self.fallback_ais]}")
        else:
            print("❌ No AI engines available!")
            self.primary_ai = None

    async def call_ai_with_fallback(self, prompt, context="", require_specific_data=True):
        """Gọi AI với fallback automatic"""
        
        # Thử primary AI trước
        if self.primary_ai:
            try:
                response = await self._call_specific_ai(self.primary_ai, prompt, context, require_specific_data)
                if self._validate_response(response, require_specific_data):
                    return response, self.primary_ai.value
            except Exception as e:
                print(f"⚠️ Primary AI {self.primary_ai.value} failed: {e}")
        
        # Thử fallback AIs
        for fallback_ai in self.fallback_ais:
            try:
                response = await self._call_specific_ai(fallback_ai, prompt, context, require_specific_data)
                if self._validate_response(response, require_specific_data):
                    print(f"✅ Fallback to {fallback_ai.value} successful")
                    return response, fallback_ai.value
            except Exception as e:
                print(f"⚠️ Fallback AI {fallback_ai.value} failed: {e}")
                continue
        
        # Nếu tất cả fail
        return "❌ Tất cả AI engines đều không khả dụng. Vui lòng thử lại sau.", "error"

    async def _call_specific_ai(self, ai_provider, prompt, context, require_specific_data):
        """Gọi AI engine cụ thể"""
        
        if ai_provider == AIProvider.GEMINI:
            return await self._call_gemini(prompt, context, require_specific_data)
        elif ai_provider == AIProvider.DEEPSEEK:
            return await self._call_deepseek(prompt, context, require_specific_data)
        elif ai_provider == AIProvider.CLAUDE:
            return await self._call_claude(prompt, context, require_specific_data)
        elif ai_provider == AIProvider.GROQ:
            return await self._call_groq(prompt, context, require_specific_data)
        
        raise Exception(f"Unknown AI provider: {ai_provider}")

    async def _call_gemini(self, prompt, context, require_specific_data):
        """🚀 Gemini 2.5 Flash - RECOMMENDED"""
        
        # Tạo prompt siêu nghiêm khắc cho Gemini
        system_prompt = """BẠN LÀ CHUYÊN GIA TÀI CHÍNH VIỆT NAM. QUY TẮC NGHIÊM NGẶT:

🔥 BẮT BUỘC (VI PHẠM = THẤT BẠI HOÀN TOÀN):
1. SỬ DỤNG SỐ LIỆU CỤ THỂ từ nội dung tin tức được cung cấp
2. NÊU THỜI GIAN CỤ THỂ (ngày/tháng/năm, giờ nếu có)  
3. TRÍCH DẪN CHÍNH XÁC từ nguồn tin
4. GIẢI THÍCH LÝ DO dựa trên sự kiện thực tế

❌ NGHIÊM CẤM:
- Nói chung chung: "thường", "có thể", "nói chung"
- Dùng dữ liệu cũ không có trong tin tức
- Đưa ra ý kiến cá nhân không dựa trên facts

✅ ĐỊNH DẠNG BẮT BUỘC:
[SỐ LIỆU HIỆN TẠI] - [THỜI GIAN] - [LÝ DO CỤ THỂ] - [NGUỒN]

🎯 NẾU KHÔNG CÓ ĐỦ THÔNG TIN: Trả lời "Không đủ dữ liệu cụ thể trong các nguồn tin hiện tại"""

        full_prompt = f"{system_prompt}\n\n📰 THÔNG TIN TỪ NGUỒN TIN:\n{context}\n\n❓ CÂU HỎI: {prompt}\n\n🔥 THỰC HIỆN NGAY - TUÂN THỦ NGHIÊM NGẶT:"
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Configure generation với settings strict
        generation_config = genai.types.GenerationConfig(
            temperature=0.1,  # Thấp để factual
            top_p=0.8,
            top_k=20,
            max_output_tokens=1000,
        )
        
        response = model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        return response.text.strip()

    async def _call_deepseek(self, prompt, context, require_specific_data):
        """💰 DeepSeek V3 - Cost Effective"""
        
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        system_message = """Bạn là chuyên gia tài chính. PHẢI tuân thủ nghiêm ngặt:
1. Sử dụng chính xác số liệu từ tin tức được cung cấp
2. Nêu thời gian cụ thể  
3. Giải thích lý do dựa trên sự kiện thực tế
4. KHÔNG được nói chung chung hoặc dùng dữ liệu cũ"""

        data = {
            'model': 'deepseek-v3',
            'messages': [
                {'role': 'system', 'content': system_message},
                {'role': 'user', 'content': f"THÔNG TIN TIN TỨC:\n{context}\n\nCÂU HỎI: {prompt}"}
            ],
            'temperature': 0.1,
            'max_tokens': 1000
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.deepseek.com/v1/chat/completions', 
                                  headers=headers, json=data) as response:
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()

    async def _call_claude(self, prompt, context, require_specific_data):
        """🧠 Claude 3.5 Sonnet - Reliable"""
        
        headers = {
            'x-api-key': ANTHROPIC_API_KEY,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': 'claude-3-5-sonnet-20241022',
            'max_tokens': 1000,
            'temperature': 0.1,
            'messages': [
                {
                    'role': 'user', 
                    'content': f"""Bạn là chuyên gia tài chính. QUY TẮC BẮT BUỘC:
- Sử dụng số liệu cụ thể từ tin tức
- Nêu thời gian chính xác  
- Giải thích lý do dựa trên facts
- Không nói chung chung

THÔNG TIN TIN TỨC:
{context}

CÂU HỎI: {prompt}"""
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.anthropic.com/v1/messages',
                                  headers=headers, json=data) as response:
                result = await response.json()
                return result['content'][0]['text'].strip()

    async def _call_groq(self, prompt, context, require_specific_data):
        """⚡ Groq - Fast Fallback"""
        
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'llama-3.3-70b-versatile',
            'messages': [
                {'role': 'system', 'content': 'Bạn là chuyên gia tài chính. Phải sử dụng số liệu cụ thể từ tin tức và nêu thời gian chính xác. Không được nói chung chung.'},
                {'role': 'user', 'content': f"THÔNG TIN TIN TỨC:\n{context}\n\nCÂU HỎI: {prompt}"}
            ],
            'temperature': 0.1,
            'max_tokens': 1000
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post('https://api.groq.com/openai/v1/chat/completions',
                                  headers=headers, json=data) as response:
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()

    def _validate_response(self, response, require_specific_data):
        """Validate AI response quality"""
        if not require_specific_data:
            return len(response.strip()) > 50
        
        # Check for specific data requirements
        has_numbers = re.search(r'\d+[.,]?\d*\s*%|\d+[.,]?\d*\s*(triệu|tỷ|USD|VND|đồng)', response)
        has_time = re.search(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}|\d{1,2}\s*(tháng|thg)\s*\d{1,2}', response)
        
        # Check for forbidden generic terms
        forbidden_terms = ['thường', 'có thể', 'nói chung', 'thông thường', 'thịnh nộp']
        has_forbidden = any(term in response.lower() for term in forbidden_terms)
        
        if require_specific_data:
            return has_numbers and has_time and not has_forbidden
        
        return not has_forbidden and len(response.strip()) > 100

# Initialize AI Manager
ai_manager = AIEngineManager()

# 🔍 IMPROVED GOOGLE SEARCH với Generic Query
async def search_reliable_sources_improved(query, max_results=5):
    """🆕 Tìm kiếm thông minh với Generic Query + Time Context"""
    
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("⚠️ Google Search API not configured")
        return []
    
    try:
        # Thêm time context cho query
        current_date = datetime.now(VN_TIMEZONE).strftime("%Y")
        current_month = datetime.now(VN_TIMEZONE).strftime("%m/%Y")
        
        # Generic query với time context - KHÔNG CẦN specific keywords
        enhanced_query = f'{query} {current_date} mới nhất tin tức site:cafef.vn OR site:vneconomy.vn OR site:vnexpress.net OR site:tuoitre.vn OR site:thanhnien.vn OR site:baodautu.vn OR site:dantri.com.vn OR site:investing.com OR site:bloomberg.com OR site:reuters.com'
        
        print(f"🔍 Enhanced search query: {enhanced_query}")
        
        from googleapiclient.discovery import build
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        result = service.cse().list(
            q=enhanced_query,
            cx=GOOGLE_CSE_ID,
            num=max_results,
            lr='lang_vi|lang_en',
            safe='active',
            sort='date'  # Sắp xếp theo ngày mới nhất
        ).execute()
        
        sources = []
        if 'items' in result:
            for item in result['items']:
                source = {
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source_name': extract_source_name(item.get('link', '')),
                    'publishedDate': item.get('pagemap', {}).get('metatags', [{}])[0].get('article:published_time', '')
                }
                sources.append(source)
        
        print(f"✅ Found {len(sources)} reliable sources")
        return sources
        
    except Exception as e:
        print(f"❌ Google Search error: {e}")
        return []

def extract_source_name(url):
    """Extract readable source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'vneconomy.vn': 'VnEconomy', 
        'vnexpress.net': 'VnExpress',
        'tuoitre.vn': 'Tuổi Trẻ',
        'thanhnien.vn': 'Thanh Niên',
        'baodautu.vn': 'Báo Đầu tư',
        'dantri.com.vn': 'Dân trí',
        'investing.com': 'Investing.com',
        'bloomberg.com': 'Bloomberg',
        'reuters.com': 'Reuters',
        'bbc.com': 'BBC'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace('www.', '')
        return domain.title()
    except:
        return 'Unknown Source'

# 🆕 CONTENT EXTRACTION FUNCTIONS (FROM ORIGINAL CODE)
async def fetch_content_with_trafilatura(url):
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
        
        return None
        
    except Exception as e:
        print(f"⚠️ Lỗi Trafilatura cho {url}: {e}")
        return None

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

# 🆕 IMPROVED CONTENT EXTRACTION
async def get_full_content_from_sources_improved(sources):
    """Lấy nội dung đầy đủ với fallback strategy"""
    
    full_contexts = []
    
    for i, source in enumerate(sources[:3], 1):  # Top 3 sources
        try:
            print(f"📄 Extracting content from source {i}: {source['source_name']}")
            
            # Try multiple extraction methods
            content = await fetch_full_content_improved(source['link'])
            
            if content and len(content) > 200:
                # Lấy 800 ký tự đầu - chứa info quan trọng nhất
                summary_content = content[:800]
                
                full_contexts.append(f"""
📰 NGUỒN {i}: {source['source_name']}
📅 Thời gian: {source.get('publishedDate', 'Không xác định')}
🔗 Link: {source['link']}
📄 Nội dung: {summary_content}
""")
            else:
                # Fallback to snippet
                full_contexts.append(f"""
📰 NGUỒN {i}: {source['source_name']} 
📄 Tóm tắt: {source['snippet']}
🔗 Link: {source['link']}
""")
                
        except Exception as e:
            print(f"⚠️ Content extraction failed for {source['source_name']}: {e}")
            # Fallback to snippet
            full_contexts.append(f"""
📰 NGUỒN {i}: {source['source_name']}
📄 Tóm tắt: {source['snippet']}
🔗 Link: {source['link']}
""")
    
    return "\n".join(full_contexts)

# RSS COLLECTION FUNCTIONS (FROM ORIGINAL CODE)
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

# BOT EVENT HANDLERS
@bot.event
async def on_ready():
    print(f'✅ {bot.user} đã online!')
    print(f'📊 Kết nối với {len(bot.guilds)} server(s)')
    
    # AI Engine status
    if ai_manager.primary_ai:
        print(f'🤖 Primary AI: {ai_manager.primary_ai.value.upper()}')
        print(f'🛡️ Fallback AIs: {[ai.value.upper() for ai in ai_manager.fallback_ais]}')
    else:
        print('⚠️ No AI engines configured')
    
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
    
    print('🎯 Gõ !menu để xem hướng dẫn')
    
    # Set bot status
    status_text = f"Multi-AI Engine • {ai_manager.primary_ai.value.upper() if ai_manager.primary_ai else 'No AI'} • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

# DISCORD COMMANDS (FROM ORIGINAL CODE)
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
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Multi-AI Engine • 📰 Từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn",
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
        embed.set_footer(text=f"🚀 Multi-AI Engine • Trang {page}/{total_pages} • !all {page+1} tiếp • !chitiet [số] xem chi tiết")
        
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
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Multi-AI Engine • Từ {len(RSS_FEEDS['domestic'])} nguồn chuyên ngành",
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
        embed.set_footer(text=f"🚀 Multi-AI Engine • Trang {page}/{total_pages} • !in {page+1} tiếp • !chitiet [số] xem chi tiết")
        
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
            description=f"🕰️ Giờ Việt Nam chính xác • 🚀 Multi-AI Engine • Từ {len(RSS_FEEDS['international'])} nguồn hàng đầu",
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
        embed.set_footer(text=f"🚀 Multi-AI Engine • Trang {page}/{total_pages} • !out {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """🆕 XEM CHI TIẾT BẰNG MULTI-AI ENGINE + TỰ ĐỘNG DỊCH"""
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
        loading_msg = await ctx.send("🚀 Đang trích xuất nội dung với Multi-AI Engine...")
        
        # Sử dụng function cải tiến
        full_content = await fetch_full_content_improved(news['link'])
        
        # 🌐 TÍNH NĂNG MỚI: Tự động dịch nếu là tin nước ngoài
        international_sources = {
            'yahoo_finance', 'reuters_business', 'bloomberg_markets', 'marketwatch_latest',
            'forbes_money', 'financial_times', 'business_insider', 'the_economist'
        }
        
        translated_content = full_content
        is_translated = False
        
        if news['source'] in international_sources and ai_manager.primary_ai:
            try:
                # Detect English content
                english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has']
                content_lower = full_content.lower()
                english_word_count = sum(1 for word in english_indicators if word in content_lower)
                
                if english_word_count >= 3:
                    print(f"🌐 Đang dịch nội dung từ {news['source']} sang tiếng Việt...")
                    
                    translation_prompt = f"""Dịch đoạn văn tiếng Anh sau sang tiếng Việt chính xác, tự nhiên:

{full_content}

Yêu cầu:
- Giữ nguyên số liệu, tỷ lệ phần trăm
- Dịch tự nhiên, không máy móc
- Sử dụng thuật ngữ kinh tế tiếng Việt chuẩn

Bản dịch:"""

                    translated_content, used_engine = await ai_manager.call_ai_with_fallback(
                        prompt=translation_prompt,
                        context="",
                        require_specific_data=False
                    )
                    
                    if translated_content and "❌" not in translated_content:
                        is_translated = True
                        print("✅ Dịch thuật thành công")
                    else:
                        translated_content = full_content
                        
            except Exception as e:
                print(f"⚠️ Lỗi dịch thuật: {e}")
                translated_content = full_content
        
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
                    value="📝 Nội dung gốc bằng tiếng Anh đã được dịch sang tiếng Việt bằng Multi-AI Engine\n💡 Để xem bản gốc, vui lòng truy cập link bài viết",
                    inline=False
                )
            
            embed2.add_field(
                name="🔗 Đọc bài viết đầy đủ",
                value=f"[Nhấn để đọc toàn bộ bài viết gốc]({news['link']})",
                inline=False
            )
            
            # Thông tin công nghệ sử dụng
            tech_info = "🚀 Multi-AI Engine"
            if TRAFILATURA_AVAILABLE:
                tech_info += " + Trafilatura"
            if NEWSPAPER_AVAILABLE:
                tech_info += " + Newspaper3k"
            if is_translated:
                tech_info += " + AI Translation"
            
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
                value="📝 Bài viết gốc bằng tiếng Anh đã được dịch sang tiếng Việt bằng Multi-AI Engine",
                inline=False
            )
        
        embed.add_field(
            name="🔗 Đọc bài viết đầy đủ",
            value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
            inline=False
        )
        
        # Thông tin công nghệ sử dụng
        tech_info = "🚀 Multi-AI Engine"
        if TRAFILATURA_AVAILABLE:
            tech_info += " + Trafilatura"
        if NEWSPAPER_AVAILABLE:
            tech_info += " + Newspaper3k"
        if is_translated:
            tech_info += " + AI Translation"
        
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

# 🆕 MAIN AI COMMAND - Completely Rewritten
@bot.command(name='hoi')
async def ask_economic_question_improved(ctx, *, question):
    """🆕 AI Q&A với Multi-Engine Support và Validation"""
    
    try:
        if not ai_manager.primary_ai:
            embed = discord.Embed(
                title="⚠️ AI Services không khả dụng",
                description="Chưa cấu hình AI API keys. Cần ít nhất một trong: GEMINI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Thông báo đang xử lý
        processing_msg = await ctx.send("🔍 Đang tìm kiếm thông tin từ các nguồn tin đáng tin cậy...")
        
        # 🔍 Step 1: Generic Google Search (No specific keywords needed)
        sources = await search_reliable_sources_improved(question, max_results=5)
        
        if not sources:
            await processing_msg.edit(content="⚠️ Không tìm thấy nguồn tin. Đang sử dụng kiến thức tổng quát...")
        
        # 📄 Step 2: Extract full content 
        await processing_msg.edit(content="📄 Đang phân tích nội dung từ các nguồn tin...")
        full_context = await get_full_content_from_sources_improved(sources)
        
        # 🤖 Step 3: AI Analysis với Multi-Engine Fallback
        await processing_msg.edit(content="🤖 Multi-AI Engine đang phân tích và tạo câu trả lời...")
        
        # Detect if question requires specific financial data
        requires_specific_data = any(keyword in question.lower() for keyword in 
                                   ['giá', 'bao nhiêu', 'tăng giảm', 'thay đổi', 'hiện tại', 'hôm nay'])
        
        ai_response, used_engine = await ai_manager.call_ai_with_fallback(
            prompt=question,
            context=full_context,
            require_specific_data=requires_specific_data
        )
        
        # Xóa thông báo processing
        await processing_msg.delete()
        
        # 📊 Create beautiful embed response
        embed = discord.Embed(
            title=f"🤖 AI Trả lời: {question.title()[:100]}...",
            description=ai_response,
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        # Add AI engine info
        engine_emoji = {
            'gemini': '💎',
            'deepseek': '💰', 
            'claude': '🧠',
            'groq': '⚡'
        }
        
        embed.add_field(
            name="🤖 AI Engine sử dụng",
            value=f"{engine_emoji.get(used_engine, '🤖')} {used_engine.upper()}",
            inline=True
        )
        
        if sources:
            embed.add_field(
                name="📊 Số nguồn tin",
                value=f"📰 {len(sources)} nguồn đáng tin cậy",
                inline=True
            )
        
        # Add source references
        if sources:
            sources_text = ""
            for i, source in enumerate(sources[:3], 1):
                sources_text += f"{i}. **{source['source_name']}**: [{source['title'][:50]}...]({source['link']})\n"
            
            embed.add_field(
                name="📰 Nguồn tin tham khảo",
                value=sources_text,
                inline=False
            )
        
        # Footer
        embed.set_footer(
            text=f"🚀 Multi-AI Engine • Dữ liệu thời gian thực • !menu để xem thêm lệnh",
            icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )
        
        await ctx.send(embed=embed)
        
        # Log cho debug
        print(f"✅ Question answered: '{question}' using {used_engine}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi trong quá trình xử lý: {str(e)}")
        print(f"❌ Error in !hoi command: {e}")

# 📊 Updated Menu Command
@bot.command(name='menu')
async def help_command_improved(ctx):
    """Menu với Multi-AI Engine info"""
    
    embed = discord.Embed(
        title="🤖🚀 Menu News Bot - Multi-AI Engine",
        description="Bot tin tức kinh tế với AI thông minh đa engine",
        color=0xff9900
    )
    
    # AI Engine status
    ai_status = ""
    if ai_manager.primary_ai:
        engine_name = ai_manager.primary_ai.value.upper()
        ai_status += f"🚀 **Primary**: {engine_name} ✅\n"
        
        for fallback in ai_manager.fallback_ais:
            ai_status += f"🛡️ **Fallback**: {fallback.value.upper()} ✅\n"
    else:
        ai_status = "❌ Chưa cấu hình AI engines"
    
    embed.add_field(
        name="🤖 AI Engines hoạt động",
        value=ai_status,
        inline=False
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="""
**!all [trang]** - Tin từ tất cả nguồn (12 tin/trang)
**!in [trang]** - Tin trong nước (12 tin/trang)  
**!out [trang]** - Tin quốc tế (12 tin/trang)
**!chitiet [số]** - Xem nội dung chi tiết + 🌐 Tự động dịch
        """,
        inline=True
    )
    
    embed.add_field(
        name="🤖 Lệnh AI thông minh",
        value="""
**!hoi [câu hỏi]** - AI trả lời với Multi-Engine
*Ví dụ: !hoi giá vàng hôm nay như thế nào*
        """,
        inline=True
    )
    
    embed.add_field(
        name="🇻🇳 Nguồn trong nước (13 nguồn)",
        value="CafeF (5 chuyên mục), CafeBiz, Báo Đầu tư, VnEconomy (2), VnExpress (2), Thanh Niên (2), Nhân Dân",
        inline=True
    )
    
    embed.add_field(
        name="🌍 Nguồn quốc tế (8 nguồn)",
        value="Yahoo Finance, Reuters, Bloomberg, MarketWatch, Forbes, Financial Times, Business Insider, The Economist",
        inline=True
    )
    
    embed.add_field(
        name="🎯 Tính năng mới",
        value="""
✅ **Multi-AI Engine** - Tự động fallback khi AI fail
✅ **Generic Search** - Không cần config từng keyword  
✅ **Real-time Data** - Dữ liệu cập nhật liên tục
✅ **Response Validation** - Đảm bảo chất lượng
✅ **Full Content Extract** - Phân tích sâu
✅ **Auto Translation** - Tự động dịch tin nước ngoài
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 Ví dụ sử dụng AI",
        value="""
`!hoi giá vàng hôm nay như thế nào` - Hỏi về giá vàng hiện tại
`!hoi tại sao tỷ giá USD tăng` - Phân tích tỷ giá
`!hoi giá nhà đất TPHCM có đắt không` - Hỏi về bất động sản
`!hoi chứng khoán VN-Index hôm nay` - Thông tin chứng khoán
        """,
        inline=False
    )
    
    if not ai_manager.primary_ai:
        embed.add_field(
            name="⚙️ Cấu hình AI (để bật thêm tính năng)",
            value="""
Bot đã hoạt động đầy đủ ở chế độ cơ bản.
Để kích hoạt AI features, thêm vào Environment Variables:
• **GEMINI_API_KEY** - Miễn phí tại aistudio.google.com (KHUYẾN NGHỊ)
• **DEEPSEEK_API_KEY** - Siêu rẻ tại platform.deepseek.com
• **ANTHROPIC_API_KEY** - Claude tại console.anthropic.com  
• **GROQ_API_KEY** - Nhanh nhất tại console.groq.com
            """,
            inline=False
        )
    
    embed.set_footer(text="🚀 Multi-AI Engine • Generic Search • Real-time Analysis • Auto Translation")
    await ctx.send(embed=embed)

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()  # Bật web server để keep alive
        print("🚀 Starting Multi-AI Discord News Bot...")
        print("🔑 Đang kiểm tra token từ Environment Variables...")
        
        if TOKEN:
            print("✅ Token đã được tải từ Environment Variables")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 Đã load {total_sources} nguồn RSS ĐÃ KIỂM TRA")
        print(f"🇻🇳 Trong nước: {len(RSS_FEEDS['domestic'])} nguồn")
        print(f"🌍 Quốc tế: {len(RSS_FEEDS['international'])} nguồn")
        print("🎯 Lĩnh vực: Kinh tế, Chứng khoán, Vĩ mô, Bất động sản")
        print("🕰️ Múi giờ: Đã sửa lỗi - Hiển thị chính xác giờ Việt Nam")
        
        print("✅ Bot ready with Multi-AI Engine support!")
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        input("Press Enter to exit...")
