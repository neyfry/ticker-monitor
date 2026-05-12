from curl_cffi import requests as _cffi_requests
_orig_request = _cffi_requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault("verify", False)
    return _orig_request(self, method, url, **kwargs)
_cffi_requests.Session.request = _patched_request

import streamlit as st
import yfinance as yf
import numpy as np
import json
import os
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(
    page_title="Monitor de Tickers",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

st.markdown("""
<style>
body, .stApp { background-color: #1a1a2e; }

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background-color: #16213e;
    padding: 8px 10px 0 10px;
    border-radius: 10px 10px 0 0;
}
.stTabs [data-baseweb="tab"] {
    background-color: #2c3e50;
    border-radius: 8px 8px 0 0;
    color: #adb5bd;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 18px;
    border: none;
}
.stTabs [aria-selected="true"] {
    background-color: #3d5a80 !important;
    color: #ffffff !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background-color: #1a1a2e;
    padding-top: 16px;
}

.ticker-card {
    padding: 14px 16px;
    border-radius: 12px;
    margin-bottom: 12px;
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    border-left: 5px solid rgba(255,255,255,0.15);
    min-height: 120px;
}
.card-normal  { background: linear-gradient(135deg, #2c3e50, #34495e); }
.card-orange  { background: linear-gradient(135deg, #d35400, #e67e22); border-left-color: #ffa500; }
.card-green   { background: linear-gradient(135deg, #1a7a40, #27ae60); border-left-color: #2ecc71; }
.card-red     { background: linear-gradient(135deg, #922b21, #e74c3c); border-left-color: #ff6b6b; }
.card-error   { background: linear-gradient(135deg, #2c2c2c, #3d3d3d); opacity: 0.6; }

.t-symbol { font-size: 20px; font-weight: 800; letter-spacing: 1px; margin-bottom: 2px; }
.t-name   { font-size: 11px; opacity: 0.65; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.t-price  { font-size: 19px; font-weight: 700; margin-bottom: 5px; }
.t-range  { font-size: 12px; opacity: 0.82; margin-bottom: 3px; }
.t-rsi    { font-size: 12px; opacity: 0.82; margin-bottom: 5px; }
.t-alert  { font-size: 12px; font-weight: 600; margin-top: 3px; }
.t-error  { font-size: 12px; color: #ff8888; }

.range-bar-wrap { background: rgba(255,255,255,0.2); border-radius: 4px; height: 5px; margin: 5px 0; }
.range-bar-fill { height: 5px; border-radius: 4px; background: rgba(255,255,255,0.75); }

section[data-testid="stSidebar"] { background-color: #16213e; }
</style>
""", unsafe_allow_html=True)

# ── Watchlists por defecto ────────────────────────────────────────────────────

DEFAULT_WATCHLISTS = {
    "💾 STORAGE":        ["SNDK", "STX", "MU", "WDC", "P"],
    "🚀 SPACE":          ["RTX", "ASTS", "PL", "LUNR", "RKLB"],
    "🔬 ASML PROD.":     ["LRCX", "ASML", "AMAT", "KLAC"],
    "🖥 DATA CENTERS":   ["CRWV", "IREN", "APLD", "LWLG", "POET", "TTMI", "AAOI", "NBIS", "MRVL", "LITE", "CIEN", "VRT", "COHR", "TSEM", "CRDO", "GLW"],
    "⚡ SEMICONDUCTORS": ["GOOGL", "MKSI", "NVDA", "ARM", "INTC", "AMKR", "ASX", "EOSE", "COHU", "AXTI", "AMD", "MSFT", "AVGO", "TSM"],
}

WATCHLISTS_FILE = os.path.join(os.path.dirname(__file__), "watchlists.json")


def load_watchlists():
    if os.path.exists(WATCHLISTS_FILE):
        try:
            with open(WATCHLISTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {k: list(v) for k, v in DEFAULT_WATCHLISTS.items()}


def save_watchlists(wl):
    with open(WATCHLISTS_FILE, "w") as f:
        json.dump(wl, f, indent=2)


if "watchlists" not in st.session_state:
    st.session_state.watchlists = load_watchlists()

WATCHLISTS = st.session_state.watchlists
ALL_TICKERS = list(dict.fromkeys(t for tickers in WATCHLISTS.values() for t in tickers))


# ── Helpers ───────────────────────────────────────────────────────────────────

def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=True).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=True).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ticker(symbol: str) -> dict:
    try:
        t = yf.Ticker(symbol)
        info = t.info
        hist = t.history(period="1y")

        price  = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        low52  = info.get("fiftyTwoWeekLow")
        high52 = info.get("fiftyTwoWeekHigh")
        name   = info.get("shortName") or info.get("longName") or symbol

        rsi = None
        if len(hist) > 15:
            rsi = compute_rsi(hist["Close"])

        pct_from_high = None
        range_pct = None
        if price and high52 and high52 > 0:
            pct_from_high = (price - high52) / high52 * 100
        if low52 and high52 and high52 > low52 and price:
            range_pct = max(0.0, min(100.0, (price - low52) / (high52 - low52) * 100))

        # últimos 14 días para la gráfica
        hist14 = hist.tail(14)[["Open", "High", "Low", "Close"]].copy() if len(hist) > 0 else None

        return dict(symbol=symbol.upper(), name=name, price=price,
                    low52=low52, high52=high52, rsi=rsi,
                    pct_from_high=pct_from_high, range_pct=range_pct,
                    hist14=hist14, error=None)
    except Exception as exc:
        return dict(symbol=symbol.upper(), error=str(exc))


def evaluate_color(d: dict, high_thr: float, rsi_thr: float) -> str:
    pulled_back = d.get("pct_from_high") is not None and d["pct_from_high"] <= -high_thr
    oversold    = d.get("rsi") is not None and d["rsi"] < rsi_thr
    if pulled_back and oversold:
        return "red"
    if pulled_back:
        return "orange"
    if oversold:
        return "green"
    return "normal"


def render_card(d: dict, high_thr: float, rsi_thr: float) -> str:
    if d.get("error"):
        return (
            f'<div class="ticker-card card-error">'
            f'<div class="t-symbol">{d["symbol"]}</div>'
            f'<div class="t-error">⚠ No se pudo cargar</div>'
            f'</div>'
        )

    color       = evaluate_color(d, high_thr, rsi_thr)
    pulled_back = d.get("pct_from_high") is not None and d["pct_from_high"] <= -high_thr
    oversold    = d.get("rsi") is not None and d["rsi"] < rsi_thr

    price_s = f"${d['price']:,.2f}" if d["price"] else "—"
    low_s   = f"${d['low52']:,.2f}"  if d["low52"]  else "—"
    high_s  = f"${d['high52']:,.2f}" if d["high52"] else "—"
    rsi_s   = str(d["rsi"]) if d["rsi"] is not None else "—"
    pct_s   = f" · {d['pct_from_high']:.1f}% desde máx." if d["pct_from_high"] is not None else ""

    bar_html = ""
    if d["range_pct"] is not None:
        bar_html = (
            f'<div class="range-bar-wrap">'
            f'<div class="range-bar-fill" style="width:{d["range_pct"]:.1f}%"></div>'
            f'</div>'
        )

    alerts = []
    if pulled_back:
        alerts.append(f"⚠ -{abs(d['pct_from_high']):.1f}% desde máximo 52s")
    if oversold:
        alerts.append("📉 Sobrevendido · RSI < 30")
    alerts_html = "".join(f'<div class="t-alert">{a}</div>' for a in alerts)

    return (
        f'<div class="ticker-card card-{color}">'
        f'<div class="t-symbol">{d["symbol"]}</div>'
        f'<div class="t-name">{d["name"]}</div>'
        f'<div class="t-price">{price_s}</div>'
        f'<div class="t-range">52s: {low_s} — {high_s}</div>'
        f'{bar_html}'
        f'<div class="t-rsi">RSI: {rsi_s}{pct_s}</div>'
        f'{alerts_html}'
        f'</div>'
    )


COLOR_MAP = {
    "normal": "#3d5a80",
    "orange": "#e67e22",
    "green":  "#27ae60",
    "red":    "#e74c3c",
}

def render_chart(d: dict, high_thr: float, rsi_thr: float, tab_key: str = ""):
    hist14 = d.get("hist14")
    if hist14 is None or len(hist14) == 0:
        return

    color = evaluate_color(d, high_thr, rsi_thr)
    line_color = COLOR_MAP[color]

    dates = hist14.index
    opens  = hist14["Open"].tolist()
    highs  = hist14["High"].tolist()
    lows   = hist14["Low"].tolist()
    closes = hist14["Close"].tolist()

    fig = go.Figure()

    # barras de rango diario (High-Low)
    for i, (dt, lo, hi, op, cl) in enumerate(zip(dates, lows, highs, opens, closes)):
        bar_color = "#2ecc71" if cl >= op else "#e74c3c"
        fig.add_trace(go.Scatter(
            x=[dt, dt], y=[lo, hi],
            mode="lines",
            line=dict(color=bar_color, width=4),
            showlegend=False,
            hoverinfo="skip",
        ))

    # línea de cierre con hover
    fig.add_trace(go.Scatter(
        x=dates,
        y=closes,
        mode="lines+markers",
        line=dict(color=line_color, width=2),
        marker=dict(size=5, color=line_color),
        name="Cierre",
        hovertemplate="<b>%{x|%d/%m}</b><br>Cierre: $%{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        height=130,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=True,
            tickformat="%d/%m", tickfont=dict(color="#adb5bd", size=9),
            tickangle=0,
        ),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.07)",
            zeroline=False, tickfont=dict(color="#adb5bd", size=9),
            tickformat="$.0f",
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#16213e", font_color="white", font_size=12),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"chart_{tab_key}_{d['symbol']}")


def render_grid(ticker_list, data_map, high_thr, rsi_thr, tab_key: str = ""):
    cols = st.columns(3, gap="medium")
    for i, sym in enumerate(ticker_list):
        with cols[i % 3]:
            st.markdown(render_card(data_map[sym], high_thr, rsi_thr), unsafe_allow_html=True)
            render_chart(data_map[sym], high_thr, rsi_thr, tab_key=tab_key)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("📋 Configuración")
st.sidebar.markdown("---")

rsi_thr  = st.sidebar.slider("Umbral RSI sobrevendido", 20, 40, 30, step=1)
high_thr = st.sidebar.slider("% caída desde máximo 52s (naranja)", 3, 30, 8, step=1)
st.sidebar.markdown("---")

if st.sidebar.button("🔄 Actualizar datos ahora"):
    st.cache_data.clear()
    st.rerun()

if HAS_AUTOREFRESH:
    refresh_min = st.sidebar.selectbox("Auto-refresh cada:", [1, 2, 5, 10, 15, 30], index=2)
    st_autorefresh(interval=refresh_min * 60 * 1000, key="autorefresh")
    st.sidebar.caption(f"Auto-refresh cada {refresh_min} min")

st.sidebar.markdown("---")

# ── Gestión de tickers ────────────────────────────────────────────────────────

with st.sidebar.expander("➕ Gestionar tickers", expanded=False):
    wl_names = list(WATCHLISTS.keys())
    selected_wl = st.selectbox("Watchlist", wl_names, key="wl_select")

    # Añadir ticker
    new_ticker = st.text_input("Añadir ticker (ej: AAPL)", key="new_ticker_input").strip().upper()
    if st.button("Añadir", key="btn_add"):
        if new_ticker:
            if new_ticker not in WATCHLISTS[selected_wl]:
                WATCHLISTS[selected_wl].append(new_ticker)
                save_watchlists(WATCHLISTS)
                st.cache_data.clear()
                st.success(f"{new_ticker} añadido a {selected_wl}")
                st.rerun()
            else:
                st.warning(f"{new_ticker} ya está en la lista")

    # Quitar tickers
    st.caption("Tickers actuales — marca para eliminar:")
    to_remove = []
    for sym in list(WATCHLISTS[selected_wl]):
        if st.checkbox(sym, key=f"chk_{selected_wl}_{sym}"):
            to_remove.append(sym)

    if to_remove and st.button("🗑 Eliminar seleccionados", key="btn_remove"):
        for sym in to_remove:
            WATCHLISTS[selected_wl].remove(sym)
        save_watchlists(WATCHLISTS)
        st.cache_data.clear()
        st.rerun()

    if st.button("↩ Restaurar por defecto", key="btn_reset"):
        st.session_state.watchlists = {k: list(v) for k, v in DEFAULT_WATCHLISTS.items()}
        save_watchlists(st.session_state.watchlists)
        st.cache_data.clear()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("""
**Leyenda:**
- ⬜ Normal
- 🟠 Naranja — caída ≥ N% desde máximo 52s
- 🟢 Verde — RSI sobrevendido
- 🔴 Rojo — ambas condiciones
""")


# ── Main ──────────────────────────────────────────────────────────────────────

st.title("📊 Monitor de Tickers")
st.caption(f"Fuente: Yahoo Finance · {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

with st.spinner("Cargando datos..."):
    data_map = {sym: fetch_ticker(sym) for sym in ALL_TICKERS}

tab_labels = ["🌐 TODAS"] + list(WATCHLISTS.keys())
tabs = st.tabs(tab_labels)

with tabs[0]:
    flagged = [d for sym, d in data_map.items()
               if not d.get("error") and evaluate_color(d, high_thr, rsi_thr) != "normal"]
    if flagged:
        emoji_map = {"orange": "🟠", "green": "🟢", "red": "🔴"}
        st.markdown("**Alertas activas:** " + " · ".join(
            f"{emoji_map[evaluate_color(d, high_thr, rsi_thr)]} {d['symbol']}" for d in flagged
        ))
        st.markdown("---")
    render_grid(ALL_TICKERS, data_map, high_thr, rsi_thr, tab_key="all")

for i, (wl_name, tickers) in enumerate(WATCHLISTS.items()):
    with tabs[i + 1]:
        render_grid(tickers, data_map, high_thr, rsi_thr, tab_key=str(i))
