import yfinance as finance 

def get_stock_price(ticker : str):
    stock = finance.Ticker(ticker)
    history = stock.history(period = "1d")
    price = history["Close"].iloc[-1]

    return {
        "ticker": ticker.upper(),
        "price": round(float(price), 2)
    }

def get_company_info(ticker: str): 
    stock = finance.Ticker(ticker)
    info = stock.info

    return {
"ticker": ticker.upper(),
"company_name": info.get("longName"),
"sector": info.get("sector"),
"industry": info.get("industry"),
"market_cap": info.get("marketCap"),
"trailing_pe": info.get("trailingPE"),
"forward_pe": info.get("forwardPE"),
"profit_margin": info.get("profitMargins"),
"revenue_growth": info.get("revenueGrowth")
}

