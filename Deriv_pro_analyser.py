import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import time
from datetime import datetime
import ta
import websocket
import json

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(page_title="Flexa Deriv Live Analyser", layout="wide", initial_sidebar_state="expanded")

# Dark mode style
st.markdown(
    """
    <style>
    body {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stApp {
        background-color: #0e1117;
    }
    .stMarkdown, .stText, .stTitle, .stHeader, .stSubheader {
        color: #fafafa !important;
    }
    .stDataFrame, .stTable {
        background-color: #161b22;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------
# Sidebar Inputs
# -------------------------------
st.sidebar.title("⚙️ Flexa-Deriv Settings")

# Deriv symbol list
default_symbols = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "Volatility_10", "Volatility_25", "Volatility_50", "Volatility_75", "Volatility_100",
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "BTCUSD", "ETHUSD"
]

symbol = st.sidebar.selectbox("Select symbol", default_symbols)
custom_symbol = st.sidebar.text_input("or enter custom symbol", "")
if custom_symbol.strip():
    symbol = custom_symbol.strip()

deriv_token = st.sidebar.text_input("Deriv API Token (optional)", type="password")

# Telegram settings
st.sidebar.subheader("🔔 Telegram Alerts")
tg_token = st.sidebar.text_input("Bot Token (optional)", type="password")
tg_chat = st.sidebar.text_input("Chat ID (optional)", "")
enable_alerts = st.sidebar.checkbox("Enable Telegram alerts")

# -------------------------------
# Functions
# -------------------------------

def send_telegram_message(message):
    if tg_token and tg_chat:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        payload = {"chat_id": tg_chat, "text": message}
        try:
            requests.post(url, json=payload)
        except:
            pass

def get_deriv_data(symbol, count=200):
    url = "https://deriv-api.com/api/v2/ticks_history"
    params = {"ticks_history": symbol, "count": count, "end": "latest", "style": "candles", "granularity": 60}
    r = requests.get(url, params=params)
    data = r.json().get("candles", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["epoch"] = pd.to_datetime(df["epoch"], unit="s")
    df.rename(columns={"epoch": "time"}, inplace=True)
    return df

def calculate_indicators(df):
    df["EMA_10"] = ta.trend.ema_indicator(df["close"], 10)
    df["SMA_20"] = ta.trend.sma_indicator(df["close"], 20)
    df["RSI"] = ta.momentum.rsi(df["close"], 14)
    macd = ta.trend.MACD(df["close"])
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    boll = ta.volatility.BollingerBands(df["close"], 20)
    df["BB_high"] = boll.bollinger_hband()
    df["BB_low"] = boll.bollinger_lband()
    return df

def get_signal(df):
    latest = df.iloc[-1]
    if latest["RSI"] < 30 and latest["close"] < latest["BB_low"]:
        return "BUY"
    elif latest["RSI"] > 70 and latest["close"] > latest["BB_high"]:
        return "SELL"
    return "NEUTRAL"

# -------------------------------
# Main App
# -------------------------------
st.title("💹 Flexa Deriv Live Trading Analyser")
st.caption("Real-time analysis for Deriv markets — with Dark Mode + Telegram Alerts")

placeholder_chart = st.empty()
placeholder_text = st.empty()

start_button = st.sidebar.button("🚀 Connect & Start")

if start_button:
    st.sidebar.success(f"Streaming data for {symbol} ...")
    while True:
        df = get_deriv_data(symbol)
        if df.empty:
            st.error("No data received — check symbol or connection.")
            break

        df = calculate_indicators(df)
        signal = get_signal(df)

        # Plot
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df["time"],
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name=symbol
        ))
        fig.add_trace(go.Scatter(x=df["time"], y=df["EMA_10"], mode="lines", line=dict(color="orange"), name="EMA 10"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["SMA_20"], mode="lines", line=dict(color="blue"), name="SMA 20"))

        fig.update_layout(
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            height=500,
            margin=dict(l=20, r=20, t=40, b=20)
        )

        placeholder_chart.plotly_chart(fig, use_container_width=True)

        # Signal text
        placeholder_text.markdown(f"### 🧭 Current Signal: **{signal}**")
        if signal in ["BUY", "SELL"] and enable_alerts:
            send_telegram_message(f"{symbol} — {signal} signal at {datetime.now().strftime('%H:%M:%S')}")

        time.sleep(30)
