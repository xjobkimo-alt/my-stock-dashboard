import datetime
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
import requests

# 1. 網頁全域設定
st.set_page_config(page_title="智慧看盤系統 V5.0", layout="centered")

# --- 🔐 密碼鎖防護機制 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("🔒 私人智慧看盤系統 V5.0")
    st.markdown("本網站已啟動安全防護，請輸入憑證以繼續瀏覽。")
    user_input = st.text_input("帳號 (Username)")
    pass_input = st.text_input("密碼 (Password)", type="password")
    if st.button("確認登入"):
        if user_input == st.secrets["credentials"]["username"] and pass_input == st.secrets["credentials"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun() 
        else:
            st.error("❌ 帳號或密碼錯誤，請重新輸入！")
    st.stop() 
# ------------------------------------

# --- 🌐 證交所三大法人數據爬蟲 ---
@st.cache_data(ttl=3600)  
def fetch_tw_legal_data_v4():
    try:
        url = "https://twse.com.tw"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        data_json = response.json()
        if "data" not in data_json:
            return None, "⚠️ 證交所今日數據尚未公佈或休市。"
        df_inst = pd.DataFrame(data_json['data'], columns=data_json['fields'])
        df_inst = df_inst[['單位名稱', '買進金額', '賣出金額', '買賣差額']]
        for col in ['買進金額', '賣出金額', '買賣差額']:
            df_inst[col] = df_inst[col].str.replace(',', '').astype(float) / 100000000
        return df_inst, "成功"
    except Exception as e:
        return None, f"無法取得籌碼數據: {e}"

# --- 📈 股價數據安全抓取函式 ---
@st.cache_data(ttl=300)
def fetch_safe_stock_data(ticker):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    stock = yf.Ticker(ticker, session=session)
    df = stock.history(period="5y")
    info = stock.info
    return df, info

# --- 🤖 AI 投資解說邏輯 ---
def get_ai_analysis(stock_name, price, change, pct, ma5, ma20, k_val, d_val):
    try:
        client = genai.Client(api_key=st.secrets["api_keys"]["gemini"])
        prompt = f"分析以下股票走勢：{stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，KD指標: K={k_val:.2f}, D={d_val:.2f}，請給予繁體中文短評。"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"AI 暫時繁忙中。錯誤訊息: {e}"

# --- ⚙️ 側邊欄：功能控制與選股清單 ---
st.sidebar.header("📋 我的自訂追蹤清單")

# 初始化 Session State 儲存追蹤名單
if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = ["2330.TW", "2454.TW", "2317.TW", "AAPL", "NVDA"]

# 功能 1：手動新增股票到清單
new_stock = st.sidebar.text_input("➕ 輸入代號新增至清單", placeholder="例如: 2603.TW 或 TSLA").strip()
if st.sidebar.button("加入清單") and new_stock:
    if new_stock not in st.session_state["watchlist"]:
        st.session_state["watchlist"].append(new_stock)
        st.rerun()

# 功能 2：下拉選單一鍵切換標的
stock_code = st.sidebar.selectbox("🔍 點擊一鍵換股看盤", st.session_state["watchlist"])

# 功能 3：手動刪除清單內的股票
if st.sidebar.button("❌ 從清單中刪除目前股票"):
    if len(st.session_state["watchlist"]) > 1:
        st.session_state["watchlist"].remove(stock_code)
        st.rerun()
    else:
        st.sidebar.warning("⚠️ 清單內至少需保留一檔股票！")

st.sidebar.markdown("---")
st.sidebar.header("🛠️ 系統功能設定")
refresh_rate = st.sidebar.slider("🔄 即時報價刷新頻率 (秒)", min_value=5, max_value=60, value=10, step=5)
show_ma = st.sidebar.checkbox("顯示均線 (MA5 / MA20 / MA60)", value=True)
sub_indicator = st.sidebar.selectbox("下方副圖指標", ["無", "KD (9, 3, 3)", "MACD (12, 26, 9)"])

# --- 📊 看盤系統主程式 ---
st.title("📊 Python 智慧看盤網頁 (V5.0 追蹤清單版)")

try:
    # 數據加載 (會跟隨側邊欄選中的 stock_code 自動變更)
    df, info = fetch_safe_stock_data(stock_code)

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
    prev_close = info.get("previousClose", df['Close'].iloc[-2])
    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100
    color_light = "#ff4d4d" if price_change >= 0 else "#00cc66"
    stock_name = info.get('longName', stock_code)

    @st.fragment(run_every=refresh_rate)
    def render_live_charts():
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"🕒 數據最後更新時間: {now} (每 {refresh_rate} 秒自動刷新線圖)")
        
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("即時價", f"{current_price:,.2f}")
        with c2: st.metric("漲跌", f"{price_change:+,.2f}")
        with c3: st.metric("幅度", f"{price_change_pct:+.2f}%")
        st.markdown("---")

        time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年")
        latest_date = df.index[-1]
        
        if time_frame == "五年": plot_df = df
        elif time_frame == "一年": plot_df = df.loc[latest_date - pd.Timedelta(days=365):]
        elif time_frame == "近月": plot_df = df.loc[latest_date - pd.Timedelta(days=30):]
        else: plot_df = yf.Ticker(stock_code).history(period="1d", interval="5m")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

        fig.add_trace(go.Candlestick(
            x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'],
            name="K線", increasing_line_color='#ff4d4d', increasing_fillcolor='#ff4d4d', decreasing_line_color='#00cc66', decreasing_fillcolor='#00cc66'
        ), row=1, col=1)

        if show_ma and time_frame != "當日":
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#ffffff', width=1), name='MA5'), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA20'], mode='lines', line=dict(color='#e6b800', width=1.2), name='MA20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA60'], mode='lines', line=dict(color='#00bcff', width=1.5), name='MA60'), row=1, col=1)

        volume_colors = ['#ff4d4d' if c >= o else '#00cc66' for o, c in zip(plot_df['Open'], plot_df['Close'])]
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=volume_colors, name="成交量", opacity=0.7), row=2, col=1)

        fig.update_layout(
            template="plotly_dark", plot_bgcolor="#1c1c1e", paper_bgcolor="#121212", margin=dict(l=20, r=20, t=30, b=10), xaxis_rangeslider_visible=False, height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white"))
        )
        fig.update_yaxes(side="right", gridcolor="#2c2c2e")
        st.plotly_chart(fig, on_select="ignore")

    render_live_charts()
    st.markdown("---")

    # 3. 📊 籌碼面區塊
    if ".tw" in stock_code.lower():
        st.markdown("### 📊 籌碼面：機構與大戶持股概況")
        institutional_holders = info.get("institutionsPercentHeld", 0) * 100
        insider_holders = info.get("heldPercentInsiders", 0) * 100
        
        if institutional_holders > 0 or insider_holders > 0:
            cc1, cc2 = st.columns(2)
            with cc1: st.metric("外資與法人持股比例", f"{institutional_holders:.2f} %")
            with cc2: st.metric("公司內部大戶持股比例", f"{insider_holders:.2f} %")
            
            bar_fig = go.Figure()
            bar_fig.add_trace(go.Bar(y=['持股'], x=[institutional_holders], orientation='h', marker_color='#ff4d4d', name='法人'))
            bar_fig.add_trace(go.Bar(y=['持股'], x=[insider_holders], orientation='h', marker_color='#00cc66', name='大戶'))
            bar_fig.update_layout(barmode='stack', template="plotly_dark", plot_bgcolor="#121212", paper_bgcolor="#121212", height=60, margin=dict(l=0,r=80,t=0,b=0))
            st.plotly_chart(bar_fig, use_container_width=True)
        else:
            st.info("ℹ️ 該個股當前交易日之大戶籌碼暫無異動。")
        st.markdown("---")

    # 4. 🤖 AI 解說區塊
    st.markdown("### 🤖 AI 智慧投資解說")
    with st.expander("✨ 展開 AI 即時盤勢分析建議", expanded=True):
        if st.button("🚀 啟動 AI 分析當前策略"):
            with st.spinner("AI 正在深度分析中..."):
                ai_report = get_ai_analysis(stock_name, current_price, price_change, price_change_pct, df['MA5'].iloc[-1], df['MA20'].iloc[-1], df['K'].iloc[-1], df['D'].iloc[-1])
                st.write(ai_report)
                
    # 5. 詳細報價
    st.markdown("---")
    st.markdown("### 📋 詳細報價")
    row1_1, row1_2, row1_3 = st.columns(3)
    with row1_1: st.markdown(f"**成交：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{current_price:,.2f}</span>", unsafe_allow_html=True)
    with row1_2: st.markdown(f"**漲跌：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change:+,.2f}</span>", unsafe_allow_html=True)
    with row1_3: st.markdown(f"**幅度：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change_pct:+.2f}%</span>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ 數據載入失敗。請檢查股票代碼是否正確（台股需加 .TW）！錯誤訊息: {e}")
