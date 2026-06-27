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
st.set_page_config(page_title="智慧看盤系統 V5.6 - XQ 完美中文化版", layout="wide") 

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
# 🛠️ 1. 處理「新增股票與刪除」的側邊欄功能
# ==================================================================== 
st.sidebar.header("🔧 我的自選股管理面版") 

with st.sidebar.expander("➕ 新增自選股", expanded=True): 
    new_code = st.text_input("輸入股票代碼", placeholder="例如: 2882").strip() 
    if st.button("確認加入自選"): 
        if new_code: 
            target_code = new_code.upper()
            pure_number = target_code.split('.')[0]
            if pure_number.isdigit() and not target_code.endswith(".TW") and not target_code.endswith(".TWO"):
                target_code = f"{pure_number}.TW"
            try:
                test_stock = yf.Ticker(target_code)
                test_df = test_stock.history(period="1d")
                if test_df.empty:
                    st.sidebar.error(f"❌ 查無此代碼 [{target_code}]")
                else:
                    detected_name = TAIWAN_STOCK_DICT.get(pure_number, test_stock.info.get('shortName', pure_number))
                    display_key = f"{detected_name} ({target_code})" if "(" not in detected_name else detected_name
                    st.session_state["watchlist_dict"][display_key] = target_code
                    save_my_watchlist()
                    st.sidebar.success(f"成功加入: {detected_name}")
                    st.rerun()
            except:
                st.sidebar.error("❌ 無法連線驗證。")

watchlist_keys = list(st.session_state["watchlist_dict"].keys())
if "current_selected_idx" not in st.session_state or st.session_state["current_selected_idx"] >= len(watchlist_keys):
    st.session_state["current_selected_idx"] = 0

selected_display = watchlist_keys[st.session_state["current_selected_idx"]]
stock_code = st.session_state["watchlist_dict"][selected_display]

if st.sidebar.button("❌ 從清單中刪除目前股票"): 
    if len(st.session_state["watchlist_dict"]) > 1: 
        del st.session_state["watchlist_dict"][selected_display] 
        save_my_watchlist()
        st.session_state["current_selected_idx"] = 0
        st.sidebar.success("已成功移出自選清單！")
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
    color_text = "#FF3333" if price_change >= 0 else "#00AA00"
    sign = "+" if price_change >= 0 else ""
except Exception as e:
    st.error(f"數據載入失敗: {e}")
    st.stop()

# ==================================================================== 
# 📊 XQ 仿真四宮格主排版控制
# ==================================================================== 
# 🌟 2. 解決切換連動問題：統一由主畫面的中央選單當作樞紐控制
st.markdown(f"### 📊 XQ 操盤模擬器 | 當前關注：<span style='color:{color_text};'>{selected_display}</span>", unsafe_allow_html=True)

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown("🧱 **【看盤重點/報價組合】**")
    
    # 這裡的下拉選單將全權引導整張網頁的其餘資訊同步更新
    selected_display = st.selectbox(
        "🔍 點擊下方下拉框，一鍵同步切換全部圖表", 
        watchlist_keys, 
        index=st.session_state["current_selected_idx"],
        key="main_central_select"
    )
    
    if watchlist_keys.index(selected_display) != st.session_state["current_selected_idx"]:
        st.session_state["current_selected_idx"] = watchlist_keys.index(selected_display)
        st.rerun()

        # 建立數據包
    for idx, (name, code) in enumerate(st.session_state["watchlist_dict"].items()):
        try:
            s_df, s_info = fetch_safe_stock_data(code)
            c_p = s_info.get("currentPrice", s_df['Close'].iloc[-1])
            p_c = s_info.get("previousClose", s_df['Close'].iloc[-2])
            chg = c_p - p_c
            pct = (chg / p_c) * 100
        except:
            c_p, chg, pct = 0.0, 0.0, 0.0
            
        # 根據漲跌決定文字顏色
        if chg > 0:
            color = "#FF3333"  # 紅色
            sign = "+"
        elif chg < 0:
            color = "#00AA00"  # 綠色
            sign = ""
        else:
            color = "#333333"  # 灰色
            sign = "+"

        # 🌟 核心創新：利用 Streamlit 的 columns 把每一列做成「按鈕 + 數據」的 XQ 仿實體表格
        b_col1, b_col2, b_col3, b_col4 = st.columns([2, 1.2, 1, 1.2])
        
        with b_col1:
            # 商品名稱做成實體按鈕，點擊立刻改寫全域索引並重整網頁！
            if st.button(f"📌 {name}", key=f"btn_{code}_{idx}", use_container_width=True):
                watchlist_keys = list(st.session_state["watchlist_dict"].keys())
                st.session_state["current_selected_idx"] = watchlist_keys.index(name)
                st.rerun()
                
        with b_col2:
            st.markdown(f"<p style='text-align:center; padding-top:6px; font-family:monospace;'>{c_p:,.2f}</p>", unsafe_allow_html=True)
        with b_col3:
            st.markdown(f"<p style='text-align:center; padding-top:6px; color:{color}; font-weight:bold; font-family:monospace;'>{sign}{chg:,.2f}</p>", unsafe_allow_html=True)
        with b_col4:
            st.markdown(f"<p style='text-align:center; padding-top:6px; color:{color}; font-weight:bold; font-family:monospace;'>{sign}{pct:.2f}%</p>", unsafe_allow_html=True)
        
        st.markdown("<hr style='margin:2px 0px; border-top:1px solid #eee;'>", unsafe_allow_html=True)



with row1_col2:
    st.markdown("📈 **【技術分析】**")
    time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年", key="tech_tf")
    df['MA5'] = df['Close'].rolling(window=5).mean()
    plot_df = df.tail(60) if time_frame == "一年" else df.tail(15)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], 
        name="K線", 
        increasing_line_color='#FF3333', increasing_fillcolor='#FF3333', 
        decreasing_line_color='#00AA00', decreasing_fillcolor='#00AA00'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#1A73E8', width=1.5)), row=1, col=1)
    
    vol_colors = ['#FF3333' if c >= o else '#00AA00' for o, c in zip(plot_df['Open'], plot_df['Close'])]
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=vol_colors), row=2, col=1)
    fig.update_layout(template="plotly_white", xaxis_rangeslider_visible=False, height=210, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
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
            # 確保抓取即時數據
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: 
                intra_df = df.tail(20)
            
            tick_df = intra_df.tail(6).copy().sort_index(ascending=False)
            
            # 建立表格
            html_table = "<table style='width:100%; border-collapse: collapse; font-size:12px; text-align:center;'>"
            html_table += "<tr style='background:#f8f9fa; border-bottom:2px solid #ddd;'><th>時間</th><th>價格</th><th>單量</th><th>總量</th></tr>"
            
            for idx, r in tick_df.iterrows():
                c_color = "red" if r['Close'] >= r['Open'] else "green"
                html_table += f"<tr style='border-bottom:1px solid #eee;'><td>{idx.strftime('%H:%M')}</td><td>{r['Close']:,.2f}</td><td style='color:{c_color}; font-weight:bold;'>{int(r['Volume']):,}</td><td>{int(r['Volume']*2):,}</td></tr>"
            
            html_table += "</table>"
            st.write(html_table, unsafe_allow_html=True)
        except Exception as ticks_err:
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
        except Exception as news_err:
            st.caption("暫無即時新聞")
            
    with tab_ai:
        st.write(f"當前分析：**{selected_display}**")
        if st.button("🚀 啟動 AI 深度策略分析", key="ai_btn_final"):
            with st.spinner("AI 正在解析多空力道..."):
                ai_report = get_ai_analysis(selected_display, current_price, price_change, price_change_pct, df['Close'].iloc[-1], 50, 50)
                st.info(ai_report)