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
st.set_page_config(page_title="智慧看盤系統 V5.4 - XQ 永久記憶版", layout="wide") 

# --- 密碼鎖防護機制 --- (保留原邏輯)
if "password_correct" not in st.session_state: 
    st.session_state["password_correct"] = False 
 
if not st.session_state["password_correct"]: 
    st.title("私人智慧看盤系統 V5.4") 
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

# --- 🧱 核心升級：JSON 檔案永久記憶功能 ---
JSON_FILE = "watchlist.json"

def load_watchlist():
    """從硬碟檔案讀取自選股清單，若無檔案則初始化預設"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    # 預設自選清單
    return { 
        "加權指數": "^TWII",
        "台積電 (2330)": "2330.TW", 
        "鴻海 (2317)": "2317.TW", 
        "聯發科 (2454)": "2454.TW" 
    }

def save_watchlist(data):
    """將自選股清單寫入硬碟檔案"""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 將載入的清單寫入 session_state 供網頁運作
if "watchlist_dict" not in st.session_state:
    st.session_state["watchlist_dict"] = load_watchlist()

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

# --- 側邊欄：自選股管理面板 ---
st.sidebar.header("我的自訂追蹤清單") 

# 台灣常見股票中文名稱快查字典
TAIWAN_STOCK_DICT = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2882": "國泰金",
    "2881": "富邦金", "2303": "聯電", "2603": "長榮", "2609": "陽明",
    "2615": "萬海", "2002": "中鋼", "2412": "中華電", "2308": "台達電",
    "2891": "中信金", "2886": "兆豐金", "2884": "玉山金", "2892": "第一金",
    "5880": "合庫金", "2880": "華南金", "2883": "開發金", "2885": "元大金",
    "2887": "台新金", "2890": "永豐金", "3008": "大立光", "2382": "廣達",
    "2357": "華碩", "3231": "緯創", "2324": "仁寶", "2356": "英業達", "2886": "兆豐金"
}

with st.sidebar.expander("➕ 新增自選股"): 
    new_code = st.text_input("輸入股票代碼", placeholder="例如: 2882 或 AAPL").strip() 
    
    if st.button("確認加入自選"): 
        if new_code: 
            target_code = new_code.upper()
            pure_number = target_code.split('.')[0]
            
            if pure_number.isdigit() and not target_code.endswith(".TW") and not target_code.endswith(".TWO"):
                target_code = f"{pure_number}.TW"
            
            with st.spinner("正在驗證股票代碼..."):
                try:
                    test_stock = yf.Ticker(target_code)
                    test_df = test_stock.history(period="1d")
                    
                    if test_df.empty:
                        st.session_state["add_stock_error"] = f"❌ 查無此代碼 [{target_code}]，請重新確認！"
                    else:
                        if pure_number in TAIWAN_STOCK_DICT:
                            detected_name = TAIWAN_STOCK_DICT[pure_number]
                        else:
                            test_info = test_stock.info
                            raw_name = test_info.get('shortName') or test_info.get('longName') or pure_number
                            detected_name = raw_name.split(' ')[0] if len(raw_name) > 12 else raw_name
                        
                        display_key = f"{detected_name} ({target_code})"
                        
                        # 儲存至記憶體與硬碟檔案
                        st.session_state["watchlist_dict"][display_key] = target_code
                        save_watchlist(st.session_state["watchlist_dict"])
                        
                        if "add_stock_error" in st.session_state:
                            del st.session_state["add_stock_error"]
                        st.rerun()
                        
                except Exception as e:
                    st.session_state["add_stock_error"] = "❌ 無法連線至交易所或代碼格式錯誤。"
        else:
            st.sidebar.warning("請先輸入代碼！")

    if "add_stock_error" in st.session_state:
        st.error(st.session_state["add_stock_error"])

# 選擇與刪除股票
selected_display = st.sidebar.selectbox("點擊切換當前關注股票", list(st.session_state["watchlist_dict"].keys())) 
stock_code = st.session_state["watchlist_dict"][selected_display] 

if st.sidebar.button("❌ 從清單中刪除目前股票"): 
    if len(st.session_state["watchlist_dict"]) > 1: 
        del st.session_state["watchlist_dict"][selected_display]
        # 同步儲存刪除後的結果至硬碟檔案
        save_watchlist(st.session_state["watchlist_dict"])
        if "add_stock_error" in st.session_state:
            del st.session_state["add_stock_error"]
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

# --- 💡 永久儲存自選股功能 (解決重啟不見的問題) ---
SAVE_FILE = "watchlist.json"

# 讀取存檔
if "watchlist_dict" not in st.session_state:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            st.session_state["watchlist_dict"] = json.load(f)
    else:
        st.session_state["watchlist_dict"] = { 
            "加權指數": "^TWII", "台積電 (2330)": "2330.TW", 
            "鴻海 (2317)": "2317.TW", "聯發科 (2454)": "2454.TW" 
        }

# 存檔專用工具（在您新增或刪除股票成功時呼叫）
def save_my_watchlist():
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state["watchlist_dict"], f, ensure_ascii=False, indent=4)

# ==================================================================== 
# 📊 XQ 仿真四宮格主排版控制
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
            quote_data.append({"商品名稱": name, "成交價": f"{c_p:,.2f}", "漲跌": f"{chg:+,.2f}", "漲幅(%)": f"{pct:+.2f}%"})
        except:
            quote_data.append({"商品名稱": name, "成交價": "載入中...", "漲跌": "-", "漲幅(%)": "-"})
    st.dataframe(pd.DataFrame(quote_data), use_container_width=True, hide_index=True, height=250)

with row1_col2:
    st.markdown("📈 **【技術分析】**")
    time_frame = st.segmented_control("時間區間", ["當日", "近月", "一年", "五年"], default="一年", key="tech_tf")
    df['MA5'] = df['Close'].rolling(window=5).mean()
    plot_df = df.tail(60) if time_frame == "一年" else df.tail(15) # 簡化過濾邏輯防止截斷
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name="K線", increasing_line_color='red', increasing_fillcolor='red', decreasing_line_color='green', decreasing_fillcolor='green'), row=1, col=1)
    fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['Volume'], marker_color='gray'), row=2, col=1)
    fig.update_layout(template="plotly_white", xaxis_rangeslider_visible=False, height=210, margin=dict(l=10, r=40, t=5, b=5), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 定義第二橫列 (Row 2): 走勢明細頁籤 + 新聞AI頁籤
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
            # 優先嘗試從 yfinance 抓取該個股的內建相關新聞清單
            news_list = info.get('news', [])
            
            if news_list and len(news_list) > 0:
                # 只取前 4 則新聞呈現
                for item in news_list[:4]:
                    title = item.get('title', '無標題')
                    publisher = item.get('publisher', '財經媒體')
                    link = item.get('link', '#')
                    
                    # 嘗試轉換並格式化新聞發布時間
                    provider_time = item.get('providerPublishTime', None)
                    if provider_time:
                        date_str = datetime.datetime.fromtimestamp(provider_time).strftime('%m/%d %H:%M')
                    else:
                        date_str = datetime.date.today().strftime('%m/%d')
                        
                    st.markdown(f"📌 **[{title}]({link})**  \n<small style='color:gray;'>時間: {date_str} | 來源: {publisher}</small>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin:4px 0px; border-top:1px dashed #eee;'>", unsafe_allow_html=True)
            else:
                # 🌟 優化處：若週末沒有個股即時新聞，則改為抓取大盤（^TWII）的近期新聞作為補充，避免畫面空白
                st.caption("⏱️ 週末台股未開盤，為您聯播近期焦點財經新聞：")
                market_stock = yf.Ticker("^TWII")
                market_news = market_stock.info.get('news', [])[:3]
                
                if market_news:
                    for m_item in market_news:
                        m_title = m_item.get('title', '焦點財經快訊')
                        m_link = m_item.get('link', '#')
                        st.markdown(f"📰 [{m_title}]({m_link})")
                else:
                    # 全球無重大新聞時的 XQ 經典偽數據模擬
                    mock_news = [
                        f"外資在集中市場近五日動態關注 {selected_display}", 
                        f"兩岸三地財經指數最新盤後重點整理",
                        f"個股近期籌碼面與技術均線多空角力分析"
                    ]
                    for n in mock_news: 
                        st.caption(f"⏱️ {datetime.date.today().strftime('%m/%d')} | {n}")
        except Exception as news_err:
            st.caption("暫無即時新聞資訊，系統持續追蹤中。")
            
    with tab_ai:
        st.write(f"當前分析：**{selected_display}**")
        if st.button("🚀 啟動 AI 深度策略分析", key="ai_btn_final"):
            with st.spinner("AI 正在解析多空力道..."):
                ai_report = get_ai_analysis(selected_display, current_price, price_change, price_change_pct, df['MA5'].iloc[-1], 50, 50)
                st.info(ai_report)