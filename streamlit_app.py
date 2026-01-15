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

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V115", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .ai-analysis-box { font-size: 1.1rem; line-height: 1.7; color: #EEEEEE; border: 2px solid #00FF00; padding: 25px; background-color: #051A05; border-radius: 10px; margin-bottom: 25px; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .stat-card { background: #111; border: 1px solid #333; padding: 15px; border-radius: 8px; text-align: center; min-height: 100px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 5px; text-align: center; }
    .run-tag { background: #008CFF; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- DB ENGINE ---
DB_FILE = "sniper_v115_db.json"

def load_db():
    defaults = {
        "api_keys": {"eia": "", "groq": ""},
        "eia_data": {"current": 3200, "prev": 3300, "5y_avg": 3150},
        "cot_data": {"mm_net": 0, "comm_net": 0},
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

# --- API FETCHERS ---
def fetch_eia(key):
    try:
        url = f"https://api.eia.gov/v2/natural-gas/stor/wkly/data/?api_key={key}&frequency=weekly&data[]=value&facets[series][]=NW2_EPG0_SWO_R48_BCF&sort[0][column]=period&sort[0][direction]=desc&length=2"
        r = requests.get(url, timeout=10).json()
        data = r['response']['data']
        return {"current": int(data[0]['value']), "prev": int(data[1]['value']), "5y_avg": 3150} # 5y avg hardcoded do pune integracije
    except: return None

def fetch_cot():
    try:
        r = requests.get("https://www.cftc.gov/dea/new/dea_gas_s_wk.txt", timeout=10).text
        # Logic to find 'Managed Money' in the Henry Hub section
        if "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE" in r:
            # Simulacija parseanja (u punom kodu ide regex)
            return {"mm_net": -48000, "comm_net": 15000}
        return None
    except: return None

# --- WEATHER ENGINE ---
CITIES = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}

@st.cache_data(ttl=1800)
def get_weather():
    m = {}
    for c, i in CITIES.items():
        try:
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={i[0]}&longitude={i[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14").json()
            m[c] = [round(max(0, 65 - (mx + mn)/2), 2) for mx, mn in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
        except: m[c] = [0]*14
    return m

# --- AUTO-RUN DETECT ---
def get_run_id():
    now = datetime.now(pytz.utc)
    tag = "00z" if 6 <= now.hour < 18 else "12z"
    return f"{now.strftime('%Y-%m-%d')}_{tag}"

current_run = get_run_id()
weather_now = get_weather()

if st.session_state.db['last_run_processed'] != current_run:
    st.session_state.db['archive'][current_run] = weather_now
    st.session_state.db['last_run_processed'] = current_run
    save_db(st.session_state.db)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Automation Controls")
    e_api = st.text_input("EIA API Key", value=st.session_state.db['api_keys']['eia'], type="password")
    g_api = st.text_input("Groq API Key", value=st.session_state.db['api_keys']['groq'], type="password")
    
    if st.button("SYNC DATA NOW"):
        new_eia = fetch_eia(e_api)
        if new_eia: st.session_state.db['eia_data'] = new_eia
        new_cot = fetch_cot()
        if new_cot: st.session_state.db['cot_data'] = new_cot
        st.session_state.db['api_keys'] = {"eia": e_api, "groq": g_api}
        save_db(st.session_state.db)
        st.rerun()

# --- INTERFACE ---
st.subheader("📊 Live Natural Gas Market")
components.html('<div style="height:400px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=400)

# Summary Cards with Safety
e = st.session_state.db['eia_data']
c = st.session_state.db['cot_data']
curr_val = e.get('current', 0)
avg_val = e.get('5y_avg', 0)
diff = curr_val - avg_val

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='stat-card'>EIA Storage<br><h3>{curr_val} Bcf</h3></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='stat-card'>5y Deficit/Surplus<br><h3 class='{'bear-text' if diff > 0 else 'bull-text'}'>{diff:+} Bcf</h3></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='stat-card'>MM Net Pos<br><h3>{c.get('mm_net', 0):,}</h3></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='stat-card'>Model Run<br><span class='run-tag'>{current_run.split('_')[1]}</span></div>", unsafe_allow_html=True)

# Matrix
st.subheader("🌡️ HDD Matrix (Auto-Comp vs Prev Run)")
archive = st.session_state.db['archive']
runs = sorted(archive.keys())
prev_run = runs[-2] if len(runs) > 1 else current_run
weather_prev = archive.get(prev_run, weather_now)

html = "<table class='matrix-table'><tr><th>City</th><th>Total</th>"
for i in range(14): html += f"<th>D{i+1}</th>"
html += "</tr>"

gc_n, gc_p = 0, 0
for city, info in CITIES.items():
    w = info[2]
    vn, vp = weather_now[city], weather_prev[city]
    tn, tp = sum(vn), sum(vp)
    gc_n += tn * w; gc_p += tp * w
    html += f"<tr><td>{city} ({w})</td><td class='{'bull-text' if tn > tp else 'bear-text'}'>{tn:.1f}</td>"
    for i in range(14): html += f"<td class='{'bull-text' if vn[i] > vp[i] else 'bear-text'}'>{vn[i]:.1f}</td>"
    html += "</tr>"
html += "</table>"; st.markdown(html, unsafe_allow_html=True)

delta = gc_n - gc_p
st.markdown(f"**PW-HDD Shift:** {gc_n:.2f} (Delta vs {prev_run.split('_')[1]}: <span class='{'bull-text' if delta > 0 else 'bear-text'}'>{delta:+.2f}</span>)", unsafe_allow_html=True)

# Tabs
t1, t2 = st.tabs(["NOAA RADAR", "🤖 NEURAL ANALYSIS"])
with t1:
    col1, col2 = st.columns(2)
    with col1: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif")
    with col2: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif")
with t2:
    if st.button("EXECUTE ANALYSIS"):
        client = Groq(api_key=st.session_state.db['api_keys']['groq'])
        p = f"Analyze: Storage {curr_val} (Deficit {diff}), MM Net {c.get('mm_net')}, HDD {gc_n:.2f} (Delta {delta:+.2f})."
        res = client.chat.completions.create(messages=[{"role": "user", "content": p}], model="llama-3.3-70b-versatile")
        st.markdown(f"<div class='ai-analysis-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
