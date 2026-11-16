import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import yfinance as yf

# Dosya yolları
STATE_FILE = "state.json"

def get_market_data():
    """Yahoo Finance üzerinden XAUUSD (Altın) verilerini çeker."""
    df = yf.download("GC=F", period="5d", interval="5m", progress=False)
    if df.empty:
        df = yf.download("XAU=X", period="5d", interval="5m", progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    return df

def calculate_indicators(df):
    """Basit teknik indikatörleri (EMA vb.) hesaplar."""
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    return df

def check_signals(df):
    """Son duruma göre BUY, SELL veya NEUTRAL sinyali üretir."""
    if len(df) < 2:
        return "NEUTRAL"
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Basit EMA Kesişim Stratejisi
    if latest['EMA9'] > latest['EMA21'] and prev['EMA9'] <= prev['EMA21']:
        return "BUY"
    elif latest['EMA9'] < latest['EMA21'] and prev['EMA9'] >= prev['EMA21']:
        return "SELL"
    
    return "NEUTRAL"

def send_email_alert(signal, price):
    """Gmail üzerinden sinyal değiştiğinde e-posta gönderir."""
    sender_email = os.environ.get("GMAIL_USER", "gkhndrk0636@gmail.com")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    
    if not app_password:
        print("Gmail uygulama şifresi bulunamadı!")
        return

    receiver_email = sender_email
    
    message = MIMEMultipart("alternative")
    message["Subject"] = f"🚨 XAUUSD Sinyal Değişti: {signal} (Fiyat: {price})"
    message["From"] = sender_email
    message["To"] = receiver_email
    
    text = f"XAUUSD Altın Botu yeni bir sinyal üretti!\n\nYön: {signal}\nFiyat: {price}"
    part = MIMEText(text, "plain")
    message.attach(part)
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print(f"E-posta başarıyla gönderildi: {signal}")
    except Exception as e:
        print(f"E-posta gönderilirken hata oluştu: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"last_signal": "NEUTRAL"}

def save_state(signal):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_signal": signal}, f)

def main():
    print("XAUUSD Bot çalıştırılıyor...")
    df = get_market_data()
    if df.empty:
        print("Veri alınamadı.")
        return
        
    df = calculate_indicators(df)
    current_signal = check_signals(df)
    latest_price = float(df['Close'].iloc[-1])
    
    print(f"Güncel Fiyat: {latest_price}, Sinyal: {current_signal}")
    
    state = load_state()
    last_signal = state.get("last_signal", "NEUTRAL")
    
    # Sadece sinyal değiştiğinde mail at
    if current_signal != "NEUTRAL" and current_signal != last_signal:
        send_email_alert(current_signal, latest_price)
        save_state(current_signal)
    else:
        print(f"Sinyal değişmedi (Mevcut: {current_signal}, Önceki: {last_signal}). Mail gönderilmedi.")

if __name__ == "__main__":
    main()
