import datetime 
import yfinance as yf 
import pandas as pd 
import streamlit as st 
import plotly.graph_objects as go 
from plotly.subplots import make_subplots 
import requests 

# 1. 網頁全域設定 
st.set_page_config(page_title="智慧看盤系統 V5.3", layout="wide") 

# --- 🔒 密碼鎖防護機制 --- 
if "password_correct" not in st.session_state: 
    st.session_state["password_correct"] = False 
 
if not st.session_state["password_correct"]: 
    st.title("🔒 私人智慧看盤系統 V5.3") 
    st.markdown("本網站已啟動安全防護，請輸入憑證以繼續瀏覽。") 
    user_input = st.text_input("帳號 (Username)") 
    pass_input = st.text_input("密碼 (Password)", type="password") 
    if st.button("確認登入"): 
        if user_input == st.secrets["credentials"]["username"] and pass_input == st.secrets["credentials"]["password"]: 
            st.session_state["password_correct"] = True 
            st.rerun() 
        else: 
            st.error("❌ 帳號或密碼錯誤，請重新輸入！") 
    st.stop()  # 🛑 強制中斷，沒登入前絕不執行下方任何程式
# ------------------------------------ 

# --- 📊 股價數據安全抓取函式 --- 
@st.cache_data(ttl=300) 
def fetch_safe_stock_data(ticker): 
    session = requests.Session() 
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) 
    stock = yf.Ticker(ticker, session=session) 
    df = stock.history(period="5y") 
    try:
        info = stock.info
    except:
        info = {}
    return df, info 

# --- 🤖 原有 Gemini 投資解說邏輯 --- 
def get_ai_analysis(stock_name, price, change, pct, ma5, ma20, k_val, d_val): 
    try: 
        from google import genai
        client = genai.Client(api_key=st.secrets["api_keys"]["gemini"]) 
        prompt = f"分析以下股票走勢：{stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，KD 指標: K={k_val:.2f}, D={d_val:.2f}，請給予繁體中文短評並提供策略建議。" 
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt) 
        return response.text 
    except Exception as e: 
        return f"Gemini AI 暫時繁忙中。錯誤訊息: {e}" 

# --- 🌐 全新串接開源 AI 模型診斷邏輯 (免金鑰超穩定 Llama-3 來源) --- 
def get_open_source_ai_analysis(stock_name, price, change, pct, ma5, ma20, k_val, d_val):
    try:
        prompt = (
            f"你是一位專業的證券分析師。請針對以下數據進行每日股價診斷。\n"
            f"股票: {stock_name}\n當前價格: {price}\n今日漲跌: {change} ({pct}%)\n"
            f"均線狀況: MA5={ma5:.2f}, MA20={ma20:.2f}\nKD指標: K={k_val:.2f}, D={d_val:.2f}\n"
            f"請提供繁體中文的精準盤勢技術面診斷與操作風險提示。"
        )
        api_url = "https://pollinations.ai"
        payload = {
            "messages": [
                {"role": "system", "content": "你是一個精通台股與美股技術面分析的 AI 智慧投顧助理，一律使用繁體中文回答。"},
                {"role": "user", "content": prompt}
            ],
            "model": "openai-large",
            "jsonMode": False
        }
        response = requests.post(api_url, json=payload, timeout=15)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return f"開源 AI 伺服器繁忙中（狀態碼: {response.status_code}），請稍後再試。"
    except Exception as e:
        return f"開源 AI 診斷連線失敗。錯誤訊息: {e}"

# --- ⚙️ 側邊欄：功能控制與選股清單 --- 
st.sidebar.header("📋 我的自訂追蹤清單") 

if "watchlist_dict" not in st.session_state: 
    st.session_state["watchlist_dict"] = { 
        "台積電 (2330)": "2330.TW", 
        "聯發科 (2454)": "2454.TW", 
        "鴻海 (2317)": "2317.TW", 
        "蘋果 (AAPL)": "AAPL", 
        "輝達 (NVDA)": "NVDA" 
    } 

with st.sidebar.expander("➕ 新增自選股"): 
    new_name = st.text_input("股票自訂名稱", placeholder="例如: 長榮").strip() 
    new_code = st.text_input("股票代碼", placeholder="例如: 2603.TW").strip() 
    if st.button("確認加入"): 
        if new_name and new_code: 
            display_key = f"{new_name} ({new_code.split('.')})" 
            st.session_state["watchlist_dict"][display_key] = new_code 
            st.rerun() 
 
selected_display = st.sidebar.selectbox("🖱️ 點擊一鍵換股看盤", list(st.session_state["watchlist_dict"].keys())) 
stock_code = st.session_state["watchlist_dict"][selected_display] 
 
if st.sidebar.button("❌ 從清單中刪除目前股票"): 
    if len(st.session_state["watchlist_dict"]) > 1: 
        del st.session_state["watchlist_dict"][selected_display] 
        st.rerun() 
    else: 
        st.sidebar.warning("⚠️ 清單內至少需保留一檔股票！") 
 
st.sidebar.markdown("---") 
st.sidebar.header("⚙️ 系統功能設定") 
refresh_rate = st.sidebar.slider("⏱️ 即時報價刷新頻率 (秒)", min_value=5, max_value=60, value=10, step=5) 
show_ma = st.sidebar.checkbox("顯示均線 (MA5 / MA20 / MA60)", value=True) 
sub_indicator = st.sidebar.selectbox("下方副圖指標", ["無", "KD (9, 3, 3)", "MACD (12, 26, 9)"]) 
 
# --- 看盤系統主程式排版控制 --- 
st.title("📈 Python 智慧看盤網頁 (V5.3 開源雙AI版)") 
 
# 【1. 最頂端：自選股行情快報看板】 
st.markdown("### 📊 我的自選股即時行情快報") 
stocks_to_show = list(st.session_state["watchlist_dict"].items()) 
cols = st.columns(len(stocks_to_show)) 
 
for idx, (name, code) in enumerate(stocks_to_show): 
    with cols[idx]: 
        try: 
            s_df, s_info = fetch_safe_stock_data(code) 
            c_p = s_info.get("currentPrice", s_df['Close'].iloc[-1] if not s_df.empty else 0) 
            p_c = s_info.get("previousClose", s_df['Close'].iloc[-2] if len(s_df) > 1 else c_p) 
            chg = c_p - p_c 
            chg_pct = (chg / p_c) * 100 if p_c != 0 else 0 
            st.metric(label=name, value=f"{c_p:,.2f}", delta=f"{chg:+,.2f} ({chg_pct:+.2f}%)") 
        except: 
            st.caption(f"{name} 載入中...") 
 
st.markdown("---") 
 
# 核心數據加載 
df, info = fetch_safe_stock_data(stock_code) 
 
st.markdown(f"## 🎯 當前關注：{selected_display}") 

if not df.empty:
    df['MA5'] = df['Close'].rolling(window=5).mean() 
    df['MA20'] = df['Close'].rolling(window=20).mean() 
    df['MA60'] = df['Close'].rolling(window=60).mean() 
     
    low_9 = df['Low'].rolling(window=9).min() 
    high_9 = df['High'].rolling(window=9).max() 
    rsv = 100 * ((df['Close'] - low_9) / (high_9 - low_9)) 
    rsv = rsv.fillna(50) 
    df['K'] = rsv.ewm(com=2, adjust=False).mean() 
    df['D'] = df['K'].ewm(com=2, adjust=False).mean() 
     
    current_price = info.get("currentPrice", df['Close'].iloc[-1]) 
    prev_close = info.get("previousClose", df['Close'].iloc[-2] if len(df) > 1 else current_price) 
    price_change = current_price - prev_close 
    price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0 
    color_light = "#ff4d4d" if price_change >= 0 else "#00cc66" 
    stock_name = info.get('longName', stock_code) 
     
    # 【2. 中間層：K 線技術線圖區塊】 
    @st.fragment(run_every=refresh_rate) 
    def render_live_charts(): 
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
        st.caption(f"🔄 數據最後更新時間: {now} (每 {refresh_rate} 秒自動刷新線圖)") 
     
        time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年") 
        latest_date = df.index[-1] 
     
        if time_frame == "五年": plot_df = df 
        elif time_frame == "一年": plot_df = df.loc[latest_date - pd.Timedelta(days=365):] 
        elif time_frame == "近月": plot_df = df.loc[latest_date - pd.Timedelta(days=30):] 
        else: plot_df = yf.Ticker(stock_code).history(period="1d", interval="5m") 
     
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3]) 
     
        fig.add_trace(go.Candlestick( 
            x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], 
            name="K 線", increasing_line_color='#ff4d4d', increasing_fillcolor='#ff4d4d', 
            decreasing_line_color='#00cc66', decreasing_fillcolor='#00cc66' 
        ), row=1, col=1) 
     
        if show_ma and time_frame != "當日": 
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#ffffff', width=1), name='MA5'), row=1, col=1) 
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA20'], mode='lines', line=dict(color='#e6b800', width=1.2), name='MA20'), row=1, col=1) 
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA60'], mode='lines', line=dict(color='#00bcff', width=1.5), name='MA60'), row=1, col=1) 
     
        volume_colors = ['#ff4d4d' if c >= o else '#00cc66' for o, c in zip(plot_df['Open'], plot_df['Close'])] 
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=volume_colors, name="成交量", opacity=0.7), row=2, col=1) 
     
        fig.update_layout( 
            template="plotly_dark", plot_bgcolor="#1c1c1e", paper_bgcolor="#121212", margin=dict(l=20, r=20, t=30, b=10), 
            xaxis_rangeslider_visible=False, height=450, 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white")) 
        ) 
        fig.update_yaxes(side="right", gridcolor="#2c2c2e") 
        st.plotly_chart(fig, on_select="ignore") 
     
    render_live_charts() 
     
    st.markdown("---") 
     
    # 【3. 詳細報價】 
    st.markdown("### 📋 詳細報價") 
    row1_1, row1_2, row1_3 = st.columns(3) 
    with row1_1: st.markdown(f"**成交：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{current_price:,.2f}</span>", unsafe_allow_html=True) 
    with row1_2: st.markdown(f"**漲跌：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change:+,.2f}</span>", unsafe_allow_html=True) 
    with row1_3: st.markdown(f"**幅度：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change_pct:+.2f}%</span>", unsafe_allow_html=True) 
    st.markdown("---") 
     
    # 【4. 籌碼面區塊】 
    if ".tw" in stock_code.lower(): 
        st.markdown("### 📊 籌碼面：機構與大戶持股概況") 
        institutional_holders = info.get("institutionsPercentHeld", 0) * 100 if info.get("institutionsPercentHeld") else 0
        insider_holders = info.get("heldPercentInsiders", 0) * 100 if info.get("heldPercentInsiders") else 0
     
        if institutional_holders > 0 or insider_holders > 0: 
            cc1, cc2 = st.columns(2) 
            with cc1: st.metric("外資與法人持股比例", f"{institutional_holders:.2f} %") 
            with cc2: st.metric("公司內部大戶持股比例", f"{insider_holders:.2f} %") 
     
