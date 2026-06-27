import datetime 
import yfinance as yf 
import pandas as pd 
import streamlit as st 
import plotly.graph_objects as go 
from plotly.subplots import make_subplots 
from google import genai 
import requests 
import json
import os

# 1. 網頁全域設定
st.set_page_config(page_title="智慧看盤系統 V5.5 - XQ 點擊連動版", layout="wide") 

# --- 💡 永久儲存自選股功能 ---
SAVE_FILE = "watchlist.json"
if "watchlist_dict" not in st.session_state:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state["watchlist_dict"] = json.load(f)
    else:
        st.session_state["watchlist_dict"] = { 
            "加權指數": "^TWII", "台積電 (2330)": "2330.TW", 
            "鴻海 (2317)": "2317.TW", "聯發科 (2454)": "2454.TW" 
        }

def save_my_watchlist():
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state["watchlist_dict"], f, ensure_ascii=False, indent=4)

# 內建台灣常見股票中文名稱快查字典
TAIWAN_STOCK_DICT = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2882": "國泰金",
    "2881": "富邦金", "2303": "聯電", "2603": "長榮", "2609": "陽明",
    "2615": "萬海", "2002": "中鋼", "2412": "中華電", "2308": "台達電",
    "2891": "中信金", "2886": "兆豐金", "2884": "玉山金", "2892": "第一金",
    "5880": "合庫金", "2880": "華南金", "2883": "開發金", "2885": "元大金",
    "2887": "台新金", "2890": "永豐金", "3008": "大立光", "2382": "廣達",
    "2357": "華碩", "3231": "緯創", "2324": "仁寶", "2356": "英業達"
}

# --- 數據安全抓取函式 ---
@st.cache_data(ttl=60)
def fetch_safe_stock_data(ticker): 
    session = requests.Session() 
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) 
    stock = yf.Ticker(ticker, session=session) 
    df = stock.history(period="5y") 
    info = stock.info 
    return df, info 

# --- AI 投資解說邏輯 ---
def get_ai_analysis(stock_name, price, change, pct, ma5, k_val, d_val): 
    try: 
        client = genai.Client(api_key=st.secrets["api_keys"]["gemini"]) 
        prompt = f"分析以下股票走勢：{stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，MA5: {ma5}，請給予繁體中文短評並提供策略建議。" 
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt) 
        return response.text 
    except Exception as e: 
        return f"AI 暫時繁忙中。錯誤訊息: {e}" 

# ==================================================================== 
# 🛠️ 側邊欄自選股管理 (已清理多餘選單)
# ==================================================================== 
# 取得目前全域選定的股票名稱與代碼
watchlist_keys = list(st.session_state["watchlist_dict"].keys())
if "current_selected_idx" not in st.session_state or st.session_state["current_selected_idx"] >= len(watchlist_keys):
    st.session_state["current_selected_idx"] = 0

selected_display = watchlist_keys[st.session_state["current_selected_idx"]]
stock_code = st.session_state["watchlist_dict"][selected_display]

# 側邊欄僅保留刪除按鈕與刷新頻率，功能更專一
if st.sidebar.button("❌ 從清單中刪除目前股票"): 
    if len(st.session_state["watchlist_dict"]) > 1: 
        del st.session_state["watchlist_dict"][selected_display] 
        save_my_watchlist()
        st.session_state["current_selected_idx"] = 0
        st.rerun() 
    else: 
        st.sidebar.warning("清單內至少需保留一檔股票！") 

refresh_rate = st.sidebar.slider("即時報價刷新頻率 (秒)", min_value=5, max_value=60, value=10, step=5) 

# 加載核心數據
try:
    df, info = fetch_safe_stock_data(stock_code) 
    current_price = info.get("currentPrice", df['Close'].iloc[-1]) 
    prev_close = info.get("previousClose", df['Close'].iloc[-2]) 
    price_change = current_price - prev_close 
    price_change_pct = (price_change / prev_close) * 100 
    color_text = "red" if price_change >= 0 else "green"
    sign = "+" if price_change >= 0 else ""
except Exception as e:
    st.error(f"數據載入失敗: {e}")
    st.stop()

# ==================================================================== 
# 📊 XQ 仿真四宮格主排版控制
# ==================================================================== 
st.markdown(f"### 📊 XQ 操盤模擬器 | 當前關注：{selected_display}")

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown("🧱 **【看盤重點/報價組合】**")
    
    # 主畫面核心切換樞紐
    selected_display = st.selectbox(
        "🔍 快速點擊切換關注商品", 
        watchlist_keys, 
        index=st.session_state["current_selected_idx"],
        key="main_grid_select"
    )
    
    if watchlist_keys.index(selected_display) != st.session_state["current_selected_idx"]:
        st.session_state["current_selected_idx"] = watchlist_keys.index(selected_display)
        st.rerun()
        
    stock_code = st.session_state["watchlist_dict"][selected_display]

    quote_data = []
    for name, code in st.session_state["watchlist_dict"].items():
        try:
            s_df, s_info = fetch_safe_stock_data(code)
            c_p = s_info.get("currentPrice", s_df['Close'].iloc[-1])
            p_c = s_info.get("previousClose", s_df['Close'].iloc[-2])
            chg = c_p - p_c
            pct = (chg / p_c) * 100
            quote_data.append({"商品名稱": name, "成交價": f"{c_p:,.2f}", "漲跌": f"{chg:+,.2f}", "漲幅(%)": f"{pct:+.2f}%"})
        except:
            quote_data.append({"商品名稱": name, "成交價": "載入中...", "漲跌": "-", "漲幅(%)": "-"})
            
    quote_df = pd.DataFrame(quote_data)
    st.dataframe(quote_df, use_container_width=True, hide_index=True, height=180)

with row1_col2:
    st.markdown("📈 **【技術分析】**")
    time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年", key="tech_tf")
    
    # 計算五日均線
    df['MA5'] = df['Close'].rolling(window=5).mean()
    plot_df = df.tail(60) if time_frame == "一年" else df.tail(15)
    
    # 建立主附圖 (K線 + 成交量)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    
    # 🌟 升級處：精準客製台股「紅漲綠跌」實心 K 線配色
    fig.add_trace(go.Candlestick(
        x=plot_df.index, 
        open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], 
        name="K線", 
        increasing_line_color='#FF3333',   # 漲：亮紅色線條
        increasing_fillcolor='#FF3333',   # 漲：紅色實心填滿
        decreasing_line_color='#00AA00',   # 跌：亮綠色線條
        decreasing_fillcolor='#00AA00'    # 跌：綠色實心填滿
    ), row=1, col=1)
    
    # 加入均線折線
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#1A73E8', width=1.5), name='MA5'), row=1, col=1)
    
    # 🌟 升級處：讓成交量柱狀圖也同步呈現「紅漲綠跌」配色
    vol_colors = ['#FF3333' if c >= o else '#00AA00' for o, c in zip(plot_df['Open'], plot_df['Close'])]
    fig.add_trace(go.Bar(
        x=plot_df.index, 
        y=plot_df['Volume'], 
        marker_color=vol_colors, 
        name="成交量"
    ), row=2, col=1)
    
    # 圖表外觀優化 (白底與單邊右側座標軸)
    fig.update_layout(
        template="plotly_white", 
        xaxis_rangeslider_visible=False, 
        height=210, 
        margin=dict(l=10, r=40, t=5, b=5), 
        showlegend=False
    )
    fig.update_yaxes(side="right", gridcolor="#e5e5e5")
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 定義第二橫列 (Row 2)
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.markdown(f"🕒 **【市場焦點動態】** <span style='color:{color_text}; font-weight:bold;'>{current_price:,.2f} ({sign}{price_change_pct:.2f}%)</span>", unsafe_allow_html=True)
    tab_trend, tab_ticks = st.tabs(["📉 當日分時走勢", "📋 即時成交明細"])
    
    with tab_trend:
        try:
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: intra_df = df.tail(30)
            fig_line = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
            fig_line.add_trace(go.Scatter(x=intra_df.index, y=intra_df['Close'], mode='lines', line=dict(color='blue', width=1.5)), row=1, col=1)
            fig_line.add_trace(go.Bar(x=intra_df.index, y=intra_df['Volume'], marker_color='lightblue'), row=2, col=1)
            fig_line.update_layout(template="plotly_white", height=200, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})
        except:
            st.info("走勢圖載入中...")

    with tab_ticks:
        try:
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: intra_df = df.tail(20)
            tick_df = intra_df.tail(6).copy().sort_index(ascending=False)
            
            html_table = "<table style='width:100%; border-collapse: collapse; font-size:12px; text-align:center;'>"
            html_table += "<tr style='background:#f8f9fa; border-bottom:2px solid #ddd;'><th>時間</th><th>價格</th><th>單量</th><th>總量</th></tr>"
            for idx, r in tick_df.iterrows():
                c_color = "red" if r['Close'] >= r['Open'] else "green"
                html_table += f"<tr style='border-bottom:1px solid #eee;'><td>{idx.strftime('%H:%M')}</td><td>{r['Close']:,.2f}</td><td style='color:{c_color}; font-weight:bold;'>{int(r['Volume']):,}</td><td>{int(r['Volume']*2):,}</td></tr>"
            html_table += "</table>"
            st.write(html_table, unsafe_allow_html=True)
        except:
            st.info("成交明細載入中...")

with row2_col2:
    tab_news, tab_ai = st.tabs(["📰 相關即時新聞", "🤖 AI 智慧投資解說"])
    
    with tab_news:
        try:
            news_list = info.get('news', [])
            if news_list and len(news_list) > 0:
                for item in news_list[:3]:
                    st.markdown(f"📌 [{item.get('title', '新聞')}]({item.get('link', '#')})")
            else:
                st.caption("⏱️ 非交易日，為您聯播大盤近期財經焦點：")
                market_news = yf.Ticker("^TWII").info.get('news', [])[:3]
                for m_item in market_news:
                    st.markdown(f"📰 [{m_item.get('title')}]({m_item.get('link')})")
        except Exception as e:
            st.caption("暫無即時新聞")
            
    with tab_ai:
        st.write(f"當前分析：**{selected_display}**")
        if st.button("🚀 啟動 AI 深度策略分析", key="ai_btn_final"):
            with st.spinner("AI 正在解析多空力道..."):
                ai_report = get_ai_analysis(selected_display, current_price, price_change, price_change_pct, df['Close'].iloc[-1], 50, 50)
                st.info(ai_report)
