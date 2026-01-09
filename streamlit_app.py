import streamlit as st
import pandas as pd
import requests
import io
import json
import os
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V87", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.1rem; line-height: 1.7; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 8px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .external-link { 
        display: block; padding: 10px; margin-bottom: 8px; background: #002B50; 
        color: #008CFF !important; text-decoration: none !important; 
        border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080;
    }
    .external-link:hover { background: #004080; color: #FFFFFF !important; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE (JSON) ---
DATA_FILE = "sniper_master_data.json"

def get_default_data():
    return {
        "eia_curr": 3375, "eia_prev": 3413, "eia_5y": 3317,
        "mm_l": 288456, "mm_s": 424123, "com_l": 512000, "com_s": 380000, "ret_l": 54120, "ret_s": 32100
    }

def load_data():
    defaults = get_default_data()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                loaded = json.load(f)
                # Spajanje s defaultima sprečava KeyError ako ključ fali
                for k, v in defaults.items():
                    if k not in loaded: loaded[k] = v
                return loaded
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

# Inicijalizacija sesije iz baze
if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- POMOĆNE FUNKCIJE ---
def get_countdown(day_idx, hour, minute):
    now = datetime.now(pytz.timezone('Europe/Zagreb'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=(day_idx - now.weekday()) % 7)
    if now > target: target += timedelta(days=7)
    diff = target - now
    return f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"

def get_14d_hdd():
    cities = {"Chicago": [41.87, -87.62, 0.40], "NYC": [40.71, -74.00, 0.35], "Detroit": [42.33, -83.04, 0.25]}
    daily_hdds = []
    try:
        for i in range(14): daily_hdds.append(0.0)
        for c, info in cities.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            mx, mn = res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min']
            for d in range(14):
                daily_hdds[d] += max(0, 65 - ((mx[d] + mn[d]) / 2)) * info[2]
        return daily_hdds
    except: return [0.0] * 14

def get_noaa_val(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return df.iloc[-1, -1]
    except: return 0.0

# --- SIDEBAR (RAZDVOJENI PERSISTENT INPUTS) ---
with st.sidebar:
    st.header("🎯 Sniper Hub Controls")
    
    with st.form("eia_storage_form"):
        st.subheader("📦 EIA Storage")
        st.write(f"Next: {get_countdown(3, 16, 30)}")
        e_curr = st.number_input("Current Bcf", value=st.session_state.data["eia_curr"])
        e_prev = st.number_input("Prev Bcf", value=st.session_state.data["eia_prev"])
        e_5y = st.number_input("5y Avg Bcf", value=st.session_state.data["eia_5y"])
        if st.form_submit_button("SAVE EIA"):
            st.session_state.data.update({"eia_curr": e_curr, "eia_prev": e_prev, "eia_5y": e_5y})
            save_data(st.session_state.data)
            st.rerun()

    with st.form("cot_positioning_form"):
        st.subheader("🏛️ COT Positioning")
        st.write(f"Next: {get_countdown(4, 21, 30)}")
        c_l, c_s = st.columns(2)
        m_l = c_l.number_input("MM Long", value=st.session_state.data["mm_l"])
        m_s = c_s.number_input("MM Short", value=st.session_state.data["mm_s"])
        co_l = c_l.number_input("Com Long", value=st.session_state.data["com_l"])
        co_s = c_s.number_input("Com Short", value=st.session_state.data["com_s"])
        re_l = c_l.number_input("Ret Long", value=st.session_state.data["ret_l"])
        re_s = c_s.number_input("Ret Short", value=st.session_state.data["ret_s"])
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": m_l, "mm_s": m_s, "com_l": co_l, "com_s": co_s, "ret_l": re_l, "ret_s": re_s})
            save_data(st.session_state.data)
            st.rerun()

# --- ANALIZA ---
hdd_list = get_14d_hdd()
ao = get_noaa_val("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
pna = get_noaa_val("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")
eia_wow = st.session_state.data["eia_curr"] - st.session_state.data["eia_prev"]
eia_5y_diff = st.session_state.data["eia_curr"] - st.session_state.data["eia_5y"]

# --- MAIN ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. HDD 14-DAY TABLE
    st.subheader("🌡️ 14-Day PW-HDD Quantum Forecast")
    
    hdd_df = pd.DataFrame({
        "Day": [f"D+{i+1}" for i in range(14)],
        "HDD Score": [round(x, 2) for x in hdd_list],
        "Term": ["Short" if i < 7 else "Long" for i in range(14)]
    })
    st.table(hdd_df.set_index("Day").T)

    # 2. STRATEGIC NARRATIVE
    st.subheader("📜 Executive Strategic Narrative")
    
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA DIVERGENCIJA:</strong> Zalihe su na <strong>{st.session_state.data["eia_curr"]} Bcf</strong>. 
        Tjedna promjena: <strong>{eia_wow:+} Bcf</strong>. Odstupanje od 5y prosjeka: 
        <span class='{"bull-text" if eia_5y_diff < 0 else "bear-text"}'>{eia_5y_diff:+} Bcf ({ (eia_5y_diff/st.session_state.data["eia_5y"])*100 :.2f}%)</span>.<br><br>
        <strong>Sinteza:</strong> Managed Money Neto ({st.session_state.data["mm_l"] - st.session_state.data["mm_s"]:+,}) sugerira visok oprez. 
        Ako HDD u Long Term sekciji raste dok je AO ({ao:.2f}) negativan, divergencija s trenutnom cijenom je tvoja prilika.
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW
    st.components.v1.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    # 4. RADAR TABS
    t_noaa, t_spag = st.tabs(["NOAA WEATHER (2x2)", "SPAGHETTI TRENDS"])
    with t_noaa:
        r1_c1, r1_c2 = st.columns(2)
        r1_c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp")
        r1_c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        r2_c1, r2_c2 = st.columns(2)
        r2_c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        r2_c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")

    with t_spag:
        
        idx_c = st.columns(3)
        idxs = [("AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Ispod -2.0 = EXTREME BULLISH"),
                ("NAO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Ispod -1.5 = EXTREME BULLISH"),
                ("PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Iznad 1.5 = EXTREME BULLISH")]
        for i, (n, v, u, l) in enumerate(idxs):
            with idx_c[i]:
                st.image(u)
                st.markdown(f"**{n}: {v:.2f}**")
                st.markdown(f"<div class='legend-box'>{l}</div>", unsafe_allow_html=True)

with col_right:
    st.subheader("📱 Social Intelligence")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">X LIST (NATGAS)</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔭 Intelligence Hub")
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE REPORT</a>', unsafe_allow_html=True)
