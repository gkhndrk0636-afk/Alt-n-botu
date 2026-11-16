import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask
import urllib.request
import json

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = "fqjk iycr ytvr zfgf"

app = Flask(__name__)
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
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=15m&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            res = data['chart']['result'][0]
            quotes = res['indicators']['quote'][0]
            prices = [p for p in quotes['close'] if p is not None]
            
            if not prices or len(prices) < 2:
                return "OK - Piyasa verisi toplanıyor...", 200
                
            current_price = prices[-1]
            return f"OK - Sistem Aktif | XAUUSD Fiyat: {current_price:.2f}", 200

    except Exception as e:
        return f"OK - Sistem Beklemede (Canlı mod aktif: {e})", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
