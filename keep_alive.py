from flask import Flask
from threading import Thread
import time

app = Flask('')

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>🔒 Discord News Bot - Bảo mật</title>
            <style>
                body { font-family: Arial; text-align: center; margin-top: 50px; background: #f0f0f0; }
                .container { background: white; padding: 30px; border-radius: 10px; max-width: 500px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                .status { color: #28a745; font-size: 24px; margin-bottom: 20px; }
                .security { color: #6f42c1; font-size: 16px; margin-bottom: 15px; }
                .features { text-align: left; margin-top: 20px; }
                .feature { margin: 10px 0; padding: 8px; background: #f8f9fa; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Discord News Bot</h1>
                <div class="status">✅ Bot đang chạy!</div>
                <div class="security">🔒 Token được bảo mật với Environment Variables</div>
                
                <div class="features">
                    <div class="feature">📰 Tin tức kinh tế từ 17 nguồn uy tín</div>
                    <div class="feature">🇻🇳 9 nguồn trong nước (CafeF, VnEconomy, VnExpress...)</div>
                    <div class="feature">🌍 8 nguồn quốc tế (Reuters, Bloomberg, Forbes...)</div>
                    <div class="feature">🔒 Bảo mật token - Không bị Discord reset</div>
                    <div class="feature">⚡ Tốc độ nhanh - Nội dung chi tiết</div>
                </div>
                
                <p style="margin-top: 30px; color: #6c757d;">
                    Gõ <strong>!menu</strong> trong Discord để xem hướng dẫn
                </p>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "message": "Discord News Bot is running securely"}

def run():
    # Chạy Flask server trên port 8080 (theo yêu cầu của Render)
    app.run(host='0.0.0.0', port=8080, debug=False)

def keep_alive():
    """Khởi động web server để keep bot alive"""
    t = Thread(target=run)
    t.daemon = True  # Thread sẽ tự động kết thúc khi main thread kết thúc
    t.start()
    print("🌐 Web server đã khởi động trên port 8080")
    print("🔗 Health check endpoint: /health")
