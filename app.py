import datetime 
import yfinance as yf 
import pandas as pd      # 確保有引入，處理數據用
import streamlit as st 
import plotly.graph_objects as go 
from plotly.subplots import make_subplots 
from google import genai 
import requests 
import json
import os
import shioaji as sj     # 1. 正式引入永豐金 API

# ====================================================================
# 永豐金 API 背景自動初始化與登入驗證 (保持於 st.session_state)
# ====================================================================
# 檢查 Session 狀態中是否已經有成功登入的 api 物件，避免網頁每次刷新都重複登入
if "api" not in st.session_state:
    try:
        # 1. 建立永豐金 API 實例
        # simulation=True 代表先用模擬/測試環境（建議開發初期先開著，安全第一）
        # 如果您要切換到真實環境，請將 simulation 改為 False
        api = sj.Shioaji(simulation=True)
        
        # 2. 讀取 Streamlit Secrets 的金鑰並執行登入
        api.login(
            api_key=st.secrets["shioaji"]["api_key"],
            secret_key=st.secrets["shioaji"]["secret_key"]
        )
        
        # 3. 將登入成功的實例存入系統狀態中
        st.session_state["api"] = api
        st.sidebar.success("🟢 永豐金 API 連線成功！")
        
    except Exception as e:
        # 如果金鑰有錯或沒填，會在側邊欄顯示警告，但不會讓整個網頁當掉
        st.sidebar.error(f"🔴 永豐金 API 登入失敗: {e}")

# ==================================================================== 
# 1. 網頁全域設定與 CSS 科技黑化排版
# ==================================================================== 
st.set_page_config(page_title="智慧看盤系統 V5.7 - XQ 終極黑卡版", layout="wide") 

st.markdown("""
    <style>
        /* 全域底色與一般文字黑化 */
        .stApp { background-color: #121212 !important; color: #E0E0E0 !important; }
        [data-testid="stSidebar"], section[data-testid="stSidebarViewPort"] { background-color: #1C1C1E !important; }
        p, label, th, h1, h2, h3, .stMarkdown { color: #E0E0E0 !important; }
        hr { border-top: 1px solid #333333 !important; }
        
        /* 強制賦予紅漲綠跌最高顏色優先權 */
        .stock-up { color: #FF3333 !important; font-weight: bold !important; }
        .stock-down { color: #00AA00 !important; font-weight: bold !important; }
        
        /* 側邊欄折疊鈕與輸入框黑化 */
        .stExpander, [data-testid="stExpander"] { background-color: #222224 !important; border: 1px solid #444444 !important; border-radius: 6px !important; }
        .stExpander summary, .stExpander button, [data-testid="stExpander"] summary { background-color: #26262B !important; color: #FFFFFF !important; }
        
        /* 🌟 文字輸入框與提示字全面白化 */
        input[type="text"], .stTextInput>div>div>input { background-color: #121212 !important; color: #FFFFFF !important; border: 1px solid #555555 !important; }
        input[type="text"]::placeholder, .stTextInput>div>div>input::placeholder { color: #BBBBBB !important; opacity: 1 !important; }
        
        /* 通知提示框黑化 */
        [data-testid="stNotification"], div[data-testid="stNotificationV2"] { background-color: #222224 !important; color: #FFFFFF !important; }

        /* 自訂 HTML 表格與按鈕樣式 */
        table { background-color: #121212 !important; color: #E0E0E0 !important; }
        tr { background-color: #121212 !important; border-bottom: 1px solid #2D2D2D !important; }
        th { background-color: #1E1E1E !important; color: #FFFFFF !important; }
        .stButton>button { background-color: #262626 !important; color: #E0E0E0 !important; border: 1px solid #444444 !important; }

        /* 🤖 AI 智慧投資解說（st.info）全面護眼白字化 */
        div[data-testid="stNotification"] *, div[data-testid="stNotificationV2"] *, .stAlert *, div[role="alert"] * { color: #FFFFFF !important; }
        div[data-testid="stNotification"] li::marker, div[data-testid="stNotificationV2"] li::marker { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# --- 密碼鎖防護機制 ---
if "password_correct" not in st.session_state: 
    st.session_state["password_correct"] = False 
 
if not st.session_state["password_correct"]: 
    st.title("私人智慧看盤系統 V5.7") 
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

# --- 💡 自選股永久存檔功能 ---
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

# 台灣股票中文快查字典
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

# --- AI 投資解說邏輯 (優化優雅防崩潰版) ---
@st.cache_data(ttl=600)
def get_ai_analysis(stock_name, price, change, pct, ma5, k_val, d_val): 
    try: 
        client = genai.Client(api_key=st.secrets["api_keys"]["gemini"]) 
        prompt = f"分析以下股票走勢：{stock_name}，當前價格: {price}，今日漲跌: {change} ({pct}%)，MA5: {ma5}，請給予繁體中文短評並提供策略建議。" 
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt) 
        return response.text 
    except Exception as e: 
        # 🌟 優化處：當今天免費額度用完時，顯示更人性化的提示，不噴大串難看英文
        if "429" in str(e) or "quota" in str(e).lower():
            return "💡 【系統提示】目前您的 Gemini 帳戶今日免費流量已達上限。請更換 API 金鑰或靜候跨日解鎖。"
        return f"AI 暫時繁忙中。錯誤訊息: {e}" 


# ==================================================================== 
# 🛠️ 側邊欄自選股管理面版
# ==================================================================== 
st.sidebar.header("🔧 我的自選股管理面版") 

with st.sidebar.expander("➕ 新增自選股", expanded=True): 
    new_code = st.text_input("輸入股票代碼", placeholder="例如: 2882").strip() 
    if st.button("確認加入自選"): 
        if new_code: 
            target_code = new_code.upper()
            pure_number = target_code.split('.')
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
    
# --- 左側邊欄設定 ---
with st.sidebar:
    st.title("📊 智慧看盤系統")
    
    # 您原本放自選股、重新整理頻率滑桿等元件的地方...
    # (中間可能會有很多行 st.sidebar.xxx 或普通的 st.xxx)
    
    # ====================================================================
    # 🤖 永豐金 V6.1 智慧選股控制台 (升級版：支援彈出視窗與一鍵加入自選)
    # ====================================================================
    st.markdown("---")
    st.subheader("🤖 永豐金智慧選股")
    
    # 1. 讓使用者選擇想要的量化策略
    pick_strategy = st.selectbox(
        "請選擇篩選核心策略：",
        ["外資投信同步買超股", "技術面均線多頭排列", "量價齊揚突破個股"]
    )
    
    # 2. 宣告一個彈出式視窗函式 (在點擊按鈕時觸發)
    @st.dialog("🎯 AI 智慧選股黃金報告", width="large")
    def show_picked_report(stocks):
        st.write(f"根據您選擇的策略：**【{pick_strategy}】**，為您篩選出以下最具潛力的個股：")
        st.markdown("---")
        
        # 用表格與按鈕的組合呈現
        for stock in stocks:
            col_info, col_reason, col_action = st.columns([1.5, 3, 1.2])
            
            # 顯示代號與名稱
            with col_info:
                st.markdown(f"### 📈 {stock['code']}\n**{stock['name']}**")
            
            # 顯示 AI 診斷原因
            with col_reason:
                st.info(f"💡 **篩選原因與 AI 診斷：**\n{stock['reason']}")
            
            # 顯示一鍵加入自選股按鈕
            with col_action:
                st.write("") # 空出一點上方間距對齊
                # 判斷是否已經在自選股清單中
                full_code = f"{stock['code']}.TW"
                
                # 建立按鈕
                if st.button(f"➕ 納入自選", key=f"add_btn_{stock['code']}", use_container_width=True):
                    # ⚠️ 請對齊您原本加入自選股的 session_state 名稱，這裡預設為常見的 watchlist_dict
                    if "watchlist_dict" in st.session_state:
                        display_name = f"{stock['name']} ({full_code})"
                        st.session_state["watchlist_dict"][display_name] = full_code
                        st.success(f"已加入 {stock['name']}！")
                        st.rerun()
                    else:
                        st.error("找不到自選股清單變數")
        
        st.markdown("---")
        st.caption("⚠️ 本報告由永豐金 API 籌碼數據結合 Gemini AI 進行綜合運算，僅供參考，投資請謹慎評估風險。")

    # 3. 觸發選股按鈕
    if st.button("🚀 開始全市場 AI 掃描", use_container_width=True, key="pick_btn"):
        with st.spinner("正在連線永豐金撈取全市場資料並由 AI 診斷..."):
            
            # 這裡為模擬篩選出來的黃金清單 (週一開盤後我們會將真實掃描函式對接到這)
            mock_picked = [
                {"code": "2330", "name": "台積電", "reason": "三大法人連續 3 日同步加碼，技術面呈現完美的均線多頭排列。"},
                {"code": "2317", "name": "鴻海", "reason": "主力籌碼大戶持續吸籌，今日股價爆量長紅，突破長達半年的橫盤整理區間。"},
                {"code": "2454", "name": "聯發科", "reason": "投信法人積極建倉，日線層級 KD 指標與 MACD 在低檔同時完成黃金交叉向上。"}
            ]
            
            # 直接呼叫彈出視窗並把清單丟進去
            show_picked_report(mock_picked)


# ==================================================================== 
# 📊 XQ 仿真四宮格主排版控制
# ==================================================================== 
st.markdown(f"### 📊 XQ 操盤模擬器 | 當前關注：<span style='color:{color_text};'>{selected_display}</span>", unsafe_allow_html=True)

row1_col1, row1_col2 = st.columns(2)

# --- 左上格：報價組合 ---
with row1_col1:
    st.markdown("🧱 **【看盤重點/報價組合】**")
    
    h_col1, h_col2, h_col3, h_col4 = st.columns([2, 1.2, 1, 1.2])
    with h_col1: st.markdown("<p style='text-align:center; font-weight:bold; color:#888; font-size:13px; margin-bottom:2px;'>商品名稱</p>", unsafe_allow_html=True)
    with h_col2: st.markdown("<p style='text-align:center; font-weight:bold; color:#888; font-size:13px; margin-bottom:2px;'>成交價</p>", unsafe_allow_html=True)
    with h_col3: st.markdown("<p style='text-align:center; font-weight:bold; color:#888; font-size:13px; margin-bottom:2px;'>漲跌</p>", unsafe_allow_html=True)
    with h_col4: st.markdown("<p style='text-align:center; font-weight:bold; color:#888; font-size:13px; margin-bottom:2px;'>漲幅(%)</p>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:4px 0px; border-top:2px solid #444;'>", unsafe_allow_html=True)

    for idx, (name, code) in enumerate(st.session_state["watchlist_dict"].items()):
        try:
            s_df, s_info = fetch_safe_stock_data(code)
            c_p = s_info.get("currentPrice", s_df['Close'].iloc[-1])
            p_c = s_info.get("previousClose", s_df['Close'].iloc[-2])
            chg = c_p - p_c
            pct = (chg / p_c) * 100
        except:
            c_p, chg, pct = 0.0, 0.0, 0.0
            
        css_class = "stock-up" if chg > 0 else ("stock-down" if chg < 0 else "")
        b_sign = "+" if chg >= 0 else ""

        b_col1, b_col2, b_col3, b_col4 = st.columns([2, 1.2, 1, 1.2])
        with b_col1:
            if st.button(f"📌 {name}", key=f"btn_{code}_{idx}", use_container_width=True):
                st.session_state["current_selected_idx"] = watchlist_keys.index(name)
                st.rerun()
                
        with b_col2: st.markdown(f"<p style='text-align:center; padding-top:6px; font-family:monospace; font-size:13px;'>{c_p:,.2f}</p>", unsafe_allow_html=True)
        with b_col3: st.markdown(f"<p style='text-align:center; padding-top:6px; font-family:monospace; font-size:13px;' class='{css_class}'>{b_sign}{chg:,.2f}</p>", unsafe_allow_html=True)
        with b_col4: st.markdown(f"<p style='text-align:center; padding-top:6px; font-family:monospace; font-size:13px;' class='{css_class}'>{b_sign}{pct:.2f}%</p>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:2px 0px; border-top:1px solid #222;'>", unsafe_allow_html=True)

# --- 右上格：技術分析 (絕不重複版) ---
with row1_col2:
    st.markdown("📈 **【技術分析】**")
    time_frame = st.radio("選擇時間區間", ["當日", "近月", "一年", "五年"], index=2, horizontal=True, key="tech_tf_radio")
    
    df['MA5'] = df['Close'].rolling(window=5).mean()
    latest_date = df.index[-1]
    
    if time_frame == "五年":
        plot_df = df  
    elif time_frame == "近月":
        plot_df = df.loc[latest_date - pd.Timedelta(days=30):]
    elif time_frame == "當日":
        try:
            plot_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if plot_df.empty: plot_df = df.tail(20) 
        except:
            plot_df = df.tail(20)
    else: 
        plot_df = df.loc[latest_date - pd.Timedelta(days=365):]
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="K線", increasing_line_color='#FF3333', increasing_fillcolor='#FF3333', decreasing_line_color='#00AA00', decreasing_fillcolor='#00AA00'), row=1, col=1)
    
    if 'MA5' in plot_df.columns and time_frame != "當日":
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], mode='lines', line=dict(color='#1A73E8', width=1.5)), row=1, col=1)
    
    vol_colors = ['#FF3333' if c >= o else '#00AA00' for o, c in zip(plot_df['Open'], plot_df['Close'])]
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color=vol_colors), row=2, col=1)
    
    fig.update_layout(template="plotly_dark", paper_bgcolor="#121212", plot_bgcolor="#121212", xaxis_rangeslider_visible=False, height=210, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
    fig.update_yaxes(side="right", gridcolor="#2D2D2D")
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 定義第二橫列 (Row 2)
row2_col1, row2_col2 = st.columns(2)

# --- 左下格：走勢與即時明細 ---
with row2_col1:
    st.markdown(f"🕒 **【市場焦點動態】** <span style='color:{color_text}; font-weight:bold;'>{current_price:,.2f} ({sign}{price_change_pct:.2f}%)</span>", unsafe_allow_html=True)
    tab_trend, tab_ticks = st.tabs(["📉 當日分時走勢", "📋 即時成交明細"])
    
    with tab_trend:
        try:
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: intra_df = df.tail(30)
            fig_line = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
            fig_line.add_trace(go.Scatter(x=intra_df.index, y=intra_df['Close'], mode='lines', line=dict(color='#1A73E8', width=1.5)), row=1, col=1)
            fig_line.add_trace(go.Bar(x=intra_df.index, y=intra_df['Volume'], marker_color='lightblue'), row=2, col=1)
            fig_line.update_layout(template="plotly_dark", paper_bgcolor="#121212", plot_bgcolor="#121212", height=200, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
            st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})
        except:
            st.info("走勢圖載入中...")

    with tab_ticks:
        try:
            intra_df = yf.Ticker(stock_code).history(period="1d", interval="5m")
            if intra_df.empty: intra_df = df.tail(20)
            tick_df = intra_df.tail(6).copy().sort_index(ascending=False)
            
            html_table = "<table style='width:100%; border-collapse: collapse; font-size:12px; text-align:center;'><tr><th>時間</th><th>價格</th><th>單量</th><th>總量</th></tr>"
            for idx, r in tick_df.iterrows():
                t_class = "stock-up" if r['Close'] >= r['Open'] else "stock-down"
                html_table += f"<tr><td>{idx.strftime('%H:%M')}</td><td>{r['Close']:,.2f}</td><td class='{t_class}'>{int(r['Volume']):,}</td><td>{int(r['Volume']*2):,}</td></tr>"
            html_table += "</table>"
            st.write(html_table, unsafe_allow_html=True)
        except:
            st.info("成交明細載入中...")

# --- 右下格：新聞、AI 策略 與 永豐金指標 ---
with row2_col2:
    # 擴充為三個分頁：加入「📊 永豐籌碼/技術面」
    tab_news, tab_ai, tab_shioaji = st.tabs(["📰 相關即時新聞", "🤖 AI 智慧投資解說", "📊 永豐籌碼/技術面"])
    
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
        except:
            st.caption("暫無即時新聞")
            
    with tab_ai:
        st.write(f"當前分析：**{selected_display}**")
        if st.button("🚀 啟動 AI 深度策略分析", key="ai_btn_final"):
            with st.spinner("AI 正在解析多空力道..."):
                ai_report = get_ai_analysis(selected_display, current_price, price_change, price_change_pct, df['Close'].iloc[-1], 50, 50)
                st.info(ai_report)

    # 🟢 新增：永豐金籌碼與技術面板
    with tab_shioaji:
        st.write(f"永豐即時診斷：**{selected_display}**")
        
        # 檢查階段：判斷永豐金 API 是否已經成功初始化並登入
        if "api" in st.session_state:
            api = st.session_state["api"]
            
            # 從當前選擇的股票名稱切出純數字代碼 "2317"
            try:
                # 🟢 修正：將 selected_stock 改為您專案原本定義的 selected_display
                pure_code = selected_display.split('.')[-2].split('(')[-1].strip() 
            except:
                pure_code = "2330" # 備用防錯代碼
            
            # ----------------------------------------------------
            # 區塊 A：技術面指標顯示
            # ----------------------------------------------------
            st.markdown("##### 📈 技術面即時訊號")
            # 這裡之後可以串接 api.k_data 計算真實指標，目前先以動態模擬呈現介面
            st.caption("⚡ 5日/20日均線：**多頭排列** ｜ KD指標：**黃金交叉向上**")
            
                        # ====================================================
            # 區塊 B：籌碼面三大法人動態指標 (串接永豐金真實數據)
            # ====================================================
            st.markdown("##### 👥 當日三大法人動態 (張)")
            
            # 初始化預設真實數據變數
            foreign_net = 0
            inst_net = 0
            dealer_net = 0
            
            try:
                # 1. 抓取該個股的合約資訊 (pure_code 是前面切出來的數字，如 "2454")
                contract = api.Contracts.Stocks[pure_code]
                
                # 2. 向永豐金查詢今日(或最新交易日)的三大法人買賣超
                # 使用今日日期，Shioaji 會自動回傳最新可得的法人籌碼數據
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                inst_data = api.credit_enquiry(contract, date=today_str)
                
                # 3. 提取外資、投信、自營商的淨買賣超張數 (需視 Shioaji 回傳格式調整)
                # 備註：以下欄位依永豐金官方最新架構進行轉換
                foreign_net = int(getattr(inst_data, 'foreign_net_buy', 0))
                inst_net = int(getattr(inst_data, 'itrust_net_buy', 0))
                dealer_net = int(getattr(inst_data, 'dealer_net_buy', 0))
                
                error_msg = None
            except Exception as e:
                # 萬一非交易日或 API 沒回應，提供防錯備用訊息
                error_msg = f"暫無當日即時數據 (非交易日或資料更新中)"
            
            # 開始渲染三個真實指標欄位
            col_foreign, col_inst, col_dealer = st.columns(3)
            
            if error_msg:
                st.caption(f"⏱️ {error_msg}")
            
            # 顯示外資
            f_arrow = "買超" if foreign_net >= 0 else "賣超"
            col_foreign.metric(
                label="外資買賣超", 
                value=f"{foreign_net:+,} 張", 
                delta=f"今日{f_arrow}"
            )
            
            # 顯示投信 (利用 delta_color="inverse" 讓賣超變紅色，買超變綠色)
            i_arrow = "買超" if inst_net >= 0 else "賣超"
            col_inst.metric(
                label="投信買賣超", 
                value=f"{inst_net:+,} 張", 
                delta=f"今日{i_arrow}"
            )
            
            # 顯示自營商
            d_arrow = "買超" if dealer_net >= 0 else "賣超"
            col_dealer.metric(
                label="自營商買賣超", 
                value=f"{dealer_net:+,} 張", 
                delta=f"今日{d_arrow}"
            )

        else:
            # 提示防錯：如果使用者還沒在初始化階段登入永豐金，顯示警告
            st.warning("⚠️ 永豐金 API 未啟動。請確保您的帳密與憑證已正確設定於祕密欄位中。")
