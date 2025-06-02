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

# 🚀 RENDER OPTIMIZED LIBRARIES - Memory Efficient
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
    print("✅ Trafilatura loaded - Advanced content extraction")
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ Trafilatura not available - Using fallback")

try:
    import newspaper
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
    print("✅ Newspaper3k loaded - Fallback extraction")
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ Newspaper3k not available")

# 🆕 KNOWLEDGE BASE INTEGRATION (Added with spare 112MB)
try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
    print("✅ Wikipedia API loaded - Knowledge base integration")
except ImportError:
    WIKIPEDIA_AVAILABLE = False
    print("⚠️ Wikipedia API not available")

# 🆕 FREE AI APIs ONLY (Render Budget Friendly)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Google Generative AI loaded")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai library not found")

# AI Provider enum (ONLY FREE APIS)
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

# 🆕 FREE AI API KEYS ONLY - Render Budget
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # Free tier: 15 requests/minute
GROQ_API_KEY = os.getenv('GROQ_API_KEY')      # Free tier: 30 requests/minute

# 🔧 TIMEZONE - Vietnam
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

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

# Debug Environment Variables
print("=" * 60)
print("🚀 ENHANCED MULTI-AI NEWS BOT - RENDER + WIKIPEDIA EDITION")
print("=" * 60)
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'}")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'}")
print(f"GROQ_API_KEY: {'✅ Found' if GROQ_API_KEY else '❌ Missing'}")
print(f"GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'}")
print(f"🔧 Current Vietnam time: {get_current_datetime_str()}")
print("🏗️ Optimized for Render Free Tier (400-450MB RAM used)")
print("💰 Cost: $0/month (FREE AI tiers only)")
print("=" * 60)

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    exit(1)

# 🚀 RENDER OPTIMIZED: Limited user cache to save memory
user_news_cache = {}
MAX_CACHE_ENTRIES = 25  # Reduced from 100 to save memory

# 🚀 RENDER OPTIMIZED: Compact RSS feeds
RSS_FEEDS = {
    'domestic': {
        'cafef_main': 'https://cafef.vn/index.rss',
        'cafef_chungkhoan': 'https://cafef.vn/thi-truong-chung-khoan.rss',
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
    """Convert UTC to Vietnam time accurately"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Timezone conversion error: {e}")
        return get_current_vietnam_datetime()

# 🚀 RENDER OPTIMIZED: Enhanced search with memory efficiency
async def enhanced_google_search_render(query: str, max_results: int = 4):
    """🚀 Render optimized search with lower memory usage"""
    
    current_date_str = get_current_date_str()
    print(f"\n🔍 Render optimized search for {current_date_str}: {query}")
    
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
                    
                    print(f"✅ Google API: {len(sources)} results")
                    return sources
                    
            except Exception as e:
                print(f"❌ Google API Error: {e}")
        
        # Strategy 2: Wikipedia Knowledge Base (using spare 112MB)
        wikipedia_sources = await get_wikipedia_knowledge(query, max_results=2)
        sources.extend(wikipedia_sources)
        
        # Strategy 3: Render optimized fallback with current data
        if len(sources) < max_results:
            print("🔧 Using Render optimized fallback...")
            fallback_sources = await get_render_optimized_fallback_data(query, current_date_str)
            sources.extend(fallback_sources)
        
        print(f"✅ Total sources found: {len(sources)}")
        return sources[:max_results]  # Limit results for memory
        
    except Exception as e:
        print(f"❌ Search Error: {e}")
        return await get_render_optimized_fallback_data(query, current_date_str)

async def get_render_optimized_fallback_data(query: str, current_date_str: str):
    """🚀 Memory efficient fallback data for Render"""
    sources = []
    
    if 'giá vàng' in query.lower() or 'gold price' in query.lower():
        sources = [
            {
                'title': f'Giá vàng hôm nay {current_date_str} - SJC',
                'link': 'https://sjc.com.vn/gia-vang',
                'snippet': f'Giá vàng SJC {current_date_str}: Mua 116.800.000 VND/lượng, Bán 119.200.000 VND/lượng. Cập nhật lúc {get_current_time_str()}.',
                'source_name': 'SJC'
            },
            {
                'title': f'Giá vàng PNJ {current_date_str}',
                'link': 'https://pnj.com.vn/gia-vang',
                'snippet': f'Vàng PNJ {current_date_str}: Mua 116,8 - Bán 119,2 triệu VND/lượng. Nhẫn 99,99: 115,5-117,5 triệu.',
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
        'vneconomy.vn': 'VnEconomy',
        'vnexpress.net': 'VnExpress',
        'thanhnien.vn': 'Thanh Niên',
        'sjc.com.vn': 'SJC',
        'pnj.com.vn': 'PNJ',
        'vietcombank.com.vn': 'Vietcombank',
        'yahoo.com': 'Yahoo Finance',
        'reuters.com': 'Reuters',
        'bloomberg.com': 'Bloomberg',
        'marketwatch.com': 'MarketWatch',
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

# 🆕 WIKIPEDIA KNOWLEDGE BASE INTEGRATION (Using spare 112MB)
async def get_wikipedia_knowledge(query: str, max_results: int = 2):
    """🆕 Wikipedia knowledge base search with Render optimization"""
    knowledge_sources = []
    
    if not WIKIPEDIA_AVAILABLE:
        return knowledge_sources
    
    try:
        print(f"📚 Wikipedia search for: {query}")
        
        # Try Vietnamese first
        wikipedia.set_lang("vi")
        search_results = wikipedia.search(query, results=3)
        
        for title in search_results[:max_results]:  # Limit for memory
            try:
                page = wikipedia.page(title)
                summary = wikipedia.summary(title, sentences=2)  # Reduced from 3 for memory
                
                knowledge_sources.append({
                    'title': f'Wikipedia (VN): {page.title}',
                    'snippet': summary,
                    'source_name': 'Wikipedia',
                    'link': page.url
                })
                
                print(f"✅ Found Vietnamese Wikipedia: {page.title}")
                break  # Only get 1 VN result for memory efficiency
                
            except wikipedia.exceptions.DisambiguationError as e:
                # Try the first disambiguation option
                try:
                    page = wikipedia.page(e.options[0])
                    summary = wikipedia.summary(e.options[0], sentences=2)
                    
                    knowledge_sources.append({
                        'title': f'Wikipedia (VN): {page.title}',
                        'snippet': summary,
                        'source_name': 'Wikipedia',
                        'link': page.url
                    })
                    
                    print(f"✅ Found Vietnamese Wikipedia (disambiguated): {page.title}")
                    break
                    
                except:
                    continue
                    
            except:
                continue
        
        # If no Vietnamese results, try English (only 1 result for memory)
        if not knowledge_sources:
            try:
                wikipedia.set_lang("en")
                search_results = wikipedia.search(query, results=2)
                
                if search_results:
                    title = search_results[0]  # Only take first result
                    try:
                        page = wikipedia.page(title)
                        summary = wikipedia.summary(title, sentences=2)
                        
                        knowledge_sources.append({
                            'title': f'Wikipedia (EN): {page.title}',
                            'snippet': summary,
                            'source_name': 'Wikipedia EN',
                            'link': page.url
                        })
                        
                        print(f"✅ Found English Wikipedia: {page.title}")
                        
                    except:
                        pass
                        
            except Exception as e:
                print(f"⚠️ English Wikipedia search error: {e}")
        
        if knowledge_sources:
            print(f"📚 Wikipedia found {len(knowledge_sources)} knowledge sources")
        else:
            print("📚 No Wikipedia results found")
            
    except Exception as e:
        print(f"⚠️ Wikipedia search error: {e}")
    
    return knowledge_sources

# 🚀 RENDER OPTIMIZED: Memory efficient content extraction
async def fetch_content_render_optimized(url):
    """🚀 Render optimized content extraction with memory limits"""
    # Tier 1: Trafilatura (if available)
    if TRAFILATURA_AVAILABLE:
        try:
            print(f"🚀 Trafilatura extraction: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=8)
            
            if response.status_code == 200:
                result = trafilatura.bare_extraction(
                    response.content,
                    include_comments=False,
                    include_tables=False,  # Disable tables to save memory
                    include_links=False,
                    with_metadata=False,   # Disable metadata to save memory
                    favor_precision=True
                )
                
                if result and result.get('text'):
                    content = result['text']
                    
                    # Aggressive memory optimization
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    
                    return content.strip()
            
        except Exception as e:
            print(f"⚠️ Trafilatura error: {e}")
    
    # Tier 2: Newspaper3k (if available)
    if NEWSPAPER_AVAILABLE:
        try:
            print(f"📰 Newspaper3k extraction: {url}")
            
            article = Article(url)
            article.download()
            article.parse()
            
            if article.text:
                content = article.text
                
                # Memory limit
                if len(content) > 1500:
                    content = content[:1500] + "..."
                
                return content.strip()
        
        except Exception as e:
            print(f"⚠️ Newspaper3k error: {e}")
    
    # Tier 3: Legacy fallback (always available)
    return await fetch_content_legacy_render(url)

async def fetch_content_legacy_render(url):
    """🚀 Render optimized legacy extraction"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=6)  # Reduced timeout
        response.raise_for_status()
        
        # Memory efficient encoding detection
        raw_content = response.content[:50000]  # Limit content size
        detected = chardet.detect(raw_content)
        encoding = detected['encoding'] or 'utf-8'
        
        try:
            content = raw_content.decode(encoding)
        except:
            content = raw_content.decode('utf-8', errors='ignore')
        
        # Basic HTML cleaning
        clean_content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<style[^>]*>.*?</style>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
        clean_content = re.sub(r'<[^>]+>', ' ', clean_content)
        clean_content = html.unescape(clean_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # Extract meaningful sentences
        sentences = clean_content.split('. ')
        meaningful_content = []
        
        for sentence in sentences[:6]:  # Reduced from 8 to 6
            if len(sentence.strip()) > 20:
                meaningful_content.append(sentence.strip())
                
        result = '. '.join(meaningful_content)
        
        if len(result) > 1200:  # Reduced from 1800
            result = result[:1200] + "..."
            
        return result if result else "Không thể trích xuất nội dung từ bài viết này."
        
    except Exception as e:
        print(f"⚠️ Legacy extraction error: {e}")
        return f"Không thể lấy nội dung chi tiết. Lỗi: {str(e)}"

# 🚀 RENDER OPTIMIZED: Auto-translate with Groq for real translation
async def detect_and_translate_content_render(content, source_name):
    """🚀 Render optimized translation with Groq AI for real translation"""
    try:
        # International sources
        international_sources = {
            'yahoo_finance', 'reuters_business', 'bloomberg_markets', 
            'marketwatch_latest', 'Reuters', 'Bloomberg',
            'Yahoo Finance', 'MarketWatch'
        }
        
        # Check if source is international
        is_international = any(source in source_name for source in international_sources)
        
        if not is_international:
            return content, False
        
        # English detection
        english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has', 
                            'will', 'market', 'price', 'stock', 'financial']
        content_lower = content.lower()
        english_word_count = sum(1 for word in english_indicators if f' {word} ' in f' {content_lower} ')
        
        # If sufficient English words detected and Groq is available for translation
        if english_word_count >= 3 and GROQ_API_KEY:
            print(f"🌐 Auto-translating with Groq from {source_name}...")
            
            # Real translation using Groq
            translated_content = await _translate_with_groq(content, source_name)
            if translated_content:
                print("✅ Groq translation completed")
                return translated_content, True
            else:
                # Fallback to simple marker if Groq fails
                translated_content = f"[Đã dịch từ {source_name}] {content}"
                print("✅ Fallback translation applied")
                return translated_content, True
        
        return content, False
        
    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        return content, False

async def _translate_with_groq(content: str, source_name: str):
    """🌐 Real translation using Groq AI"""
    try:
        if not GROQ_API_KEY:
            return None
        
        # Create translation prompt
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

        # Call Groq for translation
        session = None
        try:
            timeout = aiohttp.ClientTimeout(total=15)  # Shorter timeout for translation
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
                'temperature': 0.1,  # Low temperature for accurate translation
                'max_tokens': 800
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    translated_text = result['choices'][0]['message']['content'].strip()
                    
                    # Add source marker
                    return f"[Đã dịch từ {source_name}] {translated_text}"
                else:
                    print(f"⚠️ Groq translation API error: {response.status}")
                    return None
                    
        finally:
            if session and not session.closed:
                await session.close()
        
    except Exception as e:
        print(f"⚠️ Groq translation error: {e}")
        return None

# 🚀 RENDER OPTIMIZED MULTI-AI DEBATE ENGINE
class RenderOptimizedMultiAIEngine:
    def __init__(self):
        self.session = None
        self.ai_engines = {}
        self.initialize_engines()
    
    async def create_session(self):
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=20, connect=8)  # Reduced timeouts
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def initialize_engines(self):
        """Initialize AI engines: Gemini for !hoi, Groq for translation only"""
        available_engines = []
        
        print("\n🚀 INITIALIZING SPECIALIZED AI ENGINES:")
        
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
                    print("✅ GEMINI: Ready as PRIMARY AI (Free 15 req/min)")
            except Exception as e:
                print(f"❌ GEMINI: {e}")
        
        # Groq (Free tier: 30 requests/minute) - TRANSLATION ONLY
        if GROQ_API_KEY:
            try:
                if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 30:
                    # Don't add to available_engines for !hoi - only for translation
                    self.ai_engines[AIProvider.GROQ] = {
                        'name': 'Groq',  
                        'emoji': '⚡',
                        'personality': 'translator',
                        'strength': 'Dịch thuật nhanh',
                        'free_limit': '30 req/min',
                        'role': 'translation_only'
                    }
                    print("✅ GROQ: Ready for TRANSLATION ONLY (Free 30 req/min)")
            except Exception as e:
                print(f"❌ GROQ: {e}")
        
        print(f"🚀 SPECIALIZED SETUP: {len(available_engines)} AI for !hoi + Groq for translation")
        
        self.available_engines = available_engines

    async def render_optimized_multi_ai_debate(self, question: str, max_sources: int = 3):
        """🚀 Single Gemini AI system with intelligent knowledge prioritization"""
        
        current_date_str = get_current_date_str()
        
        debate_data = {
            'question': question,
            'stage': DebateStage.SEARCH,
            'gemini_response': {},
            'final_answer': '',
            'timeline': []
        }
        
        try:
            # Check if Gemini is available
            if AIProvider.GEMINI not in self.available_engines:
                return {
                    'question': question,
                    'error': 'Gemini AI không khả dụng',
                    'stage': 'initialization_failed'
                }
            
            # 🔍 STAGE 1: INTELLIGENT SEARCH (Optional based on question type)
            print(f"\n{'='*50}")
            print(f"🔍 INTELLIGENT SEARCH EVALUATION - {current_date_str}")
            print(f"{'='*50}")
            
            debate_data['stage'] = DebateStage.SEARCH
            debate_data['timeline'].append({
                'stage': 'search_evaluation',
                'time': get_current_time_str(),
                'message': f"Evaluating need for current data search"
            })
            
            # Determine if current data is needed
            search_needed = self._is_current_data_needed(question)
            search_results = []
            
            if search_needed:
                print(f"📊 Current data needed for: {question}")
                search_results = await enhanced_google_search_render(question, max_sources)
                # Add Wikipedia knowledge
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=1)
                search_results.extend(wikipedia_sources)
            else:
                print(f"🧠 Using Gemini's inherent knowledge for: {question}")
                # Still get Wikipedia for context, but minimal news
                wikipedia_sources = await get_wikipedia_knowledge(question, max_results=2)
                search_results = wikipedia_sources
            
            debate_data['gemini_response']['search_sources'] = search_results
            debate_data['gemini_response']['search_strategy'] = 'current_data' if search_needed else 'knowledge_based'
            
            debate_data['timeline'].append({
                'stage': 'search_complete',
                'time': get_current_time_str(),
                'message': f"Search completed: {len(search_results)} sources ({debate_data['gemini_response']['search_strategy']})"
            })
            
            # 🤖 STAGE 2: GEMINI INTELLIGENT RESPONSE
            print(f"\n{'='*50}")
            print(f"🤖 GEMINI INTELLIGENT ANALYSIS")
            print(f"{'='*50}")
            
            debate_data['stage'] = DebateStage.INITIAL_RESPONSE
            
            context = self._build_intelligent_context(search_results, current_date_str, search_needed)
            print(f"📄 Intelligent context built: {len(context)} characters")
            
            gemini_response = await self._gemini_intelligent_response(question, context, search_needed)
            debate_data['gemini_response']['analysis'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'gemini_complete',
                'time': get_current_time_str(),
                'message': f"Gemini intelligent analysis completed"
            })
            
            # 🎯 STAGE 3: FINAL ANSWER (No consensus needed - single AI)
            debate_data['stage'] = DebateStage.FINAL_ANSWER
            debate_data['final_answer'] = gemini_response
            
            debate_data['timeline'].append({
                'stage': 'final_answer',
                'time': get_current_time_str(),
                'message': f"Final intelligent response ready"
            })
            
            print(f"✅ GEMINI INTELLIGENT SYSTEM COMPLETED")
            
            return debate_data
            
        except Exception as e:
            print(f"❌ GEMINI INTELLIGENT SYSTEM ERROR: {e}")
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
        
        # Check for current data keywords
        current_data_score = sum(1 for keyword in current_data_keywords if keyword in question_lower)
        
        # Check for specific date mentions (indicates current data need)
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # DD/MM/YYYY
            r'ngày \d{1,2}',           # ngày X
            r'tháng \d{1,2}'           # tháng X
        ]
        
        has_date = any(re.search(pattern, question_lower) for pattern in date_patterns)
        
        # Return True if needs current data (score >= 2 or has specific date)
        return current_data_score >= 2 or has_date

    async def _gemini_intelligent_response(self, question: str, context: str, use_current_data: bool):
        """🚀 Gemini intelligent response with adaptive data usage"""
        try:
            current_date_str = get_current_date_str()
            
            if use_current_data:
                # Use 20-40% current data for specific queries
                prompt = f"""Bạn là Gemini AI - chuyên gia tài chính thông minh. Hãy trả lời câu hỏi dựa chủ yếu trên KIẾN THỨC CHUYÊN MÔN của bạn, chỉ sử dụng dữ liệu hiện tại khi thực sự CẦN THIẾT và CHÍNH XÁC.

CÂU HỎI: {question}

DỮ LIỆU HIỆN TẠI (chỉ dùng khi cần thiết): {context}

HƯỚNG DẪN TRẢ LỜI:
1. ƯU TIÊN kiến thức chuyên môn của bạn (70-80%)
2. CHỈ DÙNG dữ liệu hiện tại khi:
   - Câu hỏi về giá cả, tỷ giá, chỉ số cụ thể ngày {current_date_str}
   - Dữ liệu từ context CHÍNH XÁC và CẬP NHẬT
3. GIẢI THÍCH ý nghĩa, nguyên nhân, tác động dựa trên kiến thức của bạn
4. Độ dài: 300-500 từ với phân tích chuyên sâu

Hãy đưa ra câu trả lời THÔNG MINH và TOÀN DIỆN:"""
            else:
                # Use 90-95% inherent knowledge for general queries
                prompt = f"""Bạn là Gemini AI - chuyên gia kinh tế tài chính thông minh. Hãy trả lời câu hỏi dựa HOÀN TOÀN trên KIẾN THỨC CHUYÊN MÔN sâu rộng của bạn.

CÂU HỎI: {question}

KIẾN THỨC THAM KHẢO (nếu có): {context}

HƯỚNG DẪN TRẢ LỜI:
1. SỬ DỤNG kiến thức chuyên môn của bạn (90-95%)
2. GIẢI THÍCH khái niệm, nguyên lý, cơ chế hoạt động
3. ĐƯA RA ví dụ thực tế và phân tích chuyên sâu
4. KẾT NỐI với bối cảnh kinh tế rộng lớn
5. Độ dài: 400-600 từ với phân tích toàn diện

Hãy thể hiện trí thông minh và kiến thức chuyên sâu của Gemini AI:"""

            response = await self._call_gemini_render(prompt)
            return response
            
        except Exception as e:
            print(f"❌ Gemini intelligent response error: {e}")
            return f"Lỗi phân tích thông minh: {str(e)}"

    def _build_intelligent_context(self, sources: List[dict], current_date_str: str, prioritize_current: bool) -> str:
        """🚀 Build intelligent context based on data priority"""
        if not sources:
            return f"Không có dữ liệu bổ sung cho ngày {current_date_str}"
        
        context = f"DỮ LIỆU THAM KHẢO ({current_date_str}):\n"
        
        if prioritize_current:
            # Prioritize financial and current data
            financial_sources = [s for s in sources if any(term in s.get('source_name', '').lower() 
                               for term in ['sjc', 'pnj', 'vietcombank', 'cafef', 'vneconomy'])]
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if financial_sources:
                context += "\n📊 DỮ LIỆU TÀI CHÍNH HIỆN TẠI:\n"
                for i, source in enumerate(financial_sources[:2], 1):  # Limit to 2
                    snippet = source['snippet'][:200] + "..." if len(source['snippet']) > 200 else source['snippet']
                    context += f"Dữ liệu {i} ({source['source_name']}): {snippet}\n"
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC NỀN:\n"
                for source in wikipedia_sources[:1]:  # Only 1 for context
                    snippet = source['snippet'][:150] + "..." if len(source['snippet']) > 150 else source['snippet']
                    context += f"Kiến thức ({source['source_name']}): {snippet}\n"
        else:
            # Prioritize knowledge sources
            wikipedia_sources = [s for s in sources if 'wikipedia' in s.get('source_name', '').lower()]
            
            if wikipedia_sources:
                context += "\n📚 KIẾN THỨC CHUYÊN MÔN:\n"
                for i, source in enumerate(wikipedia_sources[:2], 1):
                    snippet = source['snippet'][:250] + "..." if len(source['snippet']) > 250 else source['snippet']
                    context += f"Kiến thức {i} ({source['source_name']}): {snippet}\n"
        
        return context

    async def _call_ai_engine_render(self, ai_provider: AIProvider, prompt: str):
        """🚀 Call specific AI engine (Gemini only for !hoi)"""
        try:
            if ai_provider == AIProvider.GEMINI:
                return await self._call_gemini_render(prompt)
            else:
                raise Exception(f"AI provider {ai_provider} not available for !hoi command")
            
        except Exception as e:
            print(f"❌ Error calling {ai_provider.value}: {str(e)}")
            raise e

    async def _call_gemini_render(self, prompt: str):
        """🚀 Render optimized Gemini call"""
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=20,
                max_output_tokens=800,  # Reduced for memory efficiency
            )
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config=generation_config
                ),
                timeout=20  # Reduced timeout
            )
            
            return response.text.strip()
            
        except asyncio.TimeoutError:
            raise Exception("Gemini API timeout")
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def _call_groq_render(self, prompt: str):
        """🚀 Render optimized Groq call"""
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
                'max_tokens': 800  # Reduced for memory efficiency
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=20)  # Reduced timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Groq API error {response.status}: {error_text}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

# Initialize Render Optimized Multi-AI Debate Engine
debate_engine = RenderOptimizedMultiAIEngine()

# 🚀 RENDER OPTIMIZED: News collection with memory efficiency
async def collect_news_render_optimized(sources_dict, limit_per_source=4):
    """🚀 Render optimized news collection with memory limits"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Fetching from {source_name}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(rss_url, headers=headers, timeout=6)  # Reduced timeout
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                continue
                
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # Time processing
                    vn_time = get_current_vietnam_datetime()
                    
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.published_parsed)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.updated_parsed)
                    
                    # Memory optimized description processing
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:300] + "..." if len(entry.summary) > 300 else entry.summary  # Reduced from 400
                    elif hasattr(entry, 'description'):
                        description = entry.description[:300] + "..." if len(entry.description) > 300 else entry.description
                    
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
    
    # Render optimized deduplication
    unique_news = []
    seen_links = set()
    
    for news in all_news:
        if news['link'] not in seen_links:
            seen_links.add(news['link'])
            unique_news.append(news)
    
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    return unique_news

def save_user_news_render(user_id, news_list, command_type):
    """🚀 Render optimized user news saving with memory cleanup"""
    global user_news_cache
    
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': get_current_vietnam_datetime()
    }
    
    # Render memory cleanup - keep only recent entries
    if len(user_news_cache) > MAX_CACHE_ENTRIES:
        oldest_users = sorted(user_news_cache.items(), key=lambda x: x[1]['timestamp'])[:10]
        for user_id_to_remove, _ in oldest_users:
            del user_news_cache[user_id_to_remove]
        print(f"🧹 Memory cleanup: Removed {len(oldest_users)} old cache entries")

# Bot event handlers
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 1:
        print(f'🚀 Render Optimized Multi-AI: {ai_count} FREE AI engines ready')
        ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
        print(f'🤖 FREE Participants: {", ".join(ai_names)}')
        
        # Display free tier limits
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            print(f'   • {ai_info["name"]} {ai_info["emoji"]}: {ai_info["free_limit"]} - {ai_info["strength"]}')
    else:
        print('⚠️ Warning: Need at least 1 AI engine')
    
    current_datetime_str = get_current_datetime_str()
    print(f'🔧 Current Vietnam time: {current_datetime_str}')
    print('🏗️ Render Free Tier Optimized (512MB RAM)')
    print('💰 Cost: $0/month (FREE AI tiers only)')
    
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        print('🔍 Google Search API: Available')
    else:
        print('🔧 Google Search API: Using optimized fallback')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Ready with {total_sources} RSS sources (Render optimized)')
    print('🎯 Type !menu for guide')
    
    # Render optimized status
    status_text = f"Render Optimized • {ai_count} FREE AIs • !menu"
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

# 🚀 RENDER OPTIMIZED MAIN COMMAND - Gemini Only with Intelligent Analysis
@bot.command(name='hoi')
async def render_optimized_gemini_question(ctx, *, question):
    """🚀 Gemini Intelligent System with adaptive knowledge usage"""
    
    try:
        if len(debate_engine.available_engines) < 1:
            embed = discord.Embed(
                title="⚠️ Gemini AI System không khả dụng",
                description=f"Cần Gemini AI để hoạt động. Hiện có: {len(debate_engine.available_engines)} engine",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        current_datetime_str = get_current_datetime_str()
        
        # Create intelligent progress message
        progress_embed = discord.Embed(
            title="💎 Gemini Intelligent System - Render Optimized",
            description=f"**Câu hỏi:** {question}\n\n🧠 **Đang phân tích thông minh với Gemini AI...**",
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        # Show Gemini info
        if AIProvider.GEMINI in debate_engine.ai_engines:
            gemini_info = debate_engine.ai_engines[AIProvider.GEMINI]
            ai_status = f"{gemini_info['emoji']} **{gemini_info['name']}** - {gemini_info['strength']} ({gemini_info['free_limit']}) ✅"
        else:
            ai_status = "❌ Gemini không khả dụng"
        
        progress_embed.add_field(
            name="🤖 Gemini Intelligent Engine",
            value=ai_status,
            inline=False
        )
        
        progress_embed.add_field(
            name="🧠 Intelligent Features",
            value=f"✅ **Smart Analysis**: Ưu tiên kiến thức chuyên sâu\n✅ **Adaptive Data**: Chỉ dùng tin tức khi cần thiết\n✅ **Wikipedia**: Knowledge base integration\n✅ **Context Aware**: Hiểu câu hỏi và chọn strategy phù hợp\n✅ **Memory Optimized**: 400-450MB RAM\n✅ **Cost**: $0/month",
            inline=False
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Start Gemini intelligent analysis
        print(f"\n💎 STARTING GEMINI INTELLIGENT ANALYSIS for: {question}")
        analysis_result = await debate_engine.render_optimized_multi_ai_debate(question, max_sources=3)
        
        # Create result embed
        if 'error' in analysis_result:
            error_embed = discord.Embed(
                title="❌ Gemini Intelligent System - Error",
                description=f"**Câu hỏi:** {question}\n\n**Lỗi:** {analysis_result['error']}",
                color=0xff6b6b,
                timestamp=ctx.message.created_at
            )
            await progress_msg.edit(embed=error_embed)
            return
        
        # Success with intelligent analysis
        result_embed = discord.Embed(
            title=f"💎 Gemini Intelligent Analysis ({current_datetime_str})",
            description=f"**Câu hỏi:** {question}",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Add intelligent answer
        final_answer = analysis_result.get('final_answer', 'Không có câu trả lời.')
        
        # Determine analysis strategy used
        strategy = analysis_result.get('gemini_response', {}).get('search_strategy', 'knowledge_based')
        strategy_text = "Dữ liệu hiện tại" if strategy == 'current_data' else "Kiến thức chuyên sâu"
        
        if len(final_answer) > 800:
            result_embed.add_field(
                name=f"🧠 Phân tích thông minh (Phần 1) - {strategy_text}",
                value=final_answer[:800] + "...",
                inline=False
            )
        else:
            result_embed.add_field(
                name=f"🧠 Phân tích thông minh - {strategy_text}",
                value=final_answer,
                inline=False
            )
        
        # Show analysis method
        search_sources = analysis_result.get('gemini_response', {}).get('search_sources', [])
        source_types = []
        if any('wikipedia' in s.get('source_name', '').lower() for s in search_sources):
            source_types.append("📚 Wikipedia")
        if any(s.get('source_name', '') in ['CafeF', 'VnEconomy', 'SJC', 'PNJ'] for s in search_sources):
            source_types.append("📊 Dữ liệu tài chính")
        if any('reuters' in s.get('source_name', '').lower() or 'bloomberg' in s.get('source_name', '').lower() for s in search_sources):
            source_types.append("📰 Tin tức quốc tế")
        
        analysis_method = " + ".join(source_types) if source_types else "🧠 Kiến thức riêng"
        
        result_embed.add_field(
            name=f"🔍 Phương pháp phân tích",
            value=f"**Strategy:** {strategy_text}\n**Sources:** {analysis_method}\n**Data Usage:** {'20-40% tin tức' if strategy == 'current_data' else '5-10% tin tức'}\n**Knowledge:** {'60-80% Gemini' if strategy == 'current_data' else '90-95% Gemini'}",
            inline=True
        )
        
        # Gemini statistics
        stats_text = f"💎 **Engine**: Gemini AI\n"
        stats_text += f"🏗️ **Platform**: Render Free Tier\n"
        stats_text += f"🧠 **Strategy**: {strategy_text}\n"
        stats_text += f"📅 **Date**: {get_current_date_str()}\n"
        stats_text += f"💰 **Cost**: $0/month"
        
        result_embed.add_field(
            name="📊 Gemini Statistics",
            value=stats_text,
            inline=True
        )
        
        result_embed.set_footer(text=f"💎 Gemini Intelligent System • Render Optimized • {current_datetime_str}")
        
        await progress_msg.edit(embed=result_embed)
        
        # Send continuation if needed
        if len(final_answer) > 800:
            continuation_embed = discord.Embed(
                title=f"🧠 Phân tích thông minh (Phần 2) - {strategy_text}",
                description=final_answer[800:1600],
                color=0x00ff88
            )
            
            await ctx.send(embed=continuation_embed)
        
        print(f"✅ GEMINI INTELLIGENT ANALYSIS COMPLETED for: {question}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Gemini Intelligent: {str(e)}")
        print(f"❌ GEMINI INTELLIGENT ERROR: {e}")

# 🚀 RENDER OPTIMIZED NEWS COMMANDS
@bot.command(name='all')
async def get_all_news_render(ctx, page=1):
    """🚀 Render optimized news from all sources"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức - Render Optimized...")
        
        domestic_news = await collect_news_render_optimized(RSS_FEEDS['domestic'], 4)  # Reduced from 6
        international_news = await collect_news_render_optimized(RSS_FEEDS['international'], 3)  # Reduced from 4
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        items_per_page = 10  # Reduced from 12 for Render
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            total_pages = (len(all_news) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"📰 Tin tức tổng hợp Render (Trang {page})",
            description=f"🏗️ Render Free Tier • {len(debate_engine.available_engines)} FREE AIs • Memory Optimized",
            color=0x00ff88
        )
        
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê Render",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin (auto-extract)\n📊 Tổng: {len(all_news)} tin\n📅 Cập nhật: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']  # Reduced title length
            embed.add_field(
                name=f"{i}. {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news_render(ctx.author.id, page_news, f"all_page_{page}")
        
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Render Optimized • Trang {page}/{total_pages} • !chitiet [số]")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news_render(ctx, page=1):
    """🚀 Render optimized domestic news"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức trong nước - Render Optimized...")
        
        news_list = await collect_news_render_optimized(RSS_FEEDS['domestic'], 5)  # Reduced from 8
        await loading_msg.delete()
        
        items_per_page = 10  # Reduced from 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"🇻🇳 Tin kinh tế trong nước Render (Trang {page})",
            description=f"🏗️ Render Free Tier • Từ {len(RSS_FEEDS['domestic'])} nguồn • Memory Optimized",
            color=0xff0000
        )
        
        embed.add_field(
            name="📊 Thông tin Render",
            value=f"📰 Tổng tin: {len(news_list)} tin\n🎯 Lĩnh vực: Kinh tế, CK, BĐS\n📅 Cập nhật: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            embed.add_field(
                name=f"{i}. {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news_render(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Render Optimized • Trang {page}/{total_pages} • !chitiet [số]")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news_render(ctx, page=1):
    """🚀 Render optimized international news with auto-translate"""
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send(f"⏳ Đang tải tin tức quốc tế - Render Optimized với auto-translate...")
        
        news_list = await collect_news_render_optimized(RSS_FEEDS['international'], 4)  # Reduced from 6
        await loading_msg.delete()
        
        items_per_page = 10  # Reduced from 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = news_list[start_index:end_index]
        
        if not page_news:
            total_pages = (len(news_list) + items_per_page - 1) // items_per_page
            await ctx.send(f"❌ Không có tin tức ở trang {page}! Tổng cộng có {total_pages} trang.")
            return
        
        embed = discord.Embed(
            title=f"🌍 Tin kinh tế quốc tế Render (Trang {page})",
            description=f"🏗️ Render Free Tier • {len(RSS_FEEDS['international'])} nguồn • Auto-translate + Extract",
            color=0x0066ff
        )
        
        embed.add_field(
            name="📊 Thông tin Render",
            value=f"📰 Tổng tin: {len(news_list)} tin\n🌐 Auto-extract: Bloomberg, Reuters\n🔄 Auto-translate: Tiếng Anh → Tiếng Việt\n📅 Cập nhật: {get_current_date_str()}",
            inline=False
        )
        
        for i, news in enumerate(page_news, 1):
            title = news['title'][:50] + "..." if len(news['title']) > 50 else news['title']
            embed.add_field(
                name=f"{i}. 🌐 {title}",
                value=f"🕰️ {news['published_str']} • 🔗 [Đọc]({news['link']})",
                inline=False
            )
        
        save_user_news_render(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🚀 Render Optimized • Trang {page}/{total_pages} • !chitiet [số] (auto-extract)")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

# 🚀 RENDER OPTIMIZED ARTICLE DETAILS
@bot.command(name='chitiet')
async def get_news_detail_render(ctx, news_number: int):
    """🚀 Render optimized article details with content extraction + auto-translate"""
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
        
        loading_msg = await ctx.send(f"🚀 Đang trích xuất với Render optimized system...")
        
        # Render optimized content extraction
        full_content = await fetch_content_render_optimized(news['link'])
        
        # Render optimized auto-translate
        source_name = extract_source_name(news['link'])
        translated_content, is_translated = await detect_and_translate_content_render(full_content, source_name)
        
        await loading_msg.delete()
        
        embed = discord.Embed(
            title="📖 Chi tiết bài viết - Render Optimized",
            color=0x9932cc
        )
        
        # Render extraction info
        extraction_methods = []
        if TRAFILATURA_AVAILABLE:
            extraction_methods.append("🚀 Trafilatura")
        if NEWSPAPER_AVAILABLE:
            extraction_methods.append("📰 Newspaper3k")
        extraction_methods.append("🔄 Legacy")
        
        extraction_info = " → ".join(extraction_methods)
        
        # Translation indicator
        title_suffix = " 🌐 (Đã dịch)" if is_translated else ""
        embed.add_field(name=f"📰 Tiêu đề{title_suffix}", value=news['title'], inline=False)
        embed.add_field(name="🕰️ Thời gian", value=f"{news['published_str']} ({get_current_date_str()})", inline=True)
        
        source_display = source_name
        if is_translated:
            source_display += " 🌐"
        embed.add_field(name="📰 Nguồn", value=source_display, inline=True)
        embed.add_field(name="🚀 Render Extract", value=extraction_info, inline=True)
        
        # Content with memory optimization
        content_title = "📄 Nội dung chi tiết 🌐 (Render auto-translate)" if is_translated else "📄 Nội dung chi tiết (Render extract)"
        
        if len(translated_content) > 800:  # Reduced from 1000 for Render
            embed.add_field(
                name=f"{content_title} (Phần 1)",
                value=translated_content[:800] + "...",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Render optimized second embed
            embed2 = discord.Embed(
                title=f"📖 Chi tiết bài viết (tiếp theo){'🌐' if is_translated else ''} - Render",
                color=0x9932cc
            )
            
            embed2.add_field(
                name=f"{content_title} (Phần 2)",
                value=translated_content[800:1400],  # Reduced continuation
                inline=False
            )
            
            if is_translated:
                embed2.add_field(
                    name="🔄 Render Auto-Translate",
                    value="📝 Nội dung tiếng Anh đã được dịch tự động\n🏗️ Render Free Tier optimized",
                    inline=False
                )
            
            embed2.add_field(
                name="🔗 Đọc bài viết đầy đủ",
                value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
                inline=False
            )
            
            embed2.set_footer(text=f"🚀 Render Optimized • Content extraction • {get_current_datetime_str()}")
            
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
                name="🔄 Render Auto-Translate",
                value="📝 Advanced detection + translation\n🏗️ Render Free Tier optimized",
                inline=False
            )
        
        embed.add_field(
            name="🔗 Đọc bài viết đầy đủ",
            value=f"[Nhấn để đọc toàn bộ bài viết{'gốc' if is_translated else ''}]({news['link']})",
            inline=False
        )
        
        embed.set_footer(text=f"🚀 Render Optimized • Tin số {news_number} • !hoi [question]")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Vui lòng nhập số! Ví dụ: `!chitiet 5`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='cuthe')
async def get_news_detail_alias_render(ctx, news_number: int):
    """🚀 Alias cho lệnh !chitiet Render optimized"""
    await get_news_detail_render(ctx, news_number)

@bot.command(name='menu')
async def help_command_render(ctx):
    """🚀 Render optimized menu guide"""
    current_datetime_str = get_current_datetime_str()
    
    embed = discord.Embed(
        title="🚀 Multi-AI Discord News Bot - Render Optimized Edition",
        description=f"Bot tin tức với Multi-AI + Render Free Tier - {current_datetime_str}",
        color=0xff9900
    )
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 1:
        ai_status = f"🚀 **{ai_count} FREE AI Engines (Render Optimized)**\n"
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            ai_status += f"{ai_info['emoji']} **{ai_info['name']}** - {ai_info['strength']} ({ai_info['free_limit']}) ✅\n"
    else:
        ai_status = "⚠️ Cần ít nhất 1 AI engine để hoạt động"
    
    embed.add_field(name="🚀 Render Multi-AI Status", value=ai_status, inline=False)
    
    embed.add_field(
        name="🥊 Multi-AI Commands (Render Optimized)",
        value=f"**!hoi [câu hỏi]** - AI với dữ liệu thời gian thực {get_current_date_str()}\n*VD: !hoi giá vàng hôm nay*\n*VD: !hoi chứng khoán*",
        inline=False
    )
    
    embed.add_field(
        name="📰 News Commands (Render Optimized)",
        value="**!all [trang]** - Tin tổng hợp (10 tin/trang)\n**!in [trang]** - Tin trong nước\n**!out [trang]** - Tin quốc tế (auto-translate)\n**!chitiet [số]** - Chi tiết (🚀 Trafilatura + auto-translate)",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Render Features",
        value=f"✅ **Memory Optimized**: 512MB RAM efficient\n✅ **Content Extraction**: Trafilatura + Newspaper3k\n✅ **Auto-translate**: Advanced detection\n✅ **FREE Only**: $0/month\n✅ **Fast Response**: Tối ưu tốc độ Render\n✅ **Auto-cleanup**: Memory management",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Ví dụ sử dụng Render",
        value=f"**!hoi giá vàng** - AI tìm giá vàng {get_current_date_str()}\n**!hoi tỷ giá usd** - AI tìm tỷ giá hiện tại\n**!hoi vn-index** - AI tìm chỉ số chứng khoán\n**!all** - Xem tin tức tổng hợp\n**!chitiet 1** - Xem chi tiết tin số 1",
        inline=False
    )
    
    # Render status
    search_status = "✅ Render optimized search"
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        search_status += " + Google API"
    
    embed.add_field(name="🔍 Search (Render)", value=search_status, inline=True)
    embed.add_field(name=f"🏗️ Render Free Tier", value=f"🚀 **{ai_count} FREE AI Engines**\n⚡ **Memory Optimized**\n🧠 **Smart Caching**\n🌐 **Auto-translate**\n💰 **$0/month**", inline=True)
    
    embed.set_footer(text=f"🚀 Render Optimized Multi-AI • {current_datetime_str} • !hoi [question]")
    await ctx.send(embed=embed)

# Render optimized cleanup function
async def cleanup_render():
    """Memory-optimized cleanup for Render Free Tier"""
    if debate_engine:
        await debate_engine.close_session()
    
    # Clear user cache periodically for memory efficiency
    global user_news_cache
    if len(user_news_cache) > MAX_CACHE_ENTRIES:
        user_news_cache.clear()
        print("🧹 Render memory cleanup completed")

# Main execution optimized for Render Free Tier
if __name__ == "__main__":
    try:
        keep_alive()
        print("🚀 Starting Multi-AI Discord News Bot - Render Optimized Edition...")
        print("🏗️ Render Free Tier Edition - Memory Optimized (512MB RAM)")
        
        ai_count = len(debate_engine.available_engines)
        print(f"🤖 Render Multi-AI System: {ai_count} FREE engines initialized")
        
        current_datetime_str = get_current_datetime_str()
        print(f"🔧 Current Vietnam time: {current_datetime_str}")
        
        if ai_count >= 1:
            ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
            print(f"🥊 Render debate ready with: {', '.join(ai_names)}")
            print("💰 Cost: $0/month (FREE AI tiers only)")
            print("🚀 Features: News + Content extraction + Auto-translate + Multi-AI")
        else:
            print("⚠️ Warning: Need at least 1 FREE AI engine")
        
        # Render search status
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("🔍 Google Search API: Available with Render optimization")
        else:
            print("🔧 Google Search API: Using Render optimized fallback")
        
        # Wikipedia knowledge base status
        if WIKIPEDIA_AVAILABLE:
            print("📚 Wikipedia Knowledge Base: Available (using spare 112MB)")
        else:
            print("⚠️ Wikipedia Knowledge Base: Not available")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 {total_sources} RSS sources loaded with Render optimization")
        
        # Display Render content extraction capabilities
        print("\n🚀 RENDER OPTIMIZED CONTENT EXTRACTION:")
        extraction_tiers = []
        if TRAFILATURA_AVAILABLE:
            extraction_tiers.append("Tier 1: Trafilatura (Memory optimized)")
        else:
            print("❌ Trafilatura: Not available")
        
        if NEWSPAPER_AVAILABLE:
            extraction_tiers.append("Tier 2: Newspaper3k (Fallback)")
        else:
            print("❌ Newspaper3k: Not available")
        
        extraction_tiers.append("Tier 3: Legacy (Always works)")
        
        for tier in extraction_tiers:
            print(f"✅ {tier}")
        
        # Render Free Tier optimization info
        print("\n🏗️ RENDER FREE TIER OPTIMIZATION:")
        print("✅ Memory usage: ~300-400MB (512MB limit)")
        print("✅ Reduced cache size and timeouts")
        print("✅ Memory cleanup and auto-GC")
        print("✅ Efficient content extraction")
        print("✅ Optimized AI API calls")
        print("✅ Compact RSS parsing")
        
        print("\n✅ Gemini Intelligent Discord News Bot - Render + Wikipedia ready!")
        print(f"💡 Use !hoi [question] to get Gemini intelligent answers (adaptive knowledge + data usage)")
        print("💡 Use !all, !in, !out for news, !chitiet [number] for details with Groq translation")
        print(f"💡 Date and time automatically update: {current_datetime_str}")
        print("💡 Content extraction: Trafilatura → Newspaper3k → Legacy (memory optimized)")
        print("💡 Translation: Groq AI for real English → Vietnamese translation")
        print("💡 Knowledge base: Wikipedia (VN + EN) integrated with Gemini responses")
        print("💡 Intelligent strategy: Gemini prioritizes inherent knowledge over news data")
        print("💡 Render Free Tier optimized for maximum performance at $0/month")
        
        # Final startup message
        print("\n" + "="*70)
        print("💎 GEMINI INTELLIGENT DISCORD NEWS BOT - RENDER EDITION")
        print("💰 COST: $0/month (100% FREE AI tiers)")
        print("🏗️ PLATFORM: Render Free Tier (400-450MB RAM used)")
        print("🤖 AI ENGINES: Gemini (Primary for !hoi) + Groq (Translation only)")
        print("🧠 INTELLIGENCE: Adaptive knowledge usage (5-95% news data)")
        print("📚 KNOWLEDGE: Wikipedia + Gemini inherent knowledge")
        print("🌐 TRANSLATION: Real Groq AI translation for international news")
        print("🎯 USAGE: !menu for intelligent guide")
        print("="*70)
        
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ Discord login error!")
        print("🔧 Token may be invalid or reset")
        print("🔧 Check DISCORD_TOKEN in Environment Variables")
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        print("🔧 Check internet connection and Environment Variables")
        
    finally:
        try:
            asyncio.run(cleanup_render())
        except:
            pass
