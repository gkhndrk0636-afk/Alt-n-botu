import os
import time
import requests
import pandas as pd
import yfinance as yf
from threading import Thread
from flask import Flask

# --- RENDER WEB SUNUCUSU (Port 10000) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif ve Calisiyor!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- TELEGRAM BİLGİLERİ ---
TOKEN = "867931044:AAHoQKnLTDRrc76w5HFcC8Z_1lXXf9zS48"
CHAT_ID = "1554567098"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Telegram Yanıtı: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Telegram Bağlantı Hatası: {e}")

def get_gold_data():
    symbols = ["GC=F", "XAUUSD=X", "GLD"]
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1mo", interval="1h")
            if not df.empty:
                return df, sym
        except Exception as e:
            continue
    return None, None

def analyze_and_trade():
    df, used_symbol = get_gold_data()
    if df is None or len(df) < 30:
        print("Piyasa verisi alınamadı.")
        return

    try:
        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        current_price = df['Close'].iloc[-1]
        ema9 = df['EMA9'].iloc[-1]
        ema21 = df['EMA21'].iloc[-1]

        print(f"Piyasa taranıyor ({used_symbol}) - Fiyat: {current_price:.2f}")

        if ema9 > ema21 and df['EMA9'].iloc[-2] <= df['EMA21'].iloc[-2]:
            msg = f"🚀 **ALIM SİNYALİ (XAUUSD)**\n*Fiyat:* {current_price:.2f}\n*EMA9 yukarı kesti.*"
            send_telegram_message(msg)
        elif ema9 < ema21 and df['EMA9'].iloc[-2] >= df['EMA21'].iloc[-2]:
            msg = f"📉 **SATIM SİNYALİ (XAUUSD)**\n*Fiyat:* {current_price:.2f}\n*EMA9 aşağı kesti.*"
            send_telegram_message(msg)

    except Exception as e:
        print(f"Analiz Hatası: {e}")

def main():
    print("Xauusd Scalping Botu Başlatılıyor...")
    time.sleep(3)
    
    # Başlangıç mesajını gönderip sonucunu loglarda göreceğiz
    res = send_telegram_message("🚀 **XAUUSD Scalping Botu Canlıya Alındı ve Çalışıyor!**")
    print(f"Başlangıç Mesajı Sonucu: {res}")
    
    while True:
        try:
            analyze_and_trade()
        except Exception as e:
            print(f"Döngü hatası: {e}")
        time.sleep(900)  # 15 dakikada bir tarar

if __name__ == "__main__":
    # Flask sunucusunu arka planda başlat
    web_thread = Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()
    
    # Ana bot döngüsünü başlat
    main()
if __name__ == "__main__":
    # Önce ana bot döngüsünü ayrı bir arka plan thread'i olarak başlatalım
    bot_thread = Thread(target=main)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Flask sunucusunu ana akışta çalıştıralım (Render portu beklediği için ana akışta olmalı)
    run_web()
