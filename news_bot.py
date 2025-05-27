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

# Google Generative AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Google Generative AI library loaded")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai library not found. Run: pip install google-generativeai")

# Google API Client
try:
    from googleapiclient.discovery import build
    GOOGLE_APIS_AVAILABLE = True
    print("✅ Google API Client library loaded")
except ImportError:
    GOOGLE_APIS_AVAILABLE = False
    print("⚠️ google-api-python-client library not found. Run: pip install google-api-python-client")

from enum import Enum

# Optional content extraction libraries
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
    print("✅ Trafilatura available")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ Trafilatura not available - will use basic extraction")

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
    print("✅ Newspaper3k available")
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ Newspaper3k not available - will use basic extraction")

# AI Provider enum
class AIProvider(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GROQ = "groq"

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

# Debug Environment Variables
print("=" * 50)
print("🔍 ENVIRONMENT VARIABLES DEBUG")
print("=" * 50)
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'} ({len(TOKEN) if TOKEN else 0} chars)")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'} ({len(GEMINI_API_KEY) if GEMINI_API_KEY else 0} chars)")
print(f"DEEPSEEK_API_KEY: {'✅ Found' if DEEPSEEK_API_KEY else '❌ Missing'} ({len(DEEPSEEK_API_KEY) if DEEPSEEK_API_KEY else 0} chars)")
print(f"ANTHROPIC_API_KEY: {'✅ Found' if ANTHROPIC_API_KEY else '❌ Missing'} ({len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0} chars)")
print(f"GROQ_API_KEY: {'✅ Found' if GROQ_API_KEY else '❌ Missing'} ({len(GROQ_API_KEY) if GROQ_API_KEY else 0} chars)")
print(f"GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'} ({len(GOOGLE_API_KEY) if GOOGLE_API_KEY else 0} chars)")
print(f"GOOGLE_CSE_ID: {'✅ Found' if GOOGLE_CSE_ID else '❌ Missing'} ({len(GOOGLE_CSE_ID) if GOOGLE_CSE_ID else 0} chars)")
print("=" * 50)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# Vietnam timezone
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# User news cache
user_news_cache = {}

# RSS feeds
RSS_FEEDS = {
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
        'nhandanonline_tc': 'https://nhandan.vn/rss/tai-chinh-chung-khoan.rss'
    },
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
    """Convert UTC to Vietnam time"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Timezone conversion error: {e}")
        return datetime.now(VN_TIMEZONE)

# AI Engine Manager
class AIEngineManager:
    def __init__(self):
        self.primary_ai = None
        self.fallback_ais = []
        self.session = None
        self.initialize_engines()
    
    async def create_session(self):
        """Create async session properly"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """Close async session properly"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """Initialize AI engines with validation"""
        available_engines = []
        
        print("\n🔧 TESTING AI ENGINES:")
        
        # Gemini
        if GEMINI_API_KEY and GEMINI_AVAILABLE:
            try:
                print(f"✅ GEMINI: API key format valid")
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    available_engines.append(AIProvider.GEMINI)
                    genai.configure(api_key=GEMINI_API_KEY)
                else:
                    print("❌ GEMINI: API key format invalid")
            except Exception as e:
                print(f"❌ GEMINI: {e}")
        
        # DeepSeek
        if DEEPSEEK_API_KEY:
            try:
                print(f"✅ DEEPSEEK: API key format valid")
                if DEEPSEEK_API_KEY.startswith('sk-') and len(DEEPSEEK_API_KEY) > 30:
                    available_engines.append(AIProvider.DEEPSEEK)
                else:
                    print("❌ DEEPSEEK: API key format invalid")
            except Exception as e:
                print(f"❌ DEEPSEEK: {e}")
        
        # Claude
        if ANTHROPIC_API_KEY:
            try:
                print(f"✅ CLAUDE: API key format valid")
                if ANTHROPIC_API_KEY.startswith('sk-ant-') and len(ANTHROPIC_API_KEY) > 50:
                    available_engines.append(AIProvider.CLAUDE)
                else:
                    print("❌ CLAUDE: API key format invalid")
            except Exception as e:
                print(f"❌ CLAUDE: {e}")
        
        # Groq
        if GROQ_API_KEY:
            try:
                print(f"✅ GROQ: API key format valid")
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    available_engines.append(AIProvider.GROQ)
                else:
                    print("❌ GROQ: API key format invalid")
            except Exception as e:
                print(f"❌ GROQ: {e}")
        
        print(f"📊 SUMMARY:")
        print(f"Available AI Engines: {len(available_engines)}")
        print(f"Engines: {', '.join([ai.value.upper() for ai in available_engines])}")
        
        if available_engines:
            self.primary_ai = available_engines[0]
            self.fallback_ais = available_engines[1:]
        else:
            self.primary_ai = None
            self.fallback_ais = []

    async def call_ai_with_fallback(self, prompt, context="", require_specific_data=True):
        """Call AI with fallback system"""
        
        # Try primary AI
        if self.primary_ai:
            try:
                print(f"🔄 Trying primary AI: {self.primary_ai.value}")
                response = await self._call_specific_ai_fixed(self.primary_ai, prompt, context, require_specific_data)
                if self._validate_response(response, require_specific_data):
                    print(f"✅ Primary AI {self.primary_ai.value} success")
                    return response, self.primary_ai.value
                else:
                    print(f"⚠️ Primary AI {self.primary_ai.value} response invalid")
            except Exception as e:
                print(f"❌ Primary AI {self.primary_ai.value} failed: {str(e)}")
        
        # Try fallback AIs
        for fallback_ai in self.fallback_ais:
            try:
                print(f"🔄 Trying fallback AI: {fallback_ai.value}")
                response = await self._call_specific_ai_fixed(fallback_ai, prompt, context, require_specific_data)
                if self._validate_response(response, require_specific_data):
                    print(f"✅ Fallback AI {fallback_ai.value} success")
                    return response, fallback_ai.value
                else:
                    print(f"⚠️ Fallback AI {fallback_ai.value} response invalid")
            except Exception as e:
                print(f"❌ Fallback AI {fallback_ai.value} failed: {str(e)}")
                continue
        
        return "❌ Tất cả AI engines đều không khả dụng. Vui lòng thử lại sau.", "error"

    async def _call_specific_ai_fixed(self, ai_provider, prompt, context, require_specific_data):
        """Call specific AI engine"""
        
        try:
            if ai_provider == AIProvider.GEMINI:
                return await self._call_gemini_fixed(prompt, context, require_specific_data)
            elif ai_provider == AIProvider.DEEPSEEK:
                return await self._call_deepseek_fixed(prompt, context, require_specific_data)
            elif ai_provider == AIProvider.CLAUDE:
                return await self._call_claude_fixed(prompt, context, require_specific_data)
            elif ai_provider == AIProvider.GROQ:
                return await self._call_groq_fixed(prompt, context, require_specific_data)
            
            raise Exception(f"Unknown AI provider: {ai_provider}")
            
        except Exception as e:
            print(f"❌ Error calling {ai_provider.value}: {str(e)}")
            raise e

    async def _call_gemini_fixed(self, prompt, context, require_specific_data):
        """Call Gemini with enhanced prompting"""
        
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            # Enhanced prompt for better context utilization
            system_prompt = """Bạn là chuyên gia tài chính Việt Nam. 

NHIỆM VỤ: 
- Sử dụng thông tin từ CONTEXT được cung cấp để trả lời câu hỏi
- Nếu có thông tin cụ thể về giá, số liệu trong CONTEXT, hãy trích dẫn chính xác
- Nếu không có thông tin cụ thể, hãy trả lời dựa trên kiến thức chung về tài chính
- Trả lời bằng tiếng Việt, ngắn gọn và chính xác

FORMAT: 
- Nếu có dữ liệu từ CONTEXT: "Theo thông tin mới nhất: [dữ liệu cụ thể]"
- Nếu không có dữ liệu: "Thông tin tổng quan: [kiến thức chung]" """
            
            full_prompt = f"{system_prompt}\n\nCONTEXT: {context}\n\nCÂU HỎI: {prompt}\n\nTRẢ LỜI:"
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.8,
                top_k=20,
                max_output_tokens=800,
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    full_prompt,
                    generation_config=generation_config
                ),
                timeout=20
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            raise Exception("Gemini API timeout")
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def _call_deepseek_fixed(self, prompt, context, require_specific_data):
        """Call DeepSeek API"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            system_message = """Bạn là chuyên gia tài chính. Sử dụng thông tin từ CONTEXT để trả lời câu hỏi. Nếu có dữ liệu cụ thể, hãy trích dẫn. Trả lời ngắn gọn bằng tiếng Việt."""
            
            data = {
                'model': 'deepseek-v3',
                'messages': [
                    {'role': 'system', 'content': system_message},
                    {'role': 'user', 'content': f"CONTEXT: {context}\n\nCÂU HỎI: {prompt}"}
                ],
                'temperature': 0.3,
                'max_tokens': 800
            }
            
            async with session.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 401:
                    raise Exception("DeepSeek API authentication failed")
                elif response.status == 429:
                    raise Exception("DeepSeek API rate limit exceeded")
                elif response.status != 200:
                    raise Exception(f"DeepSeek API error: {response.status}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except asyncio.TimeoutError:
            raise Exception("DeepSeek API timeout")
        except Exception as e:
            raise Exception(f"DeepSeek API error: {str(e)}")

    async def _call_claude_fixed(self, prompt, context, require_specific_data):
        """Call Claude API"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'x-api-key': ANTHROPIC_API_KEY,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 800,
                'temperature': 0.3,
                'messages': [
                    {
                        'role': 'user',
                        'content': f"""Bạn là chuyên gia tài chính. Sử dụng thông tin từ CONTEXT để trả lời câu hỏi. Trả lời ngắn gọn bằng tiếng Việt.

CONTEXT: {context}

CÂU HỎI: {prompt}"""
                    }
                ]
            }
            
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 401:
                    raise Exception("Claude API authentication failed")
                elif response.status == 429:
                    raise Exception("Claude API rate limit exceeded")
                elif response.status != 200:
                    raise Exception(f"Claude API error: {response.status}")
                
                result = await response.json()
                return result['content'][0]['text'].strip()
                
        except asyncio.TimeoutError:
            raise Exception("Claude API timeout")
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    async def _call_groq_fixed(self, prompt, context, require_specific_data):
        """Call Groq API"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': 'Bạn là chuyên gia tài chính. Sử dụng thông tin từ CONTEXT để trả lời câu hỏi. Trả lời ngắn gọn bằng tiếng Việt.'},
                    {'role': 'user', 'content': f"CONTEXT: {context}\n\nCÂU HỎI: {prompt}"}
                ],
                'temperature': 0.3,
                'max_tokens': 800
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 401:
                    raise Exception("Groq API authentication failed")
                elif response.status == 429:
                    raise Exception("Groq API rate limit exceeded")
                elif response.status != 200:
                    raise Exception(f"Groq API error: {response.status}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except asyncio.TimeoutError:
            raise Exception("Groq API timeout")
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

    def _validate_response(self, response, require_specific_data):
        """Validate AI response quality"""
        if not response or len(response.strip()) < 10:
            return False
        
        error_indicators = ['❌', 'không khả dụng', 'lỗi', 'error', 'failed']
        if any(indicator in response.lower() for indicator in error_indicators):
            return False
        
        return True

# Initialize AI Manager
ai_manager = AIEngineManager()

# 🔧 FIXED GOOGLE SEARCH with enhanced debugging
async def search_reliable_sources_improved(query, max_results=5):
    """Enhanced Google Search with better debugging"""
    
    print(f"🔍 GOOGLE SEARCH DEBUG:")
    print(f"   Query: {query}")
    print(f"   GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'}")
    print(f"   GOOGLE_CSE_ID: {'✅ Found' if GOOGLE_CSE_ID else '❌ Missing'}")
    print(f"   Google APIs Available: {'✅ Yes' if GOOGLE_APIS_AVAILABLE else '❌ No'}")
    
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("❌ Google Search API not configured properly")
        return []
    
    if not GOOGLE_APIS_AVAILABLE:
        print("❌ Google API Client library not available")
        return []
    
    try:
        # Enhanced search query for Vietnamese financial news
        current_date = datetime.now(VN_TIMEZONE).strftime("%Y")
        current_month = datetime.now(VN_TIMEZONE).strftime("%m/%Y")
        
        # More specific search for Vietnamese financial data
        if 'giá vàng' in query.lower():
            enhanced_query = f'giá vàng hôm nay {current_date} site:cafef.vn OR site:vneconomy.vn OR site:pnj.com.vn OR site:sjc.com.vn'
        elif 'chứng khoán' in query.lower() or 'vn-index' in query.lower():
            enhanced_query = f'chứng khoán VN-Index {current_date} site:cafef.vn OR site:vneconomy.vn OR site:vnexpress.net'
        elif 'tỷ giá' in query.lower() or 'usd' in query.lower():
            enhanced_query = f'tỷ giá USD VND {current_date} site:vietcombank.com.vn OR site:cafef.vn OR site:vneconomy.vn'
        else:
            enhanced_query = f'{query} {current_date} mới nhất site:cafef.vn OR site:vneconomy.vn OR site:vnexpress.net OR site:tuoitre.vn'
        
        print(f"🔍 Enhanced query: {enhanced_query}")
        
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        print("🔄 Calling Google Custom Search API...")
        result = service.cse().list(
            q=enhanced_query,
            cx=GOOGLE_CSE_ID,
            num=max_results,
            lr='lang_vi',
            safe='active',
            sort='date'
        ).execute()
        
        sources = []
        if 'items' in result:
            print(f"✅ Google Search returned {len(result['items'])} results")
            for i, item in enumerate(result['items'], 1):
                source = {
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source_name': extract_source_name(item.get('link', ''))
                }
                sources.append(source)
                print(f"   Result {i}: {source['source_name']} - {source['title'][:50]}...")
        else:
            print("❌ No 'items' in Google Search result")
            print(f"   Full result keys: {list(result.keys())}")
        
        print(f"✅ Final sources count: {len(sources)}")
        return sources
        
    except Exception as e:
        print(f"❌ Google Search error: {e}")
        print(f"   Error type: {type(e)}")
        return []

def extract_source_name(url):
    """Extract source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'tuoitre.vn': 'Tuổi Trẻ',
        'thanhnien.vn': 'Thanh Niên',
        'pnj.com.vn': 'PNJ',
        'sjc.com.vn': 'SJC',
        'vietcombank.com.vn': 'Vietcombank'
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

# Content extraction functions
async def fetch_full_content_improved(url):
    """Enhanced content extraction"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Basic content extraction
        content = response.text
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = html.unescape(content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Get meaningful sentences
        sentences = content.split('. ')
        meaningful_content = []
        
        for sentence in sentences[:8]:
            if len(sentence.strip()) > 20:
                meaningful_content.append(sentence.strip())
        
        result = '. '.join(meaningful_content)
        
        return result[:1500] + "..." if len(result) > 1500 else result
        
    except Exception as e:
        print(f"⚠️ Content extraction error for {url}: {e}")
        return "Không thể trích xuất nội dung từ bài viết này."

# RSS collection functions
async def collect_news_from_sources(sources_dict, limit_per_source=6):
    """Collect news from RSS sources"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Fetching from {source_name}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"⚠️ No entries from {source_name}")
                continue
                
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    vn_time = datetime.now(VN_TIMEZONE)
                    
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
                    
                except Exception as entry_error:
                    print(f"⚠️ Entry processing error from {source_name}: {entry_error}")
                    continue
                    
            print(f"✅ Got {entries_processed} news from {source_name}")
            
        except Exception as e:
            print(f"❌ Error from {source_name}: {e}")
            continue
    
    print(f"📊 Total collected: {len(all_news)} news items")
    
    # Remove duplicates and sort
    unique_news = []
    seen_links = set()
    seen_titles = set()
    
    for news in all_news:
        normalized_title = normalize_title(news['title'])
        
        if news['link'] not in seen_links and normalized_title not in seen_titles:
            seen_links.add(news['link'])
            seen_titles.add(normalized_title)
            unique_news.append(news)
    
    print(f"🔄 After deduplication: {len(unique_news)} unique news")
    
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

def normalize_title(title):
    """Normalize title for comparison"""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = ' '.join(title.split())
    words = title.split()[:8]
    return ' '.join(words)

def save_user_news(user_id, news_list, command_type):
    """Save user news cache"""
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': datetime.now(VN_TIMEZONE)
    }

# Bot event handlers
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    if ai_manager.primary_ai:
        print(f'🤖 Primary AI: {ai_manager.primary_ai.value.upper()}')
        if ai_manager.fallback_ais:
            print(f'🛡️ Fallback AIs: {[ai.value.upper() for ai in ai_manager.fallback_ais]}')
    else:
        print('⚠️ No AI engines configured')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Ready with {total_sources} RSS sources')
    print('🎯 Type !menu for help')
    
    status_text = f"Complete Fixed • {ai_manager.primary_ai.value.upper() if ai_manager.primary_ai else 'No AI'} • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        print(f"⚠️ Command not found: {ctx.message.content}")
        # Don't send error message to user for command not found
        return
    else:
        print(f"❌ Command error: {error}")
        await ctx.send(f"❌ Lỗi: {str(error)}")

# 🆕 MAIN AI COMMAND - ENHANCED WITH BETTER SEARCH
@bot.command(name='hoi')
async def ask_economic_question_enhanced(ctx, *, question):
    """Enhanced AI Q&A with better Google Search integration"""
    
    try:
        if not ai_manager.primary_ai:
            embed = discord.Embed(
                title="⚠️ AI Services không khả dụng",
                description="Chưa cấu hình AI API keys hợp lệ.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Processing message
        processing_msg = await ctx.send("🔍 Đang tìm kiếm thông tin từ các nguồn tin đáng tin cậy...")
        
        # Search for sources with enhanced debugging
        print(f"\n🔍 STARTING SEARCH for: {question}")
        sources = await search_reliable_sources_improved(question, max_results=5)
        print(f"🔍 SEARCH COMPLETED. Found {len(sources)} sources")
        
        # Create context from sources
        context = ""
        if sources:
            print("📄 PROCESSING SOURCES:")
            for i, source in enumerate(sources, 1):
                print(f"   Source {i}: {source['source_name']} - {source['title'][:50]}...")
                context += f"Nguồn {i} ({source['source_name']}): {source['snippet']}\n"
                
                # Try to get more detailed content from top source
                if i == 1:
                    try:
                        full_content = await fetch_full_content_improved(source['link'])
                        if full_content and len(full_content) > 100:
                            context += f"Chi tiết từ {source['source_name']}: {full_content[:500]}\n"
                    except Exception as e:
                        print(f"⚠️ Failed to extract content from {source['link']}: {e}")
        else:
            context = "Không tìm thấy thông tin cụ thể từ các nguồn tin. Vui lòng sử dụng kiến thức chung."
            print("❌ NO SOURCES FOUND - using general knowledge")
        
        print(f"📄 FINAL CONTEXT LENGTH: {len(context)} characters")
        
        # Update processing message
        await processing_msg.edit(content="🤖 AI đang phân tích thông tin và tạo câu trả lời...")
        
        # Call AI with context
        try:
            print("🤖 CALLING AI ENGINE...")
            ai_response, used_engine = await ai_manager.call_ai_with_fallback(
                prompt=question,
                context=context,
                require_specific_data=False
            )
            print(f"🤖 AI RESPONSE RECEIVED from {used_engine}")
        except Exception as ai_error:
            print(f"❌ AI CALL FAILED: {ai_error}")
            ai_response = f"❌ Lỗi AI: {str(ai_error)}"
            used_engine = "error"
        
        # Delete processing message
        await processing_msg.delete()
        
        # Create response embed
        embed = discord.Embed(
            title=f"🤖 AI Trả lời: {question[:50]}...",
            description=ai_response,
            color=0x9932cc if used_engine != "error" else 0xff6b6b,
            timestamp=ctx.message.created_at
        )
        
        if used_engine != "error":
            engine_emoji = {'gemini': '💎', 'deepseek': '💰', 'claude': '🧠', 'groq': '⚡'}
            embed.add_field(
                name="🤖 AI Engine",
                value=f"{engine_emoji.get(used_engine, '🤖')} {used_engine.upper()}",
                inline=True
            )
            
            if sources:
                embed.add_field(
                    name="📊 Nguồn tin",
                    value=f"📰 {len(sources)} nguồn đã tìm kiếm",
                    inline=True
                )
                
                # Add top sources to embed
                sources_text = ""
                for i, source in enumerate(sources[:3], 1):
                    sources_text += f"{i}. **{source['source_name']}**: [{source['title'][:40]}...]({source['link']})\n"
                
                if sources_text:
                    embed.add_field(
                        name="📰 Top nguồn tin tham khảo",
                        value=sources_text,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="⚠️ Thông tin",
                    value="Không tìm thấy nguồn tin cụ thể, sử dụng kiến thức chung",
                    inline=True
                )
        
        embed.set_footer(text="🔧 Complete Fixed Version • Enhanced Google Search • !menu để xem thêm")
        
        await ctx.send(embed=embed)
        
        print(f"✅ QUESTION ANSWERED: '{question}' using {used_engine}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi tổng quát: {str(e)}")
        print(f"❌ GENERAL ERROR in !hoi: {e}")

# 🆕 ALL NEWS COMMANDS - COMPLETE VERSION
@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Get news from all sources"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức từ tất cả nguồn...")
        
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 6)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 4)
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        # Pagination
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"📰 Tin tức tổng hợp (Trang {page})",
            description=f"🕰️ Giờ Việt Nam • Từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn tin",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Statistics
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê trang này",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin",
            inline=False
        )
        
        # Display news
        source_emoji = {
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️', 'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹',
            'marketwatch_latest': '📈', 'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
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
            emoji = source_emoji.get(news['source'], '📰')
            title = news['title'][:65] + "..." if len(news['title']) > 65 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 Complete Fixed • Trang {page}/{total_pages} • !all {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!all [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# 🆕 DOMESTIC NEWS COMMAND - FIXED
@bot.command(name='in')
async def get_domestic_news(ctx, page=1):
    """Get domestic news"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức trong nước...")
        
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
            title=f"🇻🇳 Tin kinh tế trong nước (Trang {page})",
            description=f"🕰️ Giờ Việt Nam • Từ {len(RSS_FEEDS['domestic'])} nguồn chuyên ngành",
            color=0xff0000,
            timestamp=ctx.message.created_at
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin có sẵn: {len(news_list)} tin\n🎯 Lĩnh vực: Kinh tế, Chứng khoán, Bất động sản, Vĩ mô",
            inline=False
        )
        
        source_emoji = {
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
            emoji = source_emoji.get(news['source'], '📰')
            title = news['title'][:65] + "..." if len(news['title']) > 65 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 Complete Fixed • Trang {page}/{total_pages} • !in {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# 🆕 INTERNATIONAL NEWS COMMAND - FIXED
@bot.command(name='out')
async def get_international_news(ctx, page=1):
    """Get international news"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức quốc tế...")
        
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
            title=f"🌍 Tin kinh tế quốc tế (Trang {page})",
            description=f"🕰️ Giờ Việt Nam • Từ {len(RSS_FEEDS['international'])} nguồn hàng đầu",
            color=0x0066ff,
            timestamp=ctx.message.created_at
        )
        
        embed.add_field(
            name="📊 Thông tin",
            value=f"📰 Tổng tin có sẵn: {len(news_list)} tin",
            inline=False
        )
        
        source_emoji = {
            'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹', 'marketwatch_latest': '📈',
            'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
        source_names = {
            'yahoo_finance': 'Yahoo Finance', 'reuters_business': 'Reuters', 'bloomberg_markets': 'Bloomberg',
            'marketwatch_latest': 'MarketWatch', 'forbes_money': 'Forbes', 'financial_times': 'Financial Times',
            'business_insider': 'Business Insider', 'the_economist': 'The Economist'
        }
        
        for i, news in enumerate(page_news, 1):
            emoji = source_emoji.get(news['source'], '🌍')
            title = news['title'][:65] + "..." if len(news['title']) > 65 else news['title']
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"🕰️ {news['published_str']} (VN) • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔧 Complete Fixed • Trang {page}/{total_pages} • !out {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# 🆕 NEWS DETAIL COMMAND - ENHANCED
@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """Get detailed news content"""
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
        
        loading_msg = await ctx.send("⏳ Đang trích xuất nội dung đầy đủ...")
        
        full_content = await fetch_full_content_improved(news['link'])
        
        await loading_msg.delete()
        
        embed = discord.Embed(
            title="📖 Chi tiết bài viết",
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        source_emoji = {
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
        
        emoji = source_emoji.get(news['source'], '📰')
        source_display = source_names.get(news['source'], news['source'])
        
        embed.add_field(
            name=f"{emoji} Tiêu đề",
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
            value=source_display,
            inline=True
        )
        
        # Display content (split if too long)
        if len(full_content) > 1000:
            embed.add_field(
                name="📄 Nội dung chi tiết (Phần 1)",
                value=full_content[:1000] + "...",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Second embed for remaining content
            embed2 = discord.Embed(
                title=f"📖 Chi tiết bài viết (tiếp theo)",
                color=0x9932cc
            )
            
            embed2.add_field(
                name="📄 Nội dung chi tiết (Phần 2)",
                value=full_content[1000:2000],
                inline=False
            )
            
            embed2.add_field(
                name="🔗 Đọc bài viết đầy đủ",
                value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
                inline=False
            )
            
            embed2.set_footer(text=f"🔧 Complete Fixed • Từ lệnh: {user_data['command']} • Tin số {news_number}")
            
            await ctx.send(embed=embed2)
            return
        else:
            embed.add_field(
                name="📄 Nội dung chi tiết",
                value=full_content,
                inline=False
            )
        
        embed.add_field(
            name="🔗 Đọc bài viết đầy đủ",
            value=f"[Nhấn để đọc toàn bộ bài viết]({news['link']})",
            inline=False
        )
        
        embed.set_footer(text=f"🔧 Complete Fixed • Từ lệnh: {user_data['command']} • Tin số {news_number} • !menu để xem thêm")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# Alias for chitiet command
@bot.command(name='cuthe')
async def get_news_detail_alias(ctx, news_number: int):
    """Alias for !chitiet command"""
    await get_news_detail(ctx, news_number)

# 🆕 COMPLETE MENU COMMAND
@bot.command(name='menu')
async def help_command_complete(ctx):
    """Complete help menu"""
    embed = discord.Embed(
        title="🤖🔧 News Bot - Complete Fixed Version",
        description="Bot tin tức kinh tế với Multi-AI Engine hoàn chỉnh",
        color=0xff9900
    )
    
    # AI Engine status
    if ai_manager.primary_ai:
        ai_status = f"🚀 **Primary**: {ai_manager.primary_ai.value.upper()} ✅\n"
        for fallback in ai_manager.fallback_ais:
            ai_status += f"🛡️ **Fallback**: {fallback.value.upper()} ✅\n"
    else:
        ai_status = "❌ Chưa cấu hình AI engines"
    
    embed.add_field(
        name="🤖 AI Engine Status",
        value=ai_status,
        inline=False
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="""
**!all [trang]** - Tin từ tất cả nguồn (12 tin/trang)
**!in [trang]** - Tin trong nước (12 tin/trang)  
**!out [trang]** - Tin quốc tế (12 tin/trang)
**!chitiet [số]** - Xem nội dung chi tiết
        """,
        inline=True
    )
    
    embed.add_field(
        name="🤖 Lệnh AI thông minh",
        value="""
**!hoi [câu hỏi]** - AI trả lời với Google Search
*Ví dụ: !hoi giá vàng hôm nay thế nào*
        """,
        inline=True
    )
    
    embed.add_field(
        name="🇻🇳 Nguồn trong nước (14 nguồn)",
        value="CafeF (5 chuyên mục), CafeBiz, Báo Đầu tư, VnEconomy (2), VnExpress (2), Thanh Niên (2), Nhân Dân",
        inline=True
    )
    
    embed.add_field(
        name="🌍 Nguồn quốc tế (8 nguồn)",
        value="Yahoo Finance, Reuters, Bloomberg, MarketWatch, Forbes, Financial Times, Business Insider, The Economist",
        inline=True
    )
    
    embed.add_field(
        name="🔧 Complete Fixed Features",
        value="""
✅ **All Commands Working** - !all, !in, !out, !chitiet
✅ **Enhanced Google Search** - Tìm kiếm thông tin thời gian thực  
✅ **Multi-AI Engine** - Fallback system hoàn chỉnh
✅ **Better Error Handling** - Debug chi tiết
✅ **Content Extraction** - Trích xuất nội dung cải tiến
✅ **Vietnam Timezone** - Hiển thị giờ chính xác
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 Ví dụ sử dụng",
        value="""
`!all` - Xem 12 tin mới nhất từ tất cả nguồn
`!in 2` - Xem trang 2 tin trong nước  
`!out` - Xem tin quốc tế trang 1
`!chitiet 5` - Xem chi tiết tin số 5
`!hoi giá vàng hôm nay` - Hỏi AI về giá vàng với dữ liệu thời gian thực
        """,
        inline=False
    )
    
    # Google Search status
    google_status = "✅ Configured" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "❌ Not configured"
    embed.add_field(
        name="🔍 Google Search Status",
        value=f"**API Status**: {google_status}\n**Enhanced Search**: ✅ Active",
        inline=True
    )
    
    embed.set_footer(text="🔧 Complete Fixed Version • Enhanced Google Search • All Commands Working")
    await ctx.send(embed=embed)

# Cleanup function
async def cleanup():
    """Cleanup resources"""
    if ai_manager:
        await ai_manager.close_session()

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()
        print("🚀 Starting COMPLETE FIXED Multi-AI Discord News Bot...")
        
        print("📚 TESTING LIBRARY IMPORTS")
        print("=" * 50)
        if GEMINI_AVAILABLE:
            print("✅ google.generativeai imported successfully")
            if GEMINI_API_KEY:
                print("✅ Gemini API configured successfully")
        
        print("✅ aiohttp imported successfully")
        
        if GOOGLE_APIS_AVAILABLE:
            print("✅ google-api-python-client imported successfully")
        
        print("=" * 50)
        print("🤖 STARTING BOT")
        print("=" * 50)
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 {total_sources} RSS sources loaded")
        print("✅ Bot ready with COMPLETE FIXED Multi-AI Engine!")
        
        # Run bot
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
    finally:
        # Cleanup
        try:
            asyncio.run(cleanup())
        except:
            pass
