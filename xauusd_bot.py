import os
import json
import urllib.request
import smtplib
import pandas as pd

from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# =========================================================
# AYARLAR
# =========================================================

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SYMBOL = "GC=F"
INTERVAL = "15m"

MIN_SCORE = 6

SL_ATR = 1.2
TP1_ATR = 1.5
TP2_ATR = 2.0

LOOKAHEAD_CANDLES = 20

STATE_FILE = "state.json"
SIGNALS_FILE = "signals.json"

DAILY_REPORT = os.getenv("DAILY_REPORT", "0")


# =========================================================
# MARKET DATA
# =========================================================

def get_market_data():

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{SYMBOL}?interval={INTERVAL}&range=5d"
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
        "timestamp": pd.to_datetime(
            timestamps,
            unit="s",
            utc=True
        ),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
    })

    df = df.dropna().reset_index(drop=True)

    if len(df) < 250:
        raise Exception("Yeterli piyasa verisi alınamadı.")

    return df


# =========================================================
# INDICATORS
# =========================================================

def calculate_indicators(df):

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

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df["rsi"] = 100 - (100 / (1 + rs))

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    df["atr_avg"] = df["atr"].rolling(50).mean()

    return df


# =========================================================
# EMAIL
# =========================================================

def send_email(subject, body):

    if not GMAIL_APP_PASSWORD:
        print("GMAIL_APP_PASSWORD bulunamadı.")
        return

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:

        server.starttls()

        server.login(
            GMAIL_USER,
            GMAIL_APP_PASSWORD
        )

        server.send_message(msg)

    print("E-posta gönderildi.")


# =========================================================
# JSON DOSYALARI
# =========================================================

def load_json(filename, default):

    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json(filename, data):

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# GÜVEN PUANI
# =========================================================

def calculate_confidence(score):

    confidence_map = {
        6: 65,
        7: 75,
        8: 85,
        9: 92
    }

    return confidence_map.get(score, 50)


def strength_from_score(score):

    if score == 9:
        return "ÇOK GÜÇLÜ"

    if score == 8:
        return "GÜÇLÜ"

    if score == 7:
        return "İYİ"

    return "ORTA"


# =========================================================
# SİNYAL OLUŞTUR
# =========================================================

def create_signal(df):

    # Son tamamlanmış mum
    row = df.iloc[-2]
    prev = df.iloc[-3]

    price = float(row["close"])

    ema20 = float(row["ema20"])
    ema50 = float(row["ema50"])
    ema200 = float(row["ema200"])

    rsi = float(row["rsi"])

    atr = float(row["atr"])
    atr_avg = float(row["atr_avg"])

    candle_size = abs(
        float(row["close"]) - float(row["open"])
    )

    score_buy = 0
    score_sell = 0

    buy_reasons = []
    sell_reasons = []

    # -----------------------------------------------------
    # BUY TREND
    # -----------------------------------------------------

    if ema20 > ema50 and ema50 > ema200:

        score_buy += 3
        buy_reasons.append("EMA trendi yukarı")

    # -----------------------------------------------------
    # SELL TREND
    # -----------------------------------------------------

    if ema20 < ema50 and ema50 < ema200:

        score_sell += 3
        sell_reasons.append("EMA trendi aşağı")

    # -----------------------------------------------------
    # EMA EĞİMİ
    # -----------------------------------------------------

    if ema20 > float(prev["ema20"]):

        score_buy += 1
        buy_reasons.append("EMA20 yükseliyor")

    elif ema20 < float(prev["ema20"]):

        score_sell += 1
        sell_reasons.append("EMA20 düşüyor")

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    if 52 <= rsi <= 68:

        score_buy += 2
        buy_reasons.append(
            f"RSI uygun ({rsi:.1f})"
        )

    if 32 <= rsi <= 48:

        score_sell += 2
        sell_reasons.append(
            f"RSI uygun ({rsi:.1f})"
        )

    # -----------------------------------------------------
    # FİYAT / EMA20
    # -----------------------------------------------------

    if price > ema20:

        score_buy += 1
        buy_reasons.append("Fiyat EMA20 üzerinde")

    elif price < ema20:

        score_sell += 1
        sell_reasons.append("Fiyat EMA20 altında")

    # -----------------------------------------------------
    # NORMAL MUM
    # -----------------------------------------------------

    if candle_size <= atr * 1.8:

        score_buy += 1
        score_sell += 1

        buy_reasons.append("Mum boyutu normal")
        sell_reasons.append("Mum boyutu normal")

    # -----------------------------------------------------
    # VOLATİLİTE
    # -----------------------------------------------------

    if atr >= atr_avg * 0.8 and atr <= atr_avg * 1.8:

        score_buy += 1
        score_sell += 1

        buy_reasons.append("Volatilite uygun")
        sell_reasons.append("Volatilite uygun")

    # -----------------------------------------------------
    # YÖN SEÇ
    # -----------------------------------------------------

    if score_buy >= MIN_SCORE and score_buy > score_sell:

        score = score_buy
        direction = "BUY"
        reasons = buy_reasons

        sl = price - (SL_ATR * atr)
        tp1 = price + (TP1_ATR * atr)
        tp2 = price + (TP2_ATR * atr)

    elif score_sell >= MIN_SCORE and score_sell > score_buy:

        score = score_sell
        direction = "SELL"
        reasons = sell_reasons

        sl = price + (SL_ATR * atr)
        tp1 = price - (TP1_ATR * atr)
        tp2 = price - (TP2_ATR * atr)

    else:

        return None

    confidence = calculate_confidence(score)
    strength = strength_from_score(score)

    signal = {
        "id": datetime.now(timezone.utc).strftime(
            "%Y%m%d%H%M%S"
        ),

        "time": row["timestamp"].isoformat(),

        "direction": direction,

        "score": score,

        "confidence": confidence,

        "strength": strength,

        "entry": round(price, 2),

        "sl": round(sl, 2),

        "tp1": round(tp1, 2),

        "tp2": round(tp2, 2),

        "atr": round(atr, 2),

        "rsi": round(rsi, 2),

        "ema20": round(ema20, 2),

        "ema50": round(ema50, 2),

        "ema200": round(ema200, 2),

        "reasons": reasons,

        "result": "OPEN",

        "result_time": None
    }

    return signal


# =========================================================
# SİNYAL SONUÇLARINI KONTROL ET
# =========================================================

def update_signal_results(df, signals):

    changed = False

    for signal in signals:

        if signal["result"] != "OPEN":
            continue

        signal_time = pd.Timestamp(
            signal["time"]
        )

        future = df[
            df["timestamp"] > signal_time
        ].head(LOOKAHEAD_CANDLES)

        for _, candle in future.iterrows():

            high = float(candle["high"])
            low = float(candle["low"])

            if signal["direction"] == "BUY":

                hit_sl = low <= signal["sl"]
                hit_tp2 = high >= signal["tp2"]
                hit_tp1 = high >= signal["tp1"]

            else:

                hit_sl = high >= signal["sl"]
                hit_tp2 = low <= signal["tp2"]
                hit_tp1 = low <= signal["tp1"]

            # Aynı mum içinde hem SL hem hedef görülürse
            # sıralama bilinmediği için konservatif olarak SL
            if hit_sl:

                signal["result"] = "SL"
                signal["result_time"] = candle[
                    "timestamp"
                ].isoformat()

                changed = True
                break

            if hit_tp2:

                signal["result"] = "TP2"
                signal["result_time"] = candle[
                    "timestamp"
                ].isoformat()

                changed = True
                break

            if hit_tp1:

                signal["result"] = "TP1"
                signal["result_time"] = candle[
                    "timestamp"
                ].isoformat()

                changed = True
                break

        # 20 mum içinde sonuç yoksa
        # henüz açık kabul ediyoruz

    return changed


# =========================================================
# İSTATİSTİK
# =========================================================

def calculate_stats(signals):

    total = len(signals)

    buy = sum(
        1 for s in signals
        if s["direction"] == "BUY"
    )

    sell = sum(
        1 for s in signals
        if s["direction"] == "SELL"
    )

    tp1 = sum(
        1 for s in signals
        if s["result"] == "TP1"
    )

    tp2 = sum(
        1 for s in signals
        if s["result"] == "TP2"
    )

    sl = sum(
        1 for s in signals
        if s["result"] == "SL"
    )

    open_count = sum(
        1 for s in signals
        if s["result"] == "OPEN"
    )

    closed = tp1 + tp2 + sl

    wins = tp1 + tp2

    success = (
        (wins / closed) * 100
        if closed > 0
        else 0
    )

    return {
        "total": total,
        "buy": buy,
        "sell": sell,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "open": open_count,
        "success": success
    }


# =========================================================
# GÜNLÜK RAPOR
# =========================================================

def send_daily_report(signals):

    now = datetime.now(timezone.utc)

    today = now.date()

    today_signals = []

    for s in signals:

        signal_date = pd.Timestamp(
            s["time"]
        ).date()

        if signal_date == today:

            today_signals.append(s)

    stats = calculate_stats(today_signals)
    overall = calculate_stats(signals)

    body = f"""
XAUUSD BOT GÜNLÜK RAPOR

Tarih: {today}

BUGÜN
----------------------------

Toplam sinyal: {stats["total"]}

BUY: {stats["buy"]}
SELL: {stats["sell"]}

TP1: {stats["tp1"]}
TP2: {stats["tp2"]}
SL: {stats["sl"]}
AÇIK: {stats["open"]}

Başarı oranı:
%{stats["success"]:.1f}


GENEL
----------------------------

Toplam sinyal: {overall["total"]}

BUY: {overall["buy"]}
SELL: {overall["sell"]}

TP1: {overall["tp1"]}
TP2: {overall["tp2"]}
SL: {overall["sl"]}
AÇIK: {overall["open"]}

Genel başarı:
%{overall["success"]:.1f}
"""

    send_email(
        "XAUUSD Bot Günlük Rapor",
        body
    )


# =========================================================
# SİNYAL E-POSTASI
# =========================================================

def send_signal_email(signal):

    direction = signal["direction"]

    emoji = "🟢" if direction == "BUY" else "🔴"

    body = f"""
{emoji} XAUUSD {direction}

GÜVEN: %{signal["confidence"]}
SİNYAL SEVİYESİ: {signal["strength"]}

Skor: {signal["score"]}/9

Giriş:
{signal["entry"]}

SL:
{signal["sl"]}

TP1:
{signal["tp1"]}

TP2:
{signal["tp2"]}


TEKNİK VERİLER
----------------------------

RSI:
{signal["rsi"]}

ATR:
{signal["atr"]}

EMA20:
{signal["ema20"]}

EMA50:
{signal["ema50"]}

EMA200:
{signal["ema200"]}


SİNYAL NEDENLERİ
----------------------------

"""

    for reason in signal["reasons"]:

        body += f"✓ {reason}\n"

    body += """

Not:
Bu bir teknik analiz sinyalidir.
Otomatik işlem yapılmamaktadır.
"""

    send_email(
        f"XAUUSD {direction} - %{signal['confidence']} Güven",
        body
    )


# =========================================================
# BOT
# =========================================================

def run_bot():

    print("XAUUSD bot çalışıyor...")

    df = get_market_data()
    df = calculate_indicators(df)

    state = load_json(
        STATE_FILE,
        {
            "last_processed": None,
            "last_daily_report": None
        }
    )

    signals = load_json(
        SIGNALS_FILE,
        []
    )

    # Önce eski sinyallerin sonuçlarını kontrol et
    update_signal_results(
        df,
        signals
    )

    # Aynı tamamlanmış mumu tekrar işleme
    candle_time = df.iloc[-2]["timestamp"].isoformat()

    if state["last_processed"] != candle_time:

        signal = create_signal(df)

        if signal:

            signals.append(signal)

            # Son 200 sinyali sakla
            signals = signals[-200:]

            send_signal_email(signal)

            print(
                f"SİNYAL: {signal['direction']} "
                f"| Güven: %{signal['confidence']} "
                f"| Skor: {signal['score']}/9"
            )

        else:

            print(
                "Bu mumda uygun sinyal yok."
            )

        state["last_processed"] = candle_time

    else:

        print(
            "Bu mum daha önce işlendi."
        )

    # Günlük rapor
    if DAILY_REPORT == "1":

        report_date = (
            datetime.now(timezone.utc)
            .date()
            .isoformat()
        )

        if state.get("last_daily_report") != report_date:

            send_daily_report(signals)

            state["last_daily_report"] = report_date

    save_json(
        SIGNALS_FILE,
        signals
    )

    save_json(
        STATE_FILE,
        state
    )

    print("Bot tamamlandı.")


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    run_bot()