import datetime 
import yfinance as yf 
import pandas as pd 
import streamlit as st 
import plotly.graph_objects as go 
from plotly.subplots import make_subplots 
from google import genai 
import requests 

# 1. 網頁全域設定
st.set_page_config(page_title="智慧看盤系統 V5.3 - XQ 自動偵測版", layout="wide") 

# --- 密碼鎖防護機制 --- (保留原邏輯)
if "password_correct" not in st.session_state: 
    st.session_state["password_correct"] = False 
 
if not st.session_state["password_correct"]: 
    st.title("私人智慧看盤系統 V5.3") 
    user_input = st.text_input("帳號 (Username)") 
    pass_input = st.text_input("密碼 (Password)", type="password") 
    if st.button("確認登入"): 
        if user_input == st.secrets["credentials"]["username"] and pass_input == st.secrets["credentials"]["password"]: 
            st.session_state["password_correct"] = True 
            st.rerun()
        else:
            st.error("帳號或密碼錯誤！")
            st.stop()
    st.stop()

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
        prompt = f"分析以下股票走勢：{stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，MA5: {ma5}，KD 指標: K={k_val:.2f}, D={d_val:.2f}，請給予繁體中文短評並提供策略建議。" 
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt) 
        return response.text 
    except Exception as e: 
        return f"AI 暫時繁忙中。錯誤訊息: {e}" 

# --- 側邊欄：自選股管理功能 ---
st.sidebar.header("我的自訂追蹤清單") 
if "watchlist_dict" not in st.session_state: 
    st.session_state["watchlist_dict"] = { 
        "加權指數": "^TWII",
        "台積電 (2330)": "2330.TW", 
        "鴻海 (2317)": "2317.TW", 
        "聯發科 (2454)": "2454.TW" 
    } 

# 🌟 修改處：全新升級的自動偵測名稱加入功能
with st.sidebar.expander("➕ 新增自選股"): 
    new_code = st.text_input("輸入股票代碼", placeholder="例如: 2603.TW 或 AAPL").strip() 
    
    if st.button("確認加入自選"): 
        if new_code: 
            # 將輸入轉換為大寫以防萬一
            target_code = new_code.upper()
            
            with st.spinner("正在向交易所辨識股票名稱..."):
                try:
                    # 暫時利用現有安全抓取函式抓取該代碼的 info
                    _, test_info = fetch_safe_stock_data(target_code)
                    
                    # 依序抓取最有可能包含名稱的欄位
                    detected_name = test_info.get('longName') or test_info.get('shortName') or test_info.get('symbol')
                    
                    if not detected_name:
                        detected_name = "未知名稱股"
                    
                    # 美化台股名稱展示：若長名稱太長且包含英文，進行基礎剪裁優化
                    if len(detected_name) > 15 and "Corporation" in detected_name:
                        detected_name = detected_name.replace("Corporation", "").strip()
                    
                    # 組合出最終的 XQ 格式： "股票名稱 (代碼)"
                    display_key = f"{detected_name} ({target_code})"
                    
                    # 寫入 Session 暫存清單並刷新
                    st.session_state["watchlist_dict"][display_key] = target_code
                    st.sidebar.success(f"成功識別並加入：{detected_name}")
                    st.rerun()
                    
                except Exception as e:
                    st.sidebar.error(f"代碼無效或查無此股票，請確認後再試。")
        else:
            st.sidebar.warning("請先輸入代碼！")

# 選擇與刪除股票
selected_display = st.sidebar.selectbox("點擊切換當前關注股票", list(st.session_state["watchlist_dict"].keys())) 
stock_code = st.session_state["watchlist_dict"][selected_display] 

if st.sidebar.button("❌ 從清單中刪除目前股票"): 
    if len(st.session_state["watchlist_dict"]) > 1: 
        del st.session_state["watchlist_dict"][selected_display] 
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
# XQ 仿真四宮格主排版控制
# ==================================================================== 
st.markdown(f"### 📊 XQ 操盤模擬器 | 當前關注：{selected_display}")

# 定義第一橫列 (Row 1): 報價組合 + 技術分析
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown("🧱 **【看盤重點/報價組合】**")
    quote_data = []
    for name, code in st.session_state["watchlist_dict"].items():
        try:
            s_df, s_info = fetch_safe_stock_data(code)
            c_p = s_info.get("currentPrice", s_df['Close'].iloc[-1])
            p_c = s_info.get("previousClose", s_df['Close'].iloc[-2])
            chg = c_p - p_c
            pct = (chg / p_c) * 100
            quote_data.append({
                "商品名稱": name, 
                "成交價": f"{c_p:,.2f}", 
                "漲跌": f"{chg:+,.2f}", "漲幅(%)": f"{pct:+.2f}%"
            })
        except:
            quote_data.append({"商品名稱": name, "成交價": "載入中...", "漲跌": "-", "漲幅(%)": "-"})
    
    st.dataframe(pd.DataFrame(quote_data), use_container_width=True, hide_index=True, height=280)


with row1_col2:
    st.markdown("📈 **【技術分析】**")
    time_frame = st.segmented_control(
        "時間區間", ["當日", "近月", "一年", "五年"], default="一年", key="tech_time_frame"
    )
    
    df['MA5'] = df['Close'].rolling(window=5).mean()
    low_9 = df['Low'].rolling(window=9).min()
    high_9 = df['High'].rolling(window=9).max()
    rsv = 100 * ((df['Close'] - low_9) / (high_9 - low_9)).fillna(50)
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    latest_date = df.index[-1]
    
    if time_frame == "五年":
        plot_df = df
    elif time_frame == "近月":
        plot_df = df.loc[latest_date - pd.Timedelta(days=30):]
    elif time_frame == "當日":
        plot_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
        if plot_df.empty: plot_df = df.tail(15)
    else: 
        plot_df = df.loc[latest_date - pd.Timedelta(days=365):]
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    
    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'],
        name="K線", increasing_line_color='red', increasing_fillcolor='red',
        decreasing_line_color='green', decreasing_fillcolor='green'
    ), row=1, col=1)
    
    if 'MA5' in plot_df.columns and time_frame != "當日":
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='blue', width=1), name='MA5'), row=1, col=1)
    
    vol_colors = ['red' if c >= o else 'green' for o, c in zip(plot_df['Open'], plot_df['Close'])]
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=vol_colors, name="成交量"), row=2, col=1)
    
    fig.update_layout(
        template="plotly_white", xaxis_rangeslider_visible=False, height=230,
        margin=dict(l=10, r=40, t=5, b=5), showlegend=False
    )
    fig.update_yaxes(side="right", gridcolor="#e5e5e5")
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


# ==================================================================== 
# 定義第二橫列 (Row 2): 走勢明細 + 資訊分頁 (新聞與AI)
# ==================================================================== 
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
            
            fig_line.update_layout(template="plotly_white", height=220, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
            fig_line.update_yaxes(side="right", gridcolor="#e5e5e5")
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})
        except Exception as e:
            st.info("當日走勢圖加載中...")

    with tab_ticks:
        try:
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: intra_df = df.tail(30)
            tick_df = intra_df.tail(8).copy().sort_index(ascending=False)
            
            html_table = """
            <table style='width:100%; border-collapse: collapse; font-size:13px; text-align:center; font-family:monospace;'>
                <tr style='background-color: #f8f9fa; border-bottom: 2px solid #dee2e6; color: #333;'>
                    <th style='padding:6px;'>成交時間</th>
                    <th style='padding:6px;'>價格/指數</th>
                    <th style='padding:6px;'>單量 (手/張)</th>
                    <th style='padding:6px;'>累計總量</th>
                </tr>
            """
            for index, row in tick_df.iterrows():
                time_str = index.strftime('%H:%M:%S')
                price_val = f"{row['Close']:,.2f}"
                vol_val = int(row['Volume'])
                cell_color = "red" if row['Close'] >= row['Open'] else "green"
                html_table += f"""
                <tr style='border-bottom: 1px solid #eee;'>
                    <td style='padding:5px; color:#555;'>{time_str}</td>
                    <td style='padding:5px; font-weight:bold;'>{price_val}</td>
                    <td style='padding:5px; color:{cell_color}; font-weight:bold;'>{vol_val:,}</td>
                    <td style='padding:5px; color:#333;'>{vol_val*3:,}</td>
                </tr>
                """
            html_table += "</table>"
            st.write(html_table, unsafe_allow_html=True)
        except Exception as e:
            st.info("即時成交明細加載中...")

with row2_col2:
    tab_news, tab_ai = st.tabs(["📰 相關即時新聞", "🤖 AI 智慧投資解說"])
    
    with tab_news:
        try:
            news_list = info.get('news', [])[:4] 
            if news_list:
                for item in news_list:
                    title = item.get('title', '無標題')
                    publisher = item.get('publisher', '財經媒體')
                    link = item.get('link', '#')
                    st.markdown(f"📌 [{title}]({link})  \n<small style='color:gray;'>來源: {publisher}</small>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin:4px 0px; border-top:1px dashed #eee;'>", unsafe_allow_html=True)
            else:
                mock_news = [f"兩岸三地指數最新報價", f"外資在集中市場動態關注 {selected_display}"]
                for n in mock_news: 
                    st.caption(f"⏱️ {datetime.date.today().strftime('%m/%d')} | {n}")
        except Exception as news_err:
            st.caption("暫無即時新聞資訊")
            
    with tab_ai:
        st.write(f"目前分析標的：**{selected_display}**")
        if st.button("🚀 啟動 AI 分析當前策略", key="tab_ai_btn"):
            with st.spinner("AI 正在深度分析中..."):
                stock_name = info.get('longName', stock_code)
                ai_report = get_ai_analysis(
                    stock_name, current_price, price_change, price_change_pct, 
                    df['MA5'].iloc[-1], df['K'].iloc[-1], df['D'].iloc[-1]
                )
                st.info(ai_report)