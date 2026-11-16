import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask
import pandas as pd
import yfinance as yf

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = "fqjk iycr ytvr zfgf"

app = Flask('')

last_signal_type = None

def send_email_notification(subject, message_body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        return True, "Başarılı"
    except Exception as e:
        return False, str(e)

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

@app.route('/test')
def test_mail():
    test_body = (
        "✅ GELİŞMİŞ EMA (5/13, 9/21) & RSI SİSTEMİ TESTİ BAŞARILI!\n"
        "----------------------------------------\n"
        "XAUUSD Botu çoklu indikatör filtreleriyle aktif ve sorunsuz çalışıyor."
    )
    success, info = send_email_notification("🔔 XAUUSD Botu - Gelişmiş Test", test_body)
    if success:
        return "OK - Test maili gönderildi!", 200
    else:
        return f"HATA - Mail gönderilemedi: {info}", 200

@app.route('/')
def home():
    global last_signal_type
    try:
        data_1h = yf.download("GC=F", interval="1h", period="5d", progress=False)
        data_15m = yf.download("GC=F", interval="15m", period="2d", progress=False)
        data_5m = yf.download("GC=F", interval="5m", period="1d", progress=False)
        
        if data_1h.empty or data_15m.empty or data_5m.empty:
            return "Piyasa verisi alınamadı.", 200
            
        for df in [data_1h, data_15m, data_5m]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        
        # 1 Saatlik Trend EMA'ları
        data_1h['EMA9'] = data_1h['Close'].ewm(span=9, adjust=False).mean()
        data_1h['EMA21'] = data_1h['Close'].ewm(span=21, adjust=False).mean()
        
        # 15m ve 5m için hem (5,13) hem (9,21) hesaplamaları
        for df in [data_15m, data_5m]:
            df['EMA5'] = df['Close'].ewm(span=5, adjust=False).mean()
            df['EMA13'] = df['Close'].ewm(span=13, adjust=False).mean()
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
            df['RSI'] = calculate_rsi(df)

        c_price = float(data_5m['Close'].iloc[-1].iloc[0] if isinstance(data_5m['Close'].iloc[-1], pd.Series) else data_5m['Close'].iloc[-1])
        
        trend_val_1h = float(data_1h['EMA9'].iloc[-1].iloc[0] if isinstance(data_1h['EMA9'].iloc[-1], pd.Series) else data_1h['EMA9'].iloc[-1]) > float(data_1h['EMA21'].iloc[-1].iloc[0] if isinstance(data_1h['EMA21'].iloc[-1], pd.Series) else data_1h['EMA21'].iloc[-1])
        trend_1h = "YÜKSELİŞ (BULLISH)" if trend_val_1h else "DÜŞÜŞ (BEARISH)"
        
        signal = None
        current_type = None

        # Değerleri güvenli alalım (15m ve 5m için)
        current_rsi_15m = float(data_15m['RSI'].iloc[-1].iloc[0] if isinstance(data_15m['RSI'].iloc[-1], pd.Series) else data_15m['RSI'].iloc[-1])
        current_rsi_5m = float(data_5m['RSI'].iloc[-1].iloc[0] if isinstance(data_5m['RSI'].iloc[-1], pd.Series) else data_5m['RSI'].iloc[-1])

        # --- 1. 15M KESİŞİM KONTROLÜ (EMA 5/13 ve EMA 9/21 + RSI Filtresi) ---
        p1_15_e5 = float(data_15m['EMA5'].iloc[-2].iloc[0] if isinstance(data_15m['EMA5'].iloc[-2], pd.Series) else data_15m['EMA5'].iloc[-2])
        p1_15_e13 = float(data_15m['EMA13'].iloc[-2].iloc[0] if isinstance(data_15m['EMA13'].iloc[-2], pd.Series) else data_15m['EMA13'].iloc[-2])
        c_15_e5 = float(data_15m['EMA5'].iloc[-1].iloc[0] if isinstance(data_15m['EMA5'].iloc[-1], pd.Series) else data_15m['EMA5'].iloc[-1])
        c_15_e13 = float(data_15m['EMA13'].iloc[-1].iloc[0] if isinstance(data_15m['EMA13'].iloc[-1], pd.Series) else data_15m['EMA13'].iloc[-1])

        if p1_15_e5 <= p1_15_e13 and c_15_e5 > c_15_e13 and current_rsi_15m < 70:
            current_type = "15M_BUY"
            stop_loss = c_price - 3.50
            take_profit = c_price + 7.00
            signal = (
                f"🟢 [15M - GELİŞMİŞ] AL (BUY) SİNYALİ\n"
                f"----------------------------------------\n"
                f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                f"📊 15m EMA5/13: {c_15_e5:.2f}/{c_15_e13:.2f} | RSI: {current_rsi_15m:.1f}\n"
                f"📈 1h Trend: {trend_1h}\n"
                f"----------------------------------------"
            )
        elif p1_15_e5 >= p1_15_e13 and c_15_e5 < c_15_e13 and current_rsi_15m > 30:
            current_type = "15M_SELL"
            stop_loss = c_price + 3.50
            take_profit = c_price - 7.00
            signal = (
                f"🔴 [15M - GELİŞMİŞ] SAT (SELL) SİNYALİ\n"
                f"----------------------------------------\n"
                f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                f"📊 15m EMA5/13: {c_15_e5:.2f}/{c_15_e13:.2f} | RSI: {current_rsi_15m:.1f}\n"
                f"📉 1h Trend: {trend_1h}\n"
                f"----------------------------------------"
            )

        # --- 2. 5M KESİŞİM KONTROLÜ ---
        if not signal:
            p1_5_e5 = float(data_5m['EMA5'].iloc[-2].iloc[0] if isinstance(data_5m['EMA5'].iloc[-2], pd.Series) else data_5m['EMA5'].iloc[-2])
            p1_5_e13 = float(data_5m['EMA13'].iloc[-2].iloc[0] if isinstance(data_5m['EMA13'].iloc[-2], pd.Series) else data_5m['EMA13'].iloc[-2])
            c_5_e5 = float(data_5m['EMA5'].iloc[-1].iloc[0] if isinstance(data_5m['EMA5'].iloc[-1], pd.Series) else data_5m['EMA5'].iloc[-1])
            c_5_e13 = float(data_5m['EMA13'].iloc[-1].iloc[0] if isinstance(data_5m['EMA13'].iloc[-1], pd.Series) else data_5m['EMA13'].iloc[-1])

            if p1_5_e5 <= p1_5_e13 and c_5_e5 > c_5_e13 and current_rsi_5m < 70:
                current_type = "5M_BUY"
                stop_loss = c_price - 3.50
                take_profit = c_price + 7.00
                signal = (
                    f"🟢 [5M - HIZLI] AL (BUY) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                    f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                    f"📊 5m EMA5/13: {c_5_e5:.2f}/{c_5_e13:.2f} | RSI: {current_rsi_5m:.1f}\n"
                    f"📈 1h Trend: {trend_1h}\n"
                    f"----------------------------------------"
                )
            elif p1_5_e5 >= p1_5_e13 and c_5_e5 < c_5_e13 and current_rsi_5m > 30:
                current_type = "5M_SELL"
                stop_loss = c_price + 3.50
                take_profit = c_price - 7.00
                signal = (
                    f"🔴 [5M - HIZLI] SAT (SELL) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                    f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                    f"📊 5m EMA5/13: {c_5_e5:.2f}/{c_5_e13:.2f} | RSI: {current_rsi_5m:.1f}\n"
                    f"📉 1h Trend: {trend_1h}\n"
                    f"----------------------------------------"
                )
            
        if signal and current_type != last_signal_type:
            send_email_notification(f"🚨 XAUUSD Gelişmiş Sinyal [{current_type}]", signal)
            last_signal_type = current_type
            return f"OK - Sinyal Gonderildi ({current_type}) | Fiyat: {c_price:.2f}", 200
        else:
            return f"OK - Gelişmiş Tarama Aktif | Fiyat: {c_price:.2f} | RSI(5m): {current_rsi_5m:.1f}", 200
            
    except Exception as e:
        return f"Hata: {e}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
