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
st.set_page_config(page_title="NatGas Sniper V89", layout="wide")

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
    .grand-total-box { padding: 25px; background: #0F0F0F; border: 2px solid #008CFF; border-radius: 10px; text-align: center; margin-top: 20px; }
    /* Table Styling */
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 8px; text-align: center; }
    .cell-bull { color: #00FF00; font-weight: bold; }
    .cell-bear { color: #FF4B4B; font-weight: bold; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE ---
DATA_FILE = "sniper_persistent_v89.json"

def load_data():
    defaults = {
        "eia_curr": 3375, "eia_prev": 3413, "eia_5y": 3317,
        "mm_l": 288456, "mm_s": 424123, "com_l": 512000, "com_s": 380000, "ret_l": 54120, "ret_s": 32100,
        "last_hdd_matrix": {}
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                loaded = json.load(f)
                return {**defaults, **loaded}
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- DATA ENGINES ---
CITIES = {
    "Chicago": [41.87, -87.62, 0.25],
    "NYC": [40.71, -74.00, 0.20],
    "Detroit": [42.33, -83.04, 0.15],
    "Philly": [39.95, -75.16, 0.10],
    "Boston": [42.36, -71.05, 0.10]
}

@st.cache_data(ttl=3600)
def fetch_hdd_matrix():
    matrix = {}
    try:
        for city, info in CITIES.items():
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto").json()
            hdds = [round(max(0, 65 - (mx + mn)/2), 2) for mx, mn in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
            matrix[city] = hdds
        return matrix
    except: return {}

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

def get_countdown(day_idx, hour, minute):
    now = datetime.now(pytz.timezone('Europe/Zagreb'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=(day_idx - now.weekday()) % 7)
    if now > target: target += timedelta(days=7)
    diff = target - now
    return f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"

# --- SIDEBAR (Persistent) ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    with st.form("storage_form"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        st.session_state.data["eia_curr"] = st.number_input("Current Bcf", value=st.session_state.data["eia_curr"])
        st.session_state.data["eia_prev"] = st.number_input("Prev Bcf", value=st.session_state.data["eia_prev"])
        st.session_state.data["eia_5y"] = st.number_input("5y Avg Bcf", value=st.session_state.data["eia_5y"])
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE STORAGE"):
            save_data(st.session_state.data); st.rerun()

    with st.form("cot_form"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Positioning")
        st.session_state.data["mm_l"] = st.number_input("MM Long", value=st.session_state.data["mm_l"])
        st.session_state.data["mm_s"] = st.number_input("MM Short", value=st.session_state.data["mm_s"])
        st.session_state.data["com_l"] = st.number_input("Comm Long", value=st.session_state.data["com_l"])
        st.session_state.data["com_s"] = st.number_input("Comm Short", value=st.session_state.data["com_s"])
        st.session_state.data["ret_l"] = st.number_input("Ret Long", value=st.session_state.data["ret_l"])
        st.session_state.data["ret_s"] = st.number_input("Ret Short", value=st.session_state.data["ret_s"])
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE COT"):
            save_data(st.session_state.data); st.rerun()

# --- ANALIZA ---
current_matrix = fetch_hdd_matrix()
ao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    st.subheader("🌡️ 14-Day Granular PW-HDD Matrix")
    
    
    if current_matrix:
        prev_matrix = st.session_state.data.get("last_hdd_matrix", {})
        
        # HTML Tablica za precizno bojanje
        html = "<table class='matrix-table'><tr><th>Grad (Ponder)</th><th>Total (14d)</th>"
        for i in range(14): html += f"<th>D{i+1}</th>"
        html += "</tr>"

        grand_total_curr = 0
        grand_total_prev = 0
        short_term_delta = 0
        tail_end_delta = 0

        for city, hdds in CITIES.items():
            weight = hdds[2]
            curr_vals = current_matrix.get(city, [0]*14)
            prev_vals = prev_matrix.get(city, curr_vals)
            
            city_total_curr = sum(curr_vals)
            city_total_prev = sum(prev_vals)
            grand_total_curr += city_total_curr * weight
            grand_total_prev += city_total_prev * weight

            # Analiza termina za sentiment
            short_term_delta += (sum(curr_vals[:7]) - sum(prev_vals[:7])) * weight
            tail_end_delta += (sum(curr_vals[7:]) - sum(prev_vals[7:])) * weight

            color_class = "cell-bull" if city_total_curr > city_total_prev else "cell-bear" if city_total_curr < city_total_prev else ""
            html += f"<tr><td>{city} ({weight})</td><td class='{color_class}'>{city_total_curr:.1f}</td>"
            
            for i in range(14):
                day_class = "cell-bull" if curr_vals[i] > prev_vals[i] else "cell-bear" if curr_vals[i] < prev_vals[i] else ""
                html += f"<td class='{day_class}'>{curr_vals[i]:.1f}</td>"
            html += "</tr>"
        
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)

        # GRAND TOTAL BOX
        gt_delta = grand_total_curr - grand_total_prev
        gt_color = "bull-text" if gt_delta > 0 else "bear-text"
        st.markdown(f"""
        <div class='grand-total-box'>
            <h4 style='margin:0;'>GRAND TOTAL WEIGHTED PW-HDD</h4>
            <h1 style='margin:10px 0; font-size:3rem; color:#008CFF;'>{grand_total_curr:.2f} <span class='{gt_color}' style='font-size:1.5rem;'>({gt_delta:+.2f})</span></h1>
            <div style='display:flex; justify-content:center; gap:30px;'>
                <span>Short-Term (D1-D7): <strong class='{"bull-text" if short_term_delta > 0 else "bear-text"}'>{'BULL' if short_term_delta > 0 else 'BEAR'}</strong></span>
                <span>Tail-End (D8-D14): <strong class='{"bull-text" if tail_end_delta > 0 else "bear-text"}'>{'BULL' if tail_end_delta > 0 else 'BEAR'}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("💾 SPREMI TRENUTNI MODEL KAO REFERENTNU BAZU"):
        st.session_state.data["last_hdd_matrix"] = current_matrix
        save_data(st.session_state.data); st.rerun()

    st.subheader("📜 Executive Strategic Narrative")
    
    e_diff = st.session_state.data["eia_curr"] - st.session_state.data["eia_5y"]
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA:</strong> Neto MM pozicija: <strong>{st.session_state.data["mm_l"] - st.session_state.data["mm_s"]:+,}</strong>. 
        Zalihe: <strong>{e_diff:+} Bcf</strong> vs 5y prosjek.<br>
        <strong>DIVERGENCIJA:</strong> {'Zalihe i vrijeme su usklađeni.' if (e_diff < 0 and gt_delta > 0) else 'Modeli pokazuju zatopljenje usprkos niskim zalihama.' if (e_diff < 0 and gt_delta < 0) else 'Visoke zalihe ali modeli hlade.'}<br>
        <strong>SENTIMENT:</strong> AO ({ao['now']:.2f}) i PNA ({pna['now']:.2f}) sugeriraju {'jačanje' if ao['now'] < 0 else 'slabljenje'} trenda hladnoće.
    </div>
    """, unsafe_allow_html=True)

    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    t1, t2 = st.tabs(["NOAA WEATHER", "SPAGHETTI TRENDS"])
    with t1:
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")
    with t2:
        
        idx_cols = st.columns(3)
        idxs = [("AO", ao), ("NAO", nao), ("PNA", pna)]
        u = ["https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif"]
        for i, (n, d) in enumerate(idxs):
            with idx_cols[i]:
                st.image(u[i])
                st.write(f"**{n}: {d['now']:.2f}**")

with col_right:
    st.subheader("📰 Google Intel Feed")
    f = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+OR+natgas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:6]:
        st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔗 Intelligence Hub")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD</a>', unsafe_allow_html=True)
