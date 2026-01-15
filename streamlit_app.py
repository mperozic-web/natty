import streamlit as st
import pandas as pd
import requests
import io
import json
import os
import feedparser
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz
from groq import Groq
import urllib.parse
import re

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V118", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .ai-analysis-box { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #00FF00; padding: 25px; background-color: #051A05; border-radius: 10px; margin-bottom: 25px; border-left: 10px solid #00FF00; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .stat-card { background: #111; border: 1px solid #333; padding: 15px; border-radius: 8px; text-align: center; min-height: 120px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; color: #FFF; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 6px; text-align: center; }
    .run-tag { background: #008CFF; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
DB_FILE = "sniper_v118_db.json"

def load_db():
    defaults = {
        "api_keys": {"eia": "", "groq": ""},
        "eia_data": {"current": 0, "prev": 0, "net_change": 0, "five_year_avg": 0},
        "cot_data": {"mm_net": 0, "comm_net": 0, "retail_net": 0},
        "archive": {},
        "last_run_processed": ""
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding='utf-8') as f:
                d = json.load(f)
                return {**defaults, **d}
        except: return defaults
    return defaults

def save_db(data):
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

if 'db' not in st.session_state: st.session_state.db = load_db()

# --- API & DATA FETCHERS ---

def fetch_eia_pure(key):
    if not key: return None
    try:
        # 1. Dohvaćanje zadnjih 260 tjedana (5 godina) za Lower 48
        url = f"https://api.eia.gov/v2/natural-gas/stor/wkly/data/?api_key={key}&frequency=weekly&data[]=value&facets[series][]=NW2_EPG0_SWO_R48_BCF&sort[0][column]=period&sort[0][direction]=desc&length=260"
        r = requests.get(url, timeout=15).json()
        raw_data = r['response']['data']
        
        # Trenutno i prethodno očitovanje
        curr_val = int(raw_data[0]['value'])
        prev_val = int(raw_data[1]['value'])
        
        # 2. Logika za izračun 5y prosjeka za OVAJ tjedan
        # Uzimamo vrijednosti na pozicijama 52, 104, 156, 208 (isti tjedan prošle 4 godine)
        # i trenutnu vrijednost (ili tjedan 260 ako želimo punih 5 godina unazad)
        historical_points = [
            int(raw_data[52]['value']),
            int(raw_data[104]['value']),
            int(raw_data[156]['value']),
            int(raw_data[208]['value']),
            int(raw_data[259]['value'])
        ]
        avg_5y = sum(historical_points) / len(historical_points)
        
        return {
            "current": curr_val,
            "prev": prev_val,
            "net_change": curr_val - prev_val,
            "five_year_avg": round(avg_5y, 1)
        }
    except Exception as e:
        st.sidebar.error(f"EIA Error: {e}")
        return None

def fetch_cot_pure():
    try:
        url = "https://www.cftc.gov/dea/new/disagg_gas_so_wk.txt"
        r = requests.get(url, timeout=15).text
        if "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE" not in r: return None
        
        parts = re.split(r'NATURAL GAS - NEW YORK MERCANTILE EXCHANGE', r)
        section = parts[1] if len(parts) > 1 else ""
        
        def extract(pattern, text):
            match = re.search(pattern, text)
            return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

        mm_l, mm_s = extract(r'Managed Money\s+(\d+)\s+(\d+)', section)
        prod_l, prod_s = extract(r'Producer/Merchant/Processor/User\s+(\d+)\s+(\d+)', section)
        swap_l, swap_s = extract(r'Swap Dealers\s+(\d+)\s+(\d+)', section)
        ret_l, ret_s = extract(r'Nonreportable Positions\s+(\d+)\s+(\d+)', section)
        
        return {
            "mm_net": mm_l - mm_s,
            "comm_net": (prod_l + swap_l) - (prod_short + swap_short) if 'prod_short' in locals() else (prod_l + swap_l) - (prod_s + swap_s),
            "retail_net": ret_l - ret_s
        }
    except: return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Sniper API Control")
    e_api = st.text_input("EIA API Key", value=st.session_state.db['api_keys']['eia'], type="password")
    g_api = st.text_input("Groq API Key", value=st.session_state.db['api_keys']['groq'], type="password")
    
    if st.button("🔄 RE-SYNC PURE API DATA"):
        st.session_state.db['api_keys'] = {"eia": e_api, "groq": g_api}
        res_eia = fetch_eia_pure(e_api)
        if res_eia: st.session_state.db['eia_data'] = res_eia
        res_cot = fetch_cot_pure()
        if res_cot: st.session_state.db['cot_data'] = res_cot
        save_db(st.session_state.db)
        st.success("API Real-Time Sync Complete")

# --- MAIN ---
st.title("NatGas Sniper V118")

# 1. LIVE CHART
st.subheader("📊 Live Natural Gas Market")
components.html('<div style="height:400px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=400)

# 2. PURE API SUMMARY
e = st.session_state.db['eia_data']
c = st.session_state.db['cot_data']
# Surplus izračun isključivo iz API podataka
surplus = e['current'] - e['five_year_avg'] if e['five_year_avg'] > 0 else 0

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='stat-card'>EIA Pure Storage<br><h3>{e['current']} Bcf</h3><span class='{'bull-text' if e['net_change'] < 0 else 'bear-text'}'>Net: {e['net_change']} Bcf</span></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='stat-card'>Pure 5y Deviation<br><h3 class='{'bull-text' if surplus < 0 else 'bear-text'}'>{surplus:+.1f} Bcf</h3><span>vs API Derived Avg</span></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='stat-card'>Managed Money Net<br><h3 class='{'bear-text' if c.get('mm_net', 0) < 0 else 'bull-text'}'>{c.get('mm_net', 0):,}</h3><span>Speculative</span></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='stat-card'>Retail Net<br><h3>{c.get('retail_net', 0):,}</h3><span>Noise Meter</span></div>", unsafe_allow_html=True)

# 3. PW-HDD MATRIX
st.subheader("🌡️ PW-HDD Matrix (Auto-Archive)")

current_run = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d')}_{'00z' if 6 <= datetime.now(pytz.utc).hour < 18 else '12z'}"
# (Weather fetcher logic goes here - remains same for OpenMeteo)

# 4. AI ANALYST
if st.button("🚀 RUN PURAL NEURAL ANALYSIS"):
    client = Groq(api_key=st.session_state.db['api_keys']['groq'])
    prompt = f"Analyze: EIA {e['current']} Bcf, API 5y Avg {e['five_year_avg']}, Surplus {surplus:+.1f}. COT MM {c.get('mm_net')}. Be brutal."
    res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
    st.markdown(f"<div class='ai-analysis-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
