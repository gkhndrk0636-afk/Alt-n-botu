import os
import time
import smtplib
import MetaTrader5 as mt5
import pandas as pd

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# =========================================================
# AYARLAR
# =========================================================

SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M15

# Gmail adresin
GMAIL_USER = "gkhndrk0636@gmail.com"

# Gmail App Password GitHub'a yazılmayacak.
# Render / sunucu ortam değişkeninden alınacak.
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# XM MT5 bilgileri
XM_LOGIN = os.getenv("XM_LOGIN", "")
XM_PASSWORD = os.getenv("XM_PASSWORD", "")
XM_SERVER = os.getenv("XM_SERVER", "")

# Son gönderilen sinyali takip etmek için
last_signal = None
last_candle_time = None


# =========================================================
# GMAIL
# =========================================================

def send_email_notification(subject, message_body):

    try:

        if not GMAIL_APP_PASSWORD:
            print("HATA: GMAIL_APP_PASSWORD tanımlanmamış.")
            return False

        msg = MIMEMultipart()

        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        msg["Subject"] = subject

        msg.attach(
            MIMEText(
                message_body,
                "plain",
                "utf-8"
            )
        )

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=20
        )

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

        server.quit()

        print("Gmail bildirimi gönderildi.")
        return True

    except Exception as e:

        print("Gmail gönderim hatası:", e)
        return False


# =========================================================
# MT5 BAĞLANTISI
# =========================================================

def connect_mt5():

    print("MT5 bağlantısı başlatılıyor...")

    if not mt5.initialize():

        print(
            "MT5 initialize hatası:",
            mt5.last_error()
        )

        return False

    try:

        login = int(XM_LOGIN)

    except:

        print("HATA: XM_LOGIN geçerli değil.")
        return False

    authorized = mt5.login(
        login=login,
        password=XM_PASSWORD,
        server=XM_SERVER
    )

    if not authorized:

        print(
            "XM MT5 giriş başarısız:",
            mt5.last_error()
        )

        return False

    print("================================")
    print("XM MT5 BAĞLANTISI BAŞARILI")
    print("================================")

    print("Hesap:", login)
    print("Server:", XM_SERVER)

    return True


# =========================================================
# XAUUSD VERİSİ
# =========================================================

def get_market_data():

    rates = mt5.copy_rates_from_pos(
        SYMBOL,
        TIMEFRAME,
        0,
        250
    )

    if rates is None:

        print(
            "XAUUSD verisi alınamadı:",
            mt5.last_error()
        )

        return None

    if len(rates) < 60:

        print("Yeterli mum verisi yok.")
        return None

    df = pd.DataFrame(rates)

    df["time"] = pd.to_datetime(
        df["time"],
        unit="s"
    )

    return df


# =========================================================
# İNDİKATÖRLER
# =========================================================

def calculate_indicators(df):

    # EMA 20
    df["ema20"] = (
        df["close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    # EMA 50
    df["ema50"] = (
        df["close"]
        .ewm(
            span=50,
            adjust=False
        )
        .mean()
    )

    # -----------------------------------------------------
    # RSI 14
    # -----------------------------------------------------

    delta = df["close"].diff()

    gain = delta.where(
        delta > 0,
        0
    )

    loss = -delta.where(
        delta < 0,
        0
    )

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = (
        100 -
        (100 / (1 + rs))
    )

    # -----------------------------------------------------
    # ATR 14
    # -----------------------------------------------------

    high_low = (
        df["high"] -
        df["low"]
    )

    high_close = (
        df["high"] -
        df["close"].shift()
    ).abs()

    low_close = (
        df["low"] -
        df["close"].shift()
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        true_range
        .rolling(14)
        .mean()
    )

    return df


# =========================================================
# SİNYAL ÜRETİMİ
# =========================================================

def generate_signal(df):

    # Son KAPANMIŞ mum
    candle = df.iloc[-2]

    price = float(candle["close"])

    ema20 = float(candle["ema20"])
    ema50 = float(candle["ema50"])

    rsi = float(candle["rsi"])

    atr = float(candle["atr"])

    candle_time = candle["time"]

    # Eksik veri kontrolü
    if (
        pd.isna(ema20)
        or pd.isna(ema50)
        or pd.isna(rsi)
        or pd.isna(atr)
    ):
        return None

    # =====================================================
    # BUY
    # =====================================================

    if (
        ema20 > ema50
        and 50 <= rsi <= 70
    ):

        stop_loss = (
            price -
            (atr * 1.5)
        )

        take_profit = (
            price +
            (atr * 3.0)
        )

        return {
            "type": "BUY",
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "rsi": rsi,
            "atr": atr,
            "time": candle_time
        }

    # =====================================================
    # SELL
    # =====================================================

    if (
        ema20 < ema50
        and 30 <= rsi <= 50
    ):

        stop_loss = (
            price +
            (atr * 1.5)
        )

        take_profit = (
            price -
            (atr * 3.0)
        )

        return {
            "type": "SELL",
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "rsi": rsi,
            "atr": atr,
            "time": candle_time
        }

    return None


# =========================================================
# SİNYAL MESAJI
# =========================================================

def create_signal_message(signal):

    if signal["type"] == "BUY":
        emoji = "🟢"
    else:
        emoji = "🔴"

    message = f"""
{emoji} XAUUSD BOT SİNYALİ

================================

SİNYAL: {signal["type"]}

Fiyat:
{signal["price"]:.2f}

Stop Loss:
{signal["sl"]:.2f}

Take Profit:
{signal["tp"]:.2f}

RSI:
{signal["rsi"]:.2f}

ATR:
{signal["atr"]:.2f}

Mum:
{signal["time"]}

Zaman Dilimi:
15 Dakika

Risk Yönetimi:
1 : 2

================================

OTOMATİK İŞLEM:
KAPALI

Bu bildirim yalnızca sinyaldir.
"""

    return message


# =========================================================
# ANA BOT
# =========================================================

def run_bot():

    global last_signal
    global last_candle_time

    if not connect_mt5():

        print("MT5 bağlantısı kurulamadı.")
        return

    print("")
    print("================================")
    print("XAUUSD BOT AKTİF")
    print("Sembol:", SYMBOL)
    print("Zaman Dilimi: M15")
    print("Otomatik işlem: KAPALI")
    print("================================")
    print("")

    while True:

        try:

            df = get_market_data()

            if df is None:

                time.sleep(30)
                continue

            df = calculate_indicators(df)

            # Son kapanmış mum
            candle_time = df.iloc[-2]["time"]

            # Aynı mumu tekrar işlememek
            if candle_time != last_candle_time:

                last_candle_time = candle_time

                signal = generate_signal(df)

                if signal:

                    signal_type = signal["type"]

                    # Aynı yöndeki sinyali tekrar gönderme
                    if signal_type != last_signal:

                        message = create_signal_message(
                            signal
                        )

                        subject = (
                            f"XAUUSD {signal_type} Sinyali"
                        )

                        print(message)

                        send_email_notification(
                            subject,
                            message
                        )

                        last_signal = signal_type

                    else:

                        print(
                            candle_time,
                            "- Aynı sinyal zaten gönderildi:",
                            signal_type
                        )

                else:

                    print(
                        candle_time,
                        "- WAIT"
                    )

            time.sleep(20)

        except Exception as e:

            print(
                "BOT HATASI:",
                e
            )

            time.sleep(30)


# =========================================================
# PROGRAMI BAŞLAT
# =========================================================

if __name__ == "__main__":

    run_bot()
