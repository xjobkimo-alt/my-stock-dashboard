import datetime
import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 網頁全域設定
st.set_page_config(page_title="智慧看盤系統", layout="centered")

st.title("📊 Python 智慧看盤網頁 (即時自動重新整理版)")
stock_code = st.text_input("請輸入股票代碼（台股請加 .TW，美股直接輸入）", value="2330.TW")

# ⚙️ 側邊欄：技術指標與重新整理設定
st.sidebar.header("🛠️ 系統功能設定")
refresh_rate = st.sidebar.slider("🔄 即時報價刷新頻率 (秒)", min_value=5, max_value=60, value=10, step=5)
st.sidebar.markdown("---")
show_ma = st.sidebar.checkbox("顯示均線 (MA5 / MA20 / MA60)", value=True)
sub_indicator = st.sidebar.selectbox("下方副圖指標", ["無", "KD (9, 3, 3)", "MACD (12, 26, 9)"])

# 2. 核心看盤區塊 (使用 st.fragment 實現局部定時自動重新整理)
@st.fragment(run_every=refresh_rate)
def render_stock_dashboard(ticker):
    # 顯示目前更新時間，方便觀察是否有在自動跳動
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"🕒 數據最後更新時間: {now} (每 {refresh_rate} 秒自動刷新)")
    
    # 為了即時報價，這裡我們不使用快取 (cache)，每次定時觸發都抓最新資料
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="5y")
        info = stock.info
        
        # --- 🧮 計算技術指標 (純 Pandas 內建數學公式) ---
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        low_9 = df['Low'].rolling(window=9).min()
        high_9 = df['High'].rolling(window=9).max()
        rsv = 100 * ((df['Close'] - low_9) / (high_9 - low_9))
        rsv = rsv.fillna(50)
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            
        ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        # ------------------------------------------------------

        current_price = info.get("currentPrice", df['Close'].iloc[-1])
        prev_close = info.get("previousClose", df['Close'].iloc[-2])
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100
        color_light = "#ff4d4d" if price_change >= 0 else "#00cc66"
        
        # 3. 頂部大盤即時報價區塊
        st.markdown(f"### {info.get('longName', ticker)} [{ticker.split('.')}]")
        
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("即時價", f"{current_price:,.2f}")
        with c2: st.metric("漲跌", f"{price_change:+,.2f}")
        with c3: st.metric("幅度", f"{price_change_pct:+.2f}%")

        st.markdown("---")

        # 4. 時間軸切換
        time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年")
        latest_date = df.index[-1]
        
        if time_frame == "五年": plot_df = df
        elif time_frame == "一年": plot_df = df.loc[latest_date - pd.Timedelta(days=365):]
        elif time_frame == "近月": plot_df = df.loc[latest_date - pd.Timedelta(days=30):]
        else: plot_df = yf.Ticker(ticker).history(period="1d", interval="5m")

        # 5. 動態調整圖表列數
        if sub_indicator != "無" and time_frame != "當日":
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.03, row_heights=[0.55, 0.22, 0.23])
        else:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 主圖 (Row 1)：K 線圖
        fig.add_trace(go.Candlestick(
            x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'],
            name="K線", increasing_line_color='#ff4d4d', increasing_fillcolor='#ff4d4d',
            decreasing_line_color='#00cc66', decreasing_fillcolor='#00cc66'
        ), row=1, col=1)

        # 主圖疊加均線 (MA)
        if show_ma and time_frame != "當日":
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#ffffff', width=1), name='MA5'), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA20'], mode='lines', line=dict(color='#e6b800', width=1.2), name='MA20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA60'], mode='lines', line=dict(color='#00bcff', width=1.5), name='MA60'), row=1, col=1)

        # 副圖 (Row 2)：成交量
        volume_colors = ['#ff4d4d' if c >= o else '#00cc66' for o, c in zip(plot_df['Open'], plot_df['Close'])]
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=volume_colors, name="成交量", opacity=0.7), row=2, col=1)

        # 副圖 (Row 3)：KD 或 MACD
        if sub_indicator == "KD (9, 3, 3)" and time_frame != "當日":
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['K'], mode='lines', line=dict(color='#ff9900', width=1.2), name='K'), row=3, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['D'], mode='lines', line=dict(color='#00ccff', width=1.2), name='D'), row=3, col=1)
            fig.add_hline(y=80, line_dash="dash", line_color="rgba(255,255,255,0.2)", row=3, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="rgba(255,255,255,0.2)", row=3, col=1)
            
        elif sub_indicator == "MACD (12, 26, 9)" and time_frame != "當日":
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MACD'], mode='lines', line=dict(color='#ffffff', width=1.2), name='MACD'), row=3, col=1)
            fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MACD_Signal'], mode='lines', line=dict(color='#ffcc00', width=1.2), name='Signal'), row=3, col=1)
            hist_colors = ['#ff4d4d' if h >= 0 else '#00cc66' for h in plot_df['MACD_Hist']]
            fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['MACD_Hist'], marker_color=hist_colors, name="Hist"), row=3, col=1)

        # 調整 Plotly 全域外觀
        fig.update_layout(
            template="plotly_dark", plot_bgcolor="#1c1c1e", paper_bgcolor="#121212",
            margin=dict(l=20, r=20, t=10, b=10), xaxis_rangeslider_visible=False,
            height=600 if (sub_indicator != "無" and time_frame != "當日") else 480, showlegend=True
        )
        fig.update_xaxes(gridcolor="#2c2c2e")
        fig.update_yaxes(gridcolor="#2c2c2e", side="right")
        
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
        
        # 6. 詳細報價區塊
        st.markdown("### 📋 詳細報價")
        row1_1, row1_2, row1_3 = st.columns(3)
        with row1_1: st.markdown(f"**成交：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{current_price:,.2f}</span>", unsafe_allow_html=True)
        with row1_2: st.markdown(f"**漲跌：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change:+,.2f}</span>", unsafe_allow_html=True)
        with row1_3: st.markdown(f"**幅度：** <span style='color:{color_light}; font-size:20px; font-weight:bold;'>{price_change_pct:+.2f}%</span>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"數據載入失敗。錯誤訊息: {e}")

# 執行局部刷新功能
render_stock_dashboard(stock_code)
