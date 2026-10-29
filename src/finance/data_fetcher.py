"""Fetch company data, key metrics and financial statements from yfinance."""

import pandas as pd
import yfinance as yf

KEY_METRICS = {
    "market_cap": "marketCap",
    "pe_ratio": "trailingPE",
    "forward_pe_ratio": "forwardPE",
    "peg_ratio": "pegRatio",
    "dividend_yield": "dividendYield",
    "beta": "beta",
}

# Only the rows needed for analysis; the full statements are much larger.
STATEMENT_ROWS = {
    "income": [
        "Total Revenue",
        "Gross Profit",
        "Operating Income",
        "Net Income",
        "EBITDA",
        "Diluted EPS",
        "Interest Expense",
    ],
    "balance_sheet": [
        "Total Assets",
        "Current Assets",
        "Current Liabilities",
        "Stockholders Equity",
        "Total Debt",
        "Cash And Cash Equivalents",
    ],
    "cashflow": [
        "Operating Cash Flow",
        "Capital Expenditure",
        "Free Cash Flow",
    ],
}

STATEMENT_ATTRIBUTES = {
    "income": "income_stmt",
    "balance_sheet": "balance_sheet",
    "cashflow": "cashflow",
}

# formatting to what yfinance expects 
def normalize_ticker(ticker: str) -> str:
    # yfinance uses dashes for share classes, e.g. BRK-B.
    return ticker.strip().upper().replace(".", "-")

# Returns company name, sector, industry and currency
def fetch_company_info(stock: yf.Ticker) -> dict:
    info = stock.info
    name = info.get("longName") or info.get("shortName")
    if not name:
        raise ValueError(f"No yfinance data found for {stock.ticker}.")
    return {
        "company_name": name,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("financialCurrency") or info.get("currency"),
    }

# 
def fetch_key_metrics(stock: yf.Ticker) -> dict:
    # Ticker caches info, so this does not download it again.
    info = stock.info
    return {name: info.get(key) for name, key in KEY_METRICS.items()}


def statement_to_dict(df: pd.DataFrame, rows: list[str]) -> dict:
    """Return {row: {period_end: value}}, leaving out rows and values that are missing."""
    if df is None or df.empty:
        return {}
    result = {}
    for row in rows:
        if row not in df.index:
            continue
        values = {
            column.date().isoformat(): float(value)
            for column, value in df.loc[row].items()
            if pd.notna(value)
        }
        if values:
            result[row] = values
    return result

# Returns annual and quarterly income, balance sheet and cash flow 
def fetch_statements(stock: yf.Ticker) -> dict:
    statements = {}
    for name, attribute in STATEMENT_ATTRIBUTES.items():
        rows = STATEMENT_ROWS[name]
        statements[name] = statement_to_dict(getattr(stock, attribute), rows)
        statements[f"quarterly_{name}"] = statement_to_dict(
            getattr(stock, f"quarterly_{attribute}"), rows
        )
    return statements


def fetch_financial_data(ticker: str) -> dict:
    ticker = normalize_ticker(ticker)
    stock = yf.Ticker(ticker)
    return {
        "ticker": ticker,
        "company_info": fetch_company_info(stock),
        "key_metrics": fetch_key_metrics(stock),
        "statements": fetch_statements(stock),
    }
