import discord
from discord.ext import commands
import os
import asyncio
from keep_alive import keep_alive

# 🔍 DEBUGGING - PRINT ALL ENVIRONMENT VARIABLES
print("=" * 50)
print("🔍 ENVIRONMENT VARIABLES DEBUG")
print("=" * 50)

# Discord Token
TOKEN = os.getenv('DISCORD_TOKEN')
print(f"DISCORD_TOKEN: {'✅ Found (' + str(len(TOKEN)) + ' chars)' if TOKEN else '❌ Missing'}")

# AI API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY') 
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

print(f"GEMINI_API_KEY: {'✅ Found (' + str(len(GEMINI_API_KEY)) + ' chars)' if GEMINI_API_KEY else '❌ Missing'}")
print(f"DEEPSEEK_API_KEY: {'✅ Found (' + str(len(DEEPSEEK_API_KEY)) + ' chars)' if DEEPSEEK_API_KEY else '❌ Missing'}")
print(f"ANTHROPIC_API_KEY: {'✅ Found (' + str(len(ANTHROPIC_API_KEY)) + ' chars)' if ANTHROPIC_API_KEY else '❌ Missing'}")
print(f"GROQ_API_KEY: {'✅ Found (' + str(len(GROQ_API_KEY)) + ' chars)' if GROQ_API_KEY else '❌ Missing'}")
print(f"GOOGLE_API_KEY: {'✅ Found (' + str(len(GOOGLE_API_KEY)) + ' chars)' if GOOGLE_API_KEY else '❌ Missing'}")
print(f"GOOGLE_CSE_ID: {'✅ Found (' + str(len(GOOGLE_CSE_ID)) + ' chars)' if GOOGLE_CSE_ID else '❌ Missing'}")

# Test Library Imports
print("\n" + "=" * 50)
print("📚 TESTING LIBRARY IMPORTS")
print("=" * 50)

# Test Google Generative AI
try:
    import google.generativeai as genai
    print("✅ google.generativeai imported successfully")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Gemini API configured successfully")
    else:
        print("❌ GEMINI_API_KEY missing for configuration")
except ImportError as e:
    print(f"❌ google.generativeai import failed: {e}")
except Exception as e:
    print(f"❌ Gemini configuration failed: {e}")

# Test aiohttp
try:
    import aiohttp
    print("✅ aiohttp imported successfully")
except ImportError as e:
    print(f"❌ aiohttp import failed: {e}")

# Test Google API Client
try:
    from googleapiclient.discovery import build
    print("✅ google-api-python-client imported successfully")
except ImportError as e:
    print(f"❌ google-api-python-client import failed: {e}")

print("\n" + "=" * 50)
print("🤖 STARTING BOT")
print("=" * 50)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Simple AI Engine Test
class SimpleAITest:
    def __init__(self):
        self.available_engines = []
        self.test_engines()
    
    def test_engines(self):
        print("\n🔧 TESTING AI ENGINES:")
        
        # Test Gemini
        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                
                # Validate API key format
                if GEMINI_API_KEY.startswith('AIza') and len(GEMINI_API_KEY) > 30:
                    self.available_engines.append('GEMINI')
                    print("✅ GEMINI: API key format valid")
                else:
                    print(f"❌ GEMINI: Invalid API key format (starts with: {GEMINI_API_KEY[:10]})")
            except Exception as e:
                print(f"❌ GEMINI: Failed - {e}")
        else:
            print("⚠️ GEMINI: API key not found")
        
        # Test DeepSeek
        if DEEPSEEK_API_KEY:
            if DEEPSEEK_API_KEY.startswith('sk-') and len(DEEPSEEK_API_KEY) > 20:
                self.available_engines.append('DEEPSEEK')
                print("✅ DEEPSEEK: API key format valid")
            else:
                print(f"❌ DEEPSEEK: Invalid API key format (starts with: {DEEPSEEK_API_KEY[:10]})")
        else:
            print("⚠️ DEEPSEEK: API key not found")
        
        # Test Claude
        if ANTHROPIC_API_KEY:
            if ANTHROPIC_API_KEY.startswith('sk-ant-') and len(ANTHROPIC_API_KEY) > 30:
                self.available_engines.append('CLAUDE')
                print("✅ CLAUDE: API key format valid")
            else:
                print(f"❌ CLAUDE: Invalid API key format (starts with: {ANTHROPIC_API_KEY[:10]})")
        else:
            print("⚠️ CLAUDE: API key not found")
        
        # Test Groq
        if GROQ_API_KEY:
            if GROQ_API_KEY.startswith('gsk_') and len(GROQ_API_KEY) > 20:
                self.available_engines.append('GROQ')
                print("✅ GROQ: API key format valid")
            else:
                print(f"❌ GROQ: Invalid API key format (starts with: {GROQ_API_KEY[:10]})")
        else:
            print("⚠️ GROQ: API key not found")
        
        # Summary
        print(f"\n📊 SUMMARY:")
        print(f"Available AI Engines: {len(self.available_engines)}")
        if self.available_engines:
            print(f"Engines: {', '.join(self.available_engines)}")
        else:
            print("❌ NO AI ENGINES AVAILABLE!")

# Initialize AI Test
ai_test = SimpleAITest()

@bot.event
async def on_ready():
    print(f'\n✅ {bot.user} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    if ai_test.available_engines:
        print(f'🤖 AI Engines Available: {", ".join(ai_test.available_engines)}')
    else:
        print('❌ NO AI ENGINES AVAILABLE')
    
    # Set bot status
    status_text = f"Debug Mode • {len(ai_test.available_engines)} AI engines"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        )
    )

@bot.command(name='debug')
async def debug_command(ctx):
    """Debug command to check AI engines status"""
    
    embed = discord.Embed(
        title="🔧 Debug Report",
        color=0xff9900,
        timestamp=ctx.message.created_at
    )
    
    # Environment Variables Status
    env_status = ""
    env_status += f"🔑 DISCORD_TOKEN: {'✅' if TOKEN else '❌'}\n"
    env_status += f"🔑 GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌'}\n"
    env_status += f"🔑 DEEPSEEK_API_KEY: {'✅' if DEEPSEEK_API_KEY else '❌'}\n"
    env_status += f"🔑 ANTHROPIC_API_KEY: {'✅' if ANTHROPIC_API_KEY else '❌'}\n"
    env_status += f"🔑 GROQ_API_KEY: {'✅' if GROQ_API_KEY else '❌'}\n"
    
    embed.add_field(
        name="Environment Variables",
        value=env_status,
        inline=False
    )
    
    # AI Engines Status
    if ai_test.available_engines:
        ai_status = f"✅ Available: {', '.join(ai_test.available_engines)}"
    else:
        ai_status = "❌ No AI engines available"
    
    embed.add_field(
        name="AI Engines",
        value=ai_status,
        inline=False
    )
    
    # Library Status
    try:
        import google.generativeai
        gemini_lib = "✅"
    except:
        gemini_lib = "❌"
    
    try:
        import aiohttp
        aiohttp_lib = "✅"
    except:
        aiohttp_lib = "❌"
    
    library_status = f"📚 google-generativeai: {gemini_lib}\n📚 aiohttp: {aiohttp_lib}"
    
    embed.add_field(
        name="Libraries",
        value=library_status,
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='test')
async def test_ai(ctx):
    """Test AI functionality"""
    
    if not ai_test.available_engines:
        await ctx.send("❌ No AI engines available for testing!")
        return
    
    # Test với engine đầu tiên available
    engine = ai_test.available_engines[0]
    
    if engine == 'GEMINI':
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            response = model.generate_content("Say hello in Vietnamese")
            
            embed = discord.Embed(
                title="🤖 AI Test Result",
                description=response.text,
                color=0x00ff00
            )
            embed.add_field(name="Engine Used", value="💎 Gemini", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Gemini test failed: {str(e)}")
    
    else:
        await ctx.send(f"🧪 Test for {engine} not implemented yet, but engine is available!")

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN not found!")
    print("🔧 Add DISCORD_TOKEN to Environment Variables")
    exit(1)

# Main execution
if __name__ == "__main__":
    try:
        keep_alive()
        print("\n🚀 Starting Minimal Test Bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        input("Press Enter to exit...")
