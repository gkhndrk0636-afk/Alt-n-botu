import os
import time
import requests
from flask import Flask
TOKEN = "9094158096:AAHTXv7fQ3_xpnriftXM81e-L5I0ENRQ1Vw"
CHAT_ID = "1554567098"

app = Flask('')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Telegram Yanıt Kodu: {response.status_code}")
        print(f"Telegram Yanıt İçeriği: {response.text}")
        return response.json()
    except Exception as e:
        print(f"Bağlantı Hatası: {e}")

@app.route('/')
def home():
    # Sayfaya her girildiğinde Telegram'a test mesajı tetiklenecek
    result = send_telegram_message("🔔 **Test Başarılı!** Bot ve Render Bağlantısı Çalışıyor.")
    return f"Bot Aktif! Telegram Yanıtı: {result}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
