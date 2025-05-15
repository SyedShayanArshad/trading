
from flask import Flask
import requests
import time
import pandas as pd
from ta.momentum import RSIIndicator
import os
app = Flask(__name__)

def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Telegram message error: {e}")

@app.route('/run-check')
def get_coins_with_high_change_and_recent_high():
    try:
        url_ticker = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url_ticker)
        response.raise_for_status()
        tickers = response.json()

        high_change_coins = []
        for ticker in tickers:
            symbol = ticker['symbol']
            if symbol.endswith('USDT'):
                change_percent = float(ticker['priceChangePercent'])
                if change_percent > 10:
                    high_change_coins.append({
                        'symbol': symbol,
                        'price': float(ticker['lastPrice']),
                        'change_percent': change_percent,
                        'high_price_24h': float(ticker['highPrice'])
                    })

        filtered_coins = []
        for coin in high_change_coins:
            symbol = coin['symbol']
            high_price_24h = coin['high_price_24h']

            url_kline = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': '1m',
                'limit': 20
            }
            response_kline = requests.get(url_kline, params=params)
            response_kline.raise_for_status()
            klines = response_kline.json()

            high_prices = [float(kline[2]) for kline in klines]
            close_prices = [float(kline[4]) for kline in klines]

            if not close_prices or len(close_prices) < 14:
                continue

            rsi_series = RSIIndicator(pd.Series(close_prices)).rsi()
            current_rsi = rsi_series.iloc[-1]
            recent_high = max(high_prices[-10:])

            if recent_high >= high_price_24h * 0.99:
                coin['rsi'] = current_rsi
                filtered_coins.append(coin)

            time.sleep(0.2)

        filtered_coins.sort(key=lambda x: x['change_percent'], reverse=True)

        if filtered_coins:
            print(f"\nCoins likely overbought (as of {time.ctime()}):")
            print("-" * 80)
            print(f"{'Symbol':<15} {'Price':<12} {'24h Change %':<15} {'24h High':<12} {'RSI':<8}")
            print("-" * 80)

            # Create a professional Telegram message
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = (
                "📊 *Crypto Alert: Overbought Coins Detected* 📊\n"
                f"🕒 *Time*: {current_time}\n\n"
                "The following coins have high 24-hour price changes and are near their 24-hour highs, indicating potential overbought conditions (RSI included).\n\n"
                "🔍 *Coin Details*:\n"
            )
            for coin in filtered_coins:
                print(f"{coin['symbol']:<15} {coin['price']:<12.6f} {coin['change_percent']:<15.2f} {coin['high_price_24h']:<12.6f} {coin['rsi']:<8.2f}")
                message += (
                    f"• *{coin['symbol']}*\n"
                    f"  💰 Price: ${coin['price']:.6f}\n"
                    f"  📈 24h Change: {coin['change_percent']:.2f}%\n"
                    f"  🎯 24h High: ${coin['high_price_24h']:.6f}\n"
                    f"  ⚖️ RSI: {coin['rsi']:.2f}\n\n"
                )
            message += (
                "📝 *Note*: High RSI (>70) may suggest overbought conditions. Always conduct your own research before trading.\n"
            )

            send_telegram_message(message)            
            return "Telegram message sent."
        else:
            return "No overbought coins found."

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run()
