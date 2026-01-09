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

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V85", layout="wide")

# RESTAURACIJA V82/V83 DIZAJNA
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 10px; margin-bottom: 25px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .ext-bull { color: #00FF00 !important; font-weight: 900; text-decoration: underline; background-color: #004400; padding: 2px 5px; border-radius: 3px; }
    .ext-bear { color: #FF4B4B !important; font-weight: 900; text-decoration: underline; background-color: #440000; padding: 2px 5px; border-radius: 3px; }
    .hdd-quantum-card { background: linear-gradient(135deg, #0A0A0A 0%, #111 100%); border: 1px solid #008CFF; padding: 20px; border-radius: 10px; text-align: center; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .external-link { 
        display: block; padding: 10px; margin-bottom: 8px; background: #002B50; 
        color: #008CFF !important; text-decoration: none !important; 
        border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080;
    }
    .external-link:hover { background: #004080; color: #FFFFFF !important; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.8rem; color: #CCC; line-height: 1.4; border-radius: 5px; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE (JSON) ---
DATA_FILE = "sniper_persistent.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: pass
    return {"eia_v": 3375, "eia_5": 3317, "nc_l": 288456, "nc_s": 424123, "com_l": 512000, "com_s": 380000, "ret_l": 54120, "ret_s": 32100, "last_hdd": 0.0}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- HDD & NOAA ENGINES ---
@st.cache_data(ttl=3600)
def get_hdd():
    # Proxy-8 s punim težinama
    cities = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}
    total = 0
    try:
        for c, i in cities.items():
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={i[0]}&longitude={i[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto").json()
            avg = [(x + y)/2 for x,y in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
            total += sum([max(0, 65 - t) for t in avg]) * i[2]
        return round(total, 2)
    except: return 0.0

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

# --- SIDEBAR (LIJEVO) ---
with st.sidebar:
    st.header("🎯 Sniper Hub")
    
    with st.form("persistence_form"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        st.session_state.data["eia_v"] = st.number_input("Current Bcf", value=st.session_state.data["eia_v"])
        st.session_state.data["eia_5"] = st.number_input("5y Avg Bcf", value=st.session_state.data["eia_5"])
        st.markdown("</div><div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Positioning")
        c1, c2 = st.columns(2)
        st.session_state.data["nc_l"] = c1.number_input("MM Long", value=st.session_state.data["nc_l"])
        st.session_state.data["nc_s"] = c2.number_input("MM Short", value=st.session_state.data["nc_s"])
        st.session_state.data["com_l"] = c1.number_input("Comm Long", value=st.session_state.data["com_l"])
        st.session_state.data["com_s"] = c2.number_input("Comm Short", value=st.session_state.data["com_s"])
        st.session_state.data["ret_l"] = c1.number_input("Ret Long", value=st.session_state.data["ret_l"])
        st.session_state.data["ret_s"] = c2.number_input("Ret Short", value=st.session_state.data["ret_s"])
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SINKRONIZIRAJ I SPREMI"):
            save_data(st.session_state.data)
            st.rerun()

    st.subheader("🔗 Broker Access")
    st.markdown('<a href="https://www.plus500.com/" class="external-link">PLUS 500</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://capital.com/" class="external-link">CAPITAL.COM</a>', unsafe_allow_html=True)

# --- DATA FETCH ---
curr_hdd = get_hdd()
hdd_delta = curr_hdd - st.session_state.data["last_hdd"]
ao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. HDD QUANTUM VISUALIZER
    st.markdown("### 🌡️ 14-Day PW-HDD Quantum Index")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.markdown(f"<div class='hdd-quantum-card'><h4>Aktualni Indeks</h4><h2 style='color:#008CFF;'>{curr_hdd}</h2><p>Proxy-8 PW-HDD</p></div>", unsafe_allow_html=True)
    with v2:
        d_color = "#00FF00" if hdd_delta >= 0 else "#FF4B4B"
        st.markdown(f"<div class='hdd-quantum-card'><h4>Model Delta</h4><h2 style='color:{d_color};'>{hdd_delta:+.2f}</h2><p>vs Zadnje Očitanje</p></div>", unsafe_allow_html=True)
    with v3:
        if st.button("💾 SPREMI KAO BAZU ZA DELTU"):
            st.session_state.data["last_hdd"] = curr_hdd
            save_data(st.session_state.data)
            st.rerun()

    # 2. EXECUTIVE NARRATIVE (Divergence Focus)
    st.subheader("📜 Executive Strategic Narrative")
    e_diff = st.session_state.data["eia_v"] - st.session_state.data["eia_5"]
    
    # Divergence Logic
    div_text = "Indikatori su usklađeni."
    if e_diff < 0 and hdd_delta < -5: div_text = "DIVERGENCIJA: Zalihe su niske (BULL), ali modeli zatopljuju (BEAR)."
    elif e_diff > 0 and hdd_delta > 5: div_text = "DIVERGENCIJA: Suficit zaliha (BEAR), ali modeli hlade (BULL)."
    
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA ASIMETRIJE:</strong> Managed Money Neto: <strong>{st.session_state.data["nc_l"] - st.session_state.data["nc_s"]:+,}</strong>. 
        Zalihe: <strong>{e_diff:+} Bcf</strong> od 5y prosjeka.<br><br>
        <strong>DIVERGENCIJA:</strong> {div_logic if 'div_logic' in locals() else div_text}<br>
        <strong>STATUS:</strong> {'Sustav detektira BULLISH konvergenciju.' if (e_diff < 0 and ao['now'] < 0) else 'Neutralno/Bearish čekanje.'}
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW
    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    # 4. INTELLIGENCE RADAR TABS
    st.subheader("📡 Intelligence Radar")
    t_noaa, t_spag = st.tabs(["NOAA WEATHER (Temp & Precip)", "SPAGHETTI TRENDS"])
    
    with t_noaa:
        # NOAA Slike vraćene na punu veličinu
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp")
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")

    with t_spag:
        
        idx_cols = st.columns(3)
        def get_grad(v, n):
            if n == "PNA":
                if v > 1.5: return "EXTREME BULLISH", "ext-bull"
                return ("BULLISH", "bull-text") if v > 0.5 else ("BEARISH", "bear-text")
            else:
                if v < -2.0: return "EXTREME BULLISH", "ext-bull"
                return ("BULLISH", "bull-text") if v < -0.5 else ("BEARISH", "bear-text")

        idxs = [
            ("AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Ispod -2.0: Extreme Bullish."),
            ("NAO", nao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Ispod -1.5: Extreme Bullish."),
            ("PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Iznad 1.5: Extreme Bullish.")
        ]
        for i, (name, d, url, leg) in enumerate(idxs):
            with idx_cols[i]:
                st.image(url)
                gr, css = get_grad(d['now'], name)
                st.markdown(f"**{name}: {d['now']:.2f}** | <span class='{css}'>{gr}</span>", unsafe_allow_html=True)
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")
                st.markdown(f"<div class='legend-box'>{leg}</div>", unsafe_allow_html=True)

# --- DESNA STRANA (Intel & Links) ---
with col_right:
    st.subheader("📰 Google Intel")
    feed = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+OR+natgas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for n in feed.entries[:6]:
        st.markdown(f"<div style='font-size:0.85rem; margin-bottom:8px;'><a href='{n.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{n.title}</a></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔗 Essential Links")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST (LIVE)</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE REPORT</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"""
    <div style='font-size:0.7rem; color:#666;'>
        <strong>Izvor podataka:</strong><br>
        HDD: Open-Meteo GFS 00z/12z<br>
        Indices: NOAA CPC<br>
        Persistence: Local JSON Engine
    </div>
    """, unsafe_allow_html=True)
