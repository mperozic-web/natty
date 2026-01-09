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
import google.generativeai as genai

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V102", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .ai-analysis-box { font-size: 1.1rem; line-height: 1.7; color: #EEEEEE; border: 2px solid #00FF00; padding: 25px; background-color: #051A05; border-radius: 10px; margin-bottom: 25px; border-left: 10px solid #00FF00; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .grand-total-box { padding: 25px; background: #0F0F0F; border: 2px solid #008CFF; border-radius: 10px; text-align: center; margin-top: 20px; margin-bottom: 20px; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-bottom: 20px; color: white; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 6px; text-align: center; }
    .cell-bull { color: #00FF00 !important; font-weight: bold; }
    .cell-bear { color: #FF4B4B !important; font-weight: bold; }
    .term-highlight { background-color: rgba(0, 255, 0, 0.12) !important; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ---
DATA_FILE = "sniper_v102_data.json"
def load_data():
    defaults = {"eia_curr": 3375, "eia_prev": 3413, "eia_5y": 3317, "mm_l": 0, "mm_s": 0, "com_l": 0, "com_s": 0, "ret_l": 0, "ret_s": 0, "last_hdd_matrix": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f: return {**defaults, **json.load(f)}
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)

if 'data' not in st.session_state: st.session_state.data = load_data()

# --- HDD ENGINES ---
CITIES = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}

@st.cache_data(ttl=3600)
def fetch_hdd_matrix():
    matrix = {}
    try:
        for city, info in CITIES.items():
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto").json()
            h = [round(max(0, 65 - (mx + mn)/2), 2) for mx, mn in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
            matrix[city] = h
        return matrix
    except: return {}

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

# --- SIDEBAR ---
with st.sidebar:
    st.header("AI Setup")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.header("Sniper Command")
    with st.form("storage_v102"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        ec = st.number_input("Current Bcf", value=st.session_state.data.get("eia_curr", 3375))
        e5 = st.number_input("5y Avg Bcf", value=st.session_state.data.get("eia_5y", 3317))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": ec, "eia_5y": e5})
            save_data(st.session_state.data); st.rerun()
            
    with st.form("cot_v102"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        ml, ms = st.number_input("MM Long", value=st.session_state.data.get("mm_l",0)), st.number_input("MM Short", value=st.session_state.data.get("mm_s",0))
        cl, cs = st.number_input("Comm Long", value=st.session_state.data.get("com_l",0)), st.number_input("Comm Short", value=st.session_state.data.get("com_s",0))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs})
            save_data(st.session_state.data); st.rerun()

# --- ANALIZA ---
curr_mx = fetch_hdd_matrix()
ao, nao, pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN ---
col_m, col_r = st.columns([4, 1.2])

with col_m:
    st.subheader("14-Day Granular PW-HDD Matrix")
    if curr_mx:
        prev_mx = st.session_state.data.get("last_hdd_matrix", {})
        html = "<table class='matrix-table'><tr><th>Grad</th><th>Total</th><th>ST Avg</th><th>LT Avg</th>"
        for i in range(14): html += f"<th>D{i+1}</th>"
        html += "</tr>"
        gc, gp, std, ted = 0, 0, 0, 0
        for city, info in CITIES.items():
            w = info[2]; cv = curr_mx.get(city, [0]*14); pv = prev_mx.get(city, cv)
            tc, tp = sum(cv), sum(pv); gc += tc * w; gp += tp * w
            st_avg, lt_avg = sum(cv[:7])/7, sum(cv[7:14])/7
            std += (sum(cv[:7])-sum(pv[:7]))*w; ted += (sum(cv[7:])-sum(pv[7:]))*w
            st_s = "term-highlight" if st_avg > lt_avg else ""; lt_s = "term-highlight" if lt_avg > st_avg else ""
            c_cl = "cell-bull" if tc > tp else "cell-bear" if tc < tp else ""
            html += f"<tr><td>{city}</td><td class='{c_cl}'>{tc:.1f}</td><td>{st_avg:.1f}</td><td>{lt_avg:.1f}</td>"
            for i in range(14):
                d_cl = "cell-bull" if cv[i] > pv[i] else "cell-bear" if cv[i] < pv[i] else ""
                h_s = st_s if i < 7 else lt_s
                html += f"<td class='{d_cl} {h_s}'>{cv[i]:.1f}</td>"
            html += "</tr>"
        html += "</table>"; st.markdown(html, unsafe_allow_html=True)
        gtd = gc - gp
        st.markdown(f"<div class='grand-total-box'><h1>{gc:.2f} <span class='{'bull-text' if gtd > 0 else 'bear-text'}'>({gtd:+.2f})</span></h1></div>", unsafe_allow_html=True)

    if st.button("SAVE MODEL FOR DELTA"):
        st.session_state.data["last_hdd_matrix"] = curr_mx
        save_data(st.session_state.data); st.rerun()

    # GEMINI ANALYST (STABILIZIRANO)
    st.subheader("🤖 Gemini Strategic Analyst")
    if st.button("🚀 POKRENI ANALIZU ASIMETRIJE"):
        if not gemini_key:
            st.error("Unesi API Key u sidebaru!")
        else:
            try:
                genai.configure(api_key=gemini_key)
                # Standardizirani naziv bez sufixa koji često uzrokuju 404
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = (f"Analyze NatGas: EIA storage {st.session_state.data['eia_curr']} Bcf, "
                          f"deficit vs 5y {st.session_state.data['eia_curr'] - st.session_state.data['eia_5y']} Bcf. "
                          f"COT Net MM: {st.session_state.data['mm_l'] - st.session_state.data['mm_s']}. "
                          f"HDD Matrix Total {gc:.2f} (Delta {gtd:+.2f}). "
                          f"Short-Term vs Long-Term HDD sentiment is crucial. Find the gap.")
                
                with st.spinner("AI analizira asimetriju..."):
                    response = model.generate_content(prompt)
                    st.markdown(f"<div class='ai-analysis-box'>{response.text}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Greška pri spajanju na AI: {e}")
                st.info("Savjet: Ako AI i dalje ne radi, unesi COT podatke i donesi odluku na temelju HDD Matrixa. Ne čekaj kôd.")

    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

with col_r:
    st.subheader("📰 Google Intel Feed")
    f = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:6]: st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
