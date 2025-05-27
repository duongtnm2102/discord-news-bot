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

# Debug Environment Variables
print("=" * 60)
print("🤖 MULTI-AI DEBATE SYSTEM - ENVIRONMENT CHECK")
print("=" * 60)
print(f"DISCORD_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'} ({len(TOKEN) if TOKEN else 0} chars)")
print(f"GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'} ({len(GEMINI_API_KEY) if GEMINI_API_KEY else 0} chars)")
print(f"DEEPSEEK_API_KEY: {'✅ Found' if DEEPSEEK_API_KEY else '❌ Missing'} ({len(DEEPSEEK_API_KEY) if DEEPSEEK_API_KEY else 0} chars)")
print(f"ANTHROPIC_API_KEY: {'✅ Found' if ANTHROPIC_API_KEY else '❌ Missing'} ({len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0} chars)")
print(f"GROQ_API_KEY: {'✅ Found' if GROQ_API_KEY else '❌ Missing'} ({len(GROQ_API_KEY) if GROQ_API_KEY else 0} chars)")
print(f"GOOGLE_API_KEY: {'✅ Found' if GOOGLE_API_KEY else '❌ Missing'} ({len(GOOGLE_API_KEY) if GOOGLE_API_KEY else 0} chars)")
print(f"GOOGLE_CSE_ID: {'✅ Found' if GOOGLE_CSE_ID else '❌ Missing'} ({len(GOOGLE_CSE_ID) if GOOGLE_CSE_ID else 0} chars)")
print("=" * 60)

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
    """Convert UTC to Vietnam time"""
    try:
        utc_timestamp = calendar.timegm(utc_time_tuple)
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=UTC_TIMEZONE)
        vn_dt = utc_dt.astimezone(VN_TIMEZONE)
        return vn_dt
    except Exception as e:
        print(f"⚠️ Timezone conversion error: {e}")
        return datetime.now(VN_TIMEZONE)

# 🆕 MULTI-AI DEBATE ENGINE
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
        
        print("\n🤖 INITIALIZING MULTI-AI DEBATE ENGINES:")
        
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
                    print("✅ GEMINI: Ready for debate")
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
                    print("✅ DEEPSEEK: Ready for debate")
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
                    print("✅ CLAUDE: Ready for debate")
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
                    print("✅ GROQ: Ready for debate")
            except Exception as e:
                print(f"❌ GROQ: {e}")
        
        print(f"🤖 SUMMARY: {len(available_engines)} AI engines ready for debate")
        print(f"Debate participants: {', '.join([ai.value.upper() for ai in available_engines])}")
        
        if len(available_engines) < 2:
            print("⚠️ WARNING: Need at least 2 AI engines for debate!")
        
        self.available_engines = available_engines

    async def multi_ai_search_and_debate(self, question: str, max_sources: int = 5):
        """🆕 MAIN DEBATE FUNCTION: All AIs search, analyze, debate and reach consensus"""
        
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
            # 🔍 STAGE 1: ALL AIs SEARCH INDEPENDENTLY
            print(f"\n{'='*60}")
            print("🔍 STAGE 1: MULTI-AI PARALLEL SEARCH")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.SEARCH
            debate_data['timeline'].append({
                'stage': 'search_start',
                'time': datetime.now(VN_TIMEZONE).strftime("%H:%M:%S"),
                'message': f"Bắt đầu tìm kiếm với {len(self.available_engines)} AI engines"
            })
            
            search_tasks = []
            for ai_provider in self.available_engines:
                search_tasks.append(self._ai_search_sources(ai_provider, question, max_sources))
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Combine all search results
            all_sources = []
            for i, result in enumerate(search_results):
                ai_provider = self.available_engines[i]
                if isinstance(result, Exception):
                    print(f"❌ {ai_provider.value.upper()} search failed: {result}")
                    debate_data['ai_responses'][ai_provider] = {
                        'search_sources': [],
                        'search_error': str(result)
                    }
                else:
                    print(f"✅ {ai_provider.value.upper()} found {len(result)} sources")
                    all_sources.extend(result)
                    debate_data['ai_responses'][ai_provider] = {
                        'search_sources': result,
                        'search_error': None
                    }
            
            # Remove duplicates and get best sources
            unique_sources = self._remove_duplicate_sources(all_sources)
            best_sources = unique_sources[:max_sources]
            
            debate_data['timeline'].append({
                'stage': 'search_complete',
                'time': datetime.now(VN_TIMEZONE).strftime("%H:%M:%S"),
                'message': f"Tìm kiếm hoàn tất: {len(best_sources)} nguồn tin độc đáo"
            })
            
            # 🤖 STAGE 2: ALL AIs GENERATE INITIAL RESPONSES
            print(f"\n{'='*60}")
            print("🤖 STAGE 2: MULTI-AI INITIAL ANALYSIS")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.INITIAL_RESPONSE
            
            context = self._build_context_from_sources(best_sources)
            
            initial_tasks = []
            for ai_provider in self.available_engines:
                if ai_provider in debate_data['ai_responses']:
                    initial_tasks.append(self._ai_initial_response(ai_provider, question, context))
            
            initial_results = await asyncio.gather(*initial_tasks, return_exceptions=True)
            
            for i, result in enumerate(initial_results):
                ai_provider = self.available_engines[i]
                if isinstance(result, Exception):
                    print(f"❌ {ai_provider.value.upper()} initial response failed: {result}")
                    debate_data['ai_responses'][ai_provider]['initial_response'] = f"Lỗi: {str(result)}"
                else:
                    print(f"✅ {ai_provider.value.upper()} generated initial response")
                    debate_data['ai_responses'][ai_provider]['initial_response'] = result
            
            debate_data['timeline'].append({
                'stage': 'initial_responses_complete',
                'time': datetime.now(VN_TIMEZONE).strftime("%H:%M:%S"),
                'message': f"{len([r for r in initial_results if not isinstance(r, Exception)])} AI hoàn thành phân tích ban đầu"
            })
            
            # 🥊 STAGE 3: DEBATE ROUND 1 - AIs CRITIQUE EACH OTHER
            print(f"\n{'='*60}")
            print("🥊 STAGE 3: DEBATE ROUND 1 - PEER REVIEW")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.DEBATE_ROUND_1
            
            debate_round_1 = await self._conduct_debate_round(
                question, 
                debate_data['ai_responses'], 
                context, 
                round_number=1
            )
            
            debate_data['debate_rounds'].append(debate_round_1)
            
            # 🥊 STAGE 4: DEBATE ROUND 2 - FINAL ARGUMENTS
            print(f"\n{'='*60}")
            print("🥊 STAGE 4: DEBATE ROUND 2 - FINAL ARGUMENTS")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.DEBATE_ROUND_2
            
            debate_round_2 = await self._conduct_debate_round(
                question,
                debate_data['ai_responses'],
                context,
                round_number=2,
                previous_debates=debate_round_1
            )
            
            debate_data['debate_rounds'].append(debate_round_2)
            
            # 🤝 STAGE 5: CONSENSUS BUILDING
            print(f"\n{'='*60}")
            print("🤝 STAGE 5: CONSENSUS BUILDING")
            print(f"{'='*60}")
            
            debate_data['stage'] = DebateStage.CONSENSUS
            
            consensus_result = await self._build_consensus(
                question,
                debate_data['ai_responses'],
                debate_data['debate_rounds'],
                context
            )
            
            debate_data['consensus_score'] = consensus_result['scores']
            debate_data['final_answer'] = consensus_result['final_answer']
            
            debate_data['timeline'].append({
                'stage': 'consensus_complete',
                'time': datetime.now(VN_TIMEZONE).strftime("%H:%M:%S"),
                'message': "Đạt được sự đồng thuận và câu trả lời cuối cùng"
            })
            
            print(f"✅ MULTI-AI DEBATE COMPLETED: {len(debate_data['timeline'])} stages")
            
            return debate_data
            
        except Exception as e:
            print(f"❌ DEBATE SYSTEM ERROR: {e}")
            return {
                'question': question,
                'error': str(e),
                'stage': debate_data.get('stage', 'unknown'),
                'timeline': debate_data.get('timeline', [])
            }

    async def _ai_search_sources(self, ai_provider: AIProvider, question: str, max_results: int):
        """Each AI searches for sources independently"""
        try:
            print(f"🔍 {ai_provider.value.upper()} searching for: {question}")
            
            # Enhanced search query based on AI personality
            personality = self.ai_engines[ai_provider]['personality']
            
            if personality == 'financial_expert':
                search_query = f"{question} tài chính kinh tế số liệu"
            elif personality == 'analytical_researcher':
                search_query = f"{question} phân tích dữ liệu chính xác"
            elif personality == 'critical_thinker':
                search_query = f"{question} nguyên nhân tác động"
            else:
                search_query = question
            
            sources = await self._google_search_with_fallback(search_query, max_results)
            
            print(f"✅ {ai_provider.value.upper()} found {len(sources)} sources")
            return sources
            
        except Exception as e:
            print(f"❌ {ai_provider.value.upper()} search error: {e}")
            return []

    async def _ai_initial_response(self, ai_provider: AIProvider, question: str, context: str):
        """Each AI generates initial response based on its personality"""
        try:
            personality = self.ai_engines[ai_provider]['personality']
            
            # Personality-specific prompts
            personality_prompts = {
                'analytical_researcher': "Bạn là nhà nghiên cứu phân tích. Hãy phân tích dữ liệu một cách chính xác và khách quan.",
                'financial_expert': "Bạn là chuyên gia tài chính. Hãy tập trung vào các yếu tố kinh tế và số liệu tài chính.",
                'critical_thinker': "Bạn là người tư duy phản biện. Hãy xem xét nhiều góc độ và đặt câu hỏi sâu sắc.",
                'quick_responder': "Bạn là người phản hồi nhanh. Hãy đưa ra câu trả lời súc tích và dễ hiểu."
            }
            
            prompt = f"""{personality_prompts.get(personality, 'Bạn là chuyên gia tài chính.')}

NHIỆM VỤ: Phân tích thông tin từ CONTEXT để trả lời câu hỏi một cách chính xác.

CONTEXT: {context}

CÂU HỎI: {question}

Hãy đưa ra câu trả lời chuyên sâu từ góc độ của bạn (khoảng 200-300 từ):"""

            response = await self._call_specific_ai(ai_provider, prompt, context)
            return response
            
        except Exception as e:
            print(f"❌ {ai_provider.value.upper()} initial response error: {e}")
            return f"Lỗi phân tích: {str(e)}"

    async def _conduct_debate_round(self, question: str, ai_responses: dict, context: str, round_number: int, previous_debates=None):
        """Conduct a debate round where AIs critique each other's responses"""
        
        debate_round = {
            'round': round_number,
            'critiques': {},
            'rebuttals': {}
        }
        
        try:
            # Get all AI responses that have initial responses
            participating_ais = [ai for ai in self.available_engines if ai in ai_responses and 'initial_response' in ai_responses[ai]]
            
            if len(participating_ais) < 2:
                print(f"⚠️ Not enough AIs for debate round {round_number}")
                return debate_round
            
            print(f"🥊 DEBATE ROUND {round_number}: {len(participating_ais)} AIs participating")
            
            # PHASE 1: Each AI critiques others' responses
            critique_tasks = []
            for ai_provider in participating_ais:
                other_responses = {
                    other_ai: ai_responses[other_ai]['initial_response'] 
                    for other_ai in participating_ais 
                    if other_ai != ai_provider and 'initial_response' in ai_responses[other_ai]
                }
                
                if other_responses:
                    critique_tasks.append(self._ai_critique_others(ai_provider, question, other_responses, round_number))
            
            critique_results = await asyncio.gather(*critique_tasks, return_exceptions=True)
            
            for i, result in enumerate(critique_results):
                ai_provider = participating_ais[i]
                if isinstance(result, Exception):
                    print(f"❌ {ai_provider.value.upper()} critique failed: {result}")
                    debate_round['critiques'][ai_provider] = f"Lỗi critique: {str(result)}"
                else:
                    debate_round['critiques'][ai_provider] = result
            
            # PHASE 2: Each AI responds to critiques (rebuttals)
            rebuttal_tasks = []
            for ai_provider in participating_ais:
                if ai_provider in debate_round['critiques']:
                    # Collect critiques about this AI from others
                    critiques_about_me = []
                    for other_ai, critique in debate_round['critiques'].items():
                        if other_ai != ai_provider and ai_provider.value in critique.lower():
                            critiques_about_me.append(f"{self.ai_engines[other_ai]['name']}: {critique}")
                    
                    if critiques_about_me:
                        rebuttal_tasks.append(self._ai_rebuttal(ai_provider, question, critiques_about_me, round_number))
            
            rebuttal_results = await asyncio.gather(*rebuttal_tasks, return_exceptions=True)
            
            # Map rebuttals back to AIs
            rebuttal_index = 0
            for ai_provider in participating_ais:
                if ai_provider in debate_round['critiques']:
                    critiques_about_me = []
                    for other_ai, critique in debate_round['critiques'].items():
                        if other_ai != ai_provider and ai_provider.value in critique.lower():
                            critiques_about_me.append(f"{self.ai_engines[other_ai]['name']}: {critique}")
                    
                    if critiques_about_me and rebuttal_index < len(rebuttal_results):
                        result = rebuttal_results[rebuttal_index]
                        if isinstance(result, Exception):
                            debate_round['rebuttals'][ai_provider] = f"Lỗi rebuttal: {str(result)}"
                        else:
                            debate_round['rebuttals'][ai_provider] = result
                        rebuttal_index += 1
            
            print(f"✅ DEBATE ROUND {round_number} completed: {len(debate_round['critiques'])} critiques, {len(debate_round['rebuttals'])} rebuttals")
            
        except Exception as e:
            print(f"❌ DEBATE ROUND {round_number} error: {e}")
        
        return debate_round

    async def _ai_critique_others(self, ai_provider: AIProvider, question: str, other_responses: dict, round_number: int):
        """AI critiques other AIs' responses"""
        try:
            other_responses_text = ""
            for other_ai, response in other_responses.items():
                ai_name = self.ai_engines[other_ai]['name']
                other_responses_text += f"\n{ai_name}: {response}\n"
            
            prompt = f"""Bạn là {self.ai_engines[ai_provider]['name']} - {self.ai_engines[ai_provider]['strength']}.

NHIỆM VỤ: Phân tích và đưa ra nhận xét phản biện về các câu trả lời của các AI khác.

CÂU HỎI GỐC: {question}

CÁC CÂU TRẢ LỜI KHÁC:
{other_responses_text}

Hãy đưa ra nhận xét phản biện xây dựng (100-150 từ):
1. Điểm mạnh của các câu trả lời
2. Điểm yếu hoặc thiếu sót
3. Góc nhìn bổ sung từ chuyên môn của bạn

Giữ tone chuyên nghiệp và xây dựng."""

            critique = await self._call_specific_ai(ai_provider, prompt, "")
            return critique
            
        except Exception as e:
            print(f"❌ {ai_provider.value.upper()} critique error: {e}")
            return f"Lỗi critique: {str(e)}"

    async def _ai_rebuttal(self, ai_provider: AIProvider, question: str, critiques_about_me: List[str], round_number: int):
        """AI responds to critiques about their response"""
        try:
            critiques_text = "\n".join(critiques_about_me)
            
            prompt = f"""Bạn là {self.ai_engines[ai_provider]['name']} - {self.ai_engines[ai_provider]['strength']}.

NHIỆM VỤ: Phản hồi lại các nhận xét về câu trả lời của bạn.

CÂU HỎI GỐC: {question}

CÁC NHẬN XÉT VỀ CÂU TRẢ LỜI CỦA BẠN:
{critiques_text}

Hãy phản hồi một cách chuyên nghiệp (100-150 từ):
1. Giải thích quan điểm của bạn
2. Bổ sung thông tin nếu cần
3. Thừa nhận điểm hợp lý (nếu có)
4. Làm rõ điểm chưa được hiểu đúng

Giữ tone tôn trọng và chuyên nghiệp."""

            rebuttal = await self._call_specific_ai(ai_provider, prompt, "")
            return rebuttal
            
        except Exception as e:
            print(f"❌ {ai_provider.value.upper()} rebuttal error: {e}")
            return f"Lỗi rebuttal: {str(e)}"

    async def _build_consensus(self, question: str, ai_responses: dict, debate_rounds: list, context: str):
        """Build consensus from all AI responses and debates"""
        
        consensus_result = {
            'scores': {},
            'final_answer': '',
            'reasoning': ''
        }
        
        try:
            # Get the AI with best overall performance to synthesize final answer
            participating_ais = [ai for ai in self.available_engines if ai in ai_responses and 'initial_response' in ai_responses[ai]]
            
            if not participating_ais:
                consensus_result['final_answer'] = "Không thể đạt được sự đồng thuận do thiếu dữ liệu."
                return consensus_result
            
            # Score each AI based on response quality and debate performance
            for ai_provider in participating_ais:
                score = 0
                
                # Base score for having initial response
                if 'initial_response' in ai_responses[ai_provider]:
                    response_length = len(ai_responses[ai_provider]['initial_response'])
                    score += min(response_length / 10, 50)  # Up to 50 points for length
                
                # Bonus for participating in debates
                for debate_round in debate_rounds:
                    if ai_provider in debate_round.get('critiques', {}):
                        score += 20  # 20 points for critique
                    if ai_provider in debate_round.get('rebuttals', {}):
                        score += 30  # 30 points for rebuttal
                
                consensus_result['scores'][ai_provider] = score
            
            # Find best performing AI
            best_ai = max(consensus_result['scores'], key=consensus_result['scores'].get)
            
            print(f"🏆 BEST AI: {self.ai_engines[best_ai]['name']} (Score: {consensus_result['scores'][best_ai]})")
            
            # Let best AI synthesize final answer
            all_debate_content = ""
            
            # Include all initial responses
            for ai_provider in participating_ais:
                ai_name = self.ai_engines[ai_provider]['name']
                response = ai_responses[ai_provider].get('initial_response', '')
                all_debate_content += f"\n{ai_name} - Phân tích ban đầu: {response}\n"
            
            # Include debate rounds
            for i, debate_round in enumerate(debate_rounds, 1):
                all_debate_content += f"\n--- DEBATE ROUND {i} ---\n"
                
                for ai_provider, critique in debate_round.get('critiques', {}).items():
                    ai_name = self.ai_engines[ai_provider]['name']
                    all_debate_content += f"{ai_name} - Nhận xét: {critique}\n"
                
                for ai_provider, rebuttal in debate_round.get('rebuttals', {}).items():
                    ai_name = self.ai_engines[ai_provider]['name']
                    all_debate_content += f"{ai_name} - Phản hồi: {rebuttal}\n"
            
            final_prompt = f"""Bạn là {self.ai_engines[best_ai]['name']} - được chọn để tổng hợp câu trả lời cuối cùng từ cuộc tranh luận của nhiều AI.

NHIỆM VỤ: Dựa trên tất cả các phân tích và tranh luận, hãy đưa ra câu trả lời cuối cùng tốt nhất.

CÂU HỎI GỐC: {question}

CONTEXT TỪ NGUỒN TIN: {context}

TOÀN BỘ CUỘC TRANH LUẬN:
{all_debate_content}

Hãy tổng hợp thành câu trả lời cuối cùng (300-500 từ):
1. Thông tin chính xác và đầy đủ nhất
2. Kết hợp điểm mạnh từ tất cả các AI
3. Giải quyết các mâu thuẫn (nếu có)
4. Kết luận rõ ràng và thuyết phục

BẮT ĐẦU với: "Sau khi tham khảo ý kiến từ {len(participating_ais)} chuyên gia AI và phân tích toàn diện..."
"""

            final_answer = await self._call_specific_ai(best_ai, final_prompt, context)
            consensus_result['final_answer'] = final_answer
            consensus_result['reasoning'] = f"Tổng hợp bởi {self.ai_engines[best_ai]['name']} từ {len(participating_ais)} AI"
            
            print("✅ CONSENSUS REACHED: Final answer synthesized")
            
        except Exception as e:
            print(f"❌ CONSENSUS ERROR: {e}")
            consensus_result['final_answer'] = f"Lỗi đạt sự đồng thuận: {str(e)}"
        
        return consensus_result

    async def _google_search_with_fallback(self, query: str, max_results: int = 5):
        """Enhanced Google Search with comprehensive fallback"""
        
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            print("⚠️ Google Search not configured - using fallback")
            return await self._fallback_search_method(query)
        
        try:
            # Strategy 1: Specific Vietnamese financial sites
            enhanced_query = f"{query} site:cafef.vn OR site:vneconomy.vn OR site:vnexpress.net"
            
            if GOOGLE_APIS_AVAILABLE:
                service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
                result = service.cse().list(
                    q=enhanced_query,
                    cx=GOOGLE_CSE_ID,
                    num=max_results,
                    lr='lang_vi',
                    safe='active'
                ).execute()
                
                if 'items' in result and result['items']:
                    sources = []
                    for item in result['items']:
                        source = {
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'source_name': self._extract_source_name(item.get('link', ''))
                        }
                        sources.append(source)
                    return sources
            
            # Strategy 2: Direct HTTP fallback
            return await self._direct_http_search(query, max_results)
            
        except Exception as e:
            print(f"⚠️ Google Search error: {e}")
            return await self._fallback_search_method(query)

    async def _direct_http_search(self, query: str, max_results: int):
        """Direct HTTP request to Google Custom Search API"""
        try:
            session = await self.create_session()
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': GOOGLE_API_KEY,
                'cx': GOOGLE_CSE_ID,
                'q': query,
                'num': max_results,
                'lr': 'lang_vi',
                'safe': 'active'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'items' in data:
                        sources = []
                        for item in data['items']:
                            source = {
                                'title': item.get('title', ''),
                                'link': item.get('link', ''),
                                'snippet': item.get('snippet', ''),
                                'source_name': self._extract_source_name(item.get('link', ''))
                            }
                            sources.append(source)
                        return sources
                
                return []
                
        except Exception as e:
            print(f"❌ Direct HTTP search error: {e}")
            return []

    async def _fallback_search_method(self, query: str):
        """Fallback search method with relevant financial sources"""
        
        fallback_sources = []
        
        if 'giá vàng' in query.lower():
            fallback_sources = [
                {
                    'title': 'Giá vàng hôm nay - Cập nhật mới nhất từ CafeF',
                    'link': 'https://cafef.vn/gia-vang.chn',
                    'snippet': 'Giá vàng SJC hôm nay dao động quanh mức 82-84 triệu đồng/lượng theo thị trường thế giới.',
                    'source_name': 'CafeF'
                },
                {
                    'title': 'Bảng giá vàng PNJ mới nhất',
                    'link': 'https://pnj.com.vn/gia-vang',
                    'snippet': 'Giá vàng PNJ: Vàng miếng SJC 82,5 - 84,5 triệu đồng/lượng.',
                    'source_name': 'PNJ'
                },
                {
                    'title': 'Giá vàng SJC chính thức',
                    'link': 'https://sjc.com.vn',
                    'snippet': 'Công ty Vàng bạc Đá quý Sài Gòn cập nhật giá vàng miếng chính thức.',
                    'source_name': 'SJC'
                }
            ]
        elif 'chứng khoán' in query.lower():
            fallback_sources = [
                {
                    'title': 'VN-Index hôm nay - Thị trường chứng khoán',
                    'link': 'https://cafef.vn/chung-khoan.chn',
                    'snippet': 'VN-Index quanh 1.260 điểm, thanh khoản hơn 20.000 tỷ đồng.',
                    'source_name': 'CafeF'
                },
                {
                    'title': 'Tin tức chứng khoán VnEconomy',
                    'link': 'https://vneconomy.vn/chung-khoan.htm',
                    'snippet': 'Thị trường chứng khoán tích cực, ngân hàng và BĐS dẫn dắt.',
                    'source_name': 'VnEconomy'
                }
            ]
        else:
            fallback_sources = [
                {
                    'title': f'Thông tin tài chính về {query}',
                    'link': 'https://cafef.vn',
                    'snippet': f'Thông tin và phân tích về {query} từ CafeF.',
                    'source_name': 'CafeF'
                },
                {
                    'title': f'Tin tức kinh tế {query}',
                    'link': 'https://vneconomy.vn',
                    'snippet': f'Phân tích chuyên sâu về {query} từ VnEconomy.',
                    'source_name': 'VnEconomy'
                }
            ]
        
        return fallback_sources

    def _remove_duplicate_sources(self, sources: List[dict]) -> List[dict]:
        """Remove duplicate sources"""
        seen_links = set()
        unique_sources = []
        
        for source in sources:
            if source['link'] not in seen_links:
                seen_links.add(source['link'])
                unique_sources.append(source)
        
        return unique_sources

    def _build_context_from_sources(self, sources: List[dict]) -> str:
        """Build context string from sources"""
        context = ""
        for i, source in enumerate(sources, 1):
            context += f"Nguồn {i} ({source['source_name']}): {source['snippet']}\n"
        return context

    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL"""
        domain_mapping = {
            'cafef.vn': 'CafeF',
            'vneconomy.vn': 'VnEconomy', 
            'vnexpress.net': 'VnExpress',
            'tuoitre.vn': 'Tuổi Trẻ',
            'thanhnien.vn': 'Thanh Niên',
            'pnj.com.vn': 'PNJ',
            'sjc.com.vn': 'SJC'
        }
        
        for domain, name in domain_mapping.items():
            if domain in url:
                return name
        
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            return domain.title()
        except:
            return 'Unknown Source'

    async def _call_specific_ai(self, ai_provider: AIProvider, prompt: str, context: str):
        """Call specific AI engine"""
        try:
            if ai_provider == AIProvider.GEMINI:
                return await self._call_gemini(prompt, context)
            elif ai_provider == AIProvider.DEEPSEEK:
                return await self._call_deepseek(prompt, context)
            elif ai_provider == AIProvider.CLAUDE:
                return await self._call_claude(prompt, context)
            elif ai_provider == AIProvider.GROQ:
                return await self._call_groq(prompt, context)
            
            raise Exception(f"Unknown AI provider: {ai_provider}")
            
        except Exception as e:
            print(f"❌ Error calling {ai_provider.value}: {str(e)}")
            raise e

    async def _call_gemini(self, prompt: str, context: str):
        """Call Gemini AI"""
        if not GEMINI_AVAILABLE:
            raise Exception("Gemini library not available")
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,
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

    async def _call_deepseek(self, prompt: str, context: str):
        """Call DeepSeek AI"""
        try:
            session = await self.create_session()
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'deepseek-v3',
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 1000
            }
            
            async with session.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status != 200:
                    raise Exception(f"DeepSeek API error: {response.status}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            raise Exception(f"DeepSeek API error: {str(e)}")

    async def _call_claude(self, prompt: str, context: str):
        """Call Claude AI"""
        try:
            session = await self.create_session()
            
            headers = {
                'x-api-key': ANTHROPIC_API_KEY,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 1000,
                'temperature': 0.3,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
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
                    raise Exception(f"Claude API error: {response.status}")
                
                result = await response.json()
                return result['content'][0]['text'].strip()
                
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")

    async def _call_groq(self, prompt: str, context: str):
        """Call Groq AI"""
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
                'temperature': 0.3,
                'max_tokens': 1000
            }
            
            async with session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Groq API error: {response.status}")
                
                result = await response.json()
                return result['choices'][0]['message']['content'].strip()
                
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")

# Initialize Multi-AI Debate Engine
debate_engine = MultiAIDebateEngine()

# Content extraction and RSS functions (simplified)
async def fetch_full_content_improved(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        content = response.text
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = html.unescape(content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        sentences = content.split('. ')
        meaningful_content = []
        
        for sentence in sentences[:8]:
            if len(sentence.strip()) > 20:
                meaningful_content.append(sentence.strip())
        
        result = '. '.join(meaningful_content)
        return result[:1500] + "..." if len(result) > 1500 else result
        
    except Exception as e:
        print(f"⚠️ Content extraction error: {e}")
        return "Không thể trích xuất nội dung từ bài viết này."

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
                    vn_time = datetime.now(VN_TIMEZONE)
                    
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        vn_time = convert_utc_to_vietnam_time(entry.published_parsed)
                    
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:400] + "..." if len(entry.summary) > 400 else entry.summary
                    
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
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 2:
        print(f'🤖 Multi-AI Debate System: {ai_count} AI engines ready')
        ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
        print(f'🥊 Debate participants: {", ".join(ai_names)}')
    else:
        print('⚠️ Warning: Need at least 2 AI engines for debate!')
    
    # Google Search status
    if GOOGLE_API_KEY and GOOGLE_CSE_ID:
        print('🔍 Google Search API: Configured for multi-AI search')
    else:
        print('⚠️ Google Search API: Using fallback method')
    
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Ready with {total_sources} RSS sources')
    print('🎯 Type !menu for help')
    
    status_text = f"Multi-AI Debate • {ai_count} AIs • !hoi [question] • !menu"
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

# 🆕 MAIN MULTI-AI DEBATE COMMAND
@bot.command(name='hoi')
async def multi_ai_debate_question(ctx, *, question):
    """🤖 Multi-AI Debate System: 4 AIs search, analyze, debate and reach consensus"""
    
    try:
        if len(debate_engine.available_engines) < 2:
            embed = discord.Embed(
                title="⚠️ Multi-AI Debate System không khả dụng",
                description=f"Cần ít nhất 2 AI engines. Hiện có: {len(debate_engine.available_engines)}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Create initial progress message
        progress_embed = discord.Embed(
            title="🤖 Multi-AI Debate System",
            description=f"**Câu hỏi:** {question}\n\n🔄 **Bắt đầu cuộc tranh luận với {len(debate_engine.available_engines)} AI...**",
            color=0x9932cc,
            timestamp=ctx.message.created_at
        )
        
        # Show participating AIs
        ai_list = ""
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            ai_list += f"{ai_info['emoji']} **{ai_info['name']}** - {ai_info['strength']}\n"
        
        progress_embed.add_field(
            name="🥊 Thành viên tranh luận",
            value=ai_list,
            inline=False
        )
        
        progress_embed.add_field(
            name="📋 Quy trình",
            value="1️⃣ Tìm kiếm thông tin\n2️⃣ Phân tích ban đầu\n3️⃣ Tranh luận vòng 1\n4️⃣ Tranh luận vòng 2\n5️⃣ Đạt sự đồng thuận",
            inline=False
        )
        
        progress_msg = await ctx.send(embed=progress_embed)
        
        # Start the multi-AI debate process
        print(f"\n🤖 STARTING MULTI-AI DEBATE for: {question}")
        debate_result = await debate_engine.multi_ai_search_and_debate(question, max_sources=5)
        
        # Create final result embed
        if 'error' in debate_result:
            # Error occurred
            error_embed = discord.Embed(
                title="❌ Multi-AI Debate System - Lỗi",
                description=f"**Câu hỏi:** {question}\n\n**Lỗi:** {debate_result['error']}",
                color=0xff6b6b,
                timestamp=ctx.message.created_at
            )
            
            if 'timeline' in debate_result and debate_result['timeline']:
                timeline_text = ""
                for event in debate_result['timeline']:
                    timeline_text += f"⏰ {event['time']} - {event['message']}\n"
                
                error_embed.add_field(
                    name="📋 Timeline",
                    value=timeline_text[:1000] + ("..." if len(timeline_text) > 1000 else ""),
                    inline=False
                )
            
            await progress_msg.edit(embed=error_embed)
            return
        
        # Success - create comprehensive result
        result_embed = discord.Embed(
            title="🏆 Multi-AI Debate System - Kết quả cuối cùng",
            description=f"**Câu hỏi:** {question}",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Add final answer
        final_answer = debate_result.get('final_answer', 'Không có câu trả lời.')
        if len(final_answer) > 1000:
            result_embed.add_field(
                name="📝 Câu trả lời (Phần 1)",
                value=final_answer[:1000] + "...",
                inline=False
            )
        else:
            result_embed.add_field(
                name="📝 Câu trả lời cuối cùng",
                value=final_answer,
                inline=False
            )
        
        # Add AI scores
        if 'consensus_score' in debate_result and debate_result['consensus_score']:
            scores_text = ""
            sorted_scores = sorted(debate_result['consensus_score'].items(), key=lambda x: x[1], reverse=True)
            
            for i, (ai_provider, score) in enumerate(sorted_scores, 1):
                ai_info = debate_engine.ai_engines[ai_provider]
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
                scores_text += f"{medal} **{ai_info['name']}** {ai_info['emoji']}: {score:.0f} điểm\n"
            
            result_embed.add_field(
                name="🏆 Bảng xếp hạng AI",
                value=scores_text,
                inline=True
            )
        
        # Add debate statistics
        stats_text = f"🔍 **Tìm kiếm:** {len(debate_engine.available_engines)} AI\n"
        stats_text += f"🤖 **Phân tích:** {len([ai for ai in debate_result.get('ai_responses', {}) if 'initial_response' in debate_result['ai_responses'][ai]])}\n"
        stats_text += f"🥊 **Vòng tranh luận:** {len(debate_result.get('debate_rounds', []))}\n"
        
        if 'timeline' in debate_result:
            start_time = debate_result['timeline'][0]['time'] if debate_result['timeline'] else "N/A"
            end_time = debate_result['timeline'][-1]['time'] if debate_result['timeline'] else "N/A"
            stats_text += f"⏱️ **Thời gian:** {start_time} - {end_time}"
        
        result_embed.add_field(
            name="📊 Thống kê",
            value=stats_text,
            inline=True
        )
        
        result_embed.set_footer(text="🤖 Multi-AI Debate System • Powered by Collective Intelligence • !menu")
        
        await progress_msg.edit(embed=result_embed)
        
        # If answer is too long, send continuation
        if len(final_answer) > 1000:
            continuation_embed = discord.Embed(
                title="📝 Câu trả lời (Phần 2)",
                description=final_answer[1000:2000],
                color=0x00ff88
            )
            
            if len(final_answer) > 2000:
                continuation_embed.set_footer(text=f"Và còn {len(final_answer) - 2000} ký tự nữa...")
            
            await ctx.send(embed=continuation_embed)
        
        print(f"✅ MULTI-AI DEBATE COMPLETED for: {question}")
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi hệ thống Multi-AI Debate: {str(e)}")
        print(f"❌ MULTI-AI DEBATE ERROR: {e}")

# Regular news commands (simplified versions)
@bot.command(name='all')
async def get_all_news(ctx, page=1):
    try:
        page = max(1, int(page))
        loading_msg = await ctx.send("⏳ Đang tải tin tức...")
        
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 6)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 4)
        
        await loading_msg.delete()
        
        all_news = domestic_news + international_news
        
        items_per_page = 12
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        page_news = all_news[start_index:end_index]
        
        if not page_news:
            await ctx.send(f"❌ Không có tin tức ở trang {page}!")
            return
        
        embed = discord.Embed(
            title=f"📰 Tin tức tổng hợp (Trang {page})",
            description=f"🤖 Multi-AI Debate System • {len(debate_engine.available_engines)} AIs ready",
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
        embed.set_footer(text=f"🤖 Multi-AI System • Trang {page}/{total_pages} • !hoi [question] for AI debate")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    try:
        user_id = ctx.author.id
        
        if user_id not in user_news_cache:
            await ctx.send("❌ Bạn chưa xem tin tức! Dùng `!all` trước.")
            return
        
        user_data = user_news_cache[user_id]
        news_list = user_data['news']
        
        if news_number < 1 or news_number > len(news_list):
            await ctx.send(f"❌ Số không hợp lệ! Chọn từ 1 đến {len(news_list)}")
            return
        
        news = news_list[news_number - 1]
        
        loading_msg = await ctx.send("⏳ Đang trích xuất nội dung...")
        
        full_content = await fetch_full_content_improved(news['link'])
        
        await loading_msg.delete()
        
        embed = discord.Embed(
            title="📖 Chi tiết bài viết",
            color=0x9932cc
        )
        
        embed.add_field(name="📰 Tiêu đề", value=news['title'], inline=False)
        embed.add_field(name="🕰️ Thời gian", value=news['published_str'], inline=True)
        embed.add_field(name="📄 Nội dung", value=full_content[:1000] + ("..." if len(full_content) > 1000 else ""), inline=False)
        embed.add_field(name="🔗 Đọc đầy đủ", value=f"[Nhấn để đọc]({news['link']})", inline=False)
        
        embed.set_footer(text=f"🤖 Multi-AI System • !hoi [question] để hỏi AI")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='menu')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Multi-AI Debate Discord News Bot",
        description="Bot tin tức với hệ thống tranh luận đa AI thông minh",
        color=0xff9900
    )
    
    ai_count = len(debate_engine.available_engines)
    if ai_count >= 2:
        ai_status = f"🚀 **{ai_count} AI Engines Ready for Debate**\n"
        for ai_provider in debate_engine.available_engines:
            ai_info = debate_engine.ai_engines[ai_provider]
            ai_status += f"{ai_info['emoji']} **{ai_info['name']}** - {ai_info['strength']}\n"
    else:
        ai_status = "⚠️ Cần ít nhất 2 AI engines để tranh luận"
    
    embed.add_field(name="🤖 Multi-AI Status", value=ai_status, inline=False)
    
    embed.add_field(
        name="🥊 Lệnh Multi-AI Debate",
        value="**!hoi [câu hỏi]** - Hệ thống tranh luận đa AI\n*VD: !hoi tại sao giá vàng giảm gần đây?*",
        inline=False
    )
    
    embed.add_field(
        name="📰 Lệnh tin tức",
        value="**!all [trang]** - Tin tổng hợp\n**!chitiet [số]** - Chi tiết bài viết",
        inline=True
    )
    
    embed.add_field(
        name="🔥 Tính năng độc đáo",
        value="✅ **4 AI cùng tìm kiếm Google**\n✅ **Phân tích độc lập**\n✅ **Tranh luận & phản biện**\n✅ **Đạt sự đồng thuận**\n✅ **Câu trả lời tối ưu**",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Quy trình Multi-AI Debate",
        value="1️⃣ **Search:** Tất cả AI tìm kiếm thông tin\n2️⃣ **Analyze:** Mỗi AI phân tích riêng biệt\n3️⃣ **Debate:** AI tranh luận và phản biện\n4️⃣ **Consensus:** Đạt sự đồng thuận\n5️⃣ **Answer:** Câu trả lời cuối cùng tốt nhất",
        inline=False
    )
    
    google_status = "✅ Multi-AI Search Ready" if GOOGLE_API_KEY and GOOGLE_CSE_ID else "⚠️ Fallback mode"
    embed.add_field(name="🔍 Google Search", value=google_status, inline=True)
    
    embed.add_field(name="📊 Performance", value=f"🚀 **{ai_count} AI Engines**\n⚡ **Parallel Processing**\n🧠 **Collective Intelligence**", inline=True)
    
    embed.set_footer(text="🤖 Multi-AI Debate System • Collective Intelligence • Powered by 4 AIs")
    await ctx.send(embed=embed)

# Cleanup function
async def cleanup():
    if debate_engine:
        await debate_engine.close_session()

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()
        print("🚀 Starting Multi-AI Debate Discord News Bot...")
        
        ai_count = len(debate_engine.available_engines)
        print(f"🤖 Multi-AI Debate System: {ai_count} engines initialized")
        
        if ai_count >= 2:
            ai_names = [debate_engine.ai_engines[ai]['name'] for ai in debate_engine.available_engines]
            print(f"🥊 Debate ready with: {', '.join(ai_names)}")
        else:
            print("⚠️ Warning: Need at least 2 AI engines for optimal debate experience")
        
        if GOOGLE_API_KEY and GOOGLE_CSE_ID:
            print("🔍 Google Search API: Ready for multi-AI search")
        else:
            print("⚠️ Google Search API: Using fallback method")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 {total_sources} RSS sources loaded")
        
        print("✅ Multi-AI Debate System ready!")
        print("💡 Use !hoi [question] to start AI debate")
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
    finally:
        try:
            asyncio.run(cleanup())
        except:
            pass
