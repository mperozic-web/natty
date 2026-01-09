import streamlit as st
import pandas as pd
import requests
import io
import json
import os
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V88", layout="wide")

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
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE (Safe-Load) ---
DATA_FILE = "sniper_v88_master.json"

def get_defaults():
    return {
        "eia_curr": 3375, "eia_prev": 3413, "eia_5y": 3317,
        "mm_l": 288456, "mm_s": 424123, "com_l": 512000, "com_s": 380000, "ret_l": 54120, "ret_s": 32100
    }

def load_data():
    defaults = get_defaults()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                loaded = json.load(f)
                # Sigurnosna provjera ključeva (Spas od KeyError-a)
                for k, v in defaults.items():
                    if k not in loaded: loaded[k] = v
                return loaded
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

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
    # Ključni grid gradovi
    cities = {"Chicago": [41.87, -87.62, 0.40], "NYC": [40.71, -74.00, 0.35], "Detroit": [42.33, -83.04, 0.25]}
    daily_res = [0.0] * 14
    try:
        for c, info in cities.items():
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto").json()
            mx, mn = r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min']
            for d in range(14):
                daily_res[d] += max(0, 65 - ((mx[d] + mn[d]) / 2)) * info[2]
        return daily_res
    except: return [0.0] * 14

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return df.iloc[-1, -1]
    except: return 0.0

# --- SIDEBAR (Trajni odvojeni unosi) ---
with st.sidebar:
    st.header("🎯 Sniper Master Console")
    
    with st.form("storage_form_v88"):
        st.subheader("📦 EIA Storage Control")
        st.write(f"EIA Countdown: {get_countdown(3, 16, 30)}")
        c_e = st.number_input("Current Bcf", value=st.session_state.data["eia_curr"])
        p_e = st.number_input("Prev Bcf", value=st.session_state.data["eia_prev"])
        a_e = st.number_input("5y Avg Bcf", value=st.session_state.data["eia_5y"])
        if st.form_submit_button("Spremi EIA Podatke"):
            st.session_state.data.update({"eia_curr": c_e, "eia_prev": p_e, "eia_5y": a_e})
            save_data(st.session_state.data)
            st.rerun()

    with st.form("cot_form_v88"):
        st.subheader("🏛️ COT Positioning Control")
        st.write(f"COT Countdown: {get_countdown(4, 21, 30)}")
        col1, col2 = st.columns(2)
        ml = col1.number_input("MM Long", value=st.session_state.data["mm_l"])
        ms = col2.number_input("MM Short", value=st.session_state.data["mm_s"])
        cl = col1.number_input("Comm Long", value=st.session_state.data["com_l"])
        cs = col2.number_input("Comm Short", value=st.session_state.data["com_s"])
        rl = col1.number_input("Ret Long", value=st.session_state.data["ret_l"])
        rs = col2.number_input("Ret Short", value=st.session_state.data["ret_s"])
        if st.form_submit_button("Spremi COT Podatke"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs, "ret_l": rl, "ret_s": rs})
            save_data(st.session_state.data)
            st.rerun()

# --- ANALIZA ---
hdd_forecast = get_14d_hdd()
ao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")
eia_wow = st.session_state.data["eia_curr"] - st.session_state.data["eia_prev"]
eia_5y_diff = st.session_state.data["eia_curr"] - st.session_state.data["eia_5y"]

# --- MAIN LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. 14-DAY HDD TABLE
    st.subheader("🌡️ 14-Day PW-HDD Index (Quantum Grid)")
    
    hdd_df = pd.DataFrame({
        "Day": [f"D+{i+1}" for i in range(14)],
        "Score": [round(x, 2) for x in hdd_forecast],
        "Horizon": ["Short-Term" if i < 7 else "Long-Term" for i in range(14)]
    })
    st.table(hdd_df.set_index("Day").T)

    # 2. STRATEGIC NARRATIVE
    st.subheader("📜 Executive Strategic Narrative")
    
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>STATUS ZALIHA:</strong> Trenutno stanje <strong>{st.session_state.data["eia_curr"]} Bcf</strong>. 
        Promjena (WoW): <strong>{eia_wow:+} Bcf</strong>. Deficit vs 5y prosjek: 
        <span class='{"bull-text" if eia_5y_diff < 0 else "bear-text"}'>{eia_5y_diff:+} Bcf</span>.<br><br>
        <strong>DETEKCIJA DIVERGENCIJA:</strong> Managed Money Neto pozicija iznosi <strong>{st.session_state.data["mm_l"] - st.session_state.data["mm_s"]:+,}</strong>. 
        Ukoliko su fondovi u teškom shortu dok HDD u 'Long-Term' horizontu pokazuje rastuće vrijednosti, a AO ({ao:.2f}) ostaje negativan, tržište je u stanju opasne asimetrije za medvjede.
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW
    st.components.v1.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    # 4. RADAR TABS
    st.subheader("📡 Intelligence Radar")
    t_noaa, t_spag = st.tabs(["NOAA WEATHER (2x2 Grid)", "SPAGHETTI TRENDS"])
    
    with t_noaa:
        r1c1, r1c2 = st.columns(2)
        r1c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp")
        r1c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        r2c1, r2c2 = st.columns(2)
        r2c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        r2c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")

    with t_spag:
        
        idx_cols = st.columns(3)
        idxs = [("AO Index", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Ispod -2.0: EXTREME BULLISH"),
                ("NAO Index", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Ispod -1.5: EXTREME BULLISH"),
                ("PNA Index", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Iznad 1.5: EXTREME BULLISH")]
        for i, (n, v, url, leg) in enumerate(idxs):
            with idx_cols[i]:
                st.image(url)
                st.markdown(f"**{n}: {v:.2f}**")
                st.markdown(f"<div class='legend-box'>{leg}</div>", unsafe_allow_html=True)

# --- DESNA STRANA (Strateške grupe) ---
with col_right:
    st.subheader("📱 Social Intelligence")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">X LIST (NATGAS LIVE)</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD SNIPER GROUP</a>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔬 Analysis Hub")
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS (ECMWF)</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE LIVE</a>', unsafe_allow_html=True)
