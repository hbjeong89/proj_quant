import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(layout="wide")

# 1. S&P 500 종목 리스트 가져오기 (위키피디아 활용)
@st.cache_data
def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    
    # 브라우저인 척 하기 위한 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # requests로 HTML 소스 가져오기
    response = requests.get(url, headers=headers)
    
    # 가져온 HTML 소스를 pandas로 읽기
    table = pd.read_html(response.text)
    return table[0]['Symbol'].tolist()  

# 2. 전 종목 시세 스캔 (Batch 처리)
def scan_market(tickers):
    # 전 종목의 데이터를 한 번에 가져오기 (속도 최적화)
    data = yf.download(tickers, period="2d", interval="1d", group_by='ticker', threads=True)
    
    rows = []
    for ticker in tickers:
        try:
            target = data[ticker]
            if len(target) < 2: continue
            
            prev_close = target['Close'].iloc[-2]
            curr_close = target['Close'].iloc[-1]
            change_pct = ((curr_close - prev_close) / prev_close) * 100
            
            rows.append({'Ticker': ticker, 'Price': curr_close, 'Change %': change_pct})
        except:
            continue
    return pd.DataFrame(rows)

def scan_market_advanced(tickers):
    # 1. 시세 데이터 한 번에 가져오기 (최근 5일치로 여유 있게)
    data = yf.download(tickers, period="5d", interval="1d", group_by='ticker', threads=True)
    
    rows = []
    for ticker in tickers:
        try:
            target = data[ticker].dropna() # 결측치 제거
            if len(target) < 2: continue
            
            # 종목 상세 정보 (종목명, 시총 등) 가져오기
            # Tip: yfinance에서 info를 매번 호출하면 느려질 수 있으므로 필요한 것만 구성
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            
            # 가격 데이터 추출
            prev_close = target['Close'].iloc[-2]
            curr_close = target['Close'].iloc[-1]
            high_price = target['High'].iloc[-1]
            low_price = target['Low'].iloc[-1]
            
            # 변화율 및 지표 계산
            change_pct = ((curr_close - prev_close) / prev_close) * 100
            
            # 거래량 변화 (전일 대비 얼마나 터졌는가 - 세력 개입 확인용)
            prev_vol = target['Volume'].iloc[-2]
            curr_vol = target['Volume'].iloc[-1]
            vol_ratio = (curr_vol / prev_vol) if prev_vol > 0 else 0
            
            rows.append({
                'Ticker': ticker,
                'Name': info.get('longName', 'N/A'),           # 종목 전체 이름
                'Price': round(curr_close, 2),                 # 현재가
                'Change %': round(change_pct, 2),              # 등락률
                'Vol Ratio': round(vol_ratio, 2),              # 거래량 비율 (1.5면 전일 대비 150%)
                'Market Cap (B)': round(info.get('marketCap', 0) / 1e9, 2), # 시가총액 (10억 달러 단위)
                'Day High': round(high_price, 2),
                'Day Low': round(low_price, 2),
                'Sector': info.get('sector', 'N/A')            # 섹터 정보
            })
        except:
            continue
    return pd.DataFrame(rows)

def get_stock_data(ticker, period="1y"):
    stock = yf.Ticker(ticker)
    return stock.history(period=period), stock.info

# --- 사이드바 스캔 실행 ---
st.sidebar.title("종목 발굴")
menu = st.sidebar.radio(
    "발굴 모드 선택",
    ["대시보드", "단기 투자 종목 발굴", "중기 투자 종목 발굴", "장기 투자 종목 발굴"]
)

if menu == "대시보드":
    st.header("메인 대시보드")
    st.write("원하는 투자 전략을 사이드바에서 선택하세요.")
    st.info("단기: 급락주/변동성 | 중기: 이동평균선/추세 | 장기: 재무제표/저평가")

elif menu == "단기 투자 종목 발굴":
    st.header("단기 투자 종목 발굴")
    col11, col12 = st.columns([4,1])
    with col11:
        st.subheader("1. S&P 500 대상 수집 / 2. 하락 폭이 큰 종목 10개 선정 ")
    with col12:
        if st.button("스캔 시작"):
            tickers = get_sp500_tickers()[:100]
            st.session_state['market_data'] = scan_market_advanced(tickers)

    if 'market_data' in st.session_state:
        df = st.session_state['market_data']
        
        st.subheader("하락 종목 (Top 10)")
        top_losers = df.sort_values(by='Change %').head(10)
        
        st.dataframe(top_losers, use_container_width=True)

        # 상세 분석 섹션
        selected_ticker = st.selectbox("분석할 종목 선택", top_losers['Ticker'])

        if selected_ticker:
            st.subheader(f"🔍 {selected_ticker} 상세 분석")
            detail_stock = yf.Ticker(selected_ticker)
            print(f"상세 주가: {detail_stock.news}")
            detail_hist = detail_stock.history(period="1mo")
            
            # 차트 출력
            fig = go.Figure(data=[go.Candlestick(x=detail_hist.index,
                            open=detail_hist['Open'], high=detail_hist['High'],
                            low=detail_hist['Low'], close=detail_hist['Close'])])
            fig.update_layout(title=f"{selected_ticker} 1개월 차트", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
            # # 왜 떨어졌을까? 뉴스 확인
            st.write("**최근 관련 뉴스**")
            if detail_stock.news:
                for n in detail_stock.news[:5]:
                    # 1. 최신 yfinance 구조는 'content' 키 안에 제목과 링크가 있는 경우가 많음
                    if 'content' in n:
                        title = n['content'].get('title', '제목 없음')
                        link = n['content'].get('clickThroughUrl', {}).get('url', '#')
                        publisher = n['content'].get('provider', {}).get('displayName', '알 수 없음')
                    else:
                        # 2. 구형 방식 또는 일반 딕셔너리 구조 대응
                        title = n.get('title', '제목 없음')
                        link = n.get('link', '#')
                        publisher = n.get('publisher', '알 수 없음')
                    
                    st.write(f"- **[{publisher}]** {title}")
                    st.caption(f"[기사 읽기]({link})")
            else:
                st.info("최근 뉴스 데이터가 없습니다.")

elif menu == "중기 투자 종목 발굴":
    st.header("중기 투자 종목 발굴")
    st.markdown("---")
    
    # 전략 가이드 (Expander로 묶어서 깔끔하게 정리)
    with st.expander("🔍 전략 가이드 및 조건 확인"):
        st.write("**조건 1:** 현재 주가 > 20일 > 60일 > 120일 이평선 (정배열)")
        st.write("**조건 2:** 이동평균선 우상향 여부 확인")
        st.info("⚠️ 골든크로스는 하락 추세가 끝나고 정배열로 진입하려는 초기 신호입니다.")

    # 1. 스캔 버튼
    if st.button("🚀 S&P 500 전 종목 스캔 시작"):
        try:
            all_tickers = get_sp500_tickers()
            target_tickers = all_tickers[:500] 
            
            found_stocks = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.text("데이터 수집 중... (약 20~30초 소요)")
            # 대량 데이터는 threads=True가 필수입니다.
            data = yf.download(target_tickers, period="1y", interval="1d", group_by='ticker', threads=True)

            for i, ticker in enumerate(target_tickers):
                try:
                    df = data[ticker].dropna()
                    if len(df) < 120: continue
                    
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['MA60'] = df['Close'].rolling(window=60).mean()
                    df['MA120'] = df['Close'].rolling(window=120).mean()
                    
                    last = df.iloc[-1]
                    # 정배열 조건 검사
                    if last['Close'] > last['MA20'] > last['MA60'] > last['MA120']:
                        prev_close = df['Close'].iloc[-2]
                        change_pct = ((last['Close'] - prev_close) / prev_close) * 100
                        
                        found_stocks.append({
                            "티커": ticker,
                            "현재가": round(last['Close'], 2),
                            "등락률": round(change_pct, 2),
                            "이격도": round(((last['Close'] - last['MA20']) / last['MA20']) * 100, 2)
                        })
                except: continue
                progress_bar.progress((i + 1) / len(target_tickers))
            
            # 결과를 세션에 저장 (중요!)
            st.session_state['scan_results'] = pd.DataFrame(found_stocks)
            status_text.text(f"스캔 완료! {len(found_stocks)}개 종목 발견.")

        except Exception as e:
            st.error(f"스캔 중 오류 발생: {e}")

    # 2. 스캔 결과 표시 및 상세 분석 (버튼 밖으로 배치)
    if 'scan_results' in st.session_state:
        df = st.session_state['scan_results']
        st.success(f"조건에 부합하는 종목 리스트 ({len(df)}개)")
        
        # 데이터프레임 표시
        st.dataframe(df.style.format({'등락률': '{:+.2f}%', '이격도': '{:+.2f}%'}), use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 선택 종목 상세 진단")
        
        # 상세 분석할 종목 선택
        selected_ticker = st.selectbox("분석할 티커를 선택하세요", df['티커'].tolist())
        
        if selected_ticker:
            try:
                # 상세 데이터 호출
                hist, info = get_stock_data(selected_ticker, "1y")
                hist['MA20'] = hist['Close'].rolling(window=20).mean()
                hist['MA60'] = hist['Close'].rolling(window=60).mean()
                hist['MA120'] = hist['Close'].rolling(window=120).mean()
                
                last = hist.iloc[-1]
                prev = hist.iloc[-2]
                
                # 지표 계산
                is_aligned = last['Close'] > last['MA20'] > last['MA60'] > last['MA120']
                is_golden = (prev['MA20'] < prev['MA60']) and (last['MA20'] > last['MA60'])
                disparity = ((last['Close'] - last['MA20']) / last['MA20']) * 100

                # 대시보드 레이아웃
                c1, c2, c3 = st.columns(3)
                c1.metric("현재가", f"${last['Close']:.2f}")
                c2.metric("20일선 이격도", f"{disparity:.2f}%")
                c3.metric("추세", "정배열" if is_aligned else "분석중")

                # 에이전트 리포트
                with st.chat_message("assistant"):
                    st.write(f"**{selected_ticker}** 종목을 분석한 결과입니다.")
                    if disparity > 10:
                        st.error("🚨 이격도가 너무 높습니다! 현재 구간은 단기 과열로 보입니다.")
                    elif 0 <= disparity <= 3:
                        st.success("🎯 20일선 근처 눌림목입니다. 정배열 추세 내에서 진입하기 유리한 위치입니다.")
                    else:
                        st.info("📊 추세는 안정적이며 현재 위치는 정상 범위 내에 있습니다.")

                # 차트
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Price', line=dict(color='white')))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], name='MA20', line=dict(color='yellow')))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['MA60'], name='MA60', line=dict(color='orange')))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['MA120'], name='MA120', line=dict(color='red')))
                fig.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)

            except Exception as e:
                st.error(f"상세 분석 중 오류: {e}")


elif menu == "장기 투자 종목 발굴":
    st.header("장기 투자 종목 발굴")
    st.subheader("재무제표 및 Fundamental 지표 분석")
    
    ticker = st.text_input("분석할 티커 입력", "MSFT").upper()
    if ticker:
        _, info = get_stock_data(ticker)
        col1, col2, col3 = st.columns(3)
        col1.metric("PER", info.get('trailingPE', 'N/A'))
        col2.metric("PBR", info.get('priceToBook', 'N/A'))
        col3.metric("EPS", info.get('trailingEps', 'N/A'))
        
        st.write(f"**비즈니스 요약:** {info.get('longBusinessSummary')[:500]}...")
        
# 사이드바 검색기 수정 버전
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 종목명으로 티커 찾기")

search_query = st.sidebar.text_input("회사명을 입력하세요", placeholder="e.g. Nvidia", key="search_input")

if search_query:
    try:
        # 최신 yfinance에서는 yf.Search(query).quotes 를 사용하는 것이 더 정확합니다.
        search = yf.Search(search_query, max_results=5)
        results = search.quotes  # tickers 대신 quotes 사용
        
        if results:
            st.sidebar.write("**검색 결과:**")
            for res in results:
                # 데이터 구조에 맞춰 안전하게 추출
                symbol = res.get('symbol')
                short_name = res.get('shortname') or res.get('longname') or '이름 없음'
                exch = res.get('exchange', 'Unknown')
                type_disp = res.get('quoteType', '')

                # 버튼 생성 (종목 타입이 EQUITY인 것 위주로 보여주면 좋습니다)
                btn_label = f"{symbol} | {short_name} ({exch})"
                if st.sidebar.button(btn_label, key=f"search_{symbol}"):
                    st.sidebar.success(f"선택됨: **{symbol}**")
                    # 세션 상태에 저장하여 다른 입력창에서 참조할 수 있게 함
                    st.session_state['selected_ticker'] = symbol
                    st.rerun() # 화면 즉시 갱신
        else:
            st.sidebar.warning("결과가 없습니다. 영문으로 입력해보세요.")
            
    except Exception as e:
        # 에러 메시지를 구체적으로 확인하기 위해 e 출력
        st.sidebar.error(f"검색 중 오류 발생: {e}")