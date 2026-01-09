import streamlit as st
import pandas as pd
import requests
import io
import feedparser
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V82", layout="wide")

# CSS: Visoki kontrast, "V72 style" poveznice i precizni terminal look
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 10px; margin-bottom: 25px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .ext-bull { color: #00FF00 !important; font-weight: 900; text-decoration: underline; background-color: #004400; padding: 2px 5px; border-radius: 3px; }
    .ext-bear { color: #FF4B4B !important; font-weight: 900; text-decoration: underline; background-color: #440000; padding: 2px 5px; border-radius: 3px; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.8rem; color: #CCC; line-height: 1.4; border-radius: 5px; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    
    /* Prettier Links (V72 style) */
    .external-link { 
        display: block; 
        padding: 10px; 
        margin-bottom: 8px; 
        background: #002B50; 
        color: #008CFF !important; 
        text-decoration: none !important; 
        border-radius: 4px; 
        font-weight: bold; 
        text-align: center; 
        border: 1px solid #004080;
    }
    .external-link:hover { background: #004080; color: #FFFFFF !important; }
    
    .news-card { padding: 8px; border-bottom: 1px solid #222; margin-bottom: 5px; font-size: 0.8rem; }
    .news-title { color: #008CFF !important; text-decoration: none; font-weight: bold; }
    
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- POMOĆNE FUNKCIJE (Top-level) ---
@st.cache_data(ttl=1800)
def fetch_natgas_news():
    rss_url = "https://news.google.com/rss/search?q=Natural+gas+OR+natgas+OR+%22henry+hub%22+when:7d&hl=en-US&gl=US&ceid=US:en"
    return feedparser.parse(rss_url).entries[:6]

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
    cities = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10], "Indy": [39.76, -86.15, 0.08], "Minny": [44.97, -93.26, 0.07], "Columbus": [39.96, -82.99, 0.05]}
    total_hdd = 0
    try:
        for c, info in cities.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            daily_avg = [(mx + mn) / 2 for mx, mn in zip(res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min'])]
            total_hdd += sum([max(0, 65 - t) for t in daily_avg]) * info[2]
        return round(total_hdd, 2)
    except: return 0.0

def get_gradation(val, name):
    if name == "PNA":
        if val > 1.5: return "EXTREME BULLISH", "ext-bull"
        return ("BULLISH", "bull-text") if val > 0.5 else ("BEARISH", "bear-text")
    else:
        if val < -2.0: return "EXTREME BULLISH", "ext-bull"
        return ("BULLISH", "bull-text") if val < -0.5 else ("BEARISH", "bear-text")

# --- SIDEBAR (LIJEVO) ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    price, pct = get_ng_price()
    st.metric("Henry Hub Live", f"${price:.3f}", f"{pct:+.2f}%")
    
    with st.form("master_input"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        eia_v = st.number_input("Current Bcf", value=3375)
        eia_5 = st.number_input("5y Avg Bcf", value=3317)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Box")
        c1, c2 = st.columns(2)
        nc_l = c1.number_input("MM Long", value=288456)
        nc_s = c2.number_input("MM Short", value=424123)
        cm_l = c1.number_input("Comm Long", value=512000)
        cm_s = c2.number_input("Comm Short", value=380000)
        rt_l = c1.number_input("Retail Long", value=54120)
        rt_s = c2.number_input("Retail Short", value=32100)
        st.markdown("</div>", unsafe_allow_html=True)
        st.form_submit_button("SINKRONIZIRAJ RADAR")

    st.markdown("---")
    st.subheader("🔗 My Brokers")
    st.markdown('<a href="https://www.plus500.com/" class="external-link">PLUS 500 EXECUTION</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://capital.com/" class="external-link">CAPITAL.COM EXECUTION</a>', unsafe_allow_html=True)

# --- ANALIZA PODATAKA ---
if 'last_hdd' not in st.session_state: st.session_state.last_hdd = get_current_hdd()
curr_hdd = get_current_hdd()
hdd_delta = curr_hdd - st.session_state.last_hdd

ao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. HDD LEGEND & MOMENTUM (At the top)
    st.markdown("### 🌡️ HDD Quantum & Model Momentum")
    st.markdown("""
    **Legend:** *14-Day PW HDD Index* je tvoj mjerač ukupne potražnje (što veći broj, veća potrošnja). 
    *Model Momentum* pokazuje je li zadnja prognoza postala hladnija (Bullish) ili toplija (Bearish).
    """)
    mc1, mc2 = st.columns(2)
    mc1.metric("14d PW-HDD Index", f"{curr_hdd}", f"{hdd_delta:+.2f} (Model Delta)")
    mc2.markdown(f"Status: <span class='{'bull-text' if hdd_delta > 0 else 'bear-text'}'>{'BULLISH (Hladnije)' if hdd_delta > 0 else 'BEARISH (Toplije)'}</span>", unsafe_allow_html=True)

    # 2. EXECUTIVE NARRATIVE (Divergence Focus)
    st.subheader("📜 Executive Strategic Narrative")
    e_diff = eia_v - eia_5
    nc_net = nc_l - nc_s
    
    div_logic = "Indikatori su usklađeni."
    if e_diff < 0 and hdd_delta < -5:
        div_logic = "DIVERGENCIJA: Zalihe su niske (BULL), ali modeli zatopljuju (BEAR). Oprez s long pozicijama."
    elif e_diff > 0 and hdd_delta > 5:
        div_logic = "DIVERGENCIJA: Suficit zaliha (BEAR), ali modeli snažno hlade (BULL). Moguć tehnički bounce."

    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA ASIMETRIJE:</strong> Henry Hub na <strong>${price:.3f}</strong>. Managed Money neto: <strong>{nc_net:+,}</strong>. 
        Zalihe bilježe <strong>{e_diff:+} Bcf</strong> odstupanja od prosjeka.<br><br>
        <strong>DIVERGENCIJA:</strong> {div_logic}<br>
        <strong>ZAKLJUČAK:</strong> {'Sustav detektira konvergenciju za LONG.' if (e_diff < 0 and ao['now'] < 0) else 'Tržište čeka novi impuls.'}
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW
    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    # 4. RADAR TABS
    st.subheader("📡 Intelligence Radar")
    t_noaa, t_spag = st.tabs(["NOAA WEATHER", "SPAGHETTI TRENDS"])
    
    with t_noaa:
        c1, c2 = st.columns(2)
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="Short-Term Temp", width=380)
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="Long-Term Temp", width=380)
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="Short-Term Precip", width=380)
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="Long-Term Precip", width=380)

    with t_spag:
        idx_cols = st.columns(3)
        idxs = [
            ("AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Ispod -2.0: Extreme Bullish."),
            ("NAO", nao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Ispod -1.5: Extreme Bullish."),
            ("PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Iznad 1.5: Extreme Bullish.")
        ]
        for i, (name, d, url, leg) in enumerate(idxs):
            with idx_cols[i]:
                st.image(url)
                gr, css = get_gradation(d['now'], name)
                st.markdown(f"**{name}: {d['now']:.2f}** | <span class='{css}'>{gr}</span>", unsafe_allow_html=True)
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")
                st.markdown(f"<div class='legend-box'>{leg}</div>", unsafe_allow_html=True)

# --- RIGHT PANEL ---
with col_right:
    st.subheader("📰 Google News Feed")
    news_items = fetch_natgas_news()
    for n in news_items:
        st.markdown(f"<div class='news-card'><a href='{n.link}' target='_blank' class='news-title'>{n.title}</a><br><small>{n.published}</small></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("🐦 X Live Timeline")
    # Zamijeni 'NatGasWeather' sa svojim handleom ako želiš svoj X feed
    components.html('<a class="twitter-timeline" data-height="400" data-theme="dark" href="https://twitter.com/NatGasWeather?ref_src=twsrc%5Etfw">Tweets</a> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>', height=400)

    st.markdown("---")
    st.subheader("🔗 Resources")
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE REPORT</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">DISCORD GROUP</a>', unsafe_allow_html=True)
