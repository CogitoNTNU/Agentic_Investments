from langchain.tools import tool
import yfinance as yf
from linear_models import LinearRegression, LogisticRegression

# financials of single ticker 
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

    if statement not in statements: 
        return "Invalid statement type."

    df = statements[statement]

    if df is None or df.empty: 
        return f"No financial data available for {ticker}"

    # rows become financial metrics; columns are reporting dates.

    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    #return statements.get(statement, "Invalid statement type. Choose from: income, quarterly_income, balance_sheet, quarterly_balance_sheet, cashflow, quarterly_cashflow.")
    return df.to_json(orient="split", date_format="iso")

@tool
def regression(type: str, data: str):
    """Perform regression analysis on a given stock ticker using yfinance."""
    if type == "linear":
        LR = LinearRegression(0.001, 1000)
        X = data[['Net_Activity']]
        y = data['Energy']

        LR.fit(X, y)
        return "Performing linear regression analysis."