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
st.set_page_config(page_title="NatGas Sniper V84", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 10px; margin-bottom: 25px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .external-link { 
        display: block; padding: 10px; margin-bottom: 8px; background: #002B50; 
        color: #008CFF !important; text-decoration: none !important; 
        border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080;
    }
    .external-link:hover { background: #004080; color: #FFFFFF !important; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE (JSON Storage) ---
DATA_FILE = "sniper_data.json"

def load_persistent_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "eia_v": 3375, "eia_5": 3317, 
        "nc_l": 288456, "nc_s": 424123, 
        "cm_l": 512000, "cm_s": 380000, 
        "rt_l": 54120, "rt_s": 32100,
        "prev_hdd": 0.0, "last_run_type": "12z"
    }

def save_persistent_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

p_data = load_persistent_data()

# --- HDD ENGINE ---
def get_current_hdd():
    cities = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Boston": [42.36, -71.05, 0.10]}
    total_hdd = 0
    try:
        for c, info in cities.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            avg = [(mx + mn) / 2 for mx, mn in zip(res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min'])]
            total_hdd += sum([max(0, 65 - t) for t in avg]) * info[2]
        return round(total_hdd, 2)
    except: return 0.0

# --- DATA FETCH ---
curr_hdd = get_current_hdd()
price_r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/NG=F", headers={'User-Agent': 'Mozilla/5.0'}).json()
price = price_r['chart']['result'][0]['meta']['regularMarketPrice']

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    st.metric("Henry Hub Live", f"${price:.3f}")
    
    with st.form("persistence_form"):
        st.subheader("📦 Storage & COT")
        new_eia_v = st.number_input("Current Bcf", value=p_data["eia_v"])
        new_nc_l = st.number_input("MM Long", value=p_data["nc_l"])
        new_nc_s = st.number_input("MM Short", value=p_data["nc_s"])
        
        if st.form_submit_button("TRAJNO SPREMI"):
            p_data.update({"eia_v": new_eia_v, "nc_l": new_nc_l, "nc_s": new_nc_s})
            save_persistent_data(p_data)
            st.rerun()

# --- MAIN LAYOUT ---
st.subheader("🚀 Quantum HDD Delta Tracking")

# HDD Tablica (00z vs 12z)
hdd_delta = curr_hdd - p_data["prev_hdd"]
run_type = "00z" if datetime.now().hour < 12 else "12z"

hdd_table_data = {
    "Run Type": [run_type, p_data["last_run_type"]],
    "14d PW-HDD Index": [curr_hdd, p_data["prev_hdd"]],
    "Delta": [hdd_delta, "-"]
}
st.table(pd.DataFrame(hdd_table_data))



# Gumb za spremanje trenutnog HDD kao "prethodnog"
if st.button("Spremi trenutni HDD kao referentni (za idući run)"):
    p_data["prev_hdd"] = curr_hdd
    p_data["last_run_type"] = run_type
    save_persistent_data(p_data)
    st.rerun()

# --- NARRATIVE ---
st.subheader("📜 Executive Strategic Narrative")
e_diff = p_data["eia_v"] - p_data["eia_5"]
st.markdown(f"""
<div class='summary-narrative'>
    <strong>DIVERGENCIJA:</strong> Zalihe su na <strong>{e_diff:+} Bcf</strong> od prosjeka. 
    HDD Delta od <strong>{hdd_delta:+.2f}</strong> sugerira {'jačanje' if hdd_delta > 0 else 'slabljenje'} potražnje. 
    U siječnju, svaki HDD bod vrijedi milijune dolara u asimetriji.
</div>
""", unsafe_allow_html=True)

# --- TABS ---
t_tv, t_noaa, t_news = st.tabs(["CHART", "NOAA WEATHER", "X & INTEL"])

with t_tv:
    components.html('<div style="height:500px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=500)

with t_noaa:
    # NOAA Karte pune veličine
    st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", use_container_width=True)
    st.markdown("---")
    st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", use_container_width=True)

with t_news:
    c_n, c_x = st.columns([1, 1])
    with c_n:
        st.subheader("📰 Google News")
        feed = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+when:7d&hl=en-US&gl=US&ceid=US:en")
        for n in feed.entries[:5]:
            st.markdown(f"**[{n.title}]({n.link})**")
    with c_x:
        st.subheader("🐦 X List (Embed)")
        # Pokušaj embedanja liste preko specifičnog ID-a
        list_html = """
        <a class="twitter-timeline" data-height="600" data-theme="dark" href="https://twitter.com/i/lists/1989752726553579941">My Natural Gas List</a> 
        <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
        """
        components.html(list_html, height=600)

# --- LEGEND & LINKS ---
st.markdown("---")
st.markdown("""
### 🏛️ Data Integrity Legend
* **HDD Izvor:** [Open-Meteo Weather API](https://open-meteo.com/) (Real-time forecast models).
* **NOAA Karte:** [CPC NOAA](https://www.cpc.ncep.noaa.gov/) (Atmospheric Administration).
* **Storage:** EIA Weekly Natural Gas Storage Report.
""")

st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
