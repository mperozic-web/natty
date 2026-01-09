import streamlit as st
import pandas as pd
import requests
import io
import feedparser
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V80", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .summary-narrative { font-size: 1.1rem; line-height: 1.7; color: #EEEEEE; border: 2px solid #008CFF; padding: 25px; background-color: #0A0A0A; border-radius: 8px; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .ext-bull { color: #00FF00 !important; font-weight: 900; text-decoration: underline; background-color: #004400; padding: 2px 5px; }
    .ext-bear { color: #FF4B4B !important; font-weight: 900; text-decoration: underline; background-color: #440000; padding: 2px 5px; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.85rem; color: #CCC; border-radius: 5px; margin-top: 10px; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 20px; background: #0A0A0A; }
    .broker-link { display: block; padding: 10px; margin-top: 5px; background: #111; color: #008CFF; text-decoration: none; border: 1px solid #333; text-align: center; font-weight: bold; border-radius: 4px; }
    .broker-link:hover { background: #008CFF; color: #FFF; }
    </style>
    """, unsafe_allow_html=True)

# --- ENGINES ---
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
            d_max, d_min = res['daily']['temperature_2m_max'], res['daily']['temperature_2m_min']
            total_hdd += sum([max(0, 65 - ((mx + mn) / 2)) for mx, mn in zip(d_max, d_min)]) * info['weight']
        return round(total_hdd, 2)
    except: return 0.0

def get_noaa_full(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

# --- SIDEBAR (LIJEVO) ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    
    # STORAGE BOX
    st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
    st.subheader("📦 Storage Input")
    eia_val = st.number_input("Current Bcf", value=3375)
    eia_5y = st.number_input("5y Average Bcf", value=3317)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # COT BOX
    st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
    st.subheader("🏛️ COT Positioning")
    c1, c2 = st.columns(2)
    mm_l = c1.number_input("MM Long", value=288456)
    mm_s = c2.number_input("MM Short", value=424123)
    com_l = c1.number_input("Comm Long", value=512000)
    com_s = c2.number_input("Comm Short", value=380000)
    ret_l = c1.number_input("Retail Long", value=54120)
    ret_s = c2.number_input("Retail Short", value=32100)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # BROKER LINKS
    st.subheader("🔗 Broker Access")
    st.markdown('<a href="https://www.plus500.com/" class="broker-link">PLUS 500</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://capital.com/" class="broker-link">CAPITAL.COM</a>', unsafe_allow_html=True)

# --- ANALIZA ---
if 'last_hdd' not in st.session_state: st.session_state.last_hdd = get_current_hdd()
current_hdd = get_current_hdd()
hdd_delta = current_hdd - st.session_state.last_hdd

ao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv")
nao = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv")
pna = get_noaa_full("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- CENTRALNI DIO (Main) ---
col_main, col_right = st.columns([4, 1.2])

with col_main:
    # HDD LEGEND & STATUS
    
    st.markdown(f"""
    ### 🌡️ HDD Quantum & Model Momentum
    **Legend:** *14-Day PW HDD Index* mjeri ukupnu potražnju za grijanjem u ključnim čvorištima SAD-a. *Model Momentum* pokazuje je li zadnji meteorološki model postao hladniji (Bullish) ili topliji (Bearish).
    """)
    
    mc1, mc2 = st.columns(2)
    with mc1:
        st.metric("14d PW-HDD Index", f"{current_hdd}", f"{hdd_delta:+.2f} (Model Delta)")
    with mc2:
        m_bias = "BULLISH" if hdd_delta > 0 else "BEARISH"
        st.markdown(f"Model Momentum: <span class='{'bull-text' if hdd_delta > 0 else 'bear-text'}'>{m_bias}</span>", unsafe_allow_html=True)

    # STRATEGIC NARRATIVE (Focus: Divergences)
    st.subheader("📜 Executive Strategic Narrative")
    eia_diff = eia_val - eia_5y
    mm_net = mm_l - mm_s
    
    # Divergence Logic
    div_text = "Nema značajnih divergencija."
    if eia_diff < 0 and hdd_delta < 0:
        div_text = "DIVERGENCIJA: Zalihe su niske (BULL), ali modeli zatopljuju (BEAR). Rizik od pada cijene usprkos deficitu."
    elif eia_diff > 0 and hdd_delta > 0:
        div_text = "DIVERGENCIJA: Suficit zaliha (BEAR), ali dolazi ekstremna hladnoća (BULL). Moguć snažan kratkoročni odraz."
    
    st.markdown(f"""
    <div class='summary-narrative'>
        <strong>ANALIZA DIVERGENCIJA:</strong> {div_text}<br><br>
        <strong>Sinteza:</strong> Managed Money pozicija od {mm_net:+,} sugerira da špekulanti {'očekuju daljnji pad' if mm_net < 0 else 'akumuliraju long'}. 
        Ako se AO ({ao['now']:.2f}) i PNA ({pna['now']:.2f}) ne usklade u idućih 48h, tržište će ostati u rasponu. 
        Potraži potvrdu u 'Extreme Bullish' gradacijama špageta.
    </div>
    """, unsafe_allow_html=True)

    # TRADINGVIEW EMBED
    components.html('<div id="tv" style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "timezone": "Europe/Zagreb", "theme": "dark", "container_id": "tv"});</script></div>', height=450)

    # EXECUTION & WEATHER RADAR TABS
    st.subheader("📡 Execution & Weather Radar")
    t_noaa, t_spag = st.tabs(["NOAA MAPS", "SPAGHETTI TRENDS"])
    
    with t_noaa:
        c1, c2 = st.columns(2)
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="Short-Term Temp (6-10d)")
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="Long-Term Temp (8-14d)")
        c1.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="Short-Term Precip (6-10d)")
        c2.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="Long-Term Precip (8-14d)")

    with t_spag:
        
        idx_cols = st.columns(3)
        
        def get_gradation(val, name):
            if name == "PNA":
                if val > 1.5: return "EXTREME BULLISH", "ext-bull"
                if val > 0.5: return "BULLISH", "bull-text"
                return "BEARISH", "bear-text"
            else:
                if val < -2.0: return "EXTREME BULLISH", "ext-bull"
                if val < -0.5: return "BULLISH", "bull-text"
                return "BEARISH", "bear-text"

        indices = [
            ("AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "Ispod -2.0 = Extreme Bullish (Pucanje vrtloga)."),
            ("NAO", nao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "Ispod -1.5 = Extreme Bullish (Blokada Atlantika)."),
            ("PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "Iznad 1.5 = Extreme Bullish (Dolina na istoku).")
        ]
        
        for i, (name, data, img, legend) in enumerate(indices):
            with idx_cols[i]:
                st.image(img)
                grad, css = get_gradation(data['now'], name)
                st.markdown(f"**{name}: {data['now']:.2f}** | <span class='{css}'>{grad}</span>", unsafe_allow_html=True)
                st.write(f"Dan: {data['now']-data['yesterday']:+.2f} | Tjedan: {data['now']-data['last_week']:+.2f}")
                st.markdown(f"<div class='legend-box'>{legend}</div>", unsafe_allow_html=True)

# --- DESNA STRANA (News & Twitter) ---
with col_right:
    st.subheader("🗞️ Intel & Social")
    
    # Twitter Feed (x.com)
    components.html("""
    <a class="twitter-timeline" data-height="500" data-theme="dark" href="https://twitter.com/NatGasWeather?ref_src=twsrc%5Etfw">Tweets by NatGasWeather</a> 
    <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
    """, height=500)
    
    st.markdown("---")
    st.subheader("🔗 External Resources")
    st.markdown("""
    <a href="http://celsiusenergy.co/" class="external-link" style="color:#008CFF;">CELSIUS ENERGY</a>
    <a href="https://www.wxcharts.com/" class="external-link" style="color:#008CFF;">WX CHARTS</a>
    <a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link" style="color:#008CFF;">EIA STORAGE REPORT</a>
    <a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link" style="color:#008CFF;">DISCORD GROUP</a>
    """, unsafe_allow_html=True)
