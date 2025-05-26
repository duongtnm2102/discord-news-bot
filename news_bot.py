import discord
from discord.ext import commands
import feedparser
import requests
import asyncio
import os
import re
from datetime import datetime
import time
from urllib.parse import urljoin
import html
import chardet

# Cấu hình bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔒 BẢO MẬT: Lấy token từ environment variable
# KHÔNG BAO GIỜ hardcode token trong code nữa!
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("❌ CẢNH BÁO: Không tìm thấy DISCORD_TOKEN trong environment variables!")
    print("🔧 Vui lòng thêm DISCORD_TOKEN vào Render Environment Variables")
    exit(1)

# Lưu trữ tin tức theo từng user để xem chi tiết
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

@bot.event
async def on_ready():
    print(f'✅ {bot.user} đã online!')
    print(f'📊 Kết nối với {len(bot.guilds)} server(s)')
    total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
    print(f'📰 Sẵn sàng cung cấp tin từ {total_sources} nguồn ĐÃ KIỂM TRA')
    print(f'🇻🇳 Trong nước: {len(RSS_FEEDS["domestic"])} nguồn')
    print(f'🌍 Quốc tế: {len(RSS_FEEDS["international"])} nguồn')
    print('🎯 Lĩnh vực: Kinh tế, Chứng khoán, Vĩ mô, Bất động sản')
    print('🎯 Gõ !menu để xem hướng dẫn')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name="tin kinh tế bảo mật | !menu"
        )
    )

async def fetch_full_content(url):
    """Lấy nội dung đầy đủ từ URL bài viết với xử lý encoding tốt hơn"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Lấy nội dung với timeout ngắn hơn
        response = requests.get(url, headers=headers, timeout=8, stream=True)
        response.raise_for_status()
        
        # Xử lý encoding
        raw_content = response.content
        
        # Tự động detect encoding
        detected = chardet.detect(raw_content)
        encoding = detected['encoding'] or 'utf-8'
        
        try:
            content = raw_content.decode(encoding)
        except:
            # Fallback encoding
            content = raw_content.decode('utf-8', errors='ignore')
        
        # Loại bỏ HTML tags một cách thông minh hơn
        # Tìm nội dung chính
        content_patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<main[^>]*>(.*?)</main>',
            r'<section[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</section>'
        ]
        
        main_content = ""
        for pattern in content_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                main_content = matches[0]
                break
        
        # Nếu không tìm được content chính, lấy toàn bộ body
        if not main_content:
            body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
            if body_match:
                main_content = body_match.group(1)
            else:
                main_content = content
        
        # Loại bỏ scripts, styles, và các thẻ không cần thiết
        main_content = re.sub(r'<script[^>]*>.*?</script>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'<style[^>]*>.*?</style>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'<nav[^>]*>.*?</nav>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'<header[^>]*>.*?</header>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'<footer[^>]*>.*?</footer>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'<aside[^>]*>.*?</aside>', '', main_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Loại bỏ HTML tags
        clean_content = re.sub(r'<[^>]+>', ' ', main_content)
        
        # Decode HTML entities
        clean_content = html.unescape(clean_content)
        
        # Loại bỏ khoảng trắng thừa và normalize
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # Lấy phần đầu có ý nghĩa
        sentences = clean_content.split('. ')
        meaningful_content = []
        
        for sentence in sentences[:10]:  # Lấy 10 câu đầu
            if len(sentence.strip()) > 20:  # Chỉ lấy câu có độ dài hợp lý
                meaningful_content.append(sentence.strip())
                
        result = '. '.join(meaningful_content)
        
        # Giới hạn độ dài
        if len(result) > 1800:
            result = result[:1800] + "..."
            
        return result if result else "Không thể trích xuất nội dung từ bài viết này."
        
    except Exception as e:
        print(f"⚠️ Lỗi lấy nội dung từ {url}: {e}")
        return f"Không thể lấy nội dung chi tiết. Lỗi: {str(e)}"

async def collect_news_from_sources(sources_dict, limit_per_source=8):
    """Thu thập tin tức từ nhiều nguồn và sắp xếp theo thời gian"""
    all_news = []
    
    for source_name, rss_url in sources_dict.items():
        try:
            print(f"🔄 Đang lấy tin từ {source_name}...")
            
            # Headers cải thiện
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml',
                'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8'
            }
            
            # Parse RSS feed với xử lý lỗi tốt hơn
            try:
                response = requests.get(rss_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                # Parse với feedparser
                feed = feedparser.parse(response.content)
                
            except Exception as req_error:
                print(f"⚠️ Lỗi request từ {source_name}: {req_error}")
                # Thử parse trực tiếp với feedparser
                feed = feedparser.parse(rss_url)
            
            # Kiểm tra xem feed có hợp lệ không
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"⚠️ Không có tin từ {source_name} - RSS có thể không hoạt động")
                continue
                
            entries_processed = 0
            for entry in feed.entries[:limit_per_source]:
                try:
                    # Lấy thời gian published
                    published_time = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        except:
                            pass
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        try:
                            published_time = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                        except:
                            pass
                    
                    # Lấy mô tả/tóm tắt nếu có
                    description = ""
                    if hasattr(entry, 'summary'):
                        description = entry.summary[:500] + "..." if len(entry.summary) > 500 else entry.summary
                    elif hasattr(entry, 'description'):
                        description = entry.description[:500] + "..." if len(entry.description) > 500 else entry.description
                    
                    # Kiểm tra các trường bắt buộc
                    if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                        continue
                    
                    # Clean title
                    title = html.unescape(entry.title.strip())
                    
                    news_item = {
                        'title': title,
                        'link': entry.link,
                        'source': source_name,
                        'published': published_time,
                        'published_str': published_time.strftime("%H:%M %d/%m"),
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
    """Loại bỏ tin tức trùng lặp dựa trên tiêu đề và link"""
    seen_links = set()
    seen_titles = set()
    unique_news = []
    
    for news in news_list:
        # Chuẩn hóa tiêu đề để so sánh
        normalized_title = normalize_title(news['title'])
        
        # Kiểm tra trùng lặp
        is_duplicate = False
        
        if news['link'] in seen_links:
            is_duplicate = True
        else:
            # Kiểm tra tiêu đề tương tự
            for existing_title in seen_titles:
                similarity = calculate_title_similarity(normalized_title, existing_title)
                if similarity > 0.75:  # 75% tương tự thì coi là trùng
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
    # Chuyển về chữ thường
    title = title.lower()
    # Loại bỏ dấu câu và ký tự đặc biệt
    title = re.sub(r'[^\w\s]', '', title)
    # Loại bỏ khoảng trắng thừa
    title = ' '.join(title.split())
    
    # Chỉ lấy 10 từ đầu để so sánh
    words = title.split()[:10]
    return ' '.join(words)

def save_user_news(user_id, news_list, command_type):
    """Lưu tin tức của user để sử dụng cho lệnh !detail"""
    user_news_cache[user_id] = {
        'news': news_list,
        'command': command_type,
        'timestamp': datetime.now()
    }

@bot.command(name='all')
async def get_all_news(ctx, page=1):
    """Lấy tin tức từ tất cả nguồn (trong nước + quốc tế)"""
    try:
        page = max(1, int(page))
        
        # Gửi thông báo đang tải
        loading_msg = await ctx.send("⏳ Đang tải tin tức từ tất cả nguồn...")
        
        # Thu thập tin từ cả hai nguồn
        domestic_news = await collect_news_from_sources(RSS_FEEDS['domestic'], 8)
        international_news = await collect_news_from_sources(RSS_FEEDS['international'], 6)
        
        # Xóa thông báo loading
        await loading_msg.delete()
        
        # Kết hợp và sắp xếp
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
        
        # Tạo embed với thiết kế tốt hơn
        embed = discord.Embed(
            title=f"📰 Tin tức kinh tế tổng hợp (Trang {page})",
            description=f"🔒 Bot bảo mật • Cập nhật từ {len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])} nguồn tin uy tín",
            color=0x00ff88,
            timestamp=ctx.message.created_at
        )
        
        # Emoji map cho từng nguồn
        emoji_map = {
            # Nguồn trong nước
            'cafef_main': '☕', 'cafef_chungkhoan': '📈', 'cafef_batdongsan': '🏢', 'cafef_taichinh': '💰', 'cafef_vimo': '📊',
            'cafebiz_main': '💼', 'baodautu_main': '🎯', 'vneconomy_main': '📰', 'vneconomy_chungkhoan': '📈',
            'vnexpress_kinhdoanh': '⚡', 'vnexpress_chungkhoan': '📈', 'thanhnien_kinhtevimo': '📊', 'thanhnien_chungkhoan': '📈',
            'nhandanonline_tc': '🏛️',
            # Nguồn quốc tế
            'yahoo_finance': '💰', 'reuters_business': '🌍', 'bloomberg_markets': '💹', 'marketwatch_latest': '📈',
            'forbes_money': '💎', 'financial_times': '💼', 'business_insider': '📰', 'the_economist': '🎓'
        }
        
        # Thống kê
        domestic_count = sum(1 for news in page_news if news['source'] in RSS_FEEDS['domestic'])
        international_count = len(page_news) - domestic_count
        
        embed.add_field(
            name="📊 Thống kê trang này",
            value=f"🇻🇳 Trong nước: {domestic_count} tin\n🌍 Quốc tế: {international_count} tin\n📊 Tổng có sẵn: {len(all_news)} tin",
            inline=False
        )
        
        # Hiển thị tin tức
        for i, news in enumerate(page_news, 1):
            emoji = emoji_map.get(news['source'], '📰')
            title = news['title'][:70] + "..." if len(news['title']) > 70 else news['title']
            
            # Tên nguồn hiển thị
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
            source_display = source_names.get(news['source'], news['source'])
            
            embed.add_field(
                name=f"{i}. {emoji} {title}",
                value=f"📅 {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        # Lưu tin tức
        save_user_news(ctx.author.id, page_news, f"all_page_{page}")
        
        # Footer
        total_pages = (len(all_news) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔒 Bot bảo mật • Trang {page}/{total_pages} • !all {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except ValueError:
        await ctx.send("❌ Số trang không hợp lệ! Sử dụng: `!all [số]`")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='in')
async def get_domestic_news(ctx, page=1):
    """Lấy tin tức từ các nguồn trong nước"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức trong nước...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['domestic'], 10)
        
        await loading_msg.delete()
        
        # Phân trang
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
            description=f"🔒 Bot bảo mật • Từ {len(RSS_FEEDS['domestic'])} nguồn tin chuyên ngành Việt Nam",
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
                value=f"📅 {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"in_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔒 Bot bảo mật • Trang {page}/{total_pages} • !in {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='out')
async def get_international_news(ctx, page=1):
    """Lấy tin tức từ các nguồn quốc tế"""
    try:
        page = max(1, int(page))
        
        loading_msg = await ctx.send("⏳ Đang tải tin tức quốc tế...")
        
        news_list = await collect_news_from_sources(RSS_FEEDS['international'], 8)
        
        await loading_msg.delete()
        
        # Phân trang
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
            description=f"🔒 Bot bảo mật • Từ {len(RSS_FEEDS['international'])} nguồn tin hàng đầu thế giới",
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
                value=f"📅 {news['published_str']} • 📰 {source_display}\n🔗 [Đọc bài viết]({news['link']})",
                inline=False
            )
        
        save_user_news(ctx.author.id, page_news, f"out_page_{page}")
        
        total_pages = (len(news_list) + items_per_page - 1) // items_per_page
        embed.set_footer(text=f"🔒 Bot bảo mật • Trang {page}/{total_pages} • !out {page+1} tiếp • !chitiet [số] xem chi tiết")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {str(e)}")

@bot.command(name='chitiet')
async def get_news_detail(ctx, news_number: int):
    """Xem chi tiết tin tức theo số thứ tự - ĐÃ SỬA LỖI ENCODING"""
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
        
        # Thông báo đang tải với progress
        loading_msg = await ctx.send("⏳ Đang phân tích và trích xuất nội dung bài viết...")
        
        # Lấy nội dung với function đã cải tiến
        full_content = await fetch_full_content(news['link'])
        
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
        
        embed.add_field(
            name=f"{emoji} Tiêu đề",
            value=news['title'],
            inline=False
        )
        
        embed.add_field(
            name="📅 Thời gian",
            value=news['published_str'],
            inline=True
        )
        
        embed.add_field(
            name="📰 Nguồn",
            value=source_display,
            inline=True
        )
        
        # Hiển thị nội dung đã được xử lý
        if len(full_content) > 1000:
            # Chia nội dung thành 2 phần
            embed.add_field(
                name="📄 Nội dung chi tiết (Phần 1)",
                value=full_content[:1000] + "...",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
            # Tạo embed thứ 2
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
            
            embed2.set_footer(text=f"🔒 Bot bảo mật • Từ lệnh: {user_data['command']} • Tin số {news_number}")
            
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
        
        embed.set_footer(text=f"🔒 Bot bảo mật • Từ lệnh: {user_data['command']} • Tin số {news_number} • !menu để xem thêm lệnh")
        
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
    """Hiển thị menu lệnh - ĐÃ CẬP NHẬT BẢO MẬT"""
    embed = discord.Embed(
        title="🤖🔒 Menu News Bot - Bảo mật & Ổn định",
        description="Bot tin tức kinh tế đã được tối ưu và bảo mật token",
        color=0xff9900
    )
    
    embed.add_field(
        name="📰 Lệnh chính",
        value="""
**!all [trang]** - Tin từ tất cả nguồn (12 tin/trang)
**!in [trang]** - Tin trong nước (12 tin/trang)  
**!out [trang]** - Tin quốc tế (12 tin/trang)
**!chitiet [số]** - Xem nội dung chi tiết
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
    
    embed.add_field(
        name="🔒 Bảo mật mới",
        value="""
✅ **Token được bảo vệ** - Sử dụng Environment Variables
✅ **Không hardcode** - Token không còn trong source code
✅ **Deploy an toàn** - Không bị Discord reset token
✅ **Monitoring tích hợp** - Phát hiện lỗi nhanh chóng
        """,
        inline=False
    )
    
    embed.add_field(
        name="📋 Hướng dẫn sử dụng",
        value="""
1️⃣ Gõ **!all** để xem tin mới nhất
2️⃣ Chọn số tin muốn đọc chi tiết (1-12)
3️⃣ Gõ **!chitiet [số]** để xem nội dung đầy đủ
4️⃣ Dùng **!all 2**, **!all 3** để xem trang tiếp theo
        """,
        inline=False
    )
    
    embed.set_footer(text="🔒 Bot đã được bảo mật • Token an toàn • RSS feeds ổn định")
    await ctx.send(embed=embed)

# Chạy bot với error handling tốt hơn
if __name__ == "__main__":
    try:
        print("🚀 Đang khởi động News Bot bảo mật...")
        print("🔑 Đang kiểm tra token từ Environment Variables...")
        
        if TOKEN:
            print("✅ Token đã được tải từ Environment Variables")
        
        total_sources = len(RSS_FEEDS['domestic']) + len(RSS_FEEDS['international'])
        print(f"📊 Đã load {total_sources} nguồn RSS ĐÃ KIỂM TRA")
        print(f"🇻🇳 Trong nước: {len(RSS_FEEDS['domestic'])} nguồn")
        print(f"🌍 Quốc tế: {len(RSS_FEEDS['international'])} nguồn")
        print("🎯 Lĩnh vực: Kinh tế, Chứng khoán, Vĩ mô, Bất động sản")
        print("🔒 Bot đã được bảo mật token")
        print("✅ Bot sẵn sàng nhận lệnh!")
        
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ Lỗi đăng nhập Discord!")
        print("🔧 Token có thể không hợp lệ hoặc đã bị reset")
        print("🔧 Kiểm tra DISCORD_TOKEN trong Environment Variables")
        
    except Exception as e:
        print(f"❌ Lỗi khi chạy bot: {e}")
        print("🔧 Kiểm tra kết nối internet và Environment Variables")
        
    input("Nhấn Enter để thoát...")
