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
from openai import OpenAI

# --- KONFIGURACIJA ---
st.set_page_config(page_title="NatGas Sniper V99 - Neural Sovereign", layout="wide")

# API KEY - Implementiran izravno prema zahtjevu (Savjet: Koristi st.secrets u budućnosti)
AI_KEY = "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"

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h2, h3 { color: #FFFFFF !important; font-weight: 800 !important; border-bottom: 1px solid #333; }
    .ai-analysis-box { font-size: 1.1rem; line-height: 1.7; color: #EEEEEE; border: 2px solid #8A2BE2; padding: 25px; background-color: #0D051A; border-radius: 10px; margin-bottom: 25px; border-left: 10px solid #8A2BE2; }
    .bull-text { color: #00FF00 !important; font-weight: bold; }
    .bear-text { color: #FF4B4B !important; font-weight: bold; }
    .sidebar-box { padding: 15px; border: 1px solid #222; border-radius: 5px; margin-bottom: 15px; background: #0A0A0A; }
    .external-link { display: block; padding: 10px; margin-bottom: 8px; background: #002B50; color: #008CFF !important; text-decoration: none !important; border-radius: 4px; font-weight: bold; text-align: center; border: 1px solid #004080; }
    .grand-total-box { padding: 25px; background: #0F0F0F; border: 2px solid #008CFF; border-radius: 10px; text-align: center; margin-top: 20px; margin-bottom: 20px; }
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-bottom: 20px; color: white; }
    .matrix-table th, .matrix-table td { border: 1px solid #333; padding: 6px; text-align: center; }
    .cell-bull { color: #00FF00 !important; font-weight: bold; }
    .cell-bear { color: #FF4B4B !important; font-weight: bold; }
    .term-highlight { background-color: rgba(0, 255, 0, 0.12) !important; }
    .legend-box { padding: 12px; border: 1px solid #333; background: #111; font-size: 0.8rem; color: #CCC; line-height: 1.4; border-radius: 5px; margin-top: 5px; }
    section[data-testid="stSidebar"] { background-color: #0F0F0F; border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCE ---
DATA_FILE = "sniper_v99_neural.json"
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

# --- SIDEBAR (Persistent Inputs) ---
with st.sidebar:
    st.header("🎯 Sniper Command")
    with st.form("storage_v99"):
        st.markdown("<div class='sidebar-box'>", unsafe_allow_html=True)
        st.subheader("📦 Storage Box")
        ec = st.number_input("Curr Bcf", value=st.session_state.data.get("eia_curr", 3375))
        ep = st.number_input("Prev Bcf", value=st.session_state.data.get("eia_prev", 3413))
        e5 = st.number_input("5y Bcf", value=st.session_state.data.get("eia_5y", 3317))
        st.markdown("</div>", unsafe_allow_html=True)
        if st.form_submit_button("SAVE STORAGE"):
            st.session_state.data.update({"eia_curr": ec, "eia_prev": ep, "eia_5y": e5})
            save_data(st.session_state.data); st.rerun()
            
    with st.form("cot_v99"):
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

# --- MAIN LAYOUT ---
col_m, col_r = st.columns([4, 1.2])

with col_m:
    # 1. HDD MATRIX
    st.subheader("🌡️ 14-Day Granular PW-HDD Matrix")
    if curr_mx:
        prev_mx = st.session_state.data.get("last_hdd_matrix", {})
        html = "<table class='matrix-table'><tr><th>Grad</th><th>Total</th><th>ST Avg</th><th>LT Avg</th>"
        for i in range(14): html += f"<th>D{i+1}</th>"
        html += "</tr>"
        
        gc, gp, std, ted = 0, 0, 0, 0
        for city, info in CITIES.items():
            w = info[2]; cv = curr_mx.get(city, [0]*14); pv = prev_mx.get(city, cv)
            tc, tp = sum(cv), sum(pv); gc += tc * w; gp += tp * w
            st_avg, lt_avg = sum(cv[:7])/7, sum(cv[7:14])/7
            std += (sum(cv[:7])-sum(pv[:7]))*w; ted += (sum(cv[7:])-sum(pv[7:]))*w
            st_s = "term-highlight" if st_avg > lt_avg else ""; lt_s = "term-highlight" if lt_avg > st_avg else ""
            c_cl = "cell-bull" if tc > tp else "cell-bear" if tc < tp else ""
            
            html += f"<tr><td>{city} ({w})</td><td class='{c_cl}'>{tc:.1f}</td><td>{st_avg:.1f}</td><td>{lt_avg:.1f}</td>"
            for i in range(14):
                d_cl = "cell-bull" if cv[i] > pv[i] else "cell-bear" if cv[i] < pv[i] else ""
                h_s = st_s if i < 7 else lt_s
                html += f"<td class='{d_cl} {h_s}'>{cv[i]:.1f}</td>"
            html += "</tr>"
        html += "</table>"; st.markdown(html, unsafe_allow_html=True)
        gtd = gc - gp
        st.markdown(f"<div class='grand-total-box'><h1>{gc:.2f} <span class='{'bull-text' if gtd > 0 else 'bear-text'}'>({gtd:+.2f})</span></h1></div>", unsafe_allow_html=True)

    if st.button("💾 SPREMI MODEL KAO BAZU ZA DELTU"):
        st.session_state.data["last_hdd_matrix"] = curr_mx
        save_data(st.session_state.data); st.rerun()

    # 2. AI STRATEGIC ANALYST
    st.subheader("🤖 AI Strategic Analyst (GPT-4o)")
    if st.button("🚀 POKRENI NEURALNU ANALIZU ASIMETRIJE"):
        client = OpenAI(api_key=AI_KEY)
        prompt = f"""
        Seciraj Natural Gas tržište. Henry Hub focus.
        EIA: Curr {st.session_state.data['eia_curr']}, Prev {st.session_state.data['eia_prev']}, 5y Avg {st.session_state.data['eia_5y']}.
        COT: MM Long {st.session_state.data['mm_l']}, Short {st.session_state.data['mm_s']}. Comm Long {st.session_state.data['com_l']}, Short {st.session_state.data['com_s']}.
        Weather: AO={ao['now']}, NAO={nao['now']}, PNA={pna['now']}.
        HDD: Total {gc:.2f}, Model Delta {gtd:+.2f}.
        ST Sentiment: {'BULL' if std > 0 else 'BEAR'}, LT Sentiment: {'BULL' if ted > 0 else 'BEAR'}.
        
        Zadatak: 
        1. Identificiraj gdje Managed Money 'laže' sam sebe u odnosu na HDD trend.
        2. Ako je Long-Term Avg veći od Short-Term Avg, objasni rizik od 'short squeezea'.
        3. Reci mi izravno: igram li na sitno ili podcjenjujem rizik promjene modela?
        Budi brutalan, racionalan i dubok.
        """
        try:
            with st.spinner("Neuralni Sniper analizira..."):
                resp = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": "Ti si iskusan Savjetnik za NatGas trading. Govoriš istinu, ne laskaš i tražiš asimetriju."},
                              {"role": "user", "content": prompt}]
                )
                st.markdown(f"<div class='ai-analysis-box'>{resp.choices[0].message.content}</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"AI Error: {e}")

    components.html('<div style="height:450px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize": true, "symbol": "CAPITALCOM:NATURALGAS", "interval": "D", "theme": "dark", "container_id": "tv"});</script><div id="tv"></div></div>', height=450)

    st.subheader("📡 Intelligence Radar")
    t1, t2 = st.tabs(["NOAA WEATHER", "SPAGHETTI INDICES"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/610day/610prcp.new.gif")
        with c2: st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814temp.new.gif"); st.image("https://www.cpc.ncep.noaa.gov/products/predictions/814day/814prcp.new.gif")
    with t2:
        idx_c = st.columns(3); ids = [("AO", ao), ("NAO", nao), ("PNA", pna)]
        for i, (n, d) in enumerate(ids):
            with idx_c[i]:
                st.write(f"**{n}: {d['now']:.2f}**")
                st.write(f"D: {d['now']-d['yesterday']:+.2f} | T: {d['now']-d['last_week']:+.2f}")
                lgs = {"AO": "Pucanje vrtloga.", "NAO": "Blokada Atlantika.", "PNA": "Dolina na istoku."}
                st.markdown(f"<div class='legend-box'>{lgs[n]}</div>", unsafe_allow_html=True)

with col_r:
    st.subheader("📰 Google Intel Feed")
    f = feedparser.parse("https://news.google.com/rss/search?q=Natural+gas+when:7d&hl=en-US&gl=US&ceid=US:en")
    for e in f.entries[:6]: st.markdown(f"<div style='font-size:0.85rem; margin-bottom:10px;'><a href='{e.link}' target='_blank' style='color:#008CFF; text-decoration:none;'>{e.title}</a></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("🔗 Links")
    st.markdown('<a href="https://twitter.com/i/lists/1989752726553579941" class="external-link">MY X LIST</a>', unsafe_allow_html=True)
    st.markdown('<a href="http://celsiusenergy.co/" class="external-link">CELSIUS ENERGY</a>', unsafe_allow_html=True)
    st.markdown('<a href="https://ir.eia.gov/secure/ngs/ngs.html" class="external-link">EIA STORAGE</a>', unsafe_allow_html=True)
