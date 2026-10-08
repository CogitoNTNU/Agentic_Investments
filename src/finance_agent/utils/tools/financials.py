from langchain.tools import tool
import yfinance as yf

# financials of single ticker 
@tool
def get_income(ticker: str):
    """Get income statement for a given stock ticker using yfinance."""
    ticker = yf.Ticker(ticker)
    return ticker.income_stmt

#quarterly_income 
@tool 
def get_quarterly_income(ticker: str):
    ticker = yf.Ticker(ticker)
    return ticker.quarterly_income_stmt


#balance sheet 
@tool 
def get_balance_sheet(ticker: str):
    ticker = yf.Ticker(ticker)
    return ticker.balance_sheet

@tool
def get_balance_sheet_period(ticker: str, freq: str):
    ticker_obj = yf.Ticker(ticker)

    return ticker_obj.get_balance_sheet(freq=freq)

# cashflow 
@tool 
def get_cashflow(ticker: str):
    ticker = yf.Ticker(ticker)
    return ticker.cashflow

@tool
def get_financials(
        ticker: str, 
        statement: str
    ) -> str:
    """Get financials for a given stock ticker using yfinance.
    Available statements: income, quarterly_income, balance_sheet, quarterly_balance_sheet, cashflow, quarterly_cashflow.
    """
    ticker = yf.Ticker(ticker)

    statements = {
        "income": ticker.income_stmt,
        "quarterly_income": ticker.quarterly_income_stmt,
        "balance_sheet": ticker.balance_sheet,
        "quarterly_balance_sheet": ticker.quarterly_balance_sheet,
        "cashflow": ticker.cashflow,
        "quarterly_cashflow": ticker.quarterly_cashflow,
    }
    return statements.get(statement, "Invalid statement type. Choose from: income, quarterly_income, balance_sheet, quarterly_balance_sheet, cashflow, quarterly_cashflow.")
