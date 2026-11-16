
import os
import json
import urllib.request
import smtplib
import pandas as pd

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SYMBOL = "GC=F"
STATE_FILE = "state.json"


def get_market_data():
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + SYMBOL
        + "?interval=15m&range=5d"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode())

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time": pd.to_datetime(timestamps, unit="s", utc=True),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"]
    })

    df = df.dropna().reset_index(drop=True)

    if len(df) < 60:
        raise ValueError("Yeterli piyasa verisi yok.")

    return df


def calculate_indicators(df):
    df["ema20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    return df


def send_email(subject, body):
    if not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_APP_PASSWORD eksik.")

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())


def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_processed": ""}


def save_state(candle_time):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_processed": candle_time}, f)


def run_bot():
    print("XAUUSD sinyal botu başlatıldı.")

    df = get_market_data()
    df = calculate_indicators(df)

    # Son mum henüz tamamlanmamış olabilir.
    candle = df.iloc[-2]

    candle_time = candle["time"].isoformat()

    state = read_state()

    if state.get("last_processed") == candle_time:
        print("Bu mum daha önce kontrol edildi.")
        return

    price = float(candle["close"])
    ema20 = float(candle["ema20"])
    ema50 = float(candle["ema50"])
    rsi = float(candle["rsi"])
    atr = float(candle["atr"])

    if pd.isna(rsi) or pd.isna(atr):
        raise ValueError("İndikatör verisi eksik.")

    signal = None

    if ema20 > ema50 and 50 <= rsi <= 70:
        signal = "BUY"
        sl = price - atr * 1.5
        tp = price + atr * 3

    elif ema20 < ema50 and 30 <= rsi <= 50:
        signal = "SELL"
        sl = price + atr * 1.5
        tp = price - atr * 3

    if signal:
        message = f"""
XAUUSD ALTIN SİNYALİ

Sinyal: {signal}

Veri kaynağı: Yahoo Finance GC=F
Zaman dilimi: 15 dakika

Fiyat: {price:.2f}
Stop Loss: {sl:.2f}
Take Profit: {tp:.2f}

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
RSI: {rsi:.2f}
ATR: {atr:.2f}

Mum zamanı: {candle_time}

Otomatik işlem: KAPALI

Bu bir teknik analiz sinyalidir.
XM XAUUSD fiyatıyla birebir aynı olmayabilir.
"""

        send_email("XAUUSD " + signal + " SİNYALİ", message)
        print(message)

    else:
        print("WAIT - İşlem sinyali yok.")

    save_state(candle_time)


if __name__ == "__main__":
    run_bot()
