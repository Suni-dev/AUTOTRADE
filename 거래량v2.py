import time
import pyupbit
import datetime
import requests
import pandas as pd



def get_moving_average_volume(ticker, interval, count):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None:
        return None
    return df["volume"].mean()


# 텔레그램 메시지를 보내는 함수
def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot6870720146:AAHsFIP709BrPwWixfpPwdWvkLStYZJXoWM/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",  # 메시지를 마크다운 형식으로 보냅니다.
    }
    response = requests.post(url, data=payload)
    return response.json()


# 텔레그램 봇 토큰과 채팅 ID 설정 (이 부분을 실제 값으로 변경해야 함)
TELEGRAM_BOT_TOKEN = "6870720146:AAHsFIP709BrPwWixfpPwdWvkLStYZJXoWM"
TELEGRAM_CHAT_ID = "6333326442"


# ATR을 계산하는 함수 (예시로 추가)
def get_atr(ticker, interval, count):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None:
        return None
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=count).mean().iloc[-1]
    return atr


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


def update_invested_list():
    global invested
    current_holdings = upbit.get_balances()
    holding_tickers = {
        item["currency"] for item in current_holdings if item["currency"] != "KRW"
    }
    invested = {
        ticker: info for ticker, info in invested.items() if ticker in holding_tickers
    }


# 로그인
upbit = pyupbit.Upbit(access, secret)
print("자동매매 시작")

MAX_INVESTMENT_COUNT = 6  # 최대 투자 코인 개수
INVESTMENT_RATIO = 0.166  # 총 자산 대비 투자 비율
STOP_LOSS_RATIO = 0.97  # 손절 비율 (3% 손실)
TAKE_PROFIT_RATIO = 1.03  # 익절 비율 (3% 이익)
MINIMUM_KRW_ORDER = 5000  # 최소 KRW 주문 금액
VOLUME_SURGE_THRESHOLD = 6  # 거래량이 6배

# 모든 KRW 티커 목록 가져오기
all_tickers = pyupbit.get_tickers(fiat="KRW")

invested = {}

# 자동매매 시작
while True:
    try:
        update_invested_list()
        # 보유 중인 종목과 매도 목표 가격을 출력합니다.
        if invested:  # 보유 종목이 있을 경우에만 출력
            message = "보유 중인 종목과 매도 목표:\n"
            for ticker, info in invested.items():
                current_price = get_current_price(ticker)
                sell_price = info["price"] * TAKE_PROFIT_RATIO
                profit_or_loss = (
                    (current_price - info["price"]) / info["price"] * 100
                )  # 평가손익 계산
                message += (
                    f"*{ticker}*\n"
                    f"매수 가격: `{info['price']:,}` KRW\n"  # 천 단위 구분자 추가
                    f"현재 가격: `{current_price:,}` KRW\n"  # 천 단위 구분자 추가
                    f"목표 매도가: `{sell_price:,}` KRW\n"  # 천 단위 구분자 추가
                    f"평가손익: `{profit_or_loss:.2f}%`\n\n"
                )
            send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
        else:
            send_telegram_message(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                "현재 보유 중인 종목이 없습니다. 매수 타점을 잡는 중입니다.",
            )

        krw_balance = get_balance("KRW")
        investment_limit = krw_balance * INVESTMENT_RATIO
        num_investments = len(invested)

        for ticker in all_tickers:
            current_price = get_current_price(ticker)
            avg_volume = get_moving_average_volume(ticker, "minute1", 5)  # 5분 이동 평균 거래량
            last_volume = get_moving_average_volume(ticker, "minute1", 1)  # 마지막 1분 거래량
            atr = get_atr(ticker, "day", 1)  # 1일 ATR

            if avg_volume is None or last_volume is None or atr is None:
                continue

            volume_ratio = last_volume / avg_volume
            dynamic_take_profit_ratio = 1 + (atr / current_price)
            dynamic_stop_loss_ratio = 1 - (atr / current_price)

            # 매수 조건 검사 및 매수 처리
            if (
                volume_ratio > VOLUME_SURGE_THRESHOLD
                and num_investments < MAX_INVESTMENT_COUNT
                and krw_balance > MINIMUM_KRW_ORDER
                and investment_limit > MINIMUM_KRW_ORDER
            ):
                buy_result = upbit.buy_market_order(ticker, investment_limit)
                invested[ticker] = {
                    "price": current_price,
                    "volume": investment_limit / current_price,
                    "stop_loss": current_price * dynamic_stop_loss_ratio,
                    "take_profit": current_price * dynamic_take_profit_ratio,
                }
                num_investments += 1
                message = f"{ticker}에 투자했습니다: {buy_result}"
                print(message)
                send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)

            # 매도 조건 검사 및 매도 처리
            if ticker in invested:
                investment_info = invested[ticker]
                if current_price >= investment_info["take_profit"]:
                    sell_result = upbit.sell_market_order(
                        ticker, investment_info["volume"]
                    )
                    message = f"익절 매도 주문 결과: {sell_result}"
                    print(message)
                    send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
                    del invested[ticker]
                elif current_price <= investment_info["stop_loss"]:
                    sell_result = upbit.sell_market_order(
                        ticker, investment_info["volume"]
                    )
                    message = f"손절 매도 주문 결과: {sell_result}"
                    print(message)
                    send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
                    del invested[ticker]

    except Exception as e:
        error_message = f"에러 발생: {e}"
        print(error_message)
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, error_message)
        time.sleep(1)
