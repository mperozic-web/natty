import streamlit as st
import pandas as pd
import requests
import io
import feedparser
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V79", layout="wide")

# CSS: Visoki kontrast, bez em-dasha, profesionalni terminal look
st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #008CFF; padding: 30px; background-color: #0A0A0A; border-radius: 10px; margin-bottom: 25px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .ext-bull { color: #00FF00 !important; font-weight: 900; text-decoration: underline; }
    .hdd-box { background: #111; border: 1px solid #333; padding: 15px; border-radius: 5px; text-align: center; }
    .delta-plus { color: #00FF00; font-size: 0.9rem; font-weight: bold; }
    .delta-minus { color: #FF4B4B; font-size: 0.9rem; font-weight: bold; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.85rem; color: #CCC; line-height: 1.5; border-radius: 5px; }
    .external-link { display: block; padding: 12px; margin-bottom: 10px; background: #002B50; color: #008CFF; text-decoration: none; border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PROXY-8 HDD ENGINE ---
PROXY_CITIES = {
    "Chicago": {"lat": 41.87, "lon": -87.62, "weight": 0.25},
    "New York": {"lat": 40.71, "lon": -74.00, "weight": 0.20},
    "Detroit": {"lat": 42.33, "lon": -83.04, "weight": 0.15},
    "Philadelphia": {"lat": 39.95, "lon": -75.16, "weight": 0.10},
    "Boston": {"lat": 42.36, "lon": -71.05, "weight": 0.10},
    "Indianapolis": {"lat": 39.76, "lon": -86.15, "weight": 0.08},
    "Minneapolis": {"lat": 44.97, "lon": -93.26, "weight": 0.07},
    "Columbus": {"lat": 39.96, "lon": -82.99, "weight": 0.05}
}

def get_current_hdd():
    total_hdd = 0
    try:
        for city, info in PROXY_CITIES.items():
            url = f"https://api.open-meteo.com/v1/forecast?latitude={info['lat']}&longitude={info['lon']}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto"
            res = requests.get(url).json()
            daily_max = res['daily']['temperature_2m_max']
            daily_min = res['daily']['temperature_2m_min']
            city_hdd = sum([max(0, 65 - ((mx + mn) / 2)) for mx, mn in zip(daily_max, daily_min)])
            total_hdd += city_hdd * info['weight']
        return round(total_hdd, 2)
    except: return 0.0

if 'last_hdd' not in st.session_state:
    st.session_state.last_hdd = get_current_hdd()

current_hdd = get_current_hdd()
hdd_delta = current_hdd - st.session_state.last_hdd

# --- DATA ENGINES ---
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
        now = df.iloc[-1, -1]
        return {"now": now, "d_chg": now - df.iloc[-2, -1], "w_chg": now - df.iloc[-7, -1]}
    except: return {"now": 0.0, "d_chg": 0.0, "w_chg": 0.0}

@st.cache_data(ttl=1800)
def fetch_natgas_news():
    rss_url = "https://news.google.com/rss/search?q=Natural+gas+OR+natgas+OR+%22henry+hub%22+when:7d&hl=en-US&gl=US&ceid=US:en"
    return feedparser.parse(rss_url).entries[:8]

def get_countdown(day_idx, hour, minute):
    now = datetime.now(pytz.timezone('Europe/Zagreb'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=(day_idx - now.weekday()) % 7)
    if now > target: target += timedelta(days=7)
    diff = target - now
    return f"{diff.days}d {diff.seconds // 3600}h {(diff.seconds // 60) % 60}m"

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ Sniper Controls")
    if st.button("🔄 FORCE MODEL RE-RUN"):
        st.session_state.last_hdd = current_hdd
        st.cache_data.clear()
        st.rerun()
    
    price, pct = get_ng_price()
    st.metric("Henry Hub Live", f"${price:.3f}", f"{pct:+.2f}%")
    
    with st.form("master_input"):
        st.subheader("🏛️ Storage & COT")
        eia_val = st.number_input("Storage (Bcf)", value=3375)
        eia_5y = st.number_input("5y Avg (Bcf)", value=3317)
        c1, c2 = st.columns(2)
        mm_l = c1.number_input("MM Long", value=288456)
        mm_s = c2.number_input("MM Short", value=424123)
        ret_l = c1.number_input("Retail Long", value=54120)
        ret_s = c2.number_input("Retail Short", value=32100)
        st.form_submit_button("SINKRONIZIRAJ")

# --- ANALIZA PODATAKA ---
ao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- LAYOUT ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # 1. HDD MOMENTUM MODULE
    st.subheader("🌡️ Proprietary HDD Momentum (14-Day Proxy)")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        d_class = "delta-plus" if hdd_delta >= 0 else "delta-minus"
        st.markdown(f"<div class='hdd-box'><h4>14d PW-HDD Index</h4><h2 style='color:#008CFF;'>{current_hdd}</h2><p class='{d_class}'>{'▲' if hdd_delta >= 0 else '▼'} {abs(hdd_delta):.2f} od zadnjeg runa</p></div>", unsafe_allow_html=True)
    with c2:
        status = "BULLISH (Hladnije)" if hdd_delta > 0 else "BEARISH (Toplije)"
        st.markdown(f"<div class='hdd-box'><h4>Model Momentum</h4><h2 class='{'bull-text' if hdd_delta > 0 else 'bear-text'}'>{status}</h2><p>Trend prognoze</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='hdd-box'><h4>Next Triggers</h4><p>EIA: {get_countdown(3, 16, 30)}<br>COT: {get_countdown(4, 21, 30)}</p></div>", unsafe_allow_html=True)

    # 2. STRATEGIC NARRATIVE
    st.subheader("📜 The Strategic Narrative")
    eia_diff = eia_val - eia_5y
    eia_pct = (eia_diff / eia_5y) * 100
    mm_net = mm_l - mm_s
    
    st.markdown(f"""
    <div class='summary-narrative'>
        Henry Hub operira pri <strong>${price:.3f}</strong> dok naš <strong>Quantum HDD Index</strong> bilježi <strong>{current_hdd}</strong> bodova. 
        Promjena od <strong>{hdd_delta:+.2f}</strong> sugerira da {'vremenska podrška jača' if hdd_delta > 0 else 'vremenska podrška slabi'}. 
        Uz deficit zaliha od <strong>{eia_diff:+} Bcf ({eia_pct:+.2f}%)</strong> i MM neto poziciju od <strong>{mm_net:+,}</strong>, 
        tržište je u stanju {'visoke konvergencije bika' if (eia_diff < 0 and hdd_delta > 0) else 'fragmentirane asimetrije'}.
    </div>
    """, unsafe_allow_html=True)

    # 3. TRADINGVIEW & WEATHER TABS
    st.subheader("📊 Execution & Weather Radar")
    t1, t2, t3 = st.tabs(["CHART", "NOAA MAPS", "SPAGHETTI TRENDS"])
    
    with t1:
        components.html('<div id="tv" style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script></div>', height=450)
    
    with t2:
        c1, c2 = st.columns(2)
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp")
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")
        
    with t3:
        idx_cols = st.columns(3)
        
        def draw_idx(col, name, data, url, logic):
            with col:
                st.image(url)
                st.markdown(f"**{name}: {data['now']:.2f}**")
                st.markdown(f"<div class='legend-box'>{logic}</div>", unsafe_allow_html=True)
        
        draw_idx(idx_cols[0], "AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Negativno = Hladno na jug (BULL).")
        draw_idx(idx_cols[1], "NAO", nao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Negativno = Blokada Atlantika (BULL).")
        draw_idx(idx_cols[2], "PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Pozitivno = Hladno na istok (BULL).")

with col_right:
    st.subheader("📰 News & Intel")
    news = fetch_natgas_news()
    for n in news:
        st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{n.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{n.title}</a></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<a href="http://celsiusenergy.co/" target="_blank" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" target="_blank" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
