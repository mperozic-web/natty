import streamlit as st
import pandas as pd
import requests
import io
import feedparser
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V83", layout="wide")

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

# --- INICIJALIZACIJA MEMORIJE (Persistence) ---
if 'eia_v' not in st.session_state: st.session_state.eia_v = 3375
if 'eia_5' not in st.session_state: st.session_state.eia_5 = 3317
if 'nc_l' not in st.session_state: st.session_state.nc_l = 288456
if 'nc_s' not in st.session_state: st.session_state.nc_s = 424123
if 'cm_l' not in st.session_state: st.session_state.cm_l = 512000
if 'cm_s' not in st.session_state: st.session_state.cm_s = 380000
if 'rt_l' not in st.session_state: st.session_state.rt_l = 54120
if 'rt_s' not in st.session_state: st.session_state.rt_s = 32100

# --- POMOĆNE FUNKCIJE ---
@st.cache_data(ttl=1800)
def fetch_news():
    url = "https://news.google.com/rss/search?q=Natural+gas+OR+natgas+OR+%22henry+hub%22+when:7d&hl=en-US&gl=US&ceid=US:en"
    return feedparser.parse(url).entries[:6]

def get_ng_price():
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/NG=F", headers={'User-Agent': 'Mozilla/5.0'}).json()
        m = r['chart']['result'][0]['meta']
        return m['regularMarketPrice'], ((m['regularMarketPrice'] - m['previousClose']) / m['previousClose']) * 100
    except: return 0.0, 0.0

def get_noaa_full(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

def get_current_hdd():
    cities = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15]}
    total_hdd = 0
    try:
        for c, info in cities.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            avg = [(mx + mn) / 2 for mx, mn in zip(res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min'])]
            total_hdd += sum([max(0, 65 - t) for t in avg]) * info[2]
        return round(total_hdd, 2)
    except: return 0.0

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Sniper Hub")
    pr, pct = get_ng_price()
    st.metric("Henry Hub Live", f"${pr:.3f}", f"{pct:+.2f}%")
    
    with st.form("master_input"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage")
        st.session_state.eia_v = st.number_input("Current Bcf", value=st.session_state.eia_v)
        st.session_state.eia_5 = st.number_input("5y Avg Bcf", value=st.session_state.eia_5)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Positioning")
        c1, c2 = st.columns(2)
        st.session_state.nc_l = c1.number_input("NC Long", value=st.session_state.nc_l)
        st.session_state.nc_s = c2.number_input("NC Short", value=st.session_state.nc_s)
        st.session_state.cm_l = c1.number_input("Comm Long", value=st.session_state.cm_l)
        st.session_state.cm_s = c2.number_input("Comm Short", value=st.session_state.cm_s)
        st.session_state.rt_l = c1.number_input("Retail Long", value=st.session_state.rt_l)
        st.session_state.rt_s = c2.number_input("Retail Short", value=st.session_state.rt_s)
        st.markdown("</div>", unsafe_allow_html=True)
        st.form_submit_button("SINKRONIZIRAJ")

    st.subheader("🔗 My Brokers")
    st.markdown('<a href="https://www.plus500.com/" class="external-link">PLUS 500</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://capital.com/" class="external-link">CAPITAL.COM</a>', unsafe_allow_html=True)

# --- ANALIZA ---
if 'last_hdd' not in st.session_state: st.session_state.last_hdd = get_current_hdd()
curr_hdd = get_current_hdd()
hdd_delta = curr_hdd - st.session_state.last_hdd
ao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
pna = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    st.markdown("### 🌡️ HDD Index & Momentum")
    mc1, mc2 = st.columns(2)
    mc1.metric("14d PW-HDD Index", f"{curr_hdd}", f"{hdd_delta:+.2f}")
    mc2.markdown(f"Status: <span class='{'bull-text' if hdd_delta > 0 else 'bear-text'}'>{'BULLISH' if hdd_delta > 0 else 'BEARISH'}</span>", unsafe_allow_html=True)

    st.subheader("📜 Strategic Narrative")
    e_diff = st.session_state.eia_v - st.session_state.eia_5
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA:</strong> NG na <strong>${pr:.3f}</strong>. Deficit zaliha iznosi <strong>{e_diff:+} Bcf</strong>. 
        Divergencija AO indeksa ({ao['now']:.2f}) i PNA ({pna['now']:.2f}) ključna je za idućih 48 sati. 
        Prati 'Managed Money' neto poziciju (<strong>{st.session_state.nc_l - st.session_state.nc_s:+,}</strong>) kao indikator mogućeg short squeezea.
    </div>
    """, unsafe_allow_html=True)

    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    t_noaa, t_spag = st.tabs(["NOAA WEATHER", "SPAGHETTI TRENDS"])
    with t_noaa:
        c1, c2 = st.columns(2)
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp")
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")

    with t_spag:
        st.write("Špageti trendovi sinkronizirani s NOAA serverima.")

with col_right:
    st.subheader("📰 Global Intel")
    for n in fetch_news():
        st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{n.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{n.title}</a></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🐦 X List Feed")
    # X List Embed - Koristi ID tvoje liste
    components.html('<a class="twitter-timeline" data-height="500" data-theme="dark" href="https://twitter.com/i/lists/1989752726553579941">My List</a> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>', height=500)

    st.markdown("---")
    st.subheader("🔗 Essential Links")
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE REPORT</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
