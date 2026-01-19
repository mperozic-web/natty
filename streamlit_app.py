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
st.set_page_config(page_title="NatGas Sniper V119", layout="wide")

# CSS za profesionalni izgled
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    .stat-card { background: #111; border: 1px solid #333; padding: 20px; border-radius: 10px; text-align: center; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    .matrix-table th, .matrix-table td { border: 1px solid #222; padding: 8px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ---
DB_FILE = "sniper_v119_db.json"

def load_db():
    defaults = {
        "api_keys": {"eia": "", "groq": ""},
        "eia_data": {"current": 0, "prev": 0, "5y_avg": 0},
        "cot_data": {"mm_net": 0, "comm_net": 0, "retail_net": 0},
        "archive": {}
    }
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f: return {**defaults, **json.load(f)}
    return defaults

def save_db(db):
    with open(DB_FILE, "w", encoding='utf-8') as f: json.dump(db, f, ensure_ascii=False)

if 'db' not in st.session_state: st.session_state.db = load_db()

# --- ROBUST FETCHERS (S Browser Emulacijom) ---

def fetch_eia_robust(key):
    if not key: return None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        # Dohvaćanje serije za izračun realnog 5y prosjeka
        url = f"https://api.eia.gov/v2/natural-gas/stor/wkly/data/?api_key={key}&frequency=weekly&data[]=value&facets[series][]=NW2_EPG0_SWO_R48_BCF&sort[0][column]=period&sort[0][direction]=desc&length=260"
        r = requests.get(url, headers=headers, timeout=15).json()
        raw = r['response']['data']
        curr = int(raw[0]['value'])
        prev = int(raw[1]['value'])
        # Kalkulacija 5y prosjeka za ovaj tjedan (točke: 52, 104, 156, 208 tjedana unazad)
        avg_5y = sum([int(raw[i]['value']) for i in [52, 104, 156, 208]]) / 4
        return {"current": curr, "prev": prev, "5y_avg": round(avg_5y, 1)}
    except Exception as e:
        st.error(f"EIA API Error: {e}"); return None

def fetch_cot_robust():
    # CFTC zahtijeva strog User-Agent ili blokira request
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        # Disaggregated Futures and Options combined (najprecizniji izvještaj)
        url = "https://www.cftc.gov/dea/new/disagg_gas_so_wk.txt"
        r = requests.get(url, headers=headers, timeout=20).text
        
        # Pronalaženje Henry Hub sekcije
        split_ref = "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE"
        if split_ref not in r: return None
        section = r.split(split_ref)[1]
        
        # Regex za hvatanje MM, Comm i Retail pozicija
        def parse_pos(label, text):
            # Traži labelu i hvata prva dva broja (Long i Short)
            pattern = rf"{label}\s+([\d,]+)\s+([\d,]+)"
            m = re.search(pattern, text)
            if m:
                l = int(m.group(1).replace(',', ''))
                s = int(m.group(2).replace(',', ''))
                return l - s
            return 0

        return {
            "mm_net": parse_pos("Managed Money", section),
            "comm_net": parse_pos("Producer/Merchant/Processor/User", section) + parse_pos("Swap Dealers", section),
            "retail_net": parse_pos("Nonreportable Positions", section)
        }
    except Exception as e:
        st.error(f"COT Fetch Error: {e}"); return None

# --- MAIN ---
with st.sidebar:
    st.header("⚙️ System Control")
    eia_key = st.text_input("EIA API Key", value=st.session_state.db['api_keys']['eia'], type="password")
    groq_key = st.text_input("Groq API Key", value=st.session_state.db['api_keys']['groq'], type="password")
    
    if st.button("🚀 FORCE SYNC ALL DATA"):
        st.session_state.db['api_keys'] = {"eia": eia_key, "groq": groq_key}
        eia_res = fetch_eia_robust(eia_key)
        if eia_res: st.session_state.db['eia_data'] = eia_res
        cot_res = fetch_cot_robust()
        if cot_res: st.session_state.db['cot_data'] = cot_res
        save_db(st.session_state.db)
        st.rerun()

# --- DASHBOARD ---
e = st.session_state.db['eia_data']
c = st.session_state.db['cot_data']
surplus = e['current'] - e['5y_avg'] if e['5y_avg'] > 0 else 0

st.title("NatGas Sniper V119 - Autonomous Engine")

# 1. EIA & COT SUMMARY
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='stat-card'>EIA Storage<br><h3>{e['current']} Bcf</h3></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='stat-card'>5y Surplus/Deficit<br><h3 class='{'bear-text' if surplus > 0 else 'bull-text'}'>{surplus:+.1f} Bcf</h3></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='stat-card'>Managed Money Net<br><h3>{c['mm_net']:,}</h3></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='stat-card'>Retail Net (Noise)<br><h3>{c['retail_net']:,}</h3></div>", unsafe_allow_html=True)



# 2. PW-HDD MATRIX
st.subheader("🌡️ 14-Day PW-HDD Matrix")
# (Ovdje ide tvoja provjerena OpenMeteo logika...)

# 3. AI ANALYSIS
if st.button("🧠 RUN NEURAL STRATEGY"):
    client = Groq(api_key=groq_key)
    prompt = f"Analyze: Storage {e['current']}, 5y Deviation {surplus:+.1f}. COT MM {c['mm_net']}, Retail {c['retail_net']}. Identify if Retail is trapped and MM is rotating."
    res = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
    st.markdown(f"<div class='ai-analysis-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
