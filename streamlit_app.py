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
st.set_page_config(page_title="NatGas Sniper V82-Final", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 10px; margin-bottom: 25px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .ext-bull { color: #00FF00 !important; font-weight: 900; text-decoration: underline; background-color: #004400; padding: 2px 5px; border-radius: 3px; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.85rem; color: #CCC; line-height: 1.5; border-radius: 5px; }
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

# --- PERSISTENCE ENGINE (Fixed Keys) ---
DATA_FILE = "sniper_final_fixed.json"

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
                return {**defaults, **loaded} # Spaja stare i nove ključeve
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state:
    st.session_state.data = load_data()

# --- POMOĆNE FUNKCIJE ---
def get_ng_price():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/NG=F", headers={'User-Agent': 'Mozilla/5.0'}).json()
        m = r['chart']['result'][0]['meta']
        return m['regularMarketPrice'], ((m['regularMarketPrice'] - m['previousClose']) / m['previousClose']) * 100
    except: return 0.0, 0.0

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

def get_14d_hdd():
    cities = {"Chicago": [41.87, -87.62, 0.40], "NYC": [40.71, -74.00, 0.35], "Detroit": [42.33, -83.04, 0.25]}
    daily_hdds = [0.0] * 14
    try:
        for c, info in cities.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            mx, mn = res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min']
            for d in range(14):
                daily_hdds[d] += max(0, 65 - ((mx[d] + mn[d]) / 2)) * info[2]
        return daily_hdds
    except: return [0.0] * 14

def get_countdown(day_idx, hour, minute):
    now = datetime.now(pytz.timezone('Europe/Zagreb'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=(day_idx - now.weekday()) % 7)
    if now > target: target += timedelta(days=7)
    diff = target - now
    return f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    price, pct = get_ng_price()
    st.metric("Henry Hub Live", f"${price:.3f}", f"{pct:+.2f}%")
    
    with st.form("storage_form"):
        st.subheader("📦 Storage Box")
        st.write(f"EIA: {get_countdown(3, 16, 30)}")
        e_c = st.number_input("Current Bcf", value=st.session_state.data["eia_curr"])
        e_p = st.number_input("Prev Bcf", value=st.session_state.data["eia_prev"])
        e_5 = st.number_input("5y Avg Bcf", value=st.session_state.data["eia_5y"])
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": e_c, "eia_prev": e_p, "eia_5y": e_5})
            save_data(st.session_state.data)
            st.rerun()

    with st.form("cot_form"):
        st.subheader("🏛️ COT Box")
        st.write(f"COT: {get_countdown(4, 21, 30)}")
        c1, c2 = st.columns(2)
        ml = c1.number_input("MM Long", value=st.session_state.data["mm_l"])
        ms = c2.number_input("MM Short", value=st.session_state.data["mm_s"])
        cl = c1.number_input("Comm Long", value=st.session_state.data["com_l"])
        cs = c2.number_input("Comm Short", value=st.session_state.data["com_s"])
        rl = c1.number_input("Ret Long", value=st.session_state.data["ret_l"])
        rs = c2.number_input("Ret Short", value=st.session_state.data["ret_s"])
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs, "ret_l": rl, "ret_s": rs})
            save_data(st.session_state.data)
            st.rerun()

# --- ANALIZA ---
hdd_list = get_14d_hdd()
ao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. 14-DAY HDD TABLE
    st.subheader("🌡️ 14-Day PW-HDD Forecast")
    
    hdd_df = pd.DataFrame({
        "Day": [f"D+{i+1}" for i in range(14)],
        "Score": [round(x, 2) for x in hdd_list],
        "Term": ["Short" if i < 7 else "Long" for i in range(14)]
    })
    st.table(hdd_df.set_index("Day").T)

    # 2. NARRATIVE (Divergence Focus)
    st.subheader("📜 Executive Strategic Narrative")
    
    e_diff = st.session_state.data["eia_curr"] - st.session_state.data["eia_5y"]
    mm_net = st.session_state.data["mm_l"] - st.session_state.data["mm_s"]
    
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>STATUS:</strong> NG na <strong>${price:.3f}</strong>. Managed Money Neto: <strong>{mm_net:+,}</strong>. 
        Zalihe su <strong>{st.session_state.data["eia_curr"]} Bcf</strong> (Odstupanje: <strong>{e_diff:+} Bcf</strong>).<br><br>
        <strong>DIVERGENCIJA:</strong> Ukoliko vidiš teški MM Short dok AO ({ao['now']:.2f}) pada i HDD u Long Term sekciji raste, 
        gledaš u masivnu asimetriju koja će eksplodirati čim prvi fond krene zatvarati poziciju.
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW
    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    # 4. RADAR TABS
    t_noaa, t_spag = st.tabs(["NOAA WEATHER (2x2)", "SPAGHETTI TRENDS"])
    with t_noaa:
        r1c1, r1c2 = st.columns(2)
        r1c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp")
        r1c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        r2c1, r2c2 = st.columns(2)
        r2c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        r2c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")

    with t_spag:
        
        idx_cols = st.columns(3)
        def get_grad(v, n):
            if n == "PNA": return ("EXTREME BULLISH", "ext-bull") if v > 1.5 else ("BULLISH", "bull-text") if v > 0.5 else ("BEARISH", "bear-text")
            return ("EXTREME BULLISH", "ext-bull") if v < -2.0 else ("BULLISH", "bull-text") if v < -0.5 else ("BEARISH", "bear-text")
        
        idxs = [("AO", ao), ("NAO", nao), ("PNA", pna)]
        urls = ["https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif"]
        
        for i, (name, d) in enumerate(idxs):
            with idx_cols[i]:
                st.image(urls[i])
                gr, css = get_grad(d['now'], name)
                st.markdown(f"**{name}: {d['now']:.2f}** | <span class='{css}'>{gr}</span>", unsafe_allow_html=True)
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")

with col_right:
    st.subheader("📱 Social Intelligence")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST (LIVE)</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🔭 Intelligence Hub")
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE LIVE</a>', unsafe_allow_html=True)
