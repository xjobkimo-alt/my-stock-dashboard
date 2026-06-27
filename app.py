import datetime
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
import requests

# 1. 網頁全域設定
st.set_page_config(page_title="智慧看盤系統 V3.7", layout="centered")

# --- 🔐 密碼鎖防護機制 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    st.title("🔒 私人智慧看盤系統 V3.7")
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

# --- 🌐 證交所三大法人數據爬蟲 (⚠️ 全新更名破除暫存版) ---
@st.cache_data(ttl=3600)  # 這裡的快取會因為下面名稱改變而重新建立
def fetch_tw_legal_data_v2():
    """強制更換函式名稱，100% 逼迫 Streamlit 丟掉死卡住的舊網址"""
    try:
        today = datetime.datetime.now()
        weekday = today.weekday() # 0是週一, 5是週六, 6是週日
        
        # 如果是週末，自動退回到上週五
        if weekday == 5:
            target_date = today - datetime.timedelta(days=1)
        elif weekday == 6:
            target_date = today - datetime.timedelta(days=2)
        else:
            target_date = today
            
        today_str = target_date.strftime("%Y%m%d")
        
        # 🛡️ 正確的證交所官方 RWD 接口路徑
        url = f"https://twse.com.tw{today_str}&response=json"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(url, headers=headers, timeout=10)
        data_json = response.json()
        
        if "data" not in data_json:
            return None, f"⚠️ 證交所今日 ({target_date.strftime('%Y-%m-%d')}) 籌碼數據尚未公佈或休市。"
            
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
        prompt = f"""
        你是一位專業的技術分析師。請針對以下股票當前的數據，提供一段大約 150 字內的繁體中文短評，分析其短線走勢並給出投資策略。
        股票名稱: {stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，5日均線(MA5): {ma5:.2f}，20日均線(MA20): {ma20:.2f}，KD指標: K={k_val:.2f}, D={d_val:.2f}
        請直接給出核心結論（偏多、偏空、觀望），並說明原因。
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"AI 暫時繁忙中，請稍候再點擊。錯誤訊息: {e}"

# --- 📊 看盤系統主程式 ---
st.title("📊 Python 智慧看盤網頁 (V3.7 終極定稿版)")
stock_code = st.text_input("請輸入股票代碼（台股請加 .TW，美股直接輸入）", value="2330.TW")

st.sidebar.header("🛠️ 系統功能設定")
refresh_rate = st.sidebar.slider("🔄 即時報價刷新頻率 (秒)", min_value=5, max_value=60, value=10, step=5)
st.sidebar.markdown("---")
show_ma = st.sidebar.checkbox("顯示均線 (MA5 / MA20 / MA60)", value=True)
sub_indicator = st.sidebar.selectbox("下方副圖指標", ["無", "KD (9, 3, 3)", "MACD (12, 26, 9)"])

# 數據加載
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

    if sub_indicator != "無" and time_frame != "當日":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    else:
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
        template="plotly_dark", plot_bgcolor="#1c1c1e", paper_bgcolor="#121212", 
        margin=dict(l=20, r=20, t=30, b=10), xaxis_rangeslider_visible=False, height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white"))
    )
    fig.update_yaxes(side="right", gridcolor="#2c2c2e")
    st.plotly_chart(fig, on_select="ignore")

# 執行畫圖
render_live_charts()
st.markdown("---")

# 3. 📊 三大法人籌碼面區塊 (⚠️ 移除大小寫限制，確保 100% 秀出)
if ".tw" in stock_code.lower():
    st.markdown("### 📊 籌碼面：三大法人買賣超統計 (大盤整體)")
    inst_df, msg = fetch_tw_legal_data_v2()
    if inst_df is not None:
        f_rows = inst_df.loc[inst_df['單位名稱'].str.contains('外資'), '買賣差額']
        i_rows = inst_df.loc[inst_df['單位名稱'].str.contains('投信'), '買賣差額']
        d_rows = inst_df.loc[inst_df['單位名稱'].str.contains('自營商'), '買賣差額']
        f_net = f_rows.values if not f_rows.empty else 0.0
        i_net = i_rows.values if not i_rows.empty else 0.0
        d_net = d_rows.values if not d_rows.empty else 0.0
        
        cc1, cc2, cc3 = st.columns(3)
        with cc1: st.metric("外資買賣超", f"{f_net:+.2f} 億元")
        with cc2: st.metric("投信買賣超", f"{i_net:+.2f} 億元")
        with cc3: st.metric("自營商買賣超", f"{d_net:+.2f} 億元")
        st.dataframe(inst_df.style.format({'買進金額': '{:.2f}億', '賣出金額': '{:.2f}億', '買賣差額': '{:+.2f}億'}), use_container_width=True)
    else:
        st.info(msg)
    st.markdown("---")

# 4. 🤖 AI 解說區塊
st.markdown("### 🤖 AI 智慧投資解說")
with st.expander("✨ 展開 AI 即時盤勢分析建議", expanded=True):
    if st.button("🚀 啟動 AI 分析當前策略"):
        with st.spinner("AI 正在深度分析中..."):
            ai_report = get_ai_analysis(stock_name, current_price, price_change, price_change_pct, df['MA5'].iloc[-1], df['MA20'].iloc[-1], df['K'].iloc[-1], df['D'].iloc[-1])
            st.write(ai_report)
