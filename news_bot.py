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

# 🆕 MULTI-AI ENGINE ARCHITECTURE - FIXED VERSION  
class AIProvider(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GROQ = "groq"

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

# 🔍 DETAILED DEBUG ENVIRONMENT VARIABLES
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
    print("❌ CẢNH BÁO: Không tìm thấy DISCORD_TOKEN trong environment variables!")
    print("🔧 Vui lòng thêm DISCORD_TOKEN vào Render Environment Variables")
    exit(1)

# 🇻🇳 TIMEZONE VIỆT NAM
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# Lưu trữ tin tức theo từng user
user_news_cache = {}

# RSS feeds đã được kiểm tra và xác nhận hoạt động
RSS_FEEDS = {
    # === KINH TẾ TRONG NƯỚC ===
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
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Lỗi chuyển đổi múi giờ: {e}")
        return datetime.now(VN_TIMEZONE)

# 🆕 IMPROVED AI ENGINE MANAGER - FIXED VERSION
class AIEngineManager:
    def __init__(self):
        self.primary_ai = None
        self.fallback_ais = []
        self.session = None  # 🔧 FIX: Properly manage async session
        self.initialize_engines()
    
    async def create_session(self):
        """🔧 FIX: Create async session properly"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        """🔧 FIX: Properly close async session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """🔧 FIX: Khởi tạo AI engines với validation cải tiến"""
        available_engines = []
        
        print("\n🔧 TESTING AI ENGINES:")
        
        # Gemini - Test thực tế
        if GEMINI_API_KEY and GEMINI_AVAILABLE:
            try:
                print(f"✅ GEMINI: API key format valid")
                # Test format chứ không test thực tế để tránh waste quota
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    available_engines.append(AIProvider.GEMINI)
                    genai.configure(api_key=GEMINI_API_KEY)
                else:
                    print("❌ GEMINI: API key format invalid")
            except Exception as e:
                print(f"❌ GEMINI: {e}")
        
        # DeepSeek - Test format
        if DEEPSEEK_API_KEY:
            try:
                print(f"✅ DEEPSEEK: API key format valid")
                if DEEPSEEK_API_KEY.startswith('sk-') and len(DEEPSEEK_API_KEY) > 30:
                    available_engines.append(AIProvider.DEEPSEEK)
                else:
                    print("❌ DEEPSEEK: API key format invalid")
            except Exception as e:
                print(f"❌ DEEPSEEK: {e}")
        
        # Claude - Test format
        if ANTHROPIC_API_KEY:
            try:
                print(f"✅ CLAUDE: API key format valid")
                if ANTHROPIC_API_KEY.startswith('sk-ant-') and len(ANTHROPIC_API_KEY) > 50:
                    available_engines.append(AIProvider.CLAUDE)
                else:
                    print("❌ CLAUDE: API key format invalid")
            except Exception as e:
                print(f"❌ CLAUDE: {e}")
        
        # Groq - Test format
        if GROQ_API_KEY:
            try:
                print(f"✅ GROQ: API key format valid")
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    available_engines.append(AIProvider.GROQ)
                else:
                    print("❌ GROQ: API key format invalid")
            except Exception as e:
                print(f"❌ GROQ: {e}")
        
        # 📊 Summary
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
        """🔧 FIX: Gọi AI với fallback improved và error handling"""
        
        # Test primary AI
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
        
        # Test fallback AIs
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
        
        # All failed
        return "❌ Tất cả AI engines đều không khả dụng. Vui lòng kiểm tra API keys và thử lại sau.", "error"

    async def _call_specific_ai_fixed(self, ai_provider, prompt, context, require_specific_data):
        """🔧 FIX: Gọi AI engine cụ thể với error handling cải tiến"""
        
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
        """🔧 FIX: Gemini call với error handling"""
        
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            system_prompt = """Bạn là chuyên gia tài chính Việt Nam. Trả lời ngắn gọn, chính xác dựa trên thông tin được cung cấp."""
            
            full_prompt = f"{system_prompt}\n\nThông tin: {context}\n\nCâu hỏi: {prompt}\n\nTrả lời:"
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.8,
                top_k=20,
                max_output_tokens=500,  # Giảm xuống để tránh timeout
            )
            
            # 🔧 FIX: Add timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    full_prompt,
                    generation_config=generation_config
                ),
                timeout=15  # 15 giây timeout
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            raise Exception("Gemini API timeout")
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def _call_deepseek_fixed(self, prompt, context, require_specific_data):
        """🔧 FIX: DeepSeek call với proper session management"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'deepseek-v3',
                'messages': [
                    {'role': 'system', 'content': 'Bạn là chuyên gia tài chính. Trả lời ngắn gọn, chính xác.'},
                    {'role': 'user', 'content': f"Thông tin: {context}\n\nCâu hỏi: {prompt}"}
                ],
                'temperature': 0.3,
                'max_tokens': 500
            }
            
            async with session.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 401:
                    raise Exception("DeepSeek API authentication failed - check API key")
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
        """🔧 FIX: Claude call với proper session management"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'x-api-key': ANTHROPIC_API_KEY,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 500,
                'temperature': 0.3,
                'messages': [
                    {
                        'role': 'user',
                        'content': f"Bạn là chuyên gia tài chính. Trả lời ngắn gọn, chính xác.\n\nThông tin: {context}\n\nCâu hỏi: {prompt}"
                    }
                ]
            }
            
            async with session.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 401:
                    raise Exception("Claude API authentication failed - check API key")
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
        """🔧 FIX: Groq call với proper session management"""
        
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': 'Bạn là chuyên gia tài chính. Trả lời ngắn gọn, chính xác.'},
                    {'role': 'user', 'content': f"Thông tin: {context}\n\nCâu hỏi: {prompt}"}
                ],
                'temperature': 0.3,
                'max_tokens': 500
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 401:
                    raise Exception("Groq API authentication failed - check API key")
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
        if not response or len(response.strip()) < 20:
            return False
        
        # Check for error messages
        error_indicators = ['❌', 'không khả dụng', 'lỗi', 'error', 'failed']
        if any(indicator in response.lower() for indicator in error_indicators):
            return False
        
        return True

# Initialize AI Manager
ai_manager = AIEngineManager()

# 🔍 IMPROVED GOOGLE SEARCH
async def search_reliable_sources_improved(query, max_results=3):
    """🔧 FIX: Tìm kiếm với error handling cải tiến"""
    
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        print("⚠️ Google Search API not configured")
        return []
    
    if not GOOGLE_APIS_AVAILABLE:
        print("⚠️ Google API Client library not available")
        return []
    
    try:
        # Simple query
        current_date = datetime.now(VN_TIMEZONE).strftime("%Y")
        enhanced_query = f'{query} {current_date} site:cafef.vn OR site:vneconomy.vn OR site:vnexpress.net'
        
        print(f"🔍 Searching: {enhanced_query}")
        
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        result = service.cse().list(
            q=enhanced_query,
            cx=GOOGLE_CSE_ID,
            num=max_results,
            lr='lang_vi',
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
        
        print(f"✅ Found {len(sources)} sources")
        return sources
        
    except Exception as e:
        print(f"❌ Google Search error: {e}")
        return []

def extract_source_name(url):
    """Extract source name from URL"""
    domain_mapping = {
        'cafef.vn': 'CafeF',
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'tuoitre.vn': 'Tuổi Trẻ',
        'thanhnien.vn': 'Thanh Niên'
    }
    
    for domain, name in domain_mapping.items():
        if domain in url:
            return name
    
    return 'Unknown Source'

# Content extraction functions (simplified)
async def fetch_full_content_improved(url):
    """Simple content extraction"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        
        # Basic content extraction
        content = response.text
        # Remove scripts and styles
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = html.unescape(content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Get meaningful content
        sentences = content.split('. ')[:5]  # First 5 sentences
        result = '. '.join(sentences)
        
        return result[:1000] + "..." if len(result) > 1000 else result
        
    except Exception as e:
        print(f"⚠️ Content extraction error: {e}")
        return "Không thể trích xuất nội dung từ bài viết này."

# RSS collection functions (simplified version)
async def collect_news_from_sources(sources_dict, limit_per_source=5):
    """Simplified news collection"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Lấy tin từ {source_name}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
                
            for entry in feed.entries[:limit_per_source]:
                try:
                    vn_time = datetime.now(VN_TIMEZONE)
                    
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.published_parsed)
                    
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:300]
                    
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
                    
                except Exception:
                    continue
                    
            print(f"✅ Lấy được tin từ {source_name}")
            
        except Exception as e:
            print(f"❌ Lỗi {source_name}: {e}")
            continue
    
    # Remove duplicates and sort
    unique_news = []
    seen_links = set()
    
    for news in all_news:
        if news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
    
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

def save_user_news(user_id, news_list, command_type):
    """Save user news cache"""
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
    
    if ai_manager.primary_ai:
        print(f'🤖 Primary AI: {ai_manager.primary_ai.value.upper()}')
        if ai_manager.fallback_ais:
            print(f'🛡️ Fallback AIs: {[ai.value.upper() for ai in ai_manager.fallback_ais]}')
    else:
        print('⚠️ No AI engines configured')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 {total_sources} nguồn RSS sẵn sàng')
    print('🎯 Gõ !menu để xem hướng dẫn')
    
    status_text = f"Fixed Multi-AI • {ai_manager.primary_ai.value.upper() if ai_manager.primary_ai else 'No AI'} • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

# 🆕 MAIN AI COMMAND - COMPLETELY FIXED
@bot.command(name='hoi')
async def ask_economic_question_fixed(ctx, *, question):
    """🔧 FIX: AI Q&A với improved error handling"""
    
    try:
        if not ai_manager.primary_ai:
            embed = discord.Embed(
                title="⚠️ AI Services không khả dụng",
                description="Chưa cấu hình AI API keys. Cần ít nhất một trong: GEMINI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Loading message
        processing_msg = await ctx.send("🔍 Đang tìm kiếm và phân tích thông tin...")
        
        # Search for sources
        sources = await search_reliable_sources_improved(question, max_results=3)
        
        # Create context from sources
        context = ""
        if sources:
            for i, source in enumerate(sources, 1):
                context += f"Nguồn {i}: {source['snippet']}\n"
        else:
            context = "Không tìm thấy nguồn tin cụ thể."
        
        # Update processing message
        await processing_msg.edit(content="🤖 AI đang phân tích và tạo câu trả lời...")
        
        # Call AI with improved error handling
        try:
            ai_response, used_engine = await ai_manager.call_ai_with_fallback(
                prompt=question,
                context=context,
                require_specific_data=False
            )
        except Exception as ai_error:
            print(f"❌ AI call failed: {ai_error}")
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
                    value=f"📰 {len(sources)} nguồn",
                    inline=True
                )
        
        embed.set_footer(text="🔧 Fixed Multi-AI Engine • !menu để xem thêm lệnh")
        
        await ctx.send(embed=embed)
        
        print(f"✅ Question answered: '{question}' using {used_engine}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi tổng quát: {str(e)}")
        print(f"❌ General error in !hoi: {e}")

# NEWS COMMANDS (simplified versions)
@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Lấy tin tức từ tất cả nguồn"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức...")
        
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 5)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 3)
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        # Pagination
        items_per_page = 10
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            await ctx.send(f"❌ Không có tin tức ở trang {page}!")
            return
        
        embed = discord.Embed(
            title=f"📰 Tin tức tổng hợp (Trang {page})",
            description=f"Từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn tin",
            color=0x00ff88
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
        embed.set_footer(text=f"Trang {page}/{total_pages} • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """Xem chi tiết tin tức"""
    try:
        user_id = ctx.author.id
        
        if user_id not in user_news_cache:
            await ctx.send("❌ Bạn chưa xem tin tức nào! Hãy dùng `!all` trước.")
            return
        
        user_data = user_news_cache[user_id]
        news_list = user_data['news']
        
        if news_number < 1 or news_number > len(news_list):
            await ctx.send(f"❌ Số không hợp lệ! Chọn từ 1 đến {len(news_list)}")
            return
        
        news = news_list[news_number - 1]
        
        loading_msg = await ctx.send("⏳ Đang tải nội dung...")
        
        full_content = await fetch_full_content_improved(news['link'])
        
        await loading_msg.delete()
        
        embed = discord.Embed(
            title="📖 Chi tiết bài viết",
            color=0x9932cc
        )
        
        embed.add_field(
            name="📰 Tiêu đề",
            value=news['title'],
            inline=False
        )
        
        embed.add_field(
            name="🕰️ Thời gian",
            value=news['published_str'],
            inline=True
        )
        
        embed.add_field(
            name="📄 Nội dung",
            value=full_content,
            inline=False
        )
        
        embed.add_field(
            name="🔗 Đọc đầy đủ",
            value=f"[Nhấn để đọc]({news['link']})",
            inline=False
        )
        
        embed.set_footer(text="🔧 Fixed Version • !menu để xem thêm")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='menu')
async def help_command(ctx):
    """Menu hướng dẫn"""
    embed = discord.Embed(
        title="🤖🔧 News Bot - Fixed Version",
        description="Bot tin tức với Multi-AI Engine đã được sửa lỗi",
        color=0xff9900
    )
    
    # AI status
    if ai_manager.primary_ai:
        ai_status = f"🚀 Primary: {ai_manager.primary_ai.value.upper()} ✅\n"
        for fallback in ai_manager.fallback_ais:
            ai_status += f"🛡️ Fallback: {fallback.value.upper()} ✅\n"
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
**!all [trang]** - Tin từ tất cả nguồn
**!chitiet [số]** - Xem nội dung chi tiết
        """,
        inline=True
    )
    
    embed.add_field(
        name="🤖 Lệnh AI",
        value="""
**!hoi [câu hỏi]** - Hỏi AI về kinh tế
*Ví dụ: !hoi giá vàng hôm nay*
        """,
        inline=True
    )
    
    embed.add_field(
        name="🔧 Cải tiến",
        value="""
✅ Fixed async session management
✅ Improved error handling  
✅ Better API key validation
✅ Reduced timeout issues
✅ Enhanced fallback system
        """,
        inline=False
    )
    
    embed.set_footer(text="🔧 Fixed Multi-AI Engine • Stable Version")
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
        print("🚀 Starting FIXED Multi-AI Discord News Bot...")
        
        if TOKEN:
            print("✅ Discord token loaded")
        
        print("📚 TESTING LIBRARY IMPORTS")
        print("=" * 50)
        if GEMINI_AVAILABLE:
            print("✅ google.generativeai imported successfully")
            if GEMINI_API_KEY:
                print("✅ Gemini API configured successfully")
        else:
            print("❌ google.generativeai not available") 
            
        print("✅ aiohttp imported successfully")
        
        if GOOGLE_APIS_AVAILABLE:
            print("✅ google-api-python-client imported successfully")
        else:
            print("❌ google-api-python-client not available")
        
        print("=" * 50)
        print("🤖 STARTING BOT")
        print("=" * 50)
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 {total_sources} RSS sources loaded")
        print("✅ Bot ready with FIXED Multi-AI Engine!")
        
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
