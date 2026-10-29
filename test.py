import yfinance as yf

ticker = yf.Ticker("EQNR")

print(ticker.income_stmt)