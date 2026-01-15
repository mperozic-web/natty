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
st.set_page_config(page_title="NatGas Sniper V116", layout="wide")

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
DB_FILE = "sniper_v116_db.json"

def load_db():
    defaults = {
        "api_keys": {"eia": "", "groq": ""},
        "eia_data": {"current": 0, "prev": 0, "net_change": 0, "5y_avg": 3250},
        "cot_data": {"mm_net": 0, "comm_net": 0, "retail_net": 0, "last_update": ""},
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

def fetch_eia_v2(key):
    if not key: return None
    try:
        url = f"https://api.eia.gov/v2/natural-gas/stor/wkly/data/?api_key={key}&frequency=weekly&data[]=value&facets[series][]=NW2_EPG0_SWO_R48_BCF&sort[0][column]=period&sort[0][direction]=desc&length=2"
        r = requests.get(url, timeout=10).json()
        raw = r['response']['data']
        curr = int(raw[0]['value'])
        prev = int(raw[1]['value'])
        return {"current": curr, "prev": prev, "net_change": curr - prev, "5y_avg": 3250}
    except: return None

def fetch_cot_disaggregated():
    try:
        # Povlačimo Disaggregated Futures and Options Combined izvještaj
        url = "https://www.cftc.gov/dea/new/disagg_gas_so_wk.txt"
        r = requests.get(url, timeout=10).text
        # Tražimo Henry Hub sekciju
        section = re.split(r'NATURAL GAS - NEW YORK MERCANTILE EXCHANGE', r)[1]
        
        # Ekstrakcija podataka pomoću regexa na temelju pozicija u CFTC tekstualnom formatu
        # Managed Money
        mm_long = int(re.findall(r'Managed Money\s+(\d+)', section)[0])
        mm_short = int(re.findall(r'Managed Money\s+\d+\s+(\d+)', section)[0])
        
        # Commercial (Producer + Swap Dealers)
        prod_long = int(re.findall(r'Producer/Merchant/Processor/User\s+(\d+)', section)[0])
        prod_short = int(re.findall(r'Producer/Merchant/Processor/User\s+\d+\s+(\d+)', section)[0])
        swap_long = int(re.findall(r'Swap Dealers\s+(\d+)', section)[0])
        swap_short = int(re.findall(r'Swap Dealers\s+\d+\s+(\d+)', section)[0])
        
        # Retail (Non-Reportable)
        retail_long = int(re.findall(r'Nonreportable Positions\s+(\d+)', section)[0])
        retail_short = int(re.findall(r'Nonreportable Positions\s+\d+\s+(\d+)', section)[0])
        
        return {
            "mm_net": mm_long - mm_short,
            "comm_net": (prod_long + swap_long) - (prod_short + swap_short),
            "retail_net": retail_long - retail_short,
            "last_update": datetime.now().strftime("%Y-%m-%d")
        }
    except: return None

# --- WEATHER ENGINE ---
CITIES = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}

@st.cache_data(ttl=1800)
def fetch_weather():
    m = {}
    for c, i in CITIES.items():
        try:
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={i[0]}&longitude={i[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14").json()
            m[c] = [round(max(0, 65 - (mx + mn)/2), 2) for mx, mn in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
        except: m[c] = [0]*14
    return m

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Sniper Setup")
    e_api = st.text_input("EIA API Key", value=st.session_state.db['api_keys']['eia'], type="password")
    g_api = st.text_input("Groq API Key", value=st.session_state.db['api_keys']['groq'], type="password")
    
    if st.button("🔄 FULL DATA REFRESH"):
        st.session_state.db['api_keys'] = {"eia": e_api, "groq": g_api}
        res_eia = fetch_eia_v2(e_api)
        if res_eia: st.session_state.db['eia_data'] = res_eia
        res_cot = fetch_cot_disaggregated()
        if res_cot: st.session_state.db['cot_data'] = res_cot
        save_db(st.session_state.db)
        st.success("Intelligence Updated")

# --- MAIN INTERFACE ---
st.title("NatGas Sniper V116")

# 1. LIVE CHART (TOP)
st.subheader("📊 Live Natural Gas Market")
components.html('<div style="height:400px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=400)

# 2. STRATEGIC SUMMARY CARDS
e = st.session_state.db['eia_data']
c = st.session_state.db['cot_data']
diff = e['current'] - e['5y_avg']

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='stat-card'>EIA Storage<br><h3>{e['current']} Bcf</h3><span class='{'bull-text' if e['net_change'] < 0 else 'bear-text'}'>Net: {e['net_change']} Bcf</span></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='stat-card'>5y Deviation<br><h3 class='{'bull-text' if diff < 0 else 'bear-text'}'>{diff:+} Bcf</h3><span>vs 5y Average</span></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='stat-card'>Managed Money<br><h3 class='{'bear-text' if c['mm_net'] < 0 else 'bull-text'}'>{c['mm_net']:,}</h3><span>Net Position</span></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='stat-card'>Comm/Retail Net<br><h3>{c['comm_net']:,} / {c['retail_net']:,}</h3><span>Smart / Noise</span></div>", unsafe_allow_html=True)

# 3. PW-HDD MATRIX
st.subheader("🌡️ PW-HDD Matrix (Auto-Comparison)")
current_run = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d')}_{'00z' if 6 <= datetime.now(pytz.utc).hour < 18 else '12z'}"
weather_now = fetch_weather()

# Auto-archive check
if st.session_state.db['last_run_processed'] != current_run:
    st.session_state.db['archive'][current_run] = weather_now
    st.session_state.db['last_run_processed'] = current_run
    save_db(st.session_state.db)

archive = st.session_state.db['archive']
runs = sorted(archive.keys())
prev_run = runs[-2] if len(runs) > 1 else current_run
weather_prev = archive.get(prev_run, weather_now)

dates = [(datetime.now() + timedelta(days=i)).strftime("%b %d") for i in range(14)]
html = "<table class='matrix-table'><tr><th>City (W)</th><th>Total</th>"
for d in dates: html += f"<th>{d}</th>"
html += "</tr>"

gc_now, gc_prev = 0, 0
for city, info in CITIES.items():
    w = info[2]
    vn, vp = weather_now[city], weather_prev[city]
    tn, tp = sum(vn), sum(vp)
    gc_now += tn * w; gc_prev += tp * w
    html += f"<tr><td>{city} ({w})</td><td class='{'bull-text' if tn > tp else 'bear-text'}'>{tn:.1f}</td>"
    for i in range(14):
        cl = "bull-text" if vn[i] > vp[i] else "bear-text"
        html += f"<td class='{cl}'>{vn[i]:.1f}</td>"
    html += "</tr>"
html += "</table>"; st.markdown(html, unsafe_allow_html=True)

delta = gc_now - gc_prev
st.markdown(f"**PW-HDD Shift:** {gc_now:.2f} (Delta vs {prev_run.split('_')[1]}: <span class='{'bull-text' if delta > 0 else 'bear-text'}'>{delta:+.2f}</span>)", unsafe_allow_html=True)

# 4. INTELLIGENCE RADAR
t1, t2 = st.tabs(["NOAA OUTLOOK", "🤖 NEURAL STRATEGIC ANALYSIS"])
with t1:
    cw1, cw2 = st.columns(2)
    with cw1: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif")
    with cw2: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif")
with t2:
    if st.button("🚀 EXECUTE NEURAL SQUEEZE ANALYSIS"):
        client = Groq(api_key=st.session_state.db['api_keys']['groq'])
        prompt = (f"NatGas Analysis: EIA {e['current']} Bcf (Net {e['net_change']}, Deviation {diff}). "
                  f"COT MM {c['mm_net']}, Comm {c['comm_net']}, Retail {c['retail_net']}. "
                  f"HDD Live {gc_now:.2f}, Delta {delta:+.2f}. Analyze risk asymmetry.")
        res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
        st.markdown(f"<div class='ai-analysis-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)

st.markdown("<div style='text-align:center; font-size:0.7rem; color:#444;'>Autonomous Sniper V116 | Data: EIA V2 API, CFTC Disaggregated, Open-Meteo Ensemble.</div>", unsafe_allow_html=True)
