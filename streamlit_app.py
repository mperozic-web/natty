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
from groq import Groq
import urllib.parse

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V113", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .ai-analysis-box { font-size: 1.15rem; line-height: 1.8; color: #EEEEEE; border: 2px solid #FF8C00; padding: 25px; background-color: #1A0F05; border-radius: 10px; margin-bottom: 25px; border-left: 10px solid #FF8C00; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .external-link { display: block; padding: 10px; margin-bottom: 8px; background: #002B50; color: #008CFF !important; text-decoration: none !important; border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080; }
    .grand-total-box { padding: 15px; background: #0F0F0F; border: 1px solid #333; border-radius: 10px; text-align: center; margin-top: 10px; margin-bottom: 20px; width: fit-content; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-bottom: 20px; color: white; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 5px; text-align: center; }
    .cell-bull { color: #00FF00 !important; font-weight: bold; }
    .cell-bear { color: #FF4B4B !important; font-weight: bold; }
    .term-highlight { background-color: rgba(255, 140, 0, 0.12) !important; }
    .legend-box { padding: 10px; border: 1px solid #222; background: #111; font-size: 0.75rem; color: #AAA; border-radius: 5px; margin-bottom: 15px; }
    .data-source-link { font-size: 0.75rem; color: #008CFF; text-decoration: none; font-weight: bold; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ENGINE (V113 Ironclad) ---
DATA_FILE = "sniper_v113_data.json"

def load_data():
    defaults = {
        "eia_curr": 3375, "eia_net": -50, "eia_5y": 3317,
        "mm_l": 0, "mm_s": 0, "com_l": 0, "com_s": 0, "ret_l": 0, "ret_s": 0,
        "last_hdd_matrix": {}, "news_q": "Natural gas",
        "history": {} 
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                loaded = json.load(f)
                # FORCE INITIALIZATION
                if not isinstance(loaded, dict): loaded = defaults
                if "history" not in loaded: loaded["history"] = {}
                return {**defaults, **loaded}
        except: return defaults
    return defaults

def save_data(data):
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

# Re-init if session state is broken
if 'data' not in st.session_state or "history" not in st.session_state.data:
    st.session_state.data = load_data()

# --- ENGINES ---
CITIES = {"Chicago": [41.87, -87.62, 0.25], "NYC": [40.71, -74.00, 0.20], "Detroit": [42.33, -83.04, 0.15], "Philly": [39.95, -75.16, 0.10], "Boston": [42.36, -71.05, 0.10]}

def get_run_type():
    h = datetime.now(pytz.utc).hour
    return "00z" if 6 <= h < 18 else "12z"

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

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚡ Neural Sniper Hub")
    groq_key = st.text_input("Groq API Key", type="password")
    
    with st.form("stor_v113"):
        st.subheader("📦 Storage Box")
        e_curr = st.number_input("Current Storage (Bcf)", value=st.session_state.data.get("eia_curr", 3375))
        e_net = st.number_input("Net Change (Bcf)", value=st.session_state.data.get("eia_net", -50))
        e_5y = st.number_input("5y Avg (Bcf)", value=st.session_state.data.get("eia_5y", 3317))
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": e_curr, "eia_net": e_net, "eia_5y": e_5y})
            save_data(st.session_state.data); st.rerun()

    with st.form("cot_v113"):
        st.subheader("🏛️ COT Positioning")
        c1, c2 = st.columns(2)
        ml = c1.number_input("MM Long", value=st.session_state.data.get("mm_l", 0))
        ms = c2.number_input("MM Short", value=st.session_state.data.get("mm_s", 0))
        cl = c1.number_input("Comm Long", value=st.session_state.data.get("com_l", 0))
        cs = c2.number_input("Comm Short", value=st.session_state.data.get("com_s", 0))
        rl = c1.number_input("Retail Long", value=st.session_state.data.get("ret_l", 0))
        rs = c2.number_input("Retail Short", value=st.session_state.data.get("ret_s", 0))
        if st.form_submit_button("SAVE COT"):
            st.session_state.data.update({"mm_l": ml, "mm_s": ms, "com_l": cl, "com_s": cs, "ret_l": rl, "ret_s": rs})
            save_data(st.session_state.data); st.rerun()

# --- ANALIZA ---
curr_mx = fetch_hdd_matrix()
ao, nao, pna = get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.ao.cdas.z1000.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.nao.cdas.z500.19500101_current.csv"), get_noaa_idx("https://ftp.cpc.ncep.noaa.gov/cwlinks/norm.daily.pna.cdas.z500.19500101_current.csv")
run_tag = get_run_type()

# --- MAIN LAYOUT ---
col_m, col_r = st.columns([4, 1.2])

with col_m:
    # 1. LIVE CHART
    st.subheader("📊 Live Natural Gas Market")
    components.html('<div style="height:400px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=400)

    # 2. HDD MATRIX
    st.subheader(f"🌡️ 14-Day Granular PW-HDD Matrix ({run_tag})")
    
    st.markdown(f"<div style='margin-bottom:10px;'><a href='https://open-meteo.com/' class='data-source-link'>Source: Open-Meteo Weather API (Global Models)</a></div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class='legend-box'>
        <strong>LEGEND:</strong> ST Avg (D1-7) | LT Avg (D8-14). 
        <span style='color:#00FF00;'>Green</span> = Models colder vs last save. 
        <span style='color:#FF4B4B;'>Red</span> = Models warmer. 
        <span style='background-color:rgba(255,140,0,0.12);'>Orange Shade</span> = Dominant term momentum.
    </div>
    """, unsafe_allow_html=True)

    if curr_mx:
        prev_mx = st.session_state.data.get("last_hdd_matrix", {})
        dates = [(datetime.now() + timedelta(days=i)).strftime("%b %d") for i in range(14)]
        html = "<table class='matrix-table'><tr><th>Grad</th><th>Total</th><th>ST Avg</th><th>LT Avg</th>"
        for d in dates: html += f"<th>{d}</th>"
        html += "</tr>"
        
        gc, gp, std, ted = 0, 0, 0, 0
        for city, info in CITIES.items():
            w = info[2]; cv = curr_mx.get(city, [0]*14); pv = prev_mx.get(city, cv)
            tc, tp = sum(cv), sum(pv); gc += tc * w; gp += tp * w
            st_a, lt_a = sum(cv[:7])/7, sum(cv[7:14])/7
            std += (sum(cv[:7])-sum(pv[:7]))*w; ted += (sum(cv[7:])-sum(pv[7:]))*w
            st_s = "term-highlight" if st_a > lt_a else ""; lt_s = "term-highlight" if lt_a > st_a else ""
            c_cl = "cell-bull" if tc > tp else "cell-bear" if tc < tp else ""
            html += f"<tr><td>{city} ({w})</td><td class='{c_cl}'>{tc:.1f}</td><td>{st_a:.1f}</td><td>{lt_a:.1f}</td>"
            for i in range(14):
                d_cl = "cell-bull" if cv[i] > pv[i] else "cell-bear" if cv[i] < pv[i] else ""
                html += f"<td class='{d_cl} {st_s if i < 7 else lt_s}'>{cv[i]:.1f}</td>"
            html += "</tr>"
        html += "</table>"; st.markdown(html, unsafe_allow_html=True)
        
        # PERSISTENCE AUTOMATION (WITH KEY CHECK)
        if "history" not in st.session_state.data: st.session_state.data["history"] = {}
        hist_key = f"{datetime.now().strftime('%Y-%m-%d')}_{run_tag}"
        st.session_state.data["history"][hist_key] = gc
        
        y_key = f"{(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}_{run_tag}"
        w_key = f"{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}_{run_tag}"
        
        h_y = st.session_state.data["history"].get(y_key, gc)
        h_w = st.session_state.data["history"].get(w_key, gc)
        
        dod, wow = gc - h_y, gc - h_w
        
        st.markdown(f"""
        <div class='grand-total-box'>
            <span style='font-size:0.8rem; color:#888;'>PW-HDD TOTAL ({run_tag})</span><br>
            <span style='font-size:1.6rem; font-weight:bold;'>{gc:.2f}</span><br>
            <span style='font-size:0.85rem;'>
                DoD: <span class='{"bull-text" if dod > 0 else "bear-text"}'>{dod:+.2f}</span> | 
                WoW: <span class='{"bull-text" if wow > 0 else "bear-text"}'>{wow:+.2f}</span>
            </span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("💾 SAVE MODEL AS REFERENCE"):
        st.session_state.data["last_hdd_matrix"] = curr_mx
        save_data(st.session_state.data); st.rerun()

    # 3. RADAR TABS
    st.subheader("📡 Intelligence Radar")
    t1, t2, t_ai = st.tabs(["NOAA WEATHER", "SPAGHETTI INDICES", "🤖 NEURAL ANALYST"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif")
        with c2: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif")
    with t2:
        
        idx_c = st.columns(3); ids = [
            ("AO", ao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/ao.sprd2.gif", "AO: < -2.0 (Ext Bull), -0.5 (Bull), > 0.5 (Bear)"),
            ("NAO", nao, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/nao.sprd2.gif", "NAO: < -1.5 (Ext Bull), -0.5 (Bull), > 0.5 (Bear)"),
            ("PNA", pna, "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/pna.sprd2.gif", "PNA: > 1.5 (Ext Bull), 0.5 (Bull), < -0.5 (Bear)")
        ]
        for i, (n, d, u, l) in enumerate(ids):
            with idx_c[i]:
                st.image(u); st.write(f"**{n}: {d['now']:.2f}**")
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")
                st.markdown(f"<div class='legend-box'>{l}</div>", unsafe_allow_html=True)
    with t_ai:
        if st.button("🚀 RUN NEURAL ANALYSIS"):
            if not groq_key: st.error("Enter Groq Key!")
            else:
                client = Groq(api_key=groq_key)
                p = f"Analyze NatGas: Storage {st.session_state.data['eia_curr']}, COT MM Net {st.session_state.data['mm_l']-st.session_state.data['mm_s']}. HDD {gc:.2f}, DoD {dod:+.2f}, WoW {wow:+.2f}. Be strategic."
                res = client.chat.completions.create(messages=[{"role": "user", "content": p}], model="llama-3.3-70b-versatile")
                st.markdown(f"<div class='ai-analysis-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)

with col_r:
    st.subheader("📰 Intelligence Feed")
    q_in = st.text_input("Keywords:", value=st.session_state.data.get("news_q", "Natural gas"))
    if st.button("REFRESH NEWS"):
        st.session_state.data["news_q"] = q_in; save_data(st.session_state.data); st.rerun()
    encoded = urllib.parse.quote(q_in)
    f = feedparser.parse(f"https://news.google.com/rss/search?q={encoded}+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:8]: st.markdown(f"<div style='font-size:0.8rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("🔗 Essential Hub")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://discord.com/channels/1394877262783971409/1394933693537325177" class="external-link">MY DISCORD</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE REPORT</a>', unsafe_allow_html=True)

st.markdown(f"<div style='font-size:0.7rem; color:#444; text-align:center; margin-top:30px;'>Sniper System V113 | Model Run: {run_tag} | Automated DoD/WoW Active.</div>", unsafe_allow_html=True)
