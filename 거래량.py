import time
import pyupbit
import datetime

access = "your-code"
secret = "your-code"


def get_moving_average_volume(ticker, interval, count):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None:
        return None
    return df["volume"].mean()


def get_current_price(ticker):
    return pyupbit.get_orderbook(ticker=ticker)["orderbook_units"][0]["ask_price"]


def get_balance(ticker):
    balances = upbit.get_balances()

    for b in balances:
        if b["currency"] == ticker:
            if b["balance"] is not None:
                return float(b["balance"])
            else:
                return 0
    return 0


# 로그인
upbit = pyupbit.Upbit(access, secret)
print("자동매매 시작")

MAX_INVESTMENT_COUNT = 10  # 최대 투자 코인 개수
INVESTMENT_RATIO = 0.1  # 총 자산 대비 투자 비율
STOP_LOSS_RATIO = 0.97  # 손절 비율 (3% 손실)
TAKE_PROFIT_RATIO = 1.02  # 익절 비율 (2% 이익)

# 모든 KRW 티커 목록 가져오기
all_tickers = pyupbit.get_tickers(fiat="KRW")

invested = {}

# 자동매매 시작
while True:
    try:
        krw_balance = get_balance("KRW")
        investment_limit = krw_balance * INVESTMENT_RATIO
        num_investments = len(invested)

        for ticker in all_tickers:
            current_price = get_current_price(ticker)
            avg_volume = get_moving_average_volume(
                ticker, "minute1", 10
            )  # 10분 이동 평균 거래량
            last_volume = get_moving_average_volume(ticker, "minute1", 1)  # 마지막 1분 거래량

            if avg_volume is None or last_volume is None:
                continue

            volume_ratio = last_volume / avg_volume  # 마지막 1분 거래량 / 10분 이동평균 거래량

            print(f"{ticker} - 현재 가격: {current_price}, 거래량 비율: {volume_ratio}")

            # 투자 개수가 MAX_INVESTMENT_COUNT보다 작을 때만 매수를 진행
            if volume_ratio > 2.0 and num_investments < MAX_INVESTMENT_COUNT:
                if krw_balance > 5000 and investment_limit > 5000:
                    upbit.buy_market_order(ticker, investment_limit * 1)
                    invested[ticker] = {
                        "price": current_price,
                        "volume": investment_limit * 1 / current_price,
                    }
                    num_investments += 1

                    # 매도 조건 검사 및 손절매 처리
            if ticker in invested:
                investment_info = invested[ticker]
                if current_price >= investment_info["price"] * TAKE_PROFIT_RATIO:
                    upbit.sell_market_order(ticker, investment_info["volume"] * 1)
                    del invested[ticker]
                if current_price <= investment_info["price"] * STOP_LOSS_RATIO:
                    upbit.sell_market_order(ticker, investment_info["volume"] * 1)
                    del invested[ticker]

    except Exception as e:
        print(f"에러 발생: {e}")
