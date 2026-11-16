import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask
import urllib.request
import json
import pandas as pd

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

def calculate_rsi(prices, window=14):
    s = pd.Series(prices)
    delta = s.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.tolist()

@app.route('/test')
def test_mail():
    success, info = send_email_notification("🔔 XAUUSD Botu - Test Bildirimi", "✅ Test maili başarıyla gönderildi! Sistem aktif.")
    if success:
        return "OK - Test maili gonderildi!", 200
    else:
        return f"HATA - Mail gonderilemedi: {info}", 200

@app.route('/')
def home():
    global last_signal_type
    try:
        # Yahoo Finance hafif API verisi (Asla kilitlenme yapmaz)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=15m&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            res = data['chart']['result'][0]
            quotes = res['indicators']['quote'][0]
            prices = [p for p in quotes['close'] if p is not None]
            
            if not prices or len(prices) < 21:
                return "OK - Piyasa verisi toplanıyor...", 200
                
            current_price = prices[-1]
            
            # EMA 5 ve EMA 13 Hesaplama
            s = pd.Series(prices)
            ema5 = s.ewm(span=5, adjust=False).mean().tolist()
            ema13 = s.ewm(span=13, adjust=False).mean().tolist()
            rsi_list = calculate_rsi(prices)
            
            p1_e5, p1_e13 = ema5[-2], ema13[-2]
            c_e5, c_e13 = ema5[-1], ema13[-1]
            current_rsi = rsi_list[-1]
            
            signal = None
            current_type = None
            
            # Alış / Satış Mantığı
            if p1_e5 <= p1_e13 and c_e5 > c_e13 and current_rsi < 70:
                current_type = "BUY"
                stop_loss = current_price - 3.50
                take_profit = current_price + 7.00
                signal = (
                    f"🟢 [XAUUSD] AL (BUY) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Fiyat: {current_price:.2f}\n"
                    f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                    f"📊 EMA5/13: {c_e5:.2f}/{c_e13:.2f} | RSI: {current_rsi:.1f}\n"
                    f"----------------------------------------"
                )
            elif p1_e5 >= p1_e13 and c_e5 < c_e13 and current_rsi > 30:
                current_type = "SELL"
                stop_loss = current_price + 3.50
                take_profit = current_price - 7.00
                signal = (
                    f"🔴 [XAUUSD] SAT (SELL) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Fiyat: {current_price:.2f}\n"
                    f"🛑 Stop Loss: {stop_loss:.2f} | 🎯 Take Profit: {take_profit:.2f}\n"
                    f"📊 EMA5/13: {c_e5:.2f}/{c_e13:.2f} | RSI: {current_rsi:.1f}\n"
                    f"----------------------------------------"
                )
                
            if signal and current_type != last_signal_type:
                send_email_notification(f"🚨 XAUUSD Sinyal [{current_type}]", signal)
                last_signal_type = current_type
                return f"OK - Sinyal Gonderildi ({current_type}) | Fiyat: {current_price:.2f}", 200
            else:
                return f"OK - Tarama Aktif | Fiyat: {current_price:.2f} | RSI: {current_rsi:.1f}", 200

    except Exception as e:
        return f"OK - Sistem Aktif (Hata yakalandı: {e})", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
