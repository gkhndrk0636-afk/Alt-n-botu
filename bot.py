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

# Aynı sinyali üst üste göndermemek için son sinyal türünü tutar (Örn: "5M_BUY", "15M_SELL" vb.)
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
        print("E-posta Gönderildi!")
        return True, "Başarılı"
    except Exception as e:
        print(f"E-posta Gönderme Hatası: {e}")
        return False, str(e)

@app.route('/test')
def test_mail():
    test_body = (
        "✅ ÇOKLU ZAMAN DİLİMİ TESTİ BAŞARILI!\n"
        "----------------------------------------\n"
        "XAUUSD Botu (5m & 15m) e-posta bildirim sistemi sorunsuz çalışıyor.\n"
        "Sinyaller geldiğinde hangi zaman diliminden geldiği açıkça belirtilecektir."
    )
    success, info = send_email_notification("🔔 XAUUSD Botu - Çoklu Zaman Dilimi Testi", test_body)
    if success:
        return "OK - Test maili gönderildi! Gelen kutunu kontrol et.", 200
    else:
        return f"HATA - Mail gönderilemedi: {info}", 200

@app.route('/')
def home():
    global last_signal_type
    try:
        # Verileri çekiyoruz: 1 Saatlik (Trend için), 15 Dakikalık ve 5 Dakikalık
        data_1h = yf.download("GC=F", interval="1h", period="5d", progress=False)
        data_15m = yf.download("GC=F", interval="15m", period="2d", progress=False)
        data_5m = yf.download("GC=F", interval="5m", period="1d", progress=False)
        
        if data_1h.empty or data_15m.empty or data_5m.empty:
            return "Piyasa verisi alınamadı.", 200
            
        # MultiIndex sütun düzeltmeleri
        for df in [data_1h, data_15m, data_5m]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        
        # EMA hesaplamaları
        data_1h['EMA9'] = data_1h['Close'].ewm(span=9, adjust=False).mean()
        data_1h['EMA21'] = data_1h['Close'].ewm(span=21, adjust=False).mean()
        
        data_15m['EMA9'] = data_15m['Close'].ewm(span=9, adjust=False).mean()
        data_15m['EMA21'] = data_15m['Close'].ewm(span=21, adjust=False).mean()

        data_5m['EMA9'] = data_5m['Close'].ewm(span=9, adjust=False).mean()
        data_5m['EMA21'] = data_5m['Close'].ewm(span=21, adjust=False).mean()
        
        # Fiyat ve EMA değerleri (Güvenli tip dönüşümleriyle)
        c_price = float(data_5m['Close'].iloc[-1].iloc[0] if isinstance(data_5m['Close'].iloc[-1], pd.Series) else data_5m['Close'].iloc[-1])
        
        # 1 Saatlik Trend Filtresi
        trend_val_1h = float(data_1h['EMA9'].iloc[-1].iloc[0] if isinstance(data_1h['EMA9'].iloc[-1], pd.Series) else data_1h['EMA9'].iloc[-1]) > float(data_1h['EMA21'].iloc[-1].iloc[0] if isinstance(data_1h['EMA21'].iloc[-1], pd.Series) else data_1h['EMA21'].iloc[-1])
        trend_1h = "YÜKSELİŞ (BULLISH)" if trend_val_1h else "DÜŞÜŞ (BEARISH)"
        
        signal = None
        current_type = None

        # --- 1. ÖNCELİK: 15 DAKİKALIK KESİŞİM (Daha Güçlü/Ana Sinyal) ---
        p1_15_e9 = float(data_15m['EMA9'].iloc[-2].iloc[0] if isinstance(data_15m['EMA9'].iloc[-2], pd.Series) else data_15m['EMA9'].iloc[-2])
        p1_15_e21 = float(data_15m['EMA21'].iloc[-2].iloc[0] if isinstance(data_15m['EMA21'].iloc[-2], pd.Series) else data_15m['EMA21'].iloc[-2])
        c_15_e9 = float(data_15m['EMA9'].iloc[-1].iloc[0] if isinstance(data_15m['EMA9'].iloc[-1], pd.Series) else data_15m['EMA9'].iloc[-1])
        c_15_e21 = float(data_15m['EMA21'].iloc[-1].iloc[0] if isinstance(data_15m['EMA21'].iloc[-1], pd.Series) else data_15m['EMA21'].iloc[-1])

        if p1_15_e9 <= p1_15_e21 and c_15_e9 > c_15_e21:
            current_type = "15M_BUY"
            stop_loss = c_price - 3.50
            take_profit = c_price + 7.00
            signal = (
                f"🟢 [15M - ANA ZAMAN DİLİMİ] AL (BUY) SİNYALİ\n"
                f"----------------------------------------\n"
                f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                f"🛑 Zarar Kes (Stop Loss): {stop_loss:.2f}\n"
                f"🎯 Kar Al (Take Profit): {take_profit:.2f}\n"
                f"📊 15m EMA9/EMA21: {c_15_e9:.2f} / {c_15_e21:.2f}\n"
                f"📈 1 Saatlik Ana Trend: {trend_1h}\n"
                f"----------------------------------------\n"
                f"⚡ Strateji: 15m Kesişimi & Risk/Ödül 1:2"
            )
        elif p1_15_e9 >= p1_15_e21 and c_15_e9 < c_15_e21:
            current_type = "15M_SELL"
            stop_loss = c_price + 3.50
            take_profit = c_price - 7.00
            signal = (
                f"🔴 [15M - ANA ZAMAN DİLİMİ] SAT (SELL) SİNYALİ\n"
                f"----------------------------------------\n"
                f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                f"🛑 Zarar Kes (Stop Loss): {stop_loss:.2f}\n"
                f"🎯 Kar Al (Take Profit): {take_profit:.2f}\n"
                f"📊 15m EMA9/EMA21: {c_15_e9:.2f} / {c_15_e21:.2f}\n"
                f"📉 1 Saatlik Ana Trend: {trend_1h}\n"
                f"----------------------------------------\n"
                f"⚡ Strateji: 15m Kesişimi & Risk/Ödül 1:2"
            )

        # --- 2. ÖNCELİK: 5 DAKİKALIK KESİŞİM (Hızlı/Erken Sinyal) ---
        if not signal:
            p1_5_e9 = float(data_5m['EMA9'].iloc[-2].iloc[0] if isinstance(data_5m['EMA9'].iloc[-2], pd.Series) else data_5m['EMA9'].iloc[-2])
            p1_5_e21 = float(data_5m['EMA21'].iloc[-2].iloc[0] if isinstance(data_5m['EMA21'].iloc[-2], pd.Series) else data_5m['EMA21'].iloc[-2])
            c_5_e9 = float(data_5m['EMA9'].iloc[-1].iloc[0] if isinstance(data_5m['EMA9'].iloc[-1], pd.Series) else data_5m['EMA9'].iloc[-1])
            c_5_e21 = float(data_5m['EMA21'].iloc[-1].iloc[0] if isinstance(data_5m['EMA21'].iloc[-1], pd.Series) else data_5m['EMA21'].iloc[-1])

            if p1_5_e9 <= p1_5_e21 and c_5_e9 > c_5_e21:
                current_type = "5M_BUY"
                stop_loss = c_price - 3.50
                take_profit = c_price + 7.00
                signal = (
                    f"🟢 [5M - HIZLI ZAMAN DİLİMİ] AL (BUY) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                    f"🛑 Zarar Kes (Stop Loss): {stop_loss:.2f}\n"
                    f"🎯 Kar Al (Take Profit): {take_profit:.2f}\n"
                    f"📊 5m EMA9/EMA21: {c_5_e9:.2f} / {c_5_e21:.2f}\n"
                    f"📈 1 Saatlik Ana Trend: {trend_1h}\n"
                    f"----------------------------------------\n"
                    f"⚡ Strateji: 5m Hızlı Kesişim & Risk/Ödül 1:2"
                )
            elif p1_5_e9 >= p1_5_e21 and c_5_e9 < c_5_e21:
                current_type = "5M_SELL"
                stop_loss = c_price + 3.50
                take_profit = c_price - 7.00
                signal = (
                    f"🔴 [5M - HIZLI ZAMAN DİLİMİ] SAT (SELL) SİNYALİ\n"
                    f"----------------------------------------\n"
                    f"📍 Giriş Fiyatı: {c_price:.2f}\n"
                    f"🛑 Zarar Kes (Stop Loss): {stop_loss:.2f}\n"
                    f"🎯 Kar Al (Take Profit): {take_profit:.2f}\n"
                    f"📊 5m EMA9/EMA21: {c_5_e9:.2f} / {c_5_e21:.2f}\n"
                    f"📉 1 Saatlik Ana Trend: {trend_1h}\n"
                    f"----------------------------------------\n"
                    f"⚡ Strateji: 5m Hızlı Kesişim & Risk/Ödül 1:2"
                )
            
        if signal and current_type != last_signal_type:
            send_email_notification(f"🚨 XAUUSD Sinyal Raporu [{current_type}]", signal)
            last_signal_type = current_type
            return f"OK - Sinyal Gonderildi ({current_type}) | Fiyat: {c_price:.2f}", 200
        else:
            return f"OK - Piyasa Taranıyor (5m & 15m) | Fiyat: {c_price:.2f}", 200
            
    except Exception as e:
        return f"Hata: {e}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
