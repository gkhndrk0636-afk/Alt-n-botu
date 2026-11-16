import os
import json
import urllib.request
import smtplib
import traceback
import pandas as pd

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

SYMBOL = "GC=F"
STATE_FILE = "state.json"


def get_market_data():
    url = (
        "https://yahoo.com"
        + SYMBOL
        + "?interval=15m&range=5d"
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode())

    chart_result = data.get("chart").get("result")
    result = chart_result.pop(0)
    timestamps = result.get("timestamp")
    quote_list = result.get("indicators").get("quote")
    quote = quote_list.pop(0)

    df = pd.DataFrame({
        "time": pd.to_datetime(timestamps, unit="s", utc=True),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close")
    })

    df = df.dropna().reset_index(drop=True)

    if len(df) < 205:
        raise ValueError("Yeterli piyasa verisi yok.")

    return df


def calculate_indicators(df):
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

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

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df


def send_email(subject, body):
    if not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_APP_PASSWORD eksik! GitHub Secrets ayarını kontrol edin.")

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("://gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())


def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return {
                "last_processed": data.get("last_processed", ""),
                "last_signal": data.get("last_signal", "NONE")
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_processed": "", "last_signal": "NONE"}


def save_state(candle_time, last_signal):
    with open(STATE_FILE, "w") as f:
        json.dump({
            "last_processed": candle_time,
            "last_signal": last_signal
        }, f, indent=2)


def run_bot():
    print("XAUUSD sinyal botu başlatıldı.")

    df = get_market_data()
    df = calculate_indicators(df)

    closed_candles = df.iloc[:-1].copy()

    if TEST_MODE:
        latest = closed_candles.iloc[-1]
        test_msg = f"""
XAUUSD BOT TEST BİLDİRİMİ

Bot başarıyla çalıştı ve EMA200 korumalı veri çekildi.
Son Kapanan Fiyat: {float(latest['close']):.2f}
EMA20: {float(latest['ema20']):.2f} | EMA50: {float(latest['ema50']):.2f}
EMA200 (Ana Trend): {float(latest['ema200']):.2f}
RSI: {float(latest['rsi']):.2f} | ATR: {float(latest['atr']):.2f}
Mum Zamanı (UTC): {latest['time'].isoformat()}
"""
        send_email("XAUUSD Bot - Test Başarılı", test_msg)
        print("Test e-postası gönderildi.")
        return

    state = read_state()
    last_processed = state["last_processed"]
    last_signal = state["last_signal"]

    if not last_processed:
        candles_to_check = closed_candles.iloc[-1:]
    else:
        candles_to_check = closed_candles[
            closed_candles["time"].apply(lambda x: x.isoformat() > last_processed)
        ]

    if candles_to_check.empty:
        print("Yeni kapanmış mum yok. Beklemede.")
        return

    latest_time = last_processed

    for _, candle in candles_to_check.iterrows():
        candle_time = candle["time"].isoformat()
        latest_time = candle_time

        price = float(candle["close"])
        ema20 = float(candle["ema20"])
        ema50 = float(candle["ema50"])
        ema200 = float(candle["ema200"])
        rsi = float(candle["rsi"])
        atr = float(candle["atr"])

        if pd.isna(rsi) or pd.isna(atr):
            continue

        signal = None

        if ema20 > ema50 and price > ema200 and 50 <= rsi <= 70:
            signal = "BUY"
            sl = price - atr * 1.5
            tp = price + atr * 3
        elif ema20 < ema50 and price < ema200 and 30 <= rsi <= 50:
            signal = "SELL"
            sl = price + atr * 1.5
            tp = price - atr * 3

        if signal and signal != last_signal:
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
EMA200: {ema200:.2f}
RSI: {rsi:.2f}
ATR: {atr:.2f}

Mum zamanı (UTC): {candle_time}
Otomatik işlem: KAPALI
"""
            send_email(f"XAUUSD {signal} SİNYALİ ({price:.2f})", message)
            print(f"{candle_time} için {signal} sinyali gönderildi.")
            last_signal = signal
        elif signal == last_signal:
            print(f"{candle_time} -> {signal} devam ediyor (tekrar mail atılmadı).")
        else:
            print(f"{candle_time} -> WAIT (Fiyat: {price:.2f}, EMA200: {ema200:.2f}, RSI: {rsi:.2f})")
            last_signal = "NONE"

    save_state(latest_time, last_signal)


if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        error_details = traceback.format_exc()
        print("HATA OLUŞTU:\n", error_details)
        try:
            send_email("XAUUSD Bot Hata Bildirimi", f"Bot çalışırken hata oluştu:\n\n{error_details}")
        except Exception:
            pass
        raise
