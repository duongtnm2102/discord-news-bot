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
from keep_alive import keep_alive
import google.generativeai as genai
from enum import Enum

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
    print("❌ DISCORD_TOKEN không được tìm thấy!")
    exit(1)

# 🇻🇳 TIMEZONE VIỆT NAM
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')
UTC_TIMEZONE = pytz.UTC

# Lưu trữ tin tức theo từng user
user_news_cache = {}

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

# Existing RSS feeds and other functions remain the same...
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
    }
}

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
        await processing_msg.edit(content="🤖 AI đang phân tích và tạo câu trả lời...")
        
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
**!all [trang]** - Tin từ tất cả nguồn
**!in [trang]** - Tin trong nước  
**!out [trang]** - Tin quốc tế
**!chitiet [số]** - Xem nội dung chi tiết
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
        name="🎯 Tính năng mới",
        value="""
✅ **Multi-AI Engine** - Tự động fallback
✅ **Generic Search** - Không cần config từng keyword  
✅ **Real-time Data** - Dữ liệu cập nhật liên tục
✅ **Response Validation** - Đảm bảo chất lượng
✅ **Full Content Extract** - Phân tích sâu
        """,
        inline=False
    )
    
    embed.set_footer(text="🚀 Multi-AI Engine • Generic Search • Real-time Analysis")
    await ctx.send(embed=embed)

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
    
    print('🎯 Gõ !menu để xem hướng dẫn')
    
    # Set bot status
    status_text = f"Multi-AI Engine • {ai_manager.primary_ai.value.upper() if ai_manager.primary_ai else 'No AI'} • !menu"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

# Placeholder functions (implement based on existing code)
async def fetch_full_content_improved(url):
    """Implement existing fetch_full_content_improved function"""
    # Use existing implementation from your code
    pass

# Additional RSS and content functions remain the same...
# [Include all other existing functions like collect_news_from_sources, etc.]

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()
        print("🚀 Starting Multi-AI Discord News Bot...")
        
        if not TOKEN:
            print("❌ DISCORD_TOKEN required!")
            exit(1)
        
        print("✅ Bot ready with Multi-AI Engine support!")
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        input("Press Enter to exit...")
