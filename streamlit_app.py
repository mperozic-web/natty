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
st.set_page_config(page_title="NatGas Sniper V97", layout="wide")

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
    .grand-total-box { padding: 25px; background: #0F0F0F; border: 2px solid #008CFF; border-radius: 10px; text-align: center; margin-top: 20px; margin-bottom: 20px; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-bottom: 20px; color: white; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 6px; text-align: center; }
    .cell-bull { color: #00FF00 !important; font-weight: bold; }
    .cell-bear { color: #FF4B4B !important; font-weight: bold; }
    .term-highlight { background-color: rgba(0, 255, 0, 0.15) !important; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.8rem; color: #CCC; line-height: 1.4; border-radius: 5px; margin-top: 5px; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ---
DATA_FILE = "sniper_v97_final.json"
def load_data():
    defaults = {"eia_curr": 3375, "eia_prev": 3413, "eia_5y": 3317, "mm_l": 0, "mm_s": 0, "com_l": 0, "com_s": 0, "ret_l": 0, "ret_s": 0, "last_hdd_matrix": {}}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return {**defaults, **json.load(f)}
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

if 'data' not in st.session_state: st.session_state.data = load_data()

# --- ENGINES ---
CITIES = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}

@st.cache_data(ttl=3600)
def fetch_hdd_matrix():
    matrix = {}
    try:
        for city, info in CITIES.items():
            r = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={info[0]}&longitude={info[1]}&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&forecast_days=14&timezone=auto").json()
            h = [round(max(0, 65 - (mx + mn)/2), 2) for mx, mn in zip(r['daily']['temperature_2m_max'], r['daily']['temperature_2m_min'])]
            matrix[city] = h
        return matrix
    except: return {}

def get_noaa_idx(url):
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        return {"now": df.iloc[-1, -1], "yesterday": df.iloc[-2, -1], "last_week": df.iloc[-7, -1]}
    except: return {"now": 0.0, "yesterday": 0.0, "last_week": 0.0}

def get_grad(v, n):
    if n == "PNA": return ("EXTREME BULLISH", "bull-text") if v > 1.5 else ("BULLISH", "bull-text") if v > 0.5 else ("BEARISH", "bear-text")
    return ("EXTREME BULLISH", "bull-text") if v < -2.0 else ("BULLISH", "bull-text") if v < -0.5 else ("BEARISH", "bear-text")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Sniper Hub")
    with st.form("storage_v97"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        ec = st.number_input("Curr Bcf", value=st.session_state.data.get("eia_curr", 3375))
        ep = st.number_input("Prev Bcf", value=st.session_state.data.get("eia_prev", 3413))
        e5 = st.number_input("5y Bcf", value=st.session_state.data.get("eia_5y", 3317))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": ec, "eia_prev": ep, "eia_5y": e5})
            save_data(st.session_state.data); st.rerun()
    with st.form("cot_v97"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("🏛️ COT Positioning")
        ml, ms = st.number_input("MM Long", value=st.session_state.data.get("mm_l",0)), st.number_input("MM Short", value=st.session_state.data.get("mm_s",0))
        cl, cs = st.number_input("Comm Long", value=st.session_state.data.get("com_l",0)), st.number_input("Comm Short", value=st.session_state.data.get("com_s",0))
        rl, rs = st.number_input("Ret Long", value=st.session_state.data.get("ret_l",0)), st.number_input("Ret Short", value=st.session_state.data.get("ret_s",0))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs, "ret_l": rl, "ret_s": rs})
            save_data(st.session_state.data); st.rerun()

# --- ANALIZA ---
curr_mx = fetch_hdd_matrix()
ao, nao, pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")

# --- MAIN ---
col_m, col_r = st.columns([4, 1.2])

with col_m:
    st.subheader("🌡️ 14-Day Granular PW-HDD Matrix")
    if curr_mx:
        prev_mx = st.session_state.data.get("last_hdd_matrix", {})
        html = "<table class='matrix-table'><tr><th>Grad (Ponder)</th><th>Total (14d)</th><th>ST Avg</th><th>LT Avg</th>"
        for i in range(14): html += f"<th>D{i+1}</th>"
        html += "</tr>"
        
        gc, gp, std, ted = 0, 0, 0, 0
        for city, info in CITIES.items():
            w = info[2]; cv = curr_mx.get(city, [0]*14); pv = prev_mx.get(city, cv)
            tc, tp = sum(cv), sum(pv); gc += tc * w; gp += tp * w
            st_avg = sum(cv[:7])/7; lt_avg = sum(cv[7:14])/7
            std += (sum(cv[:7])-sum(pv[:7]))*w; ted += (sum(cv[7:])-sum(pv[7:]))*w
            
            # Highlight Logic
            st_style = "term-highlight" if st_avg > lt_avg else ""
            lt_style = "term-highlight" if lt_avg > st_avg else ""
            c_cl = "cell-bull" if tc > tp else "cell-bear" if tc < tp else ""
            
            html += f"<tr><td>{city} ({w})</td><td class='{c_cl}'>{tc:.1f}</td><td>{st_avg:.1f}</td><td>{lt_avg:.1f}</td>"
            for i in range(14):
                d_cl = "cell-bull" if cv[i] > pv[i] else "cell-bear" if cv[i] < pv[i] else ""
                # Primjena highlighta na temelju prosjeka
                h_style = st_style if i < 7 else lt_style
                html += f"<td class='{d_cl} {h_style}'>{cv[i]:.1f}</td>"
            html += "</tr>"
        html += "</table>"; st.markdown(html, unsafe_allow_html=True)
        gtd = gc - gp
        st.markdown(f"<div class='grand-total-box'><h4>GRAND TOTAL PW-HDD | Analysis Run: <strong>{datetime.now().strftime('%H:%M')}</strong></h4><h1 style='margin:10px 0; font-size:3rem; color:#008CFF;'>{gc:.2f} <span class='{'bull-text' if gtd > 0 else 'bear-text'}' style='font-size:1.5rem;'>({gtd:+.2f})</span></h1><div style='display:flex; justify-content:center; gap:30px;'><span>Short-Term Sentiment: <strong class='{'bull-text' if std > 0 else 'bear-text'}'>{'BULL' if std > 0 else 'BEAR'}</strong></span><span>Tail-End Sentiment: <strong class='{'bull-text' if ted > 0 else 'bear-text'}'>{'BULL' if ted > 0 else 'BEAR'}</strong></span></div></div>", unsafe_allow_html=True)

    if st.button("💾 SPREMI MODEL KAO BAZU ZA DELTU"):
        st.session_state.data["last_hdd_matrix"] = curr_mx
        save_data(st.session_state.data); st.rerun()

    st.subheader("📜 Executive Strategic Narrative")
    
    ed = st.session_state.data.get("eia_curr", 0) - st.session_state.data.get("eia_5y", 0)
    st.markdown(f"<div class='summary-narrative'><strong>ANALIZA:</strong> MM Neto: <strong>{st.session_state.data.get('mm_l',0)-st.session_state.data.get('mm_s',0):+,}</strong>. Zalihe: <strong>{ed:+} Bcf</strong> vs 5y. HDD Delta: <strong>{gtd:+.2f}</strong>.<br><strong>DIVERGENCIJA:</strong> {'Usklađeno' if (ed < 0 and gtd > 0) else 'Oprez, divergencija.'}</div>", unsafe_allow_html=True)
    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    st.subheader("📡 Intelligence Radar")
    t1, t2 = st.tabs(["NOAA WEATHER (2x2 Grid)", "SPAGHETTI INDICES"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif", caption="6-10d Temp"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif", caption="6-10d Precip")
        with c2: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif", caption="8-14d Temp"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif", caption="8-14d Precip")
    with t2:
        
        idx_c = st.columns(3); ids = [("AO", ao), ("NAO", nao), ("PNA", pna)]; us = ["https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif"]
        for i, (n, d) in enumerate(ids):
            with idx_c[i]:
                st.image(us[i]); gr, cs = get_grad(d['now'], n)
                st.markdown(f"**{n}: {d['now']:.2f}** | <span class='{cs}'>{gr}</span>", unsafe_allow_html=True)
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")
                lgs = {"AO": "Ispod -2.0: EXTREME BULLISH (Pucanje vrtloga).", "NAO": "Ispod -1.5: EXTREME BULLISH (Blokada Atlantika).", "PNA": "Iznad 1.5: EXTREME BULLISH (Dolina na istoku)."}
                st.markdown(f"<div class='legend-box'>{lgs[n]}</div>", unsafe_allow_html=True)

with col_r:
    st.subheader("📰 Google Intel Feed")
    f = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+OR+natgas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:6]: st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
    st.markdown("---"); st.subheader("🔗 Links")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://www.wxcharts.com/" class="external-link">WX CHARTS</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE</a>', unsafe_allow_html=True)
