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
        print("Profesyonel Sinyal E-postası Gönderildi!")
        return "Başarılı"
    except Exception as e:
        print(f"E-posta Gönderme Hatası: {e}")
        return f"Hata: {e}"

def analyze_xauusd_market():
    try:
        # Verileri çekiyoruz
        data_1h = yf.download("GC=F", interval="1h", period="5d", progress=False)
        data_15m = yf.download("GC=F", interval="15m", period="2d", progress=False)
        
        if data_1h.empty or data_15m.empty:
            return "Piyasa verisi alınamadı."
            
        # Çok katmanlı başlık (MultiIndex) sorununu önlemek için düzeltme
        if isinstance(data_1h.columns, pd.MultiIndex):
            data_1h.columns = data_1h.columns.get_level_values(0)
        if isinstance(data_15m.columns, pd.MultiIndex):
            data_15m.columns = data_15m.columns.get_level_values(0)
        
        # EMA9 ve EMA21 Hesaplamaları
        data_1h['EMA9'] = data_1h['Close'].ewm(span=9, adjust=False).mean()
        data_1h['EMA21'] = data_1h['Close'].ewm(span=21, adjust=False).mean()
        
        data_15m['EMA9'] = data_15m['Close'].ewm(span=9, adjust=False).mean()
        data_15m['EMA21'] = data_15m['Close'].ewm(span=21, adjust=False).mean()
        
        # Series hatasını önlemek için değerleri güvenli şekilde float'a çeviriyoruz
        c_price = float(data_15m['Close'].iloc[-1].iloc[0] if isinstance(data_15m['Close'].iloc[-1], pd.Series) else data_15m['Close'].iloc[-1])
        p1_e9 = float(data_15m['EMA9'].iloc[-2].iloc[0] if isinstance(data_15m['EMA9'].iloc[-2], pd.Series) else data_15m['EMA9'].iloc[-2])
        p1_e21 = float(data_15m['EMA21'].iloc[-2].iloc[0] if isinstance(data_15m['EMA21'].iloc[-2], pd.Series) else data_15m['EMA21'].iloc[-2])
        c_e9 = float(data_15m['EMA9'].iloc[-1].iloc[0] if isinstance(data_15m['EMA9'].iloc[-1], pd.Series) else data_15m['EMA9'].iloc[-1])
        c_e21 = float(data_15m['EMA21'].iloc[-1].iloc[0] if isinstance(data_15m['EMA21'].iloc[-1], pd.Series) else data_15m['EMA21'].iloc[-1])
        
        trend_val_1h = float(data_1h['EMA9'].iloc[-1].iloc[0] if isinstance(data_1h['EMA9'].iloc[-1], pd.Series) else data_1h['EMA9'].iloc[-1]) > float(data_1h['EMA21'].iloc[-1].iloc[0] if isinstance(data_1h['EMA21'].iloc[-1], pd.Series) else data_1h['EMA21'].iloc[-1])
        trend_1h = "YÜKSELİŞ (BULLISH)" if trend_val_1h else "DÜŞÜŞ (BEARISH)"
        
        signal = None
        
        # AL (BUY) Kesişimi + Risk Yönetimi
        if p1_e9 <= p1_e21 and c_e9 > c_e21:
            stop_loss = c_price - 3.50
            take_profit = c_price + 7.00
            signal = (
                f"🟢 **PROFESYONEL XAUUSD AL (BUY) SİNYALİ**\n"
                f"----------------------------------------\n"
                f"📍 **Giriş Fiyatı:** {c_price:.2f}\n"
                f"🛑 **Zarar Kes (Stop Loss):** {stop_loss:.2f}\n"
                f"🎯 **Kar Al (Take Profit):** {take_profit:.2f}\n"
                f"📊 **15m EMA9/EMA21:** {c_e9:.2f} / {c_e21:.2f}\n"
                f"📈 **1 Saatlik Ana Trend:** {trend_1h}\n"
                f"----------------------------------------\n"
                f"⚡ *Strateji: EMA Kesişimi & Risk/Ödül 1:2*"
            )
            
        # SAT (SELL) Kesişimi + Risk Yönetimi
        elif p1_e9 >= p1_e21 and c_e9 < c_e21:
            stop_loss = c_price + 3.50
            take_profit = c_price - 7.00
            signal = (
                f"🔴 **PROFESYONEL XAUUSD SAT (SELL) SİNYALİ**\n"
                f"----------------------------------------\n"
                f"📍 **Giriş Fiyatı:** {c_price:.2f}\n"
                f"🛑 **Zarar Kes (Stop Loss):** {stop_loss:.2f}\n"
                f"🎯 **Kar Al (Take Profit):** {take_profit:.2f}\n"
                f"📊 **15m EMA9/EMA21:** {c_e9:.2f} / {c_e21:.2f}\n"
                f"📉 **1 Saatlik Ana Trend:** {trend_1h}\n"
                f"----------------------------------------\n"
                f"⚡ *Strateji: EMA Kesişimi & Risk/Ödül 1:2*"
            )
            
        if signal:
            send_email_notification("🚨 XAUUSD Profesyonel Sinyal & Risk Raporu", signal)
            return f"Sinyal Üretildi ve Gönderildi:<br><pre>{signal}</pre>"
        else:
            return f"Piyasa taranıyor (Hafta sonu kapanış verileriyle)... Şu an net bir kesişim yok.<br>Güncel Fiyat: {c_price:.2f} | 1 Saatlik Trend: {trend_1h}"
            
    except Exception as e:
        return f"Analiz Motoru Hatası: {e}"

@app.route('/')
def home():
    sonuc = analyze_xauusd_market()
    return f"<h3>XAUUSD Scalping Botu Çalışıyor 🚀</h3><p>{sonuc}</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
