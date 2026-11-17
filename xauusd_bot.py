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

    if len(df) < 250:
        raise ValueError("Yeterli piyasa verisi yok.")

    return df


def calculate_indicators(df):

    # EMA
    df["ema20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    df["ema200"] = df["close"].ewm(
        span=200,
        adjust=False
    ).mean()

    # RSI
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR
    high_low = df["high"] - df["low"]
    high_close = (
        df["high"] - df["close"].shift()
    ).abs()

    low_close = (
        df["low"] - df["close"].shift()
    ).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    # ATR ortalaması
    df["atr_avg"] = df["atr"].rolling(50).mean()

    return df


def send_email(subject, body):

    if not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_APP_PASSWORD eksik.")

    msg = MIMEMultipart()

    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(
        MIMEText(body, "plain", "utf-8")
    )

    with smtplib.SMTP(
        "smtp.gmail.com",
        587,
        timeout=20
    ) as server:

        server.starttls()

        server.login(
            GMAIL_USER,
            GMAIL_APP_PASSWORD
        )

        server.sendmail(
            GMAIL_USER,
            GMAIL_USER,
            msg.as_string()
        )


def read_state():

    try:

        with open(STATE_FILE, "r") as f:
            return json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return {
            "last_processed": ""
        }


def save_state(candle_time):

    with open(STATE_FILE, "w") as f:

        json.dump(
            {
                "last_processed": candle_time
            },
            f
        )


def run_bot():

    print("XAUUSD güçlü sinyal botu başlatıldı.")

    df = get_market_data()
    df = calculate_indicators(df)

    # Son tamamlanmış mum
    candle = df.iloc[-2]

    # Bir önceki tamamlanmış mum
    previous = df.iloc[-3]

    candle_time = candle["time"].isoformat()

    state = read_state()

    if state.get("last_processed") == candle_time:

        print("Bu mum daha önce kontrol edildi.")
        return

    price = float(candle["close"])

    ema20 = float(candle["ema20"])
    ema50 = float(candle["ema50"])
    ema200 = float(candle["ema200"])

    previous_ema20 = float(previous["ema20"])
    previous_ema50 = float(previous["ema50"])

    rsi = float(candle["rsi"])
    atr = float(candle["atr"])
    atr_avg = float(candle["atr_avg"])

    candle_open = float(candle["open"])
    candle_high = float(candle["high"])
    candle_low = float(candle["low"])

    if any(pd.isna(x) for x in [
        ema20,
        ema50,
        ema200,
        rsi,
        atr,
        atr_avg
    ]):

        raise ValueError(
            "İndikatör verisi eksik."
        )

    # ------------------------------------------------
    # 1. TREND
    # ------------------------------------------------

    bullish_trend = (
        ema20 > ema50 > ema200
    )

    bearish_trend = (
        ema20 < ema50 < ema200
    )

    # EMA eğimi
    ema20_rising = (
        ema20 > previous_ema20
    )

    ema20_falling = (
        ema20 < previous_ema20
    )

    # ------------------------------------------------
    # 2. RSI FİLTRESİ
    # ------------------------------------------------

    buy_rsi = (
        52 <= rsi <= 68
    )

    sell_rsi = (
        32 <= rsi <= 48
    )

    # ------------------------------------------------
    # 3. FİYAT EMA20 ÜSTÜ / ALTI
    # ------------------------------------------------

    price_above_ema20 = (
        price > ema20
    )

    price_below_ema20 = (
        price < ema20
    )

    # ------------------------------------------------
    # 4. AŞIRI HAREKET FİLTRESİ
    # ------------------------------------------------

    candle_size = (
        candle_high - candle_low
    )

    normal_candle = (
        candle_size <= atr * 1.8
    )

    # ------------------------------------------------
    # 5. VOLATİLİTE FİLTRESİ
    # ------------------------------------------------

    enough_volatility = (
        atr >= atr_avg * 0.75
    )

    # ------------------------------------------------
    # PUANLAMA
    # ------------------------------------------------

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # BUY puanları
    if bullish_trend:
        buy_score += 3
        buy_reasons.append(
            "EMA20 > EMA50 > EMA200"
        )

    if ema20_rising:
        buy_score += 1
        buy_reasons.append(
            "EMA20 yükseliyor"
        )

    if buy_rsi:
        buy_score += 2
        buy_reasons.append(
            "RSI uygun"
        )

    if price_above_ema20:
        buy_score += 1
        buy_reasons.append(
            "Fiyat EMA20 üzerinde"
        )

    if normal_candle:
        buy_score += 1

    if enough_volatility:
        buy_score += 1
        buy_reasons.append(
            "Volatilite yeterli"
        )

    # SELL puanları
    if bearish_trend:
        sell_score += 3
        sell_reasons.append(
            "EMA20 < EMA50 < EMA200"
        )

    if ema20_falling:
        sell_score += 1
        sell_reasons.append(
            "EMA20 düşüyor"
        )

    if sell_rsi:
        sell_score += 2
        sell_reasons.append(
            "RSI uygun"
        )

    if price_below_ema20:
        sell_score += 1
        sell_reasons.append(
            "Fiyat EMA20 altında"
        )

    if normal_candle:
        sell_score += 1

    if enough_volatility:
        sell_score += 1
        sell_reasons.append(
            "Volatilite yeterli"
        )

    # ------------------------------------------------
    # SİNYAL
    # ------------------------------------------------

    signal = None
    strength = None
    score = 0
    reasons = []

    if (
        buy_score >= 7
        and buy_score > sell_score
    ):

        signal = "BUY"
        score = buy_score
        reasons = buy_reasons

        if buy_score >= 9:
            strength = "GÜÇLÜ"

        else:
            strength = "ORTA"

    elif (
        sell_score >= 7
        and sell_score > buy_score
    ):

        signal = "SELL"
        score = sell_score
        reasons = sell_reasons

        if sell_score >= 9:
            strength = "GÜÇLÜ"

        else:
            strength = "ORTA"

    # ------------------------------------------------
    # TP / SL
    # ------------------------------------------------

    if signal == "BUY":

        sl_distance = atr * 1.2

        tp1_distance = atr * 1.5
        tp2_distance = atr * 2.2

        sl = price - sl_distance
        tp1 = price + tp1_distance
        tp2 = price + tp2_distance

        risk_reward_1 = (
            tp1_distance / sl_distance
        )

        risk_reward_2 = (
            tp2_distance / sl_distance
        )

    elif signal == "SELL":

        sl_distance = atr * 1.2

        tp1_distance = atr * 1.5
        tp2_distance = atr * 2.2

        sl = price + sl_distance
        tp1 = price - tp1_distance
        tp2 = price - tp2_distance

        risk_reward_1 = (
            tp1_distance / sl_distance
        )

        risk_reward_2 = (
            tp2_distance / sl_distance
        )

    # ------------------------------------------------
    # MAIL
    # ------------------------------------------------

    if signal:

        reason_text = "\n".join(
            "- " + x
            for x in reasons
        )

        message = f"""
XAUUSD ALTIN SİNYALİ

━━━━━━━━━━━━━━━━━━

SİNYAL: {signal}
GÜÇ: {strength}
PUAN: {score}/9

━━━━━━━━━━━━━━━━━━

Fiyat: {price:.2f}

Stop Loss:
{sl:.2f}

Take Profit 1:
{tp1:.2f}

Take Profit 2:
{tp2:.2f}

Risk / Ödül:
TP1 = 1:{risk_reward_1:.2f}
TP2 = 1:{risk_reward_2:.2f}

━━━━━━━━━━━━━━━━━━

İNDİKATÖRLER

EMA20: {ema20:.2f}
EMA50: {ema50:.2f}
EMA200: {ema200:.2f}

RSI: {rsi:.2f}
ATR: {atr:.2f}

━━━━━━━━━━━━━━━━━━

SİNYAL NEDENLERİ

{reason_text}

━━━━━━━━━━━━━━━━━━

Zaman dilimi: 15 dakika

Veri kaynağı:
Yahoo Finance / GC=F

Otomatik işlem:
KAPALI

Bu sinyal teknik analiz amaçlıdır.
XM XAUUSD fiyatıyla birebir aynı
olmayabilir.

Mum zamanı:
{candle_time}
"""

        send_email(
            "XAUUSD " + signal + " " + strength,
            message
        )

        print(message)

    else:

        print(
            f"WAIT - BUY:{buy_score}/9 "
            f"SELL:{sell_score}/9"
        )

    save_state(candle_time)


if __name__ == "__main__":
    run_bot()