import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = "fqjk iycr ytvr zfgf"

app = Flask('')

def send_email_notification(message_body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = "🚨 XAUUSD Scalping Sinyal Bildirimi"
        
        msg.attach(MIMEText(message_body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        print("E-posta başarıyla gönderildi!")
        return "Başarılı"
    except Exception as e:
        print(f"E-posta Gönderme Hatası: {e}")
        return f"Hata: {e}"

@app.route('/')
def home():
    durum = send_email_notification("🚀 XAUUSD Scalping Botu: E-posta bildirim sistemi başarıyla aktif ve çalışıyor!")
    return f"Bot Servisi Çalışıyor! Mail Durumu: {durum}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
