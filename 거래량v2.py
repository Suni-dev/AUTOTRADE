import time
import pyupbit
import datetime

access = ""
secret = ""


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
        # 보유 중인 종목과 매도 목표 가격을 출력합니다.
        if invested:  # 보유 종목이 있을 경우에만 출력
            print("보유 중인 종목과 매도 목표:")
            for ticker, info in invested.items():
                current_price = get_current_price(ticker)
                sell_price = info["price"] * TAKE_PROFIT_RATIO
                profit_or_loss = (
                    (current_price - info["price"]) / info["price"] * 100
                )  # 평가손익 계산
                print(
                    f"{ticker}: 매수 가격 - {info['price']} KRW, 현재 가격 - {current_price} KRW, 목표 매도가 - {sell_price} KRW, 평가손익 - {profit_or_loss:.2f}%"
                )
        else:
            print("현재 보유 중인 종목이 없습니다.")

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

            # 투자 개수가 MAX_INVESTMENT_COUNT보다 작을 때만 매수를 진행
            if volume_ratio > 2.0 and num_investments < MAX_INVESTMENT_COUNT:
                if krw_balance > 5000 and investment_limit > 5000:
                    buy_result = upbit.buy_market_order(ticker, investment_limit)
                    invested[ticker] = {
                        "price": current_price,
                        "volume": investment_limit / current_price,
                    }
                    num_investments += 1
                    print(f"{ticker}에 투자했습니다: {buy_result}")

            # 매도 조건 검사 및 매도 처리
            if ticker in invested:
                investment_info = invested[ticker]
                if current_price >= investment_info["price"] * TAKE_PROFIT_RATIO:
                    sell_result = upbit.sell_market_order(
                        ticker, investment_info["volume"]
                    )
                    print(f"익절 매도 주문 결과: {sell_result}")  # 매도 주문 결과 로깅
                    del invested[ticker]
                elif current_price <= investment_info["price"] * STOP_LOSS_RATIO:
                    sell_result = upbit.sell_market_order(
                        ticker, investment_info["volume"]
                    )
                    print(f"손절 매도 주문 결과: {sell_result}")  # 매도 주문 결과 로깅
                    del invested[ticker]

    except Exception as e:
        print(f"에러 발생: {e}")
