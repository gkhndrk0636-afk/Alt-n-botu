import time
import requests
import pandas as pd
import yfinance as yf

# Telegram Bot Bilgilerin
TOKEN = "8679310444:AAHoQknLTDRrc76w5HFcC8Z_llXxF9IfmWk"
CHAT_ID = "1554567098"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        print(f"Mesaj gonderme hatasi: {e}")

def get_gold_data():
    symbols = ["GC=F", "XAUUSD=X", "GLD"]
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1mo", interval="1h")
            if not df.empty and len(df) >= 50:
                return df, sym
        except Exception:
            continue
    return pd.DataFrame(), None

def analyze_and_trade():
    try:
        df, used_symbol = get_gold_data()
        
        if df.empty:
            print("Piyasa verisi su an alinamadi, 15 dakika sonra tekrar denenecek...")
            return

        close_prices = df['Close']
        current_price = float(close_prices.iloc[-1])

        # --- TEKNIK INDIKATORLER ---
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])

        ema9 = close_prices.ewm(span=9, adjust=False).mean()
        ema21 = close_prices.ewm(span=21, adjust=False).mean()
        current_ema9 = float(ema9.iloc[-1])
        current_ema21 = float(ema21.iloc[-1])

        ema50 = close_prices.ewm(span=50, adjust=False).mean()
        current_ema50 = float(ema50.iloc[-1])

        # --- SINYAL VE RISK YONETIMI ---
        signal = None
        reason = ""

        sl_step = round(current_price * 0.0015, 2) if used_symbol == "GLD" else 4.0
        tp_step = round(current_price * 0.0030, 2) if used_symbol == "GLD" else 8.0

        if current_price > current_ema50 and (current_rsi < 45 or (current_ema9 > current_ema21 and ema9.iloc[-2] <= ema21.iloc[-2])):
            signal = "🟢 XM XAUUSD PROFESYONEL ALIM (BUY)"
            stop_loss = round(current_price - sl_step, 2)
            take_profit = round(current_price + tp_step, 2)
            recommended_lot = "0.01 lot (100$ Kasa icin guvenli)"
            reason = f"Ana trend boga (yukselis), RSI: {current_rsi:.1f}"

        elif current_price < current_ema50 and (current_rsi > 55 or (current_ema9 < current_ema21 and ema9.iloc[-2] >= ema21.iloc[-2])):
            signal = "🔴 XM XAUUSD PROFESYONEL SATIM (SELL)"
            stop_loss = round(current_price + sl_step, 2)
            take_profit = round(current_price - tp_step, 2)
            recommended_lot = "0.01 lot (100$ Kasa icin guvenli)"
            reason = f"Ana trend ayi (dusus), RSI: {current_rsi:.1f}"

        if signal:
            report = (
                f"🎯 *XM ALTIN SINYALI* 🎯\n\n"
                f"📊 *Yon:* {signal}\n"
                f"🟡 *Giris Fiyati:* `${current_price:.2f}`\n\n"
                f"🛑 *Stop-Loss:* `${stop_loss}`\n"
                f"🎯 *Take-Profit:* `${take_profit}`\n"
                f"⚖️ *Onerilen Lot:* `{recommended_lot}`\n"
                f"📉 *RSI:* `{current_rsi:.2f}`\n\n"
                f"💡 *Analiz:* {reason}"
            )
            send_telegram_message(report)
            print(f"Sinyal Telegram'a gonderildi! ({used_symbol})")
        else:
            print(f"Piyasa tarandi ({used_symbol}). Fiyat: {current_price:.2f}, RSI: {current_rsi:.1f} - Sinyal bekleniyor...")

    except Exception as e:
        print(f"Analiz Hatasi: {e}")

def main():
    print("XM Uyumlu Altin Sinyal Botu Devrede...")
    send_telegram_message("🚀 *XM Uyumlu Altin Sinyal Botu Devrede!*")
    
    while True:
        analyze_and_trade()
        time.sleep(900)

if __name__ == "__main__":
    main()
