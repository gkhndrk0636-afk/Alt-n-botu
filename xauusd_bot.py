import os
import json
import urllib.request
import smtplib
import pandas as pd

from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# =========================
# AYARLAR
# =========================

GMAIL_USER = "gkhndrk0636@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SYMBOL = "GC=F"

STATE_FILE = "state.json"
SIGNALS_FILE = "signals.json"

MAX_SIGNALS = 100


# =========================
# PİYASA VERİSİ
# =========================

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

    with urllib.request.urlopen(
        req,
        timeout=20
    ) as response:

        data = json.loads(
            response.read().decode()
        )

    result = data["chart"]["result"][0]

    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time": pd.to_datetime(
            timestamps,
            unit="s",
            utc=True
        ),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"]
    })

    df = (
        df.dropna()
        .reset_index(drop=True)
    )

    if len(df) < 250:
        raise ValueError(
            "Yeterli piyasa verisi yok."
        )

    return df


# =========================
# İNDİKATÖRLER
# =========================

def calculate_indicators(df):

    df["ema20"] = (
        df["close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    df["ema50"] = (
        df["close"]
        .ewm(
            span=50,
            adjust=False
        )
        .mean()
    )

    df["ema200"] = (
        df["close"]
        .ewm(
            span=200,
            adjust=False
        )
        .mean()
    )

    # RSI

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = (
        gain.rolling(14)
        .mean()
    )

    avg_loss = (
        loss.rolling(14)
        .mean()
    )

    rs = (
        avg_gain /
        avg_loss.replace(
            0,
            float("nan")
        )
    )

    df["rsi"] = (
        100 -
        (100 / (1 + rs))
    )

    # ATR

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

    tr = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        tr.rolling(14)
        .mean()
    )

    df["atr_avg"] = (
        df["atr"]
        .rolling(50)
        .mean()
    )

    return df


# =========================
# EMAIL
# =========================

def send_email(subject, body):

    if not GMAIL_APP_PASSWORD:
        raise ValueError(
            "GMAIL_APP_PASSWORD eksik."
        )

    msg = MIMEMultipart()

    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject

    msg.attach(
        MIMEText(
            body,
            "plain",
            "utf-8"
        )
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


# =========================
# STATE
# =========================

def read_state():

    try:

        with open(
            STATE_FILE,
            "r"
        ) as f:

            return json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return {
            "last_processed": "",
            "last_daily_report": ""
        }


def save_state(state):

    with open(
        STATE_FILE,
        "w"
    ) as f:

        json.dump(
            state,
            f
        )


# =========================
# SİNYALLER
# =========================

def read_signals():

    try:

        with open(
            SIGNALS_FILE,
            "r"
        ) as f:

            return json.load(f)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        return []


def save_signals(signals):

    with open(
        SIGNALS_FILE,
        "w"
    ) as f:

        json.dump(
            signals[-MAX_SIGNALS:],
            f,
            indent=2
        )


# =========================
# ESKİ SİNYALLERİ KONTROL
# =========================

def update_signal_results(
    df,
    signals
):

    changed = False

    for signal in signals:

        if signal.get(
            "result"
        ) != "OPEN":

            continue

        signal_time = pd.Timestamp(
            signal["time"]
        )

        future = df[
            df["time"] >
            signal_time
        ]

        future = future.iloc[:20]

        if len(future) == 0:
            continue

        sl = float(
            signal["sl"]
        )

        tp1 = float(
            signal["tp1"]
        )

        tp2 = float(
            signal["tp2"]
        )

        signal_type = (
            signal["signal"]
        )

        for _, candle in future.iterrows():

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            if signal_type == "BUY":

                hit_sl = (
                    low <= sl
                )

                hit_tp2 = (
                    high >= tp2
                )

                hit_tp1 = (
                    high >= tp1
                )

            else:

                hit_sl = (
                    high >= sl
                )

                hit_tp2 = (
                    low <= tp2
                )

                hit_tp1 = (
                    low <= tp1
                )

            # Aynı mumda iki seviye görülürse
            # güvenli tarafta SL kabul edilir.

            if hit_sl:

                signal["result"] = "SL"

                signal["result_price"] = sl

                signal["result_time"] = (
                    candle["time"].isoformat()
                )

                changed = True

                break

            elif hit_tp2:

                signal["result"] = "TP2"

                signal["result_price"] = tp2

                signal["result_time"] = (
                    candle["time"].isoformat()
                )

                changed = True

                break

            elif hit_tp1:

                signal["result"] = "TP1"

                signal["result_price"] = tp1

                signal["result_time"] = (
                    candle["time"].isoformat()
                )

                changed = True

                break

    return changed


# =========================
# PERFORMANS
# =========================

def calculate_stats(
    signals
):

    finished = [
        s for s in signals
        if s.get("result")
        in ["TP1", "TP2", "SL"]
    ]

    total = len(finished)

    wins = sum(
        1 for s in finished
        if s["result"]
        in ["TP1", "TP2"]
    )

    losses = sum(
        1 for s in finished
        if s["result"] == "SL"
    )

    open_count = sum(
        1 for s in signals
        if s.get("result") == "OPEN"
    )

    win_rate = (
        wins / total * 100
        if total > 0
        else 0
    )

    return (
        total,
        wins,
        losses,
        open_count,
        win_rate
    )


# =========================
# GÜNLÜK RAPOR
# =========================

def send_daily_report(
    signals,
    state
):

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    if (
        state.get(
            "last_daily_report"
        ) == today
    ):

        print(
            "Bugünün raporu zaten gönderildi."
        )

        return

    today_signals = []

    for signal in signals:

        signal_time = pd.Timestamp(
            signal["time"]
        )

        if (
            signal_time
            .date()
            .isoformat()
            == today
        ):

            today_signals.append(
                signal
            )

    total = len(
        today_signals
    )

    buy = sum(
        1 for s in today_signals
        if s["signal"] == "BUY"
    )

    sell = sum(
        1 for s in today_signals
        if s["signal"] == "SELL"
    )

    tp1 = sum(
        1 for s in today_signals
        if s.get("result") == "TP1"
    )

    tp2 = sum(
        1 for s in today_signals
        if s.get("result") == "TP2"
    )

    sl = sum(
        1 for s in today_signals
        if s.get("result") == "SL"
    )

    open_count = sum(
        1 for s in today_signals
        if s.get("result") == "OPEN"
    )

    finished = (
        tp1 + tp2 + sl
    )

    if finished > 0:

        success = (
            (tp1 + tp2)
            / finished
            * 100
        )

    else:

        success = 0

    (
        all_total,
        all_wins,
        all_losses,
        all_open,
        all_success
    ) = calculate_stats(
        signals
    )

    body = f"""
XAUUSD GÜNLÜK SİNYAL RAPORU

━━━━━━━━━━━━━━━━━━

BUGÜN

Toplam sinyal:
{total}

BUY:
{buy}

SELL:
{sell}

━━━━━━━━━━━━━━━━━━

SONUÇLAR

TP1:
{tp1}

TP2:
{tp2}

STOP LOSS:
{sl}

Açık:
{open_count}

Bugünkü başarı:
%{success:.1f}

━━━━━━━━━━━━━━━━━━

GENEL PERFORMANS

Tamamlanan:
{all_total}

Kazanan:
{all_wins}

Kaybeden:
{all_losses}

Açık:
{all_open}

Genel başarı:
%{all_success:.1f}

━━━━━━━━━━━━━━━━━━

Sistem:
XAUUSD sinyal botu

Zaman dilimi:
15 dakika

Otomatik işlem:
KAPALI

Veri kaynağı:
Yahoo Finance / GC=F

Not:
GC=F ile XM XAUUSD fiyatı birebir
aynı olmayabilir.

Bu rapor teknik analiz
performans takibi içindir.
"""

    send_email(
        "XAUUSD Günlük Rapor",
        body
    )

    state[
        "last_daily_report"
    ] = today

    save_state(
        state

    )

    print(
        "Günlük rapor gönderildi."
    )


# =========================
# YENİ SİNYAL
# =========================

def create_signal(
    df,
    candle
):

    previous = df.iloc[-3]

    price = float(
        candle["close"]
    )

    ema20 = float(
        candle["ema20"]
    )

    ema50 = float(
        candle["ema50"]
    )

    ema200 = float(
        candle["ema200"]
    )

    prev_ema20 = float(
        previous["ema20"]
    )

    rsi = float(
        candle["rsi"]
    )

    atr = float(
        candle["atr"]
    )

    atr_avg = float(
        candle["atr_avg"]
    )

    candle_size = (
        float(candle["high"])
        -
        float(candle["low"])
    )

    normal_candle = (
        candle_size
        <= atr * 1.8
    )

    enough_volatility = (
        atr >= atr_avg * 0.75
    )

    bullish = (
        ema20 >
        ema50 >
        ema200
    )

    bearish = (
        ema20 <
        ema50 <
        ema200
    )

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # BUY

    if bullish:

        buy_score += 3

        buy_reasons.append(
            "EMA20 > EMA50 > EMA200"
        )

    if ema20 > prev_ema20:

        buy_score += 1

        buy_reasons.append(
            "EMA20 yükseliyor"
        )

    if 52 <= rsi <= 68:

        buy_score += 2

        buy_reasons.append(
            "RSI uygun"
        )

    if price > ema20:

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

    # SELL

    if bearish:

        sell_score += 3

        sell_reasons.append(
            "EMA20 < EMA50 < EMA200"
        )

    if ema20 < prev_ema20:

        sell_score += 1

        sell_reasons.append(
            "EMA20 düşüyor"
        )

    if 32 <= rsi <= 48:

        sell_score += 2

        sell_reasons.append(
            "RSI uygun"
        )

    if price < ema20:

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

        strength = (
            "GÜÇLÜ"
            if buy_score >= 9
            else "ORTA"
        )

    elif (
        sell_score >= 7
        and sell_score > buy_score
    ):

        signal = "SELL"
        score = sell_score
        reasons = sell_reasons

        strength = (
            "GÜÇLÜ"
            if sell_score >= 9
            else "ORTA"
        )

    if not signal:

        return None

    # TP / SL

    sl_distance = (
        atr * 1.2
    )

    tp1_distance = (
        atr * 1.5
    )

    tp2_distance = (
        atr * 2.2
    )

    if signal == "BUY":

        sl = (
            price -
            sl_distance
        )

        tp1 = (
            price +
            tp1_distance
        )

        tp2 = (
            price +
            tp2_distance
        )

    else:

        sl = (
            price +
            sl_distance
        )

        tp1 = (
            price -
            tp1_distance
        )

        tp2 = (
            price -
            tp2_distance
        )

    return {

        "time":
            candle["time"].isoformat(),

        "signal":
            signal,

        "strength":
            strength,

        "score":
            score,

        "entry":
            round(
                price,
                2
            ),

        "sl":
            round(
                sl,
                2
            ),

        "tp1":
            round(
                tp1,
                2
            ),

        "tp2":
            round(
                tp2,
                2
            ),

        "atr":
            round(
                atr,
                2
            ),

        "rsi":
            round(
                rsi,
                2
            ),

        "ema20":
            round(
                ema20,
                2
            ),

        "ema50":
            round(
                ema50,
                2
            ),

        "ema200":
            round(
                ema200,
                2
            ),

        "result":
            "OPEN",

        "reasons":
            reasons
    }


# =========================
# ANA FONKSİYON
# =========================

def run_bot():

    print(
        "XAUUSD sinyal botu başlatıldı."
    )

    df = get_market_data()

    df = calculate_indicators(
        df
    )

    state = read_state()

    signals = read_signals()

    # Eski sinyalleri güncelle

    changed = update_signal_results(
        df,
        signals
    )

    if changed:

        save_signals(
            signals
        )

    # Son tamamlanmış mum

    candle = df.iloc[-2]

    candle_time = (
        candle["time"].isoformat()
    )

    # Aynı mum tekrar işlenmesin

    if (
        state.get(
            "last_processed"
        )
        != candle_time
    ):

        new_signal = create_signal(
            df,
            candle
        )

        if new_signal:

            already_exists = any(
                s.get("time")
                == candle_time
                for s in signals
            )

            if not already_exists:

                signals.append(
                    new_signal
                )

                save_signals(
                    signals
                )

                reasons = "\n".join(
                    "- " + r
                    for r in
                    new_signal[
                        "reasons"
                    ]
                )

                body = f"""
XAUUSD ALTIN SİNYALİ

━━━━━━━━━━━━━━━━━━

Sinyal:
{new_signal["signal"]}

Güç:
{new_signal["strength"]}

Puan:
{new_signal["score"]}/9

━━━━━━━━━━━━━━━━━━

Entry:
{new_signal["entry"]:.2f}

Stop Loss:
{new_signal["sl"]:.2f}

Take Profit 1:
{new_signal["tp1"]:.2f}

Take Profit 2:
{new_signal["tp2"]:.2f}

━━━━━━━━━━━━━━━━━━

RSI:
{new_signal["rsi"]:.2f}

ATR:
{new_signal["atr"]:.2f}

EMA20:
{new_signal["ema20"]:.2f}

EMA50:
{new_signal["ema50"]:.2f}

EMA200:
{new_signal["ema200"]:.2f}

━━━━━━━━━━━━━━━━━━

Sinyal nedenleri:

{reasons}

━━━━━━━━━━━━━━━━━━

15 dakika grafik

Veri:
Yahoo Finance / GC=F

Otomatik işlem:
KAPALI

Bu teknik analiz sinyalidir.
XM XAUUSD fiyatıyla birebir
aynı olmayabilir.

Mum zamanı:
{candle_time}
"""

                send_email(
                    "XAUUSD "
                    + new_signal[
                        "signal"
                    ]
                    + " "
                    + new_signal[
                        "strength"
                    ],
                    body
                )

                print(
                    body
                )

        else:

            print(
                "WAIT - Güçlü sinyal yok."
            )

        state[
            "last_processed"
        ] = candle_time

        save_state(
            state
        )

    else:

        print(
            "Bu mum daha önce işlendi."
        )


# =========================
# GÜNLÜK RAPORU ÇALIŞTIR
# =========================

if __name__ == "__main__":

    run_bot()

    # GitHub Actions günlük rapor
    # göndermek istediğinde:
    if os.getenv(
        "DAILY_REPORT"
    ) == "1":

        signals = read_signals()

        state = read_state()

        send_daily_report(
            signals,
            state
        )