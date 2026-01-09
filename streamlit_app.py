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
st.set_page_config(page_title="NatGas Sniper V91", layout="wide")

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
    .grand-total-box { padding: 25px; background: #0F0F0F; border: 2px solid #008CFF; border-radius: 10px; text-align: center; margin-top: 20px; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 20px; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 8px; text-align: center; }
    .cell-bull { color: #00FF00 !important; font-weight: bold; }
    .cell-bear { color: #FF4B4B !important; font-weight: bold; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE ---
DATA_FILE = "sniper_v91_master_db.json"

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

# --- ENGINES ---
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

def get_run_type():
    now_utc = datetime.now(pytz.utc)
    if 6 <= now_utc.hour < 18: return "00z"
    return "12z"

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Sniper Hub")
    
    with st.form("storage_box_form"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        eia_c = st.number_input("Current Bcf", value=st.session_state.data.get("eia_curr", 3375))
        eia_p = st.number_input("Prev Bcf", value=st.session_state.data.get("eia_prev", 3413))
        eia_5 = st.number_input("5y Avg Bcf", value=st.session_state.data.get("eia_5y", 3317))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": eia_c, "eia_prev": eia_p, "eia_5y": eia_5})
            save_data(st.session_state.data); st.rerun()

    with st.form("cot_box_form"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Positioning")
        ml = st.number_input("MM Long", value=st.session_state.data.get("mm_l", 288456))
        ms = st.number_input("MM Short", value=st.session_state.data.get("mm_s", 424123))
        cl = st.number_input("Comm Long", value=st.session_state.data.get("com_l", 512000))
        cs = st.number_input("Comm Short", value=st.session_state.data.get("com_s", 380000))
        rl = st.number_input("Ret Long", value=st.session_state.data.get("ret_l", 54120))
        rs = st.number_input("Ret Short", value=st.session_state.data.get("ret_s", 32100))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs, "ret_l": rl, "ret_s": rs})
            save_data(st.session_state.data); st.rerun()

# --- ANALIZA ---
current_matrix = fetch_hdd_matrix()
ao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")
run_info = get_run_type()

# --- MAIN LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    st.subheader("🌡️ 14-Day Granular PW-HDD Matrix")
    
    if current_matrix:
        prev_matrix = st.session_state.data.get("last_hdd_matrix", {})
        
        # HTML Tablica popravljena
        html = "<table class='matrix-table'><tr><th>Grad (Ponder)</th><th>Total (14d)</th>"
        for i in range(14): html += f"<th>D{i+1}</th>"
        html += "</tr>"

        g_total_curr, g_total_prev = 0, 0
        st_delta, te_delta = 0, 0

        for city, info in CITIES.items():
            w = info[2]
            curr_v = current_matrix.get(city, [0]*14)
            prev_v = prev_matrix.get(city, curr_v)
            
            c_total_curr, c_total_prev = sum(curr_v), sum(prev_v)
            g_total_curr += c_total_curr * w
            g_total_prev += c_total_prev * w
            
            st_delta += (sum(curr_v[:7]) - sum(prev_v[:7])) * w
            te_delta += (sum(curr_v[7:]) - sum(prev_v[7:])) * w

            c_class = "cell-bull" if c_total_curr > c_total_prev else "cell-bear" if c_total_curr < c_total_prev else ""
            html += f"<tr><td>{city} ({w})</td><td class='{c_class}'>{c_total_curr:.1f}</td>"
            for i in range(14):
                d_class = "cell-bull" if curr_v[i] > prev_v[i] else "cell-bear" if curr_v[i] < prev_v[i] else ""
                html += f"<td class='{d_class}'>{curr_v[i]:.1f}</td>"
            html += "</tr>" # Kraj reda
        
        html += "</table>" # Kraj tablice izvan loopa
        st.markdown(html, unsafe_allow_html=True)

        # GRAND TOTAL BOX
        gt_delta = g_total_curr - g_total_prev
        st.markdown(f"""
        <div class='grand-total-box'>
            <h4 style='margin:0;'>GRAND TOTAL WEIGHTED PW-HDD | Model Run: <strong>{run_info}</strong></h4>
            <h1 style='margin:10px 0; font-size:3rem; color:#008CFF;'>{g_total_curr:.2f} <span class='{"bull-text" if gt_delta > 0 else "bear-text"}' style='font-size:1.5rem;'>({gt_delta:+.2f})</span></h1>
            <div style='display:flex; justify-content:center; gap:30px;'>
                <span>Short-Term (D1-D7): <strong class='{"bull-text" if st_delta > 0 else "bear-text"}'>{'BULL' if st_delta > 0 else 'BEAR'}</strong></span>
                <span>Tail-End (D8-D14): <strong class='{"bull-text" if te_delta > 0 else "bear-text"}'>{'BULL' if te_delta > 0 else 'BEAR'}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if st.button("💾 SPREMI TRENUTNI MODEL KAO REFERENTNU BAZU"):
        st.session_state.data["last_hdd_matrix"] = current_matrix
        save_data(st.session_state.data); st.rerun()

    st.subheader("📜 Executive Strategic Narrative")
    e_diff = st.session_state.data.get("eia_curr", 3375) - st.session_state.data.get("eia_5y", 3317)
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA DIVERGENCIJA:</strong> Managed Money Neto: <strong>{st.session_state.data.get("mm_l",0) - st.session_state.data.get("mm_s",0):+,}</strong>. 
        Zalihe bilježe <strong>{e_diff:+} Bcf</strong> odstupanja od prosjeka.<br>
        Trenutni model ({run_info}) pokazuje {'hladnije' if gt_delta > 0 else 'toplije'} trendove u odnosu na zadnje spremljeno stanje. 
        Prati korelacije s AO indeksom ({ao['now']:.2f}) za potvrdu snage ovog narativa.
    </div>
    """, unsafe_allow_html=True)

    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

with col_right:
    st.subheader("📰 Google Intel Feed")
    f = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+OR+natgas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:6]:
        st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔗 Essential Links")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE</a>', unsafe_allow_html=True)
